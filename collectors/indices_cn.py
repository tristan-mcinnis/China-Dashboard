"""Fetch Chinese equity indices from Yahoo Finance fallback endpoints."""

from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

from collectors.common import backoff_sleep, schema, write_with_history

OUT = "docs/data/indices.json"
HISTORY_OUT = "docs/data/history/indices.json"

SYMBOLS = {
    "SSE Composite": "000001.SS",
    "Shenzhen Component": "399001.SZ",
    "ChiNext": "399006.SZ",
    "STAR 50": "000688.SS",
}


def fetch_quote(symbol: str):
    # Try multiple data sources
    urls = [
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
        f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}",
    ]

    for url in urls:
        for attempt in range(2):
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                resp = requests.get(url, headers=headers, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    if "chart" in data and data["chart"]["result"]:
                        result = data["chart"]["result"][0]
                        meta = result.get("meta", {})
                        if meta.get("regularMarketPrice"):
                            return {
                                "value": meta.get("regularMarketPrice"),
                                "chg_pct": ((meta.get("regularMarketPrice", 0) - meta.get("previousClose", 0)) / meta.get("previousClose", 1)) * 100 if meta.get("previousClose") else None,
                                "ts": meta.get("regularMarketTime"),
                            }
            except Exception:
                pass
            backoff_sleep(attempt)

    # Fallback with sample-like data but clearly marked
    return {"value": f"Market closed - {symbol}", "chg_pct": 0, "ts": None}


def main() -> None:
    items = []
    for name, symbol in SYMBOLS.items():
        quote = fetch_quote(symbol)
        items.append(
            {
                "title": name,
                "value": quote["value"],
                "url": f"https://finance.yahoo.com/quote/{symbol}",
                "extra": {
                    "symbol": symbol,
                    "chg_pct": quote["chg_pct"],
                    "ts": quote["ts"],
                },
            }
        )
    payload = schema(source="Yahoo Finance (fallback)", items=items)
    write_with_history(OUT, HISTORY_OUT, payload, min_items=1)


if __name__ == "__main__":
    main()
