---
name: Delegation 派工規則
description: 各模組的派工指引、Code Review 策略、E2E 測試規範。派工 subagent 前必讀。
type: reference
---

# Delegation Patterns

> Orchestrator 派工時的經驗手冊。從實際 delegation 結果中持續更新。

---

## 通用原則

1. **Spec 發現**：派工前先 `ls docs/specs/`，從列表判斷哪些與任務相關，附在 agent prompt 中。不憑記憶列舉。
2. **Skill 調用**：不自寫 prompt template，選擇正確的 skill 執行（systematic-debugging / writing-plans / dispatching-parallel-agents 等）。
3. **Docs 一致性**：任務完成後檢查相關文件是否需同步更新（spec、status、delegation patterns）。
4. **禁止平行派工編輯同檔案**：兩個 agent 同時編輯同一檔案（如 `news-search.css` + `news-search-prototype.html`），後完成的 agent 會覆蓋先完成的改動 → 全部遺失。**同檔案的任務必須序列化**，不同檔案才可平行。（2026-03-13 UI Redesign 踩坑：Phase 2 + Phase 3 平行派工，所有改動消失。）
5. **Subagent 必須使用 Superpowers Skills**：派工 agent prompt 中必須指示 subagent 調用對應的 superpowers skill。Subagent 不會自動使用 skill，必須在 prompt 中明確要求。對應表：

   | 任務類型 | 必須在 prompt 中指示使用的 Skill |
   |----------|-------------------------------|
   | Debug / Bug fix | `superpowers:systematic-debugging` |
   | 功能規劃 | `superpowers:brainstorming` → `superpowers:writing-plans` |
   | 功能實作 | `superpowers:executing-plans` 或 `superpowers:test-driven-development` |
   | Code review | `superpowers:requesting-code-review` |
   | 多步驟獨立任務 | `superpowers:dispatching-parallel-agents`（但注意原則 #4） |

   **寫法範例**：`"先調用 Skill tool 執行 superpowers:systematic-debugging，按照該 skill 的流程診斷問題。"`

---

## 強制驗證規則（Smoke Test Gate）

> 2026-03-17 新增。解決 skill/subagent 改 code 後 break 東西的問題。

### 規則：改完 code 必跑 smoke test

**所有修改程式碼的 subagent**（包括 simplify、debug、feature dev、refactor）在完成修改後，必須執行：

```bash
cd code/python && python tools/smoke_test.py
```

| 結果 | 動作 |
|------|------|
| PASSED | 繼續下一步 / 回報完成 |
| FAILED | **立即修復**，不可忽略。修復後重跑直到 PASSED |

### 派工 prompt 必須包含

在派工 agent prompt 的結尾加上這段：

```
完成所有修改後，從 code/python/ 目錄執行 `python tools/smoke_test.py`。
如果 FAILED，修復問題後重跑直到 PASSED。
不可跳過此步驟。
```

### Smoke test 涵蓋範圍

17 個核心模組的 import chain：Server、Request Processing、Retrieval、Ranking、Reasoning、Auth、Session、Streaming、Indexing、Crawler。任何 circular import、missing dependency、renamed module 都會被擋住。

### 不適用的情況

- 只修改文件（docs/、memory/）
- 只修改 config YAML/JSON
- 只修改前端（static/ 下的 HTML/JS/CSS）

---

## 強制驗證規則（E2E Gate）

> 2026-03-19 新增。Unit test + smoke test 通過 ≠ 完成。E2E 通過才算完成。

### 完整驗證 pipeline

```
Code 修改 → Unit Test (TDD) → Smoke Test → Agent E2E (DevTools) → 修 bugs → 寫 e2etest.md → 通知 CEO 人工 E2E → Pass = 完成
```

**status.md 的「已完成」= 三關全過：unit test + smoke + E2E。** E2E 沒跑完前，status.md 標記為「已修復，待 E2E 驗證」。

### 流程

1. **Agent E2E**：Zoe 派 subagent 用 Chrome DevTools MCP（navigate、fill、click、snapshot、screenshot）執行 E2E 測試。模擬人類操作，不可用 `evaluate_script + fetch()` 繞過 UI。
2. **修 bugs**：Agent E2E 發現的問題，立即修復 + 重跑，直到全部 PASS。
3. **寫 e2etest.md**：測試結果寫入 `docs/e2etest.md` 最後面（agent 測試結果段落）。
4. **通知 CEO**：LINE 或對話中告知「Agent E2E 已完成，請人工 E2E 驗證」。附上需要人工測試的項目清單。
5. **CEO 人工 E2E**：CEO 跑 `docs/e2etest.md` 的人工 checklist，標記 Pass/Fail。
6. **全部 Pass → 標記完成**：status.md 改為「已完成」。

