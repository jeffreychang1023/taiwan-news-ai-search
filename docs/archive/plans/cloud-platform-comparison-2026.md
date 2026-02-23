# Cloud Platform Comparison for B2B SaaS Deployment (2026)

**System Requirements:**
- Python 3.11 aiohttp web server
- Qdrant vector database
- PostgreSQL for metadata
- LLM API calls (Azure OpenAI / Anthropic)
- SSE streaming responses
- WebSocket for real-time updates

**Deployment Scales:**
- **Small**: 10 tenants, ~1000 queries/day
- **Medium**: 50 tenants, ~5000 queries/day
- **Large**: 200 tenants, ~20000 queries/day

---

## 1. Google Cloud Platform (GCP)

### Container Orchestration

#### Cloud Run (Recommended for Small-Medium)
**Pros:**
- Fully serverless, pay-per-use billing (per second)
- Native WebSocket and SSE support
- Auto-scaling from 0 to thousands of instances
- No infrastructure management
- Automatic TLS/HTTPS
- 17% savings with 1-year CUDs, 30%+ with 3-year

**Cons:**
- Long-lived WebSocket connections incur continuous charges
- 60-minute request timeout (connections must reconnect)
- Ephemeral storage (containers restart on deployment)

**Pricing (us-central1):**
- vCPU: $0.00002400/vCPU-second ($0.0864/vCPU-hour)
- Memory: $0.00000250/GiB-second ($0.009/GiB-hour)
- Requests: First 2M free/month
- Minimum instance hours: Free tier available

**Use Cases:**
- Ideal for variable workloads
- Cost-effective for bursty traffic
- Best for <500K requests/day

#### Google Kubernetes Engine (GKE)
**Pros:**
- Full Kubernetes control
- Better for sustained WebSocket connections
- Persistent storage options
- More predictable costs at scale

**Cons:**
- Charged per VM, not per request
- Complex cost prediction
- Requires infrastructure management
- Control plane fee: $73/month (Standard), $438/month (Autopilot)

**Pricing:**
- e2-medium (2 vCPU, 4GB): ~$25/month
- n1-standard-2 (2 vCPU, 7.5GB): ~$50/month
- Better for high-utilization, predictable workloads

### Managed PostgreSQL (Cloud SQL)

**Editions:**
- Enterprise: Standard performance
- Enterprise Plus: Enhanced HA, performance

**Pricing Components:**
- **Compute**:
  - db-f1-micro (1 vCPU, 614MB): ~$9/month
  - db-g1-small (1 vCPU, 1.7GB): ~$25/month
  - db-n1-standard-2 (2 vCPU, 7.5GB): ~$180/month

- **Storage**:
  - SSD: $0.222/GB/month
  - HDD: $0.118/GB/month

- **High Availability**: +100% compute cost
- **Backups**: Free up to provisioned storage size

**Small Deployment (10GB SSD):**
- db-g1-small: $25 + (10 × $0.222) = ~$27/month
- With HA: ~$54/month

**Medium Deployment (100GB SSD):**
- db-n1-standard-2: $180 + (100 × $0.222) = ~$202/month
- With HA: ~$404/month

### Networking

**Load Balancer:**
- No additional charge for Cloud Run (built-in)
- GKE: Included with regional load balancing

**Egress Pricing:**
- To Cloud CDN/Load Balancer: Free
- Same region: Free
- Within GCP (cross-region): $0.01/GB
- Internet (North America/Europe):
  - 0-1TB: $0.12/GB
  - 1-10TB: $0.11/GB
  - 10TB+: $0.08/GB

**First 1GB/month free to internet**

### Vector Database (Qdrant)

**Options:**
1. **Qdrant Cloud (Managed)**: Pricing on request, free 1GB tier
2. **Cloud Run**: Deploy in 5 minutes, but ephemeral storage (not production-ready)
3. **GKE**: Fault-tolerant cluster across multiple zones (recommended)
4. **Self-hosted on Compute Engine**: e2-medium with persistent SSD

