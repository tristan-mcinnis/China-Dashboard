"""Collector for The Paper (澎湃新闻) RSS feed with DeepSeek translations."""

from __future__ import annotations

import sys
import time
from html import unescape
from pathlib import Path
from typing import Iterable, List
from datetime import datetime, timezone
from urllib.parse import urlencode
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

# Use Google News RSS as proxy — the previous feedx.net/rss/thepaper.xml
# feed stopped updating in December 2025.
GOOGLE_NEWS_BASE = "https://news.google.com/rss/search"
GOOGLE_COMMON_PARAMS = {
    "hl": "zh-CN",
    "gl": "CN",
    "ceid": "CN:zh-Hans",
}

FEED_QUERY = "site:thepaper.cn when:1d"


def _google_feed_url(query: str) -> str:
    params = dict(GOOGLE_COMMON_PARAMS)
    params["q"] = query
    return f"{GOOGLE_NEWS_BASE}?{urlencode(params)}"


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
    """Fetch and translate top stories from The Paper via Google News RSS."""

    headers = base_headers()
    headers["User-Agent"] = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15"
    )

    all_items: List[dict] = []

    feed_url = _google_feed_url(FEED_QUERY)
    try:
        feed = feedparser.parse(feed_url, request_headers=dict(headers))
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

        # Clean up title — Google News appends " - thepaper.cn" or source name
        if " - " in title:
            title = title.split(" - ", 1)[0].strip()

        # Translate the title using DeepSeek
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
                    "source_feed": feed_url,
                    "source_name": "澎湃新闻",
                    "translation": translation,
                },
            }
        )

    return all_items


def main() -> None:
    items = fetch_thepaper_news()
    payload = schema("The Paper (澎湃新闻)", items)
    write_with_history(OUT, HISTORY_OUT, payload, min_items=1)


if __name__ == "__main__":
    main()
