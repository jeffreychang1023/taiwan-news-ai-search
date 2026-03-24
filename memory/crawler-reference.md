---
name: Crawler Source Reference
description: 各 source 的操作細節、Full Scan 設定、Dashboard 模式。Crawler 操作或除錯時必讀。
type: reference
---

# Crawler Source Reference

> 各 source 的操作細節。Crawler 相關工作時讀取此檔。

## ID Types
- **Sequential**: LTN, UDN, einfo (monotonic integers)
- **Date-based**: CNA, ESG_BT (YYYYMMDDXXXX, 12位), Chinatimes (YYYYMMDDXXXXXX, 14位)

## Source Quick Reference

| Source | Session | Hit Rate | 月產量 | 特殊注意 |
|--------|---------|----------|--------|----------|
| **LTN** | aiohttp | ~60% | 高 | 302 redirect `/life/{id}` 通吃。`max_candidate_urls=0`。health.ltn 有多個 `.text` div。 |
| **UDN** | aiohttp | 6% (full_scan) / 100% (sitemap) | 高 | IDs <7.8M dead。**用 sitemap backfill**。Sitemap: `udn.com/sitemapxml/news/mapindex.xml` |
| **CNA** | curl_cffi | varies | 中 | 12位 ID。`aall` 通用 category。Suffix max=5004。`max_suffix=6000`。無 Cloudflare。 |
| **Chinatimes** | curl_cffi | ~37% suffix密度 | ~26,776 | 14位 ID, suffix_digits=6。Top 40 categories 覆蓋 95.6%。`max_candidate_urls=39`。GCP concurrent=10。Sitemap 只到 2025 中。 |
| **ESG BT** | curl_cffi | 2.4% | ~35 | ID 與今周刊不共用。301→homepage = not found。`date_scan_miss_limit=150`。 |
| **einfo** | curl_cffi | ~87% (with proxy) | 中 | 站可能 down。需 proxy（IP ban）。先 curl 確認再啟動。 |
| **MOEA** | curl_cffi | ~40-60% | ~30-50 | Sequential ID, latest ~121891。Soft-404 handled by parser returning None。 |

## Full Scan Config
```python
FULL_SCAN_CONFIG = {
    "udn":  {"type": "sequential", "default_start_id": 7_800_000},
    "ltn":  {"type": "sequential", "default_start_id": 4_550_000},
    "einfo": {"type": "sequential", "default_start_id": 230_000},
    "cna":  {"type": "date_based", "max_suffix": 6000},
    "esg_businesstoday": {"type": "date_based", "max_suffix": 600, "date_scan_miss_limit": 150},
    "chinatimes": {"type": "date_based", "max_suffix": 6000, "suffix_digits": 6, "date_scan_miss_limit": 700},
    "moea": {"type": "sequential"},
}
```

## Dashboard Modes
`auto`, `list_page`, `full_scan`, `retry`, `retry_urls`, `sitemap`

## 補最新文章 — 正確 Mode 對照（2026-03-11 確立）

**操作 SOP 見 `/newest-scan` skill**

| Source | 補最新 Mode | API | 為什麼 |
|--------|-------------|-----|--------|
| LTN | `auto` | crawler/start | sequential，auto 從最新 ID 往回最高效 |
| UDN | `sitemap` | crawler/start | full_scan hit rate 僅 6%，sitemap 直接拿 URL |
| CNA | `full_scan` + 明確 start_date | fullscan/start | date-based，傳日期覆蓋 watermark |
| Chinatimes | `full_scan` + 明確 start_date | fullscan/start | 同上 |
| ESG BT | `full_scan` + 明確 start_date | fullscan/start | 同上 |
| einfo | `auto` | crawler/start | sequential，先確認站 up |
| MOEA | `auto` | crawler/start | sequential，量少 |

**GCP 注意事項**：
- **不依賴 GCP watermark** — 從桌機 registry 計算起點
- **GCP home**: `/home/User/nlweb/`（不是 `/home/mounai/`）
- **GCP RAM**: 1GB，不要同時跑太多 source
- **不在 Dashboard 運行時替換 DB** — singleton 快取
- **LTN/einfo watermark 已超出有效 ID** — 必須用 auto 模式

## Monitoring Rules
- **Dashboard entry**: `python -m indexing.dashboard_server` (port 8001)
- **讀 `stats.success`**，不讀 top-level `count`
- Date-based: `last_scanned_date` 不動 + not_found 增加 = 正常（掃該日 suffix）
- CNA high skip in 已爬日期 = 正常
- Chinatimes 前 ~59 suffix 是 404 = 正常
- einfo 確認站是否 up: `curl -s -o /dev/null -w "%{http_code}" --max-time 10 https://e-info.org.tw/`
- No resume API — 用 `POST /api/indexing/fullscan/start`，自動從 watermark 繼續

## Crawler 自動化（2026-03-11）

- **GCP Cron**: 每天 05:00 台灣時間跑 newest scan（6 sources，einfo 除外）
- **Watermark fix**: `engine.py:1333` `<=` → `<`，同日重掃安全
- **Registry 同步**: 桌機 gzip (204MB) → gcloud scp → GCP gunzip
  - 注意：gunzip 要用 nohup 背景執行，SSH session 會截斷大檔案解壓
- **GCP Dashboard venv**: `/home/User/nlweb/venv/bin/python`（非 system python）
