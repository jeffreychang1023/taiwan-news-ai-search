"""
Tests for auth/auth_service.py — registration, login, JWT, brute force, password reset.

Uses real SQLite (no mocks for DB). Each test gets a fresh DB via tmp_path fixture.
"""

import os
import time
import uuid
import asyncio
import hashlib

import bcrypt
import jwt
import pytest
import pytest_asyncio

os.environ['JWT_SECRET'] = 'test-secret-key-for-jwt-signing-1234'

from auth.auth_db import AuthDB
from auth.auth_service import (
    AuthService,
    ACCESS_TOKEN_EXPIRE_SECONDS,
    BRUTE_FORCE_MAX_ATTEMPTS,
    BRUTE_FORCE_WINDOW_SECONDS,
    JWT_ALGORITHM,
)

# Force SQLite mode: pop AFTER imports (load_dotenv in logger.py re-sets them)
os.environ.pop('DATABASE_URL', None)
os.environ.pop('ANALYTICS_DATABASE_URL', None)
os.environ.pop('POSTGRES_CONNECTION_STRING', None)


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path):
    """
    Reset AuthDB singleton to a fresh SQLite file for every test.
    Also patches email_service to be a no-op so tests don't send mail.
    """
    db_path = str(tmp_path / "auth_test.db")

    # Reset singleton
    AuthDB._instance = None
    db = AuthDB(db_path=db_path)
    AuthDB._instance = db

    # Synchronous schema init (fine for tests)
    db._init_database_sync()
    db._initialized = True

    yield db

    # Cleanup singleton
    AuthDB._instance = None


@pytest.fixture
def service():
    return AuthService()


@pytest.fixture
def _no_email(monkeypatch):
    """Stub email_service functions so register/forgot_password don't fail."""
    import auth.email_service as es
    monkeypatch.setattr(es, 'send_verification_email', lambda *a, **kw: None)
    monkeypatch.setattr(es, 'send_password_reset_email', lambda *a, **kw: None)
    monkeypatch.setattr(es, 'send_lockout_notification', lambda *a, **kw: None)


async def _register_and_verify(service: AuthService,
                                email: str = "test@example.com",
                                password: str = "Password1",
                                name: str = "Test User") -> dict:
    """Helper: register a user and mark email as verified. Returns user dict."""
    user = await service.register_user(email, password, name)
    # Directly verify
    db = AuthDB.get_instance()
    await db.execute(
        "UPDATE users SET email_verified = 1, email_verification_token = NULL WHERE id = ?",
        (user['id'],)
    )
    return user


async def _register_verify_and_login(service: AuthService,
                                      email: str = "test@example.com",
                                      password: str = "Password1",
                                      name: str = "Test User") -> dict:
    """Helper: register, verify, then login. Returns login result dict."""
    await _register_and_verify(service, email, password, name)
    return await service.login(email, password, ip="127.0.0.1")


# ── Registration Tests ───────────────────────────────────────────


class TestRegisterUser:

    @pytest.mark.asyncio
    async def test_register_success(self, service, _no_email):
        result = await service.register_user("alice@example.com", "Passw0rd", "Alice")
        assert result['email'] == "alice@example.com"
        assert result['name'] == "Alice"
        # B2B bootstrap: first admin is auto-verified
        assert result['email_verified'] is True
        assert 'id' in result

    @pytest.mark.asyncio
    async def test_register_normalizes_email(self, service, _no_email):
        result = await service.register_user("  Alice@Example.COM  ", "Passw0rd", "Alice")
        assert result['email'] == "alice@example.com"

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, service, _no_email):
        # B2B model: register_user is bootstrap-only (first admin + org).
        # After bootstrap, a second register_user call raises "System already initialized"
        # because an org now exists — the B2B guard fires before the email-duplicate check.
        await service.register_user("dup@example.com", "Passw0rd", "First")
        with pytest.raises(ValueError, match="System already initialized"):
            await service.register_user("dup@example.com", "Passw0rd", "Second")

    @pytest.mark.asyncio
    async def test_register_weak_password_too_short(self, service, _no_email):
        with pytest.raises(ValueError, match="at least 8 characters"):
            await service.register_user("a@b.com", "Ab1", "X")

    @pytest.mark.asyncio
    async def test_register_weak_password_no_uppercase(self, service, _no_email):
        with pytest.raises(ValueError, match="uppercase"):
            await service.register_user("a@b.com", "password1", "X")

    @pytest.mark.asyncio
    async def test_register_weak_password_no_digit(self, service, _no_email):
        with pytest.raises(ValueError, match="digit"):
            await service.register_user("a@b.com", "Password", "X")


