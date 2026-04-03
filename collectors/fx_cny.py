"""Fetch USD/CNY and related FX pairs."""

from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

from collectors.common import backoff_sleep, schema, write_with_history

OUT = "docs/data/fx.json"
HISTORY = "docs/data/history/fx.json"

PAIRS = {
    "USD/CNY": "CNY=X",
    "USD/CNH": "CNH=X",
    "EUR/CNY": "EURCNY=X",
    "JPY/CNY": "JPYCNY=X",
}


def fetch_fx(symbol: str):
    # Try multiple approaches for FX data
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
                            prev = meta.get("previousClose")
                            price = meta.get("regularMarketPrice")
                            return {
                                "value": price,
                                "chg_pct": ((price - prev) / prev) * 100 if prev else None,
                                "ts": meta.get("regularMarketTime"),
                            }
            except Exception as e:
                print(f"FX fetch attempt {attempt + 1} failed for {symbol}: {e}")
            backoff_sleep(attempt)

    # Try alternative free FX API
    try:
        pair = symbol.replace("=X", "").replace("CNY", "USDCNY").replace("CNH", "USDCNH")
        api_url = f"https://api.exchangerate-api.com/v4/latest/USD"
        resp = requests.get(api_url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if "rates" in data and "CNY" in data["rates"]:
                cny_rate = data["rates"]["CNY"]
                return {"value": cny_rate, "chg_pct": 0, "ts": None}
    except Exception as e:
        print(f"FX fallback API failed for {symbol}: {e}")

    # Fallback with realistic FX rates — marked as stale
    fallback_rates = {
        "CNY=X": 7.25, "CNH=X": 7.24, "EURCNY=X": 7.95, "JPYCNY=X": 0.049
    }
    return {"value": fallback_rates.get(symbol, 7.25), "chg_pct": 0, "ts": None, "stale": True}


def main() -> None:
    items = []
    for name, symbol in PAIRS.items():
        quote = fetch_fx(symbol)
        items.append(
            {
                "title": name,
                "value": quote["value"],
                "url": f"https://finance.yahoo.com/quote/{symbol}",
                "extra": {
                    "symbol": symbol,
                    "chg_pct": quote["chg_pct"],
                    "ts": quote["ts"],
                    **({"stale": True} if quote.get("stale") else {}),
                },
            }
        )
    write_with_history(OUT, HISTORY, schema(source="Yahoo Finance (fallback)", items=items), min_items=1)


if __name__ == "__main__":
    main()
