"""Fetch China property market data (70-city home prices) from EastMoney."""

from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

from collectors.common import base_headers, schema, write_with_history

OUT = "docs/data/property.json"
HISTORY = "docs/data/history/property.json"
REQUEST_TIMEOUT = 15


NBS_URL = "https://data.stats.gov.cn/english/easyquery.htm"
CITY_EN = {"北京": "Beijing", "上海": "Shanghai", "深圳": "Shenzhen", "广州": "Guangzhou"}


def fetch_property_data():
    """Fetch the NBS 70-city home price index from EastMoney.

    EastMoney's RPT_ECONOMY_HOUSE_PRICE is reported per-city as a base-100
    index (e.g. 96.6 = -3.4% YoY). There is no national row, so we pull the
    latest month's full city list and average it into a 70-city headline,
    then surface the four tier-1 cities. Returns [] on failure.
    """
    try:
        url = (
            "https://datacenter.eastmoney.com/api/data/v1/get?"
            "sortColumns=REPORT_DATE&sortTypes=-1&pageSize=200&pageNumber=1"
            "&reportName=RPT_ECONOMY_HOUSE_PRICE"
            "&columns=REPORT_DATE,CITY,FIRST_COMHOUSE_SAME,FIRST_COMHOUSE_SEQUENTIAL,SECOND_HOUSE_SAME"
        )
        resp = requests.get(url, headers=base_headers(), timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return []
        data = resp.json()
        rows = data.get("result", {}).get("data") if data.get("success") else None
        if not rows:
            return []
    except Exception as exc:
        print(f"Property data fetch failed: {exc}")
        return []

    latest = rows[0].get("REPORT_DATE", "")
    month = latest[:7]
    month_rows = [r for r in rows if r.get("REPORT_DATE") == latest]

    def avg_yoy(field):
        vals = [r[field] for r in month_rows if isinstance(r.get(field), (int, float))]
        if not vals:
            return None
        # Index is base-100; subtract 100 to express as YoY % change.
        return sum(vals) / len(vals) - 100

    def avg_mom(field):
        vals = [r[field] for r in month_rows if isinstance(r.get(field), (int, float))]
        if not vals:
            return None
        return sum(vals) / len(vals) - 100

    items = []
    new_yoy = avg_yoy("FIRST_COMHOUSE_SAME")
    new_mom = avg_mom("FIRST_COMHOUSE_SEQUENTIAL")
    second_yoy = avg_yoy("SECOND_HOUSE_SAME")
    n = len(month_rows)

    if new_yoy is not None:
        items.append({
            "title": "New Home Prices YoY",
            "value": f"{new_yoy:+.1f}%",
            "url": NBS_URL,
            "extra": {"description": f"{n}-City New Home Price Index, avg YoY", "date": month},
        })
    if new_mom is not None:
        items.append({
            "title": "New Home Prices MoM",
            "value": f"{new_mom:+.1f}%",
            "url": NBS_URL,
            "extra": {"description": f"{n}-City New Home Price Index, avg MoM", "date": month},
        })
    if second_yoy is not None:
        items.append({
            "title": "Resale Prices YoY",
            "value": f"{second_yoy:+.1f}%",
            "url": NBS_URL,
            "extra": {"description": f"{n}-City Second-hand Home Price Index, avg YoY", "date": month},
        })

    # Tier-1 cities (most-watched property markets)
    for city, en in CITY_EN.items():
        row = next((r for r in month_rows if r.get("CITY") == city), None)
        if row and isinstance(row.get("FIRST_COMHOUSE_SAME"), (int, float)):
            items.append({
                "title": f"{en} New Home YoY",
                "value": f"{row['FIRST_COMHOUSE_SAME'] - 100:+.1f}%",
                "url": NBS_URL,
                "extra": {"description": f"{en} New Home Price Index YoY", "date": month},
            })

    return items


def main() -> None:
    items = fetch_property_data()

    if not items:
        # Minimal fallback
        items = [{
            "title": "New Home Prices YoY",
            "value": "-4.5%",
            "url": "https://data.stats.gov.cn/english/easyquery.htm",
            "extra": {"description": "70-City New Home Price Index YoY", "stale": True},
        }]

    source = "NBS/EastMoney" if not items[0].get("extra", {}).get("stale") else "NBS (fallback)"
    write_with_history(OUT, HISTORY, schema(source=source, items=items), min_items=1)


if __name__ == "__main__":
    main()
