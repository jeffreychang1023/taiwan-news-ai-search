"""
engine.py - 通用爬蟲引擎

核心爬蟲引擎，負責：
- 範圍爬取：run_range(start_id, end_id)
- 列表爬取：run_list(url_list)
- 自動爬取：run_auto(count)
- 併發控制、重試機制、去重機制
"""

import asyncio
import aiohttp
import logging
import random
import time
from typing import Dict, List, Optional, Any, Set, Union, Callable
from pathlib import Path
from datetime import datetime, timedelta
from enum import Enum

from . import settings
from .settings import DEFAULT_HEADERS
from .interfaces import BaseParser, SessionType
from .pipeline import Pipeline
from .crawled_registry import get_registry, CrawledRegistry

# 嘗試引入 curl_cffi
try:
    from curl_cffi.requests import AsyncSession as CurlSession
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False
    CurlSession = None


class CrawlStatus(Enum):
    """爬取狀態列舉"""
    SUCCESS = "SUCCESS"
    NOT_FOUND = "NOT_FOUND"
    BLOCKED = "BLOCKED"


class CrawlerEngine:
    """
    通用爬蟲引擎

    設計原則：
    1. 依賴注入：透過 BaseParser 介面與具體網站解耦
    2. 關注點分離：只負責爬取流程，解析邏輯委託給 Parser
    3. 可重用：適用於所有實作 BaseParser 的網站
    """

    SMART_JUMP_THRESHOLD = 100

    def __init__(
        self,
        parser: BaseParser,
        session: Optional[Union[aiohttp.ClientSession, 'CurlSession']] = None,
        auto_save: bool = True,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        chunk_size: int = 0,
        chunk_by_month: bool = False
    ):
        """
        初始化爬蟲引擎

        Args:
            parser: BaseParser 實例（必須）
            session: HTTP Session 實例（可選）
            auto_save: 是否自動儲存爬取結果（預設 True）
            progress_callback: 進度回調函數，接收 stats dict
            chunk_size: 每個檔案的最大文章數（0 表示不限制）
            chunk_by_month: 是否按文章發布月份分檔
        """
        self.parser = parser
        self.session = session
        self.auto_save = auto_save
        self.progress_callback = progress_callback
        self.chunk_size = chunk_size
        self.chunk_by_month = chunk_by_month

        # 載入來源專屬設定
        self._load_source_config()

        # 判斷 Session 類型
        if session is not None:
            if CURL_CFFI_AVAILABLE and isinstance(session, CurlSession):
                self.session_type = SessionType.CURL_CFFI
            else:
                self.session_type = SessionType.AIOHTTP
        else:
            if parser.source_name in settings.CURL_CFFI_SOURCES:
                self.session_type = SessionType.CURL_CFFI
            else:
                self.session_type = SessionType.AIOHTTP

        # 設定日誌
        self.logger = logging.getLogger(f"CrawlerEngine_{parser.source_name}")
        self._setup_logger()

        self.logger.info(f"Engine initialized with session type: {self.session_type.value}")
        self.logger.info(f"   Concurrent limit: {self.concurrent_limit}")
        self.logger.info(f"   Delay range: {self.min_delay:.1f}s - {self.max_delay:.1f}s")
        if chunk_size > 0:
            self.logger.info(f"   Chunk size: {chunk_size} articles per file")
        if chunk_by_month:
            self.logger.info(f"   Chunk by month: enabled")

        # 初始化 Pipeline
        if self.auto_save:
            self.pipeline = Pipeline(
                source_name=parser.source_name,
                chunk_size=chunk_size,
                chunk_by_month=chunk_by_month
            )

        # 初始化 SQLite Registry
        self.registry: CrawledRegistry = get_registry()

        # 載入歷史記錄（去重）- 使用內存 Set 加速查詢
        self.crawled_ids: Set[str] = set()
        self._load_history()

        # 統計資訊
        self.stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'not_found': 0,
            'blocked': 0,
        }

        # 智能跳躍狀態
        self.consecutive_failures = 0
        self.smart_jump_count = 0

        # 429 降速狀態
        self.rate_limit_hit = False
        self.rate_limit_cooldown_until = 0

        # 進度更新節流（避免太頻繁）
        self._last_progress_update = 0
        self._progress_update_interval = 1.0  # 最多每秒更新一次

    def _load_source_config(self) -> None:
        """載入來源專屬設定"""
        source_name = self.parser.source_name

        if source_name in settings.NEWS_SOURCES:
            source_config = settings.NEWS_SOURCES[source_name]
            self.concurrent_limit = source_config.get(
                'concurrent_limit', settings.CONCURRENT_REQUESTS
            )
            delay_range = source_config.get(
                'delay_range', (settings.MIN_DELAY, settings.MAX_DELAY)
            )
            self.min_delay, self.max_delay = delay_range
        else:
            self.concurrent_limit = settings.CONCURRENT_REQUESTS
            self.min_delay = settings.MIN_DELAY
            self.max_delay = settings.MAX_DELAY

    def _setup_logger(self) -> None:
        """設置日誌處理器"""
        if self.logger.handlers:
            return

        # 防止日誌重複：不傳播到 root logger
        self.logger.propagate = False

        settings.LOG_DIR.mkdir(parents=True, exist_ok=True)

        log_file = settings.LOG_DIR / f"engine_{self.parser.source_name}_{time.strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        console_handler = logging.StreamHandler()

        formatter = logging.Formatter(
            settings.LOG_FORMAT,
            datefmt=settings.LOG_DATE_FORMAT
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        self.logger.setLevel(settings.LOG_LEVEL)

    def _load_history(self) -> int:
        """
        載入歷史已爬取的 URL 記錄。

        優先使用 SQLite Registry，若發現舊的 txt 檔案則自動遷移。
        """
        try:
            source_name = self.parser.source_name

            # Check for old txt file and migrate if exists
            old_txt_file = settings.CRAWLED_IDS_DIR / f"{source_name}.txt"
            if old_txt_file.exists():
                migrated = self.registry.migrate_from_txt(source_name, old_txt_file)
                if migrated > 0:
                    self.logger.info(f"Migrated {migrated:,} URLs from txt to SQLite")
                    # Rename old file to .txt.bak
                    backup_path = old_txt_file.with_suffix('.txt.bak')
                    old_txt_file.rename(backup_path)
                    self.logger.info(f"Renamed old file to {backup_path.name}")

            # Load URLs from SQLite into memory set for fast lookup
            self.crawled_ids = self.registry.load_urls_for_source(source_name)

            count = len(self.crawled_ids)
            self.logger.info(f"Loaded {count:,} crawled URLs from SQLite registry")
            return count

        except Exception as e:
            self.logger.error(f"Error loading history: {str(e)}")
            return 0

    def _is_crawled(self, url: str) -> bool:
        """檢查 URL 是否已爬取"""
        return url in self.crawled_ids

    def _mark_as_crawled(
        self,
        url: str,
        data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        標記 URL 為已爬取，同時更新內存 Set 和 SQLite Registry。

        Args:
            url: 文章 URL
            data: 文章解析資料（包含 datePublished, dateModified, articleBody 等）
        """
        # Update in-memory set
        self.crawled_ids.add(url)

        # Update SQLite registry with metadata
        date_published = None
        date_modified = None
        content = None

        if data:
            date_published = data.get('datePublished')
            date_modified = data.get('dateModified')
            content = data.get('articleBody', '')

        self.registry.mark_crawled(
            url=url,
            source_id=self.parser.source_name,
            date_published=date_published,
            date_modified=date_modified,
            content=content
        )

    async def _create_session(self) -> Union[aiohttp.ClientSession, 'CurlSession']:
        """創建 Session"""
        if self.session_type == SessionType.CURL_CFFI:
            if not CURL_CFFI_AVAILABLE:
                self.logger.warning("curl_cffi not available, falling back to aiohttp")
                self.session_type = SessionType.AIOHTTP
            else:
                self.logger.info("Creating curl_cffi session")
                return CurlSession(
                    headers=DEFAULT_HEADERS,
                    timeout=settings.REQUEST_TIMEOUT,
                    impersonate="chrome110"
                )

        self.logger.info("Creating aiohttp session")
        import ssl
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        connector = aiohttp.TCPConnector(ssl=ssl_context)

        return aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=settings.REQUEST_TIMEOUT),
            headers=DEFAULT_HEADERS
        )

    def _get_headers(self) -> Dict[str, str]:
        """獲取請求標頭（支援動態 User-Agent 輪換）"""
        headers = DEFAULT_HEADERS.copy()
        headers['User-Agent'] = random.choice(settings.USER_AGENTS)
        return headers

    async def _handle_rate_limit(self) -> None:
        """處理 429 Rate Limit 錯誤"""
        self.rate_limit_hit = True
        cooldown = settings.RATE_LIMIT_COOLDOWN

        self.logger.warning(f"Rate limit detected (429), cooling down for {cooldown}s...")
        self.rate_limit_cooldown_until = time.time() + cooldown

        await asyncio.sleep(cooldown)

        self.rate_limit_hit = False
        self.logger.info(f"Cooldown completed, resuming...")

    async def _fetch(
        self,
        url: str,
        session: Union[aiohttp.ClientSession, 'CurlSession']
    ) -> tuple[Optional[str], CrawlStatus]:
        """獲取 URL 內容，包含重試機制"""
        if self.rate_limit_hit:
            wait_time = self.rate_limit_cooldown_until - time.time()
            if wait_time > 0:
                await asyncio.sleep(wait_time)

        retry_count = 0
        max_retries = settings.MAX_RETRIES

        while retry_count <= max_retries:
            try:
                headers = self._get_headers()

                if self.session_type == SessionType.CURL_CFFI:
                    response = await session.get(url, headers=headers)
                    status = response.status_code

                    if status == 200:
                        return (response.text, CrawlStatus.SUCCESS)
                    elif status == 404:
                        return (None, CrawlStatus.NOT_FOUND)
                    elif status in (403, 429):
                        await self._handle_rate_limit()
                    elif status in (500, 502, 503, 504):
                        pass  # 繼續重試
                    else:
                        return (None, CrawlStatus.BLOCKED)
                else:
                    async with session.get(
                        url,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=settings.REQUEST_TIMEOUT)
                    ) as response:
                        if response.status == 200:
                            return (await response.text(), CrawlStatus.SUCCESS)
                        elif response.status == 404:
                            return (None, CrawlStatus.NOT_FOUND)
                        elif response.status in (403, 429):
                            await self._handle_rate_limit()
                        elif response.status in (500, 502, 503, 504):
                            pass  # 繼續重試
                        else:
                            return (None, CrawlStatus.BLOCKED)

            except asyncio.TimeoutError:
                self.logger.debug(f"Timeout for {url}")
                return (None, CrawlStatus.NOT_FOUND)

            except Exception as e:
                self.logger.debug(f"Network error fetching {url}: {str(e)}")

            retry_count += 1
            if retry_count <= max_retries:
                wait_time = settings.RETRY_DELAY * (2 ** (retry_count - 1))
                await asyncio.sleep(min(wait_time, settings.MAX_RETRY_DELAY))

        return (None, CrawlStatus.BLOCKED)

    async def _random_delay(self):
        """隨機延遲"""
        await asyncio.sleep(random.uniform(self.min_delay, self.max_delay))

    async def _process_article(
        self,
        article_id: int,
        session: Union[aiohttp.ClientSession, 'CurlSession']
    ) -> CrawlStatus:
        """處理單篇文章"""
        url = self.parser.get_url(article_id)

        if not url:
            self.stats['not_found'] += 1
            self._report_progress()
            return CrawlStatus.NOT_FOUND

        if self._is_crawled(url):
            self.stats['skipped'] += 1
            self._report_progress()
            return CrawlStatus.SUCCESS

        html, status = await self._fetch(url, session)

        if status == CrawlStatus.NOT_FOUND:
            self.stats['not_found'] += 1
            self._report_progress()
            return CrawlStatus.NOT_FOUND

        if status == CrawlStatus.BLOCKED:
            self.stats['blocked'] += 1
            self._mark_failed(url, "blocked", "Request blocked (403/429)")
            self._report_progress()
            return CrawlStatus.BLOCKED

        if html is None:
            self.stats['failed'] += 1
            self._mark_failed(url, "fetch_error", "Failed to fetch HTML")
            self._report_progress()
            return CrawlStatus.BLOCKED

        try:
            data = await self.parser.parse(html, url)
            if data is None:
                self.stats['failed'] += 1
                self._mark_failed(url, "parse_error", "Parser returned None")
                self._report_progress()
                return CrawlStatus.NOT_FOUND

            # Mark as crawled with metadata for SQLite registry
            self._mark_as_crawled(url, data)

            # Remove from failed list if it was there (successful retry)
            self.registry.remove_failed(url)

            if self.auto_save:
                success = await self.pipeline.process_and_save(url, data)
                if success:
                    self.logger.info(f"Parsed ID: {article_id:,}")
                    self.stats['success'] += 1
                else:
                    self.stats['failed'] += 1
                    self._mark_failed(url, "save_error", "Pipeline save failed")
            else:
                self.logger.info(f"Parsed ID: {article_id:,}")
                self.stats['success'] += 1

            self._report_progress()
            return CrawlStatus.SUCCESS

        except Exception as e:
            self.logger.error(f"Error parsing {url}: {str(e)}")
            self.stats['failed'] += 1
            self._mark_failed(url, "parse_exception", str(e)[:200])
            self._report_progress()
            return CrawlStatus.BLOCKED

    def _mark_failed(self, url: str, error_type: str, error_message: str) -> None:
        """Record a failed URL in the registry."""
        try:
            self.registry.mark_failed(
                url=url,
                source_id=self.parser.source_name,
                error_type=error_type,
                error_message=error_message
            )
        except Exception as e:
            self.logger.warning(f"Failed to record failed URL: {e}")

    def _report_progress(self) -> None:
        """Report progress via callback (throttled to avoid too frequent updates)."""
        if self.progress_callback is None:
            return

        now = time.time()
        if now - self._last_progress_update < self._progress_update_interval:
            return

        self._last_progress_update = now
        try:
            self.progress_callback(self.stats.copy())
        except Exception as e:
            self.logger.warning(f"Progress callback error: {e}")

    async def run_auto(
        self,
        count: int = 100,
        stop_after_consecutive_skips: int = 10
    ) -> Dict[str, Any]:
        """
        自動爬取最新文章，連續遇到已爬取的文章時自動停止。

        Args:
            count: 最大爬取數量（上限）
            stop_after_consecutive_skips: 連續遇到幾個已爬取的文章後停止（預設 10）

        Returns:
            爬取結果統計
        """
        self.logger.info(f"Starting auto crawl: max {count} articles, stop after {stop_after_consecutive_skips} consecutive skips")

        # 創建會話（提前建立以供 get_latest_id 使用）
        need_close = self.session is None
        if need_close:
            self.session = await self._create_session()

        latest_id = await self.parser.get_latest_id(session=self.session)
        if latest_id is None:
            self.logger.error("Failed to get latest ID")
            if need_close:
                await self.close()
            return {'error': 'Failed to get latest ID'}

        self.logger.info(f"Latest ID: {latest_id:,}")

        # 重置統計
        self.stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'not_found': 0,
            'blocked': 0,
            'early_stopped': False,
            'early_stop_reason': None,
        }

        consecutive_skips = 0
        current_id = latest_id
        processed = 0

        while processed < count:
            url = self.parser.get_url(current_id)

            if url:
                self.stats['total'] += 1

                if self._is_crawled(url):
                    self.stats['skipped'] += 1
                    consecutive_skips += 1
                    self.logger.debug(f"Skip (already crawled): {current_id}, consecutive: {consecutive_skips}")

                    if consecutive_skips >= stop_after_consecutive_skips:
                        self.logger.info(f"Stopping: {consecutive_skips} consecutive skips reached")
                        self.stats['early_stopped'] = True
                        self.stats['early_stop_reason'] = f"連續 {consecutive_skips} 篇已爬取，自動停止"
                        break
                else:
                    # 重置連續 skip 計數
                    consecutive_skips = 0

                    # 實際爬取
                    await self._random_delay()
                    status = await self._process_article(current_id, self.session)

                    # 如果是新文章但爬取失敗（blocked），也算一次有效嘗試
                    if status == CrawlStatus.BLOCKED:
                        # 連續被封鎖也應該停止
                        self.consecutive_failures += 1
                        if self.consecutive_failures >= 5:
                            self.logger.warning(f"Stopping: too many consecutive failures")
                            self.stats['early_stopped'] = True
                            self.stats['early_stop_reason'] = f"連續 {self.consecutive_failures} 次請求被封鎖"
                            break
                    else:
                        self.consecutive_failures = 0

            processed += 1
            current_id -= 1

            self._report_progress()

        if need_close:
            await self.close()

        self._log_stats()
        return self.stats

    async def run_backfill(
        self,
        count: int = 100,
        overlap: int = 10
    ) -> Dict[str, Any]:
        """
        從最老的已爬取文章往前（更早）爬取，用於補齊歷史資料。

        Args:
            count: 要爬取的文章數量
            overlap: 從倒數第 N 個已爬取的文章開始（確保連續性）

        Returns:
            爬取結果統計
        """
        self.logger.info(f"Starting backfill: {count} articles, overlap {overlap}")

        # 找出最老的已爬取文章 ID
        oldest_id = self._get_oldest_crawled_id()

        if oldest_id is None:
            self.logger.warning("No crawled articles found, falling back to auto mode")
            return await self.run_auto(count=count)

        # 從 oldest_id + overlap 開始（往前爬）
        start_id = oldest_id + overlap
        end_id = oldest_id - count

        self.logger.info(f"Backfill range: {start_id:,} -> {end_id:,} (oldest crawled: {oldest_id:,})")

        # 創建會話
        need_close = self.session is None
        if need_close:
            self.session = await self._create_session()

        # 重置統計
        self.stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'not_found': 0,
            'blocked': 0,
            'early_stopped': False,
            'early_stop_reason': None,
        }

        consecutive_not_found = 0
        max_consecutive_not_found = 50  # 連續 50 個不存在就停止

        current_id = start_id
        while current_id > end_id:
            url = self.parser.get_url(current_id)

            if url:
                self.stats['total'] += 1

                if self._is_crawled(url):
                    self.stats['skipped'] += 1
                    consecutive_not_found = 0  # 有找到文章，重置計數
                else:
                    await self._random_delay()
                    status = await self._process_article(current_id, self.session)

                    if status == CrawlStatus.NOT_FOUND:
                        consecutive_not_found += 1
                        if consecutive_not_found >= max_consecutive_not_found:
                            self.logger.info(f"Stopping backfill: {consecutive_not_found} consecutive not found")
                            self.stats['early_stopped'] = True
                            self.stats['early_stop_reason'] = f"連續 {consecutive_not_found} 篇文章不存在 (404)"
                            break
                    else:
                        consecutive_not_found = 0

            current_id -= 1
            self._report_progress()

        if need_close:
            await self.close()

        self._log_stats()
        return self.stats

    def _get_oldest_crawled_id(self) -> Optional[int]:
        """
        取得最老（最小）的已爬取文章 ID。

        透過解析 URL 來提取 ID。
        """
        if not self.crawled_ids:
            return None

        min_id = None
        for url in self.crawled_ids:
            try:
                # 嘗試從 URL 提取 ID
                article_id = self.parser.extract_id_from_url(url)
                if article_id is not None:
                    if min_id is None or article_id < min_id:
                        min_id = article_id
            except Exception:
                continue

        return min_id

    async def run_range(
        self,
        start_id: int,
        end_id: int,
        reverse: bool = False
    ) -> Dict[str, Any]:
        """
        爬取指定範圍的文章 ID

        Args:
            start_id: 起始 ID
            end_id: 結束 ID
            reverse: 是否反向爬取

        Returns:
            爬取結果統計
        """
        if not reverse and start_id > end_id:
            start_id, end_id = end_id, start_id
        elif reverse and start_id < end_id:
            start_id, end_id = end_id, start_id

        step = -1 if reverse else 1
        direction = "reverse" if reverse else "forward"

        self.logger.info(f"Starting crawl: ID {start_id:,} -> {end_id:,} ({direction})")

        total_range = abs(start_id - end_id) + 1
        self.stats = {
            'total': total_range,
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'not_found': 0,
            'blocked': 0,
        }

        need_close = self.session is None
        if need_close:
            self.session = await self._create_session()

        semaphore = asyncio.Semaphore(self.concurrent_limit)

        async def process_with_semaphore(article_id: int):
            async with semaphore:
                await self._random_delay()
                return await self._process_article(article_id, self.session)

        target_ids = list(range(start_id, end_id + step, step))
        tasks = [process_with_semaphore(aid) for aid in target_ids]

        self.logger.info(f"Processing {len(tasks)} articles")
        await asyncio.gather(*tasks, return_exceptions=True)

        if need_close:
            await self.close()

        self._log_stats()
        return self.stats

    async def run_retry(
        self,
        max_retries: int = 3,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Retry failed URLs for this source.

        Args:
            max_retries: Maximum retry attempts (URLs with more retries are skipped)
            limit: Maximum number of URLs to retry in this run

        Returns:
            Crawl statistics
        """
        source_name = self.parser.source_name
        failed_urls = self.registry.get_failed_urls_for_retry(
            source_id=source_name,
            max_retries=max_retries,
            limit=limit
        )

        if not failed_urls:
            self.logger.info(f"No failed URLs to retry for {source_name}")
            return {'total': 0, 'message': 'No failed URLs to retry'}

        self.logger.info(f"Retrying {len(failed_urls)} failed URLs for {source_name}")

        # Reset stats
        self.stats = {
            'total': len(failed_urls),
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'not_found': 0,
            'blocked': 0,
        }

        need_close = self.session is None
        if need_close:
            self.session = await self._create_session()

        semaphore = asyncio.Semaphore(self.concurrent_limit)

        async def process_url_with_semaphore(url: str):
            async with semaphore:
                await self._random_delay()
                return await self._process_url(url, self.session)

        tasks = [process_url_with_semaphore(url) for url in failed_urls]
        await asyncio.gather(*tasks, return_exceptions=True)

        if need_close:
            await self.close()

        self._log_stats()
        return self.stats

    async def run_retry_urls(
        self,
        urls: List[str]
    ) -> Dict[str, Any]:
        """
        Retry specific URLs.

        Args:
            urls: List of URLs to retry

        Returns:
            Crawl statistics
        """
        if not urls:
            self.logger.info("No URLs provided for retry")
            return {'total': 0, 'message': 'No URLs provided'}

        self.logger.info(f"Retrying {len(urls)} specific URLs for {self.parser.source_name}")

        # Reset stats
        self.stats = {
            'total': len(urls),
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'not_found': 0,
            'blocked': 0,
        }

        need_close = self.session is None
        if need_close:
            self.session = await self._create_session()

        semaphore = asyncio.Semaphore(self.concurrent_limit)

        async def process_url_with_semaphore(url: str):
            async with semaphore:
                await self._random_delay()
                return await self._process_url(url, self.session)

        tasks = [process_url_with_semaphore(url) for url in urls]
        await asyncio.gather(*tasks, return_exceptions=True)

        if need_close:
            await self.close()

        self._log_stats()
        return self.stats

    async def _process_url(
        self,
        url: str,
        session: Union[aiohttp.ClientSession, 'CurlSession']
    ) -> CrawlStatus:
        """
        Process a specific URL (for retry mode).

        Similar to _process_article but takes URL directly instead of article_id.
        """
        if self._is_crawled(url):
            self.stats['skipped'] += 1
            # Already crawled, remove from failed list
            self.registry.remove_failed(url)
            self._report_progress()
            return CrawlStatus.SUCCESS

        html, status = await self._fetch(url, session)

        if status == CrawlStatus.NOT_FOUND:
            self.stats['not_found'] += 1
            self._report_progress()
            return CrawlStatus.NOT_FOUND

        if status == CrawlStatus.BLOCKED:
            self.stats['blocked'] += 1
            self._mark_failed(url, "blocked", "Request blocked on retry")
            self._report_progress()
            return CrawlStatus.BLOCKED

        if html is None:
            self.stats['failed'] += 1
            self._mark_failed(url, "fetch_error", "Failed to fetch HTML on retry")
            self._report_progress()
            return CrawlStatus.BLOCKED

        try:
            data = await self.parser.parse(html, url)
            if data is None:
                self.stats['failed'] += 1
                self._mark_failed(url, "parse_error", "Parser returned None on retry")
                self._report_progress()
                return CrawlStatus.NOT_FOUND

            # Mark as crawled
            self._mark_as_crawled(url, data)

            # Remove from failed list (successful retry)
            self.registry.remove_failed(url)
            self.logger.info(f"Successfully retried: {url[:80]}...")

            if self.auto_save:
                success = await self.pipeline.process_and_save(url, data)
                if success:
                    self.stats['success'] += 1
                else:
                    self.stats['failed'] += 1
                    self._mark_failed(url, "save_error", "Pipeline save failed on retry")
            else:
                self.stats['success'] += 1

            self._report_progress()
            return CrawlStatus.SUCCESS

        except Exception as e:
            self.logger.error(f"Error parsing {url} on retry: {str(e)}")
            self.stats['failed'] += 1
            self._mark_failed(url, "parse_exception", str(e)[:200])
            self._report_progress()
            return CrawlStatus.BLOCKED

    async def run_sitemap(
        self,
        sitemap_index_url: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 0
    ) -> Dict[str, Any]:
        """
        從 Sitemap 爬取文章。

        這是最完整的 backfill 方法，因為 sitemap 包含所有文章的
        正確 URL（包含 category），不需要猜測。

        Args:
            sitemap_index_url: Sitemap URL (optional, will use parser's config if not provided)
            date_from: 起始日期 (YYYYMM 格式，如 "202301")，None 表示不限
            date_to: 結束日期 (YYYYMM 格式，如 "202312")，None 表示不限
            limit: 最大爬取數量，0 表示不限

        Returns:
            爬取結果統計
        """
        # 獲取 parser 的 sitemap 配置
        sitemap_config = self.parser.get_sitemap_config()
        if not sitemap_config and not sitemap_index_url:
            self.logger.error(f"No sitemap config available for {self.parser.source_name}")
            return {'error': f'No sitemap config for {self.parser.source_name}'}

        # 使用提供的 URL 或 parser 配置
        sitemap_url = sitemap_index_url or sitemap_config.get('index_url')
        is_index = sitemap_config.get('is_index', True) if sitemap_config else True
        article_pattern = sitemap_config.get('article_url_pattern') if sitemap_config else None

        self.logger.info(f"Starting sitemap crawl from: {sitemap_url}")
        self.logger.info(f"  Is sitemap index: {is_index}")
        if date_from:
            self.logger.info(f"  Date from: {date_from}")
        if date_to:
            self.logger.info(f"  Date to: {date_to}")
        if limit > 0:
            self.logger.info(f"  Limit: {limit}")

        # 重置統計
        self.stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'not_found': 0,
            'blocked': 0,
            'sitemaps_processed': 0,
            'early_stopped': False,
            'early_stop_reason': None,
        }

        # 創建 session
        need_close = self.session is None
        if need_close:
            self.session = await self._create_session()

        try:
            total_urls_to_crawl = []

            if is_index:
                # Sitemap Index: 獲取所有子 sitemap URLs
                sitemap_urls = await self._fetch_sitemap_index(sitemap_url)
                if not sitemap_urls:
                    self.logger.error("Failed to fetch sitemap index or no sitemaps found")
                    return {'error': 'Failed to fetch sitemap index'}

                self.logger.info(f"Found {len(sitemap_urls)} sitemap files")

                # 過濾日期範圍（只適用於 sitemap index）
                if date_from or date_to:
                    sitemap_urls = self._filter_sitemaps_by_date(sitemap_urls, date_from, date_to)
                    self.logger.info(f"After date filter: {len(sitemap_urls)} sitemap files")

                # 逐個處理 sitemap
                for sub_sitemap_url in sitemap_urls:
                    article_urls = await self._fetch_sitemap_urls(sub_sitemap_url, article_pattern)
                    if article_urls:
                        new_urls = [url for url in article_urls if not self._is_crawled(url)]
                        total_urls_to_crawl.extend(new_urls)
                        self.stats['sitemaps_processed'] += 1
                        self.logger.info(f"Sitemap {self.stats['sitemaps_processed']}/{len(sitemap_urls)}: "
                                       f"{len(article_urls)} URLs, {len(new_urls)} new")

                    if limit > 0 and len(total_urls_to_crawl) >= limit:
                        total_urls_to_crawl = total_urls_to_crawl[:limit]
                        self.logger.info(f"Reached limit of {limit} URLs")
                        break
            else:
                # Single Sitemap: 直接獲取文章 URLs
                article_urls = await self._fetch_sitemap_urls(sitemap_url, article_pattern)
                if article_urls:
                    new_urls = [url for url in article_urls if not self._is_crawled(url)]
                    total_urls_to_crawl = new_urls
                    self.stats['sitemaps_processed'] = 1
                    self.logger.info(f"Single sitemap: {len(article_urls)} URLs, {len(new_urls)} new")

                    if limit > 0 and len(total_urls_to_crawl) > limit:
                        total_urls_to_crawl = total_urls_to_crawl[:limit]
                        self.logger.info(f"Applied limit of {limit} URLs")

            self.logger.info(f"Total URLs to crawl: {len(total_urls_to_crawl)}")

            if not total_urls_to_crawl:
                self.logger.info("No new URLs to crawl")
                return self.stats

            # 爬取文章
            self.stats['total'] = len(total_urls_to_crawl)

            semaphore = asyncio.Semaphore(self.concurrent_limit)

            async def process_with_semaphore(url: str):
                async with semaphore:
                    await self._random_delay()
                    return await self._process_url(url, self.session)

            batch_size = 100
            for i in range(0, len(total_urls_to_crawl), batch_size):
                batch = total_urls_to_crawl[i:i + batch_size]
                tasks = [process_with_semaphore(url) for url in batch]
                await asyncio.gather(*tasks, return_exceptions=True)

                self.logger.info(f"Progress: {min(i + batch_size, len(total_urls_to_crawl))}/{len(total_urls_to_crawl)}")

        finally:
            if need_close:
                await self.close()

        self._log_stats()
        return self.stats

    async def _fetch_sitemap_index(self, index_url: str) -> List[str]:
        """
        獲取 sitemap index 並解析出所有 sitemap 文件的 URL。

        Args:
            index_url: Sitemap index URL

        Returns:
            List of sitemap file URLs

        Note: Caller must ensure self.session is initialized.
        """
        import re

        if self.session is None:
            self.logger.error("Session not initialized")
            return []

        try:
            async with self.session.get(
                index_url,
                headers=self._get_headers(),
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    self.logger.error(f"Failed to fetch sitemap index: HTTP {response.status}")
                    return []

                content = await response.text()

            # 解析 sitemap URLs
            # 格式: <loc>https://...</loc>
            pattern = r'<loc>(https?://[^<]+\.xml)</loc>'
            sitemap_urls = re.findall(pattern, content)

            return sitemap_urls

        except Exception as e:
            self.logger.error(f"Error fetching sitemap index: {e}")
            return []

    async def _fetch_sitemap_urls(
        self,
        sitemap_url: str,
        article_pattern: Optional[str] = None
    ) -> List[str]:
        """
        獲取單個 sitemap 文件並解析出所有文章 URL。

        Args:
            sitemap_url: Sitemap file URL
            article_pattern: Regex pattern to extract article URLs (optional)

        Returns:
            List of article URLs
        """
        import re

        try:
            async with self.session.get(
                sitemap_url,
                headers=self._get_headers(),
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    self.logger.warning(f"Failed to fetch sitemap {sitemap_url}: HTTP {response.status}")
                    return []

                # Handle BOM encoding
                content_bytes = await response.read()
                try:
                    content = content_bytes.decode('utf-8-sig')
                except UnicodeDecodeError:
                    content = content_bytes.decode('utf-8', errors='replace')

            # 使用提供的 pattern 或通用 pattern
            if article_pattern:
                pattern = article_pattern
            else:
                # 通用 pattern：匹配所有非 .xml 結尾的 <loc>
                pattern = r'<loc>(https?://[^<]+(?<!\.xml))</loc>'

            article_urls = re.findall(pattern, content)

            return article_urls

        except Exception as e:
            self.logger.warning(f"Error fetching sitemap {sitemap_url}: {e}")
            return []

    def _filter_sitemaps_by_date(
        self,
        sitemap_urls: List[str],
        date_from: Optional[str],
        date_to: Optional[str]
    ) -> List[str]:
        """
        根據日期範圍過濾 sitemap URLs。

        UDN sitemap 命名格式: {TYPE}T{YYYYMM}W{WEEK}.xml
        例如: 2T202312W4.xml

        Args:
            sitemap_urls: List of sitemap URLs
            date_from: 起始日期 (YYYYMM)
            date_to: 結束日期 (YYYYMM)

        Returns:
            Filtered list of sitemap URLs
        """
        import re

        if not date_from and not date_to:
            return sitemap_urls

        filtered = []
        pattern = r'T(\d{6})W'  # 匹配 T202312W 中的 202312

        for url in sitemap_urls:
            match = re.search(pattern, url)
            if match:
                date_str = match.group(1)  # e.g., "202312"

                if date_from and date_str < date_from:
                    continue
                if date_to and date_str > date_to:
                    continue

                filtered.append(url)
            else:
                # 無法解析日期的 sitemap 也保留
                filtered.append(url)

        return filtered

    def _log_stats(self) -> None:
        """輸出統計資訊"""
        self.logger.info("=" * 50)
        self.logger.info("Crawl Statistics:")
        self.logger.info(f"  Total:     {self.stats['total']}")
        self.logger.info(f"  Success:   {self.stats['success']}")
        self.logger.info(f"  Failed:    {self.stats['failed']}")
        self.logger.info(f"  Skipped:   {self.stats['skipped']}")
        self.logger.info(f"  Not Found: {self.stats['not_found']}")
        self.logger.info(f"  Blocked:   {self.stats['blocked']}")

        if self.stats['total'] > 0:
            rate = (self.stats['success'] / self.stats['total']) * 100
            self.logger.info(f"  Success Rate: {rate:.1f}%")

        self.logger.info("=" * 50)

    async def close(self) -> None:
        """關閉 Session"""
        if self.session is not None:
            try:
                if self.session_type == SessionType.AIOHTTP:
                    await asyncio.wait_for(self.session.close(), timeout=5.0)
                else:
                    self.session.close()
                self.logger.info("Session closed")
            except asyncio.TimeoutError:
                self.logger.warning("Session close timed out")
            except Exception as e:
                self.logger.warning(f"Error closing session: {e}")
            finally:
                self.session = None
