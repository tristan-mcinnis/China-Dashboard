"""Collect current weather snapshots for key Chinese cities."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

import requests

if __name__ == "__main__" and __package__ is None:  # pragma: no cover
    # Allow running this file directly via ``python collectors/weather_cn.py``.
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collectors.common import base_headers, schema, write_json


OUT = "docs/data/weather.json"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
REQUEST_TIMEOUT = 10
TZ_CHINA = timezone(timedelta(hours=8))


@dataclass(frozen=True)
class City:
    """Representation of a city we want weather information for."""

    name: str
    code: str
    latitude: float
    longitude: float


CITIES: tuple[City, ...] = (
    City("Beijing", "BJ", 39.9042, 116.4074),
    City("Shanghai", "SH", 31.2304, 121.4737),
    City("Guangzhou", "GZ", 23.1291, 113.2644),
    City("Chengdu", "CD", 30.5728, 104.0668),
    City("Harbin", "HR", 45.8038, 126.5349),
)


# Mapping of Open-Meteo weather codes to a human readable description and emoji.
WEATHER_CODES: dict[int, tuple[str, str, str]] = {
    0: ("Clear sky", "☀️", "clear"),
    1: ("Mostly clear", "🌤️", "mostly_clear"),
    2: ("Partly cloudy", "⛅", "partly_cloudy"),
    3: ("Overcast", "☁️", "overcast"),
    45: ("Fog", "🌫️", "fog"),
    48: ("Depositing rime fog", "🌫️", "fog_rime"),
    51: ("Light drizzle", "🌦️", "drizzle_light"),
    53: ("Moderate drizzle", "🌦️", "drizzle_moderate"),
    55: ("Dense drizzle", "🌧️", "drizzle_dense"),
    56: ("Light freezing drizzle", "🌧️", "freezing_drizzle_light"),
    57: ("Heavy freezing drizzle", "🌧️", "freezing_drizzle_heavy"),
    61: ("Light rain", "🌧️", "rain_light"),
    63: ("Moderate rain", "🌧️", "rain_moderate"),
    65: ("Heavy rain", "🌧️", "rain_heavy"),
    66: ("Light freezing rain", "🌨️", "freezing_rain_light"),
    67: ("Heavy freezing rain", "🌨️", "freezing_rain_heavy"),
    71: ("Light snow", "🌨️", "snow_light"),
    73: ("Moderate snow", "❄️", "snow_moderate"),
    75: ("Heavy snow", "❄️", "snow_heavy"),
    77: ("Snow grains", "🌨️", "snow_grains"),
    80: ("Light rain showers", "🌦️", "rain_showers_light"),
    81: ("Moderate rain showers", "🌦️", "rain_showers_moderate"),
    82: ("Violent rain showers", "⛈️", "rain_showers_heavy"),
    85: ("Light snow showers", "🌨️", "snow_showers_light"),
    86: ("Heavy snow showers", "❄️", "snow_showers_heavy"),
    95: ("Thunderstorm", "⛈️", "thunderstorm"),
    96: ("Thunderstorm with hail", "⛈️", "thunderstorm_hail_light"),
    99: ("Thunderstorm with heavy hail", "⛈️", "thunderstorm_hail_heavy"),
}

# Default snapshots used when the API is unavailable and no cached data exists.
DEFAULT_FALLBACK: dict[str, dict[str, Any]] = {
    "BJ": {"temperature": 26.0, "condition": "Clear sky", "icon": "☀️", "kind": "clear"},
    "SH": {"temperature": 27.0, "condition": "Partly cloudy", "icon": "⛅", "kind": "partly_cloudy"},
    "GZ": {"temperature": 30.0, "condition": "Humid clouds", "icon": "🌥️", "kind": "cloudy_humid"},
    "CD": {"temperature": 24.0, "condition": "Light rain", "icon": "🌦️", "kind": "rain_light"},
    "HR": {"temperature": 18.0, "condition": "Clear and cool", "icon": "🌤️", "kind": "clear_cool"},
}


def _now_iso() -> str:
    return datetime.now(TZ_CHINA).isoformat(timespec="minutes")


def _describe_weather(code: int, is_day: bool) -> tuple[str, str, str]:
    """Return a user facing description, icon and kind for a weather code."""

    description, icon, kind = WEATHER_CODES.get(code, ("Unknown", "•", "unknown"))

    if not is_day:
        if code == 0:
            description, icon = "Clear night", "🌙"
        elif code == 1:
            description, icon = "Mostly clear night", "🌙"
        elif code == 2:
            description, icon = "Partly cloudy night", "☁️"

    return description, icon, kind


def _normalize_time(raw: str | None) -> str:
    if not raw:
        return _now_iso()

    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return _now_iso()

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ_CHINA)

    return dt.isoformat(timespec="minutes")


def _fallback_item(city: City) -> dict[str, Any]:
    base = DEFAULT_FALLBACK.get(city.code, {"temperature": None, "condition": "", "icon": "•", "kind": "unknown"})
    return {
        "code": city.code,
        "name": city.name,
        "temperature": base.get("temperature"),
        "condition": base.get("condition", ""),
        "icon": base.get("icon", "•"),
        "kind": base.get("kind", "unknown"),
        "observed_at": _now_iso(),
    }


def _fetch_single(session: requests.Session, city: City) -> tuple[dict[str, Any], bool]:
    params = {
        "latitude": city.latitude,
        "longitude": city.longitude,
        "current_weather": "true",
        "timezone": "Asia/Shanghai",
    }

    try:
        response = session.get(OPEN_METEO_URL, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:  # pragma: no cover - network failure path
        print(f"weather: failed to fetch {city.name}: {exc}")
        return _fallback_item(city), False

    current = payload.get("current_weather") or {}
    temperature = current.get("temperature")

    if temperature is None:
        print(f"weather: missing temperature for {city.name}")
        return _fallback_item(city), False

    try:
        weather_code = int(current.get("weathercode", -1))
    except (TypeError, ValueError):
        weather_code = -1

    is_day = bool(current.get("is_day", 1))
    condition, icon, kind = _describe_weather(weather_code, is_day)

    item = {
        "code": city.code,
        "name": city.name,
        "temperature": float(temperature),
        "condition": condition,
        "icon": icon,
        "kind": kind,
        "observed_at": _normalize_time(current.get("time")),
    }

    return item, True


def _collect_weather() -> tuple[list[dict[str, Any]], int]:
    headers = base_headers()
    headers.update({"Accept": "application/json"})

    results: list[dict[str, Any]] = []
    fresh_count = 0

    with requests.Session() as session:
        session.headers.update(headers)

        for city in CITIES:
            item, fresh = _fetch_single(session, city)
            results.append(item)
            if fresh:
                fresh_count += 1

    return results, fresh_count


def _load_existing_items() -> list[dict[str, Any]] | None:
    try:
        with open(OUT, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

    return payload.get("items") if isinstance(payload, dict) else None


def _has_valid_temperature(items: Iterable[dict[str, Any]]) -> bool:
    return any(item.get("temperature") is not None for item in items)


def main() -> None:
    items, fresh_count = _collect_weather()

    if fresh_count == 0:
        existing = _load_existing_items()
        if existing and _has_valid_temperature(existing):
            print("weather: using existing cached data")
            payload_items: Iterable[dict[str, Any]] = existing
            source = "Open-Meteo API (cached)"
        else:
            payload_items = items
            source = "Open-Meteo API (fallback)"
    else:
        payload_items = items
        source = "Open-Meteo API"

    write_json(OUT, schema(source=source, items=list(payload_items)))


if __name__ == "__main__":
    main()