**Estimated Self-Hosted (GKE):**
- Small (1 node, e2-medium): ~$50/month + storage
- Medium (3 nodes, HA): ~$150/month + storage
- Storage (100GB SSD): ~$20/month

### Auto-Scaling for SSE/WebSocket

**Cloud Run:**
- Scales to 250 concurrent requests/instance (default: 80)
- Auto-scales based on request concurrency
- ⚠️ WebSocket connections keep instances alive = continuous billing
- Min/max instances configurable

**Best Practice:**
- Use SSE for server-to-client streaming (simpler, cheaper)
- WebSocket only if bidirectional needed
- Set aggressive timeout for idle connections

### Estimated Monthly Costs

| Scale | Setup | Cloud Run | Cloud SQL | Qdrant | Egress (500GB) | Total |
|-------|-------|-----------|-----------|--------|----------------|-------|
| **Small** | Non-HA | $50 | $27 | $50 | $55 | **$182** |
| **Small** | HA | $50 | $54 | $75 | $55 | **$234** |
| **Medium** | HA | $200 | $202 | $150 | $55 | **$607** |
| **Large** | HA | $600 | $404 | $300 | $55 | **$1,359** |

---

## 2. Amazon Web Services (AWS)

### Container Orchestration

#### ECS with Fargate (Recommended for Most)
**Pros:**
- Serverless, no EC2 management
- Per-second billing
- Native AWS integration
- WebSocket support via ALB
- Good for variable workloads

**Cons:**
- More expensive than EC2 at high utilization
- Can cost 3x more than self-managed Kubernetes
- 9x more than EKS with Reserved Instances

**Pricing (us-east-1):**
- Linux/x86: $0.04048/vCPU-hour, $0.004445/GB-hour
- Linux/ARM (Graviton): $0.03239/vCPU-hour, $0.003556/GB-hour (20% cheaper)
- Example: 4 vCPU, 16GB = $0.22/hour = $160/month

**Savings Options:**
- Compute Savings Plans: Up to 50% (1-year or 3-year commitment)
- Fargate Spot: Up to 70% (fault-tolerant workloads)

#### EKS (Better for Large Scale)
**Pros:**
- Full Kubernetes
- Cheaper at high utilization
- Better for sustained workloads

**Cons:**
- Control plane: $73/month
- Still need to manage node groups
- More complex

**Cost Comparison (from research):**
- EKS + Fargate: $14,416/month (example workload)
- EKS + EC2 On-Demand: 6x cheaper = ~$2,400/month
- EKS + EC2 Reserved: 9x cheaper = ~$1,600/month

### Managed PostgreSQL (RDS)

**Pricing:**
- PostgreSQL is 10% costlier than MySQL/MariaDB

**Instance Types (us-east-1):**
- db.t3.micro (2 vCPU, 1GB): ~$15/month
- db.t3.small (2 vCPU, 2GB): ~$30/month
- db.t4g.medium (2 vCPU, 4GB, Graviton): ~$53/month
- db.m6g.large (2 vCPU, 8GB, Graviton): ~$120/month

**Storage:**
- General Purpose SSD: $0.115/GB/month
- First 100GB backup free
- Multi-AZ deployment: 2x compute cost

**Small Deployment (10GB):**
- db.t3.small: $30 + (10 × $0.115) = ~$31/month
- Multi-AZ: ~$62/month

**Medium Deployment (100GB):**
- db.m6g.large: $120 + (100 × $0.115) = ~$132/month
- Multi-AZ: ~$264/month

**Reserved Instances:**
- 1-year: ~35% discount
- 3-year: ~50% discount

### Networking

#### API Gateway vs Application Load Balancer

