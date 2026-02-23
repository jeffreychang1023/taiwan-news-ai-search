# B2B SaaS Implementation Summary (News Search API)

## Quick Reference

### Authentication Stack (RECOMMENDED)

```
MVP (0-50 tenants):
- Provider: Supabase Auth or WorkOS (free tier)
- M2M: API Key → JWT exchange
- Cost: $0-25/month

Growth (50-200 tenants):
- Provider: WorkOS
- M2M: OAuth 2.0 Client Credentials
- SSO: SAML (when 3+ prospects request)
- Cost: $150-1,500/month

Enterprise (200+ tenants):
- Provider: WorkOS
- SSO: SAML + OIDC
- SCIM: Directory sync
- Cost: $2,000-5,000+/month
```

### Authorization Stack (RECOMMENDED)

```
All stages:
- Pattern: Tenant-scoped RBAC
- Enforcement: aiohttp middleware
- Roles: admin, developer, viewer
- Database: PostgreSQL (tenant_users table)
- Cache: Redis (60-second TTL)
```

### Billing Stack (RECOMMENDED)

```
All stages:
- Provider: Stripe Billing
- Metrics: Per-query + LLM tokens
- Cost allocation: 1.3x markup on LLM costs
- Quotas: Monthly hard limits per plan
- Cost: 0.5% revenue + $15-30 infrastructure
```

### API Gateway Stack (RECOMMENDED)

```
MVP (0-50 tenants):
- Solution: aiolimiter (in-memory)
- Cost: $0

Growth (50-200 tenants):
- Solution: aiolimiter + Redis
- Cost: $15-50/month

Scale (500+ tenants):
- Solution: Kong OSS or Enterprise
- Cost: $50-200/month (OSS) or $1,500+/month (Enterprise)
```

---

## Total Cost of Operations

### Startup Phase (0-50 tenants)

```
Authentication:  $0-25/month
Authorization:   $0 (custom)
Billing:         0.5% revenue
API Gateway:     $0
Rate Limiting:   $0
Database:        $25-50/month
Monitoring:      $0-100/month
─────────────────────────────
TOTAL:           $25-175/month + 0.5% revenue
```

### Growth Phase (50-200 tenants)

```
Authentication:  $0-150/month
SSO (if 5 customers):  $625/month
Authorization:   $0 (custom)
Billing:         1% revenue (more traffic)
API Gateway:     $0
Rate Limiting:   $15-50/month (Redis)
Database:        $100-300/month
Monitoring:      $100-500/month
─────────────────────────────
TOTAL:           $840-1,600/month + 1% revenue
```

### Enterprise Phase (200+ tenants, $100K+ MRR)

```
Authentication:  $150-300/month
SSO (20 customers @ $125):  $2,500/month
Authorization:   $0 (custom)
Billing:         1% revenue
API Gateway:     $50-200/month (Kong)
Rate Limiting:   $100-200/month
Database:        $300-500/month
Monitoring:      $500-1000/month
Ops/Support:     $5,000+/month
─────────────────────────────
TOTAL:           $8,600-9,900/month + 1% revenue
```

---

## Implementation Roadmap

### Week 1: Core Auth + Rate Limiting

**Objectives**: Minimal viable security

**Tasks**:
- [ ] Generate API keys (dashboard endpoint)
- [ ] Hash and store API keys in PostgreSQL
- [ ] Create aiohttp auth middleware (validate API key)
- [ ] Add `tenant_id` and `role` to request context
- [ ] Implement aiolimiter middleware (100 req/min default)
- [ ] Return 429 with proper headers on rate limit

**Code locations**:
```
webserver/middleware/auth.py       # API key validation
webserver/middleware/rate_limit.py  # aiolimiter wrapper
core/baseHandler.py                # Add tenant context
```

**Files to create**:
```
webserver/middleware/auth.py
webserver/middleware/rate_limit.py
```

---

### Week 2: JWT Exchange + RBAC

**Objectives**: Stateless auth, per-tenant roles

**Tasks**:
- [ ] Create JWT token endpoint (exchange API key for token)
- [ ] Implement JWT validation middleware
- [ ] Create `tenant_users` and `role_permissions` tables
- [ ] Add RBAC middleware (role-based access checks)
- [ ] Enforce tenant isolation in all database queries
- [ ] Add role-specific test cases

**Code locations**:
```
webserver/middleware/auth.py       # JWT validation
webserver/middleware/rbac.py       # Role checks
code/python/core/rbac_engine.py    # Permission logic
```

