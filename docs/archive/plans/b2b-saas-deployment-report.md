# NLWeb B2B SaaS 雲端部署研究報告

> 研究日期：2026-02-13

---

## Executive Summary

**現狀**：NLWeb 是單租戶系統，SaaS 就緒度約 15/100。核心搜尋/推論引擎完整，但缺乏多租戶隔離、認證授權、計量計費等 SaaS 必要基礎設施。

**建議方案**：AWS Fargate + ALB 為主要平台，Qdrant payload-based 多租戶，WorkOS 認證，Stripe 計費。

**預估月費**：

| 規模 | 基礎設施 | LLM API | 總計 |
|------|---------|---------|------|
| 小（10 租戶，1K queries/day） | $70-140 | $630-900 | ~$800-1,000 |
| 中（50 租戶，5K queries/day） | $340-500 | $3,150-4,500 | ~$3,500-5,000 |
| 大（200 租戶，20K queries/day） | $680-1,200 | $12,600-18,000 | ~$13,000-19,000 |

**關鍵洞察**：LLM API 成本佔總 TCO 的 85-97%，基礎設施成本相對次要。成本優化的重點在 LLM caching 和 model 選擇，而非雲端基礎設施。

---

## 1. 多租戶架構

### 現狀分析

目前系統有以下單租戶假設：

| 元件 | 問題 | 嚴重度 |
|------|------|--------|
| **Qdrant** | 單一 collection `nlweb_collection`，無 tenant_id | CRITICAL |
| **State** | In-memory dict，無租戶隔離，無法水平擴展 | CRITICAL |
| **Config** | 全域 singleton `CONFIG`，無 per-tenant 設定 | HIGH |
| **Auth** | JWT 無 tenant_id，`/ask` endpoint 公開存取 | HIGH |
| **Analytics** | 單一 DB，查詢日誌無租戶標記 | MEDIUM |
| **LLM Client** | Singleton client，全域 API key | MEDIUM |
| **Cache** | 共用 conversation cache，無命名空間隔離 | MEDIUM |

### 方案比較

| 方案 | 隔離程度 | 複雜度 | 成本 | 建議 |
|------|---------|--------|------|------|
| **A: Shared collection + payload filter** | 邏輯隔離 | 低 | 最低 | **Phase 1 推薦** |
| B: Collection-per-tenant | 物理隔離 | 中 | 中 | Qdrant 官方不推薦（上限 1000 collections） |
| C: Cluster-per-tenant | 完全隔離 | 高 | 最高 | 企業客戶特殊需求 |

### 建議方案：Payload-based 多租戶

```python
# Qdrant 設定（利用 is_tenant=True 優化）
await client.create_payload_index(
    collection_name="nlweb",
    field_name="tenant_id",
    field_schema="keyword",
    is_tenant=True  # 關鍵：co-locate 同租戶向量，提升查詢效率
)

# 查詢時注入 tenant filter
results = await client.search(
    collection_name="nlweb",
    query_vector=vector,
    query_filter=Filter(must=[
        FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id))
    ])
)
```

**為什麼不用 collection-per-tenant？**
- Qdrant Cloud 每 cluster 上限 1000 collections
- 每個 collection 有固定 overhead（~100MB+）
- Qdrant 官方文件明確建議使用 payload-based + `is_tenant=True`
- Payload-based 在 10,000+ 租戶規模下仍然高效

**擴展路徑**：
- Phase 1（10-50 租戶）：Payload-based，單一 collection
- Phase 2（50-200 租戶）：Tiered multi-tenancy（Qdrant v1.16+），大租戶自動升級到獨立 shard
- Phase 3（200+ 租戶）：Multi-node cluster + dedicated shards for enterprise tenants

### 需要改動的核心元件

1. **所有 DB 查詢**：加入 `WHERE tenant_id = ?`
2. **Conversation State**：從 in-memory dict 遷移到 Redis，加入 tenant_id namespace
3. **Config 系統**：建立 TenantConfig service，per-tenant 控制可搜尋來源/LLM model/rate limit
4. **Request Context**：middleware 層注入 `request['tenant_id']`，向下傳遞到所有 handler

---

## 2. 認證與授權

### 現狀分析

- 已有 OAuth 基礎（Google/GitHub login）
- JWT token 存在但**不含 tenant_id**
- 無 RBAC（只分 authenticated / unauthenticated）
- `/ask` endpoint 公開存取，無租戶驗證
- 測試 token（`e2e_`）直接 bypass 認證

