# Auth Admin APIs Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 5 B2B admin API endpoints to the login system: change-password, logout-all, admin set-active, admin delete-user, and admin change-role.

**Architecture:** New service methods added to `AuthService` in `auth_service.py`, new route handlers added to `auth.py`, all wired into `setup_auth_routes()`. Tests added to the existing `test_auth_service.py` file. No new files created.

**Tech Stack:** Python 3.11, aiohttp, bcrypt, SQLite/PostgreSQL via AuthDB, pytest-asyncio

---

## Chunk 1: Service Methods

### Task 1: `change_password` service method

**Files:**
- Modify: `code/python/auth/auth_service.py` (after `reset_password`, before `create_organization`)
- Test: `code/python/tests/test_auth_service.py`

- [ ] **Step 1: Write the failing test**

Add to `code/python/tests/test_auth_service.py`, after the existing `TestRefreshToken` class:

```python
# ── Change Password Tests ────────────────────────────────────────


class TestChangePassword:

    @pytest.mark.asyncio
    async def test_change_password_success(self, service, _no_email):
        login_result = await _register_verify_and_login(service)
        user_id = login_result['user']['id']
        result = await service.change_password(user_id, "Password1", "NewPassw0rd")
        assert result is True
        # Old password no longer works
        with pytest.raises(ValueError, match="Invalid email or password"):
            await service.login("test@example.com", "Password1", ip="127.0.0.1")
        # New password works
        new_login = await service.login("test@example.com", "NewPassw0rd", ip="127.0.0.1")
        assert 'access_token' in new_login

    @pytest.mark.asyncio
    async def test_change_password_wrong_current(self, service, _no_email):
        login_result = await _register_verify_and_login(service)
        user_id = login_result['user']['id']
        with pytest.raises(ValueError, match="Current password is incorrect"):
            await service.change_password(user_id, "WrongPass1", "NewPassw0rd")

    @pytest.mark.asyncio
    async def test_change_password_weak_new_password(self, service, _no_email):
        login_result = await _register_verify_and_login(service)
        user_id = login_result['user']['id']
        with pytest.raises(ValueError, match="at least 8 characters"):
            await service.change_password(user_id, "Password1", "short")

    @pytest.mark.asyncio
    async def test_change_password_revokes_all_tokens(self, service, _no_email):
        """After change_password, old refresh tokens are revoked."""
        login_result = await _register_verify_and_login(service)
        user_id = login_result['user']['id']
        old_refresh = login_result['refresh_token']
        await service.change_password(user_id, "Password1", "NewPassw0rd")
        with pytest.raises(ValueError, match="revoked"):
            await service.refresh_token(old_refresh)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /c/users/user/nlweb/code/python && python -m pytest tests/test_auth_service.py::TestChangePassword -v --tb=short
```

Expected: FAIL with `AttributeError: 'AuthService' object has no attribute 'change_password'`

- [ ] **Step 3: Implement `change_password` in `auth_service.py`**

Add the following method to `AuthService`, inside the `# ── Password Reset` section, after `reset_password` and before `# ── Organization`:

```python
async def change_password(self, user_id: str, current_password: str, new_password: str) -> bool:
    """Change password for authenticated user. Revokes all refresh tokens."""
    self._validate_password(new_password)

    user = await self.db.fetchone(
        "SELECT id, password_hash FROM users WHERE id = ? AND is_active = ?",
        (user_id, True)
    )
    if not user or not user.get('password_hash'):
        raise ValueError("User not found")

    valid = bcrypt.checkpw(current_password.encode('utf-8'), user['password_hash'].encode('utf-8'))
    if not valid:
        raise ValueError("Current password is incorrect")

    new_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    await self.db.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (new_hash, user_id)
    )

    # Revoke all refresh tokens (force re-login on all devices)
    await self.db.execute(
        "UPDATE refresh_tokens SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
        (time.time(), user_id)
    )

    logger.info(f"Password changed for user: {user_id}")
    return True
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /c/users/user/nlweb/code/python && python -m pytest tests/test_auth_service.py::TestChangePassword -v --tb=short
```

Expected: 4 PASSED

---

### Task 2: `revoke_all_user_tokens` service method

