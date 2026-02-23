# B2B SaaS Research: Billing & Usage-Based Metering (2025-2026)

## Core Concept

Stripe Billing with usage meters = charge customers based on actual API consumption

---

## 1. Stripe Billing Architecture

**Core flow**:
```
1. Customer takes action (search query)
   ↓
2. Your service records meter event
   ↓
3. Stripe aggregates events over billing period
   ↓
4. Generate invoice based on usage
   ↓
5. Charge customer
```

---

## 2. Meter Setup

### Define What to Measure

```python
import stripe

# Meter 1: API queries
stripe.billing.Meter.create(
    event_name="api_query",
    display_name="API Queries",
    value_settings={
        "value_key": "value"
    }
)

# Meter 2: LLM tokens (for reasoning/ranking)
stripe.billing.Meter.create(
    event_name="llm_tokens",
    display_name="LLM Tokens Used",
    value_settings={
        "value_key": "token_count"
    }
)

# Meter 3: Advanced search mode (more expensive)
stripe.billing.Meter.create(
    event_name="deep_research_queries",
    display_name="Deep Research Queries",
    value_settings={
        "value_key": "value"
    }
)
```

### Create Product with Metered Pricing

```python
# Create product
product = stripe.Product.create(
    name="News Search API",
    type="service"
)

# Tiered pricing: cheaper per-query at high volume
price = stripe.Price.create(
    product=product.id,
    billing_scheme="tiered",
    tiers_mode="graduated",  # Tier 1: 0-10K, Tier 2: 10K+
    currency="usd",
    tiers=[
        {
            "unit_amount": 10,  # $0.10 per query, first 10K
            "up_to": 10000,
            "meter": "api_query"
        },
        {
            "unit_amount": 5,   # $0.05 per query, above 10K
            "up_to": "inf",
            "meter": "api_query"
        }
    ],
    recurring={
        "aggregate_usage": "sum",  # Sum all meter events
        "interval": "month",
        "usage_type": "metered"
    }
)
```

---

## 3. Recording Usage: Meter Events

### Pattern 1: Per-Query Metering (Simple)

```python
import stripe
import time
import uuid

async def record_api_usage(tenant_id: str, query_type: str):
    """Record one API query for billing"""
    stripe.billing.MeterEvent.create(
        event_name="api_query",
        payload={
            "stripe_customer_id": tenant_id,  # Maps to Stripe customer ID
            "value": 1,  # 1 query
        },
        identifier=f"{tenant_id}:{uuid.uuid4()}",  # Idempotency key
        timestamp=int(time.time())
    )
```

### Pattern 2: Batch Metering (High-Volume Systems)

```python
# Queue multiple events, send in batch
async def batch_record_usage(events: List[dict]):
    """Record multiple meter events at once"""
    for event in events:
        stripe.billing.MeterEvent.create(
            event_name=event["event_name"],
            payload=event["payload"],
            identifier=event["identifier"],
            timestamp=event["timestamp"]
        )

# In your search handler
@app.post("/api/news/search")
async def search_news(request):
    tenant_id = request["tenant_id"]

    # Perform search
    results = await search_engine.search(request.query["q"])

    # Queue meter event (don't wait for Stripe)
    meter_events.append({
        "event_name": "api_query",
        "payload": {"stripe_customer_id": tenant_id, "value": 1},
        "identifier": f"{tenant_id}:{uuid.uuid4()}",
        "timestamp": int(time.time())
    })

    return web.json_response(results)

# Background task flushes periodically
async def flush_meter_events():
    while True:
        await asyncio.sleep(5)  # Every 5 seconds
        if meter_events:
            await batch_record_usage(meter_events.copy())
            meter_events.clear()
```

### Pattern 3: LLM Token Metering (With Model Tracking)

```python
async def record_llm_usage(
    tenant_id: str,
    model: str,
    input_tokens: int,
    output_tokens: int
):
    """Track LLM token usage for reasoning/ranking"""
    total_tokens = input_tokens + output_tokens

    stripe.billing.MeterEvent.create(
        event_name="llm_tokens",
        payload={
            "stripe_customer_id": tenant_id,
            "value": total_tokens,
        },
        identifier=f"{tenant_id}:{model}:{uuid.uuid4()}",
        timestamp=int(time.time())
    )
```

---

## 4. Cost Allocation Strategies

**Challenge**: Your system uses multiple LLM APIs with different costs. How to price fairly?