### 方案比較

| 方案 | B2B 適合度 | 價格 | SSO | 特點 |
|------|-----------|------|-----|------|
| **WorkOS** | ★★★★★ | Free（1M MAU）→ $125/SSO | SAML+OIDC | **B2B 專用，推薦** |
| Auth0 | ★★★★ | ~$0.05/MAU | ✅ | 功能全面，較貴 |
| Clerk | ★★★ | $0.05/MAU | ✅ | UX 最佳，B2C 導向 |
| Supabase Auth | ★★★ | $25/月 | 有限 | 預算方案 |
| 自建 | ★★ | 開發成本高 | 需自建 | 不推薦 |

### 建議方案

**Phase 1（MVP）**：WorkOS Free Tier + API Key

```
認證流程：
1. 租戶 Admin 在管理介面建立 API Key
2. API Key → POST /api/auth/token → 取得 JWT（含 tenant_id, roles）
3. 後續請求帶 JWT（Authorization: Bearer xxx）
4. Middleware 驗證 JWT + 注入 tenant context
```

**Phase 2（Enterprise）**：加入 SAML SSO
- WorkOS SAML 整合：$125/SSO connection
- 72% 中大型企業要求 SSO
- Just-in-Time provisioning（首次 SSO 登入自動建立帳號）

### RBAC 設計

| 角色 | 權限 |
|------|------|
| **tenant_admin** | 管理用戶、API Key、設定、查看用量 |
| **developer** | 使用 API、查看分析 |
| **viewer** | 只能在 Web UI 搜尋 |

### 預估成本

| 階段 | Auth 月費 | SSO 費用 |
|------|----------|---------|
| MVP（0-50 租戶） | $0 | - |
| Growth（50-200 租戶） | $0 | $625（5 個 SSO 客戶） |
| Enterprise（200+ 租戶） | $0-150 | $2,500（20 個 SSO 客戶） |

---

## 3. 雲端基礎設施

### 平台比較總覽

| 項目 | GCP | AWS | Azure |
|------|-----|-----|-------|
| **容器服務** | Cloud Run | ECS Fargate | Container Apps |
| **Kubernetes** | GKE（免費 control plane） | EKS（$73/月） | AKS（免費首個 cluster） |
| **託管 PostgreSQL** | Cloud SQL | RDS | Azure DB for PostgreSQL |
| **vCPU 月費（1vCPU）** | $63 | $30-41 | $37 |
| **DB 小實例月費** | $25 | $30 | $25 |
| **負載均衡器月費** | 內建免費 | $22（ALB） | $528+（App Gateway v2） |
| **網路流出/GB** | $0.12 | $0.09 | $0.02 |
| **免費流出配額** | 1GB | 100GB | 100GB |
| **WebSocket 支援** | 60min 硬限制 | ALB sticky session ✅ | KEDA 原生 ✅ |
| **SSE 支援** | ✅ | ✅ | ✅ |
| **承諾折扣** | 17-30%（CUD） | 50%（Savings Plan） | 40-60%（Reserved） |

### 依規模的最佳選擇

#### 小規模（10 租戶，~1K queries/day）

| 方案 | 月費（基線） | 月費（承諾） |
|------|------------|------------|
| GCP Cloud Run | $110 | $91 |
| **AWS Fargate + ALB** | $139 | **$70** |
| Azure Container Apps | $113 | $68 |

**推薦**：AWS Fargate — Savings Plan 折扣最大（50%），操作最簡單

#### 中規模（50 租戶，~5K queries/day）

| 方案 | 月費（基線） | 月費（承諾） |
|------|------------|------------|
| GCP Cloud Run | $557 | $462 |
| **AWS Fargate + ALB** | $497 | **$339** |
| Azure Container Apps | $482 | $289 |

**推薦**：AWS Fargate + Savings Plan 或 Azure（承諾價更低但 App Gateway 很貴）

#### 大規模（200 租戶，~20K queries/day）

| 方案 | 月費（基線） | 月費（承諾） |
|------|------------|------------|
| GCP GKE | $1,089 | $763 |
| AWS EKS | $1,088 | $683 |
| **Azure AKS** | $649 | **$389** |

**推薦**：Azure AKS — 3 年 Reserved Instance 折扣 60%，最划算

### 建議方案

**Phase 1-2（MVP → 50 租戶）**：AWS Fargate + ALB
- 理由：最低進入門檻、Savings Plan 50% 折扣、無需 K8s 經驗、ALB 原生支援 WebSocket/SSE
- 升級路徑清晰：Fargate → EKS

