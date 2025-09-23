"""Collector for Tencent WeChat hot topics using TianAPI."""

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

OUT = "docs/data/tencent_wechat_hot.json"


def fetch_wechat_hot(max_items: int = 10):
    api_key = os.getenv("TIANAPI_API_KEY")
    if not api_key:
        print("Warning: TIANAPI_API_KEY not found in environment variables")
        return []

    url = "https://apis.tianapi.com/wxhottopic/index"
    params = {"key": api_key}

    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, headers=base_headers(), timeout=15)
            if resp.status_code == 200:
                data = resp.json()

                if data.get("code") == 200 and isinstance(data.get("result"), dict):
                    raw_list = data["result"].get("list", [])
                    if not isinstance(raw_list, list):
                        return []

                    items = []
                    for i, item in enumerate(raw_list[:max_items], 1):
                        if not isinstance(item, dict):
                            continue

                        topic = (item.get("word") or item.get("title") or "").strip()
                        heat_index = item.get("index") or item.get("hot") or item.get("heat") or item.get("hotvalue")

                        if not topic:
                            continue

                        score_display = ""
                        if isinstance(heat_index, (int, float)):
                            score_display = f"指数 {heat_index}"
                        elif isinstance(heat_index, str) and heat_index.strip():
                            score_display = f"指数 {heat_index.strip()}"

                        search_url = f"https://weixin.sogou.com/weixin?type=2&query={topic}"
                        translation = translate_text(topic)

                        items.append({
                            "title": f"{i}. {topic}",
                            "value": score_display,
                            "url": search_url,
                            "extra": {
                                "rank": i,
                                "raw_score": heat_index,
                                "api_source": "tianapi",
                                "translation": translation,
                            },
                        })

                    return items
                elif data.get("code") != 200:
                    print(f"TianAPI error: {data.get('msg', 'Unknown error')}")
            else:
                print(f"Unexpected status {resp.status_code} from TianAPI wxhottopic endpoint")

        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")

        backoff_sleep(attempt)

    return []


def main() -> None:
    items = fetch_wechat_hot()
    write_json(OUT, schema("Tencent WeChat Hot Topics", items))


if __name__ == "__main__":
    main()
