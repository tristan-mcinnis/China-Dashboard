"""Baselines & deviation engine — the Neon read path.

This is the first consumer of the long-term archive: it reads the
``indicators`` table back OUT of Neon (until now the DB was write-only),
computes a 30/90-day baseline for every numeric series we track, overlays the
*fresh* latest values from the local JSON feeds (so deviations describe this
run's print, not a stale one), and writes ``docs/data/baselines.json``.

The point is significance, not salience: the digest ranks stories by what is
*hot*; this module flags what is *abnormal* against our own history — an index
breaking its 90-day range, a commodity z-spike, a policy rate or monthly print
that just changed. Output flows into the daily digest's "deviation watch".

Series are classified per the archive's behaviour:
  - ``continuous``  — intraday market series (indices, FX, commodities):
                      deviation = z-score vs the winsorized 30-day baseline,
                      plus 90-day range breaks.
  - ``step``        — monthly prints and policy rates (CPI, PMI, LPR, RRR...):
                      the *change itself* is the signal; flag a new print and
                      how long the prior value had held.

Requires DATABASE_URL (Neon). Without it the script prints a warning and
exits 0 without touching the existing baselines.json, so JSON-only local runs
stay harmless. Robustness guards (young-archive problem): winsorized stats,
minimum observed-day thresholds before any z-score is trusted.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collectors.common import schema, write_json

DATA_DIR = "docs/data"
OUT_PATH = f"{DATA_DIR}/baselines.json"

WINDOW_DAYS = 90
SHORT_WINDOW_DAYS = 30
# Below this many observed days in the short window, a z-score is noise.
MIN_DAYS_FOR_Z = 10
# Below this many observed days in the long window, a range break is noise.
MIN_DAYS_FOR_RANGE = 20
Z_FLAG_THRESHOLD = 2.0
# A series whose value changes on fewer than this share of observed days is a
# step series (monthly prints, policy rates) — z-scores are meaningless there.
STEP_CHANGE_RATIO = 0.15
# Fixed ranking severity for a step-series new print: a rate cut or a fresh
# CPI number always outranks a routine market wiggle.
STEP_SEVERITY = 3.0

# Local feeds whose latest values overlay the archive (feed name -> file).
# These are the same numeric feeds db_writer routes to the indicators table.
LOCAL_FEEDS = [
    "indices",
    "fx",
    "commodities",
    "pboc_rates",
    "nbs_monthly",
    "trade_data",
    "property",
]


def parse_numeric(value) -> float | None:
    """Numeric extraction matching db_writer's storage rule, so live values
    are comparable with what the archive holds."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        cleaned = (
            str(value)
            .replace("%", "")
            .replace("$", "")
            .replace("B", "")
            .replace(",", "")
            .strip()
        )
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def _load_live_values() -> dict[str, dict]:
    """title -> {value, raw, feed} from the fresh local JSON feeds."""
    live: dict[str, dict] = {}
    for feed in LOCAL_FEEDS:
        path = os.path.join(DATA_DIR, f"{feed}.json")
        try:
            with open(path, encoding="utf-8") as f:
                payload = json.load(f)
        except Exception:
            continue
        for item in payload.get("items", []):
            title = (item.get("title") or "").strip()
            num = parse_numeric(item.get("value"))
            if title and num is not None and title not in live:
                live[title] = {
                    "value": num,
                    "raw": item.get("value"),
                    "feed": feed,
                    "unit": (item.get("extra") or {}).get("unit", ""),
                }
    return live