# ── Email Verification Tests ────────────────────────────────────


class TestVerifyEmail:

    @pytest.mark.asyncio
    async def test_verify_email_success(self, service, _no_email):
        user = await service.register_user("v@e.com", "Passw0rd", "V")
        # Grab the verification token from DB
        db = AuthDB.get_instance()
        row = await db.fetchone("SELECT email_verification_token FROM users WHERE id = ?", (user['id'],))
        token = row['email_verification_token']

        result = await service.verify_email(token)
        assert result['email_verified'] is True
        assert result['id'] == user['id']

    @pytest.mark.asyncio
    async def test_verify_email_invalid_token(self, service, _no_email):
        with pytest.raises(ValueError, match="Invalid or expired"):
            await service.verify_email("nonexistent-token")

    @pytest.mark.asyncio
    async def test_verify_email_token_consumed(self, service, _no_email):
        """After verification, the token is nulled — second call should fail."""
        user = await service.register_user("v2@e.com", "Passw0rd", "V2")
        db = AuthDB.get_instance()
        row = await db.fetchone("SELECT email_verification_token FROM users WHERE id = ?", (user['id'],))
        token = row['email_verification_token']

        await service.verify_email(token)
        with pytest.raises(ValueError, match="Invalid or expired"):
            await service.verify_email(token)


# ── Login Tests ──────────────────────────────────────────────────


class TestLogin:

    @pytest.mark.asyncio
    async def test_login_success(self, service, _no_email):
        result = await _register_verify_and_login(service)
        assert 'access_token' in result
        assert 'refresh_token' in result
        assert result['token_type'] == 'Bearer'
        assert result['expires_in'] == ACCESS_TOKEN_EXPIRE_SECONDS
        assert result['user']['email'] == "test@example.com"

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, service, _no_email):
        await _register_and_verify(service)
        with pytest.raises(ValueError, match="Invalid email or password"):
            await service.login("test@example.com", "WrongPass1", ip="127.0.0.1")

    @pytest.mark.asyncio
    async def test_login_nonexistent_email(self, service, _no_email):
        with pytest.raises(ValueError, match="Invalid email or password"):
            await service.login("nobody@example.com", "Passw0rd", ip="127.0.0.1")

    @pytest.mark.asyncio
    async def test_login_unverified_email(self, service, _no_email):
        """User with password set but email_verified=False -> should fail with Email not verified."""
        # Bootstrap admin (auto-verified), then insert an unverified user directly.
        # This represents a user whose account was manually created without going through activation.
        await service.register_user("admin@e.com", "Passw0rd", "Admin")
        db = AuthDB.get_instance()
        password_hash = bcrypt.hashpw(b"Passw0rd", bcrypt.gensalt()).decode('utf-8')
        await db.execute(
            "INSERT INTO users (id, email, password_hash, name, email_verified, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), "unv@e.com", password_hash, "Unv", False, time.time())
        )
        with pytest.raises(ValueError, match="Email not verified"):
            await service.login("unv@e.com", "Passw0rd", ip="127.0.0.1")

    @pytest.mark.asyncio
    async def test_login_deactivated_account(self, service, _no_email):
        user = await _register_and_verify(service)
        db = AuthDB.get_instance()
        await db.execute("UPDATE users SET is_active = 0 WHERE id = ?", (user['id'],))
        # Login with deactivated account returns same generic error to avoid user enumeration
        with pytest.raises(ValueError, match="Invalid email or password"):
            await service.login("test@example.com", "Password1", ip="127.0.0.1")

    @pytest.mark.asyncio
    async def test_login_jwt_payload(self, service, _no_email):
        """Verify the JWT access token contains the expected claims."""
        result = await _register_verify_and_login(service)
        payload = jwt.decode(result['access_token'], os.environ['JWT_SECRET'], algorithms=[JWT_ALGORITHM])
        assert payload['user_id'] == result['user']['id']
        assert payload['email'] == "test@example.com"
        assert 'exp' in payload
        assert 'iat' in payload