**Files:**
- Modify: `code/python/auth/auth_service.py`
- Test: `code/python/tests/test_auth_service.py`

- [ ] **Step 5: Write the failing test**

Add to `test_auth_service.py` after `TestChangePassword`:

```python
# ── Revoke All User Tokens Tests ────────────────────────────────


class TestRevokeAllUserTokens:

    @pytest.mark.asyncio
    async def test_revoke_all_tokens_success(self, service, _no_email):
        login_result = await _register_verify_and_login(service)
        user_id = login_result['user']['id']
        old_refresh = login_result['refresh_token']
        result = await service.revoke_all_user_tokens(user_id)
        assert result is True
        with pytest.raises(ValueError, match="revoked"):
            await service.refresh_token(old_refresh)

    @pytest.mark.asyncio
    async def test_revoke_all_tokens_multiple_sessions(self, service, _no_email):
        """Revokes tokens from multiple login sessions."""
        await _register_and_verify(service)
        r1 = await service.login("test@example.com", "Password1", ip="1.1.1.1")
        r2 = await service.login("test@example.com", "Password1", ip="2.2.2.2")
        user_id = r1['user']['id']
        await service.revoke_all_user_tokens(user_id)
        with pytest.raises(ValueError, match="revoked"):
            await service.refresh_token(r1['refresh_token'])
        with pytest.raises(ValueError, match="revoked"):
            await service.refresh_token(r2['refresh_token'])
```

- [ ] **Step 6: Run test to verify it fails**

```bash
cd /c/users/user/nlweb/code/python && python -m pytest tests/test_auth_service.py::TestRevokeAllUserTokens -v --tb=short
```

Expected: FAIL with `AttributeError`

- [ ] **Step 7: Implement `revoke_all_user_tokens` in `auth_service.py`**

Add after `change_password`, before `create_organization`:

```python
async def revoke_all_user_tokens(self, user_id: str) -> bool:
    """Revoke all active refresh tokens for a user (logout all devices)."""
    await self.db.execute(
        "UPDATE refresh_tokens SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
        (time.time(), user_id)
    )
    logger.info(f"All tokens revoked for user: {user_id}")
    return True
```

- [ ] **Step 8: Run tests to verify they pass**

```bash
cd /c/users/user/nlweb/code/python && python -m pytest tests/test_auth_service.py::TestRevokeAllUserTokens -v --tb=short
```

Expected: 2 PASSED

---

### Task 3: `set_user_active` service method

**Files:**
- Modify: `code/python/auth/auth_service.py`
- Test: `code/python/tests/test_auth_service.py`

- [ ] **Step 9: Write the failing test**

Add to `test_auth_service.py`:

```python
# ── Set User Active Tests ────────────────────────────────────────


class TestSetUserActive:

    async def _setup_admin_and_member(self, service):
        """Helper: bootstrap admin, create a member. Returns (admin_id, org_id, member_id)."""
        admin = await service.register_user("admin@e.com", "Passw0rd", "Admin")
        db = AuthDB.get_instance()
        org = await db.fetchone("SELECT id FROM organizations LIMIT 1")
        org_id = org['id']
        member = await service.admin_create_user("member@e.com", "Member", "member", org_id, admin['id'])
        return admin['id'], org_id, member['id']

    @pytest.mark.asyncio
    async def test_deactivate_user(self, service, _no_email):
        admin_id, org_id, member_id = await self._setup_admin_and_member(service)
        # Activate member first so they have a password
        db = AuthDB.get_instance()
        row = await db.fetchone("SELECT email_verification_token FROM users WHERE id = ?", (member_id,))
        await service.activate_account(row['email_verification_token'], "MemberPass1")

        result = await service.set_user_active(member_id, False, admin_id, org_id)
        assert result is True
        user = await db.fetchone("SELECT is_active FROM users WHERE id = ?", (member_id,))
        assert user['is_active'] in (0, False)

    @pytest.mark.asyncio
    async def test_deactivate_user_revokes_tokens(self, service, _no_email):
        admin_id, org_id, member_id = await self._setup_admin_and_member(service)
        db = AuthDB.get_instance()
        row = await db.fetchone("SELECT email_verification_token FROM users WHERE id = ?", (member_id,))
        await service.activate_account(row['email_verification_token'], "MemberPass1")
        # Member logs in to get a token
        member_login = await service.login("member@e.com", "MemberPass1", ip="127.0.0.1")
        await service.set_user_active(member_id, False, admin_id, org_id)
        with pytest.raises(ValueError, match="deactivated"):
            await service.refresh_token(member_login['refresh_token'])

    @pytest.mark.asyncio
    async def test_reactivate_user(self, service, _no_email):
        admin_id, org_id, member_id = await self._setup_admin_and_member(service)
        await service.set_user_active(member_id, False, admin_id, org_id)
        result = await service.set_user_active(member_id, True, admin_id, org_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_cannot_deactivate_self(self, service, _no_email):
        admin_id, org_id, _ = await self._setup_admin_and_member(service)
        with pytest.raises(ValueError, match="Cannot deactivate your own account"):
            await service.set_user_active(admin_id, False, admin_id, org_id)

    @pytest.mark.asyncio
    async def test_non_admin_cannot_deactivate(self, service, _no_email):
        admin_id, org_id, member_id = await self._setup_admin_and_member(service)
        with pytest.raises(ValueError, match="Only admins"):
            await service.set_user_active(admin_id, False, member_id, org_id)
```

