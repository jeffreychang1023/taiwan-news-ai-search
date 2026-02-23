# B2B SaaS Authentication, Authorization & Billing Research (2025-2026)

## Complete Research Package for News Search API

This directory contains comprehensive research on best practices for building a B2B SaaS news search API service, scaling from 0 to 200 tenants.

---

## Document Index

### 1. **b2b-saas-research-part1-authentication.md** (8.6 KB)
   **Focus**: Authentication & Identity Providers

   Contains:
   - Platform comparison: WorkOS vs Auth0 vs Clerk vs Supabase Auth vs Scalekit
   - Pricing models and cost analysis
   - M2M authentication patterns (API Keys, OAuth 2.0, JWT, mTLS)
   - Secret management best practices
   - SSO implementation (SAML vs OIDC)
   - Directory sync (SCIM) requirements
   - Enterprise sales impact and timeline
   - Selection matrix for different growth stages

   **Key Recommendation**: Start with WorkOS (free tier) or Supabase Auth, transition to WorkOS at 50 tenants

---

### 2. **b2b-saas-research-part2-authorization.md** (15 KB)
   **Focus**: Authorization & RBAC (Role-Based Access Control)

   Contains:
   - Multi-tenant RBAC design patterns (Global, Tenant-Scoped, Hybrid)
   - Complete PostgreSQL schema for RBAC
   - aiohttp middleware implementation (auth + RBAC)
   - Tenant isolation patterns (critical for security)
   - Common mistakes to avoid (data leakage, UI-only gates)
   - Authorization caching strategy
   - Enterprise integration (IdP groups → roles)
   - Resource-based access control
   - Audit logging for compliance
   - Complete test suite examples

   **Key Recommendation**: Use Tenant-Scoped RBAC with admin/developer/viewer roles

---

### 3. **b2b-saas-research-part3-billing-metering.md** (18 KB)
   **Focus**: Billing & Usage-Based Metering

   Contains:
   - Stripe Billing architecture and setup
   - Meter definitions (api_query, llm_tokens, deep_research)
   - Usage recording patterns (single, batch, LLM-specific)
   - Cost allocation strategies (Markup %, Flat-rate, Real-time)
   - Stripe API performance (V1 vs V2 EventStream)
   - Example pricing tiers (Starter $99, Professional $299, Enterprise custom)
   - aiohttp middleware for metering
   - Subscription management
   - Usage alerts and quota management
   - Invoicing and analytics
   - Complete implementation examples

   **Key Recommendation**: Use per-query + LLM token metering with 1.3x markup on LLM costs

---

### 4. **b2b-saas-research-part4-api-gateway-ratelimit.md** (20 KB)
   **Focus**: Rate Limiting & API Gateway Options

   Contains:
   - Rate limiting options comparison
   - aiolimiter (in-memory, for MVP)
   - Redis-backed rate limiting (distributed)
   - Kong API Gateway (mature solution)
   - Cloud API gateways (AWS, GCP)
   - Tiered rate limits by plan
   - Monthly quota management
   - Soft limits (warnings) vs hard limits (blocking)
   - HTTP 429 proper response headers
   - Testing rate limiting
   - Monitoring and alerting
   - Cost comparison matrix
   - Common pitfalls

   **Key Recommendation**: Start with aiolimiter (Week 1), add Redis at 50 tenants, migrate to Kong at 500 tenants

---

### 5. **b2b-saas-research-summary.md** (17 KB)
   **Focus**: Implementation Roadmap & Quick Reference

   Contains:
   - Quick reference stacks (auth, authorization, billing, API gateway)
   - Total cost of operations breakdown
   - Week-by-week implementation roadmap (6 weeks + Month 3)
   - Key implementation details (code patterns, flows, middleware stack)
   - Essential database schema
   - Complete testing checklist
   - Security checklist
   - Deployment checklist
   - Monitoring metrics and alerting rules
   - Cloud services recommendations
   - Resource links and references
   - Next steps

   **Key Recommendation**: Start Week 1 with API key + JWT, integrate Stripe by Week 3

---

## Quick Start (TL;DR)

### For MVP (This Week)

```
1. Choose: WorkOS (free) or Supabase Auth
2. Implement: API key generation + validation
3. Add: aiolimiter rate limiting (100 req/min)
4. Create: PostgreSQL tables for tenant_users, api_keys
5. Test: Auth works, rate limits work, isolation works
```

**Estimated effort**: 3-5 days | **Cost**: $0

---

### For Production (4 Weeks)

```
Week 1: API key → JWT exchange
Week 2: RBAC middleware + tenant isolation
Week 3: Stripe Billing + metering
Week 4: Quota management + alerts
```

**Estimated effort**: 4 weeks | **Cost**: $0-50/month (Redis)

---

### For Enterprise (8 Weeks)

```
Week 5-6: SSO (SAML) via WorkOS
Week 7-8: SCIM directory sync
Month 3: Advanced features (analytics, audit logs)
```