**API Gateway (for REST/HTTP/WebSocket):**
- HTTP APIs: $1.00/million requests
- REST APIs: $3.50/million requests (71% more expensive)
- WebSocket: $1.00/million messages + $0.25/million connection minutes
- Free tier: 1M API calls/month (12 months)

**Application Load Balancer (Recommended for >500K requests/day):**
- Hourly: $0.0225/hour (~$16/month)
- LCU: $0.008/LCU-hour
- **35x cheaper** than API Gateway REST APIs
- Breakeven: ~500K requests/day

**Egress Pricing:**
- Data transfer out to internet:
  - First 100GB/month: Free
  - 0-10TB: $0.09/GB
  - 10-50TB: $0.085/GB
  - 50TB+: $0.070/GB

**Recommendation:** Use ALB for production B2B SaaS

### Vector Database (Qdrant)

**Options:**
1. **Qdrant Cloud (Managed)**: Native AWS support, pricing on request
2. **ECS Fargate**: Not recommended (ephemeral)
3. **EKS**: Production-ready, multi-AZ
4. **EC2 self-hosted**: t3.medium with EBS

**Estimated Self-Hosted (EC2):**
- t3.medium (2 vCPU, 4GB): $30/month
- r6g.large (2 vCPU, 16GB, Graviton): $90/month
- EBS SSD (100GB): $10/month

### Auto-Scaling for SSE/WebSocket

**ECS Fargate:**
- Application Auto Scaling based on CloudWatch
- Step scaling recommended for WebSocket
- Target tracking for CPU/Memory
- Supports long-lived connections

**Best Practices:**
- Use ALB with WebSocket sticky sessions
- SSE via ALB HTTP/S
- Set connection timeout appropriately

### Estimated Monthly Costs

| Scale | Setup | ECS Fargate | RDS | Qdrant | ALB+Egress | Total |
|-------|-------|-------------|-----|--------|------------|-------|
| **Small** | Single-AZ | $80 | $31 | $40 | $20 | **$171** |
| **Small** | Multi-AZ | $80 | $62 | $80 | $20 | **$242** |
| **Medium** | Multi-AZ | $240 | $132 | $100 | $25 | **$497** |
| **Large** | Multi-AZ | $720 | $264 | $200 | $35 | **$1,219** |

**With Savings Plans (50%):**
- Small: $142
- Medium: $339
- Large: $839

---

## 3. Microsoft Azure

### Container Orchestration

#### Azure Container Apps (Recommended for Small-Medium)
**Pros:**
- Native WebSocket, gRPC, SSE support
- KEDA auto-scaling (event-driven)
- Scale-to-zero (cost savings)
- Per-second billing
- Free tier available

**Cons:**
- Can get pricey at scale
- Less mature than AKS

**Pricing Models:**
- **Consumption**: Free tier + pay-per-use
  - vCPU: Per-second billing
  - Memory: Per-second billing
  - Requests: Included

- **Dedicated (Workload Profiles)**:
  - Management: $0.10/hour
  - Plus resource consumption

**Estimated:**
- Small workload: ~$50-100/month (with scale-to-zero)
- Medium: ~$200-300/month

#### Azure Kubernetes Service (AKS)
**Pros:**
- Full Kubernetes control
- More cost-effective at scale
- Broader protocol support (TCP/UDP)

**Cons:**
- Control plane fees: Free, $73/month (Standard), $438/month (Premium)
- VM costs can be significant
- More complex

**VM Pricing (East US):**
- B2s (2 vCPU, 4GB): ~$30/month
- D2s_v3 (2 vCPU, 8GB): ~$70/month
- Spot VMs: Up to 90% discount

**Savings:**
- Azure Reservations: 1-year or 3-year
- Azure Savings Plan
- Spot VMs for non-critical workloads

### Managed PostgreSQL (Flexible Server)

**Pricing Tiers:**
- **Burstable**: Low-cost, variable workloads
- **General Purpose**: Balanced
- **Memory Optimized**: High-performance

