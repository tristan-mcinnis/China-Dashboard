"""Fetch NBS monthly economic indicators (CPI, PPI, PMI) from public sources."""

from __future__ import annotations

import re
import sys
from pathlib import Path

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

from collectors.common import backoff_sleep, base_headers, schema, write_with_history

OUT = "docs/data/nbs_monthly.json"
HISTORY = "docs/data/history/nbs_monthly.json"
REQUEST_TIMEOUT = 15

# Known recent values as fallback
FALLBACK_DATA = {
    "CPI YoY": {"value": "0.1%", "description": "Consumer Price Index, Year-over-Year"},
    "PPI YoY": {"value": "-2.3%", "description": "Producer Price Index, Year-over-Year"},
    "PMI Manufacturing": {"value": "49.1", "description": "Official Manufacturing PMI"},
    "PMI Non-Manufacturing": {"value": "50.2", "description": "Official Non-Manufacturing PMI"},
    "Industrial Production YoY": {"value": "6.2%", "description": "Industrial Production Growth"},
    "Retail Sales YoY": {"value": "3.7%", "description": "Retail Sales Growth"},
}


def fetch_from_eastmoney():
    """Fetch macro data from East Money API."""
    items = []

    indicators = [
        {
            "report": "RPT_ECONOMY_CPI",
            "columns": "REPORT_DATE,NATIONAL_SAME,NATIONAL_BASE,NATIONAL_SEQUENTIAL",
            "title": "CPI YoY",
            "field": "NATIONAL_SAME",
            "suffix": "%",
            "description": "Consumer Price Index, Year-over-Year",
        },
        {
            "report": "RPT_ECONOMY_PPI",
            "columns": "REPORT_DATE,PPI_SAME,PPI_SEQUENTIAL",
            "title": "PPI YoY",
            "field": "PPI_SAME",
            "suffix": "%",
            "description": "Producer Price Index, Year-over-Year",
        },
        {
            "report": "RPT_ECONOMY_PMI",
            "columns": "REPORT_DATE,MAKE_INDEX,NMAKE_INDEX",
            "title_map": {"MAKE_INDEX": "PMI Manufacturing", "NMAKE_INDEX": "PMI Non-Manufacturing"},
            "description_map": {
                "MAKE_INDEX": "Official Manufacturing PMI",
                "NMAKE_INDEX": "Official Non-Manufacturing PMI",
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

            if "title_map" in ind:
                # Multiple fields from one report
                for field, title in ind["title_map"].items():
                    val = row.get(field)
                    if val is not None:
                        items.append({
                            "title": title,
                            "value": str(val),
                            "url": "https://data.stats.gov.cn/english/easyquery.htm",
                            "extra": {
                                "description": ind["description_map"][field],
                                "date": report_date,
                            },
                        })
            else:
                val = row.get(ind["field"])
                if val is not None:
                    items.append({
                        "title": ind["title"],
                        "value": f"{val}{ind.get('suffix', '')}",
                        "url": "https://data.stats.gov.cn/english/easyquery.htm",
                        "extra": {
                            "description": ind["description"],
                            "date": report_date,
                        },
                    })

        except Exception:
            continue

    return items


def fetch_from_tradingeconomics():
    """Fallback: try Trading Economics."""
    items = []
    indicators = [
        ("china/consumer-price-index-cpi", "CPI YoY", "Consumer Price Index, Year-over-Year"),
        ("china/business-confidence", "PMI Manufacturing", "Official Manufacturing PMI"),
    ]

    for path, title, description in indicators:
        try:
            resp = requests.get(
                f"https://tradingeconomics.com/{path}",
                headers=base_headers(),
                timeout=REQUEST_TIMEOUT,
            )
            if resp.status_code == 200:
                match = re.search(r'<span[^>]*id="[^"]*last[^"]*"[^>]*>([-\d.]+)</span>', resp.text)
                if match:
                    items.append({
                        "title": title,
                        "value": match.group(1),
                        "url": f"https://tradingeconomics.com/{path}",
                        "extra": {"description": description},
                    })
        except Exception:
            continue

    return items


def main() -> None:
    # Try primary source
    items = fetch_from_eastmoney()

    # Fallback to Trading Economics if primary failed
    if len(items) < 2:
        te_items = fetch_from_tradingeconomics()
        # Merge without duplicates
        existing_titles = {i["title"] for i in items}
        for item in te_items:
            if item["title"] not in existing_titles:
                items.append(item)

    # Ultimate fallback with stale flag
    if not items:
        for name, info in FALLBACK_DATA.items():
            items.append({
                "title": name,
                "value": info["value"],
                "url": "https://data.stats.gov.cn/english/easyquery.htm",
                "extra": {"description": info["description"], "stale": True},
            })

    source = "NBS/EastMoney" if items and not items[0].get("extra", {}).get("stale") else "NBS (fallback)"
    write_with_history(OUT, HISTORY, schema(source=source, items=items), min_items=1)


if __name__ == "__main__":
    main()
