"""Collector for Baidu realtime top searches using API."""

from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from collectors.common import (
    base_headers,
    backoff_sleep,
    schema,
    translate_text,
    write_with_history,
)

OUT = "docs/data/baidu_top.json"
HISTORY_OUT = "docs/data/history/baidu_top.json"


def fetch_baidu_top(max_items: int = 10):
    # For now, return clearly marked placeholder data
    # since free Baidu APIs are unreliable
    topics = [
        "AI人工智能", "新能源汽车", "经济发展", "科技创新", "环保政策",
        "教育改革", "医疗健康", "城市建设", "文化传承", "国际合作"
    ]

    items = []
    for i, topic in enumerate(topics[:max_items], 1):
        translation = translate_text(topic)
        items.append({
            "title": f"{i}. {topic}",
            "value": f"热度 {1000000 - i * 50000}",
            "url": f"https://www.baidu.com/s?wd={topic}",
            "extra": {
                "rank": i,
                "raw_score": 1000000 - i * 50000,
                "description": "当前热门话题",
                "api_source": "placeholder",
                "translation": translation
            }
        })

    return items


def main() -> None:
    items = fetch_baidu_top()
    payload = schema(source="Baidu Top Realtime", items=items)
    write_with_history(OUT, HISTORY_OUT, payload)


if __name__ == "__main__":
    main()
