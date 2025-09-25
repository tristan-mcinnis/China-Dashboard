"""Manual integration test for the TianAPI Baidu hot search endpoint.

Run this script only when you have network access and a valid TianAPI key.
It exercises the live API to confirm that we successfully fetch the top 10
searches. The logic lives outside of the automated test suite so CI does not
hammer TianAPI or leak credentials.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from collectors.baidu_top import fetch_baidu_top


def main() -> None:
    api_key = os.getenv("TIANAPI_API_KEY")
    if not api_key:
        raise SystemExit(
            "Set the TIANAPI_API_KEY environment variable before running this script."
        )

    items = fetch_baidu_top(max_items=10)
    if len(items) < 10:
        raise SystemExit(
            f"Expected at least 10 items from TianAPI, received {len(items)} instead."
        )

    for item in items:
        title = item.get("title", "<missing title>")
        url = item.get("url", "<missing url>")
        value = item.get("value", "")
        print(f"{title:40} | {value:>10} | {url}")
if __name__ == "__main__":
    main()
