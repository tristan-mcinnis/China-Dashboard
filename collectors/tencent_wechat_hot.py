"""Collector for Tencent WeChat hot topics using TianAPI."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
from dotenv import load_dotenv

from collectors.common import base_headers, backoff_sleep, schema, write_json, translate_text

# Load environment variables from .env file
load_dotenv()

OUT = "docs/data/tencent_wechat_hot.json"


def _extract_item_list(payload: Any) -> list[Any]:
    """Return the first list of items found in a TianAPI response payload."""

    seen: set[int] = set()

    def _inner(value: Any) -> list[Any] | None:
        obj_id = id(value)
        if obj_id in seen:
            return None
        seen.add(obj_id)

        if isinstance(value, list):
            return value

        if isinstance(value, dict):
            preferred_keys = (
                "list",
                "newslist",
                "newsList",
                "items",
                "item",
                "data",
                "datas",
                "detail",
                "details",
            )

            for key in preferred_keys:
                if key in value:
                    found = _inner(value[key])
                    if isinstance(found, list):
                        return found

            for nested in value.values():
                found = _inner(nested)
                if isinstance(found, list):
                    return found

        return None

    found_list = _inner(payload)
    return found_list if isinstance(found_list, list) else []


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

                if data.get("code") == 200 and "result" in data:
                    raw_list = _extract_item_list(data.get("result"))
                    if not isinstance(raw_list, list) or not raw_list:
                        print("TianAPI wxhottopic response missing expected list of items")
                        return []

                    items = []
                    for i, item in enumerate(raw_list[:max_items], 1):
                        if not isinstance(item, dict):
                            continue

                        topic = ""
                        for key in ("word", "title", "name", "keyword", "topic", "hotword"):
                            raw_topic = item.get(key)
                            if isinstance(raw_topic, str) and raw_topic.strip():
                                topic = raw_topic.strip()
                                break

                        if not topic:
                            continue

                        heat_index = None
                        for score_key in (
                            "index",
                            "hot",
                            "heat",
                            "hotvalue",
                            "hot_value",
                            "hotindex",
                            "num",
                            "score",
                        ):
                            value = item.get(score_key)
                            if value is None:
                                continue
                            if isinstance(value, (int, float)):
                                heat_index = value
                                break
                            if isinstance(value, str) and value.strip():
                                heat_index = value.strip()
                                break

                        score_display = ""
                        if isinstance(heat_index, (int, float)):
                            score_display = f"指数 {heat_index}"
                        elif isinstance(heat_index, str) and heat_index:
                            if any(token in heat_index for token in ("指数", "热度")):
                                score_display = heat_index
                            else:
                                score_display = f"指数 {heat_index}"

                        url = ""
                        for url_key in ("url", "link", "source_url", "newsurl"):
                            raw_url = item.get(url_key)
                            if isinstance(raw_url, str) and raw_url.strip():
                                url = raw_url.strip()
                                break

                        if not url:
                            encoded_query = quote_plus(topic)
                            url = f"https://weixin.sogou.com/weixin?type=2&query={encoded_query}"

                        translation = translate_text(topic)

                        items.append({
                            "title": f"{i}. {topic}",
                            "value": score_display,
                            "url": url,
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
