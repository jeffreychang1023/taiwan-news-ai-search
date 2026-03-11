"""
Auth API routes: register, login, token refresh, password reset, org management.

All handlers directly await async AuthService methods (no asyncio.to_thread).
"""

import os

from aiohttp import web
from misc.logger.logging_config_helper import get_configured_logger
from core.audit_service import log_action, fire_and_forget

logger = get_configured_logger("auth_routes")

# BP-5: Only trust X-Forwarded-For from known proxies
_TRUSTED_PROXIES = set(
    p.strip() for p in os.environ.get('TRUSTED_PROXIES', '127.0.0.1').split(',') if p.strip()
)


def _get_service():
    """Lazy-init AuthService to avoid import-time DB hits."""
    from auth.auth_service import AuthService
    if not hasattr(_get_service, '_instance'):
        _get_service._instance = AuthService()
    return _get_service._instance


def _get_client_ip(request: web.Request) -> str:
    """Extract client IP, only trusting XFF from known proxies (BP-5)."""
    peername = request.transport.get_extra_info('peername')
    direct_ip = peername[0] if peername else '0.0.0.0'

    if direct_ip in _TRUSTED_PROXIES:
        forwarded = request.headers.get('X-Forwarded-For', '')
        if forwarded:
            return forwarded.split(',')[0].strip()

    return direct_ip


# ── Auth Routes ───────────────────────────────────────────────────

async def register_handler(request: web.Request) -> web.Response:
    """POST /api/auth/register — Bootstrap first admin only (B2B)."""
    try:
        body = await request.json()
    except Exception:
        return web.json_response({'error': 'Invalid JSON'}, status=400)

    email = body.get('email', '')
    password = body.get('password', '')
    name = body.get('name', '')
    org_name = body.get('org_name', '')

    if not email or not password or not name:
        return web.json_response({'error': 'email, password, and name are required'}, status=400)

    try:
        user = await _get_service().register_user(email, password, name, org_name)
        fire_and_forget(log_action(
            'auth.bootstrap',
            user_id=user.get('id'),
            ip=_get_client_ip(request),
            details={'email': email, 'name': name, 'org_name': org_name},
        ))
        return web.json_response({'success': True, 'user': user})
    except ValueError as e:
        return web.json_response({'error': str(e)}, status=400)
    except Exception as e:
        logger.error(f"Register error: {e}", exc_info=True)
        return web.json_response({'error': 'Internal server error'}, status=500)


async def verify_email_handler(request: web.Request) -> web.Response:
    """GET /api/auth/verify-email?token=xxx"""
    token = request.query.get('token', '')
    if not token:
        return web.json_response({'error': 'Token is required'}, status=400)

    try:
        user = await _get_service().verify_email(token)
        return web.json_response({'success': True, 'message': 'Email verified successfully', 'user': user})
    except ValueError as e:
        return web.json_response({'error': str(e)}, status=400)
    except Exception as e:
        logger.error(f"Verify email error: {e}", exc_info=True)
        return web.json_response({'error': 'Internal server error'}, status=500)


async def login_handler(request: web.Request) -> web.Response:
    """POST /api/auth/login"""
    try:
        body = await request.json()
    except Exception:
        return web.json_response({'error': 'Invalid JSON'}, status=400)

    email = body.get('email', '')
    password = body.get('password', '')

    if not email or not password:
        return web.json_response({'error': 'email and password are required'}, status=400)

    ip = _get_client_ip(request)

    try:
        result = await _get_service().login(email, password, ip)

        fire_and_forget(log_action(
            'auth.login',
            user_id=result.get('user', {}).get('id'),
            org_id=result.get('user', {}).get('org_id'),
            ip=ip,
            details={'email': email},
        ))

        # BP-1: Set access token as httpOnly cookie (replaces localStorage)
        access_token = result.pop('access_token')
        refresh_token = result.pop('refresh_token')
        response = web.json_response({'success': True, **result})
        response.set_cookie(
            'access_token', access_token,
            httponly=True,
            secure=request.secure,
            samesite='Lax',
            max_age=15 * 60,  # 15 minutes (match JWT expiry)
            path='/'
        )
        response.set_cookie(
            'refresh_token', refresh_token,
            httponly=True,
            secure=request.secure,
            samesite='Lax',
            max_age=7 * 24 * 3600,
            path='/api/auth'
        )
        return response
    except ValueError as e:
        fire_and_forget(log_action(
            'auth.login_failed',
            ip=ip,
            details={'email': email, 'reason': str(e)},
        ))
        return web.json_response({'error': str(e)}, status=401)
    except RuntimeError as e:
        logger.error(f"Login config error: {e}")
        return web.json_response({'error': 'Authentication not configured'}, status=500)
    except Exception as e:
        logger.error(f"Login error: {e}", exc_info=True)
        return web.json_response({'error': 'Internal server error'}, status=500)


