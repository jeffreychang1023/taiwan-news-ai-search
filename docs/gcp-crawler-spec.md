# GCP e2-micro Crawler 部署規格

## 概述

春節期間（~7-9 天）桌機關機，使用 GCP e2-micro 免費方案繼續跑 crawler。
桌機與 GCP 分割 ID 範圍，互不重疊，各自爬不同區段。

---

## 架構

```
桌機（平時）                    GCP e2-micro（春節）
├─ LTN: 4.55M → 7M             ├─ LTN: 7M → 9.5M
├─ CNA: 2024-01 → 2024-12      ├─ CNA: 2025-06 → 2026-02
├─ UDN: 7.8M → 8.2M            ├─ UDN: 8.8M → 9.4M
├─ Chinatimes, ESG BT, einfo   └─ MOEA: 121.3K → 121.9K
└─ MOEA: 110K → 121.3K
                                    ↓ 春節結束
                                scp articles/ + registry.db
                                    ↓
                                merge_registry.py → 桌機
                                    ↓
                                桌機跑 indexing pipeline → Qdrant
```

---

## GCP VM 資訊

| 項目 | 值 |
|------|-----|
| Instance | `nlweb-crawler` |
| Zone | `asia-east1-b` |
| Type | `e2-micro`（免費方案，shared vCPU, 1GB RAM） |
| OS | Debian 12 (bookworm) |
| Disk | 30GB pd-standard |
| Swap | 2GB |
| Python | 3.11 + venv |
| External IP | 動態分配（每次查 `gcloud compute instances list`） |
| GCP Project | `project-ad6eda6e-acac-4f93-97d` |

---

## 記憶體預估

```
Python runtime + modules:  ~60 MB
Crawler (1 source):        ~150 MB
Dashboard server:          ~100 MB
OS + buffer/cache:         ~300 MB
Swap (保險):               2048 MB
────────────────────────────────
合計:                      ~610 MB / 1 GB ✅
```

**重要**：一次只跑一個 source，避免 OOM。

---

## 環境設定

GCP 上透過 `CRAWLER_ENV=gcp` 自動降低併發：

```python
# settings.py 環境感知覆蓋
if CRAWLER_ENV == "gcp":
    concurrent_limit = min(原值, 5)
    delay_range 最小 (0.3, 0.8)
```

Dashboard 啟動時需設定：
```bash
CRAWLER_ENV=gcp python -m indexing.dashboard_server
```

---

## 常用指令

### gcloud 路徑（Windows Git Bash）

```bash
GCLOUD="/c/Program Files (x86)/Google/Cloud SDK/google-cloud-sdk/bin/gcloud"
```

### SSH 連線

```bash
"$GCLOUD" compute ssh nlweb-crawler --zone=asia-east1-b
```

### 開 Dashboard Tunnel

```bash
"$GCLOUD" compute ssh nlweb-crawler --zone=asia-east1-b --ssh-flag="-L 8002:localhost:8001"
# 瀏覽器開 http://localhost:8002（本機 8001 是桌機 Dashboard）
```

### 查看 crawler 狀態

```bash
"$GCLOUD" compute ssh nlweb-crawler --zone=asia-east1-b --command='curl -s http://localhost:8001/api/indexing/fullscan/status'
```

### 啟動 Full Scan