- [ ] **Step 10: Run test to verify it fails**

```bash
cd /c/users/user/nlweb/code/python && python -m pytest tests/test_auth_service.py::TestSetUserActive -v --tb=short
```

Expected: FAIL with `AttributeError`

- [ ] **Step 11: Implement `set_user_active` in `auth_service.py`**

Add after `revoke_all_user_tokens`, before `create_organization`:

```python
async def set_user_active(self, target_user_id: str, is_active: bool,
                           admin_user_id: str, org_id: str) -> bool:
    """Admin activates or deactivates a user. Deactivation also revokes all tokens."""
    if target_user_id == admin_user_id:
        raise ValueError("Cannot deactivate your own account")

    membership = await self.db.fetchone(
        "SELECT role FROM org_memberships WHERE user_id = ? AND org_id = ? AND status = 'active'",
        (admin_user_id, org_id)
    )
    if not membership or membership['role'] != 'admin':
        raise ValueError("Only admins can change user status")

    # Verify target is in same org
    target_membership = await self.db.fetchone(
        "SELECT id FROM org_memberships WHERE user_id = ? AND org_id = ? AND status = 'active'",
        (target_user_id, org_id)
    )
    if not target_membership:
        raise ValueError("User not found in organization")

    active_val = True if is_active else False
    if self.db.db_type == 'sqlite':
        active_val = 1 if is_active else 0

    await self.db.execute(
        "UPDATE users SET is_active = ? WHERE id = ?",
        (active_val, target_user_id)
    )

    if not is_active:
        await self.revoke_all_user_tokens(target_user_id)

    logger.info(f"User {target_user_id} set is_active={is_active} by admin {admin_user_id}")
    return True
```

- [ ] **Step 12: Run tests to verify they pass**

```bash
cd /c/users/user/nlweb/code/python && python -m pytest tests/test_auth_service.py::TestSetUserActive -v --tb=short
```

Expected: 5 PASSED

---

### Task 4: `delete_user` service method

**Files:**
- Modify: `code/python/auth/auth_service.py`
- Test: `code/python/tests/test_auth_service.py`

- [ ] **Step 13: Write the failing test**

Add to `test_auth_service.py`:

