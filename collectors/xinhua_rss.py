"""Collector for Xinhua News Agency RSS feeds with GPT-powered translations."""

from __future__ import annotations

import sys
import time
from html import unescape
from pathlib import Path
from typing import Dict, Iterable, List, Sequence
from datetime import datetime, timezone
import re

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import feedparser  # type: ignore
import requests

from collectors.common import (
    base_headers,
    schema,
    translate_text,
    write_with_history,
)

OUT = "docs/data/xinhua_news.json"
HISTORY_OUT = "docs/data/history/xinhua_news.json"
MAX_ITEMS_PER_FEED = 5
REQUEST_TIMEOUT = 15

# Official RSS feeds published by Xinhua News Agency. These URLs have been
# stable for years and are mirrored globally. Adjust or extend as needed.
FEEDS: Dict[str, Sequence[str]] = {
    # International headlines (世界/国际)
    "国际": (
        "https://rss.news.cn/world/index.xml",
        "https://www.news.cn/english/rss/worldrss.xml",
        "http://www.news.cn/worldpro/rss_world.xml",
    ),
    # Mainland China / domestic politics
    "国内": (
        "https://rss.news.cn/china/index.xml",
        "https://www.news.cn/english/rss/domestic.xml",
        "http://www.news.cn/gnpro/rss_gn.xml",
    ),
    # Economy and finance coverage
    "财经": (
        "https://rss.news.cn/finance/index.xml",
        "https://www.news.cn/english/rss/fortune.xml",
        "http://www.news.cn/fortunepro/rss_fortune.xml",
    ),
    # Science and technology developments
    "科技": (
        "https://rss.news.cn/tech/index.xml",
        "https://www.news.cn/english/rss/tech.xml",
        "http://www.news.cn/techpro/rss_tech.xml",
    ),
}


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


def _expand_variants(url: str) -> List[str]:
    """Return candidate URLs for a feed, including HTTPS/HTTP and proxy fallbacks."""

    candidates: List[str] = []

    def _add(candidate: str) -> None:
        if candidate not in candidates:
            candidates.append(candidate)

    _add(url)

    if url.startswith("http://"):
        _add("https://" + url[len("http://") :])
    elif url.startswith("https://"):
        _add("http://" + url[len("https://") :])

    for candidate in list(candidates):
        if "://" not in candidate:
            continue
        scheme, rest = candidate.split("://", 1)
        if not rest:
            continue
        _add(f"https://r.jina.ai/{scheme}://{rest}")

    return candidates


def _download_feed(urls: Sequence[str], headers: dict) -> tuple[bytes, str] | None:
    """Download a feed trying multiple mirrors and proxy fallbacks."""

    for original_url in urls:
        for candidate_url in _expand_variants(original_url):
            try:
                response = requests.get(
                    candidate_url,
                    headers=headers,
                    timeout=REQUEST_TIMEOUT,
                )
            except Exception as exc:  # pragma: no cover - network error handling
                print(f"Failed to fetch {candidate_url}: {exc}")
                continue

            if response.status_code >= 400:
                print(
                    f"Feed {candidate_url} returned HTTP {response.status_code}"
                )
                continue

            content = response.content
            if candidate_url.startswith("https://r.jina.ai/"):
                content = response.text.encode(response.encoding or "utf-8")

            if not content.strip():
                print(f"Feed {candidate_url} returned an empty body")
                continue

            canonical_url = (
                original_url if candidate_url != original_url else candidate_url
            )
            return content, canonical_url

    return None


def fetch_xinhua_news(max_items: int = MAX_ITEMS_PER_FEED) -> List[dict]:
    """Fetch and translate top stories from configured Xinhua RSS feeds."""

    headers = base_headers()
    headers["User-Agent"] = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_3_1) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15"
    )

    all_items: List[dict] = []

    for category, urls in FEEDS.items():
        downloaded = _download_feed(urls, dict(headers))
        if not downloaded:
            continue

        content, source_url = downloaded

        try:
            feed = feedparser.parse(content)
        except Exception as exc:  # pragma: no cover - defensive logging only
            print(f"Feed {source_url} parse error: {exc}")
            continue

        if getattr(feed, "bozo", False):  # pragma: no cover - logging only
            exc = getattr(feed, "bozo_exception", None)
            if exc:
                print(f"Feed {source_url} parse warning: {exc}")

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
                        "source_feed": source_url,
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

