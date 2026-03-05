"""
Tests for core/session_service.py — session CRUD, JSONB append, soft delete, preferences.

Uses real SQLite via AuthDB (no mocks). Each test gets a fresh database.
"""

import os
import json
import time
import uuid

import pytest
import pytest_asyncio

# Force SQLite mode
os.environ.pop('DATABASE_URL', None)
os.environ.pop('ANALYTICS_DATABASE_URL', None)

from auth.auth_db import AuthDB
from core.session_service import SessionService, JSONB_SIZE_WARNING_THRESHOLD


# ── Fixtures ──────────────────────────────────────────────────────


USER_ID = str(uuid.uuid4())
ORG_ID = str(uuid.uuid4())


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path):
    """Reset AuthDB singleton with a fresh SQLite for each test."""
    db_path = str(tmp_path / "session_test.db")

    AuthDB._instance = None
    db = AuthDB(db_path=db_path)
    AuthDB._instance = db
    db._init_database_sync()
    db._initialized = True

    # Insert a user and org so FK constraints are satisfied
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    now = time.time()
    conn.execute(
        "INSERT INTO organizations (id, name, slug, created_at) VALUES (?, ?, ?, ?)",
        (ORG_ID, "Test Org", "test-org", now)
    )
    conn.execute(
        "INSERT INTO users (id, email, password_hash, name, created_at) VALUES (?, ?, ?, ?, ?)",
        (USER_ID, "sess@test.com", "fakehash", "Session Tester", now)
    )
    conn.commit()
    conn.close()

    yield db

    AuthDB._instance = None


@pytest.fixture
def svc():
    return SessionService()


# ── Create Session Tests ─────────────────────────────────────────


class TestCreateSession:

    @pytest.mark.asyncio
    async def test_create_returns_id_and_timestamps(self, svc):
        result = await svc.create_session(USER_ID, ORG_ID, title="My Search")
        assert 'id' in result
        assert result['title'] == "My Search"
        assert 'created_at' in result
        assert 'updated_at' in result
        assert result['created_at'] == result['updated_at']

    @pytest.mark.asyncio
    async def test_create_with_initial_data(self, svc):
        history = [{"role": "user", "content": "hello"}]
        result = await svc.create_session(
            USER_ID, ORG_ID,
            title="With Data",
            conversation_history=history,
        )
        # Fetch back and verify
        session = await svc.get_session(result['id'], USER_ID, ORG_ID)
        assert session is not None
        assert session['conversation_history'] == history

    @pytest.mark.asyncio
    async def test_create_without_title(self, svc):
        result = await svc.create_session(USER_ID, ORG_ID)
        assert result['title'] is None


# ── Get Session Tests ────────────────────────────────────────────


class TestGetSession:

    @pytest.mark.asyncio
    async def test_get_existing_session(self, svc):
        created = await svc.create_session(USER_ID, ORG_ID, title="Find Me")
        session = await svc.get_session(created['id'], USER_ID, ORG_ID)
        assert session is not None
        assert session['id'] == created['id']
        assert session['title'] == "Find Me"

    @pytest.mark.asyncio
    async def test_get_nonexistent_session(self, svc):
        session = await svc.get_session("nonexistent-id", USER_ID, ORG_ID)
        assert session is None

    @pytest.mark.asyncio
    async def test_get_wrong_user_returns_none(self, svc):
        created = await svc.create_session(USER_ID, ORG_ID, title="Private")
        session = await svc.get_session(created['id'], "other-user-id", ORG_ID)
        assert session is None

    @pytest.mark.asyncio
    async def test_get_deserializes_json_fields(self, svc):
        articles = [{"url": "http://a.com", "title": "A"}]
        report = {"summary": "test report"}
        created = await svc.create_session(
            USER_ID, ORG_ID,
            accumulated_articles=articles,
            research_report=report,
        )
        session = await svc.get_session(created['id'], USER_ID, ORG_ID)
        assert isinstance(session['accumulated_articles'], list)
        assert session['accumulated_articles'] == articles
        assert isinstance(session['research_report'], dict)
        assert session['research_report'] == report


# ── List Sessions Tests ──────────────────────────────────────────