**Estimated effort**: 8 weeks | **Cost**: $125-250/month (SSO)

---

## Platform Recommendations by Stage

### Stage 1: MVP (0-50 tenants)

| Component | Recommendation | Cost |
|-----------|---|---|
| **Auth** | Supabase Auth OR WorkOS free tier | $0-25 |
| **M2M** | API Key → JWT exchange | Custom |
| **Authorization** | Tenant-scoped RBAC (PostgreSQL) | Custom |
| **Billing** | Stripe test mode (prepare for launch) | $0 |
| **Rate Limiting** | aiolimiter (in-memory) | $0 |
| **Total** | | **$0-25/month** |

---

### Stage 2: Growth (50-200 tenants)

| Component | Recommendation | Cost |
|-----------|---|---|
| **Auth** | WorkOS ($0 base, enterprise ready) | $0-150 |
| **M2M** | OAuth 2.0 Client Credentials | Custom |
| **Authorization** | Tenant-scoped RBAC + resource-based | Custom |
| **Billing** | Stripe production (live) | 0.5% revenue |
| **Rate Limiting** | Redis + custom middleware | $15-50 |
| **SSO** | Prepare for SAML (when 3+ customers request) | +$125/conn |
| **Total** | | **$15-200/month + 0.5% revenue** |

---

### Stage 3: Enterprise (200+ tenants)

| Component | Recommendation | Cost |
|-----------|---|---|
| **Auth** | WorkOS (enterprise-proven) | $150-300 |
| **M2M** | OAuth 2.0 + service principals | Custom |
| **Authorization** | Multi-tenant RBAC + audit logs | Custom |
| **Billing** | Stripe (mature integration) | 0.5-1% revenue |
| **Rate Limiting** | Kong OSS or Enterprise | $50-2,000 |
| **SSO** | SAML + OIDC for all enterprise customers | $125-250/conn |
| **SCIM** | Directory sync for large customers | Included in SSO |
| **Total** | | **$325-2,550/month + 0.5-1% revenue** |

---

## Key Insights from Research

### Authentication

1. **WorkOS is best for B2B SaaS**: Free tier, enterprise-ready, predictable pricing
2. **Auth0 is expensive for APIs**: M2M actors count as MAUs, costs explode with usage
3. **API key → JWT hybrid is optimal**: Easy onboarding + stateless validation
4. **SSO is a sales requirement**: 72% of mid-market companies mandate it for vendor procurement

### Authorization

1. **Tenant isolation is CRITICAL**: Missing tenant_id in a single query = data leakage
2. **RBAC must be tenant-scoped**: Same user, different roles per tenant
3. **Middleware enforcement > UI gates**: Backend must validate, not just frontend
4. **Cache with tenant context**: Cache keys must include tenant_id to prevent cross-tenant leaks

### Billing

1. **Stripe Meters are the modern standard**: Replaces flat-rate + overage models
2. **LLM token costs vary**: Need strategy to pass costs fairly to customers
3. **V2 EventStream API supports 10K req/s**: Future-proof for high-concurrency
4. **Billing reconciliation is important**: Verify invoices match recorded usage monthly

### Rate Limiting

1. **Start with aiolimiter**: Simple, zero external deps, sufficient for MVP
2. **Redis at scale**: Needed when multi-server or when approaching rate limit ceiling
3. **Kong is mature but overkill early**: Wait until 500+ tenants or 10M+ req/month
4. **Tiered limits drive adoption**: Starter (100/min) → Professional (1K/min) → Enterprise (custom)

---

## Implementation Priorities

### MUST DO (Week 1)
- [ ] API key generation + validation
- [ ] aiolimiter rate limiting
- [ ] Tenant isolation in queries
- [ ] Basic RBAC (admin/developer/viewer)

### SHOULD DO (Week 2-3)
- [ ] JWT token exchange
- [ ] Stripe Billing integration
- [ ] Usage metering
- [ ] Monthly quota enforcement

### NICE TO HAVE (Month 3+)
- [ ] SAML SSO
- [ ] SCIM directory sync
- [ ] Audit logging
- [ ] Analytics dashboard

---

## Security Checklist (BEFORE LAUNCH)

```
Authentication:
✓ HTTPS/TLS enforced
✓ API keys hashed (bcrypt)
✓ JWT tokens signed and expiring
✓ Secrets in vault, not code

Authorization:
✓ Every query filters by tenant_id
✓ Admin-only endpoints check role
✓ Cross-tenant access impossible
✓ Cache keys include tenant context

Billing:
✓ Meter events logged
✓ Idempotent keys prevent double-charging
✓ Soft limits warn, hard limits block
✓ Quota resets at month boundary

General:
✓ No hardcoded secrets
✓ Logging doesn't leak tokens
✓ Error messages are generic
✓ CORS configured correctly
```

---

## Cost Model Example (News Search API)

