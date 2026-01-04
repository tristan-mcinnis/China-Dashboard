<img width="1024" height="256" alt="Generated Image September 24, 2025 - 4_18PM" src="https://github.com/user-attachments/assets/af59cbb5-42a1-4230-bd48-30a6ccb2e370" />

[![Data Collection](https://github.com/tristan-mcinnis/China-Dashboard/actions/workflows/collect.yml/badge.svg)](https://github.com/tristan-mcinnis/China-Dashboard/actions/workflows/collect.yml)

China Snapshot is a lightweight, serverless dashboard that highlights real-time signals from across mainland China. Automated collectors gather structured JSON data and the frontend served from GitHub Pages displays the latest snapshot whenever you load the site.

## What the dashboard shows

- **Weibo Hot Search** – the most-discussed topics on China's largest microblogging platform.
- **Baidu Top Searches** – trending queries that capture what people are looking for right now.
- **WeChat Hot Topics** – widely shared stories within Tencent's messaging ecosystem.
- **Mainland Equity Indices** – key benchmarks from Shanghai and Shenzhen stock exchanges.
- **FX Rates** – currency moves for the renminbi against major trading partners.
- **Weather & Alerts** – quick read on current conditions in major cities.
- **Xinhua Headlines** – fresh policy and state-media updates that set the official narrative.

## Live dashboard

View the site on GitHub Pages: https://tristan-mcinnis.github.io/China-Dashboard/

## Setup

### API Keys Required

1. **TianAPI** (Required for Baidu, Weibo, WeChat collectors)
   - Get a free API key from: https://www.tianapi.com/
   - Add to GitHub Secrets as `TIANAPI_API_KEY`

2. **OpenAI API** (Required for translations)
   - Get your API key from: https://platform.openai.com/api-keys
   - Add to GitHub Secrets as `OPENAI_API_KEY`

3. **FX API Key** (Optional, for currency rates)
   - Add to GitHub Secrets as `FX_API_KEY`

### Local Development

1. Copy `.env.example` to `.env` and add your API keys
2. Install dependencies: `pip install -r requirements.txt`
3. Run collectors: `python collectors/[collector_name].py`

### GitHub Actions

The workflow runs automatically 5 times daily and commits data to `docs/data/` and `docs/data/history/`

### Health Monitoring

The dashboard exposes a health check endpoint at `/data/health.json` with collector status:

```json
{
  "timestamp": "2026-01-04T14:00:00Z",
  "success_count": 9,
  "total_count": 9,
  "status": "healthy",
  "failed": []
}
```

The frontend displays this status in the header as a health indicator badge.