class TestListSessions:

    @pytest.mark.asyncio
    async def test_list_returns_user_sessions(self, svc):
        await svc.create_session(USER_ID, ORG_ID, title="S1")
        await svc.create_session(USER_ID, ORG_ID, title="S2")
        sessions = await svc.list_sessions(USER_ID, ORG_ID)
        assert len(sessions) == 2
        titles = {s['title'] for s in sessions}
        assert titles == {"S1", "S2"}

    @pytest.mark.asyncio
    async def test_list_excludes_deleted(self, svc):
        s1 = await svc.create_session(USER_ID, ORG_ID, title="Active")
        s2 = await svc.create_session(USER_ID, ORG_ID, title="Deleted")
        await svc.delete_session(s2['id'], USER_ID, ORG_ID)
        sessions = await svc.list_sessions(USER_ID, ORG_ID)
        assert len(sessions) == 1
        assert sessions[0]['title'] == "Active"

    @pytest.mark.asyncio
    async def test_list_respects_limit(self, svc):
        for i in range(5):
            await svc.create_session(USER_ID, ORG_ID, title=f"S{i}")
        sessions = await svc.list_sessions(USER_ID, ORG_ID, limit=3)
        assert len(sessions) == 3

    @pytest.mark.asyncio
    async def test_list_empty_for_other_user(self, svc):
        await svc.create_session(USER_ID, ORG_ID, title="Mine")
        sessions = await svc.list_sessions("other-user", ORG_ID)
        assert len(sessions) == 0


# ── Update Session Tests ────────────────────────────────────────


class TestUpdateSession:

    @pytest.mark.asyncio
    async def test_update_title(self, svc):
        created = await svc.create_session(USER_ID, ORG_ID, title="Original")
        result = await svc.update_session(created['id'], USER_ID, ORG_ID, {'title': 'Updated'})
        assert result is True

        session = await svc.get_session(created['id'], USER_ID, ORG_ID)
        assert session['title'] == "Updated"

    @pytest.mark.asyncio
    async def test_update_conversation_history(self, svc):
        created = await svc.create_session(USER_ID, ORG_ID)
        new_history = [{"role": "user", "content": "question"}, {"role": "assistant", "content": "answer"}]
        await svc.update_session(created['id'], USER_ID, ORG_ID, {'conversation_history': new_history})

        session = await svc.get_session(created['id'], USER_ID, ORG_ID)
        assert session['conversation_history'] == new_history

    @pytest.mark.asyncio
    async def test_update_disallowed_field_ignored(self, svc):
        created = await svc.create_session(USER_ID, ORG_ID, title="NoChange")
        result = await svc.update_session(created['id'], USER_ID, ORG_ID, {'id': 'hacked'})
        assert result is False  # No allowed fields -> returns False

    @pytest.mark.asyncio
    async def test_update_bumps_updated_at(self, svc):
        created = await svc.create_session(USER_ID, ORG_ID, title="Time")
        original_time = created['updated_at']

        # Small delay to ensure timestamp difference
        import asyncio
        await asyncio.sleep(0.05)

        await svc.update_session(created['id'], USER_ID, ORG_ID, {'title': 'Time2'})
        session = await svc.get_session(created['id'], USER_ID, ORG_ID)
        assert session['updated_at'] > original_time

    @pytest.mark.asyncio
    async def test_update_is_archived(self, svc):
        created = await svc.create_session(USER_ID, ORG_ID, title="Archive Me")
        await svc.update_session(created['id'], USER_ID, ORG_ID, {'is_archived': True})

        session = await svc.get_session(created['id'], USER_ID, ORG_ID)
        assert session['is_archived'] is True


# ── Soft Delete Tests ───────────────────────────────────────────


