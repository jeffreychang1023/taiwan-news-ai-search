# B2B SaaS Research: Authentication & Identity (2025-2026)

## EXECUTIVE SUMMARY

For a news search API service scaling from 0 to 200 tenants, start with **WorkOS (free tier)** or **Supabase Auth**. Both provide foundation for enterprise SSO later.

---

## 1. Authentication Platform Comparison

### WorkOS (Recommended for B2B-First)

**Pricing Model**:
- Free up to 1 million MAUs
- SAML/SSO: $125/month per connection
  - Volume discounts: $100 (16-30), $80 (31-50), $65 (51-100)
- Directory Sync (SCIM): Included in enterprise plans
- No per-user seat charges

**Key Features**:
- Comprehensive: SAML, OIDC, SCIM, RBAC, JIT provisioning
- First-class organization support (core primitive)
- Radar security, Vault encryption
- Hosted AuthKit UI
- Python REST API integration

**Strengths**:
- Built for B2B from day one
- Predictable, flat-rate pricing (not per-user)
- Enterprise features included, not gated
- Broader feature coverage (38 vs 29 features vs Supabase)
- "WorkOS doesn't require you to outgrow it"

**Weaknesses**:
- Pure identity provider (pair with billing separately)

**Cost for 200 tenants**: $0-150/month (free) → $2,000-5,000/month with SSO

---

### Supabase Auth (Budget Option)

**Pricing**:
- 50,000 free MAUs (highest free tier)
- Pro: $25/month base + $0.00325/MAU over free tier

**Key Features**:
- PostgreSQL-powered (data ownership)
- Email/password, social login, magic links
- Basic RBAC via JWT claims
- Open-source (MIT license)
- GDPR, HIPAA, SOC2 compliant

**Strengths**:
- Lowest per-user costs at scale
- Data stays in your database
- Self-hosting option
- Simple for bootstrapped teams

**Weaknesses**:
- Enterprise SSO requires custom work
- No SCIM directory sync
- No built-in organization management
- Less polished than modern competitors

**Cost for 200 tenants**: $25-100/month (assuming 5K-20K MAUs)

---

### Auth0 (Enterprise, Expensive)

**Pricing**: ~$0.05/MAU (expensive at scale)

**Key Issues**:
- MAU model counts machine actors (APIs, jobs, agents) → cost explosion
- "Auth0's MAU model can consume 20-40% of gross margin in workspace products"
- Enterprise features (SAML, SCIM) gated behind premium tiers
- Why teams leave: "Operational cost of identity outpaces value"

**Cost for 200 tenants**: $500-2,500+/month (unpredictable)

---

### Clerk (Developer Experience Focus)

**Pricing**: ~$0.05/MAU (similar Auth0 scaling)

**Strengths**:
- Excellent React/Next.js integration
- Pre-built components (`<OrganizationSwitcher/>`)
- Production-ready in 5-15 minutes

**Weaknesses**:
- SAML SSO restricted to Enterprise tier (custom pricing)
- High vendor lock-in
- "Migrating away can be complex"
- Framework-dependent

**Cost for 200 tenants**: $500-2,500/month

---

## 2. M2M Authentication Patterns

### Option 1: API Keys (Simple)

**Pattern**: Opaque identifiers, server-side lookup

**Best for**: Simple integrations, third-party developers

```python
# Generate and store hashed
api_key = secrets.token_urlsafe(32)
stored_hash = hash_bcrypt(api_key)

# Validation
provided_key = request.headers.get("X-API-Key")
user = await db.query("""
  SELECT user_id, tenant_id FROM api_keys
  WHERE key_hash = ? AND is_active = 1
""", hash_bcrypt(provided_key))
```

**Pros**: Simple, easy onboarding
**Cons**: Static, manual revocation, requires DB lookup per request

---

### Option 2: OAuth 2.0 Client Credentials (RECOMMENDED)

**Pattern**: Exchange client_id + secret for short-lived JWT

**Token flow**:
```
1. Service A: POST /token with (client_id, client_secret)
2. AuthServer: Verify, issue JWT (exp: 1 hour)
3. Service A: Cache JWT, use for all requests
4. Service A: Refresh on expiration (auto)
```

**Pros**:
- Industry standard for M2M
- Automatic expiration (5-60 minutes)
- Granular scope-based permissions
- Stateless verification

**Cons**: More complex implementation

---

### Option 3: JWT (JSON Web Tokens)

**Pattern**: Self-contained, cryptographically signed

**Example payload for your API**:
```json
{
  "sub": "tenant_123",
  "user_id": "user_456",
  "role": "developer",
  "permissions": ["read:news", "write:queries"],
  "exp": 1707843600
}
```

**Pros**: Stateless, scales horizontally, no DB lookups
**Cons**: Cannot revoke before expiration

---