async def refresh_handler(request: web.Request) -> web.Response:
    """POST /api/auth/refresh"""
    refresh_token_value = request.cookies.get('refresh_token', '')

    if not refresh_token_value:
        try:
            body = await request.json()
            refresh_token_value = body.get('refresh_token', '')
        except Exception:
            pass

    if not refresh_token_value:
        return web.json_response({'error': 'Refresh token is required'}, status=400)

    try:
        result = await _get_service().refresh_token(refresh_token_value)

        # BP-1: Set new access token cookie
        access_token = result.pop('access_token')
        # BP-2: Set rotated refresh token cookie
        new_refresh_token = result.pop('refresh_token')

        response = web.json_response({'success': True, **result})
        response.set_cookie(
            'access_token', access_token,
            httponly=True,
            secure=request.secure,
            samesite='Lax',
            max_age=15 * 60,
            path='/'
        )
        response.set_cookie(
            'refresh_token', new_refresh_token,
            httponly=True,
            secure=request.secure,
            samesite='Lax',
            max_age=7 * 24 * 3600,
            path='/api/auth'
        )
        return response
    except ValueError as e:
        return web.json_response({'error': str(e)}, status=401)
    except Exception as e:
        logger.error(f"Refresh error: {e}", exc_info=True)
        return web.json_response({'error': 'Internal server error'}, status=500)


async def logout_handler(request: web.Request) -> web.Response:
    """POST /api/auth/logout"""
    refresh_token_value = request.cookies.get('refresh_token', '')

    if not refresh_token_value:
        try:
            body = await request.json()
            refresh_token_value = body.get('refresh_token', '')
        except Exception:
            pass

    if refresh_token_value:
        try:
            await _get_service().logout(refresh_token_value)
        except Exception as e:
            logger.warning(f"Logout error: {e}")

    response = web.json_response({'success': True, 'message': 'Logged out'})
    response.del_cookie('access_token', path='/')
    response.del_cookie('refresh_token', path='/api/auth')
    return response


async def me_handler(request: web.Request) -> web.Response:
    """GET /api/auth/me — Get current user info (requires auth)."""
    user_info = request.get('user')
    if not user_info or not user_info.get('authenticated'):
        return web.json_response({'error': 'Not authenticated'}, status=401)

    try:
        user = await _get_service().get_user_by_id(user_info['id'])
        if not user:
            return web.json_response({'error': 'User not found'}, status=404)

        user['org_id'] = user_info.get('org_id')
        user['role'] = user_info.get('role')

        return web.json_response({'success': True, 'user': user})
    except Exception as e:
        logger.error(f"Me handler error: {e}", exc_info=True)
        return web.json_response({'error': 'Internal server error'}, status=500)


async def forgot_password_handler(request: web.Request) -> web.Response:
    """POST /api/auth/forgot-password"""
    try:
        body = await request.json()
    except Exception:
        return web.json_response({'error': 'Invalid JSON'}, status=400)

    email = body.get('email', '')
    if not email:
        return web.json_response({'error': 'email is required'}, status=400)

    try:
        await _get_service().forgot_password(email)
        return web.json_response({'success': True, 'message': 'If the email exists, a reset link has been sent.'})
    except Exception as e:
        logger.error(f"Forgot password error: {e}", exc_info=True)
        return web.json_response({'error': 'Internal server error'}, status=500)


async def reset_password_handler(request: web.Request) -> web.Response:
    """POST /api/auth/reset-password"""
    try:
        body = await request.json()
    except Exception:
        return web.json_response({'error': 'Invalid JSON'}, status=400)

    token = body.get('token', '')
    new_password = body.get('new_password', '')

    if not token or not new_password:
        return web.json_response({'error': 'token and new_password are required'}, status=400)

    try:
        await _get_service().reset_password(token, new_password)
        fire_and_forget(log_action(
            'auth.password_reset',
            ip=_get_client_ip(request),
        ))
        return web.json_response({'success': True, 'message': 'Password reset successfully'})
    except ValueError as e:
        return web.json_response({'error': str(e)}, status=400)
    except Exception as e:
        logger.error(f"Reset password error: {e}", exc_info=True)
        return web.json_response({'error': 'Internal server error'}, status=500)


# ── Admin Routes (B2B) ────────────────────────────────────────────

