# B2B SaaS Research: Rate Limiting & API Gateway (2025-2026)

## 1. Rate Limiting Overview

**Purpose**: Prevent abuse, protect backend, enforce service tiers

**When needed**: Immediately (even in MVP)

---

## 2. Option 1: Custom aiohttp Middleware (RECOMMENDED for 0-200 tenants)

### Setup with aiolimiter Library

```bash
pip install aiolimiter
```

### Per-Tenant Rate Limiting

```python
from aiolimiter import AsyncLimiter
from collections import defaultdict

# Create per-tenant rate limiters
# Pattern: 100 requests per 60-second window
tenant_limiters = defaultdict(lambda: AsyncLimiter(100, 60))

@aiohttp.middleware
async def rate_limit_middleware(request, handler):
    """
    Enforce per-tenant rate limits
    """
    tenant_id = request.get("tenant_id")

    if not tenant_id:
        # No tenant context (auth failed)
        return await handler(request)

    limiter = tenant_limiters[tenant_id]

    try:
        async with limiter:
            # Request allowed, proceed
            response = await handler(request)

            # Add headers showing remaining quota
            response.headers["X-RateLimit-Limit"] = "100"
            response.headers["X-RateLimit-Remaining"] = str(limiter._total_permits)
            response.headers["X-RateLimit-Reset"] = str(int(time.time()) + 60)

            return response

    except asyncio.TimeoutError:
        # Rate limit exceeded
        raise web.HTTPTooManyRequests(
            text="Rate limit exceeded: 100 requests per minute"
        )
```

### Tiered Rate Limits (By Plan)

```python
from enum import Enum

class PlanTier(str, Enum):
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"

# Rate limits per plan
RATE_LIMITS = {
    PlanTier.STARTER: (100, 60),        # 100 req/min
    PlanTier.PROFESSIONAL: (1000, 60),   # 1K req/min
    PlanTier.ENTERPRISE: (10000, 60)     # 10K req/min
}

# Per-tenant limiters
tenant_limiters = {}

@aiohttp.middleware
async def tiered_rate_limit_middleware(request, handler):
    """Rate limiting by subscription tier"""
    tenant_id = request.get("tenant_id")

    if not tenant_id:
        return await handler(request)

    # Get tenant's plan
    plan = await get_tenant_plan(tenant_id)
    max_requests, window_seconds = RATE_LIMITS[plan]

    # Create limiter for this tenant if not exists
    if tenant_id not in tenant_limiters:
        tenant_limiters[tenant_id] = AsyncLimiter(max_requests, window_seconds)

    limiter = tenant_limiters[tenant_id]

    try:
        async with limiter:
            return await handler(request)
    except asyncio.TimeoutError:
        raise web.HTTPTooManyRequests(
            text=f"Rate limit exceeded: {max_requests} requests per {window_seconds}s"
        )
```

### Pros & Cons

**Pros**:
- Zero external dependencies
- Integrates directly with aiohttp
- Simple to implement
- Easy to test
- No infrastructure overhead

**Cons**:
- In-memory only (resets on server restart)
- Not distributed (multi-server deployments need shared state)
- No persistence across restarts

**Best for**: Single-server MVP, development

---

## 3. Option 2: Redis-Backed Rate Limiting (Distributed)

### Setup

```bash
pip install aioredis
```

### Sliding Window Counter Pattern

```python
import aioredis
from aiohttp import web

@aiohttp.middleware
async def distributed_rate_limit_middleware(request, handler):
    """
    Rate limiting with Redis
    Works across multiple servers
    """
    tenant_id = request.get("tenant_id")
    redis = request.app["redis"]  # Pre-initialized in startup

    if not tenant_id:
        return await handler(request)

    # Get plan and limits
    plan = await get_tenant_plan(tenant_id)
    max_requests, window_seconds = RATE_LIMITS[plan]

    # Redis key (includes both tenant and time window)
    current_minute = int(time.time() / window_seconds) * window_seconds
    key = f"ratelimit:{tenant_id}:{current_minute}"

    try:
        # Increment counter
        count = await redis.incr(key)

        if count == 1:
            # First request in window, set expiration
            await redis.expire(key, window_seconds + 1)

        if count > max_requests:
            # Exceeded limit
            raise web.HTTPTooManyRequests(
                text=f"Rate limit exceeded: {max_requests} requests per {window_seconds}s"
            )

        response = await handler(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(max_requests)
        response.headers["X-RateLimit-Remaining"] = str(max(0, max_requests - count))
        response.headers["X-RateLimit-Reset"] = str(current_minute + window_seconds)

        return response

    except aioredis.ResponseError as e:
        logger.error(f"Redis rate limit error: {e}")
        # Fail open: allow request if Redis is down
        return await handler(request)
```

### Pro Tip: Precise Window Tracking

