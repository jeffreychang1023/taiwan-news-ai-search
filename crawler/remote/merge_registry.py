"""
merge_registry.py - 合併兩個 crawled_registry.db

用途：從 GCP 或其他機器搬遷回來時，把遠端的 registry 合併進本地 DB。

策略：
  - crawled_articles: INSERT OR IGNORE（不覆蓋已有的）
  - not_found_articles: INSERT OR IGNORE
  - scan_watermarks: 取較大的 watermark（確保不倒退）

Usage:
  python merge_registry.py <source_db> <target_db>

Example:
  python merge_registry.py registry-gcp.db data/crawler/crawled_registry.db
"""

import sqlite3
import sys
from pathlib import Path


def merge_registries(source_path: str, target_path: str, dry_run: bool = False):
    """Merge source registry into target registry."""
    source = Path(source_path)
    target = Path(target_path)

    if not source.exists():
        print(f"Error: Source DB not found: {source}")
        sys.exit(1)
    if not target.exists():
        print(f"Error: Target DB not found: {target}")
        sys.exit(1)

    print(f"Source: {source} ({source.stat().st_size / 1024 / 1024:.1f} MB)")
    print(f"Target: {target} ({target.stat().st_size / 1024 / 1024:.1f} MB)")

    target_conn = sqlite3.connect(str(target))
    target_conn.execute("PRAGMA journal_mode=WAL")

    # Attach source DB
    target_conn.execute(f"ATTACH DATABASE ? AS source_db", (str(source),))

    # --- Pre-merge stats ---
    target_crawled = target_conn.execute("SELECT COUNT(*) FROM crawled_articles").fetchone()[0]
    source_crawled = target_conn.execute("SELECT COUNT(*) FROM source_db.crawled_articles").fetchone()[0]
    print(f"\ncrawled_articles — target: {target_crawled:,}, source: {source_crawled:,}")

    target_nf = target_conn.execute("SELECT COUNT(*) FROM not_found_articles").fetchone()[0]
    source_nf = target_conn.execute("SELECT COUNT(*) FROM source_db.not_found_articles").fetchone()[0]
    print(f"not_found_articles — target: {target_nf:,}, source: {source_nf:,}")

    if dry_run:
        print("\n[DRY RUN] No changes made.")
        target_conn.close()
        return

    # --- Merge crawled_articles ---
    result = target_conn.execute("""
        INSERT OR IGNORE INTO crawled_articles (source_id, url, crawled_at)
        SELECT source_id, url, crawled_at FROM source_db.crawled_articles
    """)
    crawled_inserted = result.rowcount
    print(f"\ncrawled_articles: inserted {crawled_inserted:,} new rows")

    # --- Merge not_found_articles ---
    result = target_conn.execute("""
        INSERT OR IGNORE INTO not_found_articles (source_id, url, checked_at)
        SELECT source_id, url, checked_at FROM source_db.not_found_articles
    """)
    nf_inserted = result.rowcount
    print(f"not_found_articles: inserted {nf_inserted:,} new rows")

    # --- Merge scan_watermarks (take the larger value) ---
    source_watermarks = target_conn.execute(
        "SELECT source_id, last_scanned_id, last_scanned_date FROM source_db.scan_watermarks"
    ).fetchall()

    wm_updated = 0
    for source_id, src_id, src_date in source_watermarks:
        target_wm = target_conn.execute(
            "SELECT last_scanned_id, last_scanned_date FROM scan_watermarks WHERE source_id = ?",
            (source_id,)
        ).fetchone()

        if target_wm is None:
            # Target doesn't have this watermark at all — insert it
            target_conn.execute(
                "INSERT INTO scan_watermarks (source_id, last_scanned_id, last_scanned_date) VALUES (?, ?, ?)",
                (source_id, src_id, src_date)
            )
            wm_updated += 1
        else:
            tgt_id, tgt_date = target_wm
            new_id = max(src_id or 0, tgt_id or 0) or None
            new_date = max(src_date or "", tgt_date or "") or None

            if new_id != tgt_id or new_date != tgt_date:
                target_conn.execute(
                    "UPDATE scan_watermarks SET last_scanned_id = ?, last_scanned_date = ? WHERE source_id = ?",
                    (new_id, new_date, source_id)
                )
                wm_updated += 1

    print(f"scan_watermarks: updated {wm_updated} entries")

    target_conn.commit()
    target_conn.execute("DETACH DATABASE source_db")
    target_conn.close()

    print(f"\nMerge complete. Target DB: {target}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python merge_registry.py <source_db> <target_db> [--dry-run]")
        print("Example: python merge_registry.py registry-gcp.db data/crawler/crawled_registry.db")
        sys.exit(1)

    dry_run = "--dry-run" in sys.argv
    merge_registries(sys.argv[1], sys.argv[2], dry_run=dry_run)
