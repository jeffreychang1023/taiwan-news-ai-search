# Crawler 部署執行指南（給執行 Agent）

> 本文件是給負責在筆電和 GCP 上部署並啟動 crawler 的 agent 的完整指引。
> 請依序執行，一步一步確認。

---

## 背景

我們有三台機器分工爬取新聞：

| 機器 | 角色 | 任務 |
|------|------|------|
| 桌機 | 主力 | LTN/CNA/einfo 收尾（今晚重啟），之後全力 Chinatimes |
| **筆電** | 中量 | UDN sitemap gap fill + MOEA backfill |
| **GCP** | 暫緩 | 目前無任務（einfo 已在桌機用 proxy 跑） |

你負責的是**筆電**。GCP 暫不需要部署。

### 桌機目前狀態（2026-02-12 下午）

所有桌機 task 已暫停，今晚重啟以下三個收尾：

| Source | Mode | 累計 Success | Checkpoint | 預估剩餘 |
|--------|------|-------------|------------|----------|
| LTN | full_scan | 179,041 | ID ~5,190,000 / 5,341,330 | ~30K |
| CNA | full_scan | 74,974 | date ~2025-12-18 / 2026-02-12 | ~20K |
| einfo | full_scan | 1,553 | ID ~239,000 / 270,000 | ~31K IDs（proxy 84%） |

LTN/CNA/einfo 收尾完成後，桌機將全力跑 **Chinatimes**（最大缺口 200K+）。

### 各 source 覆蓋缺口

| Source | 已完整覆蓋 | 缺口 | 預估缺口量 |
|--------|-----------|------|-----------|
| LTN | 2024-01~2025-09 | 2025-10~2026-02 | ~30K（桌機即將完成） |
| CNA | 2024-01~2025-11 | 2025-12~2026-02 | ~20K（桌機即將完成） |
| UDN | 2024-01~09 + 2025-08+ | 2024-10~2025-07 | ~65K（筆電負責） |
| Chinatimes | 2024-01~02, 10/23~11/18 | 2024-03~2026-02 大部分 | ~200K+（桌機之後全力） |
| ESG BT | 全覆蓋 | 無 | 完成 |
| MOEA | 2025-04~2026-02 | 2024-01~2025-03 | ~500（筆電負責） |
| einfo | 進行中 | 進行中填補 | 桌機 proxy 處理中 |

---

## Part 1: 筆電部署

### 1.1 連線

透過 Chrome Remote Desktop 連到筆電（使用者 `Mounai`）。

### 1.2 環境確認

```powershell
# 確認專案路徑
cd C:\Users\Mounai\nlweb\code\python

# 確認 Python 版本（需 3.11）
python --version

# 拉最新程式碼
cd C:\Users\Mounai\nlweb
git pull
```

### 1.3 修復 `__init__.py`（git pull 後必做）

`git pull` 會覆蓋 `indexing/__init__.py`，筆電不裝 qdrant_client 等重量級套件，必須清空：

```powershell
cd C:\Users\Mounai\nlweb\code\python
python -c "import os;[open(os.path.join('indexing',f),'w').write('# dashboard-only\n') or print('Fixed:',f) for f in os.listdir('indexing') if 'init' in f and f.endswith('.py')]"
```

### 1.4 啟動 Dashboard

```powershell
cd C:\Users\Mounai\nlweb\code\python
python -m indexing.dashboard_server
```

等到看見 `Dashboard server started on port 8001` 後，開瀏覽器確認 `http://localhost:8001` 可存取。

### 1.5 啟動任務

**重要**：一次只跑一個 source。先跑 UDN sitemap，完成後再跑 MOEA。

#### 任務 1: UDN sitemap（優先）

填補 2024-10 ~ 2025-07 的缺口。使用 sitemap 模式，100% hit rate。

```powershell
Invoke-RestMethod -Method POST -Uri "http://localhost:8001/api/indexing/crawler/start" -ContentType "application/json" -Body '{"source":"udn","mode":"sitemap","date_from":"202410","date_to":"202507"}'
```

