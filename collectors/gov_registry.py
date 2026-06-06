"""Registry-driven primary-source collector.

Generalises the hand-coded `gov_regulatory.py` (CSRC/CAC/SAMR only) to the full
set of primary-source channels validated in china-future-book's source-registry.
Sources live in `gov_registry_sources.json` (slug, agency, listing URL, mode,
chapter). Each was live-tested for static feed-ability before being added; the
JS-rendered / captcha / blocked channels were deliberately excluded.

Modes:
  scrape     - fetch HTML listing, extract <a title>/<a>text</a>, noise-filter
  scrape_kw  - as scrape, but keep only doc-like titles (通知/公告/意见/令…)
  api_fedreg - US Federal Register JSON API (results[].title/html_url/document_number)

Output: docs/data/gov_registry.json (+ history). Dual-writes to Neon if DATABASE_URL set.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

from collectors.common import base_headers, schema, translate_batch, write_with_history

OUT = "docs/data/gov_registry.json"
HISTORY = "docs/data/history/gov_registry.json"
SEED = Path(__file__).resolve().parent / "gov_registry_sources.json"
REQUEST_TIMEOUT = 20

# Document-type keywords for scrape_kw mode (CAC-style index pages).
DOC_KW = ("通知", "公告", "意见", "规定", "办法", "条例", "政策", "发布", "令", "决定", "方案")

# Pure-navigation / boilerplate noise to drop (substring match, case-insensitive).
NOISE = (
    "icp备", "公网安备", "微博", "微信", "客户端", "français", "english",
    "institutions", "policies", "简介", "网站地图", "联系我们", "版权所有",
    "listarr", "&lt;", "&gt;", "返回首页", "主办", "承办", "phone", "programs",
    "follow xi", "常驻", "代表团",
)

LINK_TITLE = re.compile(r'<a[^>]*href="([^"]+)"[^>]*title="([^"]{6,})"', re.I)
LINK_TITLE_ALT = re.compile(r'<a[^>]*title="([^"]{6,})"[^>]*href="([^"]+)"', re.I)
LINK_TEXT = re.compile(r'<a[^>]*href="([^"]+)"[^>]*>([^<]{8,})</a>', re.I)
DATE_RE = re.compile(r"(20\d{2})[-/.年]\s?(\d{1,2})[-/.月]\s?(\d{1,2})")


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _is_noise(title: str) -> bool:
    t = title.lower()
    if len(title) < 8:
        return True
    return any(n in t for n in NOISE)


def _extract_links(html: str, base_url: str):
    """Return [(title, url)] from a listing page, title-attr preferred."""
    pairs = []
    for href, title in LINK_TITLE.findall(html):
        pairs.append((_clean(title), href))
    for title, href in LINK_TITLE_ALT.findall(html):
        pairs.append((_clean(title), href))
    if len(pairs) < 3:  # fall back to anchor text
        for href, title in LINK_TEXT.findall(html):
            pairs.append((_clean(title), href))

    out, seen = [], set()
    for title, href in pairs:
        if not title or title in seen or _is_noise(title):
            continue
        if href.startswith("#") or href.lower().startswith("javascript"):
            continue
        seen.add(title)
        out.append((title, urljoin(base_url, href)))
    return out


def collect_scrape(src: dict, kw_only: bool = False):
    items = []
    try:
        resp = requests.get(src["url"], headers=base_headers(), timeout=REQUEST_TIMEOUT)
        resp.encoding = "utf-8"
        if resp.status_code != 200:
            return items
        for title, url in _extract_links(resp.text, src["url"]):
            if kw_only and not any(k in title for k in DOC_KW):
                continue
            items.append(_make_item(src, title, url))
            if len(items) >= src.get("max", 6):
                break
    except Exception as exc:
        print(f"  {src['slug']}: scrape error {type(exc).__name__}")
    return items


def collect_fedreg(src: dict):
    items = []
    try:
        resp = requests.get(src["url"], headers=base_headers(), timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return items
        for doc in resp.json().get("results", [])[: src.get("max", 10)]:
            title = _clean(doc.get("title", ""))
            if not title:
                continue
            it = _make_item(src, title, doc.get("html_url", ""))
            it["extra"]["doc_number"] = doc.get("document_number", "")
            it["extra"]["date"] = doc.get("publication_date", "")
            items.append(it)
    except Exception as exc:
        print(f"  {src['slug']}: fedreg error {type(exc).__name__}")
    return items


def _make_item(src: dict, title: str, url: str) -> dict:
    m = DATE_RE.search(title)
    date = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else ""
    return {
        "title": title,
        "value": "",
        "url": url,
        "extra": {
            "agency": src["agency"],
            "agency_zh": src.get("agency_zh", ""),
            "source_slug": src["slug"],
            "chapter": src.get("chapter", ""),
            "lang": src.get("lang", "zh"),
            "date": date,
            "translation": "",
        },
    }


def main() -> None:
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    sources = seed["sources"]

    items = []
    for src in sources:
        mode = src.get("mode", "scrape")
        if mode == "api_fedreg":
            got = collect_fedreg(src)
        elif mode == "scrape_kw":
            got = collect_scrape(src, kw_only=True)
        else:
            got = collect_scrape(src)
        print(f"{src['slug']:<18} {len(got)} items")
        items.extend(got)

    # Translate Chinese titles in one batched DeepSeek call.
    zh_idx = [i for i, it in enumerate(items) if it["extra"]["lang"] == "zh"]
    if zh_idx:
        translations = translate_batch([items[i]["title"] for i in zh_idx])
        for i, en in zip(zh_idx, translations):
            if en:
                items[i]["extra"]["translation"] = en

    agencies = sorted({it["extra"]["agency"] for it in items})
    source = f"Gov Registry ({len(agencies)} channels)"
    payload = schema(source=source, items=items)
    wrote = write_with_history(OUT, HISTORY, payload, min_items=1)
    print(f"\n{len(items)} items from {len(agencies)} channels -> {OUT} (written={wrote})")

    # Dual-write to Neon (no-op if DATABASE_URL unset), mirroring db_writer usage.
    try:
        from collectors.db_writer import write_to_db
        write_to_db(payload, category="gov_registry")
    except Exception as exc:
        print(f"DB write skipped: {type(exc).__name__}")


if __name__ == "__main__":
    main()