# ── Token Refresh Tests ──────────────────────────────────────────


class TestRefreshToken:

    @pytest.mark.asyncio
    async def test_refresh_success(self, service, _no_email):
        login_result = await _register_verify_and_login(service)
        refresh_result = await service.refresh_token(login_result['refresh_token'])
        assert 'access_token' in refresh_result
        assert refresh_result['token_type'] == 'Bearer'
        assert refresh_result['expires_in'] == ACCESS_TOKEN_EXPIRE_SECONDS
        # Verify the refreshed token decodes correctly
        payload = jwt.decode(
            refresh_result['access_token'],
            os.environ['JWT_SECRET'],
            algorithms=[JWT_ALGORITHM],
        )
        assert payload['user_id'] == login_result['user']['id']

    @pytest.mark.asyncio
    async def test_refresh_invalid_token(self, service, _no_email):
        with pytest.raises(ValueError, match="Invalid refresh token"):
            await service.refresh_token("not-a-real-token")

    @pytest.mark.asyncio
    async def test_refresh_revoked_token(self, service, _no_email):
        login_result = await _register_verify_and_login(service)
        await service.logout(login_result['refresh_token'])
        with pytest.raises(ValueError, match="revoked"):
            await service.refresh_token(login_result['refresh_token'])

    @pytest.mark.asyncio
    async def test_refresh_expired_token(self, service, _no_email):
        login_result = await _register_verify_and_login(service)
        # Force the refresh token to be expired
        token_hash = hashlib.sha256(login_result['refresh_token'].encode('utf-8')).hexdigest()
        db = AuthDB.get_instance()
        await db.execute(
            "UPDATE refresh_tokens SET expires_at = ? WHERE token_hash = ?",
            (time.time() - 1, token_hash)
        )
        with pytest.raises(ValueError, match="expired"):
            await service.refresh_token(login_result['refresh_token'])


# ── Logout Tests ─────────────────────────────────────────────────


class TestLogout:

    @pytest.mark.asyncio
    async def test_logout_revokes_token(self, service, _no_email):
        login_result = await _register_verify_and_login(service)
        result = await service.logout(login_result['refresh_token'])
        assert result is True

        # Verify the token is actually revoked in DB
        token_hash = hashlib.sha256(login_result['refresh_token'].encode('utf-8')).hexdigest()
        db = AuthDB.get_instance()
        row = await db.fetchone("SELECT revoked_at FROM refresh_tokens WHERE token_hash = ?", (token_hash,))
        assert row is not None
        assert row['revoked_at'] is not None

    @pytest.mark.asyncio
    async def test_logout_nonexistent_token_no_error(self, service, _no_email):
        """Logout with a token that doesn't exist should not raise."""
        result = await service.logout("fake-token-value")
        assert result is True


# ── Forgot Password Tests ───────────────────────────────────────


