---
description: 更新程式碼索引
---

# /index

重建 NLWeb 程式碼索引。

## 執行命令

```bash
python tools/indexer.py --index
```

## 使用時機

- 大量檔案修改後
- 新增模組後
- 搜尋結果不準確時
- 首次使用索引系統前

## 索引涵蓋範圍

- 所有 `.py` 檔案
- 函數定義、類別定義
- Docstrings
- 重要註解

## 注意事項

- 索引建立需要數秒鐘
- 索引儲存在 `tools/.code_index.db`
- 不需要頻繁重建，除非有大量檔案變動
