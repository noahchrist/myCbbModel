# weightroom (myCbbModel) — agent orientation

weightroom.io: users build college-basketball prediction models (weighted linear regression on KenPom stats)
and get daily picks vs. sportsbook lines. Hobby project, ~dozen users. Facts below verified 2026-11-01.
**This repo is public — never put secret values in it** (env var *names* only).

## Architecture

```
GitHub (main) --Actions deploy--> AWS Lightsail (us-east-2, Ubuntu 22.04, 1 GB RAM, no swap, UTC)
                                    ├─ nginx :443  weightroom.io / www      -> static React build in /var/www/html
                                    ├─ nginx :443  api.weightroom.io        -> proxy 127.0.0.1:8000
                                    ├─ systemd `weightroom` = uvicorn app.main:app (FastAPI, port 8000, firewalled from internet)
                                    └─ cron 12:00 UTC run_daily.sh (KenPom + scores); cron */15 run_odds.sh (odds)
Auth: Supabase (JWT verified in backend/app/auth.py). Everything else is SQLite on the server's disk.
```

- `frontend/` React 19 + Vite + TS (`npm run build` -> `dist/`). API base from `VITE_API_URL` (`frontend/.env.production`, tracked, non-secret).
- `backend/app/` FastAPI: `main.py` routes (`/games/{date}`, `/user-models`, `/create-model`, `/community-models`, `/todays-top-picks`, ...), `models.py`, `auth.py`, `games.py`. CORS allows localhost:5173 + weightroom.io.
- `backend/etl/` data pipeline (see below). `backend/etl/etlVault/` = archived previous-season scripts, not run.
- `backend/SETUP.md` is outdated (Windows paths); ignore it.

## Server access

```
ssh -i ~/Documents/keys/LightsailDefaultKey-us-east-2.pem ubuntu@3.129.160.93     # DNS A records point here; unconfirmed whether it's a Lightsail static IP (if not, a stop/start changes it and breaks the deploy secret LIGHTSAIL_HOST)
```
- User `ubuntu` has passwordless sudo. Hostname starts with `ip-` (the ETL logger uses that to detect "running on server").
- **Do not use VS Code Remote-SSH** — vscode-server exhausted RAM and hung the box (Oct 2026). Plain ssh only.
- If ssh connects but hangs at "banner exchange", the box is out of memory/CPU: reboot from the Lightsail console.
- When killing processes by name, `pkill -f <pattern>` also matches your own ssh command line — use `pgrep`/pids.
- Server Python is **3.10** (venv at `~/myCbbModel/backend/venv`); local is 3.13. Don't use 3.11+ only features. `sqlite3` CLI is installed on both. No `gh` CLI locally.

## Where things live (server)

| Path | What |
|---|---|
| `~/myCbbModel` | git checkout of `main` (deploy does `git pull`) |
| `~/env/weightroom.env` | **all secrets** (read by systemd `EnvironmentFile` and by `etl/logger.py` on the server). Inspect names only: `sed 's/=.*/=<redacted>/'` |
| `~/weightroomData/master.db` | **app database** (SQLite): users, models, predictions, `games2026`, `teamsMaster`, `setTarget2026`, `kenpom2026`, ... |
| `~/weightroomData/collect.db` | **raw collection database** written by the daily ETL (append-only) |
| `~/weightroomData/raw/{odds,scores,kenpom}/YYYY-MM/*.json.gz` | full raw API responses, the only copy in that form |
| `~/weightroomLogs/` | ETL logs (daily-rotated, gzipped, 30 days) + `cron.log` |
| `/var/www/html` | deployed frontend (deploy wipes and recopies it) |
| `/etc/nginx/sites-enabled/{frontend,weightroom}` | nginx vhosts; TLS by certbot (renewal cron file `/etc/cron.d/certbot` present, not dry-run tested; certs expire mid-Dec 2026) |
| `/etc/systemd/system/weightroom.service` | backend unit |

`.db` files are gitignored; `master.db`/`collect.db`/`raw` are **not** in git — back them up separately (user keeps `master.db` backups; make sure `collect.db` + `raw/` are included).
The local `backend/data/master.db` is a stale copy (useful for tests, not truth).

## Deploy

