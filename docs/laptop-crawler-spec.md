# 家用筆電 Crawler 部署規格

## 概述

桌機關機期間（春節及之後），使用家用筆電 24/7 運行 crawler + dashboard。
筆電只負責爬取（crawler-only），不跑 indexing pipeline。
TSV 收集後回桌機跑 indexing → Qdrant。

---

## 硬體規格

| 零件 | 規格 | 評估 |
|------|------|------|
| CPU | i5-8265U (4C/8T, 3.9GHz boost) | 足夠 |
| RAM | **4GB DDR4** | 吃緊但 crawler-only 可用 |
| 儲存 | **1TB HDD** | SQLite 較慢但可容忍 |
| GPU | MX250 2GB | 用不到 |
| 電池 | 內建 | 天然 UPS（短暫停電不斷） |

---

## 記憶體預算

```
Windows 10/11:           ~2.5 GB
Chrome Remote Desktop:   ~0.1 GB
Dashboard server:        ~0.1 GB
Crawler (1 source):      ~0.2 GB
─────────────────────────────────
合計:                    ~2.9 GB / 4 GB ✅
注意：不要同時開 Chrome 瀏覽器（吃 0.5-1GB）
```

**重要**：一次只跑一個 source，避免 OOM。

---

## 筆電資訊

| 項目 | 值 |
|------|-----|
| Windows 使用者 | `Mounai` |
| 專案路徑 | `C:\Users\Mounai\nlweb\` |
| Python | 3.11.9 |
| Git | 2.53 |
| Dashboard port | 8001 |
| 遠端存取 | Chrome Remote Desktop |

---

## 環境特殊設定

### indexing/__init__.py 已清空

筆電不裝 qdrant_client 等重量級套件，`indexing/__init__.py` 改為：
```python
# dashboard-only
```

**注意**：`git pull` 會覆蓋回原始版本，拉完需重新清空：
```powershell
cd C:\Users\Mounai\nlweb\code\python
python -c "import os;[open(os.path.join('indexing',f),'w').write('# dashboard-only\n') or print('Fixed:',f) for f in os.listdir('indexing') if 'init' in f and f.endswith('.py')]"
```

### PowerShell 注意事項

PowerShell 會吃掉 `__init__` 的雙底線。任何涉及 `__init__.py` 的操作，
都用 Python 來做，不要用 PowerShell 直接操作檔名。

---

## 防休眠設定

已透過 PowerShell（管理員）設定：

```powershell
# 插電不休眠
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
powercfg /change monitor-timeout-ac 0

# 蓋上螢幕不做任何動作
powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0
powercfg /setdcvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0
powercfg /setactive SCHEME_CURRENT
```

### 驗證方式

1. 蓋上筆電蓋子
2. 等 1 分鐘
3. 用 Chrome Remote Desktop 連線，確認仍可存取
4. 開 `http://localhost:8001` 確認 Dashboard 正常

---

## 常用指令

### 啟動 Dashboard

```powershell
cd C:\Users\Mounai\nlweb\code\python
python -m indexing.dashboard_server
```

### 開機自動啟動

把 `crawler\remote\start-dashboard.bat` 放入啟動資料夾：
```
Win+R → shell:startup → 貼入 start-dashboard.bat 的捷徑
```

或用 Task Scheduler：
- 觸發：使用者登入時
- 動作：啟動程式 → `python`
- 引數：`-m indexing.dashboard_server`
- 工作目錄：`C:\Users\Mounai\nlweb\code\python`

**注意**：`start-dashboard.bat` 裡的路徑寫的是 `C:\Users\User\`，
筆電上要改成 `C:\Users\Mounai\`。

### 啟動 Full Scan

```powershell
# LTN（填補桌機與 GCP 之間的空隙）
Invoke-RestMethod -Method POST -Uri "http://localhost:8001/api/indexing/fullscan/start" -ContentType "application/json" -Body '{"sources":["ltn"],"overrides":{"ltn":{"start_id":4887000,"end_id":7000000}}}'

# CNA（填補桌機與 GCP 之間）
Invoke-RestMethod -Method POST -Uri "http://localhost:8001/api/indexing/fullscan/start" -ContentType "application/json" -Body '{"sources":["cna"],"overrides":{"cna":{"start_date":"2024-12-04","end_date":"2025-05-31"}}}'

# UDN（桌機到 8.2M，GCP 從 8.8M）
Invoke-RestMethod -Method POST -Uri "http://localhost:8001/api/indexing/fullscan/start" -ContentType "application/json" -Body '{"sources":["udn"],"overrides":{"udn":{"start_id":8217000,"end_id":8800000}}}'

# Chinatimes（桌機到 2024-02-22，繼續往後）
Invoke-RestMethod -Method POST -Uri "http://localhost:8001/api/indexing/fullscan/start" -ContentType "application/json" -Body '{"sources":["chinatimes"],"overrides":{"chinatimes":{"start_date":"2024-02-23"}}}'
```

### 停止 Crawler

```powershell
# 查狀態，找 task_id
Invoke-RestMethod -Uri "http://localhost:8001/api/indexing/fullscan/status"