### Option 4: Mutual TLS (mTLS)

**Pattern**: Both parties present X.509 certificates

**Best for**: High-security, payment processing

**Pros**: Strongest security
**Cons**: Complex certificate lifecycle

---

## 3. Hybrid Recommendation for News Search API

**Stage 1 (MVP)**: API Keys
- Simple implementation
- Good for onboarding

**Stage 2 (Growth)**: API Key → JWT Exchange
- Client gets API key from dashboard
- Exchange for JWT on first request (cache 1 hour)
- Use JWT for all subsequent calls
- Avoid Auth0's MAU explosion

**Security Checklist**:
```
✓ HTTPS/TLS for all requests
✓ API keys never logged (only hash)
✓ JWT expiration enforced (max 1 hour)
✓ Rotate secrets every 90 days
✓ Hash stored keys with bcrypt/argon2
✓ Monitor for unusual patterns
```

---

## 4. Secret Management

**Critical Rule**: Never hardcode secrets in source code

**Storage Solutions**:
- AWS Secrets Manager: $0.40/secret/month
- HashiCorp Vault: Self-hosted, free tier
- GCP Secret Manager: ~$0.05-0.15 per 10K ops
- Environment variables: Dev only

**Best practice**:
```python
# Production
import hvac
vault = hvac.Client(url="https://vault.company.com")
api_secret = vault.secrets.kv2.read_secret_version("secret/api_key")
```

---

## 5. SSO & Enterprise Integration

### SAML vs OIDC Decision

| Aspect | SAML | OIDC |
|--------|------|------|
| **Foundation** | XML assertions | OAuth 2.0 + JWT |
| **Best For** | Legacy enterprise (Okta, Azure AD) | Modern apps, SPAs, APIs |
| **Developer UX** | Complex (XML, certs) | Simple (JSON, REST) |
| **Market Position** | Dominant in workforce SSO | Growing, especially APIs |
| **Setup Time** | 2-4 weeks | 1-2 weeks |

**Recommendation**: Implement **both** to avoid friction with enterprise customers

### SAML Implementation Checklist

```
✓ Validate SAML assertion signatures (CRITICAL - fatal if skipped)
✓ Enforce NotBefore/NotOnOrAfter timestamps (5-min window)
✓ Support Just-in-Time (JIT) provisioning (auto-create accounts)
✓ Implement SCIM directory sync (auto-manage users)
✓ Provide metadata endpoint for customer config
✓ Handle certificate rotation (automate or alert)
✓ Log all authentication attempts
✓ Test with Okta, Azure AD, Google Workspace
```

### Common SAML Failures

Most breakdowns caused by:
1. Clock drift (server time misalignment)
2. Incorrect ACS URLs (Assertion Consumer Service)
3. Missing attributes (email, name)
4. Certificate rotation issues
5. Signature validation failures

**Detection tools**: SAML-Tracer browser extension (Firefox)

---

## 6. Directory Sync (SCIM)

**What**: System for Cross-domain Identity Management = auto-provision users from IdP

**Why**: Required for Fortune 500 deals, automates user lifecycle

**Scope**:
```
IN (from IdP):
- Create user
- Disable user
- Update attributes (email, name, groups)

OUT (to IdP):
- Confirm provisioning success
- Handle conflicts
```

**Cost**: $65-250/month per connection (included in enterprise tiers)

---

## 7. Enterprise Sales Impact

**Market statistics**:
- "72% of mid-market companies mandate SSO for vendor procurement"
- Enterprise SSO market projected to exceed $23.99 billion by 2037

**Timeline to implement**:
- When: Targeting $50K+ ACV customers or 3+ prospects requesting
- If 1-2 prospects: Defer
- If 3+ prospects: Prioritize

**Typical enterprise purchase flow**:
```
1. Prospect evaluation (POC)
2. "We require SSO" (suddenly critical)
3. Your delay = deal lost or 2-3 month sales cycle extension
```

---

## 8. Selection Matrix for News Search API

| Stage | Recommendation | Cost |
|-------|---|---|
| **MVP (0-50 tenants)** | Supabase Auth OR WorkOS (free) | $0-25/mo |
| **Growth (50-200)** | WorkOS (enterprise-ready) | $150-1,500/mo |
| **Enterprise (200+)** | WorkOS + SAML SSO | $2,000-5,000/mo |

---

## 9. Implementation Roadmap

**Week 1-2 (MVP)**:
- Basic API key auth
- Tenant isolation
- Usage logging

**Week 3-4 (Production)**:
- JWT tokens
- RBAC middleware
- Stripe integration

**Week 5-8 (Enterprise)**:
- WorkOS integration
- SAML SSO
- SCIM directory sync

**Month 3-6 (Scale)**:
- Multi-region SSO
- Advanced audit logging
- Compliance (HIPAA, SOC2)

