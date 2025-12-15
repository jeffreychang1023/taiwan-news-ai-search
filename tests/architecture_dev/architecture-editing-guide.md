# Architecture.html 編輯指南

## 🎯 新增功能

### 1️⃣ 關係編輯功能（Edge Editing）

在編輯模式中，您可以建立和刪除節點之間的連線。

#### 新增 Edge（連線）

1. 進入編輯模式（點擊 🖊️ 編輯模式）
2. **按住 Shift 鍵 + 點擊第一個節點**（起點）
   - 節點會變成金色高亮，表示已選擇
3. **按住 Shift 鍵 + 點擊第二個節點**（終點）
   - 自動建立連線
   - 選擇狀態自動清除

#### 取消選擇

- **按住 Shift 鍵 + 點擊同一個節點**（已選擇的節點）
- 選擇狀態會被清除

#### 刪除 Edge（連線）

1. 進入編輯模式
2. **直接點擊連線**（曲線）
   - 連線在編輯模式下會變粗，方便點擊
   - 滑鼠移到連線上會變紅色
3. 確認對話框會顯示起點和終點
4. 點擊「確定」即可刪除

### 2️⃣ 儲存佈局功能（Save Layout to HTML）

將目前的節點位置、連線、模組框永久儲存到 HTML 檔案中。

#### 使用步驟

1. **編輯完成後**，進入編輯模式
2. 點擊 **💾 儲存佈局到 HTML** 按鈕
3. 瀏覽器會下載 `layout-data-for-save.json` 檔案
4. **將檔案移到 `static/` 資料夾**
5. 執行 Python script（兩種方式任選其一）：
   ```bash
   # 方式 1: 從 scripts 資料夾執行
   cd scripts
   python save_layout_to_html.py

   # 方式 2: 從專案根目錄執行
   python scripts/save_layout_to_html.py
   ```
6. Script 會顯示節點/連線數量，確認後輸入 `yes`
7. 完成！檔案會自動備份為 `architecture.html.backup-before-save`

## 🔧 操作快速參考

### 編輯模式快捷操作

| 操作 | 方式 |
|------|------|
| 拖曳節點 | 點住節點並拖曳 |
| 拖曳模組框 | 點住模組框並拖曳 |
| 調整模組框大小 | 拖曳四個角落的調整點 |
| 選擇節點（建立連線用） | **Shift + 點擊** |
| 建立連線 | **Shift + 點擊** 兩個節點 |
| 刪除連線 | 點擊連線 |
| 編輯節點內容 | 點擊節點右上角的 `i` 圖示 |
| 新增節點 | 點擊 ➕ 新增節點 |

### 非編輯模式

| 操作 | 方式 |
|------|------|
| 查看節點詳情 | 點擊節點 |
| 切換工作流程 | 點擊上方的 workflow 按鈕 |
| 匯出 JSON | 點擊 📥 匯出 JSON |
| 匯入 JSON | 點擊 📤 匯入 JSON |

## 💡 提示與技巧

### Edge 編輯提示

- ✅ **Shift + 點擊**是建立連線的關鍵
- ✅ 連線會自動檢查重複，不會建立重複的連線
- ✅ 在編輯模式下，連線會變粗且可點擊
- ✅ 滑鼠移到連線上會變紅色，方便識別

### 儲存提示

- ✅ 每次儲存前都會自動建立備份
- ✅ JSON 檔案可以先檢查再寫入 HTML
- ✅ Script 會正確處理換行符，不會破壞 HTML 檔案
- ✅ 儲存後可以刪除 `layout-data-for-save.json`

### 安全建議

- 🔒 重要修改前先匯出 JSON 備份
- 🔒 定期使用 Git 提交變更
- 🔒 測試功能時使用 workflow5（系統全貌）

## 🐛 疑難排解

### 問題：點擊節點沒有選擇

**解決方案**：確認您按住了 **Shift 鍵**再點擊節點。

### 問題：無法點擊連線

**解決方案**：
1. 確認在編輯模式
2. 連線在編輯模式下會變粗，方便點擊
3. 嘗試點擊連線的中間部分

### 問題：Python script 找不到 JSON 檔案

**解決方案**：
1. 確認 `layout-data-for-save.json` 在 `static/` 資料夾
2. 確認已在瀏覽器中點擊「💾 儲存佈局到 HTML」下載檔案
3. 確認從正確的目錄執行 script（`scripts/` 或專案根目錄）

### 問題：儲存後 HTML 檔案損壞

**解決方案**：
1. 使用自動建立的備份：`static/architecture.html.backup-before-save`
2. 或使用最初的備份：`static/architecture.html.backup`
3. 複製備份檔案覆蓋損壞的檔案

## 📁 相關檔案

- `static/architecture.html` - 主要視覺化檔案
- `scripts/save_layout_to_html.py` - 儲存佈局的 Python script
- `static/layout-data-for-save.json` - 臨時 JSON 檔案（儲存時生成，需手動移到此處）
- `static/architecture.html.backup` - 初始備份
- `static/architecture.html.backup-before-save` - 儲存前備份

## ✨ 更新日誌

### 2025-01-XX - 新增編輯功能

- ✅ 新增 Edge 建立功能（Shift + 點擊兩個節點）
- ✅ 新增 Edge 刪除功能（點擊連線）
- ✅ 新增儲存佈局到 HTML 功能
- ✅ 新增 Python script 處理換行符問題
- ✅ 改善編輯模式視覺回饋（金色高亮、紅色 hover）
