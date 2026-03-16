# UI Redesign Plan — 視覺品牌化

> Branch: `feature/ui-redesign`
> 建立日期: 2026-03-13
> Design 來源: `demo/260312/` (Figma mockup + design notes)

## 目標

純視覺換皮，不改功能邏輯。從藍灰工具風格 → 金炭品牌化（讀豹/雲豹主題）。

## Design Spec 摘要

### 色盤（5色 + 白）
| 用途 | 舊值 | 新值 |
|------|------|------|
| Primary | `#2563eb` | `#FDCB6E`（深金） |
| Primary hover | `#1d4ed8` | `#FFEAA7`（淺金） |
| Text/Dark | `#1a1a1a` | `#2D3436`（深炭） |
| Border/Gray | `#e5e5e5` | `#B2BEC3`（灰） |
| Background | `#f5f5f5` | `#FFEAA7` 或白 |

### 字體
- 主字體：Noto Sans TC Medium（一般文字 16px）
- 小字：Noto Sans TC Regular（10px）
- 載入方式：Google Fonts `<link>`

### 元件規格
| 元件 | 導角 | Margin | 其他 |
|------|------|--------|------|
| Tab selected | 10px | 上下12 左右8.5 | `#FDCB6E` 底, 2px stroke `#2D3436` |
| Tab unselected | 10px | 同上 | `#FFEAA7` 底, 1px stroke `#B2BEC3` |
| 搜尋輸入框 | 20px | 上下24 左右24 | 白底 |
| 模式 tabs | 10px | 上下8 左右8 | |

### 素材（`demo/260312/`）
- BG.png — 報紙背景
- Banner.png — 深色搜尋欄頭（含腳印）
- Leopard.png — 雲豹吉祥物
- Tail.png — 尾巴
- Paw.png — 白色腳印
- Left_Bar.png — 左側欄紋理
- B_Black.png — 黑色書籤/緞帶（右側 tab）
- Icons: Filter, New, Setting, Share, Back, Folder(黑/白), History(黑/白)

---

## Phase 1: CSS 變數換色盤 + 字體

**範圍**: `news-search.css` `:root` + `news-search-prototype.html` `<head>`
**風險**: 零（不動 HTML 結構、不動 JS）

### 修改項目
1. `:root` CSS 變數對映（見上方色盤表）
2. `body` font-family → `'Noto Sans TC', sans-serif`
3. HTML `<head>` 加 Google Fonts link
4. `body` background 顏色調整
5. 字體大小：`--font-size-lg: 16px`（已是 16px，確認不需改）

### 驗證
- 開 server，確認整站變色
- 三種搜尋模式各點一次確認不壞

---

## Phase 2: 首頁主視覺（Banner + 吉祥物 + 背景）

**範圍**: `news-search-prototype.html` `#initialState` 區域 + `news-search.css` 新增樣式
**風險**: 低（只加不改既有結構）

### 修改項目
1. 主內容區背景：`BG.png` 報紙拼貼
2. Banner：`Banner.png` 深色搜尋欄頭，放在搜尋框上方
3. 吉祥物：`Leopard.png` 絕對定位在 Banner 右側上方
4. 尾巴：`Tail.png` 絕對定位在搜尋框右下
5. 搜尋框改為白底、圓角 20px
6. 模式 tabs 改為新樣式（導角 10, 金色系）
7. 搜尋按鈕改為 `#2D3436` 深色底 + 白字
8. Logo 區域更新（可能改品牌名「讀豹」）

### 注意
- 不移動不刪除 `#initialState` 既有子元素
- 在其內部新增包裝用的 wrapper div
- 素材路徑：`/static/demo/260312/XXX.png`（或搬到 `/static/images/`）

### 驗證
- 首頁視覺對照 Figma mockup
- 搜尋功能正常

---

## Phase 3: 左側欄 + 右側欄視覺

**範圍**: CSS + HTML icon 路徑
**風險**: 中低（動佈局但不動 ID/class）

### 修改項目
1. 左側欄背景：`Left_Bar.png` 紋理
2. 左側欄按鈕 icon：emoji → 自訂 icon img
   - 收回：Icon_back.png
   - 分享：Icon_share.png
   - 新對話：Icon_New.png
   - 歷史：Icon_History_Black.png
   - 資料夾：Icon_Folder_Black.png
   - 設置：Icon_setting.png
3. 左側欄 margin 依 design note（24/16/10/8/4）
4. 右側 tab 換書籤造型（B_Black.png 背景）
5. 右側 tab 文字改為垂直排列

### 注意
- 不改 element ID（`leftSidebar`, `btnCollapseSidebar` 等）
- 不改 class name（JS 有用到的）
- 只加新 class 輔助樣式

### 驗證
- 側邊欄收合/展開正常
- 右側各 tab 開啟/關閉正常
- 來源篩選 checkbox 正常

---

## Phase 4: 按鈕/Tab/卡片細節

**範圍**: CSS
**風險**: 低

### 修改項目
1. 文章卡片套新色盤
2. Deep Research 報告套新色盤
3. Loading spinner 顏色
4. Modal 對話框套新色盤
5. 收尾：檢查所有硬編碼顏色，確認都用 CSS 變數

### 驗證
- 端到端驗證所有頁面狀態

---

## 安全原則

1. **不改任何 element ID**
2. **不改 JS 依賴的 class name**
3. **只加新 class，不改舊 class**
4. **每 Phase 完成後開 server 驗證**
5. **每 Phase 完成後 commit**
