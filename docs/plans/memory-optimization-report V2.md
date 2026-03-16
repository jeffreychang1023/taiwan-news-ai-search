# Memory System Optimization Report (v2.1 FINAL)

> **產出者**: Zoe (CTO agent)
> **日期**: 2026-03-13
> **版本**: v2.1 — 整合兩輪外部審查 (Gemini) 後定稿，可進入執行
> **目的**: Memory 系統優化的完整計畫書

---

## 1. 背景：Memory 系統的角色

Claude Code 的 memory 系統位於 `~/.claude/projects/C--users-user-nlweb/memory/`，用途是跨 session 保留專案知識。每次新對話啟動時：

1. **MEMORY.md**（索引檔）會**自動載入**到 context window（一次性，非每回合重複）
2. **CLAUDE.md**（專案指引）也會**自動載入**（同上，一次性載入）
3. 其他 memory 檔案只在**被引用時**才讀取

**重要澄清**：Claude Code 的 memory 系統**沒有 RAG（檢索增強生成）**。不會根據 frontmatter 或 type 自動向量檢索。機制是：MEMORY.md 全量載入 → agent 看到索引描述 → 自主決定讀哪個檔案。因此 MEMORY.md 的 File Index 描述品質直接決定 agent 是否能找到正確的 memory。

### Memory 檔案的類型規範

- **MEMORY.md**: 純索引檔，只放連結 + 簡短描述，不放實質內容
- **個別 memory 檔**: 帶 frontmatter（name/description/type），包含實質內容
- **type 分類**: `user`（使用者資訊）、`feedback`（行為修正）、`project`（專案狀態）、`reference`（外部資源指標）

---

## 2. 現狀快照

### 檔案清單

| 檔案 | 行數 | 大小 | 類型 | Frontmatter |
|------|------|------|------|-------------|
| `MEMORY.md` | 160 | 9.2KB | 索引 | 無（正確） |
| `lessons-learned.md` | 393 | 46.6KB | — | **無** |
| `delegation-patterns.md` | 144 | 7.1KB | — | **無** |
| `development-history.md` | 99 | 4.7KB | — | **無** |
| `project_frontend_issues_0312.md` | 76 | 3.7KB | project | 有 |
| `crawler-reference.md` | 65 | 3.7KB | — | **無** |
| `project_crawlee_evaluation.md` | 52 | 2.5KB | project | 有 |
| `compact-state.json` | 45 | 3.0KB | — | N/A（JSON） |
| `reference_slate_agent.md` | 16 | 0.9KB | reference | 有 |
| `feedback_e2e_testing.md` | 11 | 0.9KB | feedback | 有 |
| **合計** | **1061** | **82.3KB** | | |

### 自動載入的 token 成本

每次對話啟動自動載入（一次性，非每回合）：
- `MEMORY.md`: 160 行 → ~2,500 tokens
- `CLAUDE.md`: 196 行 → ~3,000 tokens
- **合計**: ~5,500 tokens 基礎消耗

---

## 3. 發現的問題

### P1: MEMORY.md 內容膨脹（違反規範）

**現狀**: MEMORY.md 160 行中，File Index 表佔 ~20 行，其餘 ~140 行都是**實質內容**。

**違反的規範**: "`MEMORY.md` is an index, not a memory — it should contain only links to memory files with brief descriptions."

**具體內容分佈**:

| 章節 | 行數 | 是否為索引 | 說明 |
|------|------|-----------|------|
| Quick Reference | 6 | 部分 | Python 版本、Dashboard port、session type 對照 |
| File Index | 20 | **是** | 這是正確的索引用途 |
| Zoe Plan Progress | 20 | 否 | Phase 1-4 全部 ✅ 完成的追蹤記錄 |
| Delegation Patterns 摘要 | 5 | 否 | 與 delegation-patterns.md 重複 |
| Key Lessons 摘要 | 12 | 否 | 與 lessons-learned.md 重複 |
| Infra Migration Progress | 18 | 否 | VPS IP、Docker 設定、資安加固細節 |
| 資料狀態 | 7 | 否 | Registry 數量、indexing 進度 |
| 全量 Indexing | 12 | 否 | 操作說明、resume 機制、GPU 溫控 |
| Crawler 自動化 | 6 | 否 | GCP cron 設定 |
| Login System | 23 | 否 | Branch info、FE 修復改動清單 |
| User Data 上傳 | 7 | 否 | 規劃資訊 |

**風險如果不改**: 每次對話多載入 ~2,000 tokens 的非索引內容。隨專案成長會持續膨脹。

### P2: MEMORY.md 與 CLAUDE.md 重複

以下資訊同時存在於兩個自動載入的檔案：

| 資訊 | MEMORY.md 位置 | CLAUDE.md 位置 |
|------|---------------|---------------|
| Python 3.11 規定 | Quick Reference | §重要開發規則 > Python 版本 |
| Registry ~2.37M 筆 | 資料狀態 | §目前工作 |
| 全量 Indexing 進度 | 全量 Indexing 章節 | §目前工作 |
| Zoe Plan Phase 1-4 完成 | Zoe Plan Progress | §目前工作 |
| VPS 部署完成 | Infra Migration | §目前工作 |

### P3: compact-state.json 完全過時

**內容**: Zoe Plan Phase 1 的工作狀態追蹤。

**過時證據**:
- `progress.backfill_completed.M5_output`: "NOT STARTED"（實際 Phase 1-4 全完成）
- `progress.delegation_patterns`: "NOT STARTED"（實際已完成）
- `next_steps[0]`: "Retry Notion API to write M3" — 2026-03-02 的待辦
- JSON 格式不符合 memory 規範（應為 Markdown + frontmatter）

**風險如果刪除**: 無。所有有價值資訊已在 `delegation-patterns.md` 和 `docs/decisions.md`。

### P4: lessons-learned.md 過度集中（46.6KB）

**現狀**: 31+ 條 lessons，393 行，全部在一個檔案。

**按主題分佈**:
- Crawler engine/registry/parser: ~15 條
- VPS/Docker/部署/資安: ~9 條
- 通用原則 + embedding/DB + 開發環境 + E2E: ~7 條

**問題**: CLAUDE.md 的 debug 規則強制「先讀 lessons-learned.md」。這意味著**每次 debug 任務都會讀取 46KB（~15,000 tokens）**，即使只是修一個 CSS bug。拆分後可改為「讀相關模組的 lessons」，只消耗 ~5,000 tokens。

### P5: 過時的 project memory

| 檔案 | 狀態 |
|------|------|
| `project_frontend_issues_0312.md` | FE-1~6 全部 FIXED。SR-1~3 標注「明天查」但已是 03-13。 |
| `project_crawlee_evaluation.md` | 決策已做（不採用），測試數據是一次性的。 |

### P6: 缺少 frontmatter

| 檔案 | 建議 type |
|------|-----------|
| `lessons-learned.md` | feedback |
| `development-history.md` | project |
| `crawler-reference.md` | reference |
| `delegation-patterns.md` | reference |

### P7: 內容重複（跨檔案）

| 內容 | 出現位置 1 | 出現位置 2 |
|------|-----------|-----------|
| E2E 測試策略（40 行） | `delegation-patterns.md` §E2E 測試策略 | `feedback_e2e_testing.md` |
| Login FE 改動清單 | `MEMORY.md` §Login System | `project_frontend_issues_0312.md` |
| Delegation Patterns 摘要 | `MEMORY.md` §Delegation Patterns | `delegation-patterns.md` 本身 |
| Key Lessons top 10 | `MEMORY.md` §Key Lessons | `lessons-learned.md` 本身 |

---

## 4. 優化建議（v2 — 整合外部審查）

