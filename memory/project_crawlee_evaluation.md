---
name: Crawlee Python 評估
description: Crawlee (Apify) 作為爬蟲替代/補充方案的評估結果與決策
type: project
---

## 決策（2026-03-13）

**不採用 Crawlee。現有 crawler 繼續維護。**

**理由**：自製 crawler 已成熟（2.37M 筆 registry、7 parser、3 mode、subprocess isolation），全面遷移成本高且風險大。

**測試結果**：桌機測試 Crawlee vs Custom crawler — 完全相同（18/20 success, 0 blocked, 31s）。底層都是 curl_cffi + chrome110 impersonation，上層 framework 不帶來額外 anti-ban 能力。einfo 的 GCP ban 是 IP 問題，需 proxy 而非換 framework。

**DX 觀察**：Crawlee API 有不少坑（ConcurrencySettings 必須同時設 desired、timedelta 而非 int）。自製 crawler API 更直覺。

**How to apply**：新爬蟲需求時先評估是否用 Crawlee，但不重構現有系統。Crawlee 的 SessionPool error scoring 和 tiered proxy 概念值得借鑑。
