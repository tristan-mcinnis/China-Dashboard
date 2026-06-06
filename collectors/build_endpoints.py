"""Generate docs/data/endpoints.json — a machine-readable manifest of every
feed this dashboard publishes, so other projects (newsletters, LLM pipelines,
custom dashboards) can pull the data by raw URL without re-scraping.

Run AFTER the collectors and the daily digest so the manifest reflects the
files that actually exist. Output does NOT follow the standard items schema.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "data")

# Primary base is Vercel: it serves /data/*.json with
# `Access-Control-Allow-Origin: *` and a short cache (see vercel.json), so it is
# safe to fetch from a browser. GitHub raw is a mirror for non-browser clients.
VERCEL_BASE = "https://china-dashboard.vercel.app/data"
GH_RAW_BASE = "https://raw.githubusercontent.com/tristan-mcinnis/china-dashboard/main/docs/data"

# name (without .json) -> (category, human description)
CATALOG = {
    "indices": ("markets", "Shanghai & Shenzhen stock market indices"),
    "fx": ("markets", "CNY currency exchange rates"),
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
    "gov_regulatory": ("regulatory", "CSRC / CAC / SAMR announcements (bilingual)"),
    "gov_registry": ("regulatory", "Primary-source registry: 12 ministry/regulator/legislature channels + US Federal Register (bilingual, chapter-tagged)"),
}


def _read_as_of(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("as_of")
    except Exception:
        return None


def build() -> dict:
    feeds = []
    for name, (category, description) in CATALOG.items():
        path = os.path.join(DATA_DIR, f"{name}.json")
        if not os.path.exists(path):
            continue
        feeds.append({
            "name": name,
            "category": category,
            "description": description,
            "url": f"{VERCEL_BASE}/{name}.json",
            "mirror_url": f"{GH_RAW_BASE}/{name}.json",
            "as_of": _read_as_of(path),
        })

    now = datetime.now(timezone(timedelta(hours=8)))
    return {
        "name": "China Snapshot Dashboard — public data API",
        "description": (
            "Serverless China-signals feeds, refreshed 5x/day (Beijing time). "
            "All endpoints are static JSON with CORS enabled, free to consume."
        ),
        "generated_at": now.isoformat(timespec="seconds"),
        "license": "Data is provided as-is for informational purposes (see dashboard disclaimer).",
        "schema": {
            "feeds": "Standard feeds use {as_of, source, items[]}, each item {title, value, url, extra{}}. Bilingual feeds add extra.translation (English).",
            "digest": "daily_digest.json is a synthesis feed (headline, narrative, market_snapshot, themes, entities, top_stories[]) — not the items schema.",
        },
        "special": {
            "daily_digest": f"{VERCEL_BASE}/daily_digest.json",
            "daily_digest_markdown": f"{VERCEL_BASE}/digest.md",
            "health": f"{VERCEL_BASE}/health.json",
        },
        "feeds": feeds,
    }


def main() -> None:
    manifest = build()
    out = os.path.join(DATA_DIR, "endpoints.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"Wrote {out} with {len(manifest['feeds'])} feeds")


if __name__ == "__main__":
    main()
