# China Snapshot Dashboard

Serverless dashboard for real-time China signals. **Collectors → JSON → GitHub Pages.** No backend servers.

## Quick start (macOS & cross-platform)

1. **Clone** the repository on macOS or your preferred OS.
2. **Create** a Python 3.11 virtual environment (e.g. `python3 -m venv .venv && source .venv/bin/activate` on macOS).
3. **Install** dependencies: `pip install -r requirements.txt`.
4. **Enable GitHub Pages:** Settings → Pages → Branch = `main`, Folder = `/site`.
5. **Set optional secrets:**
   - `WEIBO_COOKIE`
   - `FX_API_KEY`
6. **Run the workflow:** Actions → `collect` → `Run workflow` (or wait for cron).
7. Open the GitHub Pages URL to see the dashboard.

## Data files

Collectors write JSON to `/data/*.json` using a uniform schema:

```json
{ "as_of": "2025-09-23T11:15:00+08:00", "source": "string-or-array", "items": [ { "title": "", "value": "", "url": "", "extra": {} } ] }
```

Current modules:
- `baidu_top.json`
- `weibo_hot.json`
- `indices.json`
- `fx.json`

## Ops notes

- **Throttle & headers:** collectors use mobile UA + backoff.
- **Partial failures:** each collector runs independently; stale modules remain visible.
- **Anti-bot:** some sources may block scraping; prefer official/paid APIs as you scale.

## Roadmap

- Add: Xinhua/Caixin headlines, Zhihu hot, AQI, policy ticker, Stock Connect flows, commodities.
- Add: sparklines & deltas vs yesterday (store last N snapshots under `/data/history/`).

## License

MIT (adjust as needed).
