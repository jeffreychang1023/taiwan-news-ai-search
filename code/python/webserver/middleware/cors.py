"""CORS middleware for aiohttp server"""

import os
import re
from aiohttp import web
import logging

logger = logging.getLogger(__name__)

# Configurable via environment variable
_EXTRA_ORIGINS = os.environ.get('CORS_ALLOWED_ORIGINS', '').split(',')
_EXTRA_ORIGINS = [o.strip() for o in _EXTRA_ORIGINS if o.strip()]

ALLOWED_ORIGINS = {
    'http://localhost:3000',
    'http://localhost:8080',
    'http://localhost:5173',
    'http://127.0.0.1:3000',
    'http://127.0.0.1:8080',
    'http://127.0.0.1:5173',
} | set(_EXTRA_ORIGINS)

RENDER_PATTERN = re.compile(r'^https://[\w-]+\.onrender\.com$')


def _is_allowed_origin(origin: str) -> bool:
    if origin in ALLOWED_ORIGINS:
        return True
    if RENDER_PATTERN.match(origin):
        return True
    return False


@web.middleware
async def cors_middleware(request: web.Request, handler):
    """Handle CORS headers for all requests"""

    # Get CORS configuration from app config
    config = request.app.get('config', {})
    cors_enabled = config.get('server', {}).get('enable_cors', True)

    if not cors_enabled:
        return await handler(request)

    # Build CORS headers based on request origin
    origin = request.headers.get('Origin', '')
    if _is_allowed_origin(origin):
        cors_headers = {
            'Access-Control-Allow-Origin': origin,
            'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Requested-With',
            'Access-Control-Allow-Credentials': 'true',
            'Access-Control-Max-Age': '3600'
        }
    else:
        # Don't set CORS headers for unknown origins
        cors_headers = {}

    # Handle preflight OPTIONS requests
    if request.method == 'OPTIONS':
        return web.Response(
            status=200,
            headers=cors_headers
        )

    # Process the request
    try:
        response = await handler(request)
    except web.HTTPException as ex:
        # Add CORS headers to HTTP exceptions
        if cors_headers:
            ex.headers.update(cors_headers)
        raise

    # Add CORS headers to successful responses
    if cors_headers:
        response.headers.update(cors_headers)

    return response
