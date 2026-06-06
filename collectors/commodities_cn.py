"""Fetch China-demand commodity prices (real-economy pulse).

The dashboard already tracks equity indices, FX and policy rates, but had no
commodity layer — yet iron ore, copper and crude are among the cleanest
high-frequency proxies for Chinese industrial demand. These are globally priced,
so we reuse the same reliable Yahoo Finance chart endpoint as ``indices_cn.py``.

Output: ``docs/data/commodities.json`` (standard schema). Each item:
  {"title": "Iron Ore", "value": 161.9, "url": ..., "extra": {"symbol", "chg_pct", "ts", "unit"}}

NOTE (future tier): a China 10Y government-bond yield belongs here too, but the
benchmark yield needs the correct EastMoney secid (the obvious one returns a
single bond's clean price, not the benchmark yield) — deferred rather than ship a
mislabeled number.
"""

from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

from collectors.common import backoff_sleep, schema, write_with_history

OUT = "docs/data/commodities.json"
HISTORY = "docs/data/history/commodities.json"

# (display name, Yahoo symbol, unit). Ordered by China-demand relevance.
SYMBOLS = [
    ("Iron Ore", "TIO=F", "USD/t"),
    ("Copper", "HG=F", "USD/lb"),
    ("Crude (WTI)", "CL=F", "USD/bbl"),
    ("Crude (Brent)", "BZ=F", "USD/bbl"),
    ("Gold", "GC=F", "USD/oz"),
]


def fetch_quote(symbol: str):
    urls = [
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
        f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}",
    ]
    for url in urls:
        for attempt in range(2):
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                resp = requests.get(url, headers=headers, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("chart", {}).get("result"):
                        meta = data["chart"]["result"][0].get("meta", {})
                        price = meta.get("regularMarketPrice")
                        if price is not None:
                            prev = meta.get("previousClose")
                            return {
                                "value": round(price, 2),
                                "chg_pct": round(((price - prev) / prev) * 100, 2) if prev else None,
                                "ts": meta.get("regularMarketTime"),
                            }
            except Exception as e:
                print(f"Commodity fetch attempt {attempt + 1} failed for {symbol}: {e}")
            backoff_sleep(attempt)
    return {"value": None, "chg_pct": None, "ts": None}


def main() -> None:
    items = []
    for name, symbol, unit in SYMBOLS:
        quote = fetch_quote(symbol)
        items.append(
            {
                "title": name,
                "value": quote["value"],
                "url": f"https://finance.yahoo.com/quote/{symbol}",
                "extra": {
                    "symbol": symbol,
                    "unit": unit,
                    "chg_pct": quote["chg_pct"],
                    "ts": quote["ts"],
                    "pillar": "economy",
                },
            }
        )
    payload = schema(source="Yahoo Finance — commodities", items=items)
    wrote = write_with_history(OUT, HISTORY, payload, min_items=1)
    print(f"Commodities written: {len(items)} items -> {OUT} (written={wrote})")


if __name__ == "__main__":
    main()
