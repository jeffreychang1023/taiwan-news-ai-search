# B2B SaaS Research: Authorization & RBAC (2025-2026)

## Core Principle

"Every authorization decision must be tenant-aware. You don't just check 'is user an admin?', you check 'is user an admin in this tenant?'"

---

## 1. Multi-Tenant RBAC Design

### Option 1: Global Roles (Simplest)

```
Global roles:
- Owner (full access)
- Admin (manage users)
- Developer (create API keys)
- Viewer (read-only)

Problem: No differentiation per tenant
Example: User is Admin in Tenant A but Viewer in Tenant B? IMPOSSIBLE
```

**Use when**: Single-tenant or early MVP

---

### Option 2: Tenant-Scoped Roles (RECOMMENDED for 0-200 tenants)

```
user_roles table:
- (user_id=123, tenant_id=456, role="admin")
- (user_id=123, tenant_id=789, role="viewer")

Allows: Same user, different roles per tenant ✓
Problem: Role proliferation if many custom roles
```

**Use when**: Multiple customers, need flexibility

---

### Option 3: Hybrid with Role Templates

```
Global base roles:
- Owner, Admin, Developer, Viewer

Per-tenant customization:
- Tenant can create: "Data Scientist" = Viewer + "write_analysis" permission
- Still global structure, just extended

Allows: 80% use defaults, 20% customize ✓
Complexity: Medium
```

**Use when**: Enterprise customers want custom roles

---

## 2. Database Schema for RBAC

```sql
-- Tenants
CREATE TABLE tenants (
    tenant_id UUID PRIMARY KEY,
    name VARCHAR(256),
    plan VARCHAR(50),  -- 'starter', 'professional', 'enterprise'
    created_at TIMESTAMP
);

-- Users
CREATE TABLE users (
    user_id UUID PRIMARY KEY,
    email VARCHAR(256),
    created_at TIMESTAMP
);

-- Tenant memberships (CRITICAL: Use composite index)
CREATE TABLE tenant_users (
    user_id UUID,
    tenant_id UUID,
    role VARCHAR(50),  -- 'admin', 'developer', 'viewer'
    created_at TIMESTAMP,
    PRIMARY KEY (user_id, tenant_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id)
);
-- Index for fast lookups
CREATE INDEX idx_tenant_users_user_id_tenant_id
  ON tenant_users(user_id, tenant_id);
CREATE INDEX idx_tenant_users_tenant_id
  ON tenant_users(tenant_id);

-- Define role permissions
CREATE TABLE role_permissions (
    role VARCHAR(50),
    resource_type VARCHAR(50),  -- 'news_source', 'api_key', 'user'
    action VARCHAR(50),  -- 'read', 'write', 'delete'
    PRIMARY KEY (role, resource_type, action)
);

-- Example data:
-- ('admin', 'news_source', 'read')
-- ('admin', 'news_source', 'write')
-- ('admin', 'user', 'read')
-- ('admin', 'user', 'write')
-- ('developer', 'api_key', 'read')
-- ('developer', 'api_key', 'write')
-- ('viewer', 'news_source', 'read')
-- ('viewer', 'api_key', 'read')

-- Resources scoped to tenants
CREATE TABLE news_sources_per_tenant (
    tenant_id UUID,
    source_id VARCHAR(100),  -- 'udn', 'ltn', 'cna'
    added_at TIMESTAMP,
    PRIMARY KEY (tenant_id, source_id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id)
);

-- Track user permissions for audit
CREATE TABLE user_permissions_audit (
    user_id UUID,
    tenant_id UUID,
    action VARCHAR(100),  -- 'read_article', 'create_api_key'
    resource_id VARCHAR(256),
    granted BOOLEAN,
    reason VARCHAR(256),
    created_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id)
);
```

---

## 3. Authorization Enforcement in aiohttp

### Step 1: Authentication Middleware

```python
import jwt
from aiohttp import web

@aiohttp.middleware
async def auth_middleware(request, handler):
    """
    Extract JWT token and validate
    Add user context to request
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(text="Missing token")

    token = auth_header[7:]
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_exp": True}  # CRITICAL: Enforce expiration
        )
    except jwt.ExpiredSignatureError:
        raise web.HTTPUnauthorized(text="Token expired")
    except jwt.InvalidSignatureError:
        raise web.HTTPUnauthorized(text="Invalid token")

    # Store in request context
    request["user_id"] = payload["user_id"]
    request["tenant_id"] = payload["tenant_id"]
    request["role"] = payload["role"]

    return await handler(request)
```

### Step 2: RBAC Middleware

