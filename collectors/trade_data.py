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
    """Fetch trade data from EastMoney API."""
    items = []

    indicators = [
        {
            "report": "RPT_ECONOMY_EXPORT",
            "columns": "REPORT_DATE,EXIT_SAME,IMPORT_SAME,EXIT_ACCUMULATE_SAME,IMPORT_ACCUMULATE_SAME",
            "fields": {
                "EXIT_SAME": ("Exports YoY", "Total Exports Growth", "%"),
                "IMPORT_SAME": ("Imports YoY", "Total Imports Growth", "%"),
            },
        },
        {
            "report": "RPT_ECONOMY_TRADE",
            "columns": "REPORT_DATE,EXPORT_BASE,IMPORT_BASE,EXIT_SURPLUS",
            "fields": {
                "EXIT_SURPLUS": ("Trade Balance", "Monthly Trade Balance (USD $100M)", ""),
            },
        },
    ]

    for ind in indicators:
        try:
            url = (
                f"https://datacenter.eastmoney.com/api/data/v1/get?"
                f"sortColumns=REPORT_DATE&sortTypes=-1&pageSize=1&pageNumber=1"
                f"&reportName={ind['report']}&columns={ind['columns']}"
            )
            resp = requests.get(url, headers=base_headers(), timeout=REQUEST_TIMEOUT)
            if resp.status_code != 200:
                continue

            data = resp.json()
            if not data.get("success") or not data.get("result", {}).get("data"):
                continue

            row = data["result"]["data"][0]
            report_date = row.get("REPORT_DATE", "")[:10]

            for field, (title, description, suffix) in ind["fields"].items():
                val = row.get(field)
                if val is not None:
                    display_val = f"{val}{suffix}" if suffix else str(val)
                    items.append({
                        "title": title,
                        "value": display_val,
                        "url": "http://english.customs.gov.cn/",
                        "extra": {"description": description, "date": report_date},
                    })
        except Exception:
            continue

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
