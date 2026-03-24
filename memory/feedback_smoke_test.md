---
name: Smoke Test 強制驗證規則
description: 修改 Python 程式碼後必跑 smoke test，防止 skill/subagent break import chain。
type: feedback
---

修改 Python 程式碼後，必須從 code/python/ 執行 `python tools/smoke_test.py`。

**Why:** CEO 反映 simplify、code-reviewer 等 skill 經常 break 東西。根因是缺少自動化驗證閘門 — 改完 code 唯一的驗證是「server 跑起來沒」，沒有快速的自動檢查。

**How to apply:**
- 所有修改 Python 程式碼的 subagent prompt 結尾必須加上 smoke test 指令
- FAILED 時必須修復再重跑，不可跳過
- 例外：只改 docs/、memory/、config YAML/JSON、static/ 前端時不需要
- 詳見 delegation-patterns.md「強制驗證規則」段落