```python
# ── Delete User Tests ────────────────────────────────────────────


class TestDeleteUser:

    async def _setup_admin_and_member(self, service):
        admin = await service.register_user("admin@e.com", "Passw0rd", "Admin")
        db = AuthDB.get_instance()
        org = await db.fetchone("SELECT id FROM organizations LIMIT 1")
        org_id = org['id']
        member = await service.admin_create_user("member@e.com", "Member", "member", org_id, admin['id'])
        return admin['id'], org_id, member['id']

    @pytest.mark.asyncio
    async def test_delete_user_success(self, service, _no_email):
        admin_id, org_id, member_id = await self._setup_admin_and_member(service)
        result = await service.delete_user(member_id, admin_id, org_id)
        assert result is True
        db = AuthDB.get_instance()
        user = await db.fetchone("SELECT is_active, email FROM users WHERE id = ?", (member_id,))
        assert user['is_active'] in (0, False)
        assert '_deleted_' in user['email']

    @pytest.mark.asyncio
    async def test_delete_user_removes_membership(self, service, _no_email):
        admin_id, org_id, member_id = await self._setup_admin_and_member(service)
        await service.delete_user(member_id, admin_id, org_id)
        db = AuthDB.get_instance()
        membership = await db.fetchone(
            "SELECT status FROM org_memberships WHERE user_id = ? AND org_id = ?",
            (member_id, org_id)
        )
        assert membership['status'] == 'removed'

    @pytest.mark.asyncio
    async def test_delete_user_revokes_tokens(self, service, _no_email):
        admin_id, org_id, member_id = await self._setup_admin_and_member(service)
        db = AuthDB.get_instance()
        row = await db.fetchone("SELECT email_verification_token FROM users WHERE id = ?", (member_id,))
        await service.activate_account(row['email_verification_token'], "MemberPass1")
        member_login = await service.login("member@e.com", "MemberPass1", ip="127.0.0.1")
        await service.delete_user(member_id, admin_id, org_id)
        # Token revoked → deactivated error
        with pytest.raises(ValueError):
            await service.refresh_token(member_login['refresh_token'])

    @pytest.mark.asyncio
    async def test_cannot_delete_self(self, service, _no_email):
        admin_id, org_id, _ = await self._setup_admin_and_member(service)
        with pytest.raises(ValueError, match="Cannot delete your own account"):
            await service.delete_user(admin_id, admin_id, org_id)

    @pytest.mark.asyncio
    async def test_non_admin_cannot_delete(self, service, _no_email):
        admin_id, org_id, member_id = await self._setup_admin_and_member(service)
        with pytest.raises(ValueError, match="Only admins"):
            await service.delete_user(admin_id, member_id, org_id)
```

- [ ] **Step 14: Run test to verify it fails**

```bash
cd /c/users/user/nlweb/code/python && python -m pytest tests/test_auth_service.py::TestDeleteUser -v --tb=short
```

Expected: FAIL with `AttributeError`

- [ ] **Step 15: Implement `delete_user` in `auth_service.py`**

Add after `set_user_active`, before `create_organization`:

```python
async def delete_user(self, target_user_id: str, admin_user_id: str, org_id: str) -> bool:
    """Soft-delete a user: revoke tokens, remove from org, deactivate, mangle email."""
    if target_user_id == admin_user_id:
        raise ValueError("Cannot delete your own account")

    membership = await self.db.fetchone(
        "SELECT role FROM org_memberships WHERE user_id = ? AND org_id = ? AND status = 'active'",
        (admin_user_id, org_id)
    )
    if not membership or membership['role'] != 'admin':
        raise ValueError("Only admins can delete users")

    target_membership = await self.db.fetchone(
        "SELECT id FROM org_memberships WHERE user_id = ? AND org_id = ? AND status = 'active'",
        (target_user_id, org_id)
    )
    if not target_membership:
        raise ValueError("User not found in organization")

    # Revoke all tokens first
    await self.revoke_all_user_tokens(target_user_id)

    # Remove from org
    await self.db.execute(
        "UPDATE org_memberships SET status = 'removed' WHERE user_id = ? AND org_id = ? AND status = 'active'",
        (target_user_id, org_id)
    )

    # Soft delete: deactivate + mangle email to allow re-registration
    user = await self.db.fetchone("SELECT email FROM users WHERE id = ?", (target_user_id,))
    deleted_email = f"_deleted_{uuid.uuid4().hex[:8]}_{user['email']}"
    active_val = False if self.db.db_type == 'postgres' else 0
    await self.db.execute(
        "UPDATE users SET is_active = ?, email = ? WHERE id = ?",
        (active_val, deleted_email, target_user_id)
    )

    logger.info(f"User {target_user_id} soft-deleted by admin {admin_user_id} in org {org_id}")
    return True
```

- [ ] **Step 16: Run tests to verify they pass**

```bash
cd /c/users/user/nlweb/code/python && python -m pytest tests/test_auth_service.py::TestDeleteUser -v --tb=short
```