### 建議 A: MEMORY.md 瘦身 + File Index 加觸發提示 ★P0

**目標**: 從 160 行降至 ~45 行，只保留索引功能。

**保留**:
- File Index 表（更新指標，**加觸發提示**）
- Quick Reference 中不在 CLAUDE.md 的項目（Dashboard port、CURL_CFFI/AIOHTTP sources 對照、python -m 用法、Windows paths）

**移除並轉移**:
- Zoe Plan Progress → 已在 `docs/archive/plans/zoe.md`
- Delegation Patterns 摘要 → `delegation-patterns.md` 已有
- Key Lessons 摘要 → 拆分後的 lessons 各檔已有
- Infra Migration Progress → 拆到新檔 `project_infra_vps.md`
- 資料狀態 + 全量 Indexing → 拆到新檔 `project_data_status.md`
- Crawler 自動化 → 合併到 `crawler-reference.md`
- Login System → FE 細節歸檔，系統狀態已在 CLAUDE.md
- User Data 上傳 → 拆到 `project_user_data_migration.md`

**v2 新增：File Index 觸發提示**

外部審查指出：瘦身後如果 File Index 描述太簡短，新 session 的 agent 可能不知道什麼時候該去讀。因此 File Index 的描述必須包含觸發條件。

錯誤寫法：
```
| 資料狀態 | `project_data_status.md` |
```

正確寫法：
```
| 資料狀態 | `project_data_status.md` — Registry/Indexing/VPS DB 最新數字。**Crawler 或 DB 任務前必讀** |
```

**v2 新增：狀態檔記「查詢方法 + 上次確認數字」**

外部審查指出：Memory 裡寫死的數字一定會過時。但本專案查詢 registry 需連桌機 SQLite、indexing 進度需查 `.indexing_done`，不是一條指令就能跑。

折衷方案：在 `project_data_status.md` 中記錄：
1. **如何查詢最新數字**的指令/路徑
2. **上次確認的數字 + 日期**（讓 agent 知道可能過時）

**Before (160 行) → After (~45 行)**

**token 節省**: ~1,800 tokens/session

**風險評估**:
- LOW: 移除的內容轉移到獨立檔案，不會丟失
- MEDIUM: 新 session 不自動看到 Infra/VPS 資訊 → 用 File Index 觸發提示緩解

### 建議 B: 刪除 compact-state.json ★P0

**理由**: Phase 1-4 全部完成。所有有價值資訊已在其他檔案。JSON 格式不符合 memory 規範。

**風險評估**: NONE — 內容 100% 過時

### 建議 C: 拆分 lessons-learned.md 為 3 檔 ★P0

**v1 → v2 變更**: 從「暫不拆（建議 G，低優先）」提升為 P0。

**原因**：
CLAUDE.md 的 debug 規則寫「先讀 lessons-learned.md」，強制每次 debug 吃 46KB（~15,000 tokens）。拆分後可改為「讀相關模組的 lessons」，只吃 ~5,000 tokens。這是 debug session 最大的 token 節省點。

**拆分方案**:

| 新檔案 | 內容 | 估算大小 |
|--------|------|---------|
| `lessons-crawler.md` | Crawler engine/parser/registry/dashboard 相關 (~15 條) | ~20KB |
| `lessons-infra-deploy.md` | VPS/Docker/部署/資安 (~9 條) | ~15KB |
| `lessons-general.md` | 通用原則 + embedding/DB + 開發環境 + E2E (~7 條) | ~10KB |

**命名說明**: 使用 `lessons-` prefix 而非 Gemini 建議的 `feedback_` prefix。理由：這些不全是 CEO 對 agent 行為的修正（feedback），很多是技術事實發現。`lessons-` 更準確反映內容本質。

**跨模組 lesson 處理**: "Silent fail 是最危險的 bug" 等通用原則放入 `lessons-general.md`。各模組檔案開頭加一行「通用教訓見 `lessons-general.md`」。

