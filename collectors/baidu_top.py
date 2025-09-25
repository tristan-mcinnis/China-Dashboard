"""Collector for Baidu realtime top searches using TianAPI."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import quote_plus

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
from dotenv import load_dotenv

from collectors.common import (
    base_headers,
    backoff_sleep,
    schema,
    translate_text,
    write_with_history,
)

# Load environment variables from .env file
load_dotenv()

OUT = "docs/data/baidu_top.json"
HISTORY_OUT = "docs/data/history/baidu_top.json"


def _build_baidu_search_url(query: str) -> str:
    """Return a desktop-friendly Baidu search URL for the query."""

    encoded_query = quote_plus(query or "")
    return f"https://www.baidu.com/s?wd={encoded_query}"


def _extract_item_list(result: object) -> list[dict]:
    """Return the list of items from the TianAPI response result payload."""

    if isinstance(result, list):
        return [item for item in result if isinstance(item, dict)]

    if isinstance(result, dict):
        for key in ("list", "newslist", "items", "data"):
            value = result.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]

    return []


def fetch_baidu_top(max_items: int = 10):
    api_key = os.getenv("TIANAPI_API_KEY")
    if not api_key:
        print("Warning: TIANAPI_API_KEY not found in environment variables")
        return []

    url = "https://apis.tianapi.com/baiduhot/index"
    params = {"key": api_key}

    for attempt in range(3):
        try:
            response = requests.get(url, params=params, headers=base_headers(), timeout=15)
            if response.status_code != 200:
                print(f"Unexpected status {response.status_code} from TianAPI baiduhot endpoint")
                backoff_sleep(attempt)
                continue

            data = response.json()
            if data.get("code") != 200:
                print(f"TianAPI error: {data.get('msg', 'Unknown error')}")
                backoff_sleep(attempt)
                continue

            result = data.get("result", {})
            raw_items = _extract_item_list(result)
            if not raw_items:
                print("TianAPI baiduhot response missing expected list of items")
                return []

            items = []
            for idx, item in enumerate(raw_items[:max_items], 1):
                topic = ""
                for key in ("word", "keyword", "title", "name", "hotword"):
                    raw_topic = item.get(key)
                    if isinstance(raw_topic, str) and raw_topic.strip():
                        topic = raw_topic.strip()
                        break

                if not topic:
                    continue

                heat_value = None
                for score_key in ("hot", "heat", "hotnum", "num", "hot_index", "index", "hotvalue"):
                    value = item.get(score_key)
                    if value is None:
                        continue
                    if isinstance(value, (int, float)):
                        heat_value = value
                        break
                    if isinstance(value, str) and value.strip():
                        heat_value = value.strip()
                        break

                if isinstance(heat_value, (int, float)):
                    heat_display = f"热度 {heat_value}"
                elif isinstance(heat_value, str) and heat_value:
                    if any(token in heat_value for token in ("热度", "指数")):
                        heat_display = heat_value
                    else:
                        heat_display = f"热度 {heat_value}"
                else:
                    heat_display = ""

                link = ""
                for url_key in ("url", "link", "source_url", "newsurl"):
                    raw_url = item.get(url_key)
                    if isinstance(raw_url, str) and raw_url.strip():
                        link = raw_url.strip()
                        break

                if not link:
                    link = _build_baidu_search_url(topic)

                translation = translate_text(topic)

                items.append(
                    {
                        "title": f"{idx}. {topic}",
                        "value": heat_display,
                        "url": link,
                        "extra": {
                            "rank": idx,
                            "raw_score": heat_value,
                            "api_source": "tianapi",
                            "translation": translation,
                        },
                    }
                )

            return items

        except Exception as exc:
            print(f"Attempt {attempt + 1} failed: {exc}")

        backoff_sleep(attempt)

    return []


def main() -> None:
    items = fetch_baidu_top()
    payload = schema(source="Baidu Top Realtime", items=items)
    write_with_history(OUT, HISTORY_OUT, payload)


if __name__ == "__main__":
    main()
