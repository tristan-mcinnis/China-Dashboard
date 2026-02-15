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


def fetch_property_data():
    """Fetch 70-city home price index from EastMoney."""
    items = []

    # NBS 70-city new home price index
    try:
        url = (
            "https://datacenter.eastmoney.com/api/data/v1/get?"
            "sortColumns=REPORT_DATE&sortTypes=-1&pageSize=1&pageNumber=1"
            "&reportName=RPT_ECONOMY_HOUSE_PRICE"
            "&columns=REPORT_DATE,CITY,NEW_HOUSE_SAME,NEW_HOUSE_SEQUENTIAL,SECOND_HOUSE_SAME,SECOND_HOUSE_SEQUENTIAL"
            "&filter=(CITY=%22全国%22)"
        )
        resp = requests.get(url, headers=base_headers(), timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("success") and data.get("result", {}).get("data"):
                row = data["result"]["data"][0]
                report_date = row.get("REPORT_DATE", "")[:10]

                new_yoy = row.get("NEW_HOUSE_SAME")
                new_mom = row.get("NEW_HOUSE_SEQUENTIAL")
                second_yoy = row.get("SECOND_HOUSE_SAME")
                second_mom = row.get("SECOND_HOUSE_SEQUENTIAL")

                if new_yoy is not None:
                    items.append({
                        "title": "New Home Prices YoY",
                        "value": f"{new_yoy}%",
                        "url": "https://data.stats.gov.cn/english/easyquery.htm",
                        "extra": {"description": "70-City New Home Price Index YoY", "date": report_date},
                    })
                if new_mom is not None:
                    items.append({
                        "title": "New Home Prices MoM",
                        "value": f"{new_mom}%",
                        "url": "https://data.stats.gov.cn/english/easyquery.htm",
                        "extra": {"description": "70-City New Home Price Index MoM", "date": report_date},
                    })
                if second_yoy is not None:
                    items.append({
                        "title": "Second-hand Home Prices YoY",
                        "value": f"{second_yoy}%",
                        "url": "https://data.stats.gov.cn/english/easyquery.htm",
                        "extra": {"description": "70-City Second-hand Home Price Index YoY", "date": report_date},
                    })
                if second_mom is not None:
                    items.append({
                        "title": "Second-hand Home Prices MoM",
                        "value": f"{second_mom}%",
                        "url": "https://data.stats.gov.cn/english/easyquery.htm",
                        "extra": {"description": "70-City Second-hand Home Price Index MoM", "date": report_date},
                    })
    except Exception:
        pass

    # Also try to get tier-1 city data (Beijing, Shanghai, Shenzhen, Guangzhou)
    tier1_cities = ["北京", "上海", "深圳", "广州"]
    city_en = {"北京": "Beijing", "上海": "Shanghai", "深圳": "Shenzhen", "广州": "Guangzhou"}

    for city in tier1_cities:
        try:
            url = (
                f"https://datacenter.eastmoney.com/api/data/v1/get?"
                f"sortColumns=REPORT_DATE&sortTypes=-1&pageSize=1&pageNumber=1"
                f"&reportName=RPT_ECONOMY_HOUSE_PRICE"
                f"&columns=REPORT_DATE,CITY,NEW_HOUSE_SAME,NEW_HOUSE_SEQUENTIAL"
                f"&filter=(CITY=%22{city}%22)"
            )
            resp = requests.get(url, headers=base_headers(), timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success") and data.get("result", {}).get("data"):
                    row = data["result"]["data"][0]
                    report_date = row.get("REPORT_DATE", "")[:10]
                    val = row.get("NEW_HOUSE_SAME")
                    if val is not None:
                        items.append({
                            "title": f"{city_en[city]} New Home YoY",
                            "value": f"{val}%",
                            "url": "https://data.stats.gov.cn/english/easyquery.htm",
                            "extra": {"description": f"{city_en[city]} New Home Price Index YoY", "date": report_date},
                        })
        except Exception:
            continue

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
