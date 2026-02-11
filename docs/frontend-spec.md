# Frontend Specification

> 台灣新聞 AI 搜尋引擎前端功能規格書

---

## 目錄

1. [架構概覽](#1-架構概覽)
2. [檔案結構](#2-檔案結構)
3. [頁面結構](#3-頁面結構)
4. [核心功能模組](#4-核心功能模組)
5. [狀態管理](#5-狀態管理)
6. [API 整合](#6-api-整合)
7. [串流處理](#7-串流處理)
8. [樣式系統](#8-樣式系統)
9. [事件處理](#9-事件處理)
10. [LocalStorage 資料結構](#10-localstorage-資料結構)

---

## 1. 架構概覽

### 1.1 技術棧

| 技術 | 用途 |
|------|------|
| Vanilla JavaScript | 主要邏輯（無框架） |
| CSS3 + CSS Variables | 樣式系統 |
| D3.js v7 | 知識圖譜視覺化 |
| Server-Sent Events (SSE) | 串流回應 |
| LocalStorage | 客戶端資料持久化 |

### 1.2 設計原則

- **漸進式渲染**：搜尋結果、摘要、推論鏈皆採用串流式漸進渲染
- **非阻塞 UI**：所有 API 呼叫皆為非同步，支援中斷機制
- **響應式設計**：支援桌面與平板裝置
- **無障礙支援**：大字體模式、語義化 HTML

---

## 2. 檔案結構

```
static/
├── news-search-prototype.html   # 主頁面 HTML 結構
├── news-search.js               # 主要 JavaScript 邏輯 (~300KB)
├── news-search.css              # 主要樣式表 (~128KB)
├── analytics-tracker-sse.js     # 分析追蹤器
├── analytics-dashboard.html     # 分析儀表板
├── indexing-dashboard.html      # 索引儀表板
└── index.html                   # 入口重導向
```

---

## 3. 頁面結構

### 3.1 主頁面佈局

```
┌─────────────────────────────────────────────────────────────────┐
│ Header (logo, 大字體按鈕, 通知)                                   │
├──────────┬──────────────────────────────────┬───────────────────┤
│          │                                  │                   │
│  左側邊欄  │          主內容區                 │   右側 Tab 面板    │
│  (可收合)  │                                  │   (可展開/收合)    │
│          │  ┌────────────────────────────┐  │                   │
│ - 分享結果 │  │ 初始狀態 / 搜尋框 / 結果區  │  │ - 來源篩選        │
│ - 新對話   │  │                            │  │ - 我的檔案        │
│ - 歷史搜尋 │  └────────────────────────────┘  │ - 搜尋紀錄        │
│ - 資料夾   │                                  │ - 釘選新聞        │
│ - Sessions │                                  │                   │
│          │                                  │                   │
└──────────┴──────────────────────────────────┴───────────────────┘
```

### 3.2 HTML 元素 ID 對照表

| 元素 ID | 說明 | 所在區域 |
|---------|------|----------|
| `leftSidebar` | 左側邊欄容器 | 左側 |
| `rightTabsContainer` | 右側 Tab 面板容器 | 右側 |
| `initialState` | 初始歡迎畫面 | 主內容 |
| `searchContainer` | 搜尋框容器 | 主內容 |
| `loadingState` | 載入中狀態 | 主內容 |
| `resultsSection` | 搜尋結果區 | 主內容 |
| `chatContainer` | 聊天容器 (自由對話模式) | 主內容 |
| `folderPage` | 資料夾頁面 | 主內容 (覆蓋) |

---

## 4. 核心功能模組

### 4.1 搜尋模式系統

系統支援三種搜尋模式，透過 `currentMode` 變數追蹤：

| 模式 | 變數值 | 說明 | API 端點 |
|------|--------|------|----------|
| 新聞搜尋 | `search` | 快速搜尋，回傳文章列表 + 摘要 | SSE `/ask` |
| 進階搜尋 | `deep_research` | Deep Research，含推論鏈、知識圖譜 | SSE `/api/deep_research` |
| 自由對話 | `chat` | 多輪對話，支援上下文 | POST `/api/free_conversation` |

#### 4.1.1 新聞搜尋 (Search Mode)

```javascript
async function performSearch() {
    // 1. 建立 SSE 連線到 /ask
    // 2. 串流接收：articles, answer, reasoning
    // 3. 漸進式渲染文章卡片和摘要
}
```

**串流事件類型**：
- `articles` - 文章資料
- `answer_chunk` - 摘要片段
- `reasoning_chunk` - 推論片段
- `done` - 完成

#### 4.1.2 進階搜尋 (Deep Research Mode)

```javascript
async function performDeepResearch(query, skipClarification, comprehensiveSearch, userTimeRange, userTimeLabel) {
    // 1. 建立 SSE 連線到 /api/deep_research
    // 2. 處理澄清問題 (clarification)
    // 3. 串流接收研究報告
    // 4. 渲染知識圖譜、推論鏈
}
```

**輸入框位置**：進入 Deep Research 模式時，搜尋框移動到聊天區底部（與 Chat 模式相同行為），回到 Search 模式時搜尋框回歸主內容區頂部。

**進階選項**：
- 研究模式：`discovery` (廣泛探索) / `strict` (嚴謹查核) / `monitor` (情報監測)
- 知識圖譜：`kgToggle`
- 網路搜尋：`webSearchToggle`

#### 4.1.3 自由對話 (Chat Mode)

```javascript
async function performFreeConversation(userMessage) {
    // 1. POST 到 /api/free_conversation
    // 2. 維護 conversationHistory
    // 3. 支援多輪對話上下文
}
```

### 4.2 左側邊欄系統

#### 4.2.1 功能按鈕

| 按鈕 ID | 功能 | 處理函數 |
|---------|------|----------|
| `btnShareSidebar` | 分享搜尋結果 | 開啟分享 Modal |
| `btnNewConversation` | 開啟新對話 | `resetConversation()` |
| `btnHistorySearch` | 歷史搜尋 | `showHistoryPopup()` |
| `btnToggleCategories` | 資料夾系統 | `showFolderPage()` |
| `btnCollapseSidebar` | 收合側邊欄 | 隱藏側邊欄 |

#### 4.2.2 Session 列表

```javascript
// 渲染左側邊欄的 session 列表
function renderLeftSidebarSessions() {
    // 顯示最近 10 個 sessions
    // 支援拖曳到資料夾
    // 支援重新命名、刪除
}
```

### 4.3 右側 Tab 面板系統

#### 4.3.1 Tab 結構

| Tab ID | 面板 ID | 功能 |
|--------|---------|------|
| `sources` | `tabPanelSources` | 來源篩選 (Tree View) |
| `files` | `tabPanelFiles` | 我的檔案 (Tree View) |
| `history` | `tabPanelHistory` | 搜尋紀錄 |
| `pinned-news` | `tabPanelPinnedNews` | 釘選新聞 |

#### 4.3.2 來源篩選 (Source Filter)

採用 VS Code Explorer 風格的 Tree View：

```javascript
function renderSourceTreeView() {
    // 渲染資料夾結構
    // 每個來源顯示：checkbox + 主名稱 + 副資訊 (兩行)
    // 支援拖曳分類、全選/全不選
}
```

**資料結構**：
```javascript
const sourceFolders = [
    {
        id: 'folder-uuid',
        name: '資料夾名稱',
        siteNames: ['site1', 'site2'],
        collapsed: false,
        isUncategorized: false
    }
];
```

#### 4.3.3 我的檔案 (User Files)

```javascript
function renderFileTreeView() {
    // 渲染使用者上傳的檔案
    // 支援 PDF, DOCX, TXT, MD 格式
    // 顯示處理狀態：ready, processing, failed
}
```

**自動開啟**：當使用者勾選「包含文件」checkbox 時，自動呼叫 `openTab('files')` 開啟右側「我的檔案」面板。

### 4.4 搜尋結果區

#### 4.4.1 文章卡片

```javascript
function createArticleCard(article, index) {
    // 建立文章卡片 HTML
    // 包含：標題、來源、日期、摘要、相關性分數
    // 支援：釘選、複製連結
}
```

**文章資料結構**：
```javascript
{
    name: "文章標題",
    url: "https://...",
    description: "文章摘要",
    source: "來源名稱",
    date_published: "2024-01-01",
    relevance_score: 0.95,
    snippet: "AI 生成的相關片段"
}
```

#### 4.4.2 Deep Research 報告 UI 元件

**展開/折疊 Toggle**：報告頂部有單一「全部折疊/全部展開」toggle 按鈕（`addToggleAllToolbar()`），點擊切換所有章節的折疊狀態。

**進度顯示**：Deep Research 進度面板標題為「深度研究進行中」，僅顯示階段名稱（如「搜尋中...」「分析中...」），不顯示技術細節。

**參考資料**：報告末尾的引用來源列表包在可折疊 toggle 中（預設折疊），按鈕顯示「參考資料來源 (N)」，展開後顯示每條來源的完整 Title + URL。

**報告語言**：報告中所有標籤均為中文：
- 模式標籤：`discovery` → 「廣泛探索」、`strict` → 「嚴謹查核」、`monitor` → 「情報監測」
- 欄位標籤：「研究模式」「分析來源數」「時間範圍」「研究發現」等
- 信心度：「High」→「高」、「Medium」→「中」、「Low」→「低」

#### 4.4.3 摘要區

```javascript
function renderAnswerProgressive(answerData, articleCount) {
    // 漸進式渲染 AI 摘要
    // 支援 Markdown 轉 HTML
    // 支援引用連結 [1] → 點擊跳轉
}
```

#### 4.4.3 知識圖譜

```javascript
function displayKnowledgeGraph(kg) {
    // 使用 D3.js 渲染力導向圖
    // 支援：圖形視圖 / 列表視圖
    // 支援：展開/收合、隱藏/顯示
}
```

**節點類型**：
- `entity` - 實體 (人物、組織、地點)
- `event` - 事件
- `concept` - 概念
- `source` - 來源

#### 4.4.4 推論鏈

```javascript
function displayReasoningChain(argumentGraph, chainAnalysis) {
    // 渲染論證圖
    // 顯示：前提 → 推論 → 結論
    // 標示：支持/反對/中立
}
```

### 4.5 資料夾系統

```javascript
// 資料夾頁面管理
function showFolderPage() { ... }
function hideFolderPage() { ... }
function createFolder(name) { ... }
function renameFolder(folderId, newName) { ... }
function deleteFolder(folderId) { ... }
function addSessionToFolder(folderId, sessionId) { ... }
```

**資料結構**：
```javascript
const folders = [
    {
        id: 'folder-uuid',
        name: '專案名稱',
        sessionIds: ['session-1', 'session-2'],
        createdAt: 1704067200000,
        updatedAt: 1704153600000
    }
];
```

### 4.6 使用者回饋系統

```javascript
function openFeedbackModal(rating) {
    // 開啟回饋 Modal
    // rating: 'positive' | 'negative'
    // 支援選擇原因 + 文字留言
}
```

---

## 5. 狀態管理

### 5.1 全域狀態變數

| 變數名 | 類型 | 說明 |
|--------|------|------|
| `currentMode` | string | 目前搜尋模式 |
| `conversationHistory` | array | 對話歷史 |
| `sessionHistory` | array | 完整 session 資料 |
| `savedSessions` | array | 已儲存的 sessions |
| `availableSites` | array | 可用的新聞來源 |
| `selectedSites` | array | 已選取的來源 |
| `sourceFolders` | array | 來源分類資料夾 |
| `userFiles` | array | 使用者檔案列表 |
| `currentSessionId` | string | 目前 session ID |
| `currentConversationId` | string | 目前對話 ID |
| `searchGenerationId` | number | 搜尋世代 ID (用於取消) |

### 5.2 UI 狀態

| 狀態 | 控制元素 | 說明 |
|------|----------|------|
| 初始狀態 | `#initialState` | 顯示歡迎訊息 |
| 載入中 | `#loadingState` | 顯示 spinner |
| 結果區 | `#resultsSection` | 顯示搜尋結果 |
| 聊天模式 | `#chatContainer` | 顯示聊天介面 |
| 資料夾頁 | `#folderPage` | 顯示資料夾系統 |

---

## 6. API 整合

### 6.1 API 端點列表

| 端點 | 方法 | 說明 | 回應類型 |
|------|------|------|----------|
| `/ask` | GET (SSE) | 新聞搜尋 | SSE Stream |
| `/api/deep_research` | GET (SSE) | Deep Research | SSE Stream |
| `/api/free_conversation` | POST | 自由對話 | SSE Stream |
| `/sites_config` | GET | 取得網站設定 | JSON |
| `/api/user/upload` | POST | 上傳檔案 | JSON |
| `/api/user/upload/{id}/progress` | GET (SSE) | 上傳進度 | SSE Stream |
| `/api/user/sources` | GET | 取得使用者資料來源 | JSON |
| `/api/user/sources/{id}` | DELETE | 刪除使用者資料來源 | JSON |
| `/api/feedback` | POST | 提交使用者回饋 | JSON |
| `/api/analytics/event` | POST | 分析事件 | JSON |

### 6.2 SSE 串流處理

```javascript
async function handleStreamingRequest(url, query) {
    const eventSource = new EventSource(url);

    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        // 根據 data.type 分發處理
    };

    eventSource.onerror = () => {
        eventSource.close();
    };
}
```

### 6.3 搜尋取消機制

```javascript
let searchGenerationId = 0;
let currentSearchAbortController = null;
let currentSearchEventSource = null;

function cancelActiveSearch() {
    searchGenerationId++;
    if (currentSearchEventSource) {
        currentSearchEventSource.close();
    }
    if (currentSearchAbortController) {
        currentSearchAbortController.abort();
    }
}
```

---

## 7. 串流處理

### 7.1 SSE 事件類型

#### 新聞搜尋 (`/ask`)

| 事件類型 | 說明 | 資料結構 |
|----------|------|----------|
| `articles` | 文章列表 | `{ articles: [...] }` |
| `answer_chunk` | 摘要片段 | `{ chunk: "..." }` |
| `reasoning_chunk` | 推論片段 | `{ chunk: "..." }` |
| `done` | 完成 | `{}` |

#### Deep Research (`/api/deep_research`)

| 事件類型 | 說明 | 資料結構 |
|----------|------|----------|
| `clarification` | 澄清問題 | `{ questions: [...] }` |
| `status` | 狀態更新 | `{ message: "..." }` |
| `progress` | 進度更新 | `{ phase: "...", progress: 0.5 }` |
| `report_chunk` | 報告片段 | `{ chunk: "..." }` |
| `knowledge_graph` | 知識圖譜 | `{ nodes: [...], edges: [...] }` |
| `reasoning_chain` | 推論鏈 | `{ argument_graph: {...} }` |
| `sources` | 引用來源 | `{ sources: [...] }` |
| `done` | 完成 | `{ metadata: {...} }` |

### 7.2 漸進式渲染

```javascript
function renderArticlesProgressive(articles) {
    // 1. 先顯示骨架屏 (skeleton)
    // 2. 逐批渲染文章卡片
    // 3. 使用 requestAnimationFrame 優化
}

function renderAnswerProgressive(answerData) {
    // 1. 即時顯示串流文字
    // 2. 完成後轉換 Markdown → HTML
    // 3. 加入引用連結
}
```

---

## 8. 樣式系統

### 8.1 CSS 變數

```css
:root {
    /* 主色調 */
    --color-primary: #3b82f6;
    --color-primary-hover: #2563eb;

    /* 文字顏色 */
    --color-text-primary: #1f2937;
    --color-text-secondary: #4b5563;
    --color-text-muted: #9ca3af;

    /* 背景顏色 */
    --color-bg-primary: #ffffff;
    --color-bg-secondary: #f3f4f6;
    --color-bg-hover: #e5e7eb;

    /* 邊框 */
    --color-border: #e5e7eb;

    /* 陰影 */
    --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
    --shadow-md: 0 4px 6px rgba(0,0,0,0.1);
}
```

### 8.2 響應式斷點

| 斷點 | 寬度 | 說明 |
|------|------|------|
| Desktop | > 1200px | 完整三欄佈局 |
| Tablet | 768px - 1200px | 隱藏左側邊欄 |
| Mobile | < 768px | 單欄佈局 |

### 8.3 大字體模式

```css
body.large-font {
    font-size: 18px;
}

body.large-font .search-input {
    font-size: 18px;
}

body.large-font .news-card-title {
    font-size: 18px;
}

/* Deep Research 報告也受大字體影響 */
body.large-font .research-section-header .section-title {
    font-size: 20px;
}

body.large-font .research-section-content {
    font-size: 17px;
}
```

---

## 9. 事件處理

### 9.1 事件委派

```javascript
// 文章連結點擊追蹤
document.addEventListener('click', handleLinkClick);
document.addEventListener('auxclick', handleLinkClick);
document.addEventListener('contextmenu', handleLinkClick);

// Tab 面板切換
document.querySelectorAll('.right-tab-label').forEach(tab => {
    tab.addEventListener('click', () => openTab(tab.dataset.tab));
});
```

### 9.2 鍵盤快捷鍵

| 快捷鍵 | 功能 |
|--------|------|
| `Enter` | 送出搜尋 (搜尋框) |
| `Shift + Enter` | 換行 (搜尋框) |
| `Escape` | 關閉 Popup / 取消搜尋 |

### 9.3 拖曳功能

```javascript
// 來源篩選拖曳分類
container.querySelectorAll('.tree-item[draggable="true"]').forEach(item => {
    item.addEventListener('dragstart', (e) => {
        e.dataTransfer.setData('text/site-name', item.dataset.siteName);
    });
});

// Session 拖曳到資料夾
function initSidebarDragDelegation() {
    // 支援拖曳 session 到資料夾
}
```

---

## 10. LocalStorage 資料結構

### 10.1 儲存的 Key

| Key | 說明 | 資料類型 |
|-----|------|----------|
| `taiwanNewsSavedSessions` | 已儲存的 sessions | JSON Array |
| `taiwanNewsFolders` | 資料夾列表 | JSON Array |
| `taiwanNewsSourceFolders` | 來源分類資料夾 | JSON Array |
| `taiwanNewsFileFolders` | 檔案分類資料夾 | JSON Array |
| `taiwanNewsSelectedFiles` | 已選取的檔案 | JSON Array |
| `nlweb_large_font` | 大字體模式 | boolean |
| `nlweb_kg_hidden` | 知識圖譜隱藏 | boolean |
| `nlweb_session_id` | Session ID | string |

### 10.2 Session 資料結構

```javascript
{
    id: 'session-uuid',
    title: '搜尋標題',
    timestamp: 1704067200000,
    mode: 'search',
    queries: [
        {
            query: '使用者問題',
            answer: 'AI 回答',
            articles: [...],
            knowledgeGraph: {...},
            reasoningChain: {...}
        }
    ]
}
```

---

## 附錄 A：函數索引

### 搜尋相關
- `performSearch()` - 執行新聞搜尋
- `performDeepResearch()` - 執行 Deep Research
- `performFreeConversation()` - 執行自由對話
- `cancelActiveSearch()` - 取消搜尋
- `handleStreamingRequest()` - 處理 SSE 串流

### 渲染相關
- `createArticleCard()` - 建立文章卡片
- `renderArticlesProgressive()` - 漸進式渲染文章
- `renderAnswerProgressive()` - 漸進式渲染摘要
- `displayKnowledgeGraph()` - 顯示知識圖譜
- `displayReasoningChain()` - 顯示推論鏈
- `renderSourceTreeView()` - 渲染來源 Tree View
- `renderFileTreeView()` - 渲染檔案 Tree View
- `addToggleAllToolbar()` - Deep Research 報告全部展開/折疊 toggle
- `generateCitationReferenceList()` - 報告末尾可折疊引用來源列表
- `updateReasoningProgress()` - Deep Research 進度顯示（簡化版）
- `togglePrivateSources()` - 切換包含文件（自動開啟檔案面板）

### Session 管理
- `saveCurrentSession()` - 儲存目前 session
- `loadSavedSession()` - 載入 session
- `deleteSavedSession()` - 刪除 session
- `resetConversation()` - 重置對話

### 資料夾系統
- `showFolderPage()` - 顯示資料夾頁面
- `createFolder()` - 建立資料夾
- `renameFolder()` - 重新命名資料夾
- `deleteFolder()` - 刪除資料夾

### UI 控制
- `openTab()` - 開啟 Tab
- `closeAllTabs()` - 關閉所有 Tab
- `showHistoryPopup()` - 顯示歷史搜尋
- `setProcessingState()` - 設定處理中狀態

---

## 附錄 B：事件類型常數

```javascript
// SSE 事件類型
const SSE_EVENT_TYPES = {
    ARTICLES: 'articles',
    ANSWER_CHUNK: 'answer_chunk',
    REASONING_CHUNK: 'reasoning_chunk',
    CLARIFICATION: 'clarification',
    STATUS: 'status',
    PROGRESS: 'progress',
    REPORT_CHUNK: 'report_chunk',
    KNOWLEDGE_GRAPH: 'knowledge_graph',
    REASONING_CHAIN: 'reasoning_chain',
    SOURCES: 'sources',
    DONE: 'done',
    ERROR: 'error'
};

// 搜尋模式
const SEARCH_MODES = {
    SEARCH: 'search',
    DEEP_RESEARCH: 'deep_research',
    CHAT: 'chat'
};

// 研究模式
const RESEARCH_MODES = {
    DISCOVERY: 'discovery',
    STRICT: 'strict',
    MONITOR: 'monitor'
};
```

---

*最後更新：2026-02-10*