Push to `main` -> `.github/workflows/deploy.yml` SSHes in (secrets `SSH_KEY`, `LIGHTSAIL_USER`, `LIGHTSAIL_HOST`), runs `git pull`, `pip install -r requirements.txt`, `systemctl restart weightroom`, `npm install && npm run build`, copies `dist` to `/var/www/html`, reloads nginx (~1–2 min).
**Every push to main redeploys and briefly restarts the API.** Develop on a branch; merge/push to main when ready. Check a run without `gh`:
`curl -s "https://api.github.com/repos/noahchrist/myCbbModel/actions/runs?per_page=1"` (fields: head_sha, status, conclusion).
Deploy does not touch cron, databases, or env files.

## Data collection (backend/etl) — see `backend/etl/COLLECTION.md`

- `run_daily.sh` (cron, 12:00 UTC = 6 AM CST / 7 AM CDT; shift to 11:00 for 6 AM CDT) runs, under `flock`, `10_kenpom_snapshot.py` then `20_odds_snapshot.py --mode scores`; `run_odds.sh` (cron every 15 min, own lock) runs `--mode odds` (spreads+totals, change-only rows -> opening/closing line capture). Exit non-zero if either fails; each logs a row to `etl_runs` in `collect.db`.
- `collect.db`: `kenpom_raw` / `kenpom_norm` (PK season, snapshot_date, kpid; includes `data_through`), `games` (one row/game, score written once), `odds_snapshots` (append-only, pre-game lines only), `etl_runs`; views `games_current`, `odds_closing`.
- `SEASON` is hardcoded in `etl/common.py` (currently **2027** = the 2026-27 season; it's KenPom's `y` value). Bump once a year.
- Replay without network: `10_kenpom_snapshot.py --replay FILE`, `20_odds_snapshot.py --odds-file A --scores-file B [--now ISO]`. **Test against a scratch copy** (set `DB_PATH`, `ETL_LOG_DIR`, `COLLECT_DB_PATH` env vars) — never against live `collect.db`.
- Team-name join: The Odds API names -> `teamsMaster.theoddsTeamName` -> `kpid`. Unmatched names are stored with NULL kpid and logged as a warning ("align team names later").

API constraints learned the hard way:
- **The Odds API**: paid 20K credits/month plan (key `THEODDS_API_KEY`; the old 500-credit free key is `THEODDS_API_KEY_FREE`, use it for tests via `--key-env`). Odds pull = 2 (spreads+totals), scores = 2; `/sports` is free. Each added market/book/region multiplies cost. Only upcoming games are served — missed odds can't be backfilled.
- **KenPom**: the per-team loop (~1,460 calls) now gets HTTP 429 with `Retry-After` ≈ 7 min. Use the 4 bulk endpoints (no `team_id`), 4 s apart. Records join to teams by `TeamName` (bulk records lack `TeamID`).
- KenPom preseason data: only `ratings` is real; other stats are placeholders (0/100/200) until `DataThrough` moves off "Beginning of season". Don't train on those snapshots.

## Not yet migrated / known loose ends

- App + legacy ETL scripts (`3_createBaselineTargets.py`, `4_runModels.py`, `5_analyzePerformance.py`, `runPredictionsLinear.py`, `populate_top_picks.py`, `etl/2_loadTheodds2026.py`) still use season-2026 tables in `master.db` (`games2026`, `kenpom2026`, `setTarget2026`) and the March-Madness (`*MM`) tables. They are not scheduled. Moving them to read `collect.db` (view `games_current`, point-in-time `kenpom_norm`) is the next phase.
- Supabase: used only for auth; Postgres is unused (an old design). Don't remove the env vars.
- No swap on the server (deliberately skipped). Revisit if model scripts (pandas/sklearn) run on the box alongside the ETL.
- Old AWS (CloudWatch/EventBridge) scheduling was dropped in favor of cron.

## Working conventions

- Server writes needing sudo/cron/fstab may be blocked by the agent permission classifier; the user runs those themselves.
- Never print `.env`/`weightroom.env` values or API keys in output or commits. Local keys live in the gitignored repo-root `.env`.
- Verify before claiming: check `etl_runs`, `~/weightroomLogs/cron.log`, `systemctl is-active weightroom nginx cron`, and `free -m` (≈400 MB available is normal).
