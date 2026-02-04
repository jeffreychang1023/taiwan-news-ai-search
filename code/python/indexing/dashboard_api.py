"""
dashboard_api.py - Indexing Dashboard API handlers

Provides REST API endpoints for:
- Statistics (Registry + Qdrant counts)
- Crawler control (start/stop/status)
- Source listing
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional
from aiohttp import web
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class CrawlerTaskStatus(Enum):
    """Crawler task status"""
    IDLE = "idle"
    RUNNING = "running"
    STOPPING = "stopping"
    COMPLETED = "completed"
    EARLY_STOPPED = "early_stopped"  # 因連續失敗/skip 提前停止
    FAILED = "failed"


@dataclass
class CrawlerTask:
    """Represents a running crawler task"""
    task_id: str
    source: str
    mode: str
    count: int
    status: CrawlerTaskStatus = CrawlerTaskStatus.IDLE
    progress: int = 0
    total: int = 0
    started_at: float = 0
    finished_at: float = 0
    error: Optional[str] = None
    early_stop_reason: Optional[str] = None  # 提前停止的原因
    stats: Dict[str, int] = field(default_factory=dict)
    _asyncio_task: Optional[asyncio.Task] = None


class IndexingDashboardAPI:
    """API handlers for Indexing Dashboard"""

    def __init__(self):
        self._crawler_tasks: Dict[str, CrawlerTask] = {}
        self._task_counter = 0
        self._websockets: list = []

    # ==================== Statistics APIs ====================

    async def get_stats(self, request: web.Request) -> web.Response:
        """
        GET /api/indexing/stats

        Returns combined statistics from:
        - CrawledRegistry (articles by source)
        - Qdrant (vector counts) - if available
        """
        try:
            stats = {
                "registry": await self._get_registry_stats(),
                "qdrant": await self._get_qdrant_stats(),
                "timestamp": time.time()
            }
            return web.json_response(stats)
        except Exception as e:
            logger.error(f"Failed to get stats: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    async def _get_registry_stats(self) -> Dict[str, Any]:
        """Get statistics from CrawledRegistry"""
        try:
            from crawler.core.crawled_registry import get_registry
            registry = get_registry()
            stats = registry.get_stats()
            date_ranges = registry.get_date_range_by_source()
            return {
                "total_articles": stats.get("total", 0),
                "by_source": stats.get("by_source", {}),
                "date_ranges": date_ranges
            }
        except Exception as e:
            logger.warning(f"Failed to get registry stats: {e}")
            return {"total_articles": 0, "by_source": {}, "date_ranges": {}, "error": str(e)}

    async def _get_qdrant_stats(self) -> Dict[str, Any]:
        """Get statistics from Qdrant (if available)"""
        try:
            # Try to get Qdrant collection info
            from qdrant_client import QdrantClient
            import os

            qdrant_url = os.environ.get("QDRANT_URL", "http://localhost:6333")
            client = QdrantClient(url=qdrant_url, timeout=5)

            # Get collection info
            collection_name = os.environ.get("QDRANT_COLLECTION", "nlweb")
            try:
                info = client.get_collection(collection_name)
                return {
                    "vectors_count": info.vectors_count,
                    "points_count": info.points_count,
                    "collection": collection_name
                }
            except Exception:
                return {"vectors_count": 0, "points_count": 0, "error": "Collection not found"}

        except ImportError:
            return {"vectors_count": 0, "error": "qdrant-client not installed"}
        except Exception as e:
            logger.warning(f"Failed to get Qdrant stats: {e}")
            return {"vectors_count": 0, "error": str(e)}

    async def get_sources(self, request: web.Request) -> web.Response:
        """
        GET /api/indexing/sources

        Returns list of available news sources with their configurations.
        """
        try:
            from crawler.core import settings

            sources = []
            for source_id, config in settings.NEWS_SOURCES.items():
                sources.append({
                    "id": source_id,
                    "name": config.get("name", source_id),
                    "concurrent_limit": config.get("concurrent_limit", 3),
                    "delay_range": config.get("delay_range", (1.0, 2.0))
                })

            return web.json_response({
                "sources": sources,
                "count": len(sources)
            })
        except Exception as e:
            logger.error(f"Failed to get sources: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    # ==================== Crawler Control APIs ====================

    async def start_crawler(self, request: web.Request) -> web.Response:
        """
        POST /api/indexing/crawler/start

        Request body:
        {
            "source": "ltn",
            "mode": "auto",  // "auto" | "backfill" | "range"
            "count": 100,    // max articles for auto/backfill
            "stop_after_skips": 10,  // for auto mode: stop after N consecutive skips
            "overlap": 10,   // for backfill mode: start from oldest - overlap
            "start_id": 123, // for range mode
            "end_id": 456,   // for range mode
            "chunk_size": 5000,    // optional: split output every N articles
            "chunk_by_month": true // optional: split output by article month
        }
        """
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        source = body.get("source")
        mode = body.get("mode", "auto")
        count = body.get("count", 100)

        if not source:
            return web.json_response({"error": "source is required"}, status=400)

        # Check if there's already a running task for this source
        for task in self._crawler_tasks.values():
            if task.source == source and task.status == CrawlerTaskStatus.RUNNING:
                return web.json_response({
                    "error": f"Crawler for {source} is already running",
                    "task_id": task.task_id
                }, status=409)

        # Create new task
        self._task_counter += 1
        task_id = f"crawler_{source}_{self._task_counter}_{int(time.time())}"

        task = CrawlerTask(
            task_id=task_id,
            source=source,
            mode=mode,
            count=count,
            status=CrawlerTaskStatus.RUNNING,
            total=count,
            started_at=time.time()
        )

        self._crawler_tasks[task_id] = task

        # Start crawler in background
        asyncio_task = asyncio.create_task(
            self._run_crawler(task, body)
        )
        task._asyncio_task = asyncio_task

        logger.info(f"Started crawler task: {task_id} for source={source}, mode={mode}, count={count}")

        return web.json_response({
            "task_id": task_id,
            "source": source,
            "mode": mode,
            "count": count,
            "status": task.status.value
        })

    async def _run_crawler(self, task: CrawlerTask, params: Dict[str, Any]) -> None:
        """Run crawler in background"""
        try:
            # Import crawler components
            from crawler.core.engine import CrawlerEngine
            from crawler.core import settings

            source = task.source

            # Get parser for source
            parser = await self._get_parser(source)
            if parser is None:
                task.status = CrawlerTaskStatus.FAILED
                task.error = f"Unknown source: {source}"
                task.finished_at = time.time()
                await self._broadcast_status(task)
                return

            # Progress callback to update task and broadcast
            def on_progress(stats: Dict[str, Any]):
                task.stats = stats
                task.progress = stats.get("success", 0) + stats.get("skipped", 0)
                # Schedule async broadcast
                asyncio.create_task(self._broadcast_status(task))

            # Get chunk settings
            chunk_size = params.get("chunk_size", 0)
            chunk_by_month = params.get("chunk_by_month", False)

            # Create engine with progress callback and chunk settings
            engine = CrawlerEngine(
                parser=parser,
                auto_save=True,
                progress_callback=on_progress,
                chunk_size=chunk_size,
                chunk_by_month=chunk_by_month
            )

            # Run based on mode
            mode = params.get("mode", "auto")

            if mode == "auto":
                count = params.get("count", 100)
                stop_after_skips = params.get("stop_after_skips", 10)
                result = await engine.run_auto(
                    count=count,
                    stop_after_consecutive_skips=stop_after_skips
                )
            elif mode == "backfill":
                count = params.get("count", 100)
                overlap = params.get("overlap", 10)
                result = await engine.run_backfill(count=count, overlap=overlap)
            elif mode == "range":
                start_id = params.get("start_id", 1)
                end_id = params.get("end_id", 100)
                result = await engine.run_range(start_id=start_id, end_id=end_id)
            elif mode == "retry":
                max_retries = params.get("max_retries", 3)
                limit = params.get("limit", 50)
                result = await engine.run_retry(max_retries=max_retries, limit=limit)
            elif mode == "retry_urls":
                # Retry specific URLs
                urls = params.get("urls", [])
                result = await engine.run_retry_urls(urls=urls)
            elif mode == "sitemap":
                # Sitemap-based backfill (most complete method)
                sitemap_index_url = params.get("sitemap_index_url")
                if not sitemap_index_url:
                    # Use default sitemap URL for known sources
                    sitemap_index_url = self._get_default_sitemap_url(source)

                if not sitemap_index_url:
                    task.status = CrawlerTaskStatus.FAILED
                    task.error = f"No sitemap URL configured for source: {source}"
                    task.finished_at = time.time()
                    await self._broadcast_status(task)
                    return

                date_from = params.get("date_from")  # YYYYMM format
                date_to = params.get("date_to")      # YYYYMM format
                limit = params.get("limit", 0)

                result = await engine.run_sitemap(
                    sitemap_index_url=sitemap_index_url,
                    date_from=date_from,
                    date_to=date_to,
                    limit=limit
                )
            else:
                task.status = CrawlerTaskStatus.FAILED
                task.error = f"Unknown mode: {mode}"
                task.finished_at = time.time()
                await self._broadcast_status(task)
                return

            # Update task with results
            task.stats = result
            task.progress = result.get("success", 0) + result.get("skipped", 0)

            # 檢查是否提前停止
            if result.get("early_stopped"):
                task.status = CrawlerTaskStatus.EARLY_STOPPED
                task.early_stop_reason = result.get("early_stop_reason", "Unknown reason")
                logger.info(f"Crawler task {task.task_id} early stopped: {task.early_stop_reason}")
            else:
                task.status = CrawlerTaskStatus.COMPLETED
                logger.info(f"Crawler task {task.task_id} completed: {task.stats}")

            task.finished_at = time.time()

            await engine.close()

            await self._broadcast_status(task)

        except asyncio.CancelledError:
            task.status = CrawlerTaskStatus.STOPPING
            task.finished_at = time.time()
            logger.info(f"Crawler task {task.task_id} was cancelled")
            await self._broadcast_status(task)

        except Exception as e:
            task.status = CrawlerTaskStatus.FAILED
            task.error = str(e)
            task.finished_at = time.time()
            logger.error(f"Crawler task {task.task_id} failed: {e}", exc_info=True)
            await self._broadcast_status(task)

    async def _get_parser(self, source: str):
        """Get parser instance for source using CrawlerFactory"""
        try:
            from crawler.parsers.factory import CrawlerFactory
            parser = CrawlerFactory.get_parser(source)
            if parser is None:
                logger.error(f"No parser found for source: {source}")
            return parser
        except Exception as e:
            logger.error(f"Failed to get parser for {source}: {e}")
            return None

    def _get_default_sitemap_url(self, source: str) -> Optional[str]:
        """
        Get default sitemap index URL for a source.

        Add new sources here as they are discovered/configured.
        """
        sitemap_urls = {
            "udn": "https://udn.com/sitemapxml/news/mapindex.xml",
            "ltn": "https://news.ltn.com.tw/sitemap.xml",
            # CNA has no sitemap (returns 404)
        }
        return sitemap_urls.get(source)

    async def get_crawler_status(self, request: web.Request) -> web.Response:
        """
        GET /api/indexing/crawler/status
        GET /api/indexing/crawler/status/{task_id}

        Returns status of crawler task(s).
        """
        task_id = request.match_info.get("task_id")

        if task_id:
            # Get specific task
            task = self._crawler_tasks.get(task_id)
            if not task:
                return web.json_response({"error": "Task not found"}, status=404)
            return web.json_response(self._task_to_dict(task))
        else:
            # Get all tasks
            tasks = [self._task_to_dict(t) for t in self._crawler_tasks.values()]
            return web.json_response({
                "tasks": tasks,
                "count": len(tasks)
            })

    async def stop_crawler(self, request: web.Request) -> web.Response:
        """
        POST /api/indexing/crawler/stop

        Request body:
        {
            "task_id": "crawler_ltn_1_1234567890"
        }
        """
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        task_id = body.get("task_id")
        if not task_id:
            return web.json_response({"error": "task_id is required"}, status=400)

        task = self._crawler_tasks.get(task_id)
        if not task:
            return web.json_response({"error": "Task not found"}, status=404)

        if task.status != CrawlerTaskStatus.RUNNING:
            return web.json_response({
                "error": f"Task is not running (status: {task.status.value})"
            }, status=400)

        # Cancel the asyncio task
        if task._asyncio_task:
            task._asyncio_task.cancel()

        task.status = CrawlerTaskStatus.STOPPING

        logger.info(f"Stopping crawler task: {task_id}")

        return web.json_response({
            "task_id": task_id,
            "status": task.status.value,
            "message": "Stop signal sent"
        })

    def _task_to_dict(self, task: CrawlerTask) -> Dict[str, Any]:
        """Convert CrawlerTask to dict for JSON response"""
        return {
            "task_id": task.task_id,
            "source": task.source,
            "mode": task.mode,
            "count": task.count,
            "status": task.status.value,
            "progress": task.progress,
            "total": task.total,
            "started_at": task.started_at,
            "finished_at": task.finished_at,
            "error": task.error,
            "early_stop_reason": task.early_stop_reason,
            "stats": task.stats,
            "duration_seconds": (task.finished_at or time.time()) - task.started_at if task.started_at else 0
        }

    # ==================== WebSocket for Real-time Updates ====================

    async def websocket_handler(self, request: web.Request) -> web.WebSocketResponse:
        """
        WebSocket endpoint for real-time crawler status updates.

        GET /api/indexing/ws
        """
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        self._websockets.append(ws)
        logger.info(f"WebSocket client connected. Total: {len(self._websockets)}")

        try:
            # Send current status on connect
            tasks = [self._task_to_dict(t) for t in self._crawler_tasks.values()]
            await ws.send_json({
                "type": "init",
                "tasks": tasks
            })

            # Keep connection alive
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    # Handle ping/pong or other messages
                    if msg.data == "ping":
                        await ws.send_str("pong")
                elif msg.type == web.WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {ws.exception()}")
                    break

        finally:
            self._websockets.remove(ws)
            logger.info(f"WebSocket client disconnected. Total: {len(self._websockets)}")

        return ws

    async def _broadcast_status(self, task: CrawlerTask) -> None:
        """Broadcast task status to all WebSocket clients"""
        message = {
            "type": "status_update",
            "task": self._task_to_dict(task)
        }

        for ws in self._websockets[:]:  # Copy list to avoid modification during iteration
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send WebSocket message: {e}")
                if ws in self._websockets:
                    self._websockets.remove(ws)

    # ==================== Failed URLs / Errors APIs ====================

    async def get_errors(self, request: web.Request) -> web.Response:
        """
        GET /api/indexing/errors

        Query params:
            source: Filter by source (optional)
            error_type: Filter by single error type (optional)
            error_types: Filter by multiple error types, comma-separated (optional)
            limit: Max results (default 100)
            offset: Pagination offset (default 0)
        """
        try:
            source = request.query.get("source")
            error_type = request.query.get("error_type")
            error_types_str = request.query.get("error_types")
            limit = int(request.query.get("limit", 100))
            offset = int(request.query.get("offset", 0))

            # Parse multiple error types
            error_types = None
            if error_types_str:
                error_types = [t.strip() for t in error_types_str.split(",") if t.strip()]
            elif error_type:
                error_types = [error_type]

            from crawler.core.crawled_registry import get_registry
            registry = get_registry()

            errors = registry.get_failed_urls(
                source_id=source,
                error_types=error_types,
                limit=limit,
                offset=offset
            )

            stats = registry.get_failed_stats()

            return web.json_response({
                "errors": errors,
                "count": len(errors),
                "stats": stats
            })
        except Exception as e:
            logger.error(f"Failed to get errors: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    async def clear_errors(self, request: web.Request) -> web.Response:
        """
        POST /api/indexing/errors/clear

        Request body:
        {
            "source": "ltn",  // optional, if not provided clears all
            "urls": ["url1", "url2"]  // optional, specific URLs to clear
        }
        """
        try:
            body = await request.json()
        except Exception:
            body = {}

        source = body.get("source")
        urls = body.get("urls")

        try:
            from crawler.core.crawled_registry import get_registry
            registry = get_registry()

            if urls and isinstance(urls, list):
                # Clear specific URLs
                count = 0
                for url in urls:
                    if registry.remove_failed(url):
                        count += 1
                return web.json_response({
                    "cleared": count,
                    "mode": "selected"
                })
            else:
                # Clear by source or all
                count = registry.clear_failed(source_id=source)
                return web.json_response({
                    "cleared": count,
                    "source": source or "all"
                })
        except Exception as e:
            logger.error(f"Failed to clear errors: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    async def retry_errors(self, request: web.Request) -> web.Response:
        """
        POST /api/indexing/errors/retry

        Request body (option 1 - by source with optional filters):
        {
            "source": "ltn",
            "error_types": ["blocked", "parse_error"],  // optional filter
            "max_retries": 3,
            "limit": 50
        }

        Request body (option 2 - specific URLs):
        {
            "urls": ["url1", "url2"],
            "sources": {"ltn": ["url1"], "udn": ["url2"]}
        }

        Request body (option 3 - retry all with filters):
        {
            "retry_all": true,
            "source": "ltn",  // optional
            "error_types": ["blocked", "parse_error"]  // optional
        }

        This is a convenience endpoint that starts a retry crawler task.
        """
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        urls = body.get("urls")
        sources = body.get("sources")  # Dict: source -> list of URLs
        retry_all = body.get("retry_all", False)

        # Mode 0: Retry all with filters (no limit)
        if retry_all:
            return await self._retry_all_filtered(body)

        # Mode 1: Specific URLs grouped by source
        if urls and sources:
            return await self._retry_specific_urls(sources)

        # Mode 2: By source
        source = body.get("source")
        if not source:
            return web.json_response({"error": "source is required (or provide urls + sources)"}, status=400)

        # Check if there's already a running task for this source
        for task in self._crawler_tasks.values():
            if task.source == source and task.status == CrawlerTaskStatus.RUNNING:
                return web.json_response({
                    "error": f"Crawler for {source} is already running",
                    "task_id": task.task_id
                }, status=409)

        # Get count of retryable errors
        from crawler.core.crawled_registry import get_registry
        registry = get_registry()
        max_retries = body.get("max_retries", 3)
        limit = body.get("limit", 50)
        retry_urls = registry.get_failed_urls_for_retry(
            source_id=source,
            max_retries=max_retries,
            limit=limit
        )

        if not retry_urls:
            return web.json_response({
                "error": f"No failed URLs to retry for {source}",
                "count": 0
            }, status=404)

        # Create retry task
        self._task_counter += 1
        task_id = f"retry_{source}_{self._task_counter}_{int(time.time())}"

        task = CrawlerTask(
            task_id=task_id,
            source=source,
            mode="retry",
            count=len(retry_urls),
            status=CrawlerTaskStatus.RUNNING,
            total=len(retry_urls),
            started_at=time.time()
        )

        self._crawler_tasks[task_id] = task

        # Start retry in background
        params = {
            "source": source,
            "mode": "retry",
            "max_retries": max_retries,
            "limit": limit
        }
        asyncio_task = asyncio.create_task(self._run_crawler(task, params))
        task._asyncio_task = asyncio_task

        logger.info(f"Started retry task: {task_id} for {len(retry_urls)} URLs")

        return web.json_response({
            "task_id": task_id,
            "source": source,
            "mode": "retry",
            "count": len(retry_urls),
            "status": task.status.value
        })

    async def _retry_all_filtered(self, params: Dict[str, Any]) -> web.Response:
        """
        Retry all failed URLs matching filters (no limit).

        Args:
            params: Dict with optional 'source' and 'error_types' filters
        """
        source_filter = params.get("source")
        error_types = params.get("error_types")
        max_retries = params.get("max_retries", 3)

        from crawler.core.crawled_registry import get_registry
        registry = get_registry()

        # Get ALL failed URLs matching filters (use large limit)
        all_failed = registry.get_failed_urls(
            source_id=source_filter,
            error_types=error_types,
            limit=10000  # Large limit to get all
        )

        if not all_failed:
            return web.json_response({
                "error": "No failed URLs matching filters",
                "count": 0
            }, status=404)

        # Group by source
        by_source: Dict[str, list] = {}
        for err in all_failed:
            src = err["source_id"]
            if src not in by_source:
                by_source[src] = []
            by_source[src].append(err["url"])

        # Clear these URLs first
        for url_list in by_source.values():
            for url in url_list:
                registry.remove_failed(url)

        # Start retry tasks for each source
        return await self._retry_specific_urls(by_source)

    async def _retry_specific_urls(self, sources: Dict[str, list]) -> web.Response:
        """
        Retry specific URLs grouped by source.

        Args:
            sources: Dict mapping source_id to list of URLs
        """
        task_ids = []
        total_urls = 0

        for source, urls in sources.items():
            if not urls:
                continue

            # Check if there's already a running task for this source
            running = False
            for task in self._crawler_tasks.values():
                if task.source == source and task.status == CrawlerTaskStatus.RUNNING:
                    running = True
                    break

            if running:
                logger.warning(f"Skipping {source}: already running")
                continue

            # Create task for this source
            self._task_counter += 1
            task_id = f"retry_{source}_{self._task_counter}_{int(time.time())}"

            task = CrawlerTask(
                task_id=task_id,
                source=source,
                mode="retry",
                count=len(urls),
                status=CrawlerTaskStatus.RUNNING,
                total=len(urls),
                started_at=time.time()
            )

            self._crawler_tasks[task_id] = task

            # Start retry in background with specific URLs
            params = {
                "source": source,
                "mode": "retry_urls",
                "urls": urls
            }
            asyncio_task = asyncio.create_task(self._run_crawler(task, params))
            task._asyncio_task = asyncio_task

            task_ids.append(task_id)
            total_urls += len(urls)

            logger.info(f"Started retry task: {task_id} for {len(urls)} URLs from {source}")

        if not task_ids:
            return web.json_response({
                "error": "No tasks could be started (sources may already be running)",
                "count": 0
            }, status=409)

        return web.json_response({
            "task_ids": task_ids,
            "mode": "retry_selected",
            "count": total_urls,
            "status": "running"
        })


# Singleton instance
_api_instance: Optional[IndexingDashboardAPI] = None


def get_api() -> IndexingDashboardAPI:
    """Get singleton API instance"""
    global _api_instance
    if _api_instance is None:
        _api_instance = IndexingDashboardAPI()
    return _api_instance


def setup_routes(app: web.Application) -> None:
    """Setup API routes on the application"""
    api = get_api()

    # Statistics
    app.router.add_get("/api/indexing/stats", api.get_stats)
    app.router.add_get("/api/indexing/sources", api.get_sources)

    # Crawler control
    app.router.add_post("/api/indexing/crawler/start", api.start_crawler)
    app.router.add_get("/api/indexing/crawler/status", api.get_crawler_status)
    app.router.add_get("/api/indexing/crawler/status/{task_id}", api.get_crawler_status)
    app.router.add_post("/api/indexing/crawler/stop", api.stop_crawler)

    # Failed URLs / Errors
    app.router.add_get("/api/indexing/errors", api.get_errors)
    app.router.add_post("/api/indexing/errors/clear", api.clear_errors)
    app.router.add_post("/api/indexing/errors/retry", api.retry_errors)

    # WebSocket
    app.router.add_get("/api/indexing/ws", api.websocket_handler)
