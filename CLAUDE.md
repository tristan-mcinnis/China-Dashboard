# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Serverless dashboard for real-time China signals using **Collectors → JSON → GitHub Pages** architecture. No backend servers required.

## Important Requirements

- **MUST use DeepSeek for translations** - Uses `deepseek-v4-flash` model via the OpenAI-compatible DeepSeek API
- All RSS feed headlines must be translated using DeepSeek for optimal performance

## Key Architecture

- **Data Collection**: Python collectors (`collectors/*.py`) scrape various Chinese sources and output standardized JSON
- **Data Storage**: JSON files stored in `/docs/data/` for GitHub Pages serving
- **Frontend**: Static HTML/JS dashboard in `/docs/` served via GitHub Pages
- **Automation**: GitHub Actions workflow runs collectors 5 times per day (Beijing time), then regenerates the daily digest

## Common Commands

### Local Development
```bash
# Set up Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run individual collectors (for testing)
python collectors/baidu_top.py
python collectors/weibo_hot.py
python collectors/tencent_wechat_hot.py
python collectors/xinhua_rss.py
python collectors/thepaper_rss.py
python collectors/ladymax.py
python collectors/indices_cn.py
python collectors/fx_cny.py
python collectors/weather_cn.py
python collectors/pboc_rates.py
python collectors/nbs_monthly.py

# Generate the daily digest (run AFTER collectors; reads fresh docs/data/*.json)
python collectors/daily_digest.py
```

### GitHub Pages Setup
- Enable GitHub Pages: Settings → Pages → Source = Deploy from a branch → main → /site

## Data Schema

All collectors output JSON following this uniform schema:
```json
{
  "as_of": "2025-09-23T11:15:00+08:00",
  "source": "string-or-array",
  "items": [
    {
      "title": "",
      "value": "",
      "url": "",
      "extra": {}
    }
  ]
}
```

## Collector Architecture

- **Common utilities**: `collectors/common.py` provides shared functions like `schema()`, `write_json()`, `base_headers()`, `backoff_sleep()`
- **Translation**: MUST use DeepSeek (`deepseek-v4-flash`) for fast, cost-effective translations
- **Output path**: All collectors write to `docs/data/[name].json` (not `data/[name].json`)
- **Error handling**: Collectors use retry logic with exponential backoff
- **Headers**: Mobile user agents and anti-bot measures

## Data Sources