```bash
# LTN（上半段，桌機爬下半段）
"$GCLOUD" compute ssh nlweb-crawler --zone=asia-east1-b \
  --command='curl -s -X POST http://localhost:8001/api/indexing/fullscan/start \
  -H "Content-Type: application/json" \
  -d "{\"sources\":[\"ltn\"],\"overrides\":{\"ltn\":{\"start_id\":7000000,\"end_id\":9500000}}}"'

# CNA（上半段）
"$GCLOUD" compute ssh nlweb-crawler --zone=asia-east1-b \
  --command='curl -s -X POST http://localhost:8001/api/indexing/fullscan/start \
  -H "Content-Type: application/json" \
  -d "{\"sources\":[\"cna\"],\"overrides\":{\"cna\":{\"start_date\":\"2025-06-01\"}}}"'

# UDN（上半段）
"$GCLOUD" compute ssh nlweb-crawler --zone=asia-east1-b \
  --command='curl -s -X POST http://localhost:8001/api/indexing/fullscan/start \
  -H "Content-Type: application/json" \
  -d "{\"sources\":[\"udn\"],\"overrides\":{\"udn\":{\"start_id\":8800000,\"end_id\":9400000}}}"'

# MOEA
"$GCLOUD" compute ssh nlweb-crawler --zone=asia-east1-b \
  --command='curl -s -X POST http://localhost:8001/api/indexing/fullscan/start \
  -H "Content-Type: application/json" \
  -d "{\"sources\":[\"moea\"],\"overrides\":{\"moea\":{\"start_id\":121300,\"end_id\":121900}}}"'
```

### 停止 Crawler

```bash
# 先查 task_id
"$GCLOUD" compute ssh nlweb-crawler --zone=asia-east1-b \
  --command='curl -s http://localhost:8001/api/indexing/fullscan/status'

# 用 task_id 停止
"$GCLOUD" compute ssh nlweb-crawler --zone=asia-east1-b \
  --command='curl -s -X POST http://localhost:8001/api/indexing/crawler/stop \
  -H "Content-Type: application/json" \
  -d "{\"task_id\":\"<TASK_ID>\"}"'
```

### 查看產出

```bash
# TSV 檔案列表
"$GCLOUD" compute ssh nlweb-crawler --zone=asia-east1-b \
  --command='ls -lh ~/nlweb/data/crawler/articles/'

# 記憶體使用
"$GCLOUD" compute ssh nlweb-crawler --zone=asia-east1-b \
  --command='free -m'

# Crawler process
"$GCLOUD" compute ssh nlweb-crawler --zone=asia-east1-b \
  --command='ps aux | grep python'
```

### Dashboard 異常時重啟

```bash
"$GCLOUD" compute ssh nlweb-crawler --zone=asia-east1-b \
  --command='pkill -f dashboard_server; sleep 2; cd ~/nlweb/code/python && source ~/nlweb/venv/bin/activate && CRAWLER_ENV=gcp python -m indexing.dashboard_server > ~/nlweb/data/crawler/logs/dashboard.log 2>&1 &'
```

---

## 分割範圍

### 桌機 Watermark（2026-02-12 快照）

| Source | Type | Watermark | 已爬文章數 |
|--------|------|-----------|-----------|
| LTN | sequential | 4,886,777 | 398,423 |
| CNA | date_based | 2024-12-03 | 147,692 |
| UDN | sequential | 8,216,842 | 152,436 |
| MOEA | sequential | 121,298 | 821 |
| Chinatimes | date_based | 2024-02-22 | 1,017 |
| ESG BT | date_based | 2026-02-12 | 4,167 |

### GCP 範圍（不與桌機重疊）

| Source | GCP start | GCP end | 預估量 |
|--------|-----------|---------|--------|
| **LTN** | 7,000,000 | 9,500,000 | ~60% hit rate |
| **CNA** | 2025-06-01 | 2026-02-12 | date-based |
| **UDN** | 8,800,000 | 9,400,000 | ~6% hit rate (考慮用 sitemap) |
| **MOEA** | 121,300 | 121,900 | 小量 |

### UDN 替代方案：Sitemap

Full scan hit rate 只有 6%，建議改用 sitemap：

```bash
"$GCLOUD" compute ssh nlweb-crawler --zone=asia-east1-b \
  --command='curl -s -X POST http://localhost:8001/api/indexing/crawler/start \
  -H "Content-Type: application/json" \
  -d "{\"source\":\"udn\",\"mode\":\"sitemap\",\"date_from\":\"202501\"}"'
```

---

## 春節執行計畫

### 出發前（Day 0）

