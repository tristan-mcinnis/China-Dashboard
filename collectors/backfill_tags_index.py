"""One-time backfill of the cumulative tag index from Neon Postgres.

The live site only keeps a rolling JSON window, but Neon holds every news item
since the dual-write started. This script reads the historical ``news_items``
table and folds matching stories into ``docs/data/tags_index.json`` so the
dashboard's clickable tags have real historical depth immediately, instead of
only accruing from the next digest run onward.

Matching strategy: for every tag already in the index (the theme vocabulary
produced by ``daily_digest.py``), attach historical news items whose headline
contains a keyword of that tag. Safe to re-run — stories are de-duplicated by
(date, url/title), so repeated runs converge rather than double-count.

Usage:
    DATABASE_URL=postgres://...  python collectors/backfill_tags_index.py
    # optional flags:
    #   --days N    only scan items from the last N days (default: all)
    #   --dry-run   report what would change without writing
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collectors import tags_index as tags
from collectors.common import write_json


def _connect():
    url = os.getenv("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL not set — export your Neon connection string first.")
    try:
        import psycopg2
    except ImportError:
        sys.exit("psycopg2 not installed — run: pip install psycopg2-binary")
    return psycopg2.connect(url)


def _platform_for(source: str) -> str:
    """Best-effort source → platform label for the index record."""
    s = (source or "").lower()
    for key in ("baidu", "weibo", "wechat", "tencent", "xinhua",
                "thepaper", "paper", "ladymax", "csrc", "cac", "samr"):
        if key in s:
            return key
    return source or "archive"


def fetch_news(conn, days: int | None):
    """Yield historical news records shaped like digest stories."""
    where = ""
    params: list = []
    if days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        where = "WHERE captured_at >= %s"
        params.append(cutoff)

    sql = (
        "SELECT title, title_en, url, category, source, captured_at "
        f"FROM news_items {where} ORDER BY captured_at ASC"
    )
    with conn.cursor() as cur:
        cur.execute(sql, params)
        for title, title_en, url, category, source, captured_at in cur.fetchall():
            date = ""
            if captured_at:
                date = captured_at.strftime("%Y-%m-%d") if hasattr(captured_at, "strftime") \
                    else str(captured_at)[:10]
            yield {
                "title": title or "",
                "primary_title": title or "",
                "english_title": title_en or "",
                "url": url or "",
                "category": category or "",
                "date": date,
                "platforms": [_platform_for(source)],
            }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=None,
                    help="Only scan items from the last N days (default: all).")
    ap.add_argument("--dry-run", action="store_true",
                    help="Report changes without writing the index.")
    args = ap.parse_args()

    index = tags.load_index()
    vocab = [v.get("label") or k for k, v in index["tags"].items()]
    if not vocab:
        sys.exit("Tag index is empty — run daily_digest.py at least once first so "
                 "there is a theme vocabulary to backfill against.")

    print(f"Backfilling {len(vocab)} tags from Neon"
          + (f" (last {args.days} days)" if args.days else " (full history)") + " …")

    conn = _connect()
    scanned = 0
    added = 0
    try:
        for story in fetch_news(conn, args.days):
            scanned += 1
            for tag in vocab:
                if tags.story_matches(story, tag):
                    if tags.add_story(index, tag, tags.make_record(story, story["date"])):
                        added += 1
    finally:
        conn.close()

    print(f"Scanned {scanned} historical news items → +{added} new story-tag links.")
    top = sorted(index["tags"].items(), key=lambda kv: -kv[1]["count"])[:15]
    for _, v in top:
        print(f"  {v['count']:3d}  {v['label']}")

    if args.dry_run:
        print("\n--dry-run: index NOT written.")
        return

    index["updated_at"] = datetime.now(timezone(timedelta(hours=8))).isoformat()
    write_json(tags.INDEX_PATH, index, indent=2, min_items=0)
    print(f"\nWrote {tags.INDEX_PATH} ({len(index['tags'])} tags).")


if __name__ == "__main__":
    main()