class TestSoftDelete:

    @pytest.mark.asyncio
    async def test_delete_sets_deleted_at(self, svc):
        created = await svc.create_session(USER_ID, ORG_ID, title="Delete Me")
        result = await svc.delete_session(created['id'], USER_ID, ORG_ID)
        assert result is True

        # Should not be retrievable
        session = await svc.get_session(created['id'], USER_ID, ORG_ID)
        assert session is None

    @pytest.mark.asyncio
    async def test_delete_is_soft(self, svc):
        """Soft-deleted sessions still exist in DB, just have deleted_at set."""
        created = await svc.create_session(USER_ID, ORG_ID, title="Soft")
        await svc.delete_session(created['id'], USER_ID, ORG_ID)

        db = AuthDB.get_instance()
        row = await db.fetchone(
            "SELECT deleted_at FROM search_sessions WHERE id = ?", (created['id'],)
        )
        assert row is not None
        assert row['deleted_at'] is not None

    @pytest.mark.asyncio
    async def test_restore_session(self, svc):
        created = await svc.create_session(USER_ID, ORG_ID, title="Restore Me")
        await svc.delete_session(created['id'], USER_ID, ORG_ID)

        # Should not be visible
        assert await svc.get_session(created['id'], USER_ID, ORG_ID) is None

        # Restore it
        await svc.restore_session(created['id'], USER_ID, ORG_ID)

        # Should be visible again
        session = await svc.get_session(created['id'], USER_ID, ORG_ID)
        assert session is not None
        assert session['title'] == "Restore Me"

    @pytest.mark.asyncio
    async def test_restore_expired_raises(self, svc):
        """Sessions deleted more than 30 days ago cannot be restored."""
        created = await svc.create_session(USER_ID, ORG_ID, title="Old")
        db = AuthDB.get_instance()
        # Set deleted_at to 31 days ago
        old_time = time.time() - 31 * 24 * 3600
        await db.execute(
            "UPDATE search_sessions SET deleted_at = ? WHERE id = ?",
            (old_time, created['id'])
        )
        with pytest.raises(ValueError, match="past 30-day"):
            await svc.restore_session(created['id'], USER_ID, ORG_ID)


# ── Get Expired Deleted Sessions Tests ──────────────────────────


class TestExpiredDeletedSessions:

    @pytest.mark.asyncio
    async def test_returns_old_deleted_sessions(self, svc):
        s1 = await svc.create_session(USER_ID, ORG_ID, title="Old Deleted")
        s2 = await svc.create_session(USER_ID, ORG_ID, title="Recent Deleted")

        db = AuthDB.get_instance()
        # Mark s1 as deleted 45 days ago
        await db.execute(
            "UPDATE search_sessions SET deleted_at = ? WHERE id = ?",
            (time.time() - 45 * 24 * 3600, s1['id'])
        )
        # Mark s2 as deleted 5 days ago
        await db.execute(
            "UPDATE search_sessions SET deleted_at = ? WHERE id = ?",
            (time.time() - 5 * 24 * 3600, s2['id'])
        )

        expired = await svc.get_expired_deleted_sessions(days=30)
        ids = {s['id'] for s in expired}
        assert s1['id'] in ids
        assert s2['id'] not in ids

    @pytest.mark.asyncio
    async def test_active_sessions_not_returned(self, svc):
        await svc.create_session(USER_ID, ORG_ID, title="Active")
        expired = await svc.get_expired_deleted_sessions()
        assert len(expired) == 0


# ── JSONB Append Tests ──────────────────────────────────────────


class TestAppendMessage:

    @pytest.mark.asyncio
    async def test_append_message(self, svc):
        created = await svc.create_session(USER_ID, ORG_ID)
        msg = {"role": "user", "content": "hello"}
        result = await svc.append_message(created['id'], USER_ID, ORG_ID, msg)
        assert result is True

        session = await svc.get_session(created['id'], USER_ID, ORG_ID)
        assert len(session['conversation_history']) == 1
        assert session['conversation_history'][0] == msg

    @pytest.mark.asyncio
    async def test_append_multiple_messages(self, svc):
        created = await svc.create_session(USER_ID, ORG_ID)
        for i in range(3):
            await svc.append_message(created['id'], USER_ID, ORG_ID, {"role": "user", "content": f"msg {i}"})

        session = await svc.get_session(created['id'], USER_ID, ORG_ID)
        assert len(session['conversation_history']) == 3

    @pytest.mark.asyncio
    async def test_append_to_nonexistent_session(self, svc):
        result = await svc.append_message("nonexistent", USER_ID, ORG_ID, {"content": "x"})
        assert result is False


class TestAppendArticles:

    @pytest.mark.asyncio
    async def test_append_articles(self, svc):
        created = await svc.create_session(USER_ID, ORG_ID)
        articles = [{"url": "http://a.com", "title": "A"}, {"url": "http://b.com", "title": "B"}]
        result = await svc.append_articles(created['id'], USER_ID, ORG_ID, articles)
        assert result is True

        session = await svc.get_session(created['id'], USER_ID, ORG_ID)
        assert len(session['accumulated_articles']) == 2

    @pytest.mark.asyncio
    async def test_append_articles_accumulates(self, svc):
        created = await svc.create_session(USER_ID, ORG_ID)
        await svc.append_articles(created['id'], USER_ID, ORG_ID, [{"url": "http://a.com"}])
        await svc.append_articles(created['id'], USER_ID, ORG_ID, [{"url": "http://b.com"}])

        session = await svc.get_session(created['id'], USER_ID, ORG_ID)
        assert len(session['accumulated_articles']) == 2


