"""
Tests for webserver/middleware/auth.py — auth_middleware behavior.

Tests public vs protected endpoints, JWT validation, soft auth,
dev bypass, and missing JWT_SECRET handling.

Uses aiohttp.test_utils.TestClient + TestServer (no pytest-aiohttp dependency).
"""

import os
import time
import json

import jwt
import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

# Ensure no DATABASE_URL so AuthDB stays in SQLite mode
os.environ.pop('DATABASE_URL', None)
os.environ.pop('ANALYTICS_DATABASE_URL', None)

JWT_SECRET = 'test-middleware-secret-9876'
JWT_ALGORITHM = 'HS256'

from webserver.middleware.auth import auth_middleware, PUBLIC_ENDPOINTS


# ── Helpers ──────────────────────────────────────────────────────


def _make_jwt(claims: dict, secret: str = JWT_SECRET, expired: bool = False) -> str:
    """Create a JWT token for testing."""
    now = int(time.time())
    payload = {
        'user_id': claims.get('user_id', 'uid-123'),
        'email': claims.get('email', 'user@test.com'),
        'name': claims.get('name', 'Test User'),
        'org_id': claims.get('org_id', 'org-456'),
        'role': claims.get('role', 'member'),
        'iat': now,
        'exp': now - 3600 if expired else now + 3600,
    }
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def _build_app() -> web.Application:
    """Create a minimal aiohttp app with the auth middleware and test routes."""
    app = web.Application(middlewares=[auth_middleware])

    async def health(request):
        user = request.get('user')
        return web.json_response({'status': 'ok', 'user': user})

    async def ask(request):
        user = request.get('user')
        return web.json_response({'endpoint': 'ask', 'user': user})

    async def sites(request):
        return web.json_response({'sites': []})

    async def protected(request):
        user = request.get('user')
        return web.json_response({'endpoint': 'protected', 'user': user})

    async def api_sessions(request):
        user = request.get('user')
        return web.json_response({'endpoint': 'sessions', 'user': user})

    app.router.add_get('/health', health)
    app.router.add_get('/ask', ask)
    app.router.add_get('/sites', sites)
    app.router.add_get('/api/protected', protected)
    app.router.add_get('/api/sessions', api_sessions)

    return app


# ── Public Endpoint Tests ───────────────────────────────────────


class TestPublicEndpoints:

    @pytest.mark.asyncio
    async def test_health_no_auth(self, monkeypatch):
        """Public endpoint should pass through without auth."""
        monkeypatch.setenv('JWT_SECRET', JWT_SECRET)
        async with TestClient(TestServer(_build_app())) as client:
            resp = await client.get('/health')
            assert resp.status == 200
            data = await resp.json()
            assert data['status'] == 'ok'
            assert data['user'] is None

    @pytest.mark.asyncio
    async def test_ask_no_auth(self, monkeypatch):
        monkeypatch.setenv('JWT_SECRET', JWT_SECRET)
        async with TestClient(TestServer(_build_app())) as client:
            resp = await client.get('/ask')
            assert resp.status == 200

    @pytest.mark.asyncio
    async def test_sites_no_auth(self, monkeypatch):
        monkeypatch.setenv('JWT_SECRET', JWT_SECRET)
        async with TestClient(TestServer(_build_app())) as client:
            resp = await client.get('/sites')
            assert resp.status == 200