Expected: 5 PASSED

---

### Task 5: `change_member_role` service method

**Files:**
- Modify: `code/python/auth/auth_service.py`
- Test: `code/python/tests/test_auth_service.py`

- [ ] **Step 17: Write the failing test**

Add to `test_auth_service.py`:

```python
# ── Change Member Role Tests ─────────────────────────────────────


class TestChangeMemberRole:

    async def _setup_admin_and_member(self, service):
        admin = await service.register_user("admin@e.com", "Passw0rd", "Admin")
        db = AuthDB.get_instance()
        org = await db.fetchone("SELECT id FROM organizations LIMIT 1")
        org_id = org['id']
        member = await service.admin_create_user("member@e.com", "Member", "member", org_id, admin['id'])
        return admin['id'], org_id, member['id']

    @pytest.mark.asyncio
    async def test_promote_to_admin(self, service, _no_email):
        admin_id, org_id, member_id = await self._setup_admin_and_member(service)
        result = await service.change_member_role(org_id, member_id, "admin", admin_id)
        assert result is True
        db = AuthDB.get_instance()
        row = await db.fetchone(
            "SELECT role FROM org_memberships WHERE user_id = ? AND org_id = ?",
            (member_id, org_id)
        )
        assert row['role'] == 'admin'

    @pytest.mark.asyncio
    async def test_demote_to_member(self, service, _no_email):
        admin_id, org_id, member_id = await self._setup_admin_and_member(service)
        # Promote first
        await service.change_member_role(org_id, member_id, "admin", admin_id)
        # Then demote
        result = await service.change_member_role(org_id, member_id, "member", admin_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_invalid_role(self, service, _no_email):
        admin_id, org_id, member_id = await self._setup_admin_and_member(service)
        with pytest.raises(ValueError, match="role must be"):
            await service.change_member_role(org_id, member_id, "superuser", admin_id)

    @pytest.mark.asyncio
    async def test_cannot_change_own_role(self, service, _no_email):
        admin_id, org_id, _ = await self._setup_admin_and_member(service)
        with pytest.raises(ValueError, match="Cannot change your own role"):
            await service.change_member_role(org_id, admin_id, "member", admin_id)

    @pytest.mark.asyncio
    async def test_non_admin_cannot_change_role(self, service, _no_email):
        admin_id, org_id, member_id = await self._setup_admin_and_member(service)
        with pytest.raises(ValueError, match="Only admins"):
            await service.change_member_role(org_id, admin_id, "member", member_id)
```

- [ ] **Step 18: Run test to verify it fails**

```bash
cd /c/users/user/nlweb/code/python && python -m pytest tests/test_auth_service.py::TestChangeMemberRole -v --tb=short
```

Expected: FAIL with `AttributeError`

- [ ] **Step 19: Implement `change_member_role` in `auth_service.py`**

Add after `delete_user`, before `create_organization`:

```python
async def change_member_role(self, org_id: str, target_user_id: str,
                              new_role: str, admin_user_id: str) -> bool:
    """Change a member's role in an organization."""
    if target_user_id == admin_user_id:
        raise ValueError("Cannot change your own role")

    if new_role not in ('admin', 'member'):
        raise ValueError("role must be 'admin' or 'member'")

    membership = await self.db.fetchone(
        "SELECT role FROM org_memberships WHERE user_id = ? AND org_id = ? AND status = 'active'",
        (admin_user_id, org_id)
    )
    if not membership or membership['role'] != 'admin':
        raise ValueError("Only admins can change member roles")

    target_membership = await self.db.fetchone(
        "SELECT id FROM org_memberships WHERE user_id = ? AND org_id = ? AND status = 'active'",
        (target_user_id, org_id)
    )
    if not target_membership:
        raise ValueError("User not found in organization")

    await self.db.execute(
        "UPDATE org_memberships SET role = ? WHERE user_id = ? AND org_id = ? AND status = 'active'",
        (new_role, target_user_id, org_id)
    )

    logger.info(f"User {target_user_id} role changed to {new_role} by admin {admin_user_id} in org {org_id}")
    return True
```

- [ ] **Step 20: Run tests to verify they pass**

