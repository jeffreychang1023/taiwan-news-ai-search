# Crawler Best Practice Review — Handoff Document

> 2026-02-11 session 調查成果。新 session 請以此為起點，全面 review crawler 架構與各 source 的正確性。

---

## 本次調查背景

用戶發現 full scan 進度極慢、各 source 月產量數字與 spec 不符。我們進行了獨立外部驗證（HTTP probe + ID→日期映射 + DB 交叉分析），修正了多個錯誤假設。

---

## 各 Source 調查結論

### CNA（中央社）— 邏輯正確，速度待觀察

| 項目 | 值 |
|------|-----|
| 實際月產量 | **~9,300 篇**（~307/天），spec 的 9,500 接近正確 |
| ID 格式 | YYYYMMDDXXXX（12 位），suffix 1-399 有文章 |
| Full scan watermark | 2024-01-19（才掃完 19 天） |
| 覆蓋率 | 舊爬蟲（task_id=None）只抓 suffix 0-99（88/天），full scan 補 100-399（218/天） |
| DATE_SCAN_MISS_LIMIT=80 | **不是問題**（文章密度足夠，不會提前截斷） |
| max_candidate_urls | 0（正確，CNA 任何 category 都能 resolve） |

**驗證方法**：`GROUP BY task_id` 拆分舊爬蟲 vs full scan 的 suffix 分布，發現舊爬蟲 98.9% 集中在 suffix 0-99。Full scan Jan 1-7 每天 178-354 篇（old+fullscan combined）。

**注意**：外部 probe（aiohttp 打 600 suffix）會被 CNA rate limit，只有第一個日期能拿到結果。不要拿 probe 結果當 ground truth。

**待做**：無需修改邏輯，但可考慮提高 concurrent_limit（目前=4）加速。

---

### LTN（自由時報）— 兩個必修 bug

| 項目 | 值 |
|------|-----|
| 實際月產量 | **~27,000 篇**（33K IDs/月 × 80% hit rate） |
| ID 格式 | Sequential，目前最新 ~5,350,000 |
| Full scan watermark | 3,292,031（≈2021-04，遠低於目標 2024-01） |
| start_id 設定 | 3,000,000（≈2019-12）**← 太舊！用戶只要 2024-01+** |

**Bug 1：start_id 太舊**
- `FULL_SCAN_CONFIG["ltn"]["start_id"] = 3_000_000`（2019-12）
- 用戶目標：2024-01+，對應 ID ≈ **4,550,000**
- 目前在掃 150 萬個不需要的 pre-2024 ID
- **修正**：`start_id` 改為 4,550,000（或更精確的 2024-01 對應 ID）

**Bug 2：candidate URLs 完全浪費**
- `max_candidate_urls=3`，但 LTN server **會自動 redirect** 到正確 category/subdomain
- 測試確認：`news/life/5300000` → 302 → `health.ltn.com.tw/5300000`（HTTP 200）
- 404 就是文章不存在，candidate 不可能成功
- 3 個 candidate 造成 ~1.6x 請求放大
- **修正**：`max_candidate_urls` 改為 **0**

**ID→日期映射**（外部 probe 確認）：
```
ID 3,500,000 → 2021-04-14
ID 4,000,000 → 2022-07-21
ID 4,500,000 → 2023-11-24
ID 5,000,000 → 2025-04-02
ID 5,100,000 → 2025-07-08
ID 5,200,000 → 2025-10-03
ID 5,300,000 → 2026-01-05
```

**修正後預估**：800K IDs / 3,600 req/min = **~3.7 小時掃完全部 2024+ LTN**

---

### Chinatimes（中國時報）— category code 根本問題

| 項目 | 值 |
|------|-----|
| 實際月產量 | 未知（WAF 阻擋外部驗證），估計數千篇 |
| ID 格式 | YYYYMMDDXXXXXX（14 位，suffix_digits=6），max_suffix=3500 |
| Full scan watermark | 2024-02-18（只掃 50 天） |
| 已爬文章 | 247 篇 / 50 天 = **5 篇/天** |

**根本問題：category code 不對**

Chinatimes URL 必須包含正確 category code（**不像 CNA 可以任意 category resolve**）：
```
realtimenews/20240101000001-260402  ← 只有社會版才回 200
realtimenews/20240101000001-260407  ← 政治版的文章要用這個 code
```

`get_url()` 永遠用 `-260402`（社會版），candidate 只加了：
- `newspapers-260109`（文化）
- `opinion-262101`（社論）

**完全沒覆蓋的 category**：
- 260401 或 260407 — 政治
- 260405 — 生活
- 260404 — 國際
- 260408 — 科技
- 260410 — 娛樂
- 260412 — 體育

**結果**：246/247 篇都是社會版（260402），1 篇社論（262101）。其他版全部 miss。

