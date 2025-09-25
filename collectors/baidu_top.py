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


def _extract_item_list(payload: object) -> list[dict]:
    """Return the first list of dictionaries discovered inside ``payload``.

    TianAPI occasionally surfaces the hot list under different keys (``list``,
    ``newslist`` or ``items``) and sometimes omits the ``result`` wrapper.  The
    recursion below mirrors the WeChat collector so we can parse whichever shape
    the API returns without relying on a single key path.
    """

    seen: set[int] = set()

    def _inner(value: object) -> list[dict] | None:
        obj_id = id(value)
        if obj_id in seen:
            return None
        seen.add(obj_id)

        if isinstance(value, list):
            dict_items = [item for item in value if isinstance(item, dict)]
            if dict_items:
                return dict_items
            return None

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
                    if found:
                        return found

            for nested in value.values():
                found = _inner(nested)
                if found:
                    return found

        return None

    found_list = _inner(payload)
    return found_list if isinstance(found_list, list) else []


def fetch_baidu_top(max_items: int = 10):
    api_key = os.getenv("TIANAPI_API_KEY")
    if not api_key:
        print("Warning: TIANAPI_API_KEY not found in environment variables")
        return []

    url = "https://apis.tianapi.com/baiduhot/index"
    headers = base_headers()
    headers.setdefault("Accept", "application/json")

    # TianAPI recently switched a number of endpoints to POST-only.  We
    # optimistically try a POST first and gracefully fall back to GET so the
    # collector keeps working even if the API flips between the two modes.
    request_strategies = (
        ("post", {"data": {"key": api_key, "num": max(1, min(max_items, 50))}}),
        ("get", {"params": {"key": api_key, "num": max(1, min(max_items, 50))}}),
    )

    for attempt in range(3):
        for method, kwargs in request_strategies:
            try:
                response = requests.request(
                    method,
                    url,
                    headers=headers,
                    timeout=15,
                    **kwargs,
                )
            except Exception as exc:  # pragma: no cover - defensive logging
                print(f"Attempt {attempt + 1} {method.upper()} failed: {exc}")
                continue

            if response.status_code != 200:
                print(
                    "Unexpected status "
                    f"{response.status_code} from TianAPI baiduhot endpoint"
                )
                continue

            try:
                data = response.json()
            except Exception as exc:  # pragma: no cover - defensive logging
                print(f"Unable to decode TianAPI response as JSON: {exc}")
                continue

            if data.get("code") != 200:
                print(f"TianAPI error: {data.get('msg', 'Unknown error')}")
                continue

            result_payload = data.get("result")
            raw_items = _extract_item_list(result_payload if result_payload else data)
            if not raw_items:
                print("TianAPI baiduhot response missing expected list of items")
                return []

            items = []
            for idx, item in enumerate(raw_items[:max_items], 1):
                topic = ""
                for key in (
                    "word",
                    "keyword",
                    "title",
                    "name",
                    "hotword",
                    "hotWord",
                    "query",
                    "showword",
                ):
                    raw_topic = item.get(key)
                    if isinstance(raw_topic, str) and raw_topic.strip():
                        topic = raw_topic.strip()
                        break

                if not topic:
                    continue

                heat_value = None
                for score_key in (
                    "hot",
                    "heat",
                    "hotnum",
                    "num",
                    "hot_index",
                    "index",
                    "hotvalue",
                    "hot_value",
                    "hotValue",
                    "hotScore",
                ):
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
                for url_key in (
                    "url",
                    "link",
                    "source_url",
                    "newsurl",
                    "m_url",
                ):
                    raw_url = item.get(url_key)
                    if isinstance(raw_url, str) and raw_url.strip():
                        link = raw_url.strip()
                        break

                if not link:
                    link = _build_baidu_search_url(topic)

                description = ""
                for desc_key in (
                    "desc",
                    "description",
                    "digest",
                    "brief",
                    "summary",
                    "intro",
                    "content",
                ):
                    raw_desc = item.get(desc_key)
                    if isinstance(raw_desc, str) and raw_desc.strip():
                        description = raw_desc.strip()
                        break

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
                            "description": description,
                            "translation": translation,
                        },
                    }
                )

            return items

        backoff_sleep(attempt)

    return []


def main() -> None:
    items = fetch_baidu_top()
    payload = schema(source="Baidu Top Realtime", items=items)
    write_with_history(OUT, HISTORY_OUT, payload)


if __name__ == "__main__":
    main()
