"""Fetch PBOC key policy rates (LPR, MLF, RRR) from public sources."""

from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

from collectors.common import backoff_sleep, base_headers, schema, write_with_history

OUT = "docs/data/pboc_rates.json"
HISTORY = "docs/data/history/pboc_rates.json"
REQUEST_TIMEOUT = 15

# Known latest rates as fallback (updated manually when rates change)
FALLBACK_RATES = {
    "1Y LPR": {"value": "3.10%", "description": "1-Year Loan Prime Rate"},
    "5Y LPR": {"value": "3.60%", "description": "5-Year Loan Prime Rate"},
    "MLF": {"value": "2.50%", "description": "Medium-term Lending Facility"},
    "RRR": {"value": "9.50%", "description": "Reserve Requirement Ratio (large banks)"},
    "7D Reverse Repo": {"value": "1.50%", "description": "7-Day Reverse Repo Rate"},
    "CN 10Y Yield": {"value": "1.65%", "description": "China 10-Year Government Bond Yield"},
}


def fetch_lpr_from_yahoo():
    """Try to get LPR data from a financial data source."""
    # Use an open data API for Chinese rates
    urls = [
        "https://query1.finance.yahoo.com/v8/finance/chart/CNY=X",
    ]
    for url in urls:
        for attempt in range(2):
            try:
                resp = requests.get(url, headers=base_headers(), timeout=REQUEST_TIMEOUT)
                if resp.status_code == 200:
                    return resp.json()
            except Exception:
                pass
            backoff_sleep(attempt)
    return None


def fetch_rates():
    """Fetch PBOC rates from multiple sources with fallback."""
    items = []

    # Try to scrape from Trading Economics or similar
    sources_tried = []

    # Source 1: Try Trading Economics China page
    try:
        resp = requests.get(
            "https://tradingeconomics.com/china/interest-rate",
            headers={
                **base_headers(),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 200 and "interest" in resp.text.lower():
            # Try to extract rate from the page
            import re

            # Look for the current rate value on the page
            match = re.search(r'<span[^>]*id="[^"]*last[^"]*"[^>]*>([\d.]+)</span>', resp.text)
            if match:
                rate_val = match.group(1)
                sources_tried.append("tradingeconomics")
                # This gives us the benchmark rate
                items.append({
                    "title": "PBOC Benchmark Rate",
                    "value": f"{rate_val}%",
                    "url": "https://tradingeconomics.com/china/interest-rate",
                    "extra": {"description": "PBOC Benchmark Interest Rate"},
                })
    except Exception:
        pass

    # Source 2: Try East Money API (Chinese financial data)
    try:
        resp = requests.get(
            "https://datacenter.eastmoney.com/api/data/v1/get?"
            "sortColumns=REPORT_DATE&sortTypes=-1&pageSize=1&pageNumber=1"
            "&reportName=RPT_ECONOMY_LPR&columns=REPORT_DATE,LPR1Y,LPR5Y",
            headers=base_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("success") and data.get("result", {}).get("data"):
                row = data["result"]["data"][0]
                lpr1y = row.get("LPR1Y")
                lpr5y = row.get("LPR5Y")
                report_date = row.get("REPORT_DATE", "")[:10]
                sources_tried.append("eastmoney")

                if lpr1y is not None:
                    items.append({
                        "title": "1Y LPR",
                        "value": f"{lpr1y}%",
                        "url": "http://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125440/index.html",
                        "extra": {"description": "1-Year Loan Prime Rate", "date": report_date},
                    })
                if lpr5y is not None:
                    items.append({
                        "title": "5Y LPR",
                        "value": f"{lpr5y}%",
                        "url": "http://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125440/index.html",
                        "extra": {"description": "5-Year Loan Prime Rate", "date": report_date},
                    })
    except Exception:
        pass

    # If we got real data, return it
    if items:
        return items, sources_tried

    # Fallback to known rates (marked as stale)
    for name, info in FALLBACK_RATES.items():
        items.append({
            "title": name,
            "value": info["value"],
            "url": "http://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125440/index.html",
            "extra": {"description": info["description"], "stale": True},
        })

    return items, ["fallback"]


def main() -> None:
    items, sources = fetch_rates()
    source_str = f"PBOC ({', '.join(sources)})" if sources else "PBOC"
    write_with_history(OUT, HISTORY, schema(source=source_str, items=items), min_items=1)


if __name__ == "__main__":
    main()
