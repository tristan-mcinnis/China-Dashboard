"""Generate docs/data/endpoints.json — a machine-readable manifest of every
feed this dashboard publishes, so other projects (newsletters, LLM pipelines,
agents, custom dashboards) can pull the data by raw URL without re-scraping.

Also generates docs/data/digest_archive/index.json: a newest-first index of
every archived digest snapshot, giving agents stable, citable permalinks to
past briefs (the per-date/slot files can't be listed over static hosting).

Run AFTER the collectors and the daily digest so the manifest reflects the
files that actually exist. Output does NOT follow the standard items schema.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "data")
ARCHIVE_DIR = os.path.join(DATA_DIR, "digest_archive")
HISTORY_DIR = os.path.join(DATA_DIR, "history")

# Primary base is Vercel: it serves /data/*.json with
# `Access-Control-Allow-Origin: *` and a short cache (see vercel.json), so it is
# safe to fetch from a browser. GitHub raw is a mirror for non-browser clients.
SITE_BASE = "https://china-dashboard.vercel.app"
VERCEL_BASE = f"{SITE_BASE}/data"
GH_RAW_BASE = "https://raw.githubusercontent.com/tristan-mcinnis/china-dashboard/main/docs/data"

ARCHIVE_SLOTS = ["morning", "midday", "evening"]

# name (without .json) -> (category, human description)
CATALOG = {
    "indices": ("markets", "Shanghai & Shenzhen stock market indices"),
    "fx": ("markets", "CNY currency exchange rates"),
    "commodities": ("markets", "China-demand commodity prices (iron ore, copper, crude, gold)"),
    "pboc_rates": ("macro", "PBOC policy rates (LPR, MLF, RRR)"),
    "nbs_monthly": ("macro", "NBS monthly indicators (CPI, PPI, PMI)"),
    "trade_data": ("macro", "China trade data (exports, imports, balance)"),
    "property": ("macro", "70-city home price index"),
    "weather": ("markets", "Beijing weather"),
    "baidu_top": ("social", "Baidu trending search topics (bilingual)"),
    "weibo_hot": ("social", "Weibo hot search topics (bilingual)"),
    "tencent_wechat_hot": ("social", "Tencent/WeChat hot topics (bilingual)"),
    "xinhua_news": ("news", "Xinhua News Agency headlines (bilingual)"),
    "thepaper_news": ("news", "The Paper (澎湃新闻) headlines (bilingual)"),
    "ladymax_news": ("news", "LadyMax fashion-business headlines (bilingual)"),
    "elite_press": ("news", "Institutional press: party organs, Chinese financial/tech media, English-facing Chinese state media (China Daily, CGTN, Global Times), Sixth Tone, and Western elite press on China (bilingual, pillar-tagged)"),
    "gov_registry": ("regulatory", "Primary-source registry: 14 ministry/regulator/diplomacy channels (MOFCOM, MFA, Taiwan Affairs, PBOC, MOF, CSRC, CAC, NDRC, NEA, MCA, CIPS, SAFE, State Council EN) + US Federal Register (bilingual, pillar-tagged)"),
    "baselines": ("analysis", "Per-indicator 30/90-day baselines + ranked deviation flags (z-spikes, range breaks, new policy/monthly prints), computed from this project's own Neon archive"),
}


def _read_as_of(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("as_of")
    except Exception:
        return None


def build_archive_index() -> dict:
    """Newest-first index of digest_archive/<date>/<slot>.json snapshots."""
    snapshots = []
    if os.path.isdir(ARCHIVE_DIR):
        for date in sorted(os.listdir(ARCHIVE_DIR), reverse=True):
            day_dir = os.path.join(ARCHIVE_DIR, date)
            if not os.path.isdir(day_dir):
                continue
            for slot in ARCHIVE_SLOTS:
                if os.path.exists(os.path.join(day_dir, f"{slot}.json")):
                    snapshots.append({
                        "date": date,
                        "slot": slot,
                        "url": f"{VERCEL_BASE}/digest_archive/{date}/{slot}.json",
                        "mirror_url": f"{GH_RAW_BASE}/digest_archive/{date}/{slot}.json",
                    })

    now = datetime.now(timezone(timedelta(hours=8)))
    return {
        "description": (
            "Point-in-time snapshots of the daily digest. Each URL is a stable "
            "permalink — snapshots are never rewritten after their slot passes."
        ),
        "generated_at": now.isoformat(timespec="seconds"),
        "url_template": f"{VERCEL_BASE}/digest_archive/<YYYY-MM-DD>/<slot>.json",
        "slots": ARCHIVE_SLOTS,
        "earliest_date": snapshots[-1]["date"] if snapshots else None,
        "latest_date": snapshots[0]["date"] if snapshots else None,
        "count": len(snapshots),
        "snapshots": snapshots,
    }


def build(archive_index: dict) -> dict:
    feeds = []
    for name, (category, description) in CATALOG.items():
        path = os.path.join(DATA_DIR, f"{name}.json")
        if not os.path.exists(path):
            continue
        feed = {
            "name": name,
            "category": category,
            "description": description,
            "url": f"{VERCEL_BASE}/{name}.json",
            "mirror_url": f"{GH_RAW_BASE}/{name}.json",
            "as_of": _read_as_of(path),
        }
        # Rolling intraday history (bounded window) where the collector keeps one.
        if os.path.exists(os.path.join(HISTORY_DIR, f"{name}.json")):
            feed["history_url"] = f"{VERCEL_BASE}/history/{name}.json"
        feeds.append(feed)

    now = datetime.now(timezone(timedelta(hours=8)))
    return {
        "name": "China Snapshot Dashboard — public data API",
        "description": (
            "Serverless China-signals feeds, refreshed 5x/day (Beijing time). "
            "All endpoints are static JSON with CORS enabled, free to consume."
        ),
        "generated_at": now.isoformat(timespec="seconds"),
        "license": "Data is provided as-is for informational purposes (see dashboard disclaimer).",
        "llms_txt": f"{SITE_BASE}/llms.txt",
        "schema": {
            "version": 1,
            "feeds": (
                "Standard feeds use {schema_version, as_of, source, items[]}, each item "
                "{title, value, url, extra{}}. Bilingual feeds add extra.translation (English). "
                "schema_version bumps only on breaking changes to this shape."
            ),
            "digest": "daily_digest.json is a synthesis feed (headline, narrative, market_snapshot, themes, entities, pillars[], top_stories[]) — not the items schema.",
            "history": "history feeds use {source, generated_at, entries[]}; each entry is a full {as_of, source, items[]} snapshot, newest first, bounded window.",
        },
        "special": {
            "daily_digest": f"{VERCEL_BASE}/daily_digest.json",
            "daily_digest_markdown": f"{VERCEL_BASE}/digest.md",
            "digest_archive_index": f"{VERCEL_BASE}/digest_archive/index.json",
            "digest_history": f"{VERCEL_BASE}/digest_history.json",
            "tags_index": f"{VERCEL_BASE}/tags_index.json",
            "health": f"{VERCEL_BASE}/health.json",
        },
        "archive": {
            "url_template": archive_index["url_template"],
            "slots": archive_index["slots"],
            "earliest_date": archive_index["earliest_date"],
            "latest_date": archive_index["latest_date"],
            "count": archive_index["count"],
            "index_url": f"{VERCEL_BASE}/digest_archive/index.json",
        },
        "feeds": feeds,
    }


def main() -> None:
    archive_index = build_archive_index()
    archive_out = os.path.join(ARCHIVE_DIR, "index.json")
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    with open(archive_out, "w", encoding="utf-8") as f:
        json.dump(archive_index, f, ensure_ascii=False, indent=2)
    print(f"Wrote {archive_out} with {archive_index['count']} snapshots")

    manifest = build(archive_index)
    out = os.path.join(DATA_DIR, "endpoints.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"Wrote {out} with {len(manifest['feeds'])} feeds")


if __name__ == "__main__":
    main()