```bash
cd /c/users/user/nlweb/code/python && python -m pytest tests/test_auth_service.py::TestChangeMemberRole -v --tb=short
```

Expected: 5 PASSED

- [ ] **Step 21: Run all service tests to confirm no regressions**

```bash
cd /c/users/user/nlweb/code/python && python -m pytest tests/test_auth_service.py -v --tb=short
```

Expected: All existing + new tests PASS (no regressions)

- [ ] **Step 22: Commit service layer**

```bash
cd /c/users/user/nlweb && git add code/python/auth/auth_service.py code/python/tests/test_auth_service.py
git commit -m "feat: add 5 admin service methods — change_password, revoke_all_user_tokens, set_user_active, delete_user, change_member_role"
```

---

## Chunk 2: Route Handlers

### Task 6: `change_password` and `logout-all` route handlers

**Files:**
- Modify: `code/python/webserver/routes/auth.py`

- [ ] **Step 23: Add `change_password_handler` to `auth.py`**

Add after `logout_handler`, before `me_handler`:

```python
async def change_password_handler(request: web.Request) -> web.Response:
    """POST /api/auth/change-password — Authenticated user changes their own password."""
    user_info = request.get('user')
    if not user_info or not user_info.get('authenticated'):
        return web.json_response({'error': 'Not authenticated'}, status=401)

    try:
        body = await request.json()
    except Exception:
        return web.json_response({'error': 'Invalid JSON'}, status=400)

    current_password = body.get('current_password', '')
    new_password = body.get('new_password', '')

    if not current_password or not new_password:
        return web.json_response({'error': 'current_password and new_password are required'}, status=400)

    try:
        await _get_service().change_password(user_info['id'], current_password, new_password)
        fire_and_forget(log_action(
            'auth.change_password',
            user_id=user_info['id'],
            org_id=user_info.get('org_id'),
            ip=_get_client_ip(request),
        ))
        return web.json_response({'success': True, 'message': 'Password changed. Please log in again.'})
    except ValueError as e:
        return web.json_response({'error': str(e)}, status=400)
    except Exception as e:
        logger.error(f"Change password error: {e}", exc_info=True)
        return web.json_response({'error': 'Internal server error'}, status=500)
```

- [ ] **Step 24: Add `logout_all_handler` to `auth.py`**

Add after `change_password_handler`:

```python
async def logout_all_handler(request: web.Request) -> web.Response:
    """POST /api/auth/logout-all — Authenticated user logs out all their devices."""
    user_info = request.get('user')
    if not user_info or not user_info.get('authenticated'):
        return web.json_response({'error': 'Not authenticated'}, status=401)

    try:
        await _get_service().revoke_all_user_tokens(user_info['id'])
        fire_and_forget(log_action(
            'auth.logout_all',
            user_id=user_info['id'],
            org_id=user_info.get('org_id'),
            ip=_get_client_ip(request),
        ))
        response = web.json_response({'success': True, 'message': 'Logged out from all devices'})
        response.del_cookie('access_token', path='/')
        response.del_cookie('refresh_token', path='/api/auth')
        return response
    except Exception as e:
        logger.error(f"Logout all error: {e}", exc_info=True)
        return web.json_response({'error': 'Internal server error'}, status=500)
```

- [ ] **Step 25: Add `admin_logout_user_handler` to `auth.py`**

Add in the Admin Routes section, after `admin_create_user_handler`:

