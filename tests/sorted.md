# Sorted Test Files

This file tracks temporary files that have been moved to the tests directory.

## 2025-11-15

### Files Moved from C:\Users\User to tests/

1. **test_export.csv** (Created: Nov 11, 2024)
   - Purpose: Test export file from analytics dashboard
   - Temporary test data for verifying CSV export functionality

2. **analyze_agent_sessions.py** (Created: Nov 5, 2024)
   - Purpose: Script to analyze agent session data
   - One-time analysis script for debugging sessions

3. **cleanup_agent_sessions.py** (Created: Nov 5, 2024)
   - Purpose: Script to clean up agent session files
   - Utility script for maintaining session data

4. **cleanup_sessions.py** (Created: Nov 5, 2024)
   - Purpose: General session cleanup script
   - Temporary utility for session management

5. **debug_qdrant.py** (Created: Sep 26, 2024)
   - Purpose: Debug script for Qdrant vector database issues
   - Debugging utility for development

6. **Untitled.ipynb** (Created: Oct 9, 2024)
   - Purpose: Empty Jupyter notebook
   - Temporary notebook file, no content

7. **Untitled1.ipynb** (Created: Oct 9, 2024)
   - Purpose: Jupyter notebook for experiments
   - Temporary experimental notebook

**Action**: All files moved to `tests/` and added to `.gitignore`

## 2024-11-22

### Files Moved from NLWeb/ to testing/temp_files_archive/

#### 臨時 JSON/XML 文件 (3個)

1. **code/data/json_with_embeddings/tmpsayil7w6.json** (420KB, Created: Sep 26, 2024)
   - Purpose: 臨時 JSON 測試資料
   - 檔名有 `tmp` 前綴，為一次性測試文件

2. **code/data/json_with_embeddings/tmpvymsm1zk.xml** (2.6MB, Created: Sep 17, 2024)
   - Purpose: 臨時 XML 測試資料
   - 檔名有 `tmp` 前綴，為一次性測試文件

3. **code/data/json_with_embeddings/tmpwyd521pu.json** (176KB, Created: Sep 26, 2024)
   - Purpose: 臨時 JSON 測試資料
   - 檔名有 `tmp` 前綴，為一次性測試文件

#### 備份和舊版本文件 (6個)

4. **code/python/chat/conversation.backup** (22KB, Created: Oct 20, 2024)
   - Purpose: 對話模組的備份版本
   - 正式版本位於 `code/python/chat/conversation.py`

5. **code/python/core/baseHandler.py_old** (18KB, Created: Oct 20, 2024)
   - Purpose: 基礎處理器的舊版本
   - 正式版本位於 `code/python/core/baseHandler.py`

6. **code/python/core/fastTrack.py_old** (3.4KB, Created: Oct 20, 2024)
   - Purpose: 快速追蹤模組的舊版本
   - 正式版本位於 `code/python/core/fastTrack.py`

7. **code/python/core/prompts.py.backup** (16KB, Created: Oct 28, 2024)
   - Purpose: 提示詞模組的備份版本
   - 正式版本位於 `code/python/core/prompts.py`

8. **code/python/core/ranking.py.backup** (22KB, Created: Oct 22, 2024)
   - Purpose: 排名模組的備份版本
   - 正式版本位於 `code/python/core/ranking.py`

9. **code/python/methods/generate_answer.py_old** (11KB, Created: Oct 20, 2024)
   - Purpose: 答案生成模組的舊版本
   - 正式版本位於 `code/python/methods/generate_answer.py`

#### 重複的 Log 文件 (4個)

10. **logs/generate_answer.log** (31KB, Created: Oct 8, 2024)
    - Purpose: 舊的答案生成日誌
    - 較新完整版本位於 `code/python/logs/generate_answer.log` (52KB)
    - 移動為 `old_generate_answer.log`

11. **logs/prompt_runner.log** (229 bytes, Created: Oct 8, 2024)
    - Purpose: 舊的提示運行日誌
    - 較新完整版本位於 `code/python/logs/prompt_runner.log` (1.6KB)
    - 移動為 `old_prompt_runner.log`

12. **logs/qdrant_client.log** (1.5KB, Created: Oct 22, 2024)
    - Purpose: 舊的 Qdrant 客戶端日誌
    - 較新完整版本位於 `code/python/logs/qdrant_client.log` (30KB)
    - 移動為 `old_qdrant_client.log`