**連動修改**: CLAUDE.md 的 debug 規則需同步更新：
```
# Before
2. 再讀 lessons-learned.md（歷史問題/解法記錄）

# After
2. 根據問題模組讀取對應 lessons 檔案：
   - Crawler 相關 → lessons-crawler.md
   - 部署/VPS/資安 → lessons-infra-deploy.md
   - 其他 → lessons-general.md
```

**風險評估**:
- LOW: 內容不變，只是重新分檔
- MEDIUM: 新增 lesson 時需判斷放哪個檔案 → 用 MEMORY.md 的 File Index 明確對應

### 建議 D: CLAUDE.md「目前工作」精簡 ★P1

**v2 新增**（源自外部審查建議，但 Zoe 拒絕了 50 行目標）。

**外部建議**: CLAUDE.md 壓縮至 50 行。
**Zoe 判斷**: **拒絕 50 行目標**。

CLAUDE.md 中不可刪除的內容：
- 架構概述 + 關鍵檔案對應表（25 行）— agent 導航核心
- 程式碼索引工具規則（15 行）— 強制工作流程
- 文件查詢指令表（15 行）— 防止 agent 盲目探索
- 模組開發狀態表（12 行）— 快速定位
- 重要開發規則（65 行）— 核心行為規範

光這些就 132 行。砍到 50 行 = 移除導航表和查詢指令 → agent 會開始 `ls` 和 `grep` 全目錄，浪費更多 token。

**實際可精簡的部分**: 「目前工作」章節的 10 個 ✅ 已完成項（~15 行），保留當前 blocker + 最近 2-3 項即可，其餘移到 `docs/archive/completed-work.md`。

**token 節省**: ~200 tokens/session（相對於建議 A/C 的節省較小）

### 建議 E: 清理 project_frontend_issues_0312.md ★P2

**Before** (76 行): FE-1~6 完整修復記錄 + SR-1~3 待查
**After** (~25 行): 一行摘要「FE-1~6 全部 FIXED」+ 保留 SR-1~3

**風險評估**: LOW — FE 修復細節在 git history 可找回

### 建議 F: 補 frontmatter ★P2

為 4 個缺 frontmatter 的檔案補上 3 行 header。

**v1 → v2 說明**: 外部審查建議提升為高優先（理由：Claude Code 用 frontmatter 做 RAG）。Zoe 判斷：**維持中優先**。Claude Code 沒有 RAG，frontmatter 的實際用途是自我文檔化，不影響檢索行為。但拆分 lessons-learned 時會自然補上新檔案的 frontmatter。

**風險評估**: NONE

### 建議 G: 消除跨檔案重複 ★P2

- `delegation-patterns.md` 的 E2E 測試策略（40 行）改為指向 `feedback_e2e_testing.md`
- MEMORY.md 瘦身（建議 A）自然解決其他重複

### 建議 H: 精簡 project_crawlee_evaluation.md ★P3

**Before** (52 行): 完整評估 + 測試數據 + DX 觀察
**After** (~15 行): 決策（不採用）+ 理由 + 關鍵結論

---

## 5. 不建議改動的項目

| 項目 | 理由 |
|------|------|
| `development-history.md` | 內容完整且穩定，不需修改 |
| `crawler-reference.md` | 操作手冊，內容精確且常用（Crawler 自動化資訊將合併入） |
| `delegation-patterns.md` 主體 | 結構清晰，派工時必讀 |
| `reference_slate_agent.md` | 小且有效，純追蹤用 |
| `feedback_e2e_testing.md` | 符合規範的 feedback memory |
| CLAUDE.md 架構表/查詢指令/開發規則 | 核心導航，不可刪除 |

---

## 6. 執行順序（v2 最終版）

