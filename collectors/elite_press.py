"""Collector for institutional / elite-press China sources (Sinocism-style).

Pulls headlines from the source families that a serious China brief is built on:

  * Party organs & official media   -> ``politics``   (People's Daily, Qiushi)
  * Domestic financial media        -> ``economy``    (Caixin, Yicai, 21CBH)
  * Tech / industry media           -> ``tech``       (36Kr, Jiemian)
  * Western elite press on China    -> ``geopolitics``(FT, WSJ, Bloomberg, Reuters, SCMP)

Each feed is tagged with a provisional ``pillar`` so the daily digest can group
items into thematic blocks. The official mainland feeds reject non-mainland IPs
with HTTP 403, so — exactly like ``xinhua_rss.py`` — we proxy every source
through Google News' public RSS search endpoint (``site:`` queries), which is
reachable from GitHub Actions runners. Chinese-language headlines are translated
with DeepSeek; English-language sources pass through untranslated.

Output: ``docs/data/elite_press.json`` (standard collector schema). Each item:
  {
    "title":  "<original headline>",
    "url":    "<article link>",
    "extra": {
      "source":      "Caixin",            # English source label
      "source_zh":   "财新",               # native label ("" for EN sources)
      "pillar":      "economy",           # provisional thematic pillar
      "lang":        "zh" | "en",
      "translation": "<EN headline>",     # == title for EN sources
      "published":   "<ISO-8601 UTC>",
      "summary":     "<short context>"
    }
  }
"""

from __future__ import annotations

import re
import sys
import time
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Iterable, List
from urllib.parse import urlencode

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import feedparser  # type: ignore
from dotenv import load_dotenv

load_dotenv()

from collectors.common import base_headers, schema, translate_batch, write_with_history

OUT = "docs/data/elite_press.json"
HISTORY_OUT = "docs/data/history/elite_press.json"
MAX_ITEMS_PER_FEED = 4

GOOGLE_NEWS_BASE = "https://news.google.com/rss/search"


def _gnews_url(query: str, *, lang: str) -> str:
    if lang == "zh":
        params = {"hl": "zh-CN", "gl": "CN", "ceid": "CN:zh-Hans"}
    else:
        params = {"hl": "en-US", "gl": "US", "ceid": "US:en"}
    params["q"] = query
    return f"{GOOGLE_NEWS_BASE}?{urlencode(params)}"


# Source matrix. Each entry: (source_en, source_zh, pillar, lang, google_query)
# Window kept tight (when:2d) so the brief reflects the current news cycle;
# Qiushi is a low-frequency theory journal, so it gets a wider window.
FEEDS = [
    # --- Party organs & official media -> politics ----------------------------
    ("People's Daily", "人民日报", "politics", "zh", "site:people.com.cn when:2d"),
    ("Qiushi", "求是", "politics", "zh", "site:qstheory.cn when:10d"),
    # --- Domestic financial media -> economy ----------------------------------
    ("Caixin", "财新", "economy", "zh", "site:caixin.com when:2d"),
    ("Yicai", "第一财经", "economy", "zh", "site:yicai.com when:2d"),
    ("21st Century Business Herald", "21世纪经济报道", "economy", "zh", "site:21jingji.com when:2d"),
    ("Caixin Global", "", "economy", "en", "site:caixinglobal.com when:2d"),
    # --- Tech / industry media -> tech ----------------------------------------
    ("36Kr", "36氪", "tech", "zh", "site:36kr.com when:2d"),
    ("Jiemian", "界面新闻", "tech", "zh", "site:jiemian.com when:2d"),
    # --- Western elite press on China -> geopolitics --------------------------
    ("Financial Times", "", "geopolitics", "en", '"China" site:ft.com when:2d'),
    ("Wall Street Journal", "", "geopolitics", "en", '"China" site:wsj.com when:2d'),
    ("Bloomberg", "", "geopolitics", "en", '"China" site:bloomberg.com when:2d'),
    ("Reuters", "", "geopolitics", "en", "China site:reuters.com when:2d"),
    ("South China Morning Post", "", "geopolitics", "en", "China site:scmp.com when:2d"),
]


def _timestamp(entry: feedparser.FeedParserDict) -> str:
    st = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if st:
        try:
            return datetime.fromtimestamp(time.mktime(st), timezone.utc).isoformat().replace("+00:00", "Z")
        except Exception:
            pass
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _strip_html(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"<[^>]+>", " ", text)
    return " ".join(unescape(cleaned).split())[:400]


def _clean_title(title: str) -> str:
    """Google News appends ' - <source>'; drop it for a clean headline."""
    if " - " in title:
        title = title.rsplit(" - ", 1)[0].strip()
    return title.strip()


def _norm(title: str) -> str:
    return re.sub(r"\s+", "", (title or "").lower())


def fetch_elite_press(max_items: int = MAX_ITEMS_PER_FEED) -> List[dict]:
    headers = base_headers()
    headers["User-Agent"] = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15"
    )

    items: List[dict] = []
    seen: set[str] = set()

    for source_en, source_zh, pillar, lang, query in FEEDS:
        url = _gnews_url(query, lang=lang)
        try:
            feed = feedparser.parse(url, request_headers=dict(headers))
        except Exception as exc:  # pragma: no cover - network error handling
            print(f"Failed to fetch {source_en} ({url}): {exc}")
            continue

        if getattr(feed, "status", 200) >= 400:
            print(f"{source_en} feed returned HTTP {feed.status}")
            continue

        entries: Iterable[feedparser.FeedParserDict] = getattr(feed, "entries", [])
        taken = 0
        for entry in entries:
            if taken >= max_items:
                break
            title = _clean_title((entry.get("title") or "").strip())
            link = (entry.get("link") or "").strip()
            if not title:
                continue
            key = _norm(title)
            if not key or key in seen:
                continue
            seen.add(key)
            taken += 1
            items.append(
                {
                    "title": title,
                    "value": "",
                    "url": link,
                    "extra": {
                        "source": source_en,
                        "source_zh": source_zh,
                        "pillar": pillar,
                        "lang": lang,
                        "published": _timestamp(entry),
                        "summary": _strip_html(
                            entry.get("summary") or entry.get("description") or ""
                        ),
                        "translation": "",
                    },
                }
            )

    # Translate only the Chinese-language headlines; pass English through as-is.
    zh_idx = [i for i, it in enumerate(items) if it["extra"]["lang"] == "zh"]
    translations = translate_batch([items[i]["title"] for i in zh_idx]) if zh_idx else []
    for i, en in zip(zh_idx, translations):
        items[i]["extra"]["translation"] = en
    for it in items:
        if it["extra"]["lang"] == "en":
            it["extra"]["translation"] = it["title"]

    return items


def main() -> None:
    items = fetch_elite_press()
    payload = schema("Elite press (party organs, financial, tech, Western)", items)
    write_with_history(OUT, HISTORY_OUT, payload, min_items=1)
    print(f"Elite press written: {len(items)} items -> {OUT}")


if __name__ == "__main__":
    main()
