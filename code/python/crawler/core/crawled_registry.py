"""
crawled_registry.py - 已爬取文章的 SQLite 註冊表

取代原本的 txt 檔案系統，提供：
- URL 去重
- dateModified 判斷是否需要重爬
- content_hash 跨來源去重
- 統計查詢
- 失敗 URL 追蹤與重爬管理
"""

import hashlib
import logging
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from . import settings


class CrawledRegistry:
    """
    SQLite-based registry for tracking crawled articles.

    Schema:
        url: PRIMARY KEY
        source_id: 來源代號 (ltn, udn, cna, ...)
        date_published: 文章發布日期
        date_modified: 文章最後修改日期
        date_crawled: 爬取時間
        content_hash: 文章前 500 字的 hash，用於跨來源去重
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize the registry.

        Args:
            db_path: Path to SQLite database.
                    If None, uses default location in data/crawler/
        """
        if db_path is None:
            db_path = settings.DATA_DIR / "crawled_registry.db"

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.logger = logging.getLogger(self.__class__.__name__)
        self._conn: Optional[sqlite3.Connection] = None
        self._conn_lock = threading.Lock()

        self._init_db()
        self.logger.info(f"CrawledRegistry initialized: {self.db_path}")

    def _get_conn(self) -> sqlite3.Connection:
        """Get or create database connection (thread-safe)."""
        with self._conn_lock:
            if self._conn is None:
                self._conn = sqlite3.connect(
                    str(self.db_path), check_same_thread=False, timeout=30.0
                )
                self._conn.execute("PRAGMA journal_mode=WAL")
                self._conn.row_factory = sqlite3.Row
            return self._conn

    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS crawled_articles (
                url TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                date_published TEXT,
                date_modified TEXT,
                date_crawled TEXT NOT NULL,
                content_hash TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_source ON crawled_articles(source_id);
            CREATE INDEX IF NOT EXISTS idx_date_published ON crawled_articles(date_published);
            CREATE INDEX IF NOT EXISTS idx_content_hash ON crawled_articles(content_hash);

            -- Failed URLs tracking table
            CREATE TABLE IF NOT EXISTS failed_urls (
                url TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                error_type TEXT NOT NULL,
                error_message TEXT,
                failed_at TEXT NOT NULL,
                retry_count INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_failed_source ON failed_urls(source_id);
            CREATE INDEX IF NOT EXISTS idx_failed_at ON failed_urls(failed_at);
            CREATE INDEX IF NOT EXISTS idx_error_type ON failed_urls(error_type);
        """)
        conn.commit()

        # Migrate: add task_id and batch_id columns if not present
        self._migrate_add_lineage_columns(conn)

    def _migrate_add_lineage_columns(self, conn: sqlite3.Connection) -> None:
        """Add task_id and batch_id columns if they don't exist."""
        cursor = conn.execute("PRAGMA table_info(crawled_articles)")
        existing_cols = {row['name'] for row in cursor}

        for col_name in ('task_id', 'batch_id'):
            if col_name not in existing_cols:
                conn.execute(f"ALTER TABLE crawled_articles ADD COLUMN {col_name} TEXT")
                self.logger.info(f"Migrated: added {col_name} column to crawled_articles")

        try:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_task ON crawled_articles(task_id)")
        except sqlite3.OperationalError as e:
            self.logger.debug(f"Index idx_task creation skipped: {e}")

        conn.commit()

    def is_crawled(self, url: str) -> bool:
        """Check if URL has been crawled."""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT 1 FROM crawled_articles WHERE url = ?",
            (url,)
        )
        return cursor.fetchone() is not None

    def needs_update(self, url: str, new_date_modified: Optional[str]) -> bool:
        """
        Check if article needs to be re-crawled based on dateModified.

        Args:
            url: Article URL
            new_date_modified: New dateModified from the article

        Returns:
            True if article should be re-crawled
        """
        if new_date_modified is None:
            return False

        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT date_modified FROM crawled_articles WHERE url = ?",
            (url,)
        )
        row = cursor.fetchone()

        if row is None:
            return True  # Not crawled yet

        old_date_modified = row['date_modified']
        if old_date_modified is None:
            return True  # No previous dateModified, re-crawl to get it

        return new_date_modified > old_date_modified

    def mark_crawled(
        self,
        url: str,
        source_id: str,
        date_published: Optional[str] = None,
        date_modified: Optional[str] = None,
        content: Optional[str] = None,
        task_id: Optional[str] = None,
        batch_id: Optional[str] = None,
    ) -> None:
        """
        Mark an article as crawled.

        Args:
            url: Article URL
            source_id: Source identifier (ltn, udn, cna, ...)
            date_published: Article publish date (ISO format)
            date_modified: Article last modified date (ISO format)
            content: Article content for hash generation (first 500 chars used)
            task_id: Originating crawler task ID
            batch_id: Batch identifier
        """
        content_hash = None
        if content:
            # Use first 500 chars for hash
            content_hash = hashlib.sha256(content[:500].encode('utf-8')).hexdigest()[:16]

        date_crawled = datetime.now().isoformat()

        conn = self._get_conn()
        conn.execute("""
            INSERT OR REPLACE INTO crawled_articles
            (url, source_id, date_published, date_modified, date_crawled, content_hash, task_id, batch_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (url, source_id, date_published, date_modified, date_crawled, content_hash, task_id, batch_id))
        conn.commit()

    def find_duplicate_by_hash(self, content: str, exclude_url: Optional[str] = None) -> Optional[str]:
        """
        Find duplicate article by content hash.

        Args:
            content: Article content (first 500 chars used for hash)
            exclude_url: URL to exclude from search (for self-check)

        Returns:
            URL of duplicate article if found, None otherwise
        """
        content_hash = hashlib.sha256(content[:500].encode('utf-8')).hexdigest()[:16]

        conn = self._get_conn()
        if exclude_url:
            cursor = conn.execute(
                "SELECT url FROM crawled_articles WHERE content_hash = ? AND url != ?",
                (content_hash, exclude_url)
            )
        else:
            cursor = conn.execute(
                "SELECT url FROM crawled_articles WHERE content_hash = ?",
                (content_hash,)
            )

        row = cursor.fetchone()
        return row['url'] if row else None

    def get_count_by_source(self, source_id: str) -> int:
        """Get count of articles from a specific source."""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM crawled_articles WHERE source_id = ?",
            (source_id,)
        )
        return cursor.fetchone()['count']

    def get_count_by_date(self, date: str) -> int:
        """Get count of articles published on a specific date (YYYY-MM-DD)."""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM crawled_articles WHERE date_published LIKE ?",
            (f"{date}%",)
        )
        return cursor.fetchone()['count']

    def get_total_count(self) -> int:
        """Get total count of all crawled articles."""
        conn = self._get_conn()
        cursor = conn.execute("SELECT COUNT(*) as count FROM crawled_articles")
        return cursor.fetchone()['count']

    def get_stats(self) -> dict:
        """Get statistics about crawled articles."""
        conn = self._get_conn()

        # Total count
        total = self.get_total_count()

        # Count by source
        cursor = conn.execute("""
            SELECT source_id, COUNT(*) as count
            FROM crawled_articles
            GROUP BY source_id
            ORDER BY count DESC
        """)
        by_source = {row['source_id']: row['count'] for row in cursor}

        return {
            'total': total,
            'by_source': by_source
        }

    def get_date_range_by_source(self) -> Dict[str, Dict[str, Any]]:
        """
        Get the date range (oldest and newest) for each source.

        Returns:
            Dict mapping source_id to {oldest, newest, count}
        """
        conn = self._get_conn()

        cursor = conn.execute("""
            SELECT
                source_id,
                MIN(date_published) as oldest,
                MAX(date_published) as newest,
                COUNT(*) as count
            FROM crawled_articles
            WHERE date_published IS NOT NULL
            GROUP BY source_id
            ORDER BY source_id
        """)

        result = {}
        for row in cursor:
            result[row['source_id']] = {
                'oldest': row['oldest'],
                'newest': row['newest'],
                'count': row['count']
            }

        return result

    def get_monthly_counts(self, source_id: str) -> List[Dict[str, Any]]:
        """
        Get article counts grouped by month for a specific source.

        Args:
            source_id: Source identifier (ltn, udn, cna, ...)

        Returns:
            List of {month: "YYYY-MM", count: N} sorted by month
        """
        conn = self._get_conn()
        cursor = conn.execute("""
            SELECT strftime('%Y-%m', date_published) as month, COUNT(*) as count
            FROM crawled_articles
            WHERE source_id = ? AND date_published IS NOT NULL
            GROUP BY month
            ORDER BY month
        """, (source_id,))
        return [{"month": row["month"], "count": row["count"]} for row in cursor]

    def load_urls_for_source(self, source_id: str) -> set[str]:
        """
        Load all URLs for a specific source into a set.

        This is for backward compatibility with the old engine.py
        that uses an in-memory set for fast lookups.

        Args:
            source_id: Source identifier

        Returns:
            Set of URLs
        """
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT url FROM crawled_articles WHERE source_id = ?",
            (source_id,)
        )
        return {row['url'] for row in cursor}

    def migrate_from_txt(self, source_id: str, txt_path: Path) -> int:
        """
        Migrate URLs from old txt file format to SQLite.

        Args:
            source_id: Source identifier
            txt_path: Path to the txt file

        Returns:
            Number of URLs migrated
        """
        if not txt_path.exists():
            return 0

        count = 0
        with open(txt_path, 'r', encoding='utf-8') as f:
            for line in f:
                url = line.strip()
                if url and not self.is_crawled(url):
                    self.mark_crawled(url, source_id)
                    count += 1

        self.logger.info(f"Migrated {count} URLs from {txt_path}")
        return count

    # ==================== Failed URL Management ====================

    def mark_failed(
        self,
        url: str,
        source_id: str,
        error_type: str,
        error_message: Optional[str] = None
    ) -> None:
        """
        Mark a URL as failed.

        Args:
            url: The URL that failed
            source_id: Source identifier (ltn, udn, cna, ...)
            error_type: Type of error (blocked, parse_error, timeout, not_found)
            error_message: Optional error message details
        """
        failed_at = datetime.now().isoformat()
        conn = self._get_conn()

        # Check if already in failed_urls
        cursor = conn.execute(
            "SELECT retry_count FROM failed_urls WHERE url = ?",
            (url,)
        )
        row = cursor.fetchone()

        if row:
            # Update existing record, increment retry count
            conn.execute("""
                UPDATE failed_urls
                SET error_type = ?, error_message = ?, failed_at = ?, retry_count = retry_count + 1
                WHERE url = ?
            """, (error_type, error_message, failed_at, url))
        else:
            # Insert new record
            conn.execute("""
                INSERT INTO failed_urls (url, source_id, error_type, error_message, failed_at, retry_count)
                VALUES (?, ?, ?, ?, ?, 0)
            """, (url, source_id, error_type, error_message, failed_at))

        conn.commit()

    def remove_failed(self, url: str) -> bool:
        """
        Remove a URL from the failed list (usually after successful retry).

        Args:
            url: The URL to remove

        Returns:
            True if removed, False if not found
        """
        conn = self._get_conn()
        cursor = conn.execute("DELETE FROM failed_urls WHERE url = ?", (url,))
        conn.commit()
        return cursor.rowcount > 0

    def get_failed_urls(
        self,
        source_id: Optional[str] = None,
        error_type: Optional[str] = None,
        error_types: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get list of failed URLs.

        Args:
            source_id: Filter by source (optional)
            error_type: Filter by single error type (optional, deprecated)
            error_types: Filter by multiple error types (optional)
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            List of failed URL records
        """
        conn = self._get_conn()

        query = "SELECT * FROM failed_urls WHERE 1=1"
        params = []

        if source_id:
            query += " AND source_id = ?"
            params.append(source_id)

        # Support both single and multiple error types
        if error_types and len(error_types) > 0:
            placeholders = ",".join("?" * len(error_types))
            query += f" AND error_type IN ({placeholders})"
            params.extend(error_types)
        elif error_type:
            query += " AND error_type = ?"
            params.append(error_type)

        query += " ORDER BY failed_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor]

    def get_failed_stats(self) -> Dict[str, Any]:
        """
        Get statistics about failed URLs.

        Returns:
            Dict with total count, by source, and by error type
        """
        conn = self._get_conn()

        # Total count
        cursor = conn.execute("SELECT COUNT(*) as count FROM failed_urls")
        total = cursor.fetchone()['count']

        # Count by source
        cursor = conn.execute("""
            SELECT source_id, COUNT(*) as count
            FROM failed_urls
            GROUP BY source_id
            ORDER BY count DESC
        """)
        by_source = {row['source_id']: row['count'] for row in cursor}

        # Count by error type
        cursor = conn.execute("""
            SELECT error_type, COUNT(*) as count
            FROM failed_urls
            GROUP BY error_type
            ORDER BY count DESC
        """)
        by_error_type = {row['error_type']: row['count'] for row in cursor}

        return {
            'total': total,
            'by_source': by_source,
            'by_error_type': by_error_type
        }

    def clear_failed(self, source_id: Optional[str] = None, error_types: Optional[List[str]] = None) -> int:
        """
        Clear failed URLs.

        Args:
            source_id: If provided, only clear failed URLs for this source.
                      If None, clear all failed URLs.
            error_types: If provided, only clear URLs with these error types.

        Returns:
            Number of records deleted
        """
        conn = self._get_conn()

        query = "DELETE FROM failed_urls WHERE 1=1"
        params = []
        if source_id:
            query += " AND source_id = ?"
            params.append(source_id)
        if error_types:
            placeholders = ",".join("?" * len(error_types))
            query += f" AND error_type IN ({placeholders})"
            params.extend(error_types)

        cursor = conn.execute(query, params)
        conn.commit()
        return cursor.rowcount

    def has_blocked_failures(self, source_id: str) -> bool:
        """Check if there are any blocked failures for the given source."""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT 1 FROM failed_urls WHERE source_id = ? AND error_type = 'blocked' LIMIT 1",
            (source_id,)
        )
        return cursor.fetchone() is not None

    def get_failed_urls_for_retry(
        self,
        source_id: str,
        max_retries: int = 3,
        limit: int = 50
    ) -> List[str]:
        """
        Get failed URLs that are eligible for retry.

        Args:
            source_id: Source to get URLs for
            max_retries: Maximum retry count (URLs with more retries are excluded)
            limit: Maximum number of URLs to return

        Returns:
            List of URLs to retry
        """
        conn = self._get_conn()
        cursor = conn.execute("""
            SELECT url FROM failed_urls
            WHERE source_id = ? AND retry_count < ?
            ORDER BY failed_at ASC
            LIMIT ?
        """, (source_id, max_retries, limit))
        return [row['url'] for row in cursor]

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None


# Singleton instance for easy access
_registry: Optional[CrawledRegistry] = None


def get_registry() -> CrawledRegistry:
    """Get the singleton CrawledRegistry instance."""
    global _registry
    if _registry is None:
        _registry = CrawledRegistry()
    return _registry


def close_registry() -> None:
    """Close the singleton registry."""
    global _registry
    if _registry:
        _registry.close()
        _registry = None