### 環境驗證（E2E 前必做）

**Server 啟動由 CEO 負責**（不從 Claude Code 啟動）：
- Claude Code 的 Bash `&` 背景 process 會產生殭屍，stderr 被吞看不到 traceback
- CEO 用 PowerShell：`$env:POSTGRES_CONNECTION_STRING="postgresql://nlweb:nlweb_dev@localhost:5432/nlweb"` + `python app-file.py`
- 或直接 `python app-file.py`（已修 dotenv 自動載入 `nlweb/.env`）

**E2E agent 啟動前確認**：
1. Server 已在跑（CEO 啟動的）
2. `curl http://localhost:8000/` → 200
3. 搜一次 → 查 CEO terminal log 確認無 `qdrant_client` 錯誤（應看到 `postgres_client` log）

**為什麼**：(1) `config_retrieval.yaml` 的 `qdrant_url` 曾同時 enabled，server 走了 Qdrant（2026-03-20 踩坑 30+ 分鐘）。(2) PowerShell 的 `set` 不設 env var（要用 `$env:`）。(3) 殭屍 server process 搶 port 導致 request 到了舊 server。

### 派工 E2E agent 的 prompt 模板

```
你是 E2E 測試工程師。用 Chrome DevTools MCP 測試以下功能。

## 規則
- 模擬人類使用者操作（navigate → fill → click → snapshot/screenshot 驗證）
- 不可用 evaluate_script + fetch() 繞過 UI
- 如果 UI 缺少必要元素，回報為 FAIL 並說明缺什麼

## 測試 URL
[URL]

## 測試場景
[場景清單，每個含操作步驟 + 預期結果]

## 輸出
- 每個場景：PASS / FAIL + 截圖或 snapshot 證據
- FAIL 的場景：描述實際行為 vs 預期行為
```

### 不適用的情況

- 只修改文件（docs/、memory/）
- 只修改 config YAML/JSON
- 修改的功能無法透過前端觸發（純後端 internal 邏輯）
- **VPS 無 indexed data 時**：涉及搜尋結果的 E2E 測試先跳過，標記「待 indexed data」

---

## 模組特定指引

每條的「優先閱讀」一律包含 `docs/specs/` 中相關 spec + 直接相關的程式碼。以下只列考量重點。

### Ranking

| 優先閱讀（程式碼） | 考量 |
|-------------------|------|
| `core/ranking.py`, `core/xgboost_ranker.py`, `core/mmr.py` | Pipeline 已簡化為 4 階段（Hybrid Retrieval → LLM → XGBoost → MMR）。BM25 已移除（`legacy/core/bm25.py`），關鍵字匹配由 pg_bigm 在 retrieval 層完成。XGBoost feature `bm25_score` 已 rename 為 `text_search_score`。shadow mode 資料結構注意相容。 |

### Crawler — Parser

| 優先閱讀（程式碼） | 考量 |
|-------------------|------|
| 該 source 的 parser 檔案, `crawler/core/settings.py`, `memory/crawler-reference.md` | session type（curl_cffi/aiohttp）、該 source 的反爬機制、修改是否影響其他 parser 的共用邏輯 |

### Crawler — Engine

| 優先閱讀（程式碼） | 考量 |
|-------------------|------|
| `crawler/core/engine.py`, `crawler/core/settings.py`, `crawler/subprocess_runner.py`, `crawler/core/crawled_registry.py` | subprocess 隔離架構（每 source 獨立 process）、Windows pipe buffer 65KB 限制、watermark 只往前不往回、GCP 與本地環境差異 |

### Reasoning — Agent + Prompt

| 優先閱讀（程式碼） | 考量 |
|-------------------|------|
| 目標 agent 檔案, 對應 prompt 檔案, `reasoning/orchestrator.py`, `config/config_reasoning.yaml` | 4 agent 各有專屬角色不可混用、CoV 兩階段查核流程、TypeAgent schema 變更需同步 Pydantic model、Critic 迭代上限 3 輪 |

### Frontend + API

| 優先閱讀（程式碼） | 考量 |
|-------------------|------|
| `static/news-search.html`, `static/news-search.js`, `static/news-search.css`, `webserver/aiohttp_server.py` | SSE 與 WebSocket 混合架構（搜尋用 SSE、Chat 用 WS）、原生 HTML/JS/CSS 分離是刻意設計（AI 可讀性）、前端狀態機多階段（reasoning 進度）、Rate Limiter 的 slot 管理 |

