# Hybrid Search 架構改造計畫

> 2026-02-26 發現，待後續處理

## 問題

目前的 "hybrid search" 是偽 hybrid — BM25 只做 re-ranking，不做獨立 retrieval：

```
現狀（偽 hybrid）：
Vector search → 500 results → BM25 re-rank 這 500 篇 → post-filter → output
```

導致 keyword-only 查詢（如作者名「記者郭又華」）失敗：vector top 500 裡根本沒有目標文章，BM25 和 post-filter 都無用武之地。

## 正確做法

業界 hybrid search best practice — 兩路並行 retrieval + fusion：

```
Dense (vector)  → 500 results ─┐
                                ├→ Fusion (RRF / weighted) → final ranking
Sparse (BM25)   → 500 results ─┘
```

## Qdrant 支援的方案

1. **Sparse vector** — indexing 時同時存 dense + sparse vectors（SPLADE / BM42），查詢時用 `prefetch` + `Fusion.RRF`
2. **Full-text index** — 對 payload 欄位建 text index，用 `FullTextMatch` 做 keyword retrieval

兩種都讓 exact match query 透過 sparse/keyword 通道獨立撈到文章。

## 影響範圍

- `retrieval_providers/qdrant.py` — search 方法重構
- `indexing/pipeline.py` — 需加入 sparse vector 或 text index
- 可能需要 re-index 全部文章
- `core/bm25.py` — 角色從 re-ranker 變為 retriever（或由 Qdrant 原生取代）

## 受影響的功能

- 作者搜尋（目前完全失效於全站搜尋）
- 所有 keyword-heavy 查詢（專有名詞、人名、法案名稱等）
- 可能改善整體搜尋品質

## 暫時 workaround

目前 worktree 裡有 retrieval limit 3000 + strict author filter 的 patch，但這只是治標。
