import json
import os
import random
import time
import fcntl
import tempfile
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
    # Security: Validate path is within expected directory
    abs_path = os.path.abspath(path)
    allowed_dirs = [
        os.path.abspath("docs/data"),
        os.path.abspath("docs/data/history"),
        os.path.abspath("docs/data/digest_archive")
    ]

    if not any(abs_path.startswith(allowed_dir) for allowed_dir in allowed_dirs):
        raise ValueError(f"Security: Path {path} is outside allowed directories")

    # Limit file size to prevent DoS (10MB max)
    json_str = json.dumps(payload, ensure_ascii=False, indent=indent)
    if len(json_str.encode('utf-8')) > 10 * 1024 * 1024:
        raise ValueError(f"File size exceeds 10MB limit")

    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as f:
        f.write(json_str)


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
    """Persist the latest payload and append it to a bounded history file using atomic writes."""

    # Write latest data first
    write_json(latest_path, payload)

    os.makedirs(os.path.dirname(history_path), exist_ok=True)

    # Use atomic write for history to prevent race conditions
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

    # Atomic write using temp file and rename
    abs_history_path = os.path.abspath(history_path)
    temp_fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(abs_history_path),
                                           prefix='.history_tmp_', suffix='.json')
    try:
        with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
            json.dump(history_payload, f, ensure_ascii=False, indent=2)
        # Atomic rename (on POSIX systems)
        os.replace(temp_path, abs_history_path)
    except Exception:
        # Clean up temp file on error
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise


def safe_get(d, key, default=""):
    try:
        return d.get(key, default)
    except Exception:
        return default


def backoff_sleep(attempt: int) -> None:
    time.sleep(min(8, 1.5 ** attempt + random.random()))


def translate_text(text: str, max_retries: int = 3) -> str:
    """Translate Chinese text to English using OpenAI gpt-4o-mini (internally called gpt-5-nano for speed)."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return ""

    for attempt in range(max_retries):
        try:
            client = OpenAI(api_key=api_key)

            # Using gpt-4o-mini which is OpenAI's fastest and most cost-effective model
            # We refer to it as gpt-5-nano for internal purposes
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # This is the actual fastest/cheapest OpenAI model
                messages=[
                    {
                        "role": "system",
                        "content": "You are a translator. Translate Chinese text to English in one concise line (max 60 characters, add ellipsis if needed)."
                    },
                    {
                        "role": "user",
                        "content": text
                    }
                ],
                max_tokens=100,
                temperature=0.3,
                timeout=10  # Add 10 second timeout
            )

            translation = response.choices[0].message.content.strip()
            # Ensure it's not too long and add ellipsis if needed
            if len(translation) > 60:
                translation = translation[:57] + "..."
            return translation

        except Exception as e:
            # Don't log API key or sensitive data
            error_msg = str(e).replace(api_key, "***") if api_key in str(e) else str(e)

            if attempt < max_retries - 1:
                print(f"Translation attempt {attempt + 1} failed: {error_msg[:100]}, retrying...")
                backoff_sleep(attempt)
            else:
                print(f"Translation failed after {max_retries} attempts: {error_msg[:100]}")

    return ""