# 停止指定 task
Invoke-RestMethod -Method POST -Uri "http://localhost:8001/api/indexing/crawler/stop" -ContentType "application/json" -Body '{"task_id":"<TASK_ID>"}'
```

### 查看產出

```powershell
# TSV 檔案
dir C:\Users\Mounai\nlweb\data\crawler\articles\

# 記憶體（Task Manager 或）
Get-Process python | Select-Object Name, WorkingSet64
```

---

## 分割範圍（三機協作）

### 總覽

```
桌機 watermark        筆電範圍              GCP 範圍
─────────────────    ─────────────────    ─────────────────
LTN:   4,886,777 →  4,887,000 → 7,000,000  → 7,000,000 → 9,500,000
CNA:   2024-12-03 →  2024-12-04 → 2025-05-31 → 2025-06-01 → 2026-02-12
UDN:   8,216,842 →  8,217,000 → 8,800,000  → 8,800,000 → 9,400,000
MOEA:  121,298   →  （略，量太少）         → 121,300 → 121,900
Chinatimes: 2024-02-22 → 2024-02-23 → 開放  → （不跑）
```

### Source 排程建議

| 順序 | Source | 範圍 | 說明 |
|------|--------|------|------|
| 1 | **LTN** | 4,887,000 → 7,000,000 | ~60% hit rate，產量最高，已在跑 |
| 2 | **CNA** | 2024-12-04 → 2025-05-31 | date-based，接著跑 |
| 3 | **Chinatimes** | 2024-02-23 → 開放 | 高產量（月 ~10K 篇） |
| 4 | **UDN** | 8,217,000 → 8,800,000 | 或改用 sitemap |

一個跑完再切下一個。

---

## HDD 效能注意事項

SQLite 在 HDD 上隨機讀寫較慢：

- 定期 VACUUM：`python -c "import sqlite3; c=sqlite3.connect(r'C:\Users\Mounai\nlweb\data\crawler\crawled_registry.db'); c.execute('VACUUM'); c.close()"`
- 一次只跑一個 source（避免多個 crawler 同時寫 SQLite）
- 如果 I/O 太慢，考慮用 USB 隨身碟放 registry.db

---

## 斷電 / 重啟復原

1. 筆電內建電池 = 天然 UPS（短暫停電不斷）
2. 長時間斷電 → 重開機 → 自動登入 → Task Scheduler 啟動 Dashboard
3. 用 Chrome Remote Desktop 連進來，手動重啟 crawler（watermark 自動續跑）

### Windows 自動登入

```
Win+R → netplwiz → 取消勾選「必須輸入使用者名稱和密碼」→ 輸入密碼 → 確定
```

### Windows Update 防自動重啟

```
設定 → Windows Update → 進階選項 → 活動時段 → 0:00 ~ 23:59
```

---

## 遠端存取

### Chrome Remote Desktop

1. 筆電安裝 Chrome + Chrome Remote Desktop（remotedesktop.google.com）
2. 設定遠端存取（設定 PIN）
3. 從任何裝置的 Chrome 瀏覽器連線

### 日常巡檢（每天 2 分鐘）

1. Chrome Remote Desktop 連進筆電
2. 開 `http://localhost:8001` 看 Dashboard
3. 確認 Found 數字持續增長
4. Task Manager 確認 RAM < 3.5GB

---

## 春節結束：資料收回

```powershell
# 1. 停止 crawler
Invoke-RestMethod -Method POST -Uri "http://localhost:8001/api/indexing/crawler/stop" -ContentType "application/json" -Body '{"task_id":"<TASK_ID>"}'

# 2. 複製 articles 和 registry 到隨身碟或網路共享
# 　 articles: C:\Users\Mounai\nlweb\data\crawler\articles\
# 　 registry: C:\Users\Mounai\nlweb\data\crawler\crawled_registry.db

# 3. 在桌機合併 registry
python crawler/remote/merge_registry.py laptop-registry.db data/crawler/crawled_registry.db

# 4. 桌機跑 indexing
cd code/python
python -m indexing.pipeline --tsv-dir <laptop-articles-dir>
```

---

## 異常處理

### Dashboard 掛了

關掉 PowerShell 視窗，重新開一個：
```powershell
cd C:\Users\Mounai\nlweb\code\python
python -m indexing.dashboard_server
```

### Crawler 卡住（progress 不動超過 10 分鐘）

1. Dashboard 上按 Stop
2. 等 30 秒
3. 重新啟動同一個 source（watermark 自動續跑）

### 記憶體不足（RAM > 3.5GB）

1. 關掉 Chrome 瀏覽器（用 Chrome Remote Desktop 不需要開本機 Chrome）
2. Task Manager 關掉其他不需要的程式
3. 如果還不夠，停止 crawler，VACUUM registry.db，重啟

### git pull 後 Dashboard 壞掉

`__init__.py` 被覆蓋回原版。重新清空：
```powershell
cd C:\Users\Mounai\nlweb\code\python
python -c "import os;[open(os.path.join('indexing',f),'w').write('# dashboard-only\n') or print('Fixed:',f) for f in os.listdir('indexing') if 'init' in f and f.endswith('.py')]"
```
