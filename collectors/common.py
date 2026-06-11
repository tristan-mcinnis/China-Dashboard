import json
import os
import random
import sys
import time
import fcntl
import tempfile
from datetime import datetime, timedelta, timezone
from openai import OpenAI

# Warn only once per process when the DeepSeek key is missing (see translate_text).
_TRANSLATE_KEY_WARNED = False

USER_AGENTS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
]


def now_iso_tz8() -> str:
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).isoformat(timespec="seconds")


def write_json(path: str, payload: dict, *, indent: int | None = None, min_items: int = 0) -> bool:
    """Write JSON payload to file with validation.

    Returns True if data was written, False if skipped due to empty/invalid data.
    This prevents overwriting good data with empty results on API failures.
    """
    # CRITICAL: Validate payload has actual items before overwriting existing data
    if min_items > 0:
        items = payload.get("items", [])
        if not isinstance(items, list) or len(items) < min_items:
            print(f"Skipping write to {path}: insufficient items ({len(items) if isinstance(items, list) else 0} < {min_items})")
            return False

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

    return True


def base_headers() -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
    }


# Bump only on breaking changes to the feed item shape; downstream agents and
# pipelines key off this to decide whether they can still parse us.
SCHEMA_VERSION = 1


def schema(source, items):
    return {
        "schema_version": SCHEMA_VERSION,
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
    max_entries: int = 100,
    min_items: int = 1,
) -> bool:
    """Persist the latest payload and append it to a bounded history file using atomic writes.

    Returns True if data was written, False if skipped due to empty/invalid data.
    This prevents overwriting good data with empty results on API failures.
    """

    # CRITICAL: Validate payload has actual items before overwriting existing data
    items = payload.get("items", [])
    if not isinstance(items, list) or len(items) < min_items:
        print(f"Skipping write to {latest_path}: insufficient items ({len(items) if isinstance(items, list) else 0} < {min_items})")
        return False

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

    return True


def safe_get(d, key, default=""):
    try:
        return d.get(key, default)
    except Exception:
        return default


def backoff_sleep(attempt: int) -> None:
    time.sleep(min(8, 1.5 ** attempt + random.random()))


def translate_text(text: str, max_retries: int = 3) -> str:
    """Translate Chinese text to English using DeepSeek."""
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        # Warn once per process so the empty-translation cause is visible in logs.
        global _TRANSLATE_KEY_WARNED
        if not _TRANSLATE_KEY_WARNED:
            print(
                "[translate] DEEPSEEK_API_KEY is not set — translations will be "
                "empty. Set the DEEPSEEK_API_KEY secret to enable bilingual titles.",
                file=sys.stderr,
            )
            _TRANSLATE_KEY_WARNED = True
        return ""

    for attempt in range(max_retries):
        try:
            client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

            response = client.chat.completions.create(
                model="deepseek-v4-flash",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a translator. Translate the Chinese text to natural, concise English. Output ONLY the English translation on a single line — no notes, no pinyin, no quotes."
                    },
                    {
                        "role": "user",
                        "content": text
                    }
                ],
                # deepseek-v4-flash is a reasoning model: it spends completion
                # tokens on hidden reasoning BEFORE emitting `content`. A tight
                # budget (the old 100) gets fully consumed by reasoning and
                # returns empty content. Give enough headroom for a short line.
                max_tokens=600,
                temperature=0.3,
                timeout=30,
            )

            translation = response.choices[0].message.content.strip()
            # Ensure it's not too long and add ellipsis if needed, breaking at word boundaries
            if len(translation) > 60:
                # Find the last space before character 57
                truncated = translation[:57]
                last_space = truncated.rfind(' ')
                if last_space > 40:  # Only break at word if there's a reasonable break point
                    translation = translation[:last_space] + "..."
                else:
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


def translate_batch(texts: list[str], max_retries: int = 3) -> list[str]:
    """Translate a list of Chinese strings to English in ONE DeepSeek call.

    This is the cost- and latency-smart path: instead of one API request per
    headline (dozens per collector run), all headlines are translated in a
    single request and the reasoning-model overhead is amortized across them.

    Returns a list aligned 1:1 with ``texts``; any item that cannot be
    translated comes back as ``""`` so callers can safely fall back to the
    original Chinese. Empty/whitespace inputs map to ``""`` without an API call.
    """
    results = ["" for _ in texts]
    # Indices that actually need translating (non-empty), de-duplicated so we
    # never pay to translate the same headline twice in one batch.
    unique: dict[str, list[int]] = {}
    for i, t in enumerate(texts):
        s = (t or "").strip()
        if s:
            unique.setdefault(s, []).append(i)
    if not unique:
        return results

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        global _TRANSLATE_KEY_WARNED
        if not _TRANSLATE_KEY_WARNED:
            print(
                "[translate] DEEPSEEK_API_KEY is not set — translations will be "
                "empty. Set the DEEPSEEK_API_KEY secret to enable bilingual titles.",
                file=sys.stderr,
            )
            _TRANSLATE_KEY_WARNED = True
        return results

    phrases = list(unique.keys())
    numbered = "\n".join(f"{idx}. {p}" for idx, p in enumerate(phrases))
    # Headroom for hidden reasoning tokens + the JSON body, scaled to the count.
    max_tokens = min(4000, 400 + 80 * len(phrases))

    for attempt in range(max_retries):
        try:
            client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
            response = client.chat.completions.create(
                model="deepseek-v4-flash",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You translate Chinese trending-topic and news headlines "
                            "into natural, concise English. Return STRICT JSON: an "
                            "object mapping each input number (as a string key) to its "
                            "English translation. Translations only — no pinyin, no "
                            "notes, no commentary."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Translate these {len(phrases)} headlines:\n{numbered}"
                        ),
                    },
                ],
                response_format={"type": "json_object"},
                max_tokens=max_tokens,
                temperature=0.2,
                timeout=60,
            )
            parsed = json.loads(response.choices[0].message.content)
            for idx, phrase in enumerate(phrases):
                en = parsed.get(str(idx)) or parsed.get(idx) or ""
                if isinstance(en, str):
                    en = en.strip()
                    if len(en) > 80:
                        cut = en[:77]
                        sp = cut.rfind(" ")
                        en = (cut[:sp] if sp > 50 else cut) + "..."
                    for target in unique[phrase]:
                        results[target] = en
            return results
        except Exception as e:
            error_msg = str(e).replace(api_key, "***") if api_key in str(e) else str(e)
            if attempt < max_retries - 1:
                print(f"Batch translation attempt {attempt + 1} failed: {error_msg[:120]}, retrying...")
                backoff_sleep(attempt)
            else:
                print(f"Batch translation failed after {max_retries} attempts: {error_msg[:120]}")

    return results