# ── Permanent Delete Tests ──────────────────────────────────────


class TestPermanentDelete:

    @pytest.mark.asyncio
    async def test_permanent_delete_removes_from_db(self, svc):
        created = await svc.create_session(USER_ID, ORG_ID, title="Gone")
        await svc.permanent_delete(created['id'])

        db = AuthDB.get_instance()
        row = await db.fetchone("SELECT id FROM search_sessions WHERE id = ?", (created['id'],))
        assert row is None


# ── Preferences Tests ────────────────────────────────────────────


class TestPreferences:

    @pytest.mark.asyncio
    async def test_set_and_get_preference(self, svc):
        await svc.set_preference(USER_ID, ORG_ID, "theme", "dark")
        prefs = await svc.get_preferences(USER_ID, ORG_ID)
        assert prefs["theme"] == "dark"

    @pytest.mark.asyncio
    async def test_set_preference_overwrite(self, svc):
        await svc.set_preference(USER_ID, ORG_ID, "lang", "en")
        await svc.set_preference(USER_ID, ORG_ID, "lang", "zh")
        prefs = await svc.get_preferences(USER_ID, ORG_ID)
        assert prefs["lang"] == "zh"

    @pytest.mark.asyncio
    async def test_get_preferences_empty(self, svc):
        prefs = await svc.get_preferences(USER_ID, ORG_ID)
        assert prefs == {}

    @pytest.mark.asyncio
    async def test_complex_preference_value(self, svc):
        value = {"sources": ["cna", "ltn"], "maxResults": 20}
        await svc.set_preference(USER_ID, ORG_ID, "search_config", value)
        prefs = await svc.get_preferences(USER_ID, ORG_ID)
        assert prefs["search_config"] == value


# ── Visibility Tests ────────────────────────────────────────────


class TestVisibility:

    @pytest.mark.asyncio
    async def test_set_visibility_valid(self, svc):
        created = await svc.create_session(USER_ID, ORG_ID, title="Shared")
        result = await svc.set_visibility(created['id'], USER_ID, ORG_ID, 'team')
        assert result is True

        session = await svc.get_session(created['id'], USER_ID, ORG_ID)
        assert session['visibility'] == 'team'

    @pytest.mark.asyncio
    async def test_set_visibility_invalid(self, svc):
        created = await svc.create_session(USER_ID, ORG_ID, title="Bad Vis")
        with pytest.raises(ValueError, match="visibility must be one of"):
            await svc.set_visibility(created['id'], USER_ID, ORG_ID, 'public')

    @pytest.mark.asyncio
    async def test_set_visibility_nonexistent_session(self, svc):
        with pytest.raises(ValueError, match="not found"):
            await svc.set_visibility("nonexistent", USER_ID, ORG_ID, 'team')


# ── Export Tests ────────────────────────────────────────────────


class TestExport:

    @pytest.mark.asyncio
    async def test_export_json(self, svc):
        articles = [{"url": "http://x.com", "title": "X", "source": "Src"}]
        created = await svc.create_session(
            USER_ID, ORG_ID, title="Export",
            accumulated_articles=articles,
        )
        result = await svc.export_session(created['id'], USER_ID, ORG_ID, format='json')
        assert result['title'] == "Export"
        assert result['accumulated_articles'] == articles

    @pytest.mark.asyncio
    async def test_export_citations(self, svc):
        articles = [{"url": "http://x.com", "title": "Article X", "source": "Source A", "published_date": "2026-01-01"}]
        created = await svc.create_session(
            USER_ID, ORG_ID, title="Citations",
            accumulated_articles=articles,
        )
        result = await svc.export_session(created['id'], USER_ID, ORG_ID, format='citations')
        assert isinstance(result, list)
        assert len(result) == 1
        assert "Article X" in result[0]
        assert "Source A" in result[0]

    @pytest.mark.asyncio
    async def test_export_nonexistent_session(self, svc):
        with pytest.raises(ValueError, match="Session not found"):
            await svc.export_session("nonexistent", USER_ID, ORG_ID)

    @pytest.mark.asyncio
    async def test_export_unsupported_format(self, svc):
        created = await svc.create_session(USER_ID, ORG_ID, title="Bad Format")
        with pytest.raises(ValueError, match="Unsupported export format"):
            await svc.export_session(created['id'], USER_ID, ORG_ID, format='pdf')