### Strategy 1: Markup Percentage (Simplest)

```python
# OpenAI costs you ~$0.002 per search query
openai_cost = 0.002

# Charge customer 1.3x (30% markup = profit + infrastructure)
markup_multiplier = 1.30
charged_to_customer = openai_cost * markup_multiplier  # $0.0026

# Send to Stripe
stripe.billing.MeterEvent.create(
    event_name="llm_tokens",
    payload={
        "stripe_customer_id": tenant_id,
        "value": int(charged_to_customer * 10000)  # Store as units
    }
)
```

**Pros**: Simple, scalable
**Cons**: Ignores query variance, markup might be unfair if costs vary wildly

---

### Strategy 2: Flat-Rate Bundling (Recommended for predictability)

```
Tier pricing:
- Starter: $99/month
  • 1,000 queries/month included
  • BM25 + XGBoost ranking (no LLM reasoning)
  • 2 news sources

- Professional: $299/month
  • 10,000 queries/month
  • Reasoning + ranking included
  • All news sources (7 sources)

- Enterprise: Custom pricing
  • 100K+ queries/month
  • Deep research (Claude Opus) included
  • Dedicated support

Each tier includes estimated LLM costs.
Absorb variance as business cost.
```

**Pros**:
- Predictable for customers
- Simple billing
- Easier sales process

**Cons**:
- Need good cost forecasting
- May lose money on heavy users

---

### Strategy 3: Real-Time Cost Tracking (Most Accurate)

```python
# Pricing database by model
LLM_PRICING = {
    "gpt-4-turbo": {
        "input": 0.01 / 1000,      # $0.01 per 1K input tokens
        "output": 0.03 / 1000       # $0.03 per 1K output tokens
    },
    "gpt-4o-mini": {
        "input": 0.00015 / 1000,
        "output": 0.0006 / 1000
    },
    "claude-3-5-sonnet": {
        "input": 0.003 / 1000,
        "output": 0.015 / 1000
    },
    "claude-opus": {
        "input": 0.015 / 1000,
        "output": 0.075 / 1000
    }
}

async def calculate_llm_cost(
    model: str,
    input_tokens: int,
    output_tokens: int
) -> float:
    """Calculate exact cost of LLM call"""
    rates = LLM_PRICING[model]
    cost = (input_tokens * rates["input"]) + (output_tokens * rates["output"])

    # Apply markup (30%)
    return cost * 1.30

async def record_reasoning_usage(
    tenant_id: str,
    model: str,
    tokens_used: dict  # {"input": 500, "output": 200}
):
    """Record cost per reasoning call"""
    cost_cents = int(
        await calculate_llm_cost(
            model,
            tokens_used["input"],
            tokens_used["output"]
        ) * 100
    )

    stripe.billing.MeterEvent.create(
        event_name="llm_cost",
        payload={
            "stripe_customer_id": tenant_id,
            "value": cost_cents  # Store as cents
        }
    )
```

**Pros**: Fair, accurate, transparent
**Cons**: Requires tracking all LLM costs

---

## 5. Stripe API Performance

### V1 Meter Event API
- Up to 1,000 requests/second
- Standard for most use cases
- Recommended for early stage

### V2 Meter EventStream API (2026+)
- Up to 10,000 requests/second
- For high-concurrency AI workloads
- **CRITICAL for your use case** (concurrent user queries)
- Designed for modern, high-volume services

**Recommendation**: Start with V1, upgrade to V2 when approaching 500+ concurrent users

### Python Library: stripemeter

```bash
pip install stripemeter
```

**Features**:
- Exactly-once processing (idempotency)
- Real-time cost projections
- Invoice parity guarantees
- Built for Python async

---

## 6. Pricing Tiers Example (News Search API)

### Tier 1: Starter - $99/month

```
✓ 1,000 queries/month included
✓ $0.10/additional query
✓ 2 news sources (udn, ltn)
✓ Search only (no reasoning)
✓ API key management
✓ Email support
✓ 1 year data retention
```

**Target**: Individuals, small teams, content scrapers

---

### Tier 2: Professional - $299/month

```
✓ 10,000 queries/month
✓ $0.05/additional query
✓ All news sources (7 total)
✓ Reasoning + ranking
✓ Deep research mode
✓ Analytics dashboard
✓ Webhook support
✓ Priority email support
✓ 2 years data retention
```

**Target**: Content agencies, news teams, research firms

---

### Tier 3: Enterprise - Custom pricing

