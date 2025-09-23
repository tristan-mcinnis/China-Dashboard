# China Snapshot Dashboard

Serverless dashboard for real-time China signals. **Collectors → JSON → GitHub Pages.** No backend servers.

## Quick start (100% on GitHub)

1. **Create the repository** with this scaffold (import or fork).
2. **Enable GitHub Pages:** `Settings → Pages → Build and deployment → Source = Deploy from a branch`, then select `main` and `/site`.
3. **Add Actions secrets (optional but recommended):** `Settings → Secrets and variables → Actions`.
   - `WEIBO_COOKIE`
   - `FX_API_KEY`
4. **Trigger the workflow:** `Actions → collect → Run workflow` (or wait for the cron job).
5. Visit the GitHub Pages URL; the dashboard and JSON feeds are served directly from the repo.

### Optional local validation (macOS or any OS)

If you want to test collectors locally before committing, you can still clone the repo and run:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python collectors/baidu_top.py
```

All automation is GitHub-native—the local step is only for confidence checks.

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