**Pricing Components:**
- Compute: Per vCore-hour
- Storage: Per GiB-month
- Backup: Free up to 100% of provisioned storage

**Instance Examples (East US):**
- B1ms (1 vCore, 2GB, Burstable): ~$12/month
- B2s (2 vCore, 4GB, Burstable): ~$25/month
- D2s_v3 (2 vCore, 8GB, General Purpose): ~$110/month

**Storage:**
- Similar to other providers: ~$0.12-0.15/GB/month

**Small Deployment (10GB):**
- B2s: $25 + (10 × $0.12) = ~$26/month
- HA: ~$52/month

**Medium Deployment (100GB):**
- D2s_v3: $110 + (100 × $0.12) = ~$122/month
- HA: ~$244/month

**Reserved Capacity:**
- Up to 60% savings vs pay-as-you-go

### Networking

#### Application Gateway
**Pricing:**
- Time-based: Per hour provisioned
- Data processing: Per GB
- ⚠️ V1 retiring April 28, 2026 → must use V2

**Egress Pricing:**
- First 100GB/month: Free (all regions)
- Same Availability Zone: Free
- Between AZs: $0.01/GB
- Internet (North America/Europe): $0.02/GB
- Internet (Asia/Oceania/Middle East/Africa): $0.08/GB

**Note:** Azure Front Door doesn't support SSE currently

### Vector Database (Qdrant)

**Options:**
1. **Qdrant Cloud (Managed)**: Native Azure support
2. **Container Apps**: Possible but limited by ephemeral storage
3. **AKS**: Production-ready
4. **VM self-hosted**: B-series or D-series with managed disk

**Estimated Self-Hosted:**
- B2ms (2 vCPU, 8GB): $60/month
- D2s_v3 (2 vCPU, 8GB): $70/month
- Managed Disk (100GB SSD): ~$15/month

### Auto-Scaling for SSE/WebSocket

**Container Apps:**
- KEDA-based auto-scaling (event-driven)
- Custom metrics via Application Insights
- WebSocket-aware: Can scale by active connection count
- HTTP ingress supports sticky sessions (single-revision mode)

**Scaling Strategies:**
- HTTP request rate
- CPU/Memory
- Custom metrics (e.g., active WebSocket count)
- Queue depth (for async workloads)

**⚠️ SSE Limitation:** Azure Front Door doesn't support SSE

### Estimated Monthly Costs

| Scale | Setup | Container Apps | PostgreSQL | Qdrant | Egress | Total |
|-------|-------|----------------|------------|--------|--------|-------|
| **Small** | Single | $60 | $26 | $75 | $10 | **$171** |
| **Small** | HA | $60 | $52 | $120 | $10 | **$242** |
| **Medium** | HA | $250 | $122 | $150 | $10 | **$532** |
| **Large** | HA | $750 | $244 | $300 | $15 | **$1,309** |

**With Reserved Pricing (40% savings):**
- Small: $155
- Medium: $379
- Large: $935

---

## Platform Comparison Summary

### Cost Comparison (Medium Deployment, HA)

| Provider | Container | Database | Vector DB | Network | Total | With Savings |
|----------|-----------|----------|-----------|---------|-------|--------------|
| **AWS** | $240 | $132 | $100 | $25 | **$497** | **$339** (50%) |
| **GCP** | $200 | $202 | $150 | $55 | **$607** | **$425** (30%) |
| **Azure** | $250 | $122 | $150 | $10 | **$532** | **$379** (40%) |

### Key Observations

**Cheapest:**
- **AWS Fargate** has lowest base compute cost
- **Azure** has lowest egress cost (especially within region)
- **AWS** offers best discounts (50% Savings Plans)

**Most Expensive:**
- **GCP** has highest egress costs
- **GCP Cloud SQL** is pricier than competitors
- All platforms cost more without commitment discounts

### WebSocket/SSE Support Comparison