async def admin_create_user_handler(request: web.Request) -> web.Response:
    """POST /api/admin/create-user — Admin creates employee account."""
    user_info = request.get('user')
    if not user_info or not user_info.get('authenticated'):
        return web.json_response({'error': 'Not authenticated'}, status=401)

    try:
        body = await request.json()
    except Exception:
        return web.json_response({'error': 'Invalid JSON'}, status=400)

    email = body.get('email', '')
    name = body.get('name', '')
    role = body.get('role', 'member')

    if not email or not name:
        return web.json_response({'error': 'email and name are required'}, status=400)

    org_id = user_info.get('org_id')
    if not org_id:
        return web.json_response({'error': 'No organization context'}, status=400)

    try:
        result = await _get_service().admin_create_user(email, name, role, org_id, user_info['id'])
        fire_and_forget(log_action(
            'admin.create_user',
            user_id=user_info['id'],
            org_id=org_id,
            ip=_get_client_ip(request),
            details={'email': email, 'name': name, 'role': role},
        ))
        return web.json_response({'success': True, 'user': result}, status=201)
    except ValueError as e:
        return web.json_response({'error': str(e)}, status=400)
    except Exception as e:
        logger.error(f"Admin create user error: {e}", exc_info=True)
        return web.json_response({'error': 'Internal server error'}, status=500)


