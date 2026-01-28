---
description: 搜尋程式碼
---

# /search <關鍵字>

使用索引系統搜尋程式碼。

## 執行命令

```bash
cd C:\users\user\NLWeb && python tools/indexer.py --search "<關鍵字>"
```

## 優於 Grep 的原因

| 特性 | 索引搜尋 | Grep |
|------|----------|------|
| 結果精準度 | 高（FTS5 排序）| 中（全部匹配）|
| Token 消耗 | 低 | 高 |
| 速度 | 快（已索引）| 慢（遍歷檔案）|
| Context 填充 | 只顯示相關結果 | 大量無關內容 |

## 搜尋範例

```bash
# 搜尋函數名稱
python tools/indexer.py --search "orchestrator"

# 搜尋類別
python tools/indexer.py --search "BaseAgent"

# 搜尋特定功能
python tools/indexer.py --search "gap detection"
```

## 輸出格式

```
檔案路徑:行號 | 匹配內容摘要
```

## 注意事項

- 如果搜尋結果不準確，先執行 `/index` 更新索引
- 支援部分匹配
- 結果按相關性排序