13. **logs/retriever.log** (1.3KB, Created: Sep 25, 2024)
    - Purpose: 舊的檢索器日誌
    - 較新完整版本位於 `code/python/logs/retriever.log` (35KB)
    - 移動為 `old_retriever.log`

#### 重複的資料庫文件 (1個)

14. **data/analytics/query_logs.db** (76KB, Created: Nov 19, 2024)
    - Purpose: 舊的查詢日誌資料庫
    - 較新完整版本位於 `code/python/data/analytics/query_logs.db` (6.2MB)
    - 移動為 `old_query_logs.db`

**總計**: 14 個臨時/重複文件，共 3.4MB

**Action**: 所有文件移動到 `testing/temp_files_archive/` 並建立 README.md 說明文件

**保留期限**: 建議觀察 1-2 週，如無問題可安全刪除整個 `temp_files_archive/` 資料夾

**驗證方法**:
- 檢查主要文件是否正常運作
- 確認 `code/python/logs/` 中的 log 文件正常記錄
- 確認 `code/python/data/analytics/query_logs.db` 資料庫正常運作
- 如需還原任何文件，可從 `testing/temp_files_archive/` 中取回

## 2024-11-22 (Code Cleanup)

### Code Fixes - Cleanup-code Skill Execution

#### 修復 1: Analytics Salt 移至環境變數 (安全性改善)

**文件**: `code/python/webserver/analytics_handler.py`

**修改內容**:
- 行 19: 添加 `import os`
- 行 579-580: 將硬編碼的 salt 值改為從環境變數讀取

**變更前**:
```python
salt = "nlweb-analytics-salt"  # TODO: Move to config
```

**變更後**:
```python
salt = os.getenv('ANALYTICS_SALT', 'nlweb-analytics-salt-default')
```

**配置文件更新**:
- `.env.template` 行 80-83: 新增 `ANALYTICS_SALT` 環境變數說明

**影響**:
- ✅ 提升安全性 - IP 哈希的鹽值現在可以在生產環境中配置
- ⚠️ 需要在 Render 部署時添加環境變數 `ANALYTICS_SALT`

**優先級**: 高（安全性）

---

#### 修復 2: 改善錯誤處理日誌記錄

**文件**: `code/python/methods/generate_answer.py`

**修改內容**:
在 3 處裸露的 `except:` 塊中添加警告日誌

**位置 1 - 行 347-349**: 日期解析失敗
```python
except Exception as e:
    logger.warning(f"Failed to parse date for article {url}: {e}")
    pass  # Skip articles with bad dates
```

**位置 2 - 行 606-608**: 發送錯誤訊息失敗
```python
except Exception as e:
    logger.warning(f"Failed to send error message to client: {e}")
    pass
```

**位置 3 - 行 729-731**: 發送錯誤訊息失敗
```python
except Exception as e:
    logger.warning(f"Failed to send error message to client: {e}")
    pass
```

**影響**:
- ✅ 改善調試能力 - 現在可以追蹤日期解析和訊息發送失敗
- ✅ 不影響現有功能 - 只是添加日誌，不改變行為

**優先級**: 中（品質改善）

---

### 代碼分析記錄 (未修復項目)

#### 分析 1: Debug Print 語句
**文件**: `generate_answer.py`, `retriever.py`, `qdrant.py`
**狀態**: 保留 (用戶決定)
**數量**: 約 20+ 處
**優先級**: 高

#### 分析 2: Qdrant Hybrid Search 嵌套邏輯
**文件**: `retrieval_providers/qdrant.py`
**行號**: 715-960 (245+ 行)
**複雜度**: 5-6 層嵌套
**狀態**: 保留，未來考慮重構
**建議方案**: 提取方法降低複雜度
**預估工作量**: 1-2 小時 (輕量重構)
**優先級**: 中 (技術債務)

**功能說明**: 實現 Hybrid Search (Vector + BM25 + 領域檢測 + 時間過濾)
**重構建議**: 提取以下方法
- `_extract_keywords(query)`
- `_detect_domains(query)`
- `_check_negative_indicators(name, domains)`
- `_calculate_temporal_boost(payload, is_temporal)`

#### 分析 3: 未實現的 Unread 追蹤功能
**文件**: `routes/chat.py`, `websocket.py`
**狀態**: 保留 (未來功能)
**工作量**: 2-4 小時
**優先級**: 中

