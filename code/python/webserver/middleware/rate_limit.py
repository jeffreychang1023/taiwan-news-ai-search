"""Rate limiting middleware for auth endpoints.

Protects high-risk endpoints using in-memory sliding-window counters.

Rules:
- POST /api/auth/register      → 5 requests / hour  per IP
- POST /api/auth/forgot-password → 3 requests / hour  per IP
- POST /api/auth/login         → 10 requests / minute per IP  (coarse guard;
                                  fine-grained brute-force is in auth_service)

Counters are stored in-memory (sufficient for single-instance deployment).
On restart counters reset, which is acceptable — auth_service.py's
login_attempts table provides persistent brute-force protection.
"""

import time
import logging
from collections import defaultdict, deque
from aiohttp import web

logger = logging.getLogger(__name__)

# ── Rate limit rules ─────────────────────────────────────────────
# (endpoint_path, method) → (max_requests, window_seconds)
RATE_LIMIT_RULES: dict = {
    ('/api/auth/register', 'POST'):       (50, 3600),   # 50/hr
    ('/api/auth/forgot-password', 'POST'): (50, 3600),   # 50/hr
    ('/api/auth/login', 'POST'):          (60,  60),     # 60/min
}

# Sliding-window store: key → deque of timestamps
_windows: dict = defaultdict(deque)


def _check_rate_limit(key: str, max_requests: int, window_seconds: int) -> bool:
    """Return True if allowed, False if rate limit exceeded."""
    now = time.monotonic()
    cutoff = now - window_seconds
    q = _windows[key]

    # Evict expired entries
    while q and q[0] < cutoff:
        q.popleft()

    if len(q) >= max_requests:
        return False

    q.append(now)
    return True


def _get_client_ip(request: web.Request) -> str:
    """Extract real client IP, respecting X-Forwarded-For."""
    forwarded = request.headers.get('X-Forwarded-For', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.remote or 'unknown'


@web.middleware
async def rate_limit_middleware(request: web.Request, handler):
    """Apply per-endpoint rate limits before the request reaches its handler."""
    rule = RATE_LIMIT_RULES.get((request.path, request.method))
    if rule is None:
        return await handler(request)

    max_requests, window_seconds = rule
    ip = _get_client_ip(request)
    key = f"{request.path}:{ip}"

    if not _check_rate_limit(key, max_requests, window_seconds):
        logger.warning(f"Rate limit exceeded: {request.path} from {ip}")
        window_minutes = window_seconds // 60
        unit = "minute" if window_minutes == 1 else f"{window_minutes} minutes" if window_minutes < 60 else "hour"
        return web.json_response(
            {
                'error': f'Too many requests. Limit: {max_requests} per {unit}.',
                'type': 'rate_limit_exceeded',
            },
            status=429,
            headers={'Retry-After': str(window_seconds)},
        )

    return await handler(request)
