# E2E Verification Loop — Claude Code 自動指令

你是一個 E2E 測試自動化 agent。你的任務是驗證 NLWeb 新聞搜尋系統的功能。

## 啟動步驟

1. **讀取歷史**：`tests/e2e-findings.md`，了解 Open Issues、Stable Items、Round Summary
2. **分類項目**：根據 findings 將 31 項分為三類：
   - **Active**：Open Issues + 其依賴項 + 最近才從 Open 移到 Resolved 的項目（需重測確認）
   - **Stable**：列在 findings 的 Stable Items 中，且本輪無相關程式碼變更
   - **Untested**：不在以上兩類的項目（首次測試或曾 FAIL 後剛修好）
3. **標記 Stable 項目**：在 `tests/e2e-checklist.md` 中，Stable 項目直接標記 `[x] SKIP (STABLE)`
4. **如果只剩 Stable 項目且 Open Issues 為空**：檢查停止條件
5. **確認 server 狀態**：用 curl 檢查 localhost:8000 是否有回應
   - 如果沒有，啟動 server：
     ```
     source myenv311/Scripts/activate && cd code/python && python app-aiohttp.py
     ```
   - 在背景執行，等 "Server started" 出現
6. **開始測試**：先處理 Active（Open Issues），再處理 Untested

## 跨輪次 Issue 追蹤（重要！）

### 發現 issue 時的處理流程

每個測試項目完成後，對比 `tests/e2e-findings.md` 中的 Open Issues：

1. **新 issue**（findings 中沒有的）：
   
   - 記錄到 findings 的 Open Issues，標記 `[NEW Round N]`
   - 依照「核心循環」嘗試修復 → 修好標 FIXED，修不好標 FAIL + 描述

2. **Persisting issue**（findings 中已存在的）：
   
   - 這是重點！使用 `/systematic-debugging` skill 深入分析根因
   - 依照診斷結果嘗試修復程式碼
   - 更新 findings 中該 issue 的狀態，加上本輪的分析結果與修復嘗試
   - 修好 → 標 FIXED，移到 Resolved Issues
   - 修不好 → 標 `FAIL (PERSISTING)` + systematic-debugging 摘要 + 嘗試過的方案

3. **已修復 issue**（findings 中有，但本輪測試 PASS）：
   
   - 從 Open Issues 移到 Resolved Issues，標記修復的 round

### e2e-findings.md 更新格式

```markdown
## Stable Items (連續 PASS ≥ 2 輪，本輪跳過)

T01, T03, T04, T05, T06, T07, T08, T10, T13, T14, T15, ...

## Open Issues

- **T02** sidebar 點擊 session 觸發重命名而非載入
  - [Round 1] 首次發現
  - [Round 2] PERSISTING — /systematic-debugging 分析：...
  - [Round 3] FIXED：修改 event listener 綁定順序

## Resolved Issues

- **T09** Deep Research timeout >5min
  - [Round 1] 首次發現：Actor-Critic 推理耗時
  - [Round 3] 已修復：新增 timeout fallback
```

## 測試與修復流程

### 核心循環：驗證 → 修復 → 驗證

每個測試項目依照此流程：

```
驗證 → PASS? → 記錄，下一項
         ↓ FAIL
   診斷（/systematic-debugging）
         ↓
   修復程式碼
         ↓
   後端有改？ → 重啟 server
         ↓
   重新驗證 → PASS? → 記錄為 FIXED
                ↓ FAIL
          記錄為 UNRESOLVED，下一項
```

**重要**：每個 FAIL 項目都要嘗試修復，不是只記錄就跳過。

### 快速項目（程式碼檢查類）

T16-T17, T19-T25 — 可以直接讀碼驗證：

1. 讀對應原始碼，確認功能是否存在
2. **PASS** → 記錄行號 + 關鍵程式碼片段
3. **FAIL** → 直接修復程式碼 → 重新檢查 → 記錄

每項預期 2-5 個工具呼叫。

### 瀏覽器 E2E 項目

T01-T15, T18, T26-T29 — 需要實際操作瀏覽器：