Current collectors:
- `baidu_top.py`: Baidu/Chinese trending topics via TianAPI (requires TIANAPI_API_KEY)
- `weibo_hot.py`: Weibo trending topics via TianAPI (requires TIANAPI_API_KEY)
- `tencent_wechat_hot.py`: Tencent/WeChat hot topics via TianAPI (requires TIANAPI_API_KEY)
- `xinhua_rss.py`: Xinhua News Agency RSS feeds (no International section) with DeepSeek translations
- `thepaper_rss.py`: The Paper (澎湃新闻) RSS feed with DeepSeek translations
- `ladymax.py`: LadyMax mobile headlines with DeepSeek translations
- `indices_cn.py`: Chinese stock market indices
- `fx_cny.py`: Currency exchange rates (optional FX_API_KEY)
- `weather_cn.py`: Beijing weather data
- `pboc_rates.py`: PBOC policy rates (LPR, MLF, RRR) from EastMoney/Trading Economics
- `nbs_monthly.py`: NBS monthly indicators (CPI, PPI, PMI) from EastMoney
- `trade_data.py`: China trade data (exports, imports, balance) from EastMoney
- `property_cn.py`: 70-city home price index from EastMoney/NBS
- `gov_regulatory.py`: CSRC, CAC, SAMR regulatory announcements with DeepSeek translations
- `gov_registry.py`: Registry-driven primary-source collector. Reads `gov_registry_sources.json` (12 live-validated channels: MIIT, NDRC, NEA, PBOC, MOF, CSRC, MCA, CIPS, SAFE, CAC + State Council EN + US Federal Register JSON API), scrapes each listing page generically (or hits the API), DeepSeek-translates Chinese titles, and tags every item with its book `chapter`. Ported from the china-future-book source-registry (2026-06-06). JS-rendered / captcha / blocked channels are listed under `_needs_browser` in the seed and deliberately excluded (they need a headless browser, not `requests`). Generalizes the hand-coded `gov_regulatory.py`.
- `elite_press.py`: Sinocism-style institutional sources via Google News RSS proxy, each tagged with a thematic `pillar` — party organs/official media (People's Daily, Qiushi → `politics`), domestic financial media (Caixin, Yicai, 21CBH → `economy`), tech/industry media (36Kr, Jiemian → `tech`), and Western elite press on China (FT, WSJ, Bloomberg, Reuters, SCMP → `geopolitics`). Chinese headlines translated with DeepSeek; English passed through.
- `db_writer.py`: Utility to write collector data to Neon Postgres (requires DATABASE_URL)
- `daily_digest.py`: Cross-source synthesis run after all collectors. Ranks stories by cross-platform salience, uses DeepSeek (`deepseek-v4-flash`) to write the narrative brief + per-story "why it matters", and falls back to a deterministic digest if DeepSeek is unavailable.

## Daily Digest Outputs

`daily_digest.py` is the aggregation/utility layer on top of the collectors. It does
NOT follow the standard `items` schema. Outputs (all under `docs/data/`):
- `daily_digest.json`: rich feed — `headline`, `narrative`/`narrative_zh` (a sharper Sinocism-style "Lead-in"), `market_snapshot`, `themes`, `entities`, `pillars[]` (ordered thematic blocks present this run), and ranked `top_stories[]` (each with `weight`, `platforms`, `platform_count`, `primary_title`, `english_title`, `why_it_matters`, `pull_quote`, `pillar`/`pillar_label`, `source`, `category`, `url`). Stories are grouped into the `pillars` blocks (High Politics, Economy & Markets, Industry/Tech, U.S.–China/Geopolitics, Regulatory, What's Trending) in both the dashboard hero and `digest.md`.
- `digest.md`: human/LLM-friendly Markdown brief for downstream daily-digest pipelines.
- `digest_archive/<date>/<slot>.json`: point-in-time snapshot (`slot` = morning/midday/evening).

These are intended for OTHER repos to consume via the GitHub Pages raw URL. The digest
is rendered as the "Today's Brief" hero at the top of the dashboard. It is skipped in
the Neon DB writer loop (no `items` array).

## Neon Postgres (Long-term Storage)

- **Project**: china-dashboard (quiet-king-62917095)
- **Tables**: `snapshots`, `indicators`, `news_items`
- **Connection**: Set DATABASE_URL secret in GitHub Actions
- **Usage**: Dual-write — JSON files for GitHub Pages, Neon for historical queries
- Data writes happen after JSON collection in the workflow

## Vercel Deployment

- **URL**: https://china-dashboard.vercel.app
- **Config**: `vercel.json` — serves `docs/` as static output
- Linked to GitHub repo for auto-deployments

## GitHub Actions

- **Trigger**: 5 times per day (06:00, 10:30, 14:00, 18:30, 22:00 Beijing time)
- **Environment**: Runs on ubuntu-latest with Python 3.11
- **Secrets**: TIANAPI_API_KEY, DEEPSEEK_API_KEY (required), FX_API_KEY, DATABASE_URL (optional)
- **Timezone**: Asia/Shanghai
- **Commit**: Auto-commits data updates to `docs/data/*.json`

## Frontend

- **Entry point**: `docs/index.html`
- **Styling**: `docs/styles.css` with modern design inspired by Parallel.ai
- **JavaScript**: `docs/app.js` fetches and displays JSON data
- **Fonts**: Inter + JetBrains Mono from Google Fonts