"""Fetch China trade data (imports, exports, trade balance) from EastMoney."""

from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

from collectors.common import backoff_sleep, base_headers, schema, write_with_history

OUT = "docs/data/trade_data.json"
HISTORY = "docs/data/history/trade_data.json"
REQUEST_TIMEOUT = 15

FALLBACK_DATA = [
    {"title": "Exports YoY", "value": "7.1%", "description": "Total Exports Growth"},
    {"title": "Imports YoY", "value": "1.0%", "description": "Total Imports Growth"},
    {"title": "Trade Balance", "value": "$104.8B", "description": "Monthly Trade Balance (USD)"},
]


def fetch_from_eastmoney():
    """Fetch China customs trade data from EastMoney's live RPT_ECONOMY_CUSTOMS.

    Provides monthly export/import value (千美元 = thousand USD), their YoY
    growth, from which we derive exports YoY, imports YoY and the monthly
    trade balance. Returns [] on any failure so the caller can fall back.
    """
    try:
        url = (
            "https://datacenter.eastmoney.com/api/data/v1/get?"
            "sortColumns=REPORT_DATE&sortTypes=-1&pageSize=1&pageNumber=1"
            "&reportName=RPT_ECONOMY_CUSTOMS"
            "&columns=REPORT_DATE,TIME,EXIT_BASE,IMPORT_BASE,EXIT_BASE_SAME,IMPORT_BASE_SAME"
        )
        resp = requests.get(url, headers=base_headers(), timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return []
        data = resp.json()
        if not data.get("success") or not data.get("result", {}).get("data"):
            return []
        row = data["result"]["data"][0]
    except Exception as exc:
        print(f"Customs trade fetch failed: {exc}")
        return []

    month = (row.get("REPORT_DATE") or "")[:7]  # e.g. 2026-04
    exit_base = row.get("EXIT_BASE")      # thousand USD
    import_base = row.get("IMPORT_BASE")  # thousand USD
    exit_yoy = row.get("EXIT_BASE_SAME")
    import_yoy = row.get("IMPORT_BASE_SAME")

    items = []
    if exit_yoy is not None:
        items.append({
            "title": "Exports YoY",
            "value": f"{exit_yoy:+.1f}%",
            "url": "http://english.customs.gov.cn/",
            "extra": {"description": "Total Exports Growth (USD)", "date": month},
        })
    if import_yoy is not None:
        items.append({
            "title": "Imports YoY",
            "value": f"{import_yoy:+.1f}%",
            "url": "http://english.customs.gov.cn/",
            "extra": {"description": "Total Imports Growth (USD)", "date": month},
        })
    if exit_base is not None and import_base is not None:
        balance_bn = (float(exit_base) - float(import_base)) / 1e6  # → USD billions
        items.append({
            "title": "Trade Balance",
            "value": f"${balance_bn:,.1f}B",
            "url": "http://english.customs.gov.cn/",
            "extra": {"description": "Monthly Trade Surplus (USD)", "date": month},
        })

    return items


def main() -> None:
    items = fetch_from_eastmoney()

    if not items:
        for info in FALLBACK_DATA:
            items.append({
                "title": info["title"],
                "value": info["value"],
                "url": "http://english.customs.gov.cn/",
                "extra": {"description": info["description"], "stale": True},
            })

    source = "GACC/EastMoney" if items and not items[0].get("extra", {}).get("stale") else "GACC (fallback)"
    write_with_history(OUT, HISTORY, schema(source=source, items=items), min_items=1)


if __name__ == "__main__":
    main()
