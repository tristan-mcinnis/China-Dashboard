"""Collector for Baidu realtime top searches."""

from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
from bs4 import BeautifulSoup

from collectors.common import base_headers, backoff_sleep, schema, write_json

OUT = "docs/data/baidu_top.json"


def fetch_baidu_top(max_items: int = 10):
    url = "https://top.baidu.com/board?tab=realtime"
    for attempt in range(4):
        try:
            resp = requests.get(url, headers=base_headers(), timeout=15)
            if resp.status_code == 200 and ("Baidu Top" in resp.text or "百度热搜" in resp.text):
                soup = BeautifulSoup(resp.text, "lxml")
                items = []
                for card in soup.select(".category-wrap_iQLoo")[:max_items]:
                    title_el = card.select_one(".c-single-text-ellipsis")
                    hot_el = card.select_one(".hot-index_1Bl1a")
                    link_el = card.select_one("a")
                    title = title_el.get_text(strip=True) if title_el else ""
                    hot = hot_el.get_text(strip=True) if hot_el else ""
                    url_item = (
                        "https://top.baidu.com" + link_el["href"]
                        if link_el and link_el.has_attr("href")
                        else ""
                    )
                    if title:
                        items.append(
                            {
                                "title": title,
                                "value": hot,
                                "url": url_item,
                                "extra": {},
                            }
                        )
                return items
        except Exception:
            pass
        backoff_sleep(attempt)
    return []


def main() -> None:
    items = fetch_baidu_top()
    payload = schema(source="Baidu Top Realtime", items=items)
    write_json(OUT, payload)


if __name__ == "__main__":
    main()
