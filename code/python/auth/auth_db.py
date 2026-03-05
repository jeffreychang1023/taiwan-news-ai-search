"""
Database abstraction layer for authentication and session management.

Supports both SQLite (local development) and PostgreSQL (production).
Uses async connections for PostgreSQL to avoid blocking the event loop.
Shares ANALYTICS_DATABASE_URL with analytics_db.py.
"""

import os
import json
import sqlite3
import asyncio
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
from misc.logger.logging_config_helper import get_configured_logger

logger = get_configured_logger("auth_db")

# Try to import PostgreSQL libraries (optional)
try:
    import psycopg
    from psycopg.rows import dict_row
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    logger.warning("PostgreSQL libraries not available, auth falling back to SQLite")


def get_project_root_db_path() -> str:
    """Get absolute path to auth database from project root."""
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent.parent.parent
    db_path = project_root / "data" / "auth" / "auth.db"
    return str(db_path)


class AuthDB:
    """
    Database abstraction layer for auth + session tables.

    PostgreSQL: uses psycopg async connection pool.
    SQLite: uses sync connections wrapped in asyncio.to_thread (dev only).
    """

    _instance = None

    @classmethod
    def get_instance(cls) -> 'AuthDB':
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = get_project_root_db_path()

        self.database_url = os.environ.get('ANALYTICS_DATABASE_URL')
        self.db_path = Path(db_path)
        self.db_type = 'postgres' if self.database_url and POSTGRES_AVAILABLE else 'sqlite'
        self._initialized = False

        logger.info(f"Auth database type: {self.db_type}")

        if self.db_type == 'sqlite':
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            logger.info(f"Using SQLite auth database at: {self.db_path.absolute()}")
        else:
            masked = self.database_url.split('@')[1] if '@' in self.database_url else 'connected'
            logger.info(f"Using PostgreSQL auth database: {masked}")

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

    async def execute_returning(self, query: str, params: Optional[Tuple] = None) -> Optional[Dict]:
        """Execute INSERT/UPDATE with RETURNING clause (PostgreSQL only, SQLite fallback)."""
        if self.db_type == 'postgres':
            return await self._pg_fetchone(query, params)
        else:
            return await asyncio.to_thread(self._sqlite_execute, query, params)

    # ── PostgreSQL async methods ──────────────────────────────────

    def _adapt_query_pg(self, query: str) -> str:
        """Convert ? placeholders to %s for psycopg."""
        return query.replace('?', '%s')

    async def _pg_fetchone(self, query: str, params: Optional[Tuple] = None) -> Optional[Dict]:
        query = self._adapt_query_pg(query)
        async with await psycopg.AsyncConnection.connect(
            self.database_url, row_factory=dict_row
        ) as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                row = await cur.fetchone()
                return dict(row) if row else None

    async def _pg_fetchall(self, query: str, params: Optional[Tuple] = None) -> List[Dict]:
        query = self._adapt_query_pg(query)
        async with await psycopg.AsyncConnection.connect(
            self.database_url, row_factory=dict_row
        ) as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                rows = await cur.fetchall()
                return [dict(r) for r in rows]

    async def _pg_execute(self, query: str, params: Optional[Tuple] = None):
        query = self._adapt_query_pg(query)
        async with await psycopg.AsyncConnection.connect(
            self.database_url, autocommit=True
        ) as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)

    # ── SQLite sync methods (wrapped in to_thread) ────────────────

    def _sqlite_connect(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
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
                            logger.debug(f"Auth table ensured: {table_name}")
                        except Exception as e:
                            logger.error(f"Failed to create auth table {table_name}: {e}")

                    for index_sql in self._get_index_sql():
                        try:
                            await cur.execute(index_sql)
                        except Exception:
                            pass

            logger.info("Auth database initialized (PostgreSQL async)")
        except Exception as e:
            logger.error(f"Failed to initialize auth database: {e}", exc_info=True)

    def _init_database_sync(self):
        """Create tables on SQLite."""
        try:
            conn = self._sqlite_connect()
            cursor = conn.cursor()

            for table_name, create_sql in self._get_sqlite_schema().items():
                try:
                    cursor.execute(create_sql)
                    logger.debug(f"Auth table ensured: {table_name}")
                except Exception as e:
                    logger.error(f"Failed to create auth table {table_name}: {e}")

            for index_sql in self._get_index_sql():
                try:
                    cursor.execute(index_sql)
                except Exception:
                    pass

            conn.commit()
            conn.close()
            logger.info("Auth database initialized (SQLite)")
        except Exception as e:
            logger.error(f"Failed to initialize auth database: {e}", exc_info=True)

    # ── Legacy sync interface (for backward compat during transition) ─

    def connect(self):
        """Create sync connection. Use async methods instead when possible."""
        if self.db_type == 'postgres':
            return psycopg.connect(self.database_url, row_factory=dict_row)
        else:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            return conn

    def adapt_query(self, query: str) -> str:
        if self.db_type == 'postgres':
            return query.replace('?', '%s')
        return query

    # ── Schema definitions ────────────────────────────────────────

    def _get_sqlite_schema(self) -> Dict[str, str]:
        return {
            'organizations': """
                CREATE TABLE IF NOT EXISTS organizations (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    slug TEXT NOT NULL UNIQUE,
                    plan TEXT NOT NULL DEFAULT 'free',
                    max_members INTEGER NOT NULL DEFAULT 5,
                    settings TEXT DEFAULT '{}',
                    storage_quota_gb INTEGER DEFAULT 5,
                    monthly_search_limit INTEGER DEFAULT 1000,
                    created_at REAL NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1
                )
            """,
            'users': """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    name TEXT NOT NULL,
                    email_verified INTEGER NOT NULL DEFAULT 0,
                    email_verification_token TEXT,
                    password_reset_token TEXT,
                    password_reset_expires REAL,
                    last_login REAL,
                    created_at REAL NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1
                )
            """,
            'org_memberships': """
                CREATE TABLE IF NOT EXISTS org_memberships (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    org_id TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'member',
                    invited_by TEXT,
                    status TEXT NOT NULL DEFAULT 'active',
                    accepted_at REAL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE
                )
            """,
            'invitations': """
                CREATE TABLE IF NOT EXISTS invitations (
                    id TEXT PRIMARY KEY,
                    org_id TEXT NOT NULL,
                    email TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'member',
                    invited_by TEXT NOT NULL,
                    token TEXT NOT NULL UNIQUE,
                    expires_at REAL NOT NULL,
                    accepted_at REAL,
                    created_at REAL NOT NULL,
                    FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY (invited_by) REFERENCES users(id)
                )
            """,
            'refresh_tokens': """
                CREATE TABLE IF NOT EXISTS refresh_tokens (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE,
                    expires_at REAL NOT NULL,
                    created_at REAL NOT NULL,
                    revoked_at REAL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """,
            'login_attempts': """
                CREATE TABLE IF NOT EXISTS login_attempts (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL,
                    ip_address TEXT,
                    success INTEGER NOT NULL DEFAULT 0,
                    attempted_at REAL NOT NULL
                )
            """,
            'search_sessions': """
                CREATE TABLE IF NOT EXISTS search_sessions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    org_id TEXT NOT NULL,
                    title TEXT,
                    conversation_history TEXT DEFAULT '[]',
                    session_history TEXT DEFAULT '[]',
                    chat_history TEXT DEFAULT '[]',
                    accumulated_articles TEXT DEFAULT '[]',
                    pinned_messages TEXT DEFAULT '[]',
                    pinned_news_cards TEXT DEFAULT '[]',
                    research_report TEXT DEFAULT '{}',
                    user_feedback TEXT,
                    admin_note TEXT,
                    visibility TEXT DEFAULT 'private',
                    team_comments TEXT DEFAULT '[]',
                    is_archived INTEGER DEFAULT 0,
                    deleted_at REAL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (org_id) REFERENCES organizations(id)
                )
            """,
            'org_folders': """
                CREATE TABLE IF NOT EXISTS org_folders (
                    id TEXT PRIMARY KEY,
                    org_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY (created_by) REFERENCES users(id)
                )
            """,
            'org_folder_sessions': """
                CREATE TABLE IF NOT EXISTS org_folder_sessions (
                    folder_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    added_at REAL NOT NULL,
                    PRIMARY KEY (folder_id, session_id),
                    FOREIGN KEY (folder_id) REFERENCES org_folders(id) ON DELETE CASCADE,
                    FOREIGN KEY (session_id) REFERENCES search_sessions(id) ON DELETE CASCADE
                )
            """,
            'session_shares': """
                CREATE TABLE IF NOT EXISTS session_shares (
                    session_id TEXT NOT NULL,
                    shared_with_user_id TEXT NOT NULL,
                    shared_at REAL NOT NULL,
                    PRIMARY KEY (session_id, shared_with_user_id),
                    FOREIGN KEY (session_id) REFERENCES search_sessions(id) ON DELETE CASCADE,
                    FOREIGN KEY (shared_with_user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """,
            'user_preferences': """
                CREATE TABLE IF NOT EXISTS user_preferences (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    org_id TEXT NOT NULL,
                    preference_key TEXT NOT NULL,
                    preference_value TEXT NOT NULL,
                    updated_at REAL NOT NULL,
                    UNIQUE(user_id, org_id, preference_key),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (org_id) REFERENCES organizations(id)
                )
            """,
            'audit_logs': """
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id TEXT PRIMARY KEY,
                    user_id TEXT,
                    org_id TEXT,
                    action TEXT NOT NULL,
                    target_type TEXT,
                    target_id TEXT,
                    details TEXT,
                    ip_address TEXT,
                    created_at REAL NOT NULL
                )
            """
        }

    def _get_postgres_schema(self) -> Dict[str, str]:
        return {
            'organizations': """
                CREATE TABLE IF NOT EXISTS organizations (
                    id UUID PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    slug VARCHAR(255) NOT NULL UNIQUE,
                    plan VARCHAR(50) NOT NULL DEFAULT 'free',
                    max_members INTEGER NOT NULL DEFAULT 5,
                    settings TEXT DEFAULT '{}',
                    storage_quota_gb INTEGER DEFAULT 5,
                    monthly_search_limit INTEGER DEFAULT 1000,
                    created_at DOUBLE PRECISION NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE
                )
            """,
            'users': """
                CREATE TABLE IF NOT EXISTS users (
                    id UUID PRIMARY KEY,
                    email VARCHAR(255) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    email_verified BOOLEAN NOT NULL DEFAULT FALSE,
                    email_verification_token VARCHAR(255),
                    password_reset_token VARCHAR(255),
                    password_reset_expires DOUBLE PRECISION,
                    last_login DOUBLE PRECISION,
                    created_at DOUBLE PRECISION NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE
                )
            """,
            'org_memberships': """
                CREATE TABLE IF NOT EXISTS org_memberships (
                    id UUID PRIMARY KEY,
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
                    role VARCHAR(50) NOT NULL DEFAULT 'member',
                    invited_by UUID,
                    status VARCHAR(50) NOT NULL DEFAULT 'active',
                    accepted_at DOUBLE PRECISION
                )
            """,
            'invitations': """
                CREATE TABLE IF NOT EXISTS invitations (
                    id UUID PRIMARY KEY,
                    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
                    email VARCHAR(255) NOT NULL,
                    role VARCHAR(50) NOT NULL DEFAULT 'member',
                    invited_by UUID NOT NULL REFERENCES users(id),
                    token VARCHAR(255) NOT NULL UNIQUE,
                    expires_at DOUBLE PRECISION NOT NULL,
                    accepted_at DOUBLE PRECISION,
                    created_at DOUBLE PRECISION NOT NULL
                )
            """,
            'refresh_tokens': """
                CREATE TABLE IF NOT EXISTS refresh_tokens (
                    id UUID PRIMARY KEY,
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    token_hash VARCHAR(255) NOT NULL UNIQUE,
                    expires_at DOUBLE PRECISION NOT NULL,
                    created_at DOUBLE PRECISION NOT NULL,
                    revoked_at DOUBLE PRECISION
                )
            """,
            'login_attempts': """
                CREATE TABLE IF NOT EXISTS login_attempts (
                    id UUID PRIMARY KEY,
                    email VARCHAR(255) NOT NULL,
                    ip_address INET,
                    success BOOLEAN NOT NULL DEFAULT FALSE,
                    attempted_at DOUBLE PRECISION NOT NULL
                )
            """,
            'search_sessions': """
                CREATE TABLE IF NOT EXISTS search_sessions (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    org_id UUID NOT NULL REFERENCES organizations(id),
                    title VARCHAR(500),
                    conversation_history JSONB DEFAULT '[]',
                    session_history JSONB DEFAULT '[]',
                    chat_history JSONB DEFAULT '[]',
                    accumulated_articles JSONB DEFAULT '[]',
                    pinned_messages JSONB DEFAULT '[]',
                    pinned_news_cards JSONB DEFAULT '[]',
                    research_report JSONB DEFAULT '{}',
                    user_feedback VARCHAR(20),
                    admin_note TEXT,
                    visibility VARCHAR(20) DEFAULT 'private',
                    team_comments JSONB DEFAULT '[]',
                    is_archived BOOLEAN DEFAULT FALSE,
                    deleted_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """,
            'org_folders': """
                CREATE TABLE IF NOT EXISTS org_folders (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
                    name VARCHAR(255) NOT NULL,
                    created_by UUID NOT NULL REFERENCES users(id),
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """,
            'org_folder_sessions': """
                CREATE TABLE IF NOT EXISTS org_folder_sessions (
                    folder_id UUID NOT NULL REFERENCES org_folders(id) ON DELETE CASCADE,
                    session_id UUID NOT NULL REFERENCES search_sessions(id) ON DELETE CASCADE,
                    added_at TIMESTAMPTZ DEFAULT NOW(),
                    PRIMARY KEY (folder_id, session_id)
                )
            """,
            'session_shares': """
                CREATE TABLE IF NOT EXISTS session_shares (
                    session_id UUID NOT NULL REFERENCES search_sessions(id) ON DELETE CASCADE,
                    shared_with_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    shared_at TIMESTAMPTZ DEFAULT NOW(),
                    PRIMARY KEY (session_id, shared_with_user_id)
                )
            """,
            'user_preferences': """
                CREATE TABLE IF NOT EXISTS user_preferences (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    org_id UUID NOT NULL REFERENCES organizations(id),
                    preference_key VARCHAR(100) NOT NULL,
                    preference_value JSONB NOT NULL,
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE(user_id, org_id, preference_key)
                )
            """,
            'audit_logs': """
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID,
                    org_id UUID,
                    action VARCHAR(100) NOT NULL,
                    target_type VARCHAR(50),
                    target_id UUID,
                    details JSONB,
                    ip_address VARCHAR(64),
                    created_at DOUBLE PRECISION NOT NULL
                )
            """
        }

    def _get_index_sql(self) -> List[str]:
        return [
            "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",
            "CREATE INDEX IF NOT EXISTS idx_users_verification_token ON users(email_verification_token)",
            "CREATE INDEX IF NOT EXISTS idx_users_reset_token ON users(password_reset_token)",
            "CREATE INDEX IF NOT EXISTS idx_org_memberships_user ON org_memberships(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_org_memberships_org ON org_memberships(org_id)",
            "CREATE INDEX IF NOT EXISTS idx_invitations_token ON invitations(token)",
            "CREATE INDEX IF NOT EXISTS idx_invitations_email ON invitations(email)",
            "CREATE INDEX IF NOT EXISTS idx_refresh_tokens_hash ON refresh_tokens(token_hash)",
            "CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_login_attempts_email ON login_attempts(email)",
            "CREATE INDEX IF NOT EXISTS idx_login_attempts_time ON login_attempts(attempted_at)",
            "CREATE INDEX IF NOT EXISTS idx_sessions_user_org ON search_sessions(user_id, org_id)",
            "CREATE INDEX IF NOT EXISTS idx_sessions_updated ON search_sessions(updated_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_org_folders ON org_folders(org_id)",
            "CREATE INDEX IF NOT EXISTS idx_prefs_user_org ON user_preferences(user_id, org_id)",
            "CREATE INDEX IF NOT EXISTS idx_audit_user_id ON audit_logs(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_audit_org_id ON audit_logs(org_id)",
            "CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action)",
            "CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_logs(created_at)",
        ]

    def _init_database(self):
        """Legacy sync init — used by old code path. Prefer initialize() async."""
        self._init_database_sync()
        self._initialized = True