1. 用 Chrome DevTools MCP 操作瀏覽器，導航到 http://localhost:8000
2. 執行操作、截圖記錄
3. 等待 SSE streaming 完成（搜尋結果通常需要 30-120 秒）
4. **PASS** → 截圖 + 記錄
5. **FAIL** →
   a. 截圖記錄失敗狀態
   b. 檢查 server log / browser console 找線索
   c. 用 `/systematic-debugging` 診斷根因
   d. 修復程式碼（前端 JS 或後端 Python）
   e. 後端有改 → 重啟 server
   f. 重新測試 → 截圖記錄最終結果

### 修復原則

- **修根因**：不要打補丁，找到真正的問題
- **最小修改**：只改必要的部分，不要順便重構
- **不要過度工程**：解決當前問題就好
- **DEFERRED**：如果問題需要大規模架構重構，標記為 DEFERRED + 說明原因，不要硬修

### Server 重啟

修改後端 Python 程式碼後，需要重啟 server：

```bash
# 停止舊 server（找 process 並 kill）
# 重新啟動（背景執行）
source myenv311/Scripts/activate && cd code/python && python app-aiohttp.py
```

等 "Server started" 出現後再繼續測試。

### 優先順序

1. **Open Issues**（最優先）：這些是已知問題，集中火力修復
2. **Untested 項目**：最近修復的、依賴項解除的、或新項目
3. **Stable 項目跳過**：直接標 `SKIP (STABLE)`，不浪費 context

同類項目內，先做快速項目（程式碼檢查類），再做瀏覽器 E2E 項目。

### 穩定項目跳過機制

**畢業條件**：連續 PASS ≥ 2 輪 → 加入 findings 的 Stable Items

**跳過規則**：Stable 項目本輪不重測，在 checklist 標記 `[x] SKIP (STABLE)`

**降級規則（需重測）**：以下情況必須將項目從 Stable 移回 Active：
- 本輪修復的程式碼可能影響該項目（例：改了 SSE streaming → T08 需重測）
- 該項目依賴的 Open Issue 剛被修復
- 前輪標記為 Resolved 但還沒重測確認過

**每次修復後**：檢查 Stable Items，判斷是否有項目需要降級重測。
如果有，從 Stable Items 移除，標記為 Active 並重新測試。

## 記錄規則

每完成一項（無論原始 PASS 或修復後 PASS）：

1. 更新 `tests/e2e-checklist.md`：`- [ ]` 改為 `- [x]`，填寫結果
2. 結果格式：
   - `PASS` 簡述
   - `FIXED` 問題描述 + 改了什麼 + 驗證結果
   - `FAIL` 問題描述 + 嘗試了什麼修復 + 為什麼仍失敗
   - `DEFERRED` 需要大規模重構，描述根因和原因
   - `NOT IMPLEMENTED` 該功能尚未實作
   - `BLOCKED` 原因（如 API key、外部服務等）
   - `SKIP (STABLE)` 連續 PASS ≥ 2 輪，本輪跳過
3. 截圖存到 `tests/screenshots/`（用 T 編號命名，如 `T01-mode-switch.png`）

## Session 結束規則

- 每個 session 盡量完成越多 測試+修復 越好
- 如果 context 快滿了，先更新 checklist + findings 再結束
- 更新 `tests/e2e-findings.md`：
  - 修好的 issue：從 Open Issues 移到 Resolved Issues
  - 未修好的 issue：更新診斷進度 + 嘗試過的修復方案
  - Round Summary 表格新增一行（含 FIXED 數量）

## 停止信號

如果本輪所有 Active/Untested 項目都 PASS，且 Open Issues 為空（Stable 項目算 PASS）：

1. 在 `tests/e2e-findings.md` 的 Round History 加上 `ALL_CLEAR`
2. 建立檔案 `tests/e2e-loop-status.txt`，內容為 `ALL_CLEAR`
3. 這代表系統穩定，外部 loop 會據此停止

## 重要提醒

- **目標是修復所有問題**，不只是記錄問題
- 可以且應該修改業務程式碼（前端 JS、後端 Python）來修 bug
- 但不要新增功能或順便重構，只修復測試中發現的 bug
- 搜尋/Deep Research 需要 LLM API 回應，如果 API key 失效記錄為 BLOCKED
- 瀏覽器測試要截圖作為證據
- 參考文件：`docs/bugfix-phases.md` 有每個 bug 的詳細描述和驗證方法
- **Persisting issue 一定要用 `/systematic-debugging`**，不要只記錄就跳過
- 修復一個 bug 前，先想想會不會影響其他功能