```python
# Better: Sliding window (track each request individually)

async def check_rate_limit_precise(tenant_id: str, redis) -> bool:
    """
    Sliding window rate limiting
    More accurate than fixed windows
    """
    max_requests = 100
    window_seconds = 60

    key = f"ratelimit:{tenant_id}"
    now = time.time()
    window_start = now - window_seconds

    # Add current request to set
    await redis.zadd(key, {str(now): now})

    # Remove old requests outside window
    await redis.zremrangebyscore(key, 0, window_start)

    # Count remaining
    count = await redis.zcard(key)

    # Cleanup old keys
    await redis.expire(key, window_seconds + 1)

    return count <= max_requests
```

### Pros & Cons

**Pros**:
- Distributed across servers
- Survives server restarts
- Precise tracking per request

**Cons**:
- Redis dependency (adds complexity)
- Network latency (Redis lookup)
- Cost ($15-50/month for managed Redis)

**Best for**: Multi-server deployments, production

---

## 4. Option 3: Kong API Gateway (Mature Solution)

### When to Migrate

- 500+ tenants
- 10M+ requests/month
- Need advanced routing, load balancing
- Ops team ready for infrastructure

### Kong Configuration Example

```yaml
# docker-compose.yml
version: '3'
services:
  kong:
    image: kong:latest
    environment:
      KONG_DATABASE: postgres
      KONG_PG_HOST: postgres
      KONG_PG_USER: kong
      KONG_PG_PASSWORD: kong
    ports:
      - "8000:8000"  # API traffic
      - "8001:8001"  # Admin API
    depends_on:
      - postgres

  kong-database:
    image: postgres:13
    environment:
      POSTGRES_DB: kong
      POSTGRES_USER: kong
      POSTGRES_PASSWORD: kong
    volumes:
      - kong_data:/var/lib/postgresql/data

volumes:
  kong_data:
```

### Plugin Configuration

```bash
# Add rate limiting plugin
curl -X POST http://localhost:8001/plugins \
  --data "name=rate-limiting" \
  --data "config.minute=100" \
  --data "config.hour=5000" \
  --data "policy=sliding_window"

# Add API key authentication
curl -X POST http://localhost:8001/plugins \
  --data "name=key-auth" \
  --data "config.key_names=apikey,api-key"

# Add request transformation (inject tenant ID)
curl -X POST http://localhost:8001/plugins \
  --data "name=request-transformer" \
  --data "config.add.headers=X-Tenant-ID:{{ tenant_id }}"
```

### Pros & Cons

**Pros**:
- Battle-tested, production-proven
- Extensive plugin ecosystem
- Can deploy anywhere (on-prem or cloud)
- Load balancing, caching, auth in one place

**Cons**:
- Infrastructure complexity
- Operational overhead
- Learning curve
- Cost: $0 (OSS) or $1,500+/month (Enterprise)

**Best for**: 500+ tenants, complex routing needs

---

## 5. Option 4: Cloud API Gateways

### AWS API Gateway

```
Pricing: $3.50 per million requests + data transfer

Best for:
- AWS-locked ecosystem
- Serverless architecture
- Simple REST APIs

Cons:
- Limited customization
- Vendor lock-in
- Can get expensive at scale
```

### GCP Cloud API Management

```
Pricing: Complex (varies by product)
Similar model to AWS
```

---

## 6. Quota Management (Beyond Rate Limiting)

### Monthly Quotas (Hard Limits)

```python
async def check_monthly_quota(tenant_id: str, redis) -> bool:
    """
    Enforce hard monthly limit
    (separate from rate limiting)
    """
    plan = await get_tenant_plan(tenant_id)
    monthly_quota = MONTHLY_QUOTAS[plan]  # 1000, 10000, etc.

    current_month = datetime.now().strftime("%Y-%m")
    quota_key = f"monthly_quota:{tenant_id}:{current_month}"

    # Get current usage
    usage = await redis.get(quota_key)
    if usage is None:
        usage = 0
    else:
        usage = int(usage)

    if usage >= monthly_quota:
        raise web.HTTPPaymentRequired(
            text=f"Monthly quota exceeded ({usage}/{monthly_quota})"
        )

    # Increment usage
    await redis.incr(quota_key)

    # Auto-expire at end of month
    days_left = (calendar.monthrange(
        datetime.now().year,
        datetime.now().month
    )[1] - datetime.now().day) + 1
    await redis.expire(quota_key, 86400 * days_left)

    return True

# Usage in middleware
@aiohttp.middleware
async def quota_middleware(request, handler):
    """Enforce monthly quotas"""
    tenant_id = request.get("tenant_id")

    if tenant_id:
        if not await check_monthly_quota(tenant_id, request.app["redis"]):
            raise web.HTTPPaymentRequired()

    return await handler(request)
```