**Database**:
```sql
-- Create tables
CREATE TABLE tenant_users (...);
CREATE TABLE role_permissions (...);
CREATE INDEX idx_tenant_users_user_id_tenant_id ON tenant_users(user_id, tenant_id);
```

---

### Week 3: Billing Integration

**Objectives**: Track usage, integrate Stripe

**Tasks**:
- [ ] Set up Stripe test account
- [ ] Create Stripe meter definitions (api_query, llm_tokens)
- [ ] Create pricing tiers in Stripe
- [ ] Implement metering middleware (record events async)
- [ ] Create subscription creation endpoint
- [ ] Implement webhook handler for payment events
- [ ] Add usage tracking to PostgreSQL (audit table)

**Code locations**:
```
billing/stripe_client.py           # Stripe wrapper
billing/usage_tracker.py           # Meter events
webserver/middleware/metering.py   # Record usage
webserver/routes/billing.py        # Subscription endpoints
```

**Stripe setup**:
```python
# Create meters in Stripe
stripe.billing.Meter.create(event_name="api_query", ...)
stripe.billing.Meter.create(event_name="llm_tokens", ...)

# Create prices with tiered metering
stripe.Price.create(...)
```

---

### Week 4: Quota Management + Alerts

**Objectives**: Enforce monthly limits, warn users

**Tasks**:
- [ ] Implement monthly quota tracking (Redis)
- [ ] Add soft limit warnings (90% of quota)
- [ ] Add hard limit blocking (100% of quota)
- [ ] Send email alerts to tenant admins
- [ ] Create usage dashboard endpoint
- [ ] Add quota check to rate limit middleware

**Code locations**:
```
billing/quota_manager.py           # Quota enforcement
webserver/middleware/quota.py      # Quota middleware
core/utils/email_sender.py         # Alert emails
webserver/routes/admin.py          # Usage dashboard
```

---

### Week 5-6: Enterprise Features (SSO + SCIM)

**Objectives**: Support SAML SSO for enterprise deals

**Tasks**:
- [ ] Integrate WorkOS (or Auth0)
- [ ] Implement SAML assertion validation
- [ ] Support JIT (Just-in-Time) user provisioning
- [ ] Map IdP groups to tenant roles
- [ ] Implement SCIM endpoint for directory sync
- [ ] Provide metadata endpoint for customer config

**Code locations**:
```
auth/workos_client.py              # WorkOS integration
auth/saml_handler.py               # SAML processing
auth/scim_endpoint.py              # Directory sync
```

**SAML checklist**:
```
✓ Validate signature
✓ Check NotBefore/NotOnOrAfter
✓ Extract user attributes
✓ Create/update user in DB
✓ Map groups to roles
✓ Return signed response
```

---

### Month 3: Advanced Features

**Objectives**: Production-ready, scale-safe

**Tasks**:
- [ ] Migrate rate limiting to Redis (multi-server)
- [ ] Implement usage analytics dashboard
- [ ] Add audit logging (who did what when)
- [ ] Set up monitoring/alerting (DataDog, CloudWatch)
- [ ] Performance optimization (caching, indexing)
- [ ] Security hardening (penetration testing)

**Code locations**:
```
webserver/middleware/redis_rate_limit.py  # Distributed limiting
webserver/routes/analytics.py             # Usage dashboards
core/audit_log.py                         # Audit trail
```

---

## Key Implementation Details

### Tenant Isolation Pattern (CRITICAL)

**Every database query must include tenant_id filter**:

```python
# ❌ WRONG
results = await db.fetch("SELECT * FROM articles")

# ✅ CORRECT
results = await db.fetch(
    "SELECT * FROM articles WHERE tenant_id = ?",
    request["tenant_id"]
)
```

### API Key Exchange Flow

```
Client: Has API key (stored securely)
  ↓
Client: POST /api/auth/token
  Body: {"api_key": "sk_live_abc123"}
  ↓
Server: Validate API key against database
  Hash provided key, compare to stored hash
  ↓
Server: Return JWT token
  {
    "access_token": "eyJ...",
    "expires_in": 3600,
    "token_type": "Bearer"
  }
  ↓
Client: Cache JWT (1 hour)
  ↓
Client: All requests use JWT
  Authorization: Bearer eyJ...
  ↓
Server: Verify JWT signature (no DB lookup!)
  Extract tenant_id, role from claims
  Proceed
```

### Middleware Stack Order

