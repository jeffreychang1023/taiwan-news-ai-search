"""
S3 Data Pipeline: Load articles into PostgreSQL with Qwen3 embeddings.

Reads TSV files from data/crawler/articles/, chunks text, embeds with
Qwen3-Embedding-4B (INT8), and writes to PostgreSQL. Builds IVF index
after all data is loaded.

Usage:
    python infra/s3_data_pipeline.py

Run from project root: C:\\users\\user\\nlweb
"""

import json
import logging
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import psycopg
from psycopg.rows import dict_row

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "crawler" / "articles"
CHECKPOINT_FILE = PROJECT_ROOT / "infra" / "s3_checkpoint.json"
LOG_FILE = PROJECT_ROOT / "infra" / "s3_pipeline.log"

DB_URL = "postgresql://nlweb:nlweb_dev@localhost:5432/nlweb"

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SOURCES = {
    "cna": {"prefix": "cna_", "limit": 20_000},
    "ltn": {"prefix": "ltn_", "limit": 20_000},
}

# Chunking parameters
CHUNK_TARGET = 170
CHUNK_MIN = 100
SHORT_ARTICLE_THRESHOLD = 200
CHUNK_OVERLAP = 30

# Batching
ARTICLE_BATCH_SIZE = 500       # articles parsed per batch
EMBED_BATCH_SIZE = 32          # texts sent to model per batch (reduced from 64 for thermal safety)
DB_INSERT_BATCH_SIZE = 500     # chunks inserted per DB batch
PROGRESS_INTERVAL = 100        # log progress every N articles

# Thermal protection
GPU_TEMP_LIMIT = 83            # pause embedding if GPU temp exceeds this (°C)
GPU_TEMP_RESUME = 75           # resume when GPU cools below this (°C)
GPU_TEMP_CHECK_INTERVAL = 10   # check temp every N embed batches

# Sentence-ending delimiters for Chinese text
SENTENCE_ENDS = re.compile(r"(?<=[。！？])")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging() -> logging.Logger:
    logger = logging.getLogger("s3_pipeline")
    logger.setLevel(logging.DEBUG)

    # Console handler — INFO and above
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"
    ))
    logger.addHandler(ch)

    # File handler — DEBUG and above, flush every write
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    ))
    logger.addHandler(fh)

    # Force flush on every log message (so we can monitor in real-time)
    for handler in logger.handlers:
        handler.flush = handler.stream.flush if hasattr(handler, 'stream') else handler.flush

    return logger


log = setup_logging()

# ---------------------------------------------------------------------------
# Checkpoint
# ---------------------------------------------------------------------------

def load_checkpoint() -> set[str]:
    """Load set of already-processed article URLs."""
    if CHECKPOINT_FILE.exists():
        data = json.loads(CHECKPOINT_FILE.read_text(encoding="utf-8"))
        urls = set(data.get("processed_urls", []))
        log.info(f"Checkpoint loaded: {len(urls)} articles already processed")
        return urls
    return set()