```python
async def admin_logout_user_handler(request: web.Request) -> web.Response:
    """POST /api/admin/logout-user/{user_id} — Admin force-logs-out a member."""
    user_info = request.get('user')
    if not user_info or not user_info.get('authenticated'):
        return web.json_response({'error': 'Not authenticated'}, status=401)

    target_user_id = request.match_info.get('user_id')
    org_id = user_info.get('org_id')
    if not org_id:
        return web.json_response({'error': 'No organization context'}, status=400)

    # Verify requester is admin of same org
    from auth.auth_db import AuthDB
    db = AuthDB.get_instance()
    membership = await db.fetchone(
        "SELECT role FROM org_memberships WHERE user_id = ? AND org_id = ? AND status = 'active'",
        (user_info['id'], org_id)
    )
    if not membership or membership['role'] != 'admin':
        return web.json_response({'error': 'Only admins can force logout members'}, status=403)

    # Verify target is in same org
    target_membership = await db.fetchone(
        "SELECT id FROM org_memberships WHERE user_id = ? AND org_id = ? AND status = 'active'",
        (target_user_id, org_id)
    )
    if not target_membership:
        return web.json_response({'error': 'User not found in organization'}, status=404)

    try:
        await _get_service().revoke_all_user_tokens(target_user_id)
        fire_and_forget(log_action(
            'admin.logout_user',
            user_id=user_info['id'],
            org_id=org_id,
            ip=_get_client_ip(request),
            details={'target_user_id': target_user_id},
        ))
        return web.json_response({'success': True, 'message': 'User logged out from all devices'})
    except Exception as e:
        logger.error(f"Admin logout user error: {e}", exc_info=True)
        return web.json_response({'error': 'Internal server error'}, status=500)
```

---

### Task 7: `set_active`, `delete_user`, `change_role` route handlers

**Files:**
- Modify: `code/python/webserver/routes/auth.py`

- [ ] **Step 26: Add `admin_set_user_active_handler` to `auth.py`**

Add in Admin Routes section:

```python
async def admin_set_user_active_handler(request: web.Request) -> web.Response:
    """PATCH /api/admin/user/{user_id}/active — Admin activates or deactivates a member."""
    user_info = request.get('user')
    if not user_info or not user_info.get('authenticated'):
        return web.json_response({'error': 'Not authenticated'}, status=401)

    target_user_id = request.match_info.get('user_id')
    org_id = user_info.get('org_id')
    if not org_id:
        return web.json_response({'error': 'No organization context'}, status=400)

    try:
        body = await request.json()
    except Exception:
        return web.json_response({'error': 'Invalid JSON'}, status=400)

    if 'is_active' not in body:
        return web.json_response({'error': 'is_active is required'}, status=400)

    is_active = bool(body['is_active'])

    try:
        await _get_service().set_user_active(target_user_id, is_active, user_info['id'], org_id)
        fire_and_forget(log_action(
            'admin.set_user_active',
            user_id=user_info['id'],
            org_id=org_id,
            ip=_get_client_ip(request),
            details={'target_user_id': target_user_id, 'is_active': is_active},
        ))
        action = 'activated' if is_active else 'deactivated'
        return web.json_response({'success': True, 'message': f'User {action}'})
    except ValueError as e:
        return web.json_response({'error': str(e)}, status=400)
    except Exception as e:
        logger.error(f"Admin set user active error: {e}", exc_info=True)
        return web.json_response({'error': 'Internal server error'}, status=500)
```

- [ ] **Step 27: Add `admin_delete_user_handler` to `auth.py`**

Add in Admin Routes section:

```python
async def admin_delete_user_handler(request: web.Request) -> web.Response:
    """DELETE /api/admin/user/{user_id} — Admin soft-deletes a member."""
    user_info = request.get('user')
    if not user_info or not user_info.get('authenticated'):
        return web.json_response({'error': 'Not authenticated'}, status=401)

    target_user_id = request.match_info.get('user_id')
    org_id = user_info.get('org_id')
    if not org_id:
        return web.json_response({'error': 'No organization context'}, status=400)

    try:
        await _get_service().delete_user(target_user_id, user_info['id'], org_id)
        fire_and_forget(log_action(
            'admin.delete_user',
            user_id=user_info['id'],
            org_id=org_id,
            ip=_get_client_ip(request),
            details={'target_user_id': target_user_id},
        ))
        return web.json_response({'success': True, 'message': 'User deleted'})
    except ValueError as e:
        return web.json_response({'error': str(e)}, status=400)
    except Exception as e:
        logger.error(f"Admin delete user error: {e}", exc_info=True)
        return web.json_response({'error': 'Internal server error'}, status=500)
```

- [ ] **Step 28: Add `admin_change_role_handler` to `auth.py`**

Add in Admin Routes section:

```python
async def admin_change_role_handler(request: web.Request) -> web.Response:
    """PATCH /api/admin/user/{user_id}/role — Admin changes a member's role."""
    user_info = request.get('user')
    if not user_info or not user_info.get('authenticated'):
        return web.json_response({'error': 'Not authenticated'}, status=401)

    target_user_id = request.match_info.get('user_id')
    org_id = user_info.get('org_id')
    if not org_id:
        return web.json_response({'error': 'No organization context'}, status=400)

    try:
        body = await request.json()
    except Exception:
        return web.json_response({'error': 'Invalid JSON'}, status=400)

    role = body.get('role', '')
    if not role:
        return web.json_response({'error': 'role is required'}, status=400)

    try:
        await _get_service().change_member_role(org_id, target_user_id, role, user_info['id'])
        fire_and_forget(log_action(
            'admin.change_role',
            user_id=user_info['id'],
            org_id=org_id,
            ip=_get_client_ip(request),
            details={'target_user_id': target_user_id, 'new_role': role},
        ))
        return web.json_response({'success': True, 'message': f'Role updated to {role}'})
    except ValueError as e:
        return web.json_response({'error': str(e)}, status=400)
    except Exception as e:
        logger.error(f"Admin change role error: {e}", exc_info=True)
        return web.json_response({'error': 'Internal server error'}, status=500)
```

---

### Task 8: Register all new routes in `setup_auth_routes`

**Files:**
- Modify: `code/python/webserver/routes/auth.py` — `setup_auth_routes` function

- [ ] **Step 29: Update `setup_auth_routes` to register new routes**

In `setup_auth_routes()`, add after the existing auth routes (after `app.router.add_post('/api/auth/activate', activate_account_handler)`):

```python
    app.router.add_post('/api/auth/change-password', change_password_handler)
    app.router.add_post('/api/auth/logout-all', logout_all_handler)
```

And in the Admin routes section, add after `app.router.add_post('/api/admin/create-user', admin_create_user_handler)`:

```python
    app.router.add_post('/api/admin/logout-user/{user_id}', admin_logout_user_handler)
    # Literal sub-paths before {user_id} wildcard — none needed here, but keep order safe
    app.router.add_patch('/api/admin/user/{user_id}/active', admin_set_user_active_handler)
    app.router.add_patch('/api/admin/user/{user_id}/role', admin_change_role_handler)
    app.router.add_delete('/api/admin/user/{user_id}', admin_delete_user_handler)
```

**Important:** The `PATCH /active` and `PATCH /role` routes use sub-paths under `{user_id}` which is safe in aiohttp — aiohttp matches `/api/admin/user/{user_id}/active` as a distinct route from `DELETE /api/admin/user/{user_id}`.

- [ ] **Step 30: Run the full test suite to confirm everything passes**

```bash
cd /c/users/user/nlweb/code/python && python -m pytest tests/test_auth_service.py -v --tb=short
```

Expected: All tests PASS (no regressions)

- [ ] **Step 31: Final commit**

```bash
cd /c/users/user/nlweb && git add code/python/webserver/routes/auth.py
git commit -m "feat: add 6 admin route handlers — change-password, logout-all, admin logout-user, set-active, delete-user, change-role"
```

---

## Summary of Changes

| File | Change |
|------|--------|
| `code/python/auth/auth_service.py` | +5 methods: `change_password`, `revoke_all_user_tokens`, `set_user_active`, `delete_user`, `change_member_role` |
| `code/python/webserver/routes/auth.py` | +6 handlers: `change_password_handler`, `logout_all_handler`, `admin_logout_user_handler`, `admin_set_user_active_handler`, `admin_delete_user_handler`, `admin_change_role_handler` |
| `code/python/tests/test_auth_service.py` | +5 test classes with 21 test cases |

## New API Endpoints

| Method | Path | Handler | Auth |
|--------|------|---------|------|
| POST | `/api/auth/change-password` | `change_password_handler` | Authenticated user |
| POST | `/api/auth/logout-all` | `logout_all_handler` | Authenticated user |
| POST | `/api/admin/logout-user/{user_id}` | `admin_logout_user_handler` | Admin |
| PATCH | `/api/admin/user/{user_id}/active` | `admin_set_user_active_handler` | Admin |
| DELETE | `/api/admin/user/{user_id}` | `admin_delete_user_handler` | Admin |
| PATCH | `/api/admin/user/{user_id}/role` | `admin_change_role_handler` | Admin |