### Soft Limits (Warnings)

```python
QUOTAS = {
    "starter": {
        "monthly": 1000,
        "soft_limit": 900,   # Warn at 90%
        "hard_limit": 1000   # Block at 100%
    },
    "professional": {
        "monthly": 10000,
        "soft_limit": 9000,
        "hard_limit": 10000
    }
}

async def check_quota_and_warn(tenant_id: str, redis):
    """Alert tenant when approaching limits"""
    plan = await get_tenant_plan(tenant_id)
    config = QUOTAS[plan]

    current_month = datetime.now().strftime("%Y-%m")
    key = f"quota:{tenant_id}:{current_month}"

    usage = int(await redis.get(key) or 0)

    if usage > config["soft_limit"] and usage <= config["soft_limit"] + 100:
        # Send warning email (once per window to avoid spam)
        warning_key = f"quota_warning_sent:{tenant_id}:{current_month}"
        if not await redis.get(warning_key):
            admin_email = await get_tenant_admin_email(tenant_id)
            await send_email(
                to=admin_email,
                subject=f"Approaching {config['monthly']} monthly query limit",
                body=f"Current usage: {usage}/{config['monthly']}"
            )
            await redis.setex(warning_key, 86400, "1")  # Don't spam hourly

    if usage >= config["hard_limit"]:
        raise web.HTTPPaymentRequired(
            text=f"Monthly quota exceeded: {usage}/{config['hard_limit']}"
        )
```

---

## 7. Handling Rate Limit Responses

### Proper HTTP Headers

```python
# Return 429 Too Many Requests with headers

response = web.json_response(
    {"error": "Rate limit exceeded"},
    status=429
)

response.headers["Retry-After"] = "60"  # Retry in 60 seconds
response.headers["X-RateLimit-Limit"] = "100"
response.headers["X-RateLimit-Remaining"] = "0"
response.headers["X-RateLimit-Reset"] = str(int(time.time()) + 60)

return response
```

### Client Best Practices

**Document in API docs**:
```markdown
## Rate Limiting

Your API tier includes:
- Starter: 100 requests/minute
- Professional: 1,000 requests/minute
- Enterprise: 10,000 requests/minute

Responses include:
- `X-RateLimit-Limit`: Requests allowed per window
- `X-RateLimit-Remaining`: Requests remaining
- `X-RateLimit-Reset`: Unix timestamp when limit resets

When rate limited (429):
1. Backoff exponentially (1s, 2s, 4s, 8s)
2. Check `Retry-After` header
3. Upgrade plan if consistently hitting limits
```

---

## 8. Implementation Roadmap

### Phase 1: MVP (Week 1)
```
✓ In-memory aiolimiter
✓ Basic 100 req/min per tenant
✓ Return 429 with proper headers
```

### Phase 2: Production (Week 2)
```
✓ Redis-backed rate limiting
✓ Tiered limits by plan
✓ Monthly quota tracking
✓ Soft limit warnings
```

### Phase 3: Growth (Month 3)
```
✓ Kong API Gateway (if 500+ tenants)
✓ Advanced routing/caching
✓ Analytics dashboard
✓ Auto-scaling rules
```

---

## 9. Testing Rate Limiting

```python
import pytest
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase

class TestRateLimiting(AioHTTPTestCase):

    async def get_app(self):
        app = web.Application(middlewares=[
            rate_limit_middleware
        ])
        return app

    async def test_rate_limit_enforced(self):
        """Verify rate limit kicks in after N requests"""
        tenant_id = "test_tenant_123"

        # Make 101 requests (limit is 100)
        for i in range(100):
            resp = await self.client.get(
                "/api/news/search",
                headers={"Authorization": f"Bearer {jwt_token}"}
            )
            assert resp.status == 200

        # 101st request should be rate limited
        resp = await self.client.get(
            "/api/news/search",
            headers={"Authorization": f"Bearer {jwt_token}"}
        )
        assert resp.status == 429
        assert "X-RateLimit-Remaining" in resp.headers

    async def test_rate_limit_resets(self):
        """Verify rate limit resets per window"""
        # Make 100 requests in window 1
        for _ in range(100):
            resp = await self.client.get("/api/news/search")
            assert resp.status == 200

        # Next request in same window should be rate limited
        resp = await self.client.get("/api/news/search")
        assert resp.status == 429

        # Wait for window to reset
        await asyncio.sleep(61)

        # Should work again
        resp = await self.client.get("/api/news/search")
        assert resp.status == 200

    async def test_tiered_limits(self):
        """Verify different plans have different limits"""
        # Starter tier: 100 req/min
        starter_token = await get_token_for_plan("starter")
        for i in range(100):
            resp = await self.client.get(
                "/api/news/search",
                headers={"Authorization": f"Bearer {starter_token}"}
            )
            assert resp.status == 200

        resp = await self.client.get(
            "/api/news/search",
            headers={"Authorization": f"Bearer {starter_token}"}
        )
        assert resp.status == 429  # Limited

        # Professional tier: 1000 req/min
        prof_token = await get_token_for_plan("professional")
        for i in range(1000):
            resp = await self.client.get(
                "/api/news/search",
                headers={"Authorization": f"Bearer {prof_token}"}
            )
            assert resp.status == 200

        resp = await self.client.get(
            "/api/news/search",
            headers={"Authorization": f"Bearer {prof_token}"}
        )
        assert resp.status == 429  # Limited at 1000
```

