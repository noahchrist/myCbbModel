#!/usr/bin/env bash
# Frequent odds pull (spreads + totals, 2 credits). Run from cron every 15 min (see COLLECTION.md).
# Own lock, separate from run_daily.sh, so it never blocks or is blocked by the daily job;
# SQLite WAL + busy_timeout handle the concurrent writes. If a pull is still running the
# next one is skipped silently (exit 0) - a missed 15-minute slot is harmless.

cd "$(dirname "$0")" || exit 1
PY="../venv/bin/python"

exec 8>/tmp/weightroom_odds.lock
flock -n 8 || exit 0

exec "$PY" 20_odds_snapshot.py --mode odds
