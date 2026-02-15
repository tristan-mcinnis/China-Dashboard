# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Serverless dashboard for real-time China signals using **Collectors → JSON → GitHub Pages** architecture. No backend servers required.

## Important Requirements

- **MUST use gpt-5-nano for translations** - This is our internal name for gpt-4o-mini, OpenAI's fastest and most cost-effective model
- All RSS feed headlines must be translated using this model for optimal performance

## Key Architecture

- **Data Collection**: Python collectors (`collectors/*.py`) scrape various Chinese sources and output standardized JSON
- **Data Storage**: JSON files stored in `/docs/data/` for GitHub Pages serving
- **Frontend**: Static HTML/JS dashboard in `/docs/` served via GitHub Pages
- **Automation**: GitHub Actions workflow runs collectors every 30 minutes

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
- **Translation**: MUST use gpt-5-nano (implemented as gpt-4o-mini) for fast, cost-effective translations
- **Output path**: All collectors write to `docs/data/[name].json` (not `data/[name].json`)
- **Error handling**: Collectors use retry logic with exponential backoff
- **Headers**: Mobile user agents and anti-bot measures

## Data Sources

Current collectors:
- `baidu_top.py`: Baidu/Chinese trending topics via TianAPI (requires TIANAPI_API_KEY)
- `weibo_hot.py`: Weibo trending topics via TianAPI (requires TIANAPI_API_KEY)
- `tencent_wechat_hot.py`: Tencent/WeChat hot topics via TianAPI (requires TIANAPI_API_KEY)
- `xinhua_rss.py`: Xinhua News Agency RSS feeds (no International section) with gpt-5-nano translations
- `thepaper_rss.py`: The Paper (澎湃新闻) RSS feed with gpt-5-nano translations
- `ladymax.py`: LadyMax mobile headlines with gpt-5-nano translations
- `indices_cn.py`: Chinese stock market indices
- `fx_cny.py`: Currency exchange rates (optional FX_API_KEY)
- `weather_cn.py`: Beijing weather data
- `pboc_rates.py`: PBOC policy rates (LPR, MLF, RRR) from EastMoney/Trading Economics
- `nbs_monthly.py`: NBS monthly indicators (CPI, PPI, PMI) from EastMoney
- `trade_data.py`: China trade data (exports, imports, balance) from EastMoney
- `property_cn.py`: 70-city home price index from EastMoney/NBS
- `gov_regulatory.py`: CSRC, CAC, SAMR regulatory announcements with gpt-5-nano translations
- `db_writer.py`: Utility to write collector data to Neon Postgres (requires DATABASE_URL)

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
- **Secrets**: TIANAPI_API_KEY, OPENAI_API_KEY (required), FX_API_KEY, DATABASE_URL (optional)
- **Timezone**: Asia/Shanghai
- **Commit**: Auto-commits data updates to `docs/data/*.json`

## Frontend

- **Entry point**: `docs/index.html`
- **Styling**: `docs/styles.css` with modern design inspired by Parallel.ai
- **JavaScript**: `docs/app.js` fetches and displays JSON data
- **Fonts**: Inter + JetBrains Mono from Google Fonts