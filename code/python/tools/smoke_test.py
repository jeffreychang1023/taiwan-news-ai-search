#!/usr/bin/env python3
"""
Smoke Test — 核心模組 import 檢查。

用途：任何程式碼修改後跑一次，確認沒有 break import chain。
執行：從 code/python/ 目錄執行
    python tools/smoke_test.py

成功：exit code 0，印 "SMOKE TEST PASSED"
失敗：exit code 1，印失敗的模組和錯誤訊息
"""

import os
import sys
import time

# 確保 code/python/ 在 sys.path（不論從哪裡執行）
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# 所有關鍵模組，對應 CLAUDE.md 的關鍵檔案對應表
CORE_MODULES = [
    # Server & Middleware
    "webserver.aiohttp_server",
    # Request Processing
    "core.baseHandler",
    "core.state",
    "core.schemas",
    # Retrieval
    "core.retriever",
    "retrieval_providers.postgres_client",
    # Ranking
    "core.ranking",
    "core.xgboost_ranker",
    "core.mmr",
    # Reasoning
    "reasoning.orchestrator",
    # Auth
    "auth.auth_db",
    "auth.auth_service",
    # Session
    "core.session_service",
    # Streaming
    "core.utils.message_senders",
    # Indexing
    "indexing.pipeline",
    "indexing.chunking_engine",
    # Crawler
    "crawler.core.engine",
]


def run_smoke_test() -> bool:
    """Import 所有核心模組，回報結果。"""
    start = time.time()
    failed = []

    for module_name in CORE_MODULES:
        try:
            __import__(module_name)
        except Exception as e:
            failed.append((module_name, type(e).__name__, str(e)))

    elapsed = time.time() - start
    total = len(CORE_MODULES)
    passed = total - len(failed)

    print(f"\n{'=' * 50}")
    print(f"  SMOKE TEST: {passed}/{total} modules OK  ({elapsed:.1f}s)")
    print(f"{'=' * 50}")

    if failed:
        print("\nFAILED MODULES:\n")
        for module_name, error_type, error_msg in failed:
            print(f"  FAIL: {module_name}")
            print(f"        {error_type}: {error_msg}\n")
        print("SMOKE TEST FAILED")
        return False

    print("\nSMOKE TEST PASSED")
    return True


if __name__ == "__main__":
    success = run_smoke_test()
    sys.exit(0 if success else 1)
