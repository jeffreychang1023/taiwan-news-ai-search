---
name: 資料庫與 Indexing 狀態
description: Registry 數量、Indexing 進度、各環境 DB 狀態。修改 Crawler 寫入邏輯或確認資料庫總量時讀取。
type: project
---

> **給 Agent 的指示**：如果今天距離 Last Updated 日期已超過 2 天，且任務依賴最新數字，請執行下方查詢指令重新獲取，並更新此檔。否則可直接參考。

**Last Updated**: 2026-03-18 (indexing 已啟動)

## 資料狀態

- **Crawler Registry**: ~2.37M 筆。桌機為 master，已同步至 GCP
- **GCP Registry**: 與桌機同步（2026-03-11），daily cron 自動追最新
- **Qdrant Cloud**: 已棄用（遷移至 PG）
- **桌機 Local PG**: ~237K+ articles（開始時幾乎全是 chinatimes，正在增加中）
- **VPS PostgreSQL**: 500 articles / 1841 chunks（少量測試資料：chinatimes 258 + udn 213 + cna 29）
- **上線 blocker**: 全量 indexing（桌機 GPU 跑 Qwen3-4B → 本地 PG → pg_dump → VPS pg_restore）

## 全量 Indexing

- **來源**: `data/crawler/articles/`（463 TSV 檔案，~2M+ 篇）
- **真實進度**: ~237K/2M（~11.5%），幾乎只有 chinatimes 完成。ltn、cna、udn、einfo、esg 等來源都未 indexed 進 PG
- **Pipeline**: `indexing/pg_batch.py`（2026-03-18 建立，取代舊的 pipeline.py + Qdrant 流程）
  - Flow: TSV → IngestionEngine → QualityGate → ChunkingEngine → PostgreSQLUploader
  - 單 Python process 處理所有檔案（model 只載入一次）
  - 自動跳過已在 PG 的文章（pre-fetch indexed URLs）
  - ON CONFLICT upsert 保證冪等性
- **速度**: ~2.5 articles/sec（含 GPU 溫控暫停）
- **啟動方式**: `cd code/python && python -m indexing.pg_batch batch`（或 `bash run_indexing.sh`）
- **Resume 機制**:
  - 檔案級：`.pg_indexing_done`（新，取代舊 `.indexing_done`）
  - 文章級：每個 TSV 的 `.pg_checkpoint.json`（每 10 篇存檔）
  - 啟動時 pre-fetch PG 已有 URLs，自動跳過
- **⚠️ 舊檔案**: `.indexing_done` 和 `.checkpoint.json` 是 Qdrant 時代殘留，不再使用
- **暫停/繼續**：kill python process → 再跑同一指令
- **GPU 溫控**：83°C 暫停、75°C 恢復（`postgresql_uploader.py` 內建）
- **2026-03-18 22:19 啟動**：background process running

## 查詢方法

**Registry 數量**：
```bash
cd code/python && python -c "from crawler.core.crawled_registry import CrawledRegistry; r = CrawledRegistry(); print(r.get_total_count())"
```

**Indexing 進度**：
```bash
# PG 實際文章/chunk 數
docker exec nlweb-postgres psql -U nlweb -d nlweb -t -c "SELECT COUNT(*) FROM articles; SELECT COUNT(*) FROM chunks;"
# 已完成檔案數
wc -l data/.pg_indexing_done
# 各來源進度
docker exec nlweb-postgres psql -U nlweb -d nlweb -t -c "SELECT source, COUNT(*) FROM articles GROUP BY source ORDER BY count DESC;"
# 目前 checkpoint 進度
python -c "import json; d=json.load(open('data/crawler/articles/<current_file>.pg_checkpoint.json')); print(len(d['processed_urls']))"
```