def _fetch_archive_series() -> dict[str, list[tuple[str, float]]]:
    """name -> [(date, last value that day), ...] ascending, from Neon."""
    url = os.getenv("DATABASE_URL")
    if not url:
        return {}
    import psycopg2

    conn = psycopg2.connect(url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT name, captured_at::date AS day, numeric_value
                FROM (
                    SELECT name, captured_at, numeric_value,
                           ROW_NUMBER() OVER (
                               PARTITION BY name, captured_at::date
                               ORDER BY captured_at DESC
                           ) AS rn
                    FROM indicators
                    WHERE numeric_value IS NOT NULL
                      AND name <> ''
                      AND captured_at >= now() - interval '%s days'
                ) t
                WHERE rn = 1
                ORDER BY name, day
                """
                % WINDOW_DAYS
            )
            series: dict[str, list[tuple[str, float]]] = {}
            for name, day, value in cur.fetchall():
                series.setdefault(name, []).append((day.isoformat(), float(value)))
            return series
    finally:
        conn.close()


def _winsorize(values: list[float], pct: float = 0.05) -> list[float]:
    """Clip the tails so one collector hiccup can't poison the baseline."""
    if len(values) < 5:
        return list(values)
    ordered = sorted(values)
    lo = ordered[max(0, int(len(ordered) * pct))]
    hi = ordered[min(len(ordered) - 1, int(len(ordered) * (1 - pct)))]
    return [min(max(v, lo), hi) for v in values]


def _stats(values: list[float]) -> dict:
    import statistics

    w = _winsorize(values)
    mean = statistics.fmean(w)
    std = statistics.pstdev(w) if len(w) > 1 else 0.0
    return {
        "days": len(values),
        "mean": round(mean, 4),
        "std": round(std, 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
    }


def _is_step_series(values: list[float]) -> bool:
    if len(values) < 2:
        return True
    changes = sum(1 for a, b in zip(values, values[1:]) if a != b)
    return (changes / (len(values) - 1)) < STEP_CHANGE_RATIO


def _days_at_prior_value(daily: list[tuple[str, float]], prior: float) -> int | None:
    """How long the prior value held before the latest change, in calendar days."""
    held_since = None
    for day, value in reversed(daily):
        if value == prior:
            held_since = day
        elif held_since is not None:
            break
    if held_since is None:
        return None
    try:
        first = datetime.strptime(held_since, "%Y-%m-%d").date()
        last = datetime.strptime(daily[-1][0], "%Y-%m-%d").date()
        return (last - first).days
    except ValueError:
        return None


def _fmt(num: float) -> str:
    return f"{num:,.2f}".rstrip("0").rstrip(".")


def build_series(
    archive: dict[str, list[tuple[str, float]]], live: dict[str, dict]
) -> tuple[list[dict], list[dict]]:
    """Returns (items, deviations) — items in the standard feed shape."""
    items: list[dict] = []
    deviations: list[dict] = []

    for name, daily in sorted(archive.items()):
        values = [v for _, v in daily]
        live_entry = live.get(name)
        latest = live_entry["value"] if live_entry else values[-1]
        latest_source = "live" if live_entry else "archive"

        # Baseline windows exclude the live print so it can deviate from them.
        short = values[-SHORT_WINDOW_DAYS:]
        stats30 = _stats(short)
        stats90 = _stats(values)
        kind = "step" if _is_step_series(values) else "continuous"

        flags: list[str] = []
        notes: list[str] = []
        z30 = None
        severity = 0.0

        if kind == "continuous":
            if stats30["days"] >= MIN_DAYS_FOR_Z and stats30["std"] > 1e-9:
                z30 = round((latest - stats30["mean"]) / stats30["std"], 2)
                if abs(z30) >= Z_FLAG_THRESHOLD:
                    flags.append("z_spike")
                    direction = "above" if z30 > 0 else "below"
                    notes.append(
                        f"{name} at {_fmt(latest)} is {abs(z30):.1f}σ {direction} "
                        f"its 30-day mean ({_fmt(stats30['mean'])})"
                    )
                    severity = max(severity, abs(z30))
            if stats90["days"] >= MIN_DAYS_FOR_RANGE:
                if latest > stats90["max"]:
                    flags.append("range_high")
                    notes.append(
                        f"{name} at {_fmt(latest)} is a {stats90['days']}-day high "
                        f"(prior max {_fmt(stats90['max'])})"
                    )
                    severity = max(severity, Z_FLAG_THRESHOLD, abs(z30 or 0))
                elif latest < stats90["min"]:
                    flags.append("range_low")
                    notes.append(
                        f"{name} at {_fmt(latest)} is a {stats90['days']}-day low "
                        f"(prior min {_fmt(stats90['min'])})"
                    )
                    severity = max(severity, Z_FLAG_THRESHOLD, abs(z30 or 0))
        else:  # step series: a new print IS the signal
            prior = None
            for v in reversed(values):
                if v != latest:
                    prior = v
                    break
            if prior is not None and latest != values[-1]:
                # Live value differs from the last archived value: fresh print.
                flags.append("new_print")
                held = _days_at_prior_value(daily, prior)
                held_txt = f" after holding {held}d" if held and held > 1 else ""
                notes.append(
                    f"{name} moved {_fmt(values[-1])} → {_fmt(latest)}{held_txt}"
                )
                severity = STEP_SEVERITY
            elif prior is not None and len(daily) >= 2 and daily[-1][1] != daily[-2][1]:
                # Changed on the most recent archived day (caught last run).
                flags.append("new_print")
                held = _days_at_prior_value(daily[:-1], prior)
                held_txt = f" after holding {held}d" if held and held > 1 else ""
                notes.append(
                    f"{name} moved {_fmt(prior)} → {_fmt(latest)}{held_txt}"
                )
                severity = STEP_SEVERITY

        if stats90["days"] < MIN_DAYS_FOR_Z:
            flags.append("baseline_building")

        item = {
            "title": name,
            "value": latest,
            "url": "",
            "extra": {
                "feed": (live_entry or {}).get("feed", ""),
                "unit": (live_entry or {}).get("unit", ""),
                "kind": kind,
                "latest_source": latest_source,
                "baseline_30d": stats30,
                "baseline_90d": stats90,
                "z30": z30,
                "flags": flags,
                "note": "; ".join(notes),
            },
        }
        items.append(item)

        if notes:
            deviations.append(
                {
                    "title": name,
                    "feed": (live_entry or {}).get("feed", ""),
                    "kind": kind,
                    "flags": [f for f in flags if f != "baseline_building"],
                    "z30": z30,
                    "severity": round(severity, 2),
                    "note": "; ".join(notes),
                }
            )

    deviations.sort(key=lambda d: d["severity"], reverse=True)
    return items, deviations


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        print(
            "[baselines] DATABASE_URL is not set — skipping (existing "
            "baselines.json left untouched).",
            file=sys.stderr,
        )
        return

    archive = _fetch_archive_series()
    if not archive:
        print("[baselines] No archive series returned from Neon — skipping write.")
        return

    live = _load_live_values()
    items, deviations = build_series(archive, live)

    payload = schema("Neon archive baselines (30/90-day)", items)
    payload["window_days"] = WINDOW_DAYS
    payload["short_window_days"] = SHORT_WINDOW_DAYS
    payload["deviations"] = deviations
    payload["notes"] = (
        "Per-indicator baselines computed from this project's own Neon archive. "
        "deviations[] ranks what is statistically abnormal right now: z_spike = "
        f"|z| >= {Z_FLAG_THRESHOLD} vs winsorized 30-day mean; range_high/low = "
        "outside the 90-day range; new_print = a step series (policy rate, "
        "monthly print) just changed. Series flagged baseline_building have "
        "too little history for reliable z-scores."
    )

    if write_json(OUT_PATH, payload, indent=2, min_items=1):
        flagged = ", ".join(d["title"] for d in deviations) or "none"
        print(
            f"Baselines written: {len(items)} series, "
            f"{len(deviations)} deviations ({flagged}) → {OUT_PATH}"
        )


if __name__ == "__main__":
    main()