class TestForgotPassword:

    @pytest.mark.asyncio
    async def test_forgot_password_existing_email(self, service, _no_email):
        user = await _register_and_verify(service)
        result = await service.forgot_password("test@example.com")
        assert result is True

        # Verify a reset token was stored
        db = AuthDB.get_instance()
        row = await db.fetchone("SELECT password_reset_token FROM users WHERE id = ?", (user['id'],))
        assert row['password_reset_token'] is not None

    @pytest.mark.asyncio
    async def test_forgot_password_nonexistent_email(self, service, _no_email):
        """Should return True even for non-existent email (no leak)."""
        result = await service.forgot_password("nobody@example.com")
        assert result is True

    @pytest.mark.asyncio
    async def test_reset_password_success(self, service, _no_email):
        user = await _register_and_verify(service)
        await service.forgot_password("test@example.com")

        db = AuthDB.get_instance()
        row = await db.fetchone("SELECT password_reset_token FROM users WHERE id = ?", (user['id'],))
        reset_token = row['password_reset_token']

        result = await service.reset_password(reset_token, "NewPassword1")
        assert result is True

        # Should be able to login with new password
        login_result = await service.login("test@example.com", "NewPassword1", ip="127.0.0.1")
        assert 'access_token' in login_result

    @pytest.mark.asyncio
    async def test_reset_password_invalid_token(self, service, _no_email):
        with pytest.raises(ValueError, match="Invalid or expired"):
            await service.reset_password("bogus-token", "NewPassword1")


# ── Brute Force Tests ───────────────────────────────────────────


class TestBruteForce:

    @pytest.mark.asyncio
    async def test_lockout_after_max_attempts(self, service, _no_email):
        """5 failed logins in 15 min should trigger lockout."""
        await _register_and_verify(service)

        for i in range(BRUTE_FORCE_MAX_ATTEMPTS):
            with pytest.raises(ValueError, match="Invalid email or password"):
                await service.login("test@example.com", "WrongPass1", ip="127.0.0.1")

        # Next attempt should get the lockout message
        with pytest.raises(ValueError, match="Too many failed login attempts"):
            await service.login("test@example.com", "Password1", ip="127.0.0.1")

    @pytest.mark.asyncio
    async def test_lockout_blocks_correct_password(self, service, _no_email):
        """Even the correct password should be blocked during lockout."""
        await _register_and_verify(service)

        for _ in range(BRUTE_FORCE_MAX_ATTEMPTS):
            with pytest.raises(ValueError, match="Invalid email or password"):
                await service.login("test@example.com", "Wrong1234", ip="127.0.0.1")

        with pytest.raises(ValueError, match="Too many failed login attempts"):
            await service.login("test@example.com", "Password1", ip="127.0.0.1")

    @pytest.mark.asyncio
    async def test_successful_login_after_fewer_than_max_failures(self, service, _no_email):
        """Under the threshold, login should still work with correct password."""
        await _register_and_verify(service)

        for _ in range(BRUTE_FORCE_MAX_ATTEMPTS - 1):
            with pytest.raises(ValueError, match="Invalid email or password"):
                await service.login("test@example.com", "Wrong1234", ip="127.0.0.1")

        # Should still be able to login
        result = await service.login("test@example.com", "Password1", ip="127.0.0.1")
        assert 'access_token' in result


# ── Organization Tests ───────────────────────────────────────────


class TestOrganization:

    @pytest.mark.asyncio
    async def test_create_org(self, service, _no_email):
        user = await _register_and_verify(service)
        org = await service.create_organization("Test Org", user['id'])
        assert org['name'] == "Test Org"
        assert 'id' in org
        assert org['slug'] == "test-org"

    @pytest.mark.asyncio
    async def test_list_user_orgs(self, service, _no_email):
        # B2B bootstrap: register_user automatically creates an org for the admin.
        user = await _register_and_verify(service)
        orgs = await service.list_user_orgs(user['id'])
        assert len(orgs) == 1
        # Auto-created org name follows the pattern "{name}'s organization"
        assert "Test User" in orgs[0]['name']
        assert orgs[0]['role'] == "admin"
