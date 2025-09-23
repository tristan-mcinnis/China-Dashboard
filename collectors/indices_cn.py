"""Fetch Chinese equity indices from Yahoo Finance fallback endpoints."""

from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

from collectors.common import backoff_sleep, schema, write_json

OUT = "docs/data/indices.json"

SYMBOLS = {
    "SSE Composite": "000001.SS",
    "Shenzhen Component": "399001.SZ",
    "ChiNext": "399006.SZ",
    "STAR 50": "000688.SS",
}


def fetch_quote(symbol: str):
    url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={symbol}"
    for attempt in range(4):
        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200:
                data = resp.json().get("quoteResponse", {}).get("result", [])
                if data:
                    item = data[0]
                    return {
                        "value": item.get("regularMarketPrice"),
                        "chg_pct": item.get("regularMarketChangePercent"),
                        "ts": item.get("regularMarketTime"),
                    }
        except Exception:
            pass
        backoff_sleep(attempt)
    return {"value": None, "chg_pct": None, "ts": None}


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
    write_json(OUT, schema(source="Yahoo Finance (fallback)", items=items))


if __name__ == "__main__":
    main()