---

## 10. Monitoring Rate Limiting

### Log Rate Limit Events

```python
import logging

logger = logging.getLogger(__name__)

@aiohttp.middleware
async def rate_limit_logging_middleware(request, handler):
    """Track rate limiting for monitoring"""
    tenant_id = request.get("tenant_id")

    if not tenant_id:
        return await handler(request)

    try:
        response = await handler(request)
        return response
    except web.HTTPTooManyRequests as e:
        logger.warning(
            f"Rate limit exceeded",
            extra={
                "tenant_id": tenant_id,
                "path": request.path,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        raise
```

### Alerting

```python
async def monitor_rate_limit_abuse():
    """Alert if a tenant is consistently hitting limits"""
    while True:
        await asyncio.sleep(300)  # Check every 5 min

        # Count rate limit hits per tenant
        rate_limit_counts = await db.fetch("""
            SELECT tenant_id, COUNT(*) as hits
            FROM rate_limit_events
            WHERE created_at > NOW() - INTERVAL 5 minute
            GROUP BY tenant_id
            HAVING COUNT(*) > 10
        """)

        for row in rate_limit_counts:
            tenant_id = row["tenant_id"]
            hits = row["hits"]

            # Alert ops team
            if hits > 50:
                await send_alert(
                    f"Tenant {tenant_id} hit rate limit {hits} times in 5min"
                )
```

---

## 11. Cost Comparison

| Solution | Startup Cost | Monthly (0-50 tenants) | Monthly (200 tenants) |
|----------|---|---|---|
| **aiohttp custom** | $0 | $0 | $0 |
| **+ Redis** | $15-30 | $15-30 | $100-200 |
| **Kong OSS** | $0 | $50-100 (infra) | $200-500 (infra) |
| **Kong Enterprise** | N/A | $1,500/month | $2,000+/month |
| **AWS API Gateway** | $3.50/M | $350 (100M req) | $1,750 (500M req) |

**Recommendation for News Search API**:
1. **Start**: Custom aiohttp + aiolimiter ($0)
2. **At 50 tenants**: Add Redis ($15-30/month)
3. **At 500 tenants**: Evaluate Kong ($50-200/month infra)
4. **At 1M+ requests/month**: Kong Enterprise or cloud gateway

---

## 12. Common Pitfalls

### Pitfall 1: Not Handling Rate Limit Headers

```python
# ❌ WRONG: No headers
raise web.HTTPTooManyRequests()

# ✅ CORRECT: Include rate limit info
response = web.json_response(
    {"error": "Rate limit exceeded"},
    status=429
)
response.headers["X-RateLimit-Remaining"] = "0"
response.headers["X-RateLimit-Reset"] = str(int(time.time()) + 60)
return response
```

### Pitfall 2: Rate Limiting Before Auth

```python
# ❌ WRONG: Rate limit before verifying user
@aiohttp.middleware
async def middleware(request, handler):
    await check_rate_limit()  # Anonymous user?
    await check_auth()

# ✅ CORRECT: Auth first, then rate limit
@aiohttp.middleware
async def middleware(request, handler):
    await check_auth()
    await check_rate_limit(request["tenant_id"])
```

### Pitfall 3: Distributed System Without Redis

```python
# ❌ WRONG: In-memory limits in multi-server setup
limiter = AsyncLimiter(100, 60)  # Per server!
# Server A: 100 req/min
# Server B: 100 req/min
# Total: 200 req/min (limits ignored!)

# ✅ CORRECT: Use Redis for shared state
await redis.incr(f"limit:{tenant_id}")
```

---

## Summary: API Gateway Selection Matrix

| Scenario | Recommendation | Cost/Month |
|----------|---|---|
| **MVP** | aiolimiter in-memory | $0 |
| **Single server, 50 tenants** | aiolimiter | $0 |
| **Multi-server, 50-200 tenants** | Redis + custom middleware | $15-50 |
| **200-500 tenants** | Kong OSS (self-hosted) | $50-200 |
| **500+ tenants or 10M+ req/month** | Kong Enterprise or cloud | $1,500-5,000 |
| **AWS ecosystem** | AWS API Gateway | $3.50/M requests |

