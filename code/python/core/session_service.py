"""
Session management service for B2B search sessions.

Handles CRUD operations for search sessions, folders, preferences,
and session sharing. Uses async AuthDB interface.

JSONB append mode for conversation_history to avoid full-column rewrites.
Monitors JSONB size and logs warnings when exceeding 200KB threshold.
"""

import json
import time
import uuid
from typing import Any, Dict, List, Optional

from auth.auth_db import AuthDB
from misc.logger.logging_config_helper import get_configured_logger

logger = get_configured_logger("session_service")

# Size monitoring threshold (bytes)
JSONB_SIZE_WARNING_THRESHOLD = 200 * 1024  # 200KB


class SessionService:
    """Async session management service."""

    def __init__(self):
        self.db = AuthDB.get_instance()

    # ── Session CRUD ─────────────────────────────────────────────

    async def list_sessions(self, user_id: str, org_id: str,
                            limit: int = 50, offset: int = 0,
                            include_archived: bool = False) -> List[Dict]:
        """List sessions for a user within an org (soft-deleted excluded)."""
        query = (
            "SELECT id, title, user_feedback, visibility, is_archived, "
            "created_at, updated_at "
            "FROM search_sessions "
            "WHERE user_id = ? AND org_id = ? AND deleted_at IS NULL"
        )
        params: list = [user_id, org_id]

        if not include_archived:
            query += " AND is_archived = ?"
            params.append(0 if self.db.db_type == 'sqlite' else False)

        query += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = await self.db.fetchall(query, tuple(params))
        if self.db.db_type == 'sqlite':
            for r in rows:
                r['is_archived'] = bool(r.get('is_archived', 0))
        return rows

    async def create_session(self, user_id: str, org_id: str,
                             title: str = None,
                             conversation_history: list = None,
                             session_history: list = None,
                             chat_history: list = None,
                             accumulated_articles: list = None,
                             research_report: dict = None) -> Dict:
        """Create a new search session."""
        session_id = str(uuid.uuid4())
        now = time.time()

        await self.db.execute(
            "INSERT INTO search_sessions "
            "(id, user_id, org_id, title, conversation_history, session_history, "
            "chat_history, accumulated_articles, research_report, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                session_id, user_id, org_id, title,
                json.dumps(conversation_history or []),
                json.dumps(session_history or []),
                json.dumps(chat_history or []),
                json.dumps(accumulated_articles or []),
                json.dumps(research_report or {}),
                now, now
            )
        )

        logger.info(f"Session created: {session_id} by user {user_id}")
        return {
            'id': session_id,
            'title': title,
            'created_at': now,
            'updated_at': now,
        }

    async def get_session(self, session_id: str, user_id: str, org_id: str) -> Optional[Dict]:
        """Get a single session with full data. Checks ownership."""
        row = await self.db.fetchone(
            "SELECT * FROM search_sessions "
            "WHERE id = ? AND user_id = ? AND org_id = ? AND deleted_at IS NULL",
            (session_id, user_id, org_id)
        )
        if not row:
            return None
        return self._deserialize_session(row)

    async def update_session(self, session_id: str, user_id: str, org_id: str,
                             updates: Dict[str, Any]) -> bool:
        """Partial update of a session. Only allowed fields are updated."""
        allowed_fields = {
            'title', 'conversation_history', 'session_history', 'chat_history',
            'accumulated_articles', 'pinned_messages', 'pinned_news_cards',
            'research_report', 'user_feedback', 'admin_note', 'visibility',
            'team_comments', 'is_archived'
        }

        set_clauses = []
        params = []
        for key, value in updates.items():
            if key not in allowed_fields:
                continue
            set_clauses.append(f"{key} = ?")
            if isinstance(value, (dict, list)):
                params.append(json.dumps(value))
            elif key == 'is_archived' and self.db.db_type == 'sqlite':
                params.append(1 if value else 0)
            else:
                params.append(value)

        if not set_clauses:
            return False

        set_clauses.append("updated_at = ?")
        params.append(time.time())

        params.extend([session_id, user_id, org_id])

        await self.db.execute(
            f"UPDATE search_sessions SET {', '.join(set_clauses)} "
            "WHERE id = ? AND user_id = ? AND org_id = ? AND deleted_at IS NULL",
            tuple(params)
        )
        return True

    async def delete_session(self, session_id: str, user_id: str, org_id: str) -> bool:
        """Soft-delete a session (sets deleted_at)."""
        await self.db.execute(
            "UPDATE search_sessions SET deleted_at = ?, updated_at = ? "
            "WHERE id = ? AND user_id = ? AND org_id = ? AND deleted_at IS NULL",
            (time.time(), time.time(), session_id, user_id, org_id)
        )
        logger.info(f"Session soft-deleted: {session_id}")
        return True

    async def restore_session(self, session_id: str, user_id: str, org_id: str) -> bool:
        """Restore a soft-deleted session (admin, within 30 days)."""
        cutoff = time.time() - 30 * 24 * 3600
        row = await self.db.fetchone(
            "SELECT id FROM search_sessions "
            "WHERE id = ? AND user_id = ? AND org_id = ? "
            "AND deleted_at IS NOT NULL AND deleted_at > ?",
            (session_id, user_id, org_id, cutoff)
        )
        if not row:
            raise ValueError("Session not found or expired (past 30-day restore window)")

        await self.db.execute(
            "UPDATE search_sessions SET deleted_at = NULL, updated_at = ? WHERE id = ?",
            (time.time(), session_id)
        )
        logger.info(f"Session restored: {session_id}")
        return True

    # ── JSONB Append Operations ──────────────────────────────────

    async def append_message(self, session_id: str, user_id: str, org_id: str,
                             message: Dict) -> bool:
        """Append a message to conversation_history using JSONB append mode."""
        if self.db.db_type == 'postgres':
            new_json = json.dumps([message])
            self._check_jsonb_size(session_id, 'conversation_history', new_json)
            await self.db.execute(
                "UPDATE search_sessions "
                "SET conversation_history = conversation_history || %s::jsonb, "
                "    updated_at = %s "
                "WHERE id = %s AND user_id = %s AND org_id = %s AND deleted_at IS NULL",
                (new_json, time.time(), session_id, user_id, org_id)
            )
        else:
            # SQLite: read-modify-write
            row = await self.db.fetchone(
                "SELECT conversation_history FROM search_sessions "
                "WHERE id = ? AND user_id = ? AND org_id = ? AND deleted_at IS NULL",
                (session_id, user_id, org_id)
            )
            if not row:
                return False
            history = json.loads(row['conversation_history'] or '[]')
            history.append(message)
            serialized = json.dumps(history)
            self._check_jsonb_size(session_id, 'conversation_history', serialized)
            await self.db.execute(
                "UPDATE search_sessions SET conversation_history = ?, updated_at = ? WHERE id = ?",
                (serialized, time.time(), session_id)
            )
        return True

    async def append_articles(self, session_id: str, user_id: str, org_id: str,
                              articles: List[Dict]) -> bool:
        """Append articles to accumulated_articles."""
        if self.db.db_type == 'postgres':
            new_json = json.dumps(articles)
            self._check_jsonb_size(session_id, 'accumulated_articles', new_json)
            await self.db.execute(
                "UPDATE search_sessions "
                "SET accumulated_articles = accumulated_articles || %s::jsonb, "
                "    updated_at = %s "
                "WHERE id = %s AND user_id = %s AND org_id = %s AND deleted_at IS NULL",
                (new_json, time.time(), session_id, user_id, org_id)
            )
        else:
            row = await self.db.fetchone(
                "SELECT accumulated_articles FROM search_sessions "
                "WHERE id = ? AND user_id = ? AND org_id = ? AND deleted_at IS NULL",
                (session_id, user_id, org_id)
            )
            if not row:
                return False
            existing = json.loads(row['accumulated_articles'] or '[]')
            existing.extend(articles)
            serialized = json.dumps(existing)
            self._check_jsonb_size(session_id, 'accumulated_articles', serialized)
            await self.db.execute(
                "UPDATE search_sessions SET accumulated_articles = ?, updated_at = ? WHERE id = ?",
                (serialized, time.time(), session_id)
            )
        return True

    async def update_article_annotation(self, session_id: str, user_id: str, org_id: str,
                                        article_url: str, annotation: Dict) -> bool:
        """Update annotation on a specific article within accumulated_articles."""
        row = await self.db.fetchone(
            "SELECT accumulated_articles FROM search_sessions "
            "WHERE id = ? AND user_id = ? AND org_id = ? AND deleted_at IS NULL",
            (session_id, user_id, org_id)
        )
        if not row:
            return False

        articles = json.loads(row['accumulated_articles'] or '[]')
        found = False
        for article in articles:
            if article.get('url') == article_url:
                article.update(annotation)
                found = True
                break

        if not found:
            raise ValueError(f"Article not found: {article_url}")

        await self.db.execute(
            "UPDATE search_sessions SET accumulated_articles = ?, updated_at = ? "
            "WHERE id = ? AND user_id = ? AND org_id = ?",
            (json.dumps(articles), time.time(), session_id, user_id, org_id)
        )
        return True

    # ── Migration ────────────────────────────────────────────────

    async def migrate_sessions(self, user_id: str, org_id: str,
                               sessions: List[Dict]) -> Dict:
        """Batch migrate sessions from localStorage format."""
        created = 0
        errors = []

        for s in sessions:
            try:
                await self.create_session(
                    user_id=user_id,
                    org_id=org_id,
                    title=s.get('title'),
                    conversation_history=s.get('conversationHistory', []),
                    session_history=s.get('sessionHistory', []),
                    chat_history=s.get('chatHistory', []),
                    accumulated_articles=s.get('accumulatedArticles', []),
                    research_report=s.get('researchReport', {}),
                )
                created += 1
            except Exception as e:
                errors.append({'title': s.get('title', 'unknown'), 'error': str(e)})
                logger.error(f"Migration error for session '{s.get('title')}': {e}")

        logger.info(f"Migration completed: {created} created, {len(errors)} errors")
        return {'created': created, 'errors': errors}

    # ── Export ────────────────────────────────────────────────────

    async def export_session(self, session_id: str, user_id: str, org_id: str,
                             format: str = 'json') -> Any:
        """Export session in various formats."""
        session = await self.get_session(session_id, user_id, org_id)
        if not session:
            raise ValueError("Session not found")

        if format == 'json':
            return session

        if format == 'citations':
            return self.generate_citations(session)

        if format == 'csv':
            return self._export_csv(session)

        if format == 'ris':
            return self._export_ris(session)

        raise ValueError(f"Unsupported export format: {format}")

    @staticmethod
    def _normalize_article(a: Dict) -> Dict:
        """Normalize article fields: support schema.org style (name/site/description) and flat style (title/source/summary)."""
        schema = a.get('schema_object') or {}
        title = a.get('title') or a.get('name') or schema.get('headline', '')
        publisher = schema.get('publisher', {})
        source = a.get('source') or a.get('site') or (publisher.get('name', '') if isinstance(publisher, dict) else '')
        summary = a.get('summary') or a.get('description') or schema.get('articleBody', '')
        published_date = a.get('published_date') or a.get('datePublished') or schema.get('datePublished', '')
        return {
            'url': a.get('url', ''),
            'title': title or '',
            'source': source or '',
            'published_date': published_date or '',
            'summary': summary or '',
            'status': a.get('status', ''),
            'importance': a.get('importance', ''),
        }

    def generate_citations(self, session: Dict) -> List[str]:
        """Generate APA-style citations from accumulated articles."""
        citations = []
        for article in session.get('accumulated_articles', []):
            a = self._normalize_article(article)
            source = a['source'] or 'Unknown'
            title = a['title'] or 'Untitled'
            date = a['published_date'] or 'n.d.'
            url = a['url']
            citation = f"{source}. ({date}). {title}. Retrieved from {url}"
            citations.append(citation)
        return citations

    @staticmethod
    def _csv_safe(value: str) -> str:
        """Sanitize a value for CSV to prevent formula injection."""
        if value and value[0] in ('=', '+', '-', '@', '\t', '\r'):
            value = "'" + value
        return value.replace('"', "'")

    def _export_csv(self, session: Dict) -> str:
        """Export articles as CSV string."""
        lines = ["url,title,source,published_date,status,importance"]
        for article in session.get('accumulated_articles', []):
            a = self._normalize_article(article)
            row = ','.join([
                f'"{self._csv_safe(a["url"])}"',
                f'"{self._csv_safe(a["title"])}"',
                f'"{self._csv_safe(a["source"])}"',
                f'"{self._csv_safe(a["published_date"])}"',
                f'"{self._csv_safe(a["status"])}"',
                str(a["importance"]),
            ])
            lines.append(row)
        return '\n'.join(lines)

    def _export_ris(self, session: Dict) -> str:
        """Export articles in RIS format."""
        entries = []
        for article in session.get('accumulated_articles', []):
            a = self._normalize_article(article)
            entry = '\n'.join([
                'TY  - NEWS',
                f'TI  - {a["title"]}',
                f'PB  - {a["source"]}',
                f'DA  - {a["published_date"]}',
                f'UR  - {a["url"]}',
                f'AB  - {a["summary"][:300] if a["summary"] else ""}',
                'ER  - ',
            ])
            entries.append(entry)
        return '\n'.join(entries)

    # ── Session Sharing ──────────────────────────────────────────

    VALID_VISIBILITY = {'private', 'team', 'org'}

    async def set_visibility(self, session_id: str, user_id: str, org_id: str,
                             visibility: str) -> bool:
        """Change a session's visibility. Caller must own the session."""
        if visibility not in self.VALID_VISIBILITY:
            raise ValueError(f"visibility must be one of: {', '.join(sorted(self.VALID_VISIBILITY))}")

        # Verify ownership before updating
        row = await self.db.fetchone(
            "SELECT id FROM search_sessions "
            "WHERE id = ? AND user_id = ? AND org_id = ? AND deleted_at IS NULL",
            (session_id, user_id, org_id)
        )
        if not row:
            raise ValueError("Session not found or access denied")

        await self.db.execute(
            "UPDATE search_sessions SET visibility = ?, updated_at = ? "
            "WHERE id = ? AND user_id = ? AND org_id = ?",
            (visibility, time.time(), session_id, user_id, org_id)
        )
        logger.info(f"Session {session_id} visibility set to '{visibility}' by user {user_id}")
        return True

    async def get_shared_sessions(self, user_id: str, org_id: str,
                                  limit: int = 50, offset: int = 0) -> List[Dict]:
        """
        Return sessions from the same org that are visible to this user
        but not owned by them (visibility = 'team' or 'org').
        Includes owner name/email from the users table.
        """
        query = (
            "SELECT s.id, s.user_id, s.title, s.visibility, s.user_feedback, "
            "s.created_at, s.updated_at, "
            "u.name AS owner_name, u.email AS owner_email "
            "FROM search_sessions s "
            "LEFT JOIN users u ON u.id = s.user_id "
            "WHERE s.org_id = ? AND s.user_id != ? "
            "AND s.visibility IN ('team', 'org') "
            "AND s.deleted_at IS NULL "
            "ORDER BY s.updated_at DESC LIMIT ? OFFSET ?"
        )
        rows = await self.db.fetchall(query, (org_id, user_id, limit, offset))
        return [dict(r) for r in rows]

    async def get_session_shared(self, session_id: str, user_id: str, org_id: str) -> Optional[Dict]:
        """
        Get a session if the requesting user has access — either as owner,
        or because visibility is 'team'/'org' within the same org.
        """
        logger.debug(f"get_session_shared: id={session_id!r} org={org_id!r} user={user_id!r}")
        row = await self.db.fetchone(
            "SELECT * FROM search_sessions "
            "WHERE id = ? AND org_id = ? AND deleted_at IS NULL "
            "AND (user_id = ? OR visibility IN ('team', 'org'))",
            (session_id, org_id, user_id)
        )
        if not row:
            # Diagnose: check if session exists at all
            exists = await self.db.fetchone(
                "SELECT id, org_id, user_id, visibility, deleted_at FROM search_sessions WHERE id = ?",
                (session_id,)
            )
            logger.warning(f"get_session_shared: not found. Raw lookup: {exists}")
            return None
        return self._deserialize_session(row)

    # ── Soft Delete Cleanup ──────────────────────────────────────

    async def get_expired_deleted_sessions(self, days: int = 30) -> List[Dict]:
        """Get sessions soft-deleted more than N days ago."""
        from datetime import datetime, timedelta, timezone
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return await self.db.fetchall(
            "SELECT id, user_id, org_id FROM search_sessions "
            "WHERE deleted_at IS NOT NULL AND deleted_at < ?",
            (cutoff,)
        )

    async def permanent_delete(self, session_id: str):
        """Permanently delete a session and its junction table records."""
        # Junction tables cascade, so just delete the session
        await self.db.execute(
            "DELETE FROM search_sessions WHERE id = ?",
            (session_id,)
        )
        logger.info(f"Session permanently deleted: {session_id}")

    # ── Preferences ──────────────────────────────────────────────

    async def get_preferences(self, user_id: str, org_id: str) -> Dict[str, Any]:
        """Get all preferences for a user in an org."""
        rows = await self.db.fetchall(
            "SELECT preference_key, preference_value FROM user_preferences "
            "WHERE user_id = ? AND org_id = ?",
            (user_id, org_id)
        )
        result = {}
        for r in rows:
            try:
                result[r['preference_key']] = json.loads(r['preference_value'])
            except (json.JSONDecodeError, TypeError):
                result[r['preference_key']] = r['preference_value']
        return result

    async def set_preference(self, user_id: str, org_id: str,
                             key: str, value: Any) -> bool:
        """Set a user preference (upsert)."""
        pref_id = str(uuid.uuid4())
        now = time.time()
        serialized_value = json.dumps(value)

        if self.db.db_type == 'postgres':
            await self.db.execute(
                "INSERT INTO user_preferences (id, user_id, org_id, preference_key, preference_value, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (user_id, org_id, preference_key) "
                "DO UPDATE SET preference_value = EXCLUDED.preference_value, updated_at = EXCLUDED.updated_at",
                (pref_id, user_id, org_id, key, serialized_value, now)
            )
        else:
            await self.db.execute(
                "INSERT OR REPLACE INTO user_preferences "
                "(id, user_id, org_id, preference_key, preference_value, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (pref_id, user_id, org_id, key, serialized_value, now)
            )
        return True

    # ── Helpers ───────────────────────────────────────────────────

    def _deserialize_session(self, row: Dict) -> Dict:
        """Deserialize JSONB fields from a session row."""
        jsonb_fields = [
            'conversation_history', 'session_history', 'chat_history',
            'accumulated_articles', 'pinned_messages', 'pinned_news_cards',
            'research_report', 'team_comments'
        ]
        result = dict(row)
        for field in jsonb_fields:
            if field in result and isinstance(result[field], str):
                try:
                    result[field] = json.loads(result[field])
                except (json.JSONDecodeError, TypeError):
                    pass
        if self.db.db_type == 'sqlite' and 'is_archived' in result:
            result['is_archived'] = bool(result['is_archived'])
        return result

    def _check_jsonb_size(self, session_id: str, field: str, serialized: str):
        """Log warning if JSONB field exceeds size threshold."""
        size = len(serialized.encode('utf-8'))
        if size > JSONB_SIZE_WARNING_THRESHOLD:
            logger.warning(
                f"JSONB size warning: session={session_id}, field={field}, "
                f"size={size / 1024:.1f}KB (threshold={JSONB_SIZE_WARNING_THRESHOLD / 1024:.0f}KB). "
                f"Consider migrating to session_messages table."
            )