### Pricing Tiers

**Starter** - $99/month
- 1,000 queries/month
- 2 news sources
- No reasoning (BM25 + XGBoost only)
- Est. LLM cost: $0

**Professional** - $299/month
- 10,000 queries/month
- All 7 news sources
- Reasoning + ranking included
- Est. LLM cost: $50-100/month (absorbed)

**Enterprise** - Custom
- 100K+ queries/month
- Deep research (Claude Opus)
- SAML SSO (+$125-250/month)
- 99.9% SLA

### Unit Economics

Assuming 200 tenants:
- 50% Starter: 50 × $99 = $4,950/month
- 35% Professional: 70 × $299 = $20,930/month
- 15% Enterprise: 30 × $3,000+ = $90,000+/month
- **MRR**: $115,880 (80% tier mix)

After costs:
- Stripe fees (0.5%): $580/month
- Infrastructure: $100-500/month
- SSO (20 customers): $2,500/month
- **Gross margin**: ~95%

---

## Testing Strategy

### Unit Tests (Per Module)
- Authentication: Valid/invalid tokens, expiration
- Authorization: Role checks, tenant isolation
- Billing: Meter events recorded correctly
- Rate Limiting: Limit enforced, headers correct

### Integration Tests
- Full auth flow (API key → JWT → request)
- User creation → RBAC assignment → access check
- Query recorded → Stripe event → invoice
- Rate limit + quota combined

### End-to-End Tests
- New tenant signup → SSO flow (if enabled)
- User invitation → permission assignment → access
- Query made → usage tracked → quota checked → billed

### Load Tests
- 1,000 concurrent requests
- Rate limiting doesn't drop valid requests
- Database queries remain <100ms
- Stripe metering doesn't become bottleneck

---

## Monitoring & Alerts

### Key Metrics

**Authentication**:
- Failed auth attempts/hour
- Average token validation latency
- SSO provisioning failures

**Authorization**:
- Cross-tenant access attempts (should be 0!)
- Permission check failures
- Role change audit trail

**Billing**:
- Meter events recorded/day
- Stripe API error rate
- Revenue tracking accuracy

**Rate Limiting**:
- 429 response rate
- Requests hitting quotas
- Rate limit bypass attempts

### Critical Alerts

```
EMERGENCY:
- Cross-tenant data access detected
- Stripe API failing
- Rate limiter offline
- Database down

URGENT:
- High 429 rate (>10% of traffic)
- Soft quota hitting (>50 tenants at limit)
- Failed auth attempts (>100/hour)

WARNING:
- High database query latency (>200ms)
- Meter event backlog (>1,000 pending)
- SSL certificate expiring in <7 days
```

---

## References

### Official Docs
- WorkOS: https://workos.com/docs
- Stripe Billing: https://docs.stripe.com/billing/subscriptions/usage-based
- aiolimiter: https://pypi.org/project/aiolimiter/
- Kong: https://konghq.com/docs

### Best Practices
- Multi-Tenant RBAC: https://workos.com/blog/how-to-design-multi-tenant-rbac-saas
- SAML SSO: https://www.scalekit.com/blog/saml-sso-in-b2b-saas-the-complete-guide-for-developers-and-enterprise-buyers
- M2M Auth: https://guptadeepak.com/beyond-human-access-machine-to-machine-authentication-for-modern-b2b-saas/
- Rate Limiting: https://quentin.pradet.me/blog/how-do-you-rate-limit-calls-with-aiohttp.html

### Libraries
- stripemeter: https://github.com/geminimir/stripemeter
- aiohttp: https://docs.aiohttp.org/
- pytest-aiohttp: https://pypi.org/project/pytest-aiohttp/

---

## Next Steps

### This Week
- [ ] Read b2b-saas-research-part1-authentication.md (choose provider)
- [ ] Set up WorkOS or Supabase Auth account
- [ ] Review database schema (b2b-saas-research-part2-authorization.md)
- [ ] Create PR for tenant_users table

### Next Week
- [ ] Implement API key generation
- [ ] Implement JWT token endpoint
- [ ] Add RBAC middleware
- [ ] First code review with security focus

### Month 1
- [ ] Stripe Billing integration
- [ ] Metering middleware
- [ ] Quota management
- [ ] Production launch checklist

---

## Document Version

**Created**: February 2026
**Based on**: 2025-2026 SaaS best practices
**Status**: Complete research package, ready for implementation
**Maintenance**: Review quarterly as industry evolves

---

## Questions?

For each component:
1. **Authentication**: See part1-authentication.md
2. **Authorization**: See part2-authorization.md
3. **Billing**: See part3-billing-metering.md
4. **Rate Limiting**: See part4-api-gateway-ratelimit.md
5. **Implementation**: See summary.md for roadmap

All documents include:
- Complete code examples
- Database schemas
- Configuration examples
- Test cases
- Security considerations
- Deployment guidance