**次要問題**：
- Cloudflare WAF 擋 6.5%（353 blocked），aiohttp probe 全部 403
- `DATE_SCAN_MISS_LIMIT=80` 在 Chinatimes 確實會過早截斷（密度 5/3500 = 0.14%）
- 即使修了 category，如果每天需要試 3500 suffix × 8 category = 28,000 請求/天，效能堪憂

**待做**：
1. 先調查 Chinatimes 的 URL routing 機制（是否有 redirect？是否有 category-agnostic URL？）
2. 確認 curl_cffi impersonation 是否正常（WAF bypass）
3. 根據調查結果決定方案：加 candidate categories / 改用 list_page 模式 / 其他

---

### UDN（聯合報）— 正常，無需處理

| 項目 | 值 |
|------|-----|
| 實際月產量 | **~28,000 篇**（65K IDs/月 × 43% hit rate） |
| Full scan watermark | 8,174,278（≈2024-08） |
| max_candidate_urls | 0（正確） |
| 狀態 | 兩方向掃描進行中，gap 自然合攏中 |

---

### einfo（環境資訊中心）— 待觀察

- 小站，~20-30 篇/月
- Full scan watermark: ID 233,125
- 目前 ~13 篇/月，可能有部分遺漏
- 低優先級

---

### ESG BusinessToday（今周刊 ESG）— 已完成

- ~100-150 篇/月，已掃到 2026-02-10
- 全部完成，不需處理

---

## 已更新的文件

- `docs/indexing-spec.md`：月產量數字已用外部驗證更新，新增「Backfill 目標範圍」和「外部驗證數據」段落
- `.claude/memory/lessons-learned.md`：新增 5 條 lesson（見下方）

---

## 關鍵 Lessons Learned（本 session）

1. **外部 HTTP probe 被 rate limit 會嚴重誤導**：CNA probe 只有第一個日期可靠，後續全被封。不要拿 probe 結果當 ground truth。
2. **爬蟲覆蓋率分析必須按 task_id 拆分**：`GROUP BY task_id` 看各批次貢獻，比對 suffix 分布。
3. **LTN 自動 redirect 使 candidate URLs 完全浪費**：LTN server 302 到正確 category，candidate 純浪費。
4. **Chinatimes URL 必須包含正確 category code**：跟 CNA 不同，Chinatimes 錯 category 直接 404。
5. **月產量驗證需三步交叉**：DB 分析 + ID→日期映射 + sitemap，單一方法都有盲點。

---

## 新 Session 的建議 Review 方向

### 必做（修 bug）
1. **LTN start_id**：改為 ~4,550,000（2024-01）
2. **LTN max_candidate_urls**：改為 0
3. **Chinatimes category 問題**：需要先調查 URL routing，再決定方案
4. 更新 `dashboard_api.py` 的 `FULL_SCAN_CONFIG` 對應的 `start_id` / `default_end_id`

### 應做（best practice review）
5. **所有 parser 的 URL routing 機制**：逐一測試每個 source 是否支援 redirect、是否需要正確 category
6. **max_candidate_urls 合理性**：每個 source 的 candidate 是否真的有用？
7. **DATE_SCAN_MISS_LIMIT 合理性**：對 date-based source 是否應該 source-specific？
8. **FULL_SCAN_CONFIG 的 start_id / default_end_id**：是否都對應 2024-01+？
9. **Full scan 速度**：各 source 的 concurrent_limit / delay_range 是否合理？

### 可選（進階）
10. **Coverage Tab**：spec 有設計但尚未完整實作，reference points 機制是否有效？
11. **Auto mode vs Full scan 策略**：同一 source 是否應同時跑？互斥設計是否最優？
12. **Zombie task 處理**：dashboard 重啟時的 auto-resume 是否可靠？

---

## 相關檔案快速索引

| 檔案 | 用途 |
|------|------|
| `code/python/crawler/core/engine.py` | 核心掃描邏輯（`_full_scan_date_based`, `_full_scan_sequential`, `_process_article`） |
| `code/python/crawler/core/settings.py` | 所有設定（FULL_SCAN_CONFIG, FULL_SCAN_OVERRIDES, DATE_SCAN_MISS_LIMIT） |
| `code/python/crawler/parsers/*.py` | 各 source parser（`get_url()`, `get_candidate_urls()`, `parse()`） |
| `code/python/indexing/dashboard_api.py` | Dashboard API（`FULL_SCAN_CONFIG` 另一份在這裡，要同步） |
| `code/python/crawler/core/crawled_registry.py` | SQLite registry（`scan_watermarks`, `crawled_articles`, `not_found_articles`） |
| `data/crawler/crawled_registry.db` | 實際資料庫 |
| `data/crawler/logs/` | 各 source 的爬蟲 log |
| `docs/indexing-spec.md` | Indexing 規格文件（已更新月產量） |
| `docs/crawler-dashboard-spec.md` | Dashboard 規格（Coverage Tab 設計） |
| `.claude/memory/lessons-learned.md` | 累積的 lessons |