async def activate_page_handler(request: web.Request) -> web.Response:
    """GET /api/auth/activate?token=xxx — Show password setup form."""
    token = request.query.get('token', '')
    if not token:
        return web.Response(text='Missing activation token.', content_type='text/html', status=400)

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Activate Account</title></head>
<body style="max-width:400px;margin:60px auto;font-family:sans-serif">
<h2>Set Your Password</h2>
<form id="f" onsubmit="return go()">
<input type="hidden" name="token" value="{token}">
<p><label>Password<br><input type="password" id="pw" required minlength="8" style="width:100%;padding:8px"></label></p>
<p><label>Confirm<br><input type="password" id="pw2" required style="width:100%;padding:8px"></label></p>
<p id="err" style="color:red"></p>
<button type="submit" style="padding:8px 24px">Activate</button>
</form>
<script>
async function go(){{
  event.preventDefault();
  const pw=document.getElementById('pw').value, pw2=document.getElementById('pw2').value;
  if(pw!==pw2){{document.getElementById('err').textContent='Passwords do not match';return}}
  const r=await fetch('/api/auth/activate',{{method:'POST',headers:{{'Content-Type':'application/json'}},
    body:JSON.stringify({{token:'{token}',password:pw}})}});
  const d=await r.json();
  if(d.success){{document.body.innerHTML='<h2>Account activated!</h2><p><a href="/">Go to login</a></p>'}}
  else{{document.getElementById('err').textContent=d.error||'Activation failed'}}
}}
</script>
</body></html>"""
    return web.Response(text=html, content_type='text/html')


async def activate_account_handler(request: web.Request) -> web.Response:
    """POST /api/auth/activate — Employee sets password to activate account."""
    try:
        body = await request.json()
    except Exception:
        return web.json_response({'error': 'Invalid JSON'}, status=400)

    token = body.get('token', '')
    password = body.get('password', '')

    if not token or not password:
        return web.json_response({'error': 'token and password are required'}, status=400)

    try:
        result = await _get_service().activate_account(token, password)
        fire_and_forget(log_action(
            'auth.activate',
            user_id=result.get('id'),
            ip=_get_client_ip(request),
            details={'email': result.get('email')},
        ))
        return web.json_response({'success': True, 'user': result})
    except ValueError as e:
        return web.json_response({'error': str(e)}, status=400)
    except Exception as e:
        logger.error(f"Activate account error: {e}", exc_info=True)
        return web.json_response({'error': 'Internal server error'}, status=500)


# ── Organization Routes ───────────────────────────────────────────

async def create_org_handler(request: web.Request) -> web.Response:
    """POST /api/org"""
    user_info = request.get('user')
    if not user_info or not user_info.get('authenticated'):
        return web.json_response({'error': 'Not authenticated'}, status=401)

    try:
        body = await request.json()
    except Exception:
        return web.json_response({'error': 'Invalid JSON'}, status=400)

    name = body.get('name', '')
    if not name:
        return web.json_response({'error': 'name is required'}, status=400)

    try:
        org = await _get_service().create_organization(name, user_info['id'])
        return web.json_response({'success': True, 'organization': org})
    except ValueError as e:
        return web.json_response({'error': str(e)}, status=400)
    except Exception as e:
        logger.error(f"Create org error: {e}", exc_info=True)
        return web.json_response({'error': 'Internal server error'}, status=500)


async def list_orgs_handler(request: web.Request) -> web.Response:
    """GET /api/org"""
    user_info = request.get('user')
    if not user_info or not user_info.get('authenticated'):
        return web.json_response({'error': 'Not authenticated'}, status=401)

    try:
        orgs = await _get_service().list_user_orgs(user_info['id'])
        return web.json_response({'success': True, 'organizations': orgs})
    except Exception as e:
        logger.error(f"List orgs error: {e}", exc_info=True)
        return web.json_response({'error': 'Internal server error'}, status=500)


async def invite_member_handler(request: web.Request) -> web.Response:
    """POST /api/org/{id}/invite"""
    user_info = request.get('user')
    if not user_info or not user_info.get('authenticated'):
        return web.json_response({'error': 'Not authenticated'}, status=401)

    org_id = request.match_info.get('id')

    try:
        body = await request.json()
    except Exception:
        return web.json_response({'error': 'Invalid JSON'}, status=400)

    email = body.get('email', '')
    role = body.get('role', 'member')

    if not email:
        return web.json_response({'error': 'email is required'}, status=400)

    try:
        result = await _get_service().invite_member(org_id, email, role, user_info['id'])
        fire_and_forget(log_action('member.invite', user_id=user_info['id'], org_id=org_id, target_type='org', target_id=org_id, details={'email': email, 'role': role}))
        return web.json_response({'success': True, 'invitation': result})
    except ValueError as e:
        return web.json_response({'error': str(e)}, status=400)
    except Exception as e:
        logger.error(f"Invite member error: {e}", exc_info=True)
        return web.json_response({'error': 'Internal server error'}, status=500)


async def list_members_handler(request: web.Request) -> web.Response:
    """GET /api/org/{id}/members"""
    user_info = request.get('user')
    if not user_info or not user_info.get('authenticated'):
        return web.json_response({'error': 'Not authenticated'}, status=401)

    org_id = request.match_info.get('id')

    try:
        members = await _get_service().list_org_members(org_id, user_info['id'])
        return web.json_response({'success': True, 'members': members})
    except ValueError as e:
        return web.json_response({'error': str(e)}, status=403)
    except Exception as e:
        logger.error(f"List members error: {e}", exc_info=True)
        return web.json_response({'error': 'Internal server error'}, status=500)


async def remove_member_handler(request: web.Request) -> web.Response:
    """DELETE /api/org/{id}/members/{user_id}"""
    user_info = request.get('user')
    if not user_info or not user_info.get('authenticated'):
        return web.json_response({'error': 'Not authenticated'}, status=401)

    org_id = request.match_info.get('id')
    target_user_id = request.match_info.get('user_id')

    try:
        await _get_service().remove_member(org_id, target_user_id, user_info['id'])
        fire_and_forget(log_action('member.remove', user_id=user_info['id'], org_id=org_id, target_type='org', target_id=org_id, details={'removed_user_id': target_user_id}))
        return web.json_response({'success': True, 'message': 'Member removed'})
    except ValueError as e:
        return web.json_response({'error': str(e)}, status=403)
    except Exception as e:
        logger.error(f"Remove member error: {e}", exc_info=True)
        return web.json_response({'error': 'Internal server error'}, status=500)


async def accept_invite_handler(request: web.Request) -> web.Response:
    """POST /api/org/accept-invite"""
    user_info = request.get('user')
    if not user_info or not user_info.get('authenticated'):
        return web.json_response({'error': 'Not authenticated'}, status=401)

    try:
        body = await request.json()
    except Exception:
        return web.json_response({'error': 'Invalid JSON'}, status=400)

    token = body.get('token', '')
    if not token:
        return web.json_response({'error': 'token is required'}, status=400)

    try:
        result = await _get_service().accept_invitation(token, user_info['id'])
        return web.json_response({'success': True, **result})
    except ValueError as e:
        return web.json_response({'error': str(e)}, status=400)
    except Exception as e:
        logger.error(f"Accept invite error: {e}", exc_info=True)
        return web.json_response({'error': 'Internal server error'}, status=500)


# ── Route Setup ───────────────────────────────────────────────────

def setup_auth_routes(app: web.Application):
    """Register all auth routes."""
    # Auth routes
    app.router.add_post('/api/auth/register', register_handler)
    app.router.add_get('/api/auth/verify-email', verify_email_handler)
    app.router.add_post('/api/auth/login', login_handler)
    app.router.add_post('/api/auth/refresh', refresh_handler)
    app.router.add_post('/api/auth/logout', logout_handler)
    app.router.add_get('/api/auth/me', me_handler)
    app.router.add_post('/api/auth/forgot-password', forgot_password_handler)
    app.router.add_post('/api/auth/reset-password', reset_password_handler)
    app.router.add_get('/api/auth/activate', activate_page_handler)
    app.router.add_post('/api/auth/activate', activate_account_handler)

    # Admin routes (B2B)
    app.router.add_post('/api/admin/create-user', admin_create_user_handler)

    # Organization routes
    app.router.add_post('/api/org', create_org_handler)
    app.router.add_get('/api/org', list_orgs_handler)
    app.router.add_post('/api/org/{id}/invite', invite_member_handler)
    app.router.add_get('/api/org/{id}/members', list_members_handler)
    app.router.add_delete('/api/org/{id}/members/{user_id}', remove_member_handler)
    app.router.add_post('/api/org/accept-invite', accept_invite_handler)

    logger.info("Auth routes registered")
