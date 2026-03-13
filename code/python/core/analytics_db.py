# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Database abstraction layer for analytics logging system.

Supports both SQLite (local development) and PostgreSQL (production).
Uses async connections for PostgreSQL to avoid blocking the event loop.
Reads DATABASE_URL (or ANALYTICS_DATABASE_URL fallback).
Uses AsyncConnectionPool for PostgreSQL to avoid per-query connection overhead.
"""

import os
import sqlite3
import asyncio
from typing import Any, List, Dict, Optional, Tuple
from pathlib import Path
from misc.logger.logging_config_helper import get_configured_logger

logger = get_configured_logger("analytics_db")

# Try to import PostgreSQL libraries (optional)
try:
    import psycopg
    from psycopg.rows import dict_row
    from psycopg_pool import AsyncConnectionPool
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    logger.warning("PostgreSQL libraries not available, analytics falling back to SQLite")


def get_project_root_db_path() -> str:
    """Get absolute path to analytics database from project root."""
    current_file = Path(__file__).resolve()
    # analytics_db.py -> core/ -> python/ -> code/ -> project root
    project_root = current_file.parent.parent.parent.parent
    db_path = project_root / "data" / "analytics" / "query_logs.db"
    return str(db_path)


class AnalyticsDB:
    """
    Database abstraction layer for analytics tables.

    PostgreSQL: uses psycopg async connection pool.
    SQLite: uses sync connections wrapped in asyncio.to_thread (dev only).
    """

    _instance = None

    @classmethod
    def get_instance(cls) -> 'AnalyticsDB':
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = get_project_root_db_path()

        # Unified: prefer POSTGRES_CONNECTION_STRING, fall back to DATABASE_URL / ANALYTICS_DATABASE_URL (legacy)
        self.database_url = (os.environ.get('POSTGRES_CONNECTION_STRING')
                             or os.environ.get('DATABASE_URL')
                             or os.environ.get('ANALYTICS_DATABASE_URL'))
        self.db_path = Path(db_path)
        self.db_type = 'postgres' if self.database_url and POSTGRES_AVAILABLE else 'sqlite'
        self._initialized = False
        self._pool = None
        self._pool_lock = asyncio.Lock()

        logger.info(f"Analytics database type: {self.db_type}")

        if self.db_type == 'sqlite':
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            logger.info(f"Using SQLite analytics database at: {self.db_path.absolute()}")
        else:
            masked = self.database_url.split('@')[1] if '@' in self.database_url else 'connected'
            logger.info(f"Using PostgreSQL analytics database: {masked}")

    async def initialize(self):
        """Initialize database tables (async). Called once at startup."""
        if self._initialized:
            return
        if self.db_type == 'sqlite':
            await asyncio.to_thread(self._init_database_sync)
        else:
            await self._init_database_async()
        self._initialized = True

    # ── Async query interface ─────────────────────────────────────

    async def fetchone(self, query: str, params: Optional[Tuple] = None) -> Optional[Dict]:
        """Execute query and return one row as dict."""
        if self.db_type == 'postgres':
            return await self._pg_fetchone(query, params)
        else:
            return await asyncio.to_thread(self._sqlite_fetchone, query, params)

    async def fetchall(self, query: str, params: Optional[Tuple] = None) -> List[Dict]:
        """Execute query and return all rows as list of dicts."""
        if self.db_type == 'postgres':
            return await self._pg_fetchall(query, params)
        else:
            return await asyncio.to_thread(self._sqlite_fetchall, query, params)

    async def execute(self, query: str, params: Optional[Tuple] = None):
        """Execute a query (INSERT/UPDATE/DELETE) and commit."""
        if self.db_type == 'postgres':
            await self._pg_execute(query, params)
        else:
            await asyncio.to_thread(self._sqlite_execute, query, params)

    # ── PostgreSQL connection pool ───────────────────────────────

    async def _get_pool(self) -> 'AsyncConnectionPool':
        """Get or create the async connection pool (lazy init, thread-safe)."""
        if self._pool is None:
            async with self._pool_lock:
                if self._pool is None:
                    self._pool = AsyncConnectionPool(
                        conninfo=self.database_url,
                        min_size=1,
                        max_size=5,
                        open=False,
                    )
                    await self._pool.open()
                    logger.info("Analytics DB connection pool initialized")
        return self._pool

    async def close(self):
        """Close the connection pool. Call on shutdown."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("Analytics DB connection pool closed")

    # ── PostgreSQL async methods ──────────────────────────────────

    def _adapt_query_pg(self, query: str) -> str:
        """Convert ? placeholders to %s for psycopg."""
        return query.replace('?', '%s')

    async def _pg_fetchone(self, query: str, params: Optional[Tuple] = None) -> Optional[Dict]:
        query = self._adapt_query_pg(query)
        pool = await self._get_pool()
        async with pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(query, params)
                row = await cur.fetchone()
                return dict(row) if row else None

    async def _pg_fetchall(self, query: str, params: Optional[Tuple] = None) -> List[Dict]:
        query = self._adapt_query_pg(query)
        pool = await self._get_pool()
        async with pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(query, params)
                rows = await cur.fetchall()
                return [dict(r) for r in rows]

    async def _pg_execute(self, query: str, params: Optional[Tuple] = None):
        query = self._adapt_query_pg(query)
        pool = await self._get_pool()
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
            await conn.commit()

    # ── SQLite sync methods (wrapped in to_thread) ────────────────

    def _sqlite_connect(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _sqlite_fetchone(self, query: str, params: Optional[Tuple] = None) -> Optional[Dict]:
        conn = self._sqlite_connect()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def _sqlite_fetchall(self, query: str, params: Optional[Tuple] = None) -> List[Dict]:
        conn = self._sqlite_connect()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def _sqlite_execute(self, query: str, params: Optional[Tuple] = None):
        conn = self._sqlite_connect()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            conn.commit()
        finally:
            conn.close()

    # ── Initialization ────────────────────────────────────────────

    async def _init_database_async(self):
        """Create tables on PostgreSQL."""
        try:
            async with await psycopg.AsyncConnection.connect(
                self.database_url, autocommit=True
            ) as conn:
                async with conn.cursor() as cur:
                    for table_name, create_sql in self._get_postgres_schema().items():
                        try:
                            await cur.execute(create_sql)
                            logger.debug(f"Analytics table ensured: {table_name}")
                        except Exception as e:
                            logger.error(f"Failed to create analytics table {table_name}: {e}")
                            raise

                    for index_sql in self.get_index_sql():
                        try:
                            await cur.execute(index_sql)
                        except Exception as e:
                            logger.warning(f"Analytics index creation skipped: {e}")

            logger.info("Analytics database initialized (PostgreSQL async)")
        except Exception as e:
            logger.error(f"Failed to initialize analytics database: {e}", exc_info=True)

    def _init_database_sync(self):
        """Create tables on SQLite."""
        try:
            conn = self._sqlite_connect()
            cursor = conn.cursor()

            for table_name, create_sql in self._get_sqlite_schema().items():
                try:
                    cursor.execute(create_sql)
                    logger.debug(f"Analytics table ensured: {table_name}")
                except Exception as e:
                    logger.error(f"Failed to create analytics table {table_name}: {e}")
                    raise

            for index_sql in self.get_index_sql():
                try:
                    cursor.execute(index_sql)
                except Exception as e:
                    logger.warning(f"Analytics index creation skipped: {e}")

            conn.commit()
            conn.close()
            logger.info("Analytics database initialized (SQLite)")
        except Exception as e:
            logger.error(f"Failed to initialize analytics database: {e}", exc_info=True)

    # ── Schema definitions ────────────────────────────────────────

    def _get_sqlite_schema(self) -> Dict[str, str]:
        """SQLite schema definitions."""
        return {
            'queries': """
                CREATE TABLE IF NOT EXISTS queries (
                    query_id TEXT PRIMARY KEY,
                    timestamp REAL NOT NULL,
                    user_id TEXT NOT NULL,
                    session_id TEXT,
                    conversation_id TEXT,
                    query_text TEXT NOT NULL,
                    decontextualized_query TEXT,
                    site TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    model TEXT,
                    parent_query_id TEXT,
                    org_id TEXT,
                    latency_total_ms REAL,
                    latency_retrieval_ms REAL,
                    latency_ranking_ms REAL,
                    latency_generation_ms REAL,
                    num_results_retrieved INTEGER,
                    num_results_ranked INTEGER,
                    num_results_returned INTEGER,
                    cost_usd REAL,
                    error_occurred INTEGER DEFAULT 0,
                    error_message TEXT
                )
            """,
            'retrieved_documents': """
                CREATE TABLE IF NOT EXISTS retrieved_documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_id TEXT NOT NULL,
                    doc_url TEXT NOT NULL,
                    doc_title TEXT,
                    doc_snippet TEXT,
                    vector_similarity_score REAL,
                    keyword_boost_score REAL,
                    final_retrieval_score REAL,
                    retrieval_position INTEGER NOT NULL,
                    retrieval_method TEXT,
                    doc_metadata TEXT,
                    FOREIGN KEY (query_id) REFERENCES queries(query_id) ON DELETE CASCADE
                )
            """,
            'ranking_scores': """
                CREATE TABLE IF NOT EXISTS ranking_scores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_id TEXT NOT NULL,
                    doc_url TEXT NOT NULL,
                    llm_score REAL,
                    llm_reasoning TEXT,
                    text_search_score REAL,
                    mmr_score REAL,
                    xgboost_score REAL,
                    final_score REAL,
                    ranking_position INTEGER,
                    ranking_model TEXT,
                    FOREIGN KEY (query_id) REFERENCES queries(query_id) ON DELETE CASCADE
                )
            """,
            'user_interactions': """
                CREATE TABLE IF NOT EXISTS user_interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_id TEXT NOT NULL,
                    doc_url TEXT NOT NULL,
                    interaction_type TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    position INTEGER,
                    dwell_time_ms INTEGER,
                    scroll_depth_percent REAL,
                    interaction_metadata TEXT,
                    FOREIGN KEY (query_id) REFERENCES queries(query_id) ON DELETE CASCADE
                )
            """,
            'tier_6_enrichment': """
                CREATE TABLE IF NOT EXISTS tier_6_enrichment (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    cache_hit INTEGER DEFAULT 0,
                    latency_ms INTEGER,
                    timeout_occurred INTEGER DEFAULT 0,
                    result_count INTEGER,
                    timestamp REAL NOT NULL,
                    metadata TEXT,
                    schema_version INTEGER DEFAULT 2,
                    FOREIGN KEY (query_id) REFERENCES queries(query_id) ON DELETE CASCADE
                )
            """
        }

    def _get_postgres_schema(self) -> Dict[str, str]:
        """PostgreSQL schema definitions."""
        return {
            'queries': """
                CREATE TABLE IF NOT EXISTS queries (
                    query_id VARCHAR(255) PRIMARY KEY,
                    timestamp DOUBLE PRECISION NOT NULL,
                    user_id VARCHAR(255) NOT NULL,
                    session_id VARCHAR(255),
                    conversation_id VARCHAR(255),
                    query_text TEXT NOT NULL,
                    decontextualized_query TEXT,
                    site VARCHAR(100) NOT NULL,
                    mode VARCHAR(50) NOT NULL,
                    model VARCHAR(100),
                    parent_query_id VARCHAR(255),
                    org_id VARCHAR(255),
                    latency_total_ms DOUBLE PRECISION,
                    latency_retrieval_ms DOUBLE PRECISION,
                    latency_ranking_ms DOUBLE PRECISION,
                    latency_generation_ms DOUBLE PRECISION,
                    num_results_retrieved INTEGER,
                    num_results_ranked INTEGER,
                    num_results_returned INTEGER,
                    cost_usd DOUBLE PRECISION,
                    error_occurred INTEGER DEFAULT 0,
                    error_message TEXT
                )
            """,
            'retrieved_documents': """
                CREATE TABLE IF NOT EXISTS retrieved_documents (
                    id SERIAL PRIMARY KEY,
                    query_id VARCHAR(255) NOT NULL,
                    doc_url TEXT NOT NULL,
                    doc_title TEXT,
                    doc_snippet TEXT,
                    vector_similarity_score DOUBLE PRECISION,
                    keyword_boost_score DOUBLE PRECISION,
                    final_retrieval_score DOUBLE PRECISION,
                    retrieval_position INTEGER NOT NULL,
                    retrieval_method VARCHAR(50),
                    doc_metadata TEXT,
                    FOREIGN KEY (query_id) REFERENCES queries(query_id) ON DELETE CASCADE
                )
            """,
            'ranking_scores': """
                CREATE TABLE IF NOT EXISTS ranking_scores (
                    id SERIAL PRIMARY KEY,
                    query_id VARCHAR(255) NOT NULL,
                    doc_url TEXT NOT NULL,
                    llm_score DOUBLE PRECISION,
                    llm_reasoning TEXT,
                    text_search_score DOUBLE PRECISION,
                    mmr_score DOUBLE PRECISION,
                    xgboost_score DOUBLE PRECISION,
                    final_score DOUBLE PRECISION,
                    ranking_position INTEGER,
                    ranking_model VARCHAR(100),
                    FOREIGN KEY (query_id) REFERENCES queries(query_id) ON DELETE CASCADE
                )
            """,
            'user_interactions': """
                CREATE TABLE IF NOT EXISTS user_interactions (
                    id SERIAL PRIMARY KEY,
                    query_id VARCHAR(255) NOT NULL,
                    doc_url TEXT NOT NULL,
                    interaction_type VARCHAR(50) NOT NULL,
                    timestamp DOUBLE PRECISION NOT NULL,
                    position INTEGER,
                    dwell_time_ms INTEGER,
                    scroll_depth_percent DOUBLE PRECISION,
                    interaction_metadata TEXT,
                    FOREIGN KEY (query_id) REFERENCES queries(query_id) ON DELETE CASCADE
                )
            """,
            'tier_6_enrichment': """
                CREATE TABLE IF NOT EXISTS tier_6_enrichment (
                    id SERIAL PRIMARY KEY,
                    query_id VARCHAR(255) NOT NULL,
                    source_type VARCHAR(50) NOT NULL,
                    cache_hit INTEGER DEFAULT 0,
                    latency_ms INTEGER,
                    timeout_occurred INTEGER DEFAULT 0,
                    result_count INTEGER,
                    timestamp DOUBLE PRECISION NOT NULL,
                    metadata TEXT,
                    schema_version INTEGER DEFAULT 2,
                    FOREIGN KEY (query_id) REFERENCES queries(query_id) ON DELETE CASCADE
                )
            """
        }

    def get_index_sql(self) -> List[str]:
        """Get SQL statements for creating indexes. Same syntax for SQLite and PostgreSQL."""
        return [
            "CREATE INDEX IF NOT EXISTS idx_queries_timestamp ON queries(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_queries_user_id ON queries(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_queries_mode ON queries(mode)",
            "CREATE INDEX IF NOT EXISTS idx_queries_org_id ON queries(org_id)",
            "CREATE INDEX IF NOT EXISTS idx_retrieved_documents_query_id ON retrieved_documents(query_id)",
            "CREATE INDEX IF NOT EXISTS idx_ranking_scores_query_id ON ranking_scores(query_id)",
            "CREATE INDEX IF NOT EXISTS idx_user_interactions_query_id ON user_interactions(query_id)",
            "CREATE INDEX IF NOT EXISTS idx_tier_6_query ON tier_6_enrichment(query_id)",
            "CREATE INDEX IF NOT EXISTS idx_tier_6_source_type ON tier_6_enrichment(source_type)"
        ]

    # ── Deprecated sync interface (kept for backward compatibility) ─
    # analytics_handler.py and ranking_analytics_handler.py use these during
    # the transition period. Migrate callers to the async methods above.

    def get_schema_sql(self) -> Dict[str, str]:
        """[DEPRECATED] Use _get_sqlite_schema() / _get_postgres_schema() directly."""
        if self.db_type == 'postgres':
            return self._get_postgres_schema()
        else:
            return self._get_sqlite_schema()

    def connect(self):
        """[DEPRECATED] Create sync connection. Use async fetchone/fetchall/execute instead."""
        if self.db_type == 'postgres':
            return psycopg.connect(self.database_url, row_factory=dict_row)
        else:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            return conn

    def adapt_query(self, query: str) -> str:
        """[DEPRECATED] Use async methods which handle adaptation internally."""
        if self.db_type == 'postgres':
            return query.replace('?', '%s')
        return query

    def execute(self, conn, query: str, params: Optional[Tuple] = None):
        """[DEPRECATED] Use async self.execute(query, params) instead."""
        adapted_query = self.adapt_query(query)
        cursor = conn.cursor()
        if params:
            cursor.execute(adapted_query, params)
        else:
            cursor.execute(adapted_query)
        return cursor

    def executemany(self, conn, query: str, params_list: List[Tuple]):
        """[DEPRECATED] No async equivalent yet; migrate callers when needed."""
        adapted_query = self.adapt_query(query)
        cursor = conn.cursor()
        cursor.executemany(adapted_query, params_list)
        return cursor