1. ✅ GCP VM 已建好、venv 已裝好
2. ✅ Dashboard 已啟動
3. ✅ LTN 已在跑（7M → 9.5M）
4. 確認 LTN Found 數字持續增長
5. 設定 cron 監控：
   ```bash
   "$GCLOUD" compute ssh nlweb-crawler --zone=asia-east1-b \
     --command='chmod +x ~/nlweb/crawler/remote/monitor-gcp.sh && (crontab -l 2>/dev/null; echo "*/30 * * * * ~/nlweb/crawler/remote/monitor-gcp.sh") | crontab -'
   ```

### 春節期間遠端巡檢

每天花 5 分鐘：

```bash
# 1. 查狀態
"$GCLOUD" compute ssh nlweb-crawler --zone=asia-east1-b \
  --command='curl -s http://localhost:8001/api/indexing/fullscan/status' | python -m json.tool

# 2. 查記憶體
"$GCLOUD" compute ssh nlweb-crawler --zone=asia-east1-b \
  --command='free -m && echo "---" && ls -lh ~/nlweb/data/crawler/articles/'

# 3. 查監控 log
"$GCLOUD" compute ssh nlweb-crawler --zone=asia-east1-b \
  --command='tail -30 ~/nlweb/data/crawler/logs/monitor.log'
```

### Source 排程建議

| 天數 | Source | 說明 |
|------|--------|------|
| Day 1-3 | LTN | 7M→9.5M，~60% hit rate，產量最高 |
| Day 3-5 | CNA | 2025-06→2026-02，date-based |
| Day 5-7 | UDN sitemap | 2025-01 起，100% hit rate |
| Day 7+ | MOEA | 低量收尾 |

**注意**：一個跑完/確認穩定後再切下一個，一次只跑一個 source。

### 春節結束（返回後）

```bash
# 1. 下載 articles
"$GCLOUD" compute scp --recurse nlweb-crawler:/home/User/nlweb/data/crawler/articles/ ./articles-gcp/ --zone=asia-east1-b

# 2. 下載 registry
"$GCLOUD" compute scp nlweb-crawler:/home/User/nlweb/data/crawler/crawled_registry.db ./registry-gcp.db --zone=asia-east1-b

# 3. 合併 registry
python crawler/remote/merge_registry.py registry-gcp.db data/crawler/crawled_registry.db

# 4. 桌機跑 indexing
cd code/python
python -m indexing.pipeline --tsv-dir ../../articles-gcp/

# 5. 確認無誤後刪除 GCP VM
"$GCLOUD" compute instances delete nlweb-crawler --zone=asia-east1-b
```

---

## 檔案清單

```
crawler/remote/
├── setup-gcp.sh              # GCP VM 初始化腳本
├── launch-crawler.sh          # 直接啟動 crawler（不經 Dashboard）
├── nlweb-crawler.service      # Crawler systemd 服務
├── nlweb-dashboard.service    # Dashboard systemd 服務
├── monitor-gcp.sh             # cron 監控腳本
├── merge_registry.py          # Registry DB 合併
├── setup-laptop-windows.ps1   # Windows 筆電防休眠設定
└── start-dashboard.bat        # Windows 開機自動啟動 Dashboard
```

---

## 異常處理

### Dashboard 掛了

```bash
"$GCLOUD" compute ssh nlweb-crawler --zone=asia-east1-b \
  --command='pkill -f dashboard_server; sleep 2; cd ~/nlweb/code/python && source ~/nlweb/venv/bin/activate && CRAWLER_ENV=gcp python -m indexing.dashboard_server > ~/nlweb/data/crawler/logs/dashboard.log 2>&1 &'
```

### Crawler 卡住（progress 不動）

1. 查 log：`tail -50 ~/nlweb/data/crawler/logs/*.log`
2. 停掉重啟（watermark 會自動續跑）
3. 如果被 rate limit，等 10 分鐘再啟動

### OOM（記憶體不足）

1. `free -m` 確認
2. 確保只跑一個 source
3. 如果 swap 用超過 1GB，考慮降低 `concurrent_limit`

### VM 意外重啟

Dashboard 和 crawler 都不會自動重啟（除非設了 systemd）。
手動重啟 Dashboard，crawler 從 watermark 自動續跑。
