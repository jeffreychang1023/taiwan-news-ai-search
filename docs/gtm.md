# Go-to-Market Readiness Checklist

> **最後更新**：2026-03-24
> **用途**：追蹤上線前後必須完成的非功能性工作（系統、文件、資安、法務、營運）

---

## P0：上線 Blocker

| # | 類別 | 項目 | 現狀 | 需要做的 | 狀態 |
|---|------|------|------|----------|:----:|
| 0-1 | Data | 全量 Indexing | 33/475 TSV (224K articles) | 剩 442 TSV + pg_dump → VPS restore | 🔄 進行中 |
| 0-2 | Legal | 隱私權政策 | 不存在 | 台灣個資法第 8 條：蒐集個資前需告知。收 email + 使用行為（analytics），法律上必須有 | ❌ |
| 0-3 | Legal | 服務條款 | 不存在 | B2B 客戶預期有正式條款。定義使用範圍、責任限制、終止條件 | ❌ |
| 0-4 | Legal | 新聞著作權立場 | 未公開說明 | (1) 明確引用原文連結（已有 citation）(2) 對外說明「摘要分析 + 引導回原始報導」(3) 確認 robots.txt 合規 | ❌ |

---

## P1：上線後 30 天內

### Ops / 可靠性

| # | 項目 | 現狀 | 需要做的 | 狀態 |
|---|------|------|----------|:----:|
| 1-1 | Health Check Endpoint | 只有基本 200 | 深層健檢：測 PG 連線 + embedding service 可用性，供監控系統呼叫 | ❌ |
| 1-2 | Uptime 監控 | 無 | UptimeRobot 免費版或等價物，掛了要知道 | ❌ |
| 1-3 | PG 備份 | 無 | pg_dump cron → 異地儲存（S3/GCS/本地 rsync）。PG 掛了現在是全毀 | ❌ |
| 1-4 | 日誌管理 | console only | file-based log rotation（logrotate 或 Python RotatingFileHandler），理想 structured JSON logging | ❌ |
| 1-5 | 錯誤訊息優化 | "搜尋失敗" 太 vague | 前端顯示更具體的錯誤訊息（逾時/無結果/伺服器錯誤分開處理） | ❌ |

### Security

| # | 項目 | 現狀 | 需要做的 | 狀態 |
|---|------|------|----------|:----:|
| 1-6 | CSP Headers | 無 | `Content-Security-Policy` header 防 XSS，aiohttp middleware 加設定 | ❌ |
| 1-7 | security.txt | 無 | `/.well-known/security.txt` — 業界標準，讓白帽知道怎麼回報漏洞 | ❌ |
| 1-8 | Token Revocation (D4) | JWT 內含 org_id，revoke 有延遲 | 短期：確認 JWT expiry 足夠短。中期：PostgreSQL blacklist table | ❌ |
| 1-9 | login_attempts Cleanup (D5) | 無 cleanup 機制 | scheduled SQL DELETE，簡單但不做會持續膨脹 | ❌ |

### Product

| # | 項目 | 現狀 | 需要做的 | 狀態 |
|---|------|------|----------|:----:|
| 1-10 | 使用者文件 | 無 | 至少一頁「如何使用讀豹」+ FAQ。B2B 客戶需要 onboarding guide | ❌ |
| 1-11 | 空結果 Session UX | 點不進去 | 空結果 session 可點擊並顯示「此搜尋無結果」或 retry 建議 | ❌ |

---

## P2：上線後 60 天內

### Ops / 品質

| # | 項目 | 說明 | 狀態 |
|---|------|------|:----:|
| 2-1 | Error Tracking | Sentry 或等價物。客戶報問題時需快速定位，不能只翻 server log | ❌ |
| 2-2 | Load Testing | 沒壓測過。需要知道同時 N 人搜尋的上限，LLM API 是瓶頸 | ❌ |
| 2-3 | Structured Logging | JSON format + correlation ID，方便跨 request 追蹤問題 | ❌ |

### Security

| # | 項目 | 說明 | 狀態 |
|---|------|------|:----:|
| 2-4 | Penetration Test | Guardrails Phase 1+2 到位但無第三方驗證。至少 OWASP ZAP 掃一遍 | ❌ |
| 2-5 | Rate Limit 調校 | 目前值是 code review 設定的，需根據真實流量 pattern 調整 | ❌ |
| 2-6 | Dependency Audit | pip audit / safety check，確認無已知 CVE 的套件 | ❌ |

### Business

| # | 項目 | 說明 | 狀態 |
|---|------|------|:----:|
| 2-7 | 定價模型 | B2B 但沒定價。客戶問「多少錢」要能答 | ❌ |
| 2-8 | SLA 定義 | B2B 客戶預期有 uptime 承諾。不用 99.99%，但至少要有數字和補償條款 | ❌ |
| 2-9 | Feedback 機制 | 使用者怎麼回報問題？至少一個表單或 email channel | ❌ |
| 2-10 | 客戶支援流程 | B2B 需要：誰收問題、回覆 SLA、升級路徑 | ❌ |

---

## P3：中期完善

| # | 項目 | 說明 | 狀態 |
|---|------|------|:----:|
| 3-1 | Disaster Recovery Plan | VPS 掛了 / PG 掛了 / LLM API 掛了的應對方案，至少寫成文件 | ❌ |
| 3-2 | Horizontal Scaling 方案 | 目前 single VPS，流量成長後怎麼 scale（read replica / load balancer / worker 拆分） | ❌ |
| 3-3 | Private Documents 遷移 PG | 目前 broken（Qdrant 依賴），status.md 已記錄 | ❌ |
| 3-4 | PDPA 合規完整評估 | 台灣個資法完整檢視 — B2B 大客戶可能要求合規證明 | ❌ |
| 3-5 | 自動化 XGBoost 重訓練 | 上線後才有真實數據，建立 pipeline 定期重訓 | ❌ |
| 3-6 | A/B 測試基礎設施 | Reasoning vs 標準搜尋 feature flag + query routing | ❌ |

---

## 建議執行順序

```
現在        → 0-1 Indexing 跑完（已在進行）
上線前      → 0-2~0-4 法律文件（文字工作，不用寫 code）
上線前      → 1-6, 1-7 CSP + security.txt（各 < 1hr）
上線前      → 1-1 Health check endpoint（< 2hr）
上線第一週  → 1-3, 1-4 PG 備份 + log rotation
上線第一週  → 1-2 UptimeRobot
上線第二週  → 1-10 使用者文件 + 1-5, 1-11 UX 修復
上線一個月  → 2-4 OWASP ZAP + 2-2 Load test + 2-7 定價
```

---

## 參考

- 系統狀態：`docs/status.md`
- 決策日誌：`docs/decisions.md`
- Guardrails Spec：`docs/specs/guardrail-spec.md`
- Login Spec：`docs/specs/login-spec.md`（Known Gaps 段落）
- Analytics Spec：`docs/specs/analytics-spec.md`