| Feature | GCP Cloud Run | AWS Fargate + ALB | Azure Container Apps |
|---------|---------------|-------------------|----------------------|
| **WebSocket** | ✅ Native | ✅ Via ALB | ✅ Native |
| **SSE** | ✅ Native | ✅ Via ALB | ⚠️ Not on Front Door |
| **Timeout** | 60 min | Configurable | Configurable |
| **Sticky Sessions** | ❌ | ✅ | ✅ (single-revision) |
| **Auto-scaling** | Request-based | CloudWatch metrics | KEDA (event-driven) |
| **Cost Model** | Per-second active | Per-second allocated | Per-second active |

### Recommendations by Scale

#### Small (10 tenants, 1K queries/day)
**Winner: AWS Fargate + ALB**
- Cost: $171/month (single-AZ) or $242/month (HA)
- With Savings Plan: $142/month
- Reasons:
  - Lowest base cost
  - Best for variable workloads
  - Simple management
  - ALB is cheaper than API Gateway at this scale

**Alternative: GCP Cloud Run**
- Cost: $182/month
- Good for: Very bursty traffic, minimal management

#### Medium (50 tenants, 5K queries/day)
**Winner: AWS Fargate + Savings Plan**
- Cost: $497/month → **$339/month** with plan
- Reasons:
  - Best discounts (50%)
  - Mature ecosystem
  - Good auto-scaling

**Alternative: Azure Container Apps**
- Cost: $532/month → $379/month with reservations
- Good for: Microsoft ecosystem integration, KEDA scaling

#### Large (200 tenants, 20K queries/day)
**Winner: AWS EKS + EC2 Reserved Instances**
- Cost: ~$800-1,000/month (vs $1,219 Fargate)
- Reasons:
  - Fixed VM pricing more economical at high utilization
  - Better control
  - Larger discount potential

**Alternative: Azure AKS + Reserved VMs**
- Cost: ~$900-1,100/month
- Good for: Multi-cloud strategy, Azure ecosystem

---

## Additional Cost Factors

### LLM API Costs
**Not included in estimates above**, but critical for AI reasoning system:

**Azure OpenAI (GPT-4o):**
- Input: $5/1M tokens
- Output: $20/1M tokens
- Same pricing as public OpenAI
- Committed use discounts available (up to 50%)

**Anthropic Claude (Sonnet):**
- Input: ~$3/1M tokens
- Output: ~$15/1M tokens
- Pricing varies by model tier

**Estimated LLM Costs:**
- Small (1K queries/day, avg 2K tokens/query): ~$120-180/month
- Medium (5K queries/day): ~$600-900/month
- Large (20K queries/day): ~$2,400-3,600/month

**⚠️ This can be your largest cost component!**

### Qdrant Cloud (Managed) Alternative
**Benefits:**
- No infrastructure management
- Multi-cloud (AWS/GCP/Azure)
- Auto-scaling, HA, backups included
- Free 1GB tier

**Pricing:**
- Custom quotes (not publicly listed)
- Breakeven analysis: ~60-80M queries/month
- Below this: Managed is often cheaper
- Above: Self-hosted wins

**When to Use:**
- Small-Medium deployments
- Want to avoid vector DB operations
- Multi-cloud/hybrid deployment

### True Total Cost of Ownership

**Small Deployment (Monthly):**
- Infrastructure: $171-242
- LLM APIs: $120-180
- Qdrant Managed (optional): ~$50-100
- **Total: $341-522/month**

**Medium Deployment (Monthly):**
- Infrastructure: $339-497 (with savings)
- LLM APIs: $600-900
- Qdrant Managed (optional): ~$150-250
- **Total: $1,089-1,647/month**

**Large Deployment (Monthly):**
- Infrastructure: $800-1,219
- LLM APIs: $2,400-3,600
- Qdrant Managed (optional): ~$400-600
- **Total: $3,600-5,419/month**

---

## Decision Matrix

