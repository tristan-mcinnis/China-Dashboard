"""Collector for Weibo hot search list using TianAPI."""

from __future__ import annotations

import os
import sys
from pathlib import Path

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
from dotenv import load_dotenv

from collectors.common import base_headers, backoff_sleep, schema, write_json, translate_text

# Load environment variables from .env file
load_dotenv()

OUT = "docs/data/weibo_hot.json"


def fetch_weibo_hot(max_items: int = 10):
    api_key = os.getenv("TIANAPI_API_KEY")
    if not api_key:
        print("Warning: TIANAPI_API_KEY not found in environment variables")
        return []

    url = "https://apis.tianapi.com/weibohot/index"
    params = {"key": api_key}

    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, headers=base_headers(), timeout=15)
            if resp.status_code == 200:
                data = resp.json()

                if data.get("code") == 200 and "result" in data:
                    result = data["result"]
                    if "list" in result and isinstance(result["list"], list):
                        items = []
                        for i, item in enumerate(result["list"][:max_items], 1):
                            if isinstance(item, dict):
                                hotword = item.get("hotword", "")
                                hotwordnum = item.get("hotwordnum", "")
                                hottag = item.get("hottag", "")

                                if hotword:
                                    # Format hot score
                                    if hotwordnum and hotwordnum.strip():
                                        hot_display = f"{hotwordnum.strip()} 热度"
                                    else:
                                        hot_display = ""

                                    # Build search URL
                                    search_url = f"https://s.weibo.com/weibo?q={hotword}"

                                    # Add tag to title if present
                                    title_with_tag = f"{i}. {hotword}"
                                    if hottag and hottag.strip():
                                        title_with_tag += f" [{hottag.strip()}]"

                                    # Get translation for the hotword (without numbering and tags)
                                    translation = translate_text(hotword)

                                    items.append({
                                        "title": title_with_tag,
                                        "value": hot_display,
                                        "url": search_url,
                                        "extra": {
                                            "rank": i,
                                            "raw_score": hotwordnum,
                                            "tag": hottag,
                                            "api_source": "tianapi",
                                            "translation": translation
                                        }
                                    })

                        return items
                elif data.get("code") != 200:
                    print(f"TianAPI error: {data.get('msg', 'Unknown error')}")

        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")

        backoff_sleep(attempt)

    return []


def main() -> None:
    items = fetch_weibo_hot()
    write_json(OUT, schema("Weibo Hot Search", items))


if __name__ == "__main__":
    main()
