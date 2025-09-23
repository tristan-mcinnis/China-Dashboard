# PRD: China Snapshot Dashboard

## 1. Objective

Build a live, automated dashboard that delivers a concise, real-time snapshot of China’s key signals—policy, markets, social sentiment, and risks—by pulling structured data into a single, easy-to-scan webpage.

The dashboard should run fully serverless using GitHub Actions (for data collection) and GitHub Pages (for hosting the dashboard and JSON feeds).

## 2. Users & Use Cases

**Primary User:** Market/strategy analysts who need a morning/evening pulse check on China.

**Use Cases:**
1. Daily read of what’s happening in China across policy, society, and markets.
2. Spot sudden anomalies (currency swings, censorship events, hot posts).
3. Pull structured JSON feeds for further analysis or slide decks.

## 3. Scope

### In Scope
- **Data modules** (JSON outputs, refreshed every 15–30 minutes):
  - News: Xinhua, People’s Daily, Caixin, Yicai (headlines only).
  - Social/Search: Weibo Hot Search/Posts, Baidu Top 10, WeChat Hot Topics, Zhihu hot questions.
  - Markets: SSE Composite, Shenzhen, ChiNext, STAR Market + sector gainers/losers.
  - FX & Flows: CNY/CNH vs USD/EUR/JPY, Stock Connect (north/south).
  - Commodities: coal, rare earths, pork.
  - Policy: recent State Council/NDRC/MOFCOM/MIIT releases.
  - Culture: Douyin/XHS trending tags, daily box office.
  - Risk: AQI, extreme weather alerts.
- **Dashboard Frontend:**
  - Single-page site (index.html + app.js + styles.css).
  - Loads JSON feeds from /data/.
  - Displays in 4 sections: Narrative, Markets, Social/Search, Policy & Risk.
- **Automation:**
  - GitHub Actions cron jobs run collectors.
  - Collectors write JSON to /data/.
  - Commits pushed back to repo.
  - GitHub Pages serves dashboard + JSON.

### Out of Scope (V1)
- Authentication / user management.
- Long-term time-series storage beyond what is in GitHub history.
- Advanced alerting/notifications.

## 4. Data Architecture

### JSON Schema (per module)

```json
{
  "as_of": "2025-09-23T11:15:00+08:00",
  "source": "string-or-array",
  "items": [
    {
      "title": "string",
      "value": "string-or-number",
      "url": "string",
      "extra": { "field": "value" }
    }
  ]
}
```

### Repo Structure

```
china-snapshot/
  collectors/
    weibo_hot.py
    baidu_top.py
    indices.py
    fx.py
    ...
  data/
    weibo_hot.json
    baidu_top.json
    indices.json
    fx.json
    ...
  site/
    index.html
    app.js
    styles.css
  .github/
    workflows/
      collect.yml
  README.md
  prd.md
```

## 5. Technical Design

### Collectors
- **Language:** Python 3.11.
- **Method:** requests/BeautifulSoup, or vendor APIs if available.
- **Output:** JSON to /data/.
- **Secrets:** stored in GitHub Actions (WEIBO_COOKIE, FX_API_KEY, etc.).
- **Retry logic:** exponential backoff; circuit breaker on repeated failures.
- **Execution:** each collector independent → ensures partial failure doesn’t break workflow.

### Automation (GitHub Actions)
- **Trigger:**
  - Cron every 30 min.
  - Manual workflow dispatch.
- **Steps:**
  1. Checkout repo.
  2. Setup Python.
  3. Install requirements.
  4. Run collectors.
  5. Commit updated JSONs.
  6. Push to main branch.

### Frontend
- **Static HTML/JS:** No framework dependency.
- **Data fetching:** fetch('/data/xxx.json').
- **Rendering:**
  - Cards for each module.
  - Sparklines for markets (Chart.js or uPlot).
  - Ticker for policy/risk.
  - Auto-refresh: JS reloads data every 60 sec.

## 6. UX Layout

### Header
- Date/time (CST), last refresh status.
- Quick summary metrics (SSE index, USD/CNY rate, Weibo #1 hot topic).

### Row 1 — Narrative
- 5 official/market headlines (Xinhua, People’s Daily, Caixin).
- 1-line implication tags.

### Row 2 — Markets
- Index tiles (current value, Δ%).
- Table of top 5 gainers/losers.
- FX widget (CNY vs USD, EUR, JPY).
- Commodities (3 key prices).

### Row 3 — Social & Search
- Weibo top 10 (rank + Δ trend arrow).
- Baidu top 10 searches.
- Zhihu trending Qs.

### Row 4 — Policy & Risk
- Policy ticker (latest government releases).
- AQI table (top 5 polluted cities).
- Weather alerts (typhoon, flood, heatwave).

### Footer
- “Last update” timestamp.
- Data integrity status (OK/FAIL per module).

## 7. Success Metrics
- Coverage: At least 80% of modules updated hourly.
- Latency: Dashboard reflects new data within 5 min of source update.
- Stability: 95% successful cron runs in a 30-day window.
- Usability: One-page load <2s; mobile responsive.

## 8. Risks & Mitigations
- Anti-scraping blocks → mitigate with mobile UA headers, low QPS, fallback APIs.
- Source censorship → monitor sudden topic deletions (signal itself).
- Secrets leakage → only via GitHub Actions secrets store.
- Data incompleteness → mark module “stale” if JSON older than 1h.

## 9. Roadmap

### V1 (MVP)
- Collectors: Weibo Hot, WeChat Hot, Baidu Top, SSE index, FX.
- Static dashboard with auto-refresh.
- GitHub Actions every 30 min.

### V2
- Add Zhihu, commodities, Stock Connect flows, AQI.
- Add sparklines + deltas vs yesterday.
- Mobile-optimized layout.

### V3
- Extend to Douyin/XHS trends.
- Add sentiment analysis layer (positive/negative trending topics).
- Archive JSON snapshots for time-series analysis.
