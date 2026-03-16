# Context Hub — 第三方 API 文件查詢

> 使用 context-hub MCP server 查詢經過整理的 API 文件，避免依賴訓練資料的過時知識。

## 觸發時機

當你需要使用第三方 library 的 API 且不確定用法時（尤其是有版本變化風險的 library），用 context-hub 查詢。

**適用**：openai SDK、qdrant-client、redis、stripe、firebase、anthropic SDK 等 50+ 常見服務
**不適用**：專案內部程式碼（用 `python tools/indexer.py --search`）、專案架構（讀 `docs/reference/systemmap.md`）

## 工作流程

### Step 1: 搜尋

用 `chub_search` MCP tool 搜尋關鍵字：

```
chub_search: query="openai"
```

從結果中找到正確的 doc ID（如 `openai/chat`）。

### Step 2: 取得文件

用 `chub_get` MCP tool 取得文件，指定語言：

```
chub_get: id="openai/chat", lang="py"
```

### Step 3: 使用文件

根據文件寫程式碼。**不要依賴記憶中的 API 用法** — 用文件說的。

### Step 4: 記錄發現

如果發現文件沒提到的 gotcha（版本怪癖、workaround、專案特定細節），用 `chub_annotate` 記錄：

```
chub_annotate: id="openai/chat", note="gpt-5.1 需用 Responses API (client.responses.create)，非舊的 chat.completions.create"
```

Annotation 是本地的、跨 session 持久的，下次 `chub_get` 自動帶出。

### Step 5: 回饋（可選）

文件品質好或壞，回報給維護者：

```
chub_feedback: id="openai/chat", rating="up"
chub_feedback: id="openai/chat", rating="down", label="outdated"
```

## NLWeb 常用查詢

| 用途 | Doc ID | 語言 | 說明 |
|------|--------|------|------|
| LLM API（Ranking/Reasoning/Query Analysis） | `openai/chat` | py | 我們全線用 OpenAI，gpt-5.1 Responses API |
| Vector DB（legacy） | `qdrant/vector-search` | py | 遷移中，但 indexing 仍用 |
| Cache | `redis/key-value` | py | 快取層 |

## 未收錄的 library

以下我們常用但 context-hub 尚未收錄，需直接查官方文件：
- **psycopg3** — PostgreSQL async driver（我們的主力 DB client）
- **aiohttp** — HTTP server + client（我們的 web framework）
- **curl_cffi** — Crawler 用的 HTTP client
- **pg_bigm** — PostgreSQL 全文搜尋（bigram）
- **instructor** — Structured LLM output（TypeAgent 用）

## 快速參考

| 目標 | MCP Tool |
|------|----------|
| 列出所有可用文件 | `chub_search` (無 query) |
| 搜尋特定 library | `chub_search: query="stripe"` |
| 取得 Python 文件 | `chub_get: id="stripe/api", lang="py"` |
| 取得所有檔案 | `chub_get: id="openai/chat", lang="py", full=true` |
| 記錄踩坑心得 | `chub_annotate: id="openai/chat", note="..."` |
| 查看所有筆記 | `chub_annotate: mode="list"` |
| 回報文件品質 | `chub_feedback: id="openai/chat", rating="up"` |