class TestSoftAuth:

    @pytest.mark.asyncio
    async def test_public_endpoint_with_valid_token(self, monkeypatch):
        """Public endpoint with valid Bearer token -> request['user'] is populated."""
        monkeypatch.setenv('JWT_SECRET', JWT_SECRET)
        token = _make_jwt({'user_id': 'u-soft', 'name': 'Soft User', 'org_id': 'o-1', 'role': 'admin'})
        async with TestClient(TestServer(_build_app())) as client:
            resp = await client.get('/health', headers={'Authorization': f'Bearer {token}'})
            assert resp.status == 200
            data = await resp.json()
            assert data['user'] is not None
            assert data['user']['id'] == 'u-soft'
            assert data['user']['authenticated'] is True

    @pytest.mark.asyncio
    async def test_public_endpoint_with_invalid_token(self, monkeypatch):
        """Public endpoint with invalid token -> user is None (soft auth ignores errors)."""
        monkeypatch.setenv('JWT_SECRET', JWT_SECRET)
        async with TestClient(TestServer(_build_app())) as client:
            resp = await client.get('/health', headers={'Authorization': 'Bearer bad-token'})
            assert resp.status == 200
            data = await resp.json()
            assert data['user'] is None

    @pytest.mark.asyncio
    async def test_public_endpoint_with_expired_token(self, monkeypatch):
        """Public endpoint with expired token -> user is None (soft auth ignores)."""
        monkeypatch.setenv('JWT_SECRET', JWT_SECRET)
        token = _make_jwt({}, expired=True)
        async with TestClient(TestServer(_build_app())) as client:
            resp = await client.get('/health', headers={'Authorization': f'Bearer {token}'})
            assert resp.status == 200
            data = await resp.json()
            assert data['user'] is None


# ── Protected Endpoint Tests ─────────────────────────────────────


class TestProtectedEndpoints:

    @pytest.mark.asyncio
    async def test_no_token_returns_401(self, monkeypatch):
        """Protected endpoint without token -> 401."""
        monkeypatch.setenv('JWT_SECRET', JWT_SECRET)
        monkeypatch.delenv('NLWEB_DEV_AUTH_BYPASS', raising=False)
        async with TestClient(TestServer(_build_app())) as client:
            resp = await client.get('/api/protected')
            assert resp.status == 401
            data = await resp.json()
            assert data['type'] == 'auth_required'

    @pytest.mark.asyncio
    async def test_valid_token_passes(self, monkeypatch):
        """Protected endpoint with valid JWT -> request['user'] has id, org_id, role."""
        monkeypatch.setenv('JWT_SECRET', JWT_SECRET)
        token = _make_jwt({
            'user_id': 'u-prot',
            'email': 'prot@test.com',
            'name': 'Protected User',
            'org_id': 'org-789',
            'role': 'admin',
        })
        async with TestClient(TestServer(_build_app())) as client:
            resp = await client.get('/api/protected', headers={'Authorization': f'Bearer {token}'})
            assert resp.status == 200
            data = await resp.json()
            user = data['user']
            assert user['id'] == 'u-prot'
            assert user['org_id'] == 'org-789'
            assert user['role'] == 'admin'
            assert user['authenticated'] is True

    @pytest.mark.asyncio
    async def test_expired_token_returns_401(self, monkeypatch):
        """Protected endpoint with expired JWT -> 401 with type=token_expired."""
        monkeypatch.setenv('JWT_SECRET', JWT_SECRET)
        token = _make_jwt({}, expired=True)
        async with TestClient(TestServer(_build_app())) as client:
            resp = await client.get('/api/protected', headers={'Authorization': f'Bearer {token}'})
            assert resp.status == 401
            data = await resp.json()
            assert data['type'] == 'token_expired'

    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(self, monkeypatch):
        """Protected endpoint with garbage token -> 401."""
        monkeypatch.setenv('JWT_SECRET', JWT_SECRET)
        async with TestClient(TestServer(_build_app())) as client:
            resp = await client.get('/api/protected', headers={'Authorization': 'Bearer not.a.jwt'})
            assert resp.status == 401
            data = await resp.json()
            assert data['type'] == 'invalid_token'

    @pytest.mark.asyncio
    async def test_wrong_secret_returns_401(self, monkeypatch):
        """Token signed with wrong secret -> 401."""
        monkeypatch.setenv('JWT_SECRET', JWT_SECRET)
        token = _make_jwt({}, secret='wrong-secret')
        async with TestClient(TestServer(_build_app())) as client:
            resp = await client.get('/api/protected', headers={'Authorization': f'Bearer {token}'})
            assert resp.status == 401

    @pytest.mark.asyncio
    async def test_token_missing_user_id_returns_401(self, monkeypatch):
        """JWT with no user_id claim -> 401 invalid_token."""
        monkeypatch.setenv('JWT_SECRET', JWT_SECRET)
        now = int(time.time())
        payload = {'email': 'x@y.com', 'iat': now, 'exp': now + 3600}  # no user_id
        token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        async with TestClient(TestServer(_build_app())) as client:
            resp = await client.get('/api/protected', headers={'Authorization': f'Bearer {token}'})
            assert resp.status == 401
            data = await resp.json()
            assert data['type'] == 'invalid_token'


