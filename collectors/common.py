import json
import os
import random
import time
from datetime import datetime, timedelta, timezone
from openai import OpenAI

USER_AGENTS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
]


def now_iso_tz8() -> str:
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).isoformat(timespec="seconds")


def write_json(path: str, payload: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)


def base_headers() -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
    }


def schema(source, items):
    return {
        "as_of": now_iso_tz8(),
        "source": source,
        "items": items,
    }


def safe_get(d, key, default=""):
    try:
        return d.get(key, default)
    except Exception:
        return default


def backoff_sleep(attempt: int) -> None:
    time.sleep(min(8, 1.5 ** attempt + random.random()))


def translate_text(text: str) -> str:
    """Translate Chinese text to English using OpenAI GPT-5-nano API."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return ""

    try:
        client = OpenAI(api_key=api_key)

        response = client.responses.create(
            model="gpt-5-nano",
            input=[
                {
                    "role": "developer",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "You are a Chinese to English translator. Translate Chinese text to English concisely in one line (max 60 characters). Add ellipsis if needed."
                        }
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": f"Translate this Chinese text to English: {text}"
                        }
                    ]
                }
            ],
            text={
                "format": {
                    "type": "text"
                },
                "verbosity": "medium"
            },
            reasoning={
                "effort": "medium"
            },
            tools=[],
            store=False
        )

        translation = response.text.content.strip()
        # Ensure it's not too long and add ellipsis if needed
        if len(translation) > 60:
            translation = translation[:57] + "..."
        return translation

    except Exception as e:
        print(f"Translation error: {e}")
        return ""