```python
@aiohttp.middleware
async def rbac_middleware(request, handler):
    """
    Check if user has permission for this resource
    """
    if "tenant_id" not in request:
        # Auth middleware not applied?
        raise web.HTTPInternalServerError()

    tenant_id = request["tenant_id"]
    user_id = request["user_id"]
    role = request["role"]

    # Example: Only admins can modify sources
    if request.method in ["POST", "PUT", "DELETE"]:
        if role != "admin":
            raise web.HTTPForbidden(text="Admin access required")

    # Example: Verify user is still active in tenant
    still_member = await db.fetchval("""
        SELECT 1 FROM tenant_users
        WHERE user_id = ? AND tenant_id = ?
    """, user_id, tenant_id)

    if not still_member:
        raise web.HTTPForbidden(text="Not a tenant member")

    return await handler(request)
```

### Step 3: Handler with Tenant Isolation

```python
async def search_news(request):
    """
    Search endpoint with mandatory tenant filtering
    """
    tenant_id = request["tenant_id"]  # Already extracted
    user_id = request["user_id"]
    role = request["role"]

    query = request.query.get("q", "")

    # CRITICAL: Always add tenant_id filter
    results = await db.fetch("""
        SELECT * FROM news_articles
        WHERE tenant_id = ?
        AND source IN (
            SELECT source_id FROM news_sources_per_tenant
            WHERE tenant_id = ?
        )
        AND body ILIKE ?
        LIMIT 100
    """, tenant_id, tenant_id, f"%{query}%")

    return web.json_response({
        "results": results,
        "count": len(results)
    })


async def create_api_key(request):
    """
    Create API key - admin only
    """
    tenant_id = request["tenant_id"]
    user_id = request["user_id"]
    role = request["role"]

    # Enforce admin role
    if role != "admin":
        raise web.HTTPForbidden(text="Admin access required")

    # Verify tenant exists and user is admin
    is_admin = await db.fetchval("""
        SELECT 1 FROM tenant_users
        WHERE user_id = ? AND tenant_id = ? AND role = 'admin'
    """, user_id, tenant_id)

    if not is_admin:
        raise web.HTTPForbidden()

    # Generate API key
    api_key = secrets.token_urlsafe(32)
    key_hash = hash_bcrypt(api_key)

    # Store in DB
    await db.execute("""
        INSERT INTO api_keys (tenant_id, key_hash, created_by)
        VALUES (?, ?, ?)
    """, tenant_id, key_hash, user_id)

    # Log for audit
    await db.execute("""
        INSERT INTO user_permissions_audit
        (user_id, tenant_id, action, granted, created_at)
        VALUES (?, ?, 'create_api_key', 1, NOW())
    """, user_id, tenant_id)

    return web.json_response({"api_key": api_key})
```

---

## 4. CRITICAL Mistakes to Avoid

### Mistake 1: Missing Tenant Filter in Queries

```python
# ❌ WRONG: Returns ALL articles across ALL tenants (data leakage!)
articles = await db.fetch("SELECT * FROM news_articles")

# ✅ CORRECT: Always add tenant filter
articles = await db.fetch(
    "SELECT * FROM news_articles WHERE tenant_id = ?",
    request["tenant_id"]
)
```

### Mistake 2: Assuming Global Roles

```python
# ❌ WRONG: Is this admin global or tenant-scoped?
if user.role == "admin":
    # Undefined behavior - could be admin in other tenant!

# ✅ CORRECT: Explicit tenant context
if await is_tenant_admin(user_id, tenant_id):
    # Clear intent
```

### Mistake 3: UI-Only Permission Checks

```javascript
// ❌ WRONG: Frontend gate without backend enforcement
if (user.role !== "admin") {
    // Hide delete button
}
// But backend doesn't check! User crafts malicious request.
```

```python
# ✅ CORRECT: Backend enforcement
@aiohttp.middleware
async def enforce_admin(request, handler):
    if request["role"] != "admin":
        raise web.HTTPForbidden()
    return await handler(request)
```

### Mistake 4: Sharing Authorization Cache Across Tenants

```python
# ❌ WRONG: Cache key doesn't include tenant
cache_key = f"authz:{user_id}:{action}"
# Tenant A admin's permission bleeds to Tenant B!

# ✅ CORRECT: Cache key includes tenant
cache_key = f"authz:{user_id}:{tenant_id}:{action}"
```

---

## 5. Caching Authorization Decisions

**Pattern**: Cache with short TTL (60-300 seconds)

```python
import aioredis

async def check_permission(
    user_id: str, tenant_id: str, action: str, redis
) -> bool:
    """
    Check if user has permission in tenant
    Use cache to avoid DB queries
    """
    # CRITICAL: Include tenant in cache key
    cache_key = f"authz:{user_id}:{tenant_id}:{action}"

    # Try cache first
    cached = await redis.get(cache_key)
    if cached is not None:
        return cached == "1"

    # Compute permission from DB
    allowed = await db.fetchval("""
        SELECT 1 FROM role_permissions
        WHERE role = (
            SELECT role FROM tenant_users
            WHERE user_id = ? AND tenant_id = ?
        ) AND action = ?
    """, user_id, tenant_id, action)

    # Cache for 60 seconds (short TTL for security)
    await redis.setex(cache_key, 60, "1" if allowed else "0")

    return allowed
```

