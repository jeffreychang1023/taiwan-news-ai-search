---
name: 前端除錯教訓
description: CSS、JS、瀏覽器行為、快取、前端 UX 相關的除錯教訓。前端問題優先閱讀。
type: feedback
---

## CSS

### CSS selector 對不上 JS 動態渲染元素 — 必須查 JS 原始碼確認 class name
**問題**：CSS 用 `.session-item` 作為 selector，但 session items 是 JS 動態渲染的，實際 class 是 `left-sidebar-session-item`。CSS 規則完全沒生效。
**解決方案**：**靜態 HTML 中找不到的元素，搜尋 JS 中的 `createElement` / `innerHTML` / template literal 確認實際 class name。**
**信心**：高
**日期**：2026-03

### CSS opacity 繼承導致 hover 閃爍 — 直接移除
**問題**：`.left-sidebar-session-item:hover` 加 `opacity: 0.85`，子元素 hover 觸發重繪 → 閃爍迴圈。
**解決方案**：直接移除 hover 效果 + 相關 transition。
**信心**：高
**日期**：2026-03

### CSS `!important` override 會覆蓋同 selector 的基礎定義
**問題**：CSS 檔案後段（~line 5400+）用 `!important` 強制覆蓋前段定義。改 base 無效。
**解決方案**：改 CSS 前搜全文，確認同 selector 所有出現位置。Phase 1-4 override 區在 line ~5300-5500。
**信心**：高
**日期**：2026-03-20

### .news-excerpt 預設 display:none — 動態 error card 要加 visible class
**問題**：Guardrail error card 用 `<div class="news-excerpt">` 顯示訊息，但 CSS 定義 `.news-excerpt { display: none }` + `.news-excerpt.visible { display: block }`。Agent E2E 用 console 報 PASS，CEO 看不到訊息。
**解決方案**：動態建含 `.news-excerpt` 的 HTML 時，必須加 `visible` class。**通則：動態建 HTML 前，查 CSS 是否有 display 條件 class。**
**信心**：高
**日期**：2026-03-20

## 瀏覽器 / 快取

### Cloudflare CDN cache 讓部署看不到效果
**問題**：push + deploy 後前端 JS/HTML 被 Cloudflare cache，新版 code 沒生效。
**解決方案**：(1) script src 加 cache buster `?v=20260320a` (2) nginx 加 `Cache-Control: no-cache` (3) 每次改前端 bump cache buster + purge Cloudflare。
**信心**：高
**日期**：2026-03-16

### 本地開發也有 cache 問題 — hard refresh 不一定夠
**問題**：修改 `news-search.js` 後 hard refresh（Ctrl+Shift+R）無效，瀏覽器仍用舊版。原因：HTML 的 `<script src>` 有 cache buster `?v=20260317e` 但沒更新到當天版本。
**解決方案**：改前端 JS/CSS 後，同步更新 `news-search-prototype.html` 的 cache buster（`?v=YYYYMMDD` + 遞增字母）。或用無痕模式測試。
**信心**：高
**日期**：2026-03-20

## JS / 前端架構

### EventSource 無法讀 error response body — 改用 fetch + ReadableStream
**問題**：DR 用 `new EventSource(url)` 做 SSE。Server 回 429/503 時，EventSource 只觸發 `onerror`，不暴露 HTTP status 或 response body。具體錯誤訊息完全丟失。
**解決方案**：改為 `fetch()` + `response.body.getReader()`（跟 search mode 同 pattern）。fetch 可以先檢查 `response.status`，再進入 SSE parsing。
**信心**：高
**日期**：2026-03-20

## 開發環境

### PowerShell `set` 不是設環境變數
**問題**：PowerShell 的 `set` 是 `Set-Variable`（程式變數），不會進 `os.environ`。Server 讀不到 env var。
**解決方案**：PowerShell 用 `$env:VAR="value"`。CMD 用 `set VAR=value`。
**信心**：高
**日期**：2026-03-20

### Claude Code 不應啟動 server — 殭屍 process 管理不可靠
**問題**：從 Bash tool 用 `&` 背景啟動 server，累積殭屍 process 搶 port 8000。stderr 被吞（看不到 traceback）。`taskkill` 有時殺不掉。
**解決方案**：Server 由 CEO 從 PowerShell/CMD 啟動。殺 process 用 `Get-Process python* | Stop-Process -Force`。
**信心**：高
**日期**：2026-03-20

*最後更新：2026-03-20*
