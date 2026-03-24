---
name: User Data 上傳功能 PostgreSQL 遷移規劃
description: User Data 功能的 PostgreSQL 遷移計畫與資安問題。User Data 相關開發時讀取。
type: project
---

## User Data 上傳功能 — PostgreSQL 遷移規劃（2026-03-07）

- **狀態**: Login 已合併，可推進
- 現有功能完整（upload/chunking/Qdrant vector search）但有 CRITICAL 資安漏洞
- VPS 500 根因：Docker 路徑計算溢出 + 無 Qdrant
- **決策**: 獨立表（user_sources/user_documents/user_chunks）、1024D Qwen3、PostgreSQL-only
- **資安 6 個 CRITICAL/HIGH**: T1 無認證、T2 路徑穿越、T4 MIME 未驗證、T5 租戶隔離、T6 無速率限制、T7 處理炸彈
- **詳細**: `docs/decisions.md` + agent transcript (2026-03-07)
