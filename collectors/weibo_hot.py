"""Collector for Weibo hot search list."""

from __future__ import annotations

import os
import sys
from pathlib import Path

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
from bs4 import BeautifulSoup

from collectors.common import base_headers, backoff_sleep, schema, write_json

OUT = "data/weibo_hot.json"


def fetch_weibo_hot(max_items: int = 10):
    url = "https://s.weibo.com/top/summary"
    headers = base_headers()
    cookie = os.getenv("WEIBO_COOKIE", "").strip()
    if cookie:
        headers["Cookie"] = cookie

    for attempt in range(4):
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "lxml")
                table = soup.select_one("table.table")
                rows = table.select("tr") if table else []
                items = []
                for tr in rows[1 : 1 + max_items]:
                    tds = tr.select("td")
                    if len(tds) >= 2:
                        rank = tds[0].get_text(strip=True)
                        anchor = tds[1].select_one("a")
                        title = anchor.get_text(strip=True) if anchor else ""
                        href = (
                            "https://s.weibo.com" + anchor["href"]
                            if anchor and anchor.has_attr("href")
                            else ""
                        )
                        hot = tds[1].get_text(strip=True).replace(title, "").strip()
                        items.append(
                            {
                                "title": f"{rank}. {title}",
                                "value": hot,
                                "url": href,
                                "extra": {},
                            }
                        )
                return items
        except Exception:
            pass
        backoff_sleep(attempt)
    return []


def main() -> None:
    items = fetch_weibo_hot()
    write_json(OUT, schema("Weibo Hot Search", items))


if __name__ == "__main__":
    main()