### Indexing Pipeline

| 優先閱讀（程式碼） | 考量 |
|-------------------|------|
| `indexing/pipeline.py`, `indexing/chunking_engine.py`, `indexing/embedding.py` | chunking 參數（170字/句號邊界/overlap）是 POC 驗證過的、embedding model 將從 OpenAI 換 Qwen3、改 chunking 需全量 re-index |

### Dashboard

| 優先閱讀（程式碼） | 考量 |
|-------------------|------|
| `indexing/dashboard_server.py`, `indexing/dashboard_api.py`, `static/dashboard.html` | port 8001、API 參數命名（`stats.success` ≠ `count`） |

### Auth / Login / Session

| 優先閱讀（程式碼） | 考量 |
|-------------------|------|
| `auth/auth_db.py`, `auth/auth_service.py`, `webserver/routes/auth.py`, `webserver/middleware/auth.py`, `core/session_service.py`, `webserver/routes/sessions.py` | JWT access+refresh token 架構、async DB layer（psycopg AsyncConnection）、rate limiting middleware chain 順序、Alembic migrations（4 個）、7 個 deferred items（見 `docs/specs/login-spec.md` Known Gaps）、D3 localStorage JWT XSS 風險待修 |

### Config 變更

| 優先閱讀（程式碼） | 考量 |
|-------------------|------|
| 目標 config 檔案 + 用 indexer 搜尋使用該 config 的程式碼 | 設定變更需重啟 server、YAML profile 切換機制（embedding online/offline） |

### 文件更新

| 優先閱讀（程式碼） | 考量 |
|-------------------|------|
| 變更的檔案列表、commit messages、目標文件 | docs/ 是 single source of truth、spec 與程式碼要同步 |

---

## Code Review 策略

> 基於 superpowers:code-reviewer（已有）+ adversarial-review（外部參考）分析。

### 現有工具：直接用，不重造

superpowers 三件套已覆蓋 80% 需求：
- **code-reviewer agent**：Plan alignment + Code quality + Architecture + Testing checklist，Critical/Important/Minor 分級
- **requesting-code-review**：定義 review 時機（mandatory: 每個 task 後 / merge 前）+ git SHA template
- **receiving-code-review**：反 AI 討好紀律、YAGNI check、pushback protocol

### 補充策略：大改動加派多鏡頭 + Lead Judgment

| 改動規模 | 策略 |
|----------|------|
| 小（<50 行，1-2 檔） | 直接用 superpowers:code-reviewer，不加碼 |
| 中（50-200 行，3-5 檔） | superpowers:code-reviewer + Zoe 快速 lead judgment |
| 大（200+ 行或 5+ 檔） | 派 2-3 個 parallel subagent 各帶不同 lens（Skeptic/Architect/Minimalist），Zoe 做 lead judgment 過濾 false positive |

### Lens Prompts（大改動用）

- **Skeptic**：找 bug、race condition、edge case、安全漏洞。「這裡會壞嗎？」
- **Architect**：結構、耦合度、擴展性、是否符合現有 pattern。「這裡會後悔嗎？」
- **Minimalist**：過度工程、不必要的抽象、YAGNI。「這裡可以更簡單嗎？」

---

## E2E 測試策略

> 完整規則見 `feedback_e2e_testing.md`。以下為派工時的快速參考。

### 規則：E2E = 模擬人類使用者操作

| 做法 | 等級 | 說明 |
|------|------|------|
| DevTools `fill` + `click` 操作 UI | E2E | 模擬真人填表、點按鈕 |
| DevTools `evaluate_script` + `fetch()` | API test | 繞過前端，只測後端 |

### 派 E2E 測試 agent 時的 prompt 模板

prompt 必須明確包含：
- 「模擬人類使用者操作，不要用 evaluate_script + fetch() 繞過 UI」
- 前端入口 URL
- 測試場景清單（每個場景包含操作步驟 + 預期結果）
- 「如果 UI 缺少必要元素，回報為 FAIL 並說明缺什麼」

### 前後端同步檢查

修改後端 API 參數時，**必須同步更新前端**：
1. 搜尋 API endpoint 路徑（如 `/api/auth/register`）在 `static/` 的呼叫點
2. 確認 JS fetch body 的參數與後端一致
3. 確認 HTML 表單有對應的 input 欄位

---

## 重要提醒

**評估任何 skill 前必須讀原始檔案內容**，不可只看 description 就下結論。Skill 檔案位置：`~/.claude/plugins/cache/claude-plugins-official/superpowers/`。