```python
app = web.Application(middlewares=[
    error_handler_middleware,       # 1. Catch exceptions
    cors_middleware,                # 2. CORS headers
    auth_middleware,                # 3. JWT validation
    tenant_context_middleware,      # 4. Extract tenant_id
    rbac_middleware,                # 5. Role checks
    rate_limit_middleware,          # 6. Check rate limit
    quota_middleware,               # 7. Check monthly quota
    metering_middleware,            # 8. Record usage
])
```

### Database Schema Essentials

```sql
-- Tenants
CREATE TABLE tenants (
    tenant_id UUID PRIMARY KEY,
    name VARCHAR(256),
    plan VARCHAR(50),
    stripe_customer_id VARCHAR(256),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Users
CREATE TABLE users (
    user_id UUID PRIMARY KEY,
    email VARCHAR(256) UNIQUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Tenant memberships
CREATE TABLE tenant_users (
    user_id UUID,
    tenant_id UUID,
    role VARCHAR(50),
    created_at TIMESTAMP,
    PRIMARY KEY (user_id, tenant_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id)
);
CREATE INDEX idx_tenant_users_user_id_tenant_id
  ON tenant_users(user_id, tenant_id);
CREATE INDEX idx_tenant_users_tenant_id
  ON tenant_users(tenant_id);

-- API keys
CREATE TABLE api_keys (
    api_key_id UUID PRIMARY KEY,
    tenant_id UUID,
    key_hash VARCHAR(256),  -- bcrypt hash
    created_by UUID,
    created_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id),
    FOREIGN KEY (created_by) REFERENCES users(user_id)
);
CREATE INDEX idx_api_keys_tenant_id
  ON api_keys(tenant_id);

-- Role permissions
CREATE TABLE role_permissions (
    role VARCHAR(50),
    resource_type VARCHAR(50),
    action VARCHAR(50),
    PRIMARY KEY (role, resource_type, action)
);

-- Usage tracking (for analytics + billing)
CREATE TABLE usage_events (
    event_id BIGSERIAL PRIMARY KEY,
    tenant_id UUID,
    user_id UUID,
    event_type VARCHAR(50),  -- 'api_query', 'llm_tokens'
    value INT,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
CREATE INDEX idx_usage_events_tenant_id_created_at
  ON usage_events(tenant_id, created_at);
```

---

## Testing Checklist

### Authentication Tests

```python
✓ Valid API key → JWT token
✓ Invalid API key → 401
✓ Expired JWT → 401
✓ Missing Authorization header → 401
✓ Malformed JWT → 401
✓ Token with wrong signature → 401
```

### RBAC Tests

```python
✓ Admin can read articles
✓ Developer can read articles
✓ Viewer can read articles
✓ Admin can create API keys
✓ Developer can create API keys
✓ Viewer cannot create API keys
✓ User cannot access other tenant's articles
```

### Rate Limiting Tests

```python
✓ First 100 requests succeed
✓ 101st request returns 429
✓ Response includes X-RateLimit-* headers
✓ After window expires, counter resets
✓ Different tenants have separate limits
✓ Different plans have different limits
```

### Billing Tests

```python
✓ Meter event recorded after successful query
✓ LLM tokens tracked separately
✓ Monthly quota enforced (soft limit)
✓ Monthly quota enforced (hard limit)
✓ Subscription created in Stripe
✓ Invoice generated after month
```

---

## Security Checklist

### Authentication
- [ ] HTTPS/TLS enforced for all requests
- [ ] API keys hashed (bcrypt/argon2), not plain text
- [ ] JWT tokens signed (HS256 or RS256)
- [ ] Token expiration enforced (max 1 hour)
- [ ] Secrets stored in vault, not code/env
- [ ] Rate limiting prevents brute force
- [ ] Audit log tracks all auth attempts

### Authorization
- [ ] Every query includes tenant_id filter
- [ ] Admin-only endpoints check role in middleware
- [ ] UI gates backed by backend enforcement
- [ ] Cross-tenant access is impossible
- [ ] Authorization cache includes tenant context
- [ ] Permission checks are comprehensive (no bypass)

### Billing
- [ ] Meter events logged with timestamps
- [ ] Double-charging prevention (idempotent keys)
- [ ] Billing reconciliation (invoices match usage)
- [ ] Soft/hard quota limits enforced
- [ ] Quota reset at month boundary
- [ ] Failed payments trigger alerts

### General
- [ ] No hardcoded secrets in code/config
- [ ] Logging doesn't include sensitive data (tokens, keys)
- [ ] Error messages don't leak implementation details
- [ ] Dependencies kept up-to-date
- [ ] CORS correctly configured (no * origin)
- [ ] Input validation on all endpoints

