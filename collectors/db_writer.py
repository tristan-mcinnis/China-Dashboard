"""Write collector data to Neon Postgres for long-term storage.

Usage:
    from collectors.db_writer import write_to_db
    write_to_db(payload, category="market")

Requires DATABASE_URL environment variable (Neon connection string).
Silently skips if DATABASE_URL is not set (so JSON-only mode still works).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone


def _get_connection():
    """Get a psycopg2 connection to Neon, or None if unavailable."""
    url = os.getenv("DATABASE_URL")
    if not url:
        return None

    try:
        import psycopg2
        return psycopg2.connect(url)
    except Exception as e:
        print(f"DB connection failed: {e}")
        return None


def write_snapshot(payload: dict, category: str = "general") -> bool:
    """Write a raw snapshot to the snapshots table."""
    conn = _get_connection()
    if not conn:
        return False

    try:
        source = payload.get("source", "")
        captured_at = payload.get("as_of", datetime.now(timezone.utc).isoformat())

        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO snapshots (source, captured_at, category, raw_payload) "
                "VALUES (%s, %s, %s, %s)",
                (source, captured_at, category, json.dumps(payload, ensure_ascii=False)),
            )
        conn.commit()
        return True
    except Exception as e:
        print(f"DB snapshot write failed: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def write_indicators(payload: dict, source_name: str | None = None) -> bool:
    """Write indicator items (market data, rates, macro stats) to the indicators table."""
    conn = _get_connection()
    if not conn:
        return False

    try:
        source = source_name or payload.get("source", "")
        captured_at = payload.get("as_of", datetime.now(timezone.utc).isoformat())
        items = payload.get("items", [])

        with conn.cursor() as cur:
            for item in items:
                title = item.get("title", "")
                value = str(item.get("value", ""))
                extra = item.get("extra", {})

                # Try to extract numeric value
                numeric = None
                try:
                    cleaned = value.replace("%", "").replace("$", "").replace("B", "").replace(",", "").strip()
                    numeric = float(cleaned)
                except (ValueError, TypeError):
                    pass

                cur.execute(
                    "INSERT INTO indicators (source, captured_at, name, value, numeric_value, extra) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (source, captured_at, title, value, numeric, json.dumps(extra, ensure_ascii=False)),
                )
        conn.commit()
        return True
    except Exception as e:
        print(f"DB indicators write failed: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def write_news(payload: dict, source_name: str | None = None) -> bool:
    """Write news items to the news_items table."""
    conn = _get_connection()
    if not conn:
        return False

    try:
        source = source_name or payload.get("source", "")
        captured_at = payload.get("as_of", datetime.now(timezone.utc).isoformat())
        items = payload.get("items", [])

        with conn.cursor() as cur:
            for item in items:
                title = item.get("title", "")
                url = item.get("url", "")
                extra = item.get("extra", {})
                title_en = extra.get("translation", "")
                category = extra.get("category", extra.get("agency", ""))

                cur.execute(
                    "INSERT INTO news_items (source, captured_at, title, title_en, url, category, extra) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (source, captured_at, title, title_en, url, category,
                     json.dumps(extra, ensure_ascii=False)),
                )
        conn.commit()
        return True
    except Exception as e:
        print(f"DB news write failed: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def write_to_db(payload: dict, category: str = "general") -> bool:
    """Convenience function: write snapshot + typed data based on category."""
    success = write_snapshot(payload, category)

    if category in ("market", "fx", "rates", "macro", "trade", "property"):
        write_indicators(payload)
    elif category in ("news", "social", "regulatory"):
        write_news(payload)

    return success
