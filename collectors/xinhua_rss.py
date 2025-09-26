"""Collector for Xinhua News Agency RSS feeds with GPT-powered translations."""

from __future__ import annotations

import sys
import time
from html import unescape
from pathlib import Path
from typing import Dict, Iterable, List
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

OUT = "docs/data/xinhua_news.json"
HISTORY_OUT = "docs/data/history/xinhua_news.json"
MAX_ITEMS_PER_FEED = 5

# Google News exposes a public RSS endpoint that can be filtered via the
# search syntax. We rely on it as a proxy source after the official feeds
# began rejecting non-mainland IP ranges with HTTP 403 responses in 2025.
GOOGLE_NEWS_BASE = "https://news.google.com/rss/search"
GOOGLE_COMMON_PARAMS = {
    "hl": "zh-CN",
    "gl": "CN",
    "ceid": "CN:zh-Hans",
}

FEEDS: Dict[str, str] = {
    "要闻": "site:xinhuanet.com when:1d",
    "国内": "site:xinhuanet.com 国内 when:1d",
    "财经": "site:xinhuanet.com 财经 when:1d",
    "科技": "site:xinhuanet.com 科技 when:1d",
}


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


def fetch_xinhua_news(max_items: int = MAX_ITEMS_PER_FEED) -> List[dict]:
    """Fetch and translate top stories from configured Xinhua RSS feeds."""

    headers = base_headers()
    headers["User-Agent"] = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15"
    )

    all_items: List[dict] = []

    for category, query in FEEDS.items():
        feed_url = _google_feed_url(query)
        try:
            feed = feedparser.parse(feed_url, request_headers=dict(headers))
        except Exception as exc:  # pragma: no cover - network error handling
            print(f"Failed to fetch {feed_url}: {exc}")
            continue

        if getattr(feed, "bozo", False):  # pragma: no cover - logging only
            exc = getattr(feed, "bozo_exception", None)
            if exc:
                print(f"Feed {feed_url} parse warning: {exc}")

        if getattr(feed, "status", 200) >= 400:
            print(f"Feed {feed_url} returned HTTP {feed.status}")
            continue

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

            if " - " in title:
                title = title.split(" - ", 1)[0].strip()

            translation = translate_text(title) if title else ""

            all_items.append(
                {
                    "title": title or "(无标题)",
                    "value": "",
                    "url": link,
                    "extra": {
                        "category": category,
                        "published": _entry_timestamp(entry),
                        "summary": summary,
                        "source_feed": feed_url,
                        "source_name": entry.get("source", {}).get("title"),
                        "translation": translation,
                    },
                }
            )

    return all_items


def main() -> None:
    items = fetch_xinhua_news()
    payload = schema("Xinhua News Agency RSS", items)
    write_with_history(OUT, HISTORY_OUT, payload)


if __name__ == "__main__":
    main()