**預期行為**：
- 會下載 UDN 的 sitemap index XML，然後逐一處理子 sitemap
- 每個子 sitemap 包含數千個 URL
- 成功率接近 100%（sitemap 裡的 URL 都是有效的）
- 預估產出 ~65,000 篇文章
- 預估時間：視網速，可能 6-24 小時

**監控**：
- Dashboard 上看 Crawler tab，確認 success 數字持續增長
- 如果卡住超過 10 分鐘（success 不動），停掉重啟

#### 任務 2: MOEA backfill（UDN 完成後）

填補 2024-01 ~ 2025-03 的缺口。掃描 ID 100,000 → 122,000。

```powershell
Invoke-RestMethod -Method POST -Uri "http://localhost:8001/api/indexing/fullscan/start" -ContentType "application/json" -Body '{"sources":["moea"],"start_id":100000,"end_id":122000}'
```

**預期行為**：
- 掃描 22,000 個 ID，hit rate ~9%（大部分是其他部會的新聞）
- 預估產出 ~500 篇文章
- MOEA 網站較慢，預估 2-4 小時
- `not_found` 數字快速增長是正常的（91% 的 ID 不是經濟部新聞）

**監控**：
- Dashboard 上看 Full Scan tab
- success + not_found 持續增長 = 正常
- 全部停住不動 = 異常，需重啟

### 1.6 日常巡檢

每天花 2 分鐘：

1. Chrome Remote Desktop 連進筆電
2. 開 `http://localhost:8001` 看 Dashboard
3. 確認 success 數字有增長
4. Task Manager 確認 RAM < 3.5GB

### 1.7 注意事項

- **一次只跑一個 source**：筆電只有 4GB RAM + HDD，多個 source 會 OOM
- **不要開 Chrome 瀏覽器**：用 Chrome Remote Desktop 不需要本機 Chrome，省記憶體
- **蓋上螢幕沒關係**：已設定蓋上不休眠
- **停電自動復原**：重開機後需手動重啟 Dashboard，crawler 從 watermark 自動續跑
- **PowerShell 會吃雙底線**：任何涉及 `__init__.py` 的操作用 Python 做，不用 PowerShell

---

## Part 2: GCP 部署（暫緩）

目前 GCP 不需要啟動任何任務。原因：
- einfo 已在桌機用 proxy pool 跑，成功率 84%，即將完成
- GCP 只有 1GB RAM，效能有限

如果未來需要 GCP 跑其他任務，參考 `docs/gcp-crawler-spec.md` 中的部署步驟。

---

## Part 3: 完成後資料收回

### 筆電

1. 停止 crawler：Dashboard 上按 Stop，或：
   ```powershell
   # 查 task_id
   Invoke-RestMethod -Uri "http://localhost:8001/api/indexing/fullscan/status"
   # 停止
   Invoke-RestMethod -Method POST -Uri "http://localhost:8001/api/indexing/crawler/stop" -ContentType "application/json" -Body '{"task_id":"<TASK_ID>"}'
   ```

2. 複製檔案到桌機（透過隨身碟或網路共享）：
   - `C:\Users\Mounai\nlweb\data\crawler\articles\` — TSV 文章檔
   - `C:\Users\Mounai\nlweb\data\crawler\crawled_registry.db` — Registry DB

3. 在桌機合併：
   ```bash
   cd /c/users/user/nlweb/code/python
   python crawler/remote/merge_registry.py <laptop-registry-path> data/crawler/crawled_registry.db
   python -m indexing.pipeline --tsv-dir <laptop-articles-dir>
   ```

---

## 異常排除速查

| 症狀 | 原因 | 解法 |
|------|------|------|
| Dashboard 打不開 | 程序掛了 | 重啟 `python -m indexing.dashboard_server` |
| success 不動超過 10 分鐘 | 卡住 | 停掉重啟，watermark 自動續跑 |
| RAM > 3.5GB（筆電） | 記憶體洩漏 | 停止 crawler，重啟 Dashboard |
| `__init__.py` 報錯（筆電） | git pull 覆蓋 | 執行 1.3 步驟清空 |

---

*更新：2026-02-12*
