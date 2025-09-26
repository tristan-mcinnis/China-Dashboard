"""Collector for The Paper (澎湃新闻) RSS feed with GPT-powered translations."""

from __future__ import annotations

import sys
import time
from html import unescape
from pathlib import Path
from typing import Iterable, List
from datetime import datetime, timezone
import re

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import feedparser  # type: ignore
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from collectors.common import (
    base_headers,
    schema,
    translate_text,
    write_with_history,
)

OUT = "docs/data/thepaper_news.json"
HISTORY_OUT = "docs/data/history/thepaper_news.json"
MAX_ITEMS = 20

# The Paper RSS feed URL
FEED_URL = "https://feedx.net/rss/thepaper.xml"


def _entry_timestamp(entry: feedparser.FeedParserDict) -> str:
    """Return an ISO-8601 UTC timestamp for a feed entry."""

    struct_time = getattr(entry, "published_parsed", None) or getattr(
        entry, "updated_parsed", None
    )
    if struct_time:
        try:
            dt = datetime.fromtimestamp(time.mktime(struct_time), timezone.utc)
            return dt.isoformat().replace("+00:00", "Z")
        except Exception:
            pass

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _strip_html(text: str) -> str:
    """Lightweight HTML tag stripper for RSS summaries."""

    if not text:
        return ""

    cleaned = re.sub(r"<[^>]+>", " ", text)
    cleaned = " ".join(unescape(cleaned).split())
    return cleaned[:500]


def fetch_thepaper_news(max_items: int = MAX_ITEMS) -> List[dict]:
    """Fetch and translate top stories from The Paper RSS feed."""

    headers = base_headers()
    headers["User-Agent"] = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15"
    )

    all_items: List[dict] = []

    try:
        feed = feedparser.parse(FEED_URL, request_headers=dict(headers))
    except Exception as exc:
        print(f"Failed to fetch The Paper RSS feed: {exc}")
        return all_items

    if getattr(feed, "bozo", False):
        exc = getattr(feed, "bozo_exception", None)
        if exc:
            print(f"The Paper feed parse warning: {exc}")

    if getattr(feed, "status", 200) >= 400:
        print(f"The Paper feed returned HTTP {feed.status}")
        return all_items

    entries: Iterable[feedparser.FeedParserDict] = getattr(feed, "entries", [])

    for entry in list(entries)[:max_items]:
        title = (entry.get("title") or "").strip()
        link = (entry.get("link") or "").strip()

        if not title and not link:
            continue

        summary = _strip_html(
            entry.get("summary")
            or entry.get("description")
            or entry.get("subtitle")
            or ""
        )

        # Clean up title if needed
        if " - " in title:
            title = title.split(" - ", 1)[0].strip()

        # Translate the title using GPT-4o-mini
        translation = translate_text(title) if title else ""

        # Extract category from entry tags if available
        category = ""
        tags = entry.get("tags", [])
        if tags and isinstance(tags, list):
            category = tags[0].get("term", "") if isinstance(tags[0], dict) else ""

        all_items.append(
            {
                "title": title or "(无标题)",
                "value": "",
                "url": link,
                "extra": {
                    "category": category or "新闻",
                    "published": _entry_timestamp(entry),
                    "summary": summary,
                    "source_feed": FEED_URL,
                    "source_name": "澎湃新闻",
                    "translation": translation,
                },
            }
        )

    return all_items


def main() -> None:
    items = fetch_thepaper_news()
    payload = schema("The Paper (澎湃新闻)", items)
    write_with_history(OUT, HISTORY_OUT, payload)


if __name__ == "__main__":
    main()