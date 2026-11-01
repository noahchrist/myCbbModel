# Daily data collection

Writes to `collect.db` (next to `master.db`; override with `COLLECT_DB_PATH`).
Raw API responses are archived as gzipped JSON under `raw/` (override with `RAW_PAYLOAD_DIR`).
Everything is stored in UTC. `SEASON` is hardcoded in `common.py` (KenPom `y` value) — bump once a year.

| table | key | notes |
|---|---|---|
| `kenpom_raw` | season, snapshot_date, kpid | raw stats; same-day re-run replaces that day |
| `kenpom_norm` | season, snapshot_date, kpid | z-scores of the above (old ETL's method) |
| `games` | game_id | identity from odds feed; final score written once |
| `odds_snapshots` | game_id, pulled_at | append-only, change-only (a row only when a game's lines changed); pre-game lines only. First row ≈ opening line seen, last row before tip ≈ closing line; `*_last_update` is the book's own quote time |
| `etl_runs` | run_id | one row per script run (status, rows, credits left, error) |

Views: `games_current` (latest odds, old `games2026` column names), `odds_closing` (last pre-tip snapshot; accuracy = pull frequency, ~15 min).

## Scripts
- `10_kenpom_snapshot.py` — 5 KenPom calls (teams + 4 bulk endpoints, 4s apart); a per-team loop trips
  KenPom's rate limit (HTTP 429). Honors `Retry-After` up to 120s, otherwise fails. Writes nothing unless
  >=95% of teams return data. `data_through` records KenPom's "DataThrough" (preseason: "Beginning of season").
- `20_odds_snapshot.py --mode odds` — spreads+totals (h2h dropped), 2 credits per pull, every 15 min via `run_odds.sh` (own lock; skips if a pull is still running). `--mode scores` — last 3 days of scores, 2 credits, once daily. `--key-env THEODDS_API_KEY_FREE` runs against the free key for tests. The odds job pauses itself when the previous run reported <100 credits left, so scores keep working.
- `run_daily.sh` — KenPom then scores under `flock`; non-zero exit if either failed.
- `run_odds.sh` — the 15-minute odds job.
- Credit budget (20K/month plan): odds 96 pulls/day x 2 = ~5,800/month + scores ~60/month.

Both scripts exit non-zero on failure. Re-ingest a saved payload without network:
`10_kenpom_snapshot.py --replay FILE`, `20_odds_snapshot.py --odds-file A --scores-file B [--now ISO]`.

## Cron (server is UTC)
```
# 12:00 UTC = 6:00 AM CST (7:00 AM CDT after Mar 8 2027; use 11:00 for 6 AM CDT)
0 12 * * * /home/ubuntu/myCbbModel/backend/etl/run_daily.sh >> /home/ubuntu/weightroomLogs/cron.log 2>&1
*/15 * * * * /home/ubuntu/myCbbModel/backend/etl/run_odds.sh >> /home/ubuntu/weightroomLogs/cron.log 2>&1
```