```
✓ 100K+ queries/month
✓ $0.01-0.03/query (volume discount)
✓ Custom data freshness SLA
✓ Dedicated API key management
✓ SAML SSO (add $125-250/month)
✓ Custom data export
✓ Dedicated Slack support
✓ 5 years data retention
✓ Audit logging
```

**Target**: News organizations, government agencies, large enterprises

---

## 7. Integration with aiohttp

### Middleware to Track Usage

```python
import asyncio
from aiohttp import web

@aiohttp.middleware
async def metering_middleware(request, handler):
    """Record API usage for billing"""
    tenant_id = request.get("tenant_id")
    if not tenant_id:
        return await handler(request)

    try:
        response = await handler(request)

        # Log successful queries
        if request.path.startswith("/api/news/search") and response.status == 200:
            # Don't block request - send async
            asyncio.create_task(
                record_stripe_event(
                    event_name="api_query",
                    tenant_id=tenant_id,
                    query_mode=request.query.get("mode", "standard")
                )
            )

        return response
    except Exception as e:
        # Failed queries might still count (depends on SLA)
        # Decide: should failed requests be charged?
        raise


async def record_stripe_event(
    event_name: str,
    tenant_id: str,
    query_mode: str = None
):
    """
    Queue meter event for Stripe
    Run async to avoid blocking requests
    """
    try:
        payload = {
            "stripe_customer_id": tenant_id,
            "value": 1,
        }

        stripe.billing.MeterEvent.create(
            event_name=event_name,
            payload=payload,
            identifier=f"{tenant_id}:{uuid.uuid4()}",
            timestamp=int(time.time())
        )

        logger.info(f"Recorded meter event: {event_name} for {tenant_id}")

    except Exception as e:
        logger.error(f"Failed to record Stripe event: {e}")
        # TODO: Retry logic, alerting
```

---

## 8. Subscription Management

### Create Subscription from UI

```python
async def create_subscription(tenant_id: str, plan: str):
    """Create subscription for customer"""

    # Get Stripe customer ID for tenant
    customer_id = await db.fetchval(
        "SELECT stripe_customer_id FROM tenants WHERE tenant_id = ?",
        tenant_id
    )

    if not customer_id:
        # Create new Stripe customer
        customer = stripe.Customer.create(
            metadata={"tenant_id": tenant_id}
        )
        customer_id = customer.id

        # Store in DB
        await db.execute(
            "UPDATE tenants SET stripe_customer_id = ? WHERE tenant_id = ?",
            customer_id, tenant_id
        )

    # Create subscription
    prices = {
        "starter": "price_starter_monthly",
        "professional": "price_pro_monthly",
    }

    subscription = stripe.Subscription.create(
        customer=customer_id,
        items=[
            {
                "price": prices[plan],
            }
        ],
        payment_behavior="default_incomplete",
        expand=["latest_invoice.payment_intent"]
    )

    return {
        "subscription_id": subscription.id,
        "client_secret": subscription.latest_invoice.payment_intent.client_secret
    }
```

### Handle Webhook Events

```python
async def webhook_handler(request):
    """Process Stripe webhook events"""
    event = await request.json()

    if event["type"] == "customer.subscription.created":
        # New subscription
        subscription = event["data"]["object"]
        tenant_id = subscription["metadata"]["tenant_id"]
        await db.execute(
            "UPDATE tenants SET subscription_active = 1 WHERE tenant_id = ?",
            tenant_id
        )

    elif event["type"] == "invoice.payment_failed":
        # Payment failed
        invoice = event["data"]["object"]
        tenant_id = invoice["metadata"]["tenant_id"]
        # Send alert to tenant admin
        await send_payment_failed_alert(tenant_id, invoice)

    elif event["type"] == "customer.subscription.deleted":
        # Subscription canceled
        subscription = event["data"]["object"]
        tenant_id = subscription["metadata"]["tenant_id"]
        await revoke_api_access(tenant_id)

    return web.json_response({"ok": True})
```

---

## 9. Usage Alerts & Quota Management

### Soft Limit (Warning)