| 順序 | 優先級 | 動作 | token 影響 |
|------|--------|------|-----------|
| 1 | ★P0 | 刪除 `compact-state.json` | 消除過時檔案 |
| 2 | ★P0 | MEMORY.md 瘦身至 ~45 行 + File Index 加觸發提示 | -1,800 tokens/session |
| 3 | ★P0 | 拆分 `lessons-learned.md` 為 3 檔 + 更新 CLAUDE.md debug 規則 | -10,000 tokens/debug session |
| 4 | ★P1 | CLAUDE.md「目前工作」精簡已完成項 | -200 tokens/session |
| 5 | ★P2 | 清理 `project_frontend_issues_0312.md` | 減少過時資訊 |
| 6 | ★P2 | 補 frontmatter + 消除跨檔案重複 | 一致性提升 |
| 7 | ★P3 | 精簡 Crawlee 評估 | 低 ROI |

### 預估效果

- **每 session 基礎消耗**: ~5,500 → ~3,700 tokens（-33%）
- **debug session 額外消耗**: ~15,000 → ~5,000 tokens（-67%）
- **每 session 總節省**: ~2,000-12,000 tokens（視任務類型）

---

## 7. 外部審查回應記錄

### 第一輪審查 (Gemini, 2026-03-13)

| Gemini 建議 | Zoe 判斷 | 理由 |
|-------------|---------|------|
| File Index 加觸發提示 | **接受** | 零成本高回報，防止情境斷層 |
| 記查詢方法而非寫死數字 | **部分接受** | 原則對，但本專案查詢不便，折衷為「方法 + 上次數字」 |
| 強制拆分 lessons-learned（P0） | **接受拆分，修正命名** | token 節省確實顯著；但用 `lessons-` 非 `feedback_`，且理由非 RAG 而是 token 成本 |
| CLAUDE.md 壓到 50 行（P0） | **拒絕目標值，接受方向** | 50 行會失去關鍵導航表；只精簡「已完成項」（~15 行） |
| Frontmatter 提升為高優先 | **維持中優先** | Claude Code 無 RAG，frontmatter 是好習慣但不影響檢索 |
| 估算 40-50% token 節省 | **修正為 33-67%** | 基礎消耗降 33%，debug session 降 67%，視任務而定 |

### Gemini 的技術誤解（記錄，供後續參考）

1. **「Claude Code 用 frontmatter 做 RAG」** — 不正確。Claude Code 的 memory 沒有向量檢索，MEMORY.md 是全量載入的純文字索引
2. **「CLAUDE.md 每回合都消耗」** — 不正確。CLAUDE.md 是 system prompt，每次對話載入一次，不按回合計費
3. **「Context Dilution 讓 LLM 忽略關鍵教訓」** — 過度誇大。Claude 的 200K context window 中，15K tokens 不會造成嚴重注意力稀釋，真正問題是 token 成本

---

## 8. 給審查 Agent 的問題（v2）

1. **拆分 lessons-learned 為 3 檔的分類是否合理？** Crawler / Infra-Deploy / General 三分法是否有更好的切法？跨模組的通用原則（如 "Silent fail"）放 general 是否正確？
2. **MEMORY.md File Index 的觸發提示措辭是否足夠？** 「任務前必讀」是否太強（導致不必要的讀取）或太弱（agent 仍然忽略）？
3. **CLAUDE.md 不做激進瘦身的判斷是否正確？** 132 行的「不可刪除」內容中，是否有可以進一步精簡但 Zoe 沒注意到的部分？
4. **project_data_status.md 用「查詢方法 + 上次數字」的折衷方案，是否有更好的做法？**
5. **整體方案是否有遺漏的風險？** 例如：拆分後 CLAUDE.md 的 debug 規則指向 3 個檔案，agent 可能讀錯檔？

---

*v1 產出時間: 2026-03-13*
*v2 更新時間: 2026-03-13（整合 Gemini 審查意見 + Zoe CTO 判斷）*
*所有檔案大小和行數為實測值*
