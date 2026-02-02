"""Reset e2e-checklist.md — 全部重置為未完成狀態。跨輪記錄在 e2e-findings.md，不受影響。"""
from pathlib import Path

CHECKLIST = Path(__file__).parent / "e2e-checklist.md"

TEMPLATE = """\
# E2E Verification Checklist

> 自動化驗證清單 — Claude Code Loop 使用
> 每完成一項，改為 [x] 並附上結果摘要
> Stable 項目（見 findings.md）直接標記 [x] SKIP (STABLE)
> 跨輪次記錄請見 tests/e2e-findings.md

---

## I. 前端 UI/UX 基礎

- [ ] **T01** 三種模式切換（新聞搜尋 / 進階搜尋 / 自由對話）
- [ ] **T02** Session 切換是否正常
- [ ] **T03** Session 拖曳到資料夾
- [ ] **T04** 來源篩選面板開關與選擇
- [ ] **T05** 問答紀錄載入/顯示
- [ ] **T06** 釘選功能（釘選/取消/跨 session 保持）
- [ ] **T07** 介面之間切換流暢度（模式切換時 UI 狀態正確）

## II. 搜尋核心流程

- [ ] **T08** 一般新聞搜尋 → SSE streaming → 結果卡片顯示
- [ ] **T09** 進階搜尋（Deep Research）完整流程
- [ ] **T10** 自由對話基本功能
- [ ] **T11** Deep Research 後 → 自由對話 follow-up

## III. Bugfix Phase 1 驗證（Prompt + 輕量前端）

- [ ] **T12** Bug #1：自由對話問「今天幾月幾號」→ 回答正確日期 2026-01-31
- [ ] **T13** Bug #3：自由對話問「為什麼只有某天的新聞」→ 不合理化，提到資料庫收錄限制
- [ ] **T14** Bug #9：自由對話問新聞問題 → 不說「無法存取即時新聞」
- [ ] **T15** Bug #24：自由對話回覆有 Markdown 排版（段落、列表、粗體）
- [ ] **T16** Bug #10：輸入法 composing 時 Enter 不誤觸搜尋（檢查 JS 程式碼中有 isComposing）
- [ ] **T17** Bug #13：private:// 引用顯示為不可點擊標記（檢查 addCitationLinks 程式碼）
- [ ] **T18** Bug #22：深度研究引用格式自然通順

## IV. Bugfix Phase 2 驗證（前端架構）

- [ ] **T19** Bug #17：KG 知識圖譜收起/展開（圖形模式 & 列表模式）
- [ ] **T20** Bug #23：暫停按鈕 + cancelAllActiveRequests 存在
- [ ] **T21** Bug #25：引用數字超出來源數量時降級顯示（非純文字）

## V. Bugfix Phase 3 驗證（後端架構）

- [ ] **T22** Bug #6：時間範圍解析（中文數字 + prefix）
- [ ] **T23** Bug #11+16：Retriever 時間過濾機制存在
- [ ] **T24** Bug #18-20：記者文章搜尋 author filter

## VI. Bugfix Phase 4-5 驗證

- [ ] **T25** Bug #2：釘選文章注入 Free Conversation（擴展 pinnedNewsCards 結構）
- [ ] **T26** Bug #4+5：深度研究歧義檢測（Clarification 選項有自由輸入 + 直接開始按鈕）
- [ ] **T27** Bug #7：紫色虛線標記 AI 知識
- [ ] **T28** Bug #14：摘要回饋 👍👎 按鈕彈出對話框
- [ ] **T29** Bug #15：股票查詢 Tier 6 API

## VII. 後端穩定性

- [ ] **T30** Qdrant 向量搜尋回應正常（無 timeout error）
- [ ] **T31** Error handling 優雅降級（server log 無 silent fail）
"""


if __name__ == "__main__":
    CHECKLIST.write_text(TEMPLATE, encoding="utf-8")
    count = TEMPLATE.count("- [ ]")
    print(f"Checklist reset: {CHECKLIST}")
    print(f"Total items: {count} (all unchecked)")
