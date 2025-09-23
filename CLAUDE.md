# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Serverless dashboard for real-time China signals using **Collectors → JSON → GitHub Pages** architecture. No backend servers required.

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
python collectors/indices_cn.py
python collectors/fx_cny.py
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
- **Output path**: All collectors write to `docs/data/[name].json` (not `data/[name].json`)
- **Error handling**: Collectors use retry logic with exponential backoff
- **Headers**: Mobile user agents and anti-bot measures

## Data Sources

Current collectors:
- `baidu_top.py`: Baidu real-time hot searches
- `weibo_hot.py`: Weibo trending topics (requires WEIBO_COOKIE secret)
- `indices_cn.py`: Chinese stock market indices
- `fx_cny.py`: Currency exchange rates (requires FX_API_KEY secret)

## GitHub Actions

- **Trigger**: Every 30 minutes via cron or manual dispatch
- **Environment**: Runs on ubuntu-latest with Python 3.11
- **Secrets**: WEIBO_COOKIE, FX_API_KEY (optional but recommended)
- **Timezone**: Asia/Shanghai
- **Commit**: Auto-commits data updates to `docs/data/*.json`

## Frontend

- **Entry point**: `docs/index.html`
- **Styling**: `docs/styles.css` with modern design inspired by Parallel.ai
- **JavaScript**: `docs/app.js` fetches and displays JSON data
- **Fonts**: Inter + JetBrains Mono from Google Fonts