---
name: 台灣讀豹品牌設計規範 + 前端審計
description: Figma 設計稿的 5 色品牌規範 + 未品牌化區域完整清單。前端品牌化工作時必讀。
type: reference
---

## 品牌色彩規範（來源：Figma frontpage-ui-note-1.jpg）

**只有 5 個顏色，沒有例外**：

| 色票 | Hex | 用途 |
|------|-----|------|
| 淡金 | `#FFEAA7` | 非選取狀態背景、highlight |
| 金 | `#FDCB6E` | 選取狀態、品牌主色 |
| 灰 | `#B2BEC3` | 非選取 stroke、次要邊框 |
| 炭 | `#2D3436` | 所有深色文字、選取 stroke |
| 白 | `#FFFFFF` | 打字框、卡片背景 |

- 只有在 `#2D3436` 需要加 stroke 時才用 `#000000`
- 頁面背景：`#FBF5E6`（主站用，CSS variable `--color-bg`）

### 排版
- 一般字級 16, 小字 10
- Noto Sans TC Medium（一般）/ Regular（小字）

### 元件規則
- 導角（border-radius）: **10**（一般元件）/ **20**（搜尋框）
- 選取狀態：`#FDCB6E` fill, Stroke 2px `#2D3436`
- 非選取狀態：`#FFEAA7` fill, Stroke 1px `#B2BEC3`
- Margin 標準：上下 12 左右 8.5（tab）/ 上下 8 左右 8（mode selector）/ 上下 24 左右 24（搜尋框與按鈕）

### 功能色（品牌 5 色之外的例外）
- 成功：`#059669`
- 危險：`#dc2626`
- Citation 連結：`#3498db`（藍色，CEO 確認保留藍字）
- 這些色僅限功能提示，不用於裝飾

### 品牌命名（CEO 確認 2026-03-20）
- 正式名稱：**臺灣讀豹**（用「臺」不是「台」）
- 前端所有「AI」「AI 助理」「研究助理」→ 統一用「讀豹」
- Email footer / 頁面標題等官方露出用「臺灣讀豹」

### Figma 設計稿位置
- `demo/260312/frontpage-ui-note-1.jpg` — 品牌規範 Note
- `demo/260312/frontpage-ui-note-2.jpg` — Margin 標註
- `demo/260312/frontpage-ui.jpg` — 完整首頁 mockup
- `demo/figma/` — 各頁面 Figma 截圖（模式選擇、搜尋結果等）

---

## 前端品牌審計（2026-03-19 審計 → 2026-03-20 修復）

### B1-B12：已完成（2026-03-20）

Auth 頁面 4 個 + Email 模板 5 封 + Reasoning Chain + Clarification Card + Pinned Banner + Citation URN + 進度條 + 進度訊息 — 全部品牌化完成。另外 Deep Research 進度條從 terminal 深色風改為品牌奶油底。

### 額外完成：品牌文案統一
- 全站「AI」「AI 助理」「研究助理」→「讀豹」
- 「台灣讀豹」→「臺灣讀豹」
- 頁面標題 → 「臺灣讀豹 — 新聞搜尋引擎」
- 移除所有 🤖 emoji

### 殘餘 LOW — 管理/內部（待排）

| # | 區域 | 位置 | 問題 |
|---|------|------|------|
| B13 | Org Modal 管理按鈕 | `news-search.css:5978-6056` | Flat UI 調色盤 |
| B14 | index.html spinner | `index.html:22-36` | 藍色 `#2563eb` |
| B15 | Analytics Dashboard | `analytics-dashboard.html` | 紫色漸層 |
| B16 | Indexing Dashboard | `indexing-dashboard.html` | 深藍漸層 |

### 待做（CEO 回饋）
- Loading spinner → 讀豹動畫（CEO 構想中，具體做法待定）
- ~~Citation「讀豹背景知識」字色調整為炭色~~ → 已修（2026-03-20）

### 違規色 → 正確色對照

| 違規色 | 出現位置 | 應改為 |
|--------|---------|-------|
| `#c8a96e` | Auth 頁面按鈕 | `#FDCB6E` |
| `#1a1a2e → #0f3460` | Auth 頁面背景 | `#FBF5E6` |
| `#6366f1` | Reasoning Chain | `#FDCB6E` |
| `#8b5cf6` | Citation URN | `#2D3436` |
| `#f59e0b` / `#fbbf24` | Pinned banner | `#FDCB6E` |
| `#92400e` / `#78350f` | Pinned text | `#2D3436` |
| `#667eea → #764ba2` | Analytics dashboard | `#FBF5E6` |
| `#e74c3c` / `#dc3545` / `#d63031` | Error colors | 統一 `#dc2626` |
| `#666` / `#888` / `#333` | 散落各處 | `#2D3436` 或 `#B2BEC3` |
| `#ddd` / `#e5e7eb` | 邊框 | `#B2BEC3` |