### Choose GCP Cloud Run if:
- ✅ Highly variable/bursty traffic
- ✅ Want minimal infrastructure management
- ✅ Startup/rapid prototyping
- ✅ <500K requests/day
- ❌ Long-lived WebSocket connections (can get expensive)
- ❌ Need persistent storage for Qdrant

### Choose AWS Fargate if:
- ✅ Want balance of serverless + control
- ✅ AWS ecosystem preference
- ✅ Can commit to Savings Plan (50% discount)
- ✅ Need ALB features (sticky sessions)
- ✅ Best overall cost-performance ratio
- ❌ Not cost-effective vs EKS at very high scale

### Choose Azure Container Apps if:
- ✅ Microsoft/Azure ecosystem
- ✅ Want KEDA event-driven scaling
- ✅ Lowest egress costs
- ✅ Can commit to reservations
- ⚠️ Check SSE requirements (Front Door limitation)

### Choose Kubernetes (EKS/GKE/AKS) if:
- ✅ Large scale (>20K queries/day)
- ✅ High utilization (>60%)
- ✅ Need full control
- ✅ Multi-cloud strategy
- ✅ Complex networking requirements
- ❌ More operational overhead
- ❌ Higher learning curve

---

## Migration Path Recommendation

### Phase 1: MVP (Months 1-3)
- **Platform:** AWS Fargate + ALB
- **Database:** RDS PostgreSQL (db.t3.small, single-AZ)
- **Vector DB:** Qdrant Cloud (managed, free tier)
- **Cost:** ~$100-200/month + LLM costs
- **Why:** Fastest time-to-market, minimal ops

### Phase 2: Early Customers (Months 4-12)
- **Platform:** AWS Fargate + Savings Plan
- **Database:** RDS PostgreSQL (multi-AZ)
- **Vector DB:** Qdrant Cloud or self-hosted (decide at 10+ tenants)
- **Cost:** ~$300-500/month + LLM costs
- **Why:** Production-ready, cost-optimized

### Phase 3: Scale (Year 2+)
- **Platform:** AWS EKS + EC2 Reserved Instances
- **Database:** RDS with Reserved Instances
- **Vector DB:** Self-hosted on EKS (multi-AZ)
- **Cost:** ~$800-1,500/month + LLM costs
- **Why:** Most cost-effective at scale, full control

### Alternative Path (GCP-focused)
1. Start with Cloud Run + Cloud SQL + Qdrant Cloud
2. Move to GKE when hitting consistent 500K+ requests/day
3. Self-host Qdrant on GKE when >50 tenants

---

## Cost Optimization Checklist

### Immediate Actions
- [ ] Use commitment discounts (Savings Plans/Reserved/CUDs)
- [ ] Choose ARM/Graviton instances (20% cheaper)
- [ ] Use Application Load Balancer instead of API Gateway (35x cheaper)
- [ ] Enable auto-scaling with aggressive scale-to-zero
- [ ] Set appropriate connection timeouts

### Medium-Term
- [ ] Implement request caching (reduce LLM costs)
- [ ] Use CDN for static assets (reduce egress)
- [ ] Optimize LLM prompts (reduce token usage)
- [ ] Monitor and right-size database instances
- [ ] Consider regional deployment (reduce cross-region costs)

### Long-Term
- [ ] Migrate to Kubernetes at high scale
- [ ] Self-host Qdrant if >60M queries/month
- [ ] Implement multi-region for specific tenants only
- [ ] Consider hybrid cloud for data sovereignty
- [ ] Bulk LLM API commitments (50% discount)

---

## References

### GCP
- [Cloud Run Pricing](https://cloud.google.com/run/pricing)
- [Cloud Run Pricing Guide (2025)](https://cloudchipr.com/blog/cloud-run-pricing)
- [Cloud SQL PostgreSQL Pricing](https://cloud.google.com/sql/docs/postgres/pricing)
- [GCP Network Pricing](https://cloud.google.com/vpc/network-pricing)
- [Using WebSockets on Cloud Run](https://docs.cloud.google.com/run/docs/triggering/websockets)
- [Building a High-Scale Chat Server on Cloud Run](https://ahmet.im/blog/cloud-run-chat-server/)
- [Deploy Qdrant on GKE](https://docs.cloud.google.com/kubernetes-engine/docs/tutorials/deploy-qdrant)

### AWS
- [AWS Fargate Pricing](https://aws.amazon.com/fargate/pricing/)
- [Fargate Pricing Calculator](https://cloudburn.io/tools/aws-fargate-pricing-calculator)
- [RDS PostgreSQL Pricing](https://aws.amazon.com/rds/postgresql/pricing/)
- [AWS RDS Pricing Guide](https://cloudchipr.com/blog/rds-pricing)
- [API Gateway vs ALB Pricing](https://tinystacks.hashnode.dev/aws-application-load-balancer-alb-vs-api-gateway-pricing)
- [Scalable WebSockets on AWS](https://codezup.com/scalable-websockets-aws-load-balancing/)
- [ECS Service Auto Scaling on Fargate](https://repost.aws/knowledge-center/ecs-fargate-service-auto-scaling)

### Azure
- [Azure Container Apps Pricing](https://azure.microsoft.com/en-us/pricing/details/container-apps/)
- [Azure Database for PostgreSQL Pricing](https://azure.microsoft.com/en-us/pricing/details/postgresql/flexible-server/)
- [Azure Bandwidth Pricing](https://azure.microsoft.com/en-us/pricing/details/bandwidth/)
- [Scaling in Azure Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/scale-app)
- [ACA Auto Scaling with KEDA](https://azure.github.io/aca-dotnet-workshop/aca/09-aca-autoscale-keda/)

### Multi-Platform Comparisons
- [Comparing Prices: AWS Fargate vs Azure Container Apps vs Google Cloud Run](https://sliplane.io/blog/comparing-prices-aws-fargate-vs-azure-container-apps-vs-google-cloud-run)
- [AWS vs Azure vs Google Cloud 2026](https://northflank.com/blog/aws-vs-azure-vs-google-cloud)
- [Serverless Containers Comparison](https://quabyt.com/blog/serverless-containers-platforms)

### Qdrant
- [Qdrant Cloud Pricing](https://qdrant.tech/pricing/)
- [Qdrant Cloud Billing & Payments](https://qdrant.tech/documentation/cloud-pricing-payments/)
- [When Self-Hosting Vector Databases Becomes Cheaper](https://openmetal.io/resources/blog/when-self-hosting-vector-databases-becomes-cheaper-than-saas/)
- [Deploy Qdrant on Cloud Run](https://milumon.medium.com/deploy-a-qdrant-vector-db-on-cloud-run-in-5-minutes-and-use-it-inside-kilo-code-f2117f093256)

### LLM API
- [LLM API Pricing 2026 Comparison](https://www.cloudidr.com/llm-pricing)
- [LLM Cost Calculator](https://www.helicone.ai/llm-cost)
- [Anthropic API Pricing Guide 2026](https://www.nops.io/blog/anthropic-api-pricing/)

### Multi-Tenant SaaS
- [Multi-Tenant Deployment 2026 Guide](https://qrvey.com/blog/multi-tenant-deployment/)
- [Building Multi-Tenant SaaS on AWS](https://www.clickittech.com/software-development/multi-tenant-architecture/)
- [Let's Architect! Building Multi-Tenant SaaS Systems](https://aws.amazon.com/blogs/architecture/lets-architect-building-multi-tenant-saas-systems/)

---

**Document Version:** 1.0
**Last Updated:** 2026-02-13
**Research Date:** 2026-02-13
**Note:** Pricing and features subject to change. Always verify current pricing with official provider documentation before making deployment decisions.