**Key insight**: "Cache keys must include tenant context to prevent cross-tenant leaks. Keep TTLs short (60-300 seconds)"

---

## 6. Enterprise Integration: IdP Groups to Roles

When using SAML/OIDC SSO, map IdP groups to roles:

```python
async def provision_user_from_saml(saml_attributes, tenant_id):
    """
    Just-in-Time (JIT) user provisioning from SAML assertion
    Map IdP groups to tenant roles
    """
    email = saml_attributes["email"]
    idp_groups = saml_attributes.get("groups", [])

    # Get or create user
    user_id = await db.fetchval(
        "SELECT user_id FROM users WHERE email = ?", email
    )
    if not user_id:
        user_id = str(uuid.uuid4())
        await db.execute(
            "INSERT INTO users (user_id, email) VALUES (?, ?)",
            user_id, email
        )

    # Map IdP groups to roles (per-tenant)
    role_mapping = {
        "engineering": "developer",
        "management": "admin",
        "observers": "viewer"
    }

    role = "viewer"  # Default
    for group in idp_groups:
        if group in role_mapping:
            role = role_mapping[group]
            break

    # Upsert tenant membership
    await db.execute("""
        INSERT INTO tenant_users (user_id, tenant_id, role)
        VALUES (?, ?, ?)
        ON CONFLICT (user_id, tenant_id) DO UPDATE SET role = ?
    """, user_id, tenant_id, role, role)

    return user_id, role
```

---

## 7. Resource-Based Access Control

Beyond role-based, restrict by resource:

```python
# Which news sources can this tenant access?
tenant_sources = {
    "tenant_123": ["udn", "ltn", "cna"],  # Taiwanese news only
    "tenant_456": ["udn", "ltn", "cna", "chinatimes", "einfo", "moea"]  # All
}

async def check_source_access(tenant_id: str, source: str) -> bool:
    """Verify tenant can access this news source"""
    allowed_sources = await db.fetch("""
        SELECT source_id FROM news_sources_per_tenant
        WHERE tenant_id = ?
    """, tenant_id)

    source_ids = {row["source_id"] for row in allowed_sources}
    return source in source_ids
```

---

## 8. Audit Logging

Track all authorization decisions for compliance:

```python
async def audit_log_permission(
    user_id: str,
    tenant_id: str,
    action: str,
    resource_id: str,
    granted: bool,
    reason: str = None,
    db = None
):
    """Log authorization decision for audit trail"""
    await db.execute("""
        INSERT INTO user_permissions_audit
        (user_id, tenant_id, action, resource_id, granted, reason, created_at)
        VALUES (?, ?, ?, ?, ?, ?, NOW())
    """, user_id, tenant_id, action, resource_id, granted, reason)

# Usage in handlers
await audit_log_permission(
    user_id="user_123",
    tenant_id="tenant_456",
    action="read_article",
    resource_id="article_789",
    granted=True,
    reason="User role is viewer",
    db=db
)
```

---

## 9. Testing Authorization

```python
import pytest

@pytest.mark.asyncio
async def test_tenant_isolation():
    """Verify users can't access other tenant's data"""

    # Create two tenants
    tenant_a = await create_tenant("Tenant A")
    tenant_b = await create_tenant("Tenant B")

    # Create users
    user_a = await create_user("user_a@company.com", tenant_a)
    user_b = await create_user("user_b@other.com", tenant_b)

    # Add articles
    article_a = await create_article(tenant_a, "Article A")
    article_b = await create_article(tenant_b, "Article B")

    # User A should only see their tenant's articles
    articles_a = await get_articles(user_a, tenant_a)
    assert article_a in articles_a
    assert article_b not in articles_a

    # User B should only see their tenant's articles
    articles_b = await get_articles(user_b, tenant_b)
    assert article_b in articles_b
    assert article_a not in articles_b


@pytest.mark.asyncio
async def test_rbac_enforcement():
    """Verify role-based access control"""

    tenant = await create_tenant("Test Tenant")
    admin = await create_user("admin@company.com", tenant, role="admin")
    viewer = await create_user("viewer@company.com", tenant, role="viewer")

    # Admin can create API keys
    api_key = await create_api_key(admin, tenant)
    assert api_key is not None

    # Viewer cannot create API keys
    with pytest.raises(HTTPForbidden):
        await create_api_key(viewer, tenant)
```

---

## 10. Authorization Patterns Summary

| Pattern | Use Case | Complexity |
|---------|----------|-----------|
| **Global roles** | Simple apps, single tenant | Low |
| **Tenant-scoped roles** | Multi-tenant SaaS (recommended) | Medium |
| **Hybrid with templates** | Enterprise customization | High |
| **Resource-based** | Fine-grained control (news sources) | High |
| **Relationship-based** | Dynamic hierarchies | Very High |

**Recommendation for News Search API**: Start with tenant-scoped roles, add resource-based controls for news sources

