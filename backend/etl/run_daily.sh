#!/usr/bin/env bash
# Daily collection: KenPom snapshot, then odds/scores. Run from cron (see COLLECTION.md).
# Takes a lock so runs can never overlap; a failure in one step does not skip the other,
# but the exit code is non-zero if either failed.

cd "$(dirname "$0")" || exit 1
PY="../venv/bin/python"

exec 9>/tmp/weightroom_etl.lock
if ! flock -n 9; then
    echo "$(date -u +%FT%TZ) another ETL run holds the lock; exiting" >&2
    exit 1
fi

rc=0
"$PY" 10_kenpom_snapshot.py || rc=1
"$PY" 20_odds_snapshot.py   || rc=1
exit $rc