def save_checkpoint(processed_urls: set[str]) -> None:
    """Persist processed URLs to disk."""
    CHECKPOINT_FILE.write_text(
        json.dumps({
            "processed_urls": sorted(processed_urls),
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    log.debug(f"Checkpoint saved: {len(processed_urls)} URLs")

# ---------------------------------------------------------------------------
# TSV reading
# ---------------------------------------------------------------------------

def collect_tsv_files(source: str, prefix: str) -> list[Path]:
    """Return TSV files matching prefix, sorted newest-first by filename."""
    files = sorted(
        DATA_DIR.glob(f"{prefix}*.tsv"),
        key=lambda p: p.name,
        reverse=True,
    )
    log.info(f"  {source}: found {len(files)} TSV files")
    return files


def parse_tsv_line(line: str) -> Optional[dict]:
    """Parse a single TSV line into an article dict. Returns None on failure."""
    line = line.strip()
    if not line:
        return None

    parts = line.split("\t", maxsplit=1)
    if len(parts) != 2:
        return None

    url, schema_str = parts

    try:
        schema = json.loads(schema_str)
    except json.JSONDecodeError:
        return None

    body = schema.get("articleBody", "").strip()
    title = schema.get("headline", "").strip()
    if not body or not title:
        return None

    # Parse date
    date_str = schema.get("datePublished", "")
    date_published = None
    if date_str:
        try:
            dt = datetime.fromisoformat(date_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            date_published = dt
        except (ValueError, TypeError):
            pass

    author = schema.get("author", "") or ""
    if isinstance(author, list):
        author = ", ".join(str(a) for a in author)
    author = author.strip() or None

    keywords = schema.get("keywords", [])
    if isinstance(keywords, str):
        keywords = [keywords]

    publisher = schema.get("publisher", "")

    return {
        "url": url.strip(),
        "title": title,
        "author": author,
        "date_published": date_published,
        "content": body,
        "metadata": {
            "keywords": keywords,
            "publisher": publisher,
        },
    }


def read_articles_for_source(
    source: str, prefix: str, limit: int, already_processed: set[str]
) -> list[dict]:
    """Read up to `limit` articles from TSV files (newest first), skipping processed."""
    tsv_files = collect_tsv_files(source, prefix)
    articles: list[dict] = []
    skipped_processed = 0
    skipped_malformed = 0

    for fpath in tsv_files:
        if len(articles) >= limit:
            break
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                for line_no, line in enumerate(f, start=1):
                    if len(articles) >= limit:
                        break
                    art = parse_tsv_line(line)
                    if art is None:
                        skipped_malformed += 1
                        log.debug(f"Malformed line: {fpath.name}:{line_no}")
                        continue
                    if art["url"] in already_processed:
                        skipped_processed += 1
                        continue
                    art["source"] = source
                    articles.append(art)
        except Exception as e:
            log.warning(f"Error reading {fpath}: {e}")

    log.info(
        f"  {source}: collected {len(articles)} articles "
        f"(skipped {skipped_processed} already processed, "
        f"{skipped_malformed} malformed)"
    )
    return articles

# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_text(text: str) -> list[dict]:
    """
    Split text into chunks following NLWeb chunking rules.

    Returns list of dicts with keys:
      - chunk_text: the stored text (no overlap)
      - embed_text: the text to embed (with overlap from previous chunk)
      - chunk_index: 0-based position
    """
    text = text.strip()

    # Short articles: keep as single chunk
    if len(text) <= SHORT_ARTICLE_THRESHOLD:
        return [{
            "chunk_text": text,
            "embed_text": text,
            "chunk_index": 0,
        }]

    # Split at sentence boundaries
    sentences = SENTENCE_ENDS.split(text)
    sentences = [s for s in sentences if s.strip()]

    if not sentences:
        return [{
            "chunk_text": text,
            "embed_text": text,
            "chunk_index": 0,
        }]

    # Build chunks by accumulating sentences up to target size
    raw_chunks: list[str] = []
    current = ""

    for sent in sentences:
        if current and len(current) + len(sent) > CHUNK_TARGET:
            raw_chunks.append(current)
            current = sent
        else:
            current += sent

    if current:
        raw_chunks.append(current)

    # Merge short trailing chunk with previous
    if len(raw_chunks) > 1 and len(raw_chunks[-1]) < CHUNK_MIN:
        raw_chunks[-2] += raw_chunks[-1]
        raw_chunks.pop()

    # Merge any remaining short chunks (scan left to right)
    merged: list[str] = []
    for chunk in raw_chunks:
        if merged and len(chunk) < CHUNK_MIN:
            merged[-1] += chunk
        else:
            merged.append(chunk)

    # Build output with overlap
    result: list[dict] = []
    for i, chunk in enumerate(merged):
        if i == 0:
            overlap_prefix = ""
        else:
            prev = merged[i - 1]
            overlap_prefix = prev[-CHUNK_OVERLAP:]

        result.append({
            "chunk_text": chunk,
            "embed_text": overlap_prefix + chunk,
            "chunk_index": i,
        })

    return result

# ---------------------------------------------------------------------------
# Embedding model
# ---------------------------------------------------------------------------

def get_gpu_temp() -> Optional[int]:
    """Get GPU temperature in °C. Returns None if unavailable."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5
        )
        return int(result.stdout.strip())
    except Exception:
        return None


def wait_for_gpu_cooldown():
    """Block until GPU temperature drops below GPU_TEMP_RESUME."""
    temp = get_gpu_temp()
    if temp is None or temp <= GPU_TEMP_LIMIT:
        return

    log.warning(f"GPU temp {temp}°C exceeds {GPU_TEMP_LIMIT}°C — pausing embedding")
    while True:
        time.sleep(15)
        temp = get_gpu_temp()
        if temp is None:
            log.warning("Cannot read GPU temp, resuming anyway")
            return
        log.info(f"  GPU cooling: {temp}°C (resume at <={GPU_TEMP_RESUME}°C)")
        if temp <= GPU_TEMP_RESUME:
            log.info(f"GPU cooled to {temp}°C — resuming")
            return


def load_embedding_model():
    """Load Qwen3-Embedding-4B with INT8 quantization."""
    log.info("Loading Qwen3-Embedding-4B (INT8)...")
    t0 = time.time()

    from sentence_transformers import SentenceTransformer
    from transformers import BitsAndBytesConfig

    quantization_config = BitsAndBytesConfig(load_in_8bit=True)
    model = SentenceTransformer(
        "Qwen/Qwen3-Embedding-4B",
        model_kwargs={"quantization_config": quantization_config},
        truncate_dim=1024,
    )
    elapsed = time.time() - t0
    log.info(f"Model loaded in {elapsed:.1f}s")
    return model


def embed_texts(model, texts: list[str]) -> np.ndarray:
    """Embed a list of texts. Returns (N, 1024) float32 array.

    Uses large blocks with internal batch_size=8 (proven fast in S1 test).
    Thermal check between blocks.
    """
    if not texts:
        return np.empty((0, 1024), dtype=np.float32)

    BLOCK_SIZE = 100  # texts per encode call (thermal check between blocks)

    all_embeddings = []
    for i in range(0, len(texts), BLOCK_SIZE):
        # Thermal check between blocks
        if i > 0:
            wait_for_gpu_cooldown()

        block = texts[i : i + BLOCK_SIZE]
        # batch_size=8 matches S1 proven speed (10.7 chunks/sec)
        embs = model.encode(block, batch_size=8, show_progress_bar=False)
        all_embeddings.append(embs)

    return np.vstack(all_embeddings).astype(np.float32)

# ---------------------------------------------------------------------------
# Database operations
# ---------------------------------------------------------------------------

def get_connection() -> psycopg.Connection:
    """Open a new database connection."""
    return psycopg.connect(DB_URL, row_factory=dict_row)


def drop_ivf_index(conn: psycopg.Connection) -> None:
    """Drop the (empty-table) IVF index so inserts are fast."""
    log.info("Dropping existing IVF index (if any)...")
    conn.execute("DROP INDEX IF EXISTS idx_chunks_embedding_ivf")
    conn.commit()
    log.info("IVF index dropped")


def create_ivf_index(conn: psycopg.Connection) -> None:
    """Create IVFFlat index after data is loaded."""
    log.info("Creating IVFFlat index (this may take a while)...")
    t0 = time.time()
    conn.execute("""
        CREATE INDEX idx_chunks_embedding_ivf
        ON chunks
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 1000)
    """)
    conn.commit()
    elapsed = time.time() - t0
    log.info(f"IVF index created in {elapsed:.1f}s")


def insert_article(conn: psycopg.Connection, article: dict) -> Optional[int]:
    """Insert article row, return article_id. Returns None if URL already exists."""
    try:
        result = conn.execute(
            """
            INSERT INTO articles (url, title, author, source, date_published, content, metadata)
            VALUES (%(url)s, %(title)s, %(author)s, %(source)s, %(date_published)s, %(content)s, %(metadata)s)
            ON CONFLICT (url) DO NOTHING
            RETURNING id
            """,
            {
                "url": article["url"],
                "title": article["title"],
                "author": article["author"],
                "source": article["source"],
                "date_published": article["date_published"],
                "content": article["content"],
                "metadata": json.dumps(article["metadata"], ensure_ascii=False),
            },
        )
        row = result.fetchone()
        if row is None:
            # URL already existed
            return None
        return row["id"]
    except Exception as e:
        log.error(f"Failed to insert article {article['url']}: {e}")
        conn.rollback()
        return None


def insert_chunks_batch(
    conn: psycopg.Connection,
    chunk_rows: list[tuple],
) -> int:
    """
    Batch insert chunk rows using executemany.
    Each tuple: (article_id, chunk_index, chunk_text, embedding_list, tsv_text)
    Returns number of rows inserted.
    """
    if not chunk_rows:
        return 0

    try:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO chunks (article_id, chunk_index, chunk_text, embedding, tsv)
                VALUES (%s, %s, %s, %s::vector, %s)
                ON CONFLICT (article_id, chunk_index) DO NOTHING
                """,
                chunk_rows,
            )
        conn.commit()
        return len(chunk_rows)
    except Exception as e:
        log.error(f"Failed to insert chunk batch: {e}")
        conn.rollback()
        return 0

# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def format_time(seconds: float) -> str:
    """Format seconds into HH:MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def main():
    log.info("=" * 70)
    log.info("S3 Data Pipeline — Starting")
    log.info(f"Project root: {PROJECT_ROOT}")
    log.info(f"Data dir: {DATA_DIR}")
    log.info(f"Database: {DB_URL}")
    log.info("=" * 70)

    # -----------------------------------------------------------------------
    # 1. Load checkpoint
    # -----------------------------------------------------------------------
    processed_urls = load_checkpoint()

    # -----------------------------------------------------------------------
    # 2. Collect articles from TSV files
    # -----------------------------------------------------------------------
    log.info("Collecting articles from TSV files...")
    all_articles: list[dict] = []
    for source, cfg in SOURCES.items():
        articles = read_articles_for_source(
            source, cfg["prefix"], cfg["limit"], processed_urls,
        )
        all_articles.extend(articles)

    total_target = len(all_articles)
    log.info(f"Total articles to process: {total_target}")

    if total_target == 0:
        log.info("Nothing to process. Exiting.")
        return

    # -----------------------------------------------------------------------
    # 3. Load embedding model
    # -----------------------------------------------------------------------
    model = load_embedding_model()

    # -----------------------------------------------------------------------
    # 4. Drop IVF index for fast inserts
    # -----------------------------------------------------------------------
    conn = get_connection()
    drop_ivf_index(conn)

    # -----------------------------------------------------------------------
    # 5. Process articles in batches
    # -----------------------------------------------------------------------
    pipeline_start = time.time()
    total_articles_done = 0
    total_chunks_created = 0
    total_errors = 0

    for batch_start in range(0, total_target, ARTICLE_BATCH_SIZE):
        batch_end = min(batch_start + ARTICLE_BATCH_SIZE, total_target)
        batch = all_articles[batch_start:batch_end]

        # --- Phase A: Parse, chunk, and collect embed texts ---
        # Each entry: (article, chunks, embed_start_idx)
        # chunks is None if chunking failed
        article_chunk_info: list[tuple[dict, Optional[list[dict]], int]] = []
        all_embed_texts: list[str] = []

        for article in batch:
            try:
                chunks = chunk_text(article["content"])
                start_idx = len(all_embed_texts)
                for c in chunks:
                    all_embed_texts.append(c["embed_text"])
                article_chunk_info.append((article, chunks, start_idx))
            except Exception as e:
                log.error(f"Chunking failed for {article['url']}: {e}")
                total_errors += 1
                # Still track as processed to not retry
                processed_urls.add(article["url"])
                article_chunk_info.append((article, None, -1))

        # --- Phase B: Embed all texts in this batch ---
        if all_embed_texts:
            embeddings = embed_texts(model, all_embed_texts)
        else:
            embeddings = np.empty((0, 1024), dtype=np.float32)

        # --- Phase C: Insert into database ---
        chunk_insert_buffer: list[tuple] = []

        for article, chunks, start_idx in article_chunk_info:
            if chunks is None:
                # Chunking had failed
                continue

            try:
                article_id = insert_article(conn, article)
                if article_id is None:
                    # Duplicate URL — mark as processed and skip
                    processed_urls.add(article["url"])
                    total_articles_done += 1
                    continue

                for j, chunk in enumerate(chunks):
                    emb_idx = start_idx + j
                    emb_vector = embeddings[emb_idx].tolist()
                    # Format as pgvector string: [0.1, 0.2, ...]
                    emb_str = "[" + ",".join(f"{v:.8f}" for v in emb_vector) + "]"
                    chunk_insert_buffer.append((
                        article_id,
                        chunk["chunk_index"],
                        chunk["chunk_text"],
                        emb_str,
                        chunk["chunk_text"],  # tsv = same as chunk_text for bigm search
                    ))

                processed_urls.add(article["url"])
                total_articles_done += 1
                total_chunks_created += len(chunks)

            except Exception as e:
                log.error(f"Error processing article {article['url']}: {e}")
                total_errors += 1
                processed_urls.add(article["url"])
                conn.rollback()

            # Flush chunk buffer when full
            if len(chunk_insert_buffer) >= DB_INSERT_BATCH_SIZE:
                inserted = insert_chunks_batch(conn, chunk_insert_buffer)
                if inserted == 0 and chunk_insert_buffer:
                    log.warning(f"Chunk batch insert returned 0 for {len(chunk_insert_buffer)} rows")
                chunk_insert_buffer = []

        # Flush remaining chunks
        if chunk_insert_buffer:
            insert_chunks_batch(conn, chunk_insert_buffer)
            chunk_insert_buffer = []

        # --- Checkpoint ---
        save_checkpoint(processed_urls)

        # --- Progress logging ---
        elapsed = time.time() - pipeline_start
        if total_articles_done > 0:
            rate = total_articles_done / elapsed  # articles/sec
            remaining = total_target - total_articles_done
            eta_seconds = remaining / rate if rate > 0 else 0
        else:
            rate = 0
            eta_seconds = 0

        # Log at batch boundaries and at progress intervals
        if total_articles_done % PROGRESS_INTERVAL < ARTICLE_BATCH_SIZE or batch_end == total_target:
            log.info(
                f"Progress: {total_articles_done}/{total_target} articles "
                f"({total_articles_done / total_target * 100:.1f}%) | "
                f"{total_chunks_created} chunks | "
                f"Elapsed: {format_time(elapsed)} | "
                f"Rate: {rate:.1f} art/s | "
                f"ETA: {format_time(eta_seconds)}"
            )

    # -----------------------------------------------------------------------
    # 6. Create IVF index
    # -----------------------------------------------------------------------
    log.info("All articles processed. Building IVF index...")
    create_ivf_index(conn)

    # -----------------------------------------------------------------------
    # 7. Final summary
    # -----------------------------------------------------------------------
    total_elapsed = time.time() - pipeline_start
    avg_speed = total_articles_done / total_elapsed if total_elapsed > 0 else 0

    log.info("=" * 70)
    log.info("Pipeline Complete")
    log.info(f"  Total articles inserted: {total_articles_done}")
    log.info(f"  Total chunks created:    {total_chunks_created}")
    log.info(f"  Errors:                  {total_errors}")
    log.info(f"  Total time:              {format_time(total_elapsed)}")
    log.info(f"  Average speed:           {avg_speed:.2f} articles/sec")
    log.info("=" * 70)

    # -----------------------------------------------------------------------
    # 8. Verify counts
    # -----------------------------------------------------------------------
    try:
        art_count = conn.execute("SELECT COUNT(*) AS cnt FROM articles").fetchone()["cnt"]
        chunk_count = conn.execute("SELECT COUNT(*) AS cnt FROM chunks").fetchone()["cnt"]
        log.info(f"  DB verification: {art_count} articles, {chunk_count} chunks in database")
    except Exception as e:
        log.warning(f"Could not verify DB counts: {e}")

    conn.close()
    log.info("Done.")


if __name__ == "__main__":
    main()