**Phase 3（50-200+ 租戶）**：評估遷移到 EKS 或 Azure AKS
- 若團隊有 K8s 經驗 → Azure AKS（成本最低）
- 若留在 AWS 生態 → EKS + Spot Instance

### Qdrant 部署

| 階段 | 方案 | 月費 |
|------|------|------|
| MVP | Qdrant Cloud Free Tier（1GB） | $0 |
| Growth | Qdrant Cloud 或 自建於 K8s | $100-200 |
| Scale | 自建於 K8s（3-node HA） | $150-300 |

### LLM API 成本（TCO 主要組成）

| 規模 | Azure OpenAI (GPT-4o) | Anthropic Claude Sonnet | Claude Haiku |
|------|----------------------|------------------------|--------------|
| 1K queries/day | $900/月 | $630/月 | ~$150/月 |
| 5K queries/day | $4,500/月 | $3,150/月 | ~$750/月 |
| 20K queries/day | $18,000/月 | $12,600/月 | ~$3,000/月 |

**成本優化策略**：
1. **LLM Caching**：相同查詢快取結果，預估減少 50-70% token
2. **Model Tiering**：簡單查詢用 Haiku/Flash，複雜查詢才用 Sonnet/GPT-4o
3. **Prompt 優化**：減少 input token 數
4. **Azure OpenAI Batch API**：非即時查詢享 50% 折扣
5. **Bulk Commitment**：年承諾量可談 30-50% 折扣

---

## 4. API Gateway & 計量

### 現狀分析

- 無 rate limiting
- 無 API key 管理（YAML 靜態設定）
- 無用量追蹤
- 無配額管理

### 建議方案（漸進式）

| 階段 | 方案 | 月費 |
|------|------|------|
| Phase 1 | aiolimiter（in-memory） | $0 |
| Phase 2 | Redis-backed rate limiting | $15-50 |
| Phase 3 | Kong OSS（500+ 租戶） | $200+ |

### Rate Limiting 設計

| Plan Tier | requests/min | queries/day | Deep Research/day |
|-----------|-------------|-------------|-------------------|
| Starter | 60 | 500 | 20 |
| Professional | 300 | 2,500 | 100 |
| Enterprise | 1,000+ | 10,000+ | unlimited |

### 計量與計費

**建議**：Stripe Billing + Usage Metering

```
計量維度：
1. api_query — 每次搜尋查詢
2. llm_tokens — LLM token 消耗量（可轉嫁成本）
3. deep_research — Deep Research 使用次數（高價值操作）
```

**Stripe 整合架構**：

```
Request → aiohttp middleware → 記錄用量 → Stripe Meter API
                                           ↓
                              月底自動計算帳單 → Invoice
```

**定價範例**：

| Plan | 月費 | 包含 | 超額 |
|------|------|------|------|
| Starter | $99 | 500 queries/day, 100K tokens | $0.02/query |
| Professional | $299 | 2,500 queries/day, 500K tokens | $0.015/query |
| Enterprise | Custom | Unlimited | 量身定制 |

### 預估成本

| 項目 | 月費 |
|------|------|
| Stripe 平台費 | 營收的 0.5-1% |
| Redis（計量/Rate limiting） | $15-50 |
| 合計 | $15-50 + 營收抽成 |

---

## 5. 安全與合規

### 需要實作的安全功能

| 功能 | 優先級 | 說明 |
|------|--------|------|
| **租戶資料隔離** | P0 | 每個 DB 查詢必須包含 tenant_id filter |
| **傳輸加密** | P0 | HTTPS everywhere（ALB/Cloud Run 自動處理） |
| **靜態加密** | P1 | RDS/Qdrant 開啟 encryption at rest |
| **API Key 管理** | P1 | 支援建立、撤銷、輪替 |
| **Audit Log** | P1 | 記錄誰在何時存取了什麼 |
| **RBAC** | P1 | 角色權限控制 |
| **移除測試 token** | P1 | 生產環境禁止 `e2e_` token bypass |
| **GDPR 資料刪除** | P2 | 租戶退租時完整刪除所有資料 |
| **SOC2 合規** | P3 | 企業客戶可能要求 |

### 資料隔離最佳實踐

```
1. Middleware 層：從 JWT 提取 tenant_id，注入 request context
2. Repository 層：所有查詢自動加入 tenant_id filter
3. 測試：寫 integration test 驗證跨租戶查詢回傳 0 筆
4. Code Review：所有 DB 查詢必須經過 tenant isolation 檢查
```

