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


def write_json(path: str, payload: dict, *, indent: int | None = None) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=indent)


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


def _load_history_entries(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:  # pragma: no cover - defensive logging only
        print(f"History read error for {path}: {exc}")
        return []

    entries = data.get("entries", []) if isinstance(data, dict) else []
    cleaned: list[dict] = []

    if not isinstance(entries, list):
        return cleaned

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        cleaned.append(
            {
                "as_of": entry.get("as_of"),
                "source": entry.get("source"),
                "items": entry.get("items", []),
            }
        )

    return cleaned


def write_with_history(
    latest_path: str,
    history_path: str,
    payload: dict,
    *,
    max_entries: int = 30,
) -> None:
    """Persist the latest payload and append it to a bounded history file."""

    write_json(latest_path, payload)

    os.makedirs(os.path.dirname(history_path), exist_ok=True)

    entries = _load_history_entries(history_path)

    snapshot = {
        "as_of": payload.get("as_of"),
        "source": payload.get("source"),
        "items": payload.get("items", []),
    }

    if snapshot.get("as_of"):
        entries = [entry for entry in entries if entry.get("as_of") != snapshot["as_of"]]

    entries.insert(0, snapshot)

    entries.sort(key=lambda entry: entry.get("as_of") or "", reverse=True)
    if max_entries > 0:
        entries = entries[:max_entries]

    history_payload = {
        "source": payload.get("source"),
        "generated_at": now_iso_tz8(),
        "entries": entries,
    }

    write_json(history_path, history_payload, indent=2)


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
                            "text": f"Translate this Chinese text to English in one concise line (max 60 characters, add ellipsis if needed): {text}"
                        }
                    ]
                }
            ],
            text={
                "format": {
                    "type": "text"
                },
                "verbosity": "low"
            },
            reasoning={
                "effort": "low",
                "summary": "auto"
            },
            tools=[],
            store=False,
            include=[
                "reasoning.encrypted_content",
                "web_search_call.action.sources"
            ]
        )

        translation = response.output_text.strip()
        # Ensure it's not too long and add ellipsis if needed
        if len(translation) > 60:
            translation = translation[:57] + "..."
        return translation

    except Exception as e:
        print(f"Translation error: {e}")
        return ""
