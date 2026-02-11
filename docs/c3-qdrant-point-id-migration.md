# C3: Qdrant Point ID Migration Plan

> **狀態**: ✅ 已完成 — 2026-02-10（Qdrant 尚無資料，直接改）
> **來源**: 2026-02-09 Code Review
> **影響範圍**: `code/python/indexing/qdrant_uploader.py`

---

## 問題

`QdrantUploader._generate_point_id()` 使用 MD5 截斷為 64-bit integer 作為 Qdrant point ID：

```python
# qdrant_uploader.py:165-172
def _generate_point_id(self, chunk_id: str) -> int:
    hash_hex = hashlib.md5(chunk_id.encode()).hexdigest()[:16]  # 取前 16 hex = 64 bit
    return int(hash_hex, 16)
```

**風險**:
- MD5 已知有碰撞弱點
- 截斷到 64-bit 大幅提高碰撞機率（Birthday Paradox）
- 碰撞時新 chunk 會**靜默覆蓋**舊 chunk（Qdrant upsert 語意）
- `check_exists()` 也用同一函式，碰撞導致誤判「已存在」

**影響估算**:
- < 50 萬 chunks: 碰撞機率極低（~0.003%），實務上安全
- 100 萬 chunks: 碰撞機率 ~0.003%
- 1000 萬 chunks: 碰撞機率顯著上升

---

## 修復方案

### 改用 UUID5 string ID

Qdrant 原生支援 UUID string 作為 point ID，無需數字。

```python
import uuid

NAMESPACE_NLWEB = uuid.uuid5(uuid.NAMESPACE_URL, "nlweb.chunk")

def _generate_point_id(self, chunk_id: str) -> str:
    """Generate a UUID5 point ID from chunk_id (deterministic, no collision)."""
    return str(uuid.uuid5(NAMESPACE_NLWEB, chunk_id))
```

**優點**:
- UUID5 基於 SHA-1，128-bit，碰撞機率趨近於零
- 相同 chunk_id 永遠生成相同 UUID（deterministic）
- Qdrant 原生支援，無需額外設定

---

## 執行步驟

### 在 re-index 時執行

1. **修改 `_generate_point_id()`** — 改用上方 UUID5 方案
2. **修改 `check_exists()`** — 確認 `id_map` 的 key 型別從 `int` 改為 `str`
3. **刪除舊 collection** — `client.delete_collection("nlweb")`
4. **重建 collection** — `_ensure_collection()` 會自動建立
5. **重新上傳全部資料** — 從 Vault (SQLite) 讀取所有 chunks 重新 embed + upload

### 受影響的檔案

| 檔案 | 改動 |
|------|------|
| `indexing/qdrant_uploader.py` | `_generate_point_id()` 回傳 `str`，`check_exists()` 適配 |
| `indexing/pipeline.py` | 無需改動（透過 uploader 介面） |

### 注意事項

- **不能漸進式遷移** — 舊 ID (int) 和新 ID (str) 無法共存於同一 collection
- 必須一次性 re-index
- Re-index 期間搜尋服務會受影響（collection 為空或不完整）
- 建議先建立新 collection（不同名稱），完成後切換

---

## 驗證

Re-index 完成後：

```python
# 確認 point 數量一致
info = uploader.get_collection_info()
print(f"Points: {info['points_count']}")

# 抽樣確認 chunk_id → point_id mapping
sample_chunk_id = "ltn_https://news.ltn.com.tw/news/life/breakingnews/1234567_0"
expected_uuid = str(uuid.uuid5(NAMESPACE_NLWEB, sample_chunk_id))
results = client.retrieve(collection_name="nlweb", ids=[expected_uuid])
assert len(results) == 1
```