#### 分析 4: 資料庫兼容性處理模式
**文件**: `analytics_handler.py`, `query_logger.py`
**狀態**: 保留 (by design for PostgreSQL/SQLite)
**說明**: Dict vs Tuple 處理是為了支援兩種資料庫
**優先級**: 低

---

### 總結

**執行的修復**: 2 項
- ✅ Analytics Salt 安全性改善
- ✅ 錯誤處理日誌改善

**分析但未修復**: 4 項主要技術債務
- Debug print 語句 (高優先級，用戶決定保留)
- Qdrant 嵌套邏輯 (中優先級，未來重構)
- Unread 追蹤功能 (中優先級，功能規劃)
- 資料庫兼容性 (低優先級，by design)

**驗證方法**:
1. 測試 Analytics API 功能正常（特別是 IP 哈希）
2. 檢查 `code/python/logs/generate_answer.log` 是否有新的警告訊息
3. 執行查詢測試，確認日期解析和錯誤處理正常

**部署注意事項**:
⚠️ **重要**: 在 Render 部署時添加環境變數 `ANALYTICS_SALT`
- 建議值: 隨機生成的 32+ 字元字串
- 範例: `openssl rand -base64 32` 生成

## 2025-12-07 (File Cleanup)

### Files Deleted - Cleanup-files Skill Execution

#### Architecture Development Scripts (6 files)
1. **add_draggable_boxes.py**
   - Purpose: Script to add draggable box functionality to architecture diagram
   - Reason: One-time development script for architecture visualization

2. **clean_architecture.py**
   - Purpose: Script to clean up architecture diagram data
   - Reason: One-time cleanup script

3. **fix_layout_comprehensive.py**
   - Purpose: Script to fix comprehensive layout issues
   - Reason: One-time layout fix script

4. **implement_edges_and_resize.py**
   - Purpose: Script to implement edges and resize functionality
   - Reason: One-time development script

5. **temp_fix_architecture.py**
   - Purpose: Temporary architecture fix script
   - Reason: Explicitly marked as temporary (filename prefix)

6. **update_architecture_layout.py**
   - Purpose: Script to update architecture layout
   - Reason: One-time layout update script

#### Backup Files (4 files)
7. **architecture-diagram.json.before_reorg**
   - Purpose: Backup of architecture diagram before reorganization
   - Reason: Historical backup, current version is stable

8. **new_graphdata.json**
   - Purpose: New version of graph data (intermediate file)
   - Reason: Superseded by current graphData.json

9. **static/architecture.html.before_new_arch**
   - Purpose: HTML backup before new architecture
   - Reason: Historical backup, current version is stable

10. **static/architecture.html.before_reorg**
    - Purpose: HTML backup before reorganization
    - Reason: Historical backup, current version is stable

#### Patch Scripts (2 files)
11. **code/python/training/patch_qdrant.py**
    - Purpose: Patch script for Qdrant integration
    - Reason: One-time patch for development, no longer needed

12. **code/python/training/patch_xgboost_ranker.py**
    - Purpose: Patch script for XGBoost ranker
    - Reason: One-time patch for development, no longer needed

#### Documentation Files (3 files)
13. **EDGE_EDITING_GUIDE.md**
    - Purpose: Guide for editing edges in architecture diagram
    - Reason: Development documentation, no longer needed

14. **DATA_FLOW_EDGES.md**
    - Purpose: Data flow edges documentation
    - Reason: Development documentation, no longer needed

15. **algo/PHASE_BC_IMPLEMENTATION_PLAN.md**
    - Purpose: Phase B/C implementation plan
    - Reason: Planning document, implementation details in other docs

#### Scripts (1 file)
16. **scripts/apply_new_architecture.py**
    - Purpose: Script to apply new architecture
    - Reason: One-time migration script, architecture already applied

**Total**: 16 files deleted

**Action**: All files permanently deleted (not moved to tests/ or archive)

**Files Kept** (User decision):
- .obsidian/ folder (Obsidian vault)
- 1217演講.pptx (presentation file)
- scripts/update_architecture.py (may still be useful)
- models/ directory (potentially ML models)
- code/python/jobs/ directory (need to check contents)

**Verification Steps**:
1. ✅ Check git status - untracked files reduced
2. ✅ Verify architecture.html still loads correctly
3. ✅ Verify architecture-diagram.json exists and is current
4. ✅ Verify graphData.json exists and is current
5. ✅ Check training scripts still run (export_training_data.py, train_phase_c1.py, etc.)