```python
QUOTAS = {
    "starter": {
        "monthly": 1000,
        "soft_limit": 900,  # Warn at 90%
        "hard_limit": 1000   # Block at 100%
    },
    "professional": {
        "monthly": 10000,
        "soft_limit": 9000,
        "hard_limit": 10000
    }
}

async def check_usage_and_alert(tenant_id: str):
    """Check if tenant approaching quota"""
    plan = await get_tenant_plan(tenant_id)
    current_month = datetime.now().strftime("%Y-%m")
    quota_key = f"usage:{tenant_id}:{current_month}"

    usage = await redis.get(quota_key) or 0
    quota_config = QUOTAS[plan]

    if usage > quota_config["soft_limit"]:
        # Send warning email
        admin_email = await get_tenant_admin_email(tenant_id)
        await send_quota_warning_email(
            admin_email,
            tenant_id=tenant_id,
            usage=usage,
            limit=quota_config["hard_limit"],
            percentage=(usage / quota_config["hard_limit"]) * 100
        )

    if usage >= quota_config["hard_limit"]:
        # Block requests
        raise web.HTTPPaymentRequired(
            text=f"Monthly quota exceeded: {usage}/{quota_config['hard_limit']}"
        )
```

### Hard Limit (Block)

```python
async def enforce_quota(request, handler):
    """Enforce hard limits"""
    tenant_id = request.get("tenant_id")
    plan = await get_tenant_plan(tenant_id)

    current_month = datetime.now().strftime("%Y-%m")
    quota_key = f"usage:{tenant_id}:{current_month}"

    usage = int(await redis.get(quota_key) or 0)
    limit = QUOTAS[plan]["hard_limit"]

    if usage >= limit:
        raise web.HTTPPaymentRequired(
            text=f"Monthly quota exceeded ({usage}/{limit}). Upgrade plan or wait for reset."
        )

    return await handler(request)
```

---

## 10. Invoicing & Analytics

### Preview Invoice (Before Billing)

```python
# Stripe automatically calculates usage-based charges
subscription = stripe.Subscription.retrieve("sub_123")
upcoming_invoice = stripe.Invoice.upcoming(customer=subscription.customer)

print(f"Upcoming invoice: ${upcoming_invoice.amount_due / 100}")
print(f"Items: {upcoming_invoice.lines}")
```

### Meter Usage Analytics

```python
# Query usage over time
usage_records = stripe.billing.MeterEventAdjustment.list(
    meter="api_query",
    customer="cus_123"
)

# Aggregate per day
daily_usage = defaultdict(int)
for event in usage_records:
    date = event.timestamp.date()
    daily_usage[date] += event.value

print(daily_usage)
```

---

## 11. Cost Considerations

### Infrastructure Costs

- **Stripe Billing**: No base cost, 0.5% of revenue in transaction fees
- **Redis for metering**: $15-30/month (1GB managed)
- **Database**: $25-50/month (PostgreSQL)
- **Monitoring**: $0-100/month (DataDog, CloudWatch)

### Total Billing Stack

**Startup (0-50 tenants)**: $40-200/month
**Growth (50-200 tenants)**: $1,000-2,000/month
**Enterprise (200+ tenants)**: $3,000+/month (ops overhead)

---

## 12. Monitoring & Debugging

### Log All Meter Events

```python
async def record_meter_event_with_logging(
    event_name: str,
    tenant_id: str,
    value: int = 1,
    **kwargs
):
    """Record meter event with detailed logging"""

    logger.info(
        f"Meter event: {event_name}",
        extra={
            "tenant_id": tenant_id,
            "value": value,
            "timestamp": datetime.utcnow().isoformat(),
            **kwargs
        }
    )

    try:
        stripe.billing.MeterEvent.create(
            event_name=event_name,
            payload={"stripe_customer_id": tenant_id, "value": value},
            identifier=f"{tenant_id}:{uuid.uuid4()}",
            timestamp=int(time.time())
        )
    except Exception as e:
        logger.error(f"Failed to record meter event: {e}")
        # Retry queue, alerting
```

### Verify Invoices Match Usage

```python
async def audit_invoice_accuracy(subscription_id: str):
    """Verify invoice matches recorded usage"""

    invoice = stripe.Invoice.retrieve(subscription_id)

    # Get meter events for this billing period
    meter_events = stripe.billing.MeterEvent.list(
        meter="api_query",
        customer=invoice.customer,
        # Filter by billing period
    )

    total_recorded = sum(event.value for event in meter_events)

    # Compare
    invoice_amount = invoice.lines.data[0].quantity
    if total_recorded != invoice_amount:
        logger.error(
            f"Invoice mismatch: recorded={total_recorded}, invoiced={invoice_amount}"
        )
        # Investigate discrepancy
```