### Secret 管理

| 環境 | 方案 |
|------|------|
| 開發 | .env 檔案（gitignore） |
| Production | AWS Secrets Manager / Azure Key Vault |
| API Keys | 儲存在 DB（hashed），不存 YAML |

---

## 6. DevOps & 可觀測性

### CI/CD Pipeline

```
GitHub Push → GitHub Actions → Build Docker Image → Push to ECR/GCR
                                                        ↓
                                              Run Tests → Deploy to Staging
                                                        ↓
                                              Manual Approval → Deploy to Production
```

### 部署策略

| 策略 | 適用場景 |
|------|---------|
| **Rolling Update**（推薦 Phase 1） | Fargate 預設，零停機 |
| Blue/Green | 需要快速 rollback |
| Canary | 大流量、需要漸進式驗證 |

### 監控（三大支柱）

| 支柱 | 工具 | 用途 |
|------|------|------|
| **Metrics** | CloudWatch / Prometheus + Grafana | CPU、記憶體、request latency、error rate |
| **Logs** | CloudWatch Logs / ELK | 結構化日誌、per-tenant 查詢 |
| **Traces** | AWS X-Ray / OpenTelemetry | 請求追蹤、瓶頸分析 |

### Per-Tenant 監控

```
關鍵指標：
- 每租戶 QPS
- 每租戶 error rate
- 每租戶 LLM token 消耗
- 每租戶 latency p50/p95/p99
- 配額使用率（%）
```

### Auto-Scaling

| 方案 | 觸發指標 | 回應時間 |
|------|---------|---------|
| AWS Fargate Auto Scaling | CPU > 70%, request count | 1-2 分鐘 |
| Azure KEDA | HTTP request rate, custom metrics | 30-60 秒 |
| K8s HPA | CPU/Memory + custom metrics | 15-30 秒 |

---

## 架構總覽圖

### 目標架構（Phase 2 完成後）

```
                    ┌─────────────────────────────────┐
                    │          DNS / CDN              │
                    └──────────────┬──────────────────┘
                                   │
                    ┌──────────────▼──────────────────┐
                    │     AWS ALB (Load Balancer)      │
                    │   TLS termination, sticky session │
                    └──────────────┬──────────────────┘
                                   │
                    ┌──────────────▼──────────────────┐
                    │       Auth Middleware            │
                    │  JWT verify → tenant_id inject   │
                    │  Rate limiting (Redis-backed)    │
                    │  Usage metering → Stripe         │
                    └──────────────┬──────────────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          │                        │                        │
┌─────────▼─────────┐  ┌─────────▼──────────┐  ┌─────────▼─────────┐
│   Search API      │  │  Deep Research API  │  │   Chat API        │
│  (Fargate Task)   │  │  (Fargate Task)     │  │  (Fargate Task)   │
│  Auto-scaling     │  │  Auto-scaling       │  │  WebSocket/SSE    │
└─────────┬─────────┘  └─────────┬──────────┘  └─────────┬─────────┘
          │                        │                        │
          └────────────────────────┼────────────────────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          │                        │                        │
┌─────────▼─────────┐  ┌─────────▼──────────┐  ┌─────────▼─────────┐
│   Qdrant          │  │  PostgreSQL (RDS)   │  │  Redis            │
│ (payload-based    │  │  tenant_users       │  │  sessions         │
│  multi-tenancy)   │  │  analytics          │  │  rate_limits      │
│                   │  │  conversations      │  │  cache            │
└───────────────────┘  └────────────────────┘  └───────────────────┘
          │
          │  query filter: tenant_id = ?
          │
┌─────────▼─────────┐
│   LLM API         │
│  (per-tenant      │
│   routing &       │
│   metering)       │
└───────────────────┘
```

---

## 遷移路線圖

### Phase 1: 最小可行 SaaS（Minimum Viable SaaS）

**目標**：讓第一批客戶能用

| 項目 | 內容 |
|------|------|
| **認證** | API Key 發放 + JWT（含 tenant_id） |
| **資料隔離** | Qdrant payload filter + DB 加 tenant_id 欄位 |
| **部署** | AWS Fargate + ALB + RDS（單 AZ） |
| **Rate Limiting** | aiolimiter in-memory（100 req/min per tenant） |
| **計量** | 基本 query count logging |
| **監控** | CloudWatch 基礎監控 |
| **預估月費** | ~$70-140（基礎設施）+ LLM 費用 |

