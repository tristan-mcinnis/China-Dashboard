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
- **Today's Brief** – a DeepSeek-generated cross-source digest that ranks the day's stories by how many platforms they trend on, summarises why they matter, and attaches a market snapshot.

## Daily Digest (for downstream use)

Every collection run regenerates a single synthesized brief so other tools (daily
digests, newsletters, LLM pipelines) can consume China signals without re-scraping:

- **`docs/data/daily_digest.json`** – rich, machine-readable feed: ranked stories
  with cross-platform salience weights, bilingual titles, "why it matters" lines,
  themes, entities, and a deterministic market snapshot.
- **`docs/data/digest.md`** – a clean Markdown brief, ready to paste into another
  digest or hand to an LLM.

Both are served from GitHub Pages, so any repo can fetch them by raw URL, e.g.
`https://tristan-mcinnis.github.io/China-Dashboard/data/digest.md`.

Synthesis uses DeepSeek (`deepseek-v4-flash`). If `DEEPSEEK_API_KEY` is absent or the
call fails, the generator falls back to a deterministic salience-ranked digest so
the artifact is always present and valid. You can confirm which path ran via
`generated_by` in `daily_digest.json` (`deepseek-v4-flash` vs `heuristic`) and
`deepseek_configured` in `health.json`.

## Public data API

Every feed is plain static JSON with CORS enabled (`Access-Control-Allow-Origin: *`)
and short caching, so anyone can pull this data into their own dashboard, newsletter,
or LLM pipeline without re-scraping. The discovery manifest lists every endpoint:

- **`docs/data/endpoints.json`** – machine-readable catalogue of all feeds, their
  categories, raw URLs, freshness (`as_of`), and schema notes. Regenerated each run
  by `collectors/build_endpoints.py`.

Primary base (Vercel, browser-friendly): `https://china-dashboard.vercel.app/data/<feed>.json`.
GitHub raw mirror: `https://raw.githubusercontent.com/tristan-mcinnis/china-dashboard/main/docs/data/<feed>.json`.
Bilingual feeds carry the English title in `extra.translation`.

## Live dashboard

View the site on GitHub Pages: https://tristan-mcinnis.github.io/China-Dashboard/

## Setup

### API Keys Required

1. **TianAPI** (Required for Baidu, Weibo, WeChat collectors)
   - Get a free API key from: https://www.tianapi.com/
   - Add to GitHub Secrets as `TIANAPI_API_KEY`

2. **DeepSeek API** (Required for translations and the daily digest)
   - Get your API key from: https://platform.deepseek.com/
   - Add to GitHub Secrets as `DEEPSEEK_API_KEY`
   - Uses the `deepseek-v4-flash` model via the OpenAI-compatible DeepSeek API

3. **FX API Key** (Optional, for currency rates)
   - Add to GitHub Secrets as `FX_API_KEY`

### Visitor analytics (optional)

Privacy-friendly visitor counts use [GoatCounter](https://www.goatcounter.com/)
(no cookies, no personal data). To enable: create a free site, then replace
`MYCODE` in both `docs/index.html` (the `data-goatcounter` attribute) and the
`GOATCOUNTER_CODE` constant in `docs/app.js` with your site code. Until then it
stays inert and the on-page unique-visitor count is hidden.

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
  "success_count": 14,
  "total_count": 14,
  "status": "healthy",
  "failed": []
}
```

The frontend displays this status in the header as a health indicator badge.
