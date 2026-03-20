# NLWeb Project Memory

> 純索引。實質內容在各專門檔案。MEMORY.md 禁止寫入實質內容。

## Quick Reference

- **Dashboard**: `python -m indexing.dashboard_server` (port 8001)
- **CURL_CFFI sources**: cna, chinatimes, einfo, esg_businesstoday, moea
- **AIOHTTP sources**: ltn, udn
- **Windows paths**: Git Bash 用 `/c/users/...`，native 用 `C:\users\...`
- **python -m**: 從 `code/python/` 目錄執行（`code` 衝突 Python built-in）

## File Index

| 需要什麼 | 讀哪裡 | 何時讀取 |
|----------|--------|---------|
| Crawler 除錯教訓 | `lessons-crawler.md` | Crawler 或 Dashboard 除錯時 |
| 部署/資安除錯教訓 | `lessons-infra-deploy.md` | VPS、Docker、SSH 除錯時 |
| Auth/Login 除錯教訓 | `lessons-auth.md` | Auth、httpOnly cookie、B2B login 除錯時 |
| 前端除錯教訓 | `lessons-frontend.md` | CSS、JS、瀏覽器 cache、前端 UX 問題時 |
| 通用除錯教訓 | `lessons-general.md` | 問題模組不明時優先讀取 |
| VPS 部署狀態 | `project_infra_vps.md` | 部署或 VPS 相關工作時 |
| DB/Indexing 狀態 | `project_data_status.md` | 修改 Crawler 寫入邏輯或確認資料庫總量時 |
| User Data 遷移規劃 | `project_user_data_migration.md` | User Data 功能開發時 |
| 前端問題追蹤 | `project_frontend_issues_0312.md` | 前端除錯時（FE-1~6 已修，SS-1~2 已修，SR-1~3 待查） |
| Crawlee 評估 | `project_crawlee_evaluation.md` | 評估新爬蟲框架時（結論：不採用） |
| 專案開發歷程 | `development-history.md` | 了解專案背景時 |
| Crawler source 操作 | `crawler-reference.md` | Crawler 操作、啟動 scan、GCP cron 相關 |
| Delegation 派工規則 | `delegation-patterns.md` | 派工 subagent 前 |
| Smoke Test 驗證規則 | `feedback_smoke_test.md` | 修改 Python 程式碼時（skill/subagent 必讀） |
| E2E 測試規則 | `feedback_e2e_testing.md` | 派 E2E 測試時 |
| Slate agent 追蹤 | `reference_slate_agent.md` | 評估 coding agent 工具時 |
| 品牌設計規範 + 審計 | `reference_brand_spec.md` | 前端品牌化工作時（Figma 5 色規範 + 違規區域清單） |
| 架構決策 | `docs/decisions.md` | 查決策理由時 |
| 系統架構 | `docs/reference/systemmap.md` | 了解模組關係時 |
| 目前工作 | `docs/status.md` | 確認專案狀態時 |
| Zoe Plan | `docs/archive/plans/zoe.md` | 查 Zoe 規劃歷程時 |