### Phase 2: 商業化功能

**目標**：可規模化銷售

| 項目 | 內容 |
|------|------|
| **認證** | WorkOS 整合 + RBAC（admin/developer/viewer） |
| **計費** | Stripe Billing + usage metering |
| **Rate Limiting** | Redis-backed，per-plan tier 限制 |
| **RDS** | 升級到 Multi-AZ |
| **Tenant Admin** | 租戶管理 dashboard（用戶管理、API Key、用量查看） |
| **Audit Log** | 記錄所有 API 存取 |
| **LLM 優化** | Caching layer + model tiering |
| **預估月費** | ~$340-500（基礎設施）+ LLM 費用 |

### Phase 3: 企業級功能

**目標**：服務大型企業客戶

| 項目 | 內容 |
|------|------|
| **SSO** | SAML/OIDC via WorkOS（$125/connection） |
| **合規** | GDPR 資料刪除流程、SOC2 準備 |
| **SLA** | 99.9% uptime guarantee |
| **Multi-region** | 高價值客戶部署到就近區域 |
| **K8s 遷移** | 評估 EKS 或 Azure AKS（大規模更划算） |
| **進階安全** | WAF、DDoS protection、IP allowlist |
| **預估月費** | ~$680-1,200（基礎設施）+ LLM 費用 |

---

## 成本估算

### 按租戶數量分級

#### 10 租戶

| 項目 | 月費 |
|------|------|
| AWS Fargate (2 tasks, Savings Plan) | $35 |
| RDS PostgreSQL (t3.small, single-AZ) | $31 |
| Qdrant Cloud (free tier) | $0 |
| ALB | $22 |
| Redis (ElastiCache t3.micro) | $13 |
| Auth (WorkOS free) | $0 |
| **基礎設施小計** | **~$101** |
| LLM API (Anthropic, 1K queries/day) | ~$630 |
| **總計** | **~$731/月** |

#### 50 租戶

| 項目 | 月費 |
|------|------|
| AWS Fargate (3-5 tasks, Savings Plan) | $120 |
| RDS PostgreSQL (m6g.large, multi-AZ) | $132 |
| Qdrant Cloud or self-hosted | $100 |
| ALB | $25 |
| Redis (ElastiCache) | $30 |
| Auth (WorkOS free) | $0 |
| Stripe 平台費 | ~$50 |
| **基礎設施小計** | **~$457** |
| LLM API (Anthropic, 5K queries/day) | ~$3,150 |
| LLM Caching 優化 (-40%) | -$1,260 |
| **總計** | **~$2,347/月** |

#### 200 租戶

| 項目 | 月費 |
|------|------|
| AWS EKS or Azure AKS (承諾價) | $400-680 |
| RDS/Azure PostgreSQL (HA, Reserved) | $145-264 |
| Qdrant self-hosted (3-node) | $150-300 |
| ALB / Load Balancer | $25-35 |
| Redis | $50-100 |
| Auth (WorkOS) | $0-150 |
| SSO (20 connections) | $2,500 |
| Stripe 平台費 | ~$200 |
| **基礎設施小計** | **~$3,470-4,229** |
| LLM API (20K queries/day, optimized) | ~$6,300-9,000 |
| **總計** | **~$9,770-13,229/月** |

---

## 風險與待決事項

### 技術風險

| 風險 | 影響 | 緩解 |
|------|------|------|
| 多租戶改造範圍大 | 全 codebase 改動 | 漸進式重構，從 middleware + DB layer 開始 |
| In-memory state 遷移 | Conversation 功能暫時中斷 | Redis migration 需完整測試 |
| LLM 成本失控 | 單一租戶大量使用可能虧損 | Rate limiting + 用量配額 + 成本告警 |
| Qdrant 效能在大量租戶下的表現 | 查詢延遲增加 | 使用 `is_tenant=True` + 監控 p99 latency |

### 待決事項

| 項目 | 需決定 |
|------|--------|
| **定價模型** | 按 query？按 seat？按 token？混合？ |
| **SLA 承諾** | 99.9%？99.95%？影響架構複雜度 |
| **資料保留政策** | 租戶退租後保留多久？影響 GDPR 合規 |
| **Multi-region** | 是否需要？哪些區域？ |
| **Crawler 資料共享** | 所有租戶共享同一資料庫？部分隔離？影響 Qdrant 架構 |
| **自有 LLM key** | 允許企業租戶自帶 LLM API key？ |