# ── Dev Auth Bypass Tests ────────────────────────────────────────


class TestDevAuthBypass:

    @pytest.mark.asyncio
    async def test_bypass_no_token_passes(self, monkeypatch):
        """NLWEB_DEV_AUTH_BYPASS=true -> protected endpoint passes with authenticated=False."""
        monkeypatch.setenv('JWT_SECRET', JWT_SECRET)
        monkeypatch.setenv('NLWEB_DEV_AUTH_BYPASS', 'true')
        async with TestClient(TestServer(_build_app())) as client:
            resp = await client.get('/api/protected')
            assert resp.status == 200
            data = await resp.json()
            assert data['user']['id'] == 'dev_user'
            assert data['user']['authenticated'] is False

    @pytest.mark.asyncio
    async def test_bypass_with_token_uses_jwt(self, monkeypatch):
        """Even with bypass enabled, if a valid token is provided, it should use JWT auth."""
        monkeypatch.setenv('JWT_SECRET', JWT_SECRET)
        monkeypatch.setenv('NLWEB_DEV_AUTH_BYPASS', 'true')
        token = _make_jwt({'user_id': 'real-user'})
        async with TestClient(TestServer(_build_app())) as client:
            resp = await client.get('/api/protected', headers={'Authorization': f'Bearer {token}'})
            assert resp.status == 200
            data = await resp.json()
            assert data['user']['id'] == 'real-user'
            assert data['user']['authenticated'] is True


# ── JWT_SECRET Not Set Tests ────────────────────────────────────


class TestJWTSecretNotSet:

    @pytest.mark.asyncio
    async def test_protected_returns_500(self, monkeypatch):
        """Protected endpoint without JWT_SECRET configured -> 500."""
        monkeypatch.delenv('JWT_SECRET', raising=False)
        monkeypatch.delenv('NLWEB_DEV_AUTH_BYPASS', raising=False)
        token = _make_jwt({})  # signed with test secret, but server has no secret
        async with TestClient(TestServer(_build_app())) as client:
            resp = await client.get('/api/protected', headers={'Authorization': f'Bearer {token}'})
            assert resp.status == 500
            data = await resp.json()
            assert data['type'] == 'auth_not_configured'

    @pytest.mark.asyncio
    async def test_public_still_works(self, monkeypatch):
        """Public endpoints should work even without JWT_SECRET."""
        monkeypatch.delenv('JWT_SECRET', raising=False)
        async with TestClient(TestServer(_build_app())) as client:
            resp = await client.get('/health')
            assert resp.status == 200


# ── Auth Token from Cookie Tests ─────────────────────────────────


class TestCookieAuth:

    @pytest.mark.asyncio
    async def test_auth_from_cookie(self, monkeypatch):
        """Protected endpoint should accept auth_token from cookie."""
        monkeypatch.setenv('JWT_SECRET', JWT_SECRET)
        monkeypatch.delenv('NLWEB_DEV_AUTH_BYPASS', raising=False)
        token = _make_jwt({'user_id': 'cookie-user'})
        async with TestClient(TestServer(_build_app())) as client:
            client.session.cookie_jar.update_cookies({'auth_token': token})
            resp = await client.get('/api/protected')
            assert resp.status == 200
            data = await resp.json()
            assert data['user']['id'] == 'cookie-user'


# ── Query Param Auth Tests ──────────────────────────────────────


class TestQueryParamAuth:

    @pytest.mark.asyncio
    async def test_auth_from_query_param(self, monkeypatch):
        """Protected GET endpoint should accept auth_token from query param."""
        monkeypatch.setenv('JWT_SECRET', JWT_SECRET)
        monkeypatch.delenv('NLWEB_DEV_AUTH_BYPASS', raising=False)
        token = _make_jwt({'user_id': 'query-user'})
        async with TestClient(TestServer(_build_app())) as client:
            resp = await client.get(f'/api/protected?auth_token={token}')
            assert resp.status == 200
            data = await resp.json()
            assert data['user']['id'] == 'query-user'