---

## Deployment Checklist

### Pre-Launch
- [ ] Set environment variables (JWT_SECRET, STRIPE_KEY)
- [ ] Create Stripe test account, then production
- [ ] Configure domain SSL certificates
- [ ] Set up database backups
- [ ] Configure monitoring (DataDog/CloudWatch)
- [ ] Load test rate limiting (simulate 1000+ concurrent)

### Launch
- [ ] Deploy auth middleware to staging
- [ ] Test with real Stripe test keys
- [ ] Load test with realistic traffic
- [ ] Verify rate limit headers
- [ ] Verify tenant isolation (data doesn't leak)
- [ ] Test webhook handling (Stripe events)

### Post-Launch
- [ ] Monitor 429 rates (unexpected spikes = misconfiguration)
- [ ] Monitor failed auth attempts
- [ ] Monitor Stripe sync failures
- [ ] Check logs daily for anomalies
- [ ] Quarterly penetration testing
- [ ] Annual security audit

---

## Monitoring Metrics

### Key Metrics to Track

```
Authentication:
- Failed auth attempts (per tenant)
- API key rotation rate
- SSO provisioning failures
- JWT validation latency

Authorization:
- Permission check failures
- Role changes (audit)
- Cross-tenant access attempts (should be 0)

Billing:
- Meter events recorded (per day)
- Failed Stripe API calls
- Invoice generation time
- Revenue tracking accuracy

Rate Limiting:
- 429 response rate
- Requests hitting soft limit
- Requests hitting hard limit
- Rate limit bypass attempts
```

### Alerting Rules

```
CRITICAL (PagerDuty):
- Cross-tenant data access detected
- Stripe API failing (>5% error rate)
- Rate limiter not working (all requests blocked)
- Database down

WARNING (Email):
- High 429 rate (>10% of traffic)
- Soft quota limit reached (>50 tenants)
- Failed auth attempts (>100/hour)
- Meter event backlog (>1000 pending)
```

---

## Recommended AWS/Cloud Services

If deploying to cloud:

```
Compute:           ECS (Docker) or Lambda (serverless)
Database:          RDS PostgreSQL (managed)
Cache:             ElastiCache Redis
Auth:              AWS Cognito or WorkOS
API Gateway:       API Gateway or ALB
Monitoring:        CloudWatch + DataDog
Secrets:           AWS Secrets Manager
Billing:           Stripe (third-party)
```

---

## Resources & References

### Authentication
- WorkOS Docs: https://workos.com/docs
- SAML SSO Guide: https://www.scalekit.com/blog/saml-sso-in-b2b-saas-the-complete-guide-for-developers-and-enterprise-buyers
- OAuth 2.0 Client Credentials: https://www.scalekit.com/blog/securing-m2m-tokens-b2b-saas
- M2M Auth: https://guptadeepak.com/beyond-human-access-machine-to-machine-authentication-for-modern-b2b-saas/

### Authorization
- RBAC Design: https://workos.com/blog/how-to-design-multi-tenant-rbac-saas
- Multi-Tenant RBAC: https://www.permit.io/blog/best-practices-for-multi-tenant-authorization
- Audit Logging: https://www.cloudflare.com/learning/security/audit-logs/

### Billing
- Stripe Billing: https://docs.stripe.com/billing/subscriptions/usage-based
- Usage Metering: https://stripe.com/resources/more/usage-metering
- stripemeter: https://github.com/geminimir/stripemeter

### Rate Limiting
- aiolimiter: https://pypi.org/project/aiolimiter/
- aiohttp Rate Limiting: https://quentin.pradet.me/blog/how-do-you-rate-limit-calls-with-aiohttp.html
- Kong Gateway: https://konghq.com

### Testing
- pytest-aiohttp: https://pypi.org/project/pytest-aiohttp/
- Faker (test data): https://pypi.org/project/faker/
- Factory Boy (fixtures): https://factoryboy.readthedocs.io/

---

## Next Steps

1. **This week**: Pick authentication provider (WorkOS recommended)
2. **Week 1**: Implement API key + JWT exchange
3. **Week 2**: Add RBAC middleware + tenant isolation
4. **Week 3**: Integrate Stripe Billing + metering
5. **Week 4**: Add quota management + alerts
6. **Month 3**: Launch with SAML SSO support

---

**Document Version**: 2026-02
**Last Updated**: Based on 2025-2026 SaaS best practices
**Status**: Ready for implementation

