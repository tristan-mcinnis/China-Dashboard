"""Collect current weather snapshots for key Chinese cities."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import python_weather

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collectors.common import schema, write_json


OUT = "docs/data/weather.json"


@dataclass(frozen=True)
class City:
    name: str
    code: str


CITIES: tuple[City, ...] = (
    City("Beijing", "BJ"),
    City("Shanghai", "SH"),
    City("Guangzhou", "GZ"),
    City("Chengdu", "CD"),
    City("Harbin", "HR"),
)


async def _fetch_single(client: python_weather.Client, city: City) -> dict[str, Any]:
    """Fetch the latest conditions for a single city."""

    try:
        forecast = await client.get(city.name)
    except Exception as exc:  # pragma: no cover - network failure path
        # Log the issue so the workflow surface shows which city failed.
        print(f"weather: failed to fetch {city.name}: {exc}")
        return {
            "code": city.code,
            "name": city.name,
            "temperature": None,
            "condition": "",
            "icon": "",
            "kind": "",
            "observed_at": None,
        }

    temperature = int(forecast.temperature)
    condition = forecast.description.strip()
    kind = getattr(forecast, "kind", None)
    icon = getattr(kind, "emoji", "") if kind else ""

    return {
        "code": city.code,
        "name": forecast.location or city.name,
        "temperature": temperature,
        "condition": condition,
        "icon": icon,
        "kind": kind.name if kind else "",
        "observed_at": forecast.datetime.isoformat(),
    }


async def _collect_weather() -> list[dict[str, Any]]:
    async with python_weather.Client(unit=python_weather.METRIC) as client:
        results: list[dict[str, Any]] = []
        for city in CITIES:
            results.append(await _fetch_single(client, city))
        return results


def _load_existing_items() -> list[dict[str, Any]] | None:
    try:
        with open(OUT, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None

    return payload.get("items") if isinstance(payload, dict) else None


def main() -> None:
    if os.name == "nt":  # pragma: no cover - Windows event loop quirk
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    items = asyncio.run(_collect_weather())

    has_fresh_data = any(item.get("temperature") is not None for item in items)

    if not has_fresh_data:
        existing = _load_existing_items()
        if existing:
            print("weather: using existing cached data")
            payload = schema(source="wttr.in via python-weather", items=existing)
        else:
            payload = schema(source="wttr.in via python-weather", items=items)
    else:
        payload = schema(source="wttr.in via python-weather", items=items)

    write_json(OUT, payload)


if __name__ == "__main__":
    main()
