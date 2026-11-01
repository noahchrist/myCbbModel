"""Daily KenPom snapshot -> collect.db (kenpom_raw + kenpom_norm).

Append-only by (season, snapshot_date): a same-day re-run replaces that day's rows
in one transaction. Nothing is written unless enough teams came back.
Uses KenPom's bulk endpoints: 5 calls total (teams + ratings, four-factors, height, misc-stats).

Usage:
    python 10_kenpom_snapshot.py                      # live pull
    python 10_kenpom_snapshot.py --replay FILE.json.gz  # re-ingest a saved payload, no network
"""
import argparse
import os
import statistics
import sys
import time

import requests

from logger import get_logger
from common import (
    SEASON, KENPOM_STATS, RunLog, connect_collect, fmt_ts, load_payload,
    save_payload, utc_now,
)

logger = get_logger("10_kenpom_snapshot")

BASE_URL = "https://kenpom.com"
DELAY_BETWEEN_CALLS = 4
MAX_RETRY_AFTER = 120  # seconds; a longer 429 lockout fails the run instead of sleeping on it
MIN_SUCCESS_RATIO = 0.95

# Multiplied by -1 before z-scoring so higher is always better.
INVERT_FIELDS = {
    "adjDefEff", "defEffFgPct", "trnvrPct", "defFtRate",
    "defRebPct", "oppThreesPct", "oppThreesRate",
}

BULK_ENDPOINTS = ("ratings", "four-factors", "height", "misc-stats")


def kenpom_get(session, endpoint, params):
    """GET one KenPom endpoint. Honors Retry-After on 429; raises if it can't get a 200."""
    params = dict(params, endpoint=endpoint)
    last = None
    for attempt in range(1, 4):
        try:
            r = session.get(f"{BASE_URL}/api.php", params=params, timeout=60)
            if r.status_code == 200:
                return r.json()
            last = f"HTTP {r.status_code}"
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", 60))
                if wait > MAX_RETRY_AFTER:
                    raise RuntimeError(f"{endpoint}: rate limited, Retry-After={wait}s")
                logger.warning(f"{endpoint}: rate limited, sleeping {wait}s (attempt {attempt})")
                time.sleep(wait + 1)
                continue
        except (requests.RequestException, ValueError) as e:
            last = str(e)
        logger.warning(f"{endpoint} {params} failed: {last} (attempt {attempt})")
        time.sleep(5 * attempt)
    raise RuntimeError(f"{endpoint} failed after 3 attempts: {last}")


def pull_live():
    api_key = os.environ.get("KENPOM_API_KEY")
    if not api_key:
        raise ValueError("Missing KENPOM_API_KEY in environment variables or .env file")

    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "weightroom-kenpom-snapshot/2.0",
    })

    payload = {"season": SEASON}
    teams = kenpom_get(session, "teams", {"y": SEASON})
    payload["teams"] = teams if isinstance(teams, list) else teams.get("teams", [])
    logger.info(f"Found {len(payload['teams'])} teams for {SEASON}")

    for endpoint in BULK_ENDPOINTS:
        time.sleep(DELAY_BETWEEN_CALLS)
        payload[endpoint] = kenpom_get(session, endpoint, {"y": SEASON})
        logger.info(f"{endpoint}: {len(payload[endpoint])} records")
    return payload


def build_rows(payload):
    """Join the four bulk endpoints to teams (by TeamName); one dict per team.
    Teams missing from `ratings` are skipped."""
    by_name = {
        ep: {r["TeamName"]: r for r in payload.get(ep, [])} for ep in BULK_ENDPOINTS
    }
    rows, skipped = [], []
    for team in payload["teams"]:
        name = team.get("TeamName")
        ratings = by_name["ratings"].get(name)
        if not ratings:
            skipped.append(name)
            continue
        ff = by_name["four-factors"].get(name, {})
        ht = by_name["height"].get(name, {})
        misc = by_name["misc-stats"].get(name, {})

        rows.append({
            "kpid": team.get("TeamID"),
            "team": name,
            "data_through": ratings.get("DataThrough"),
            "adjOffEff": ratings.get("AdjOE"),
            "adjDefEff": ratings.get("AdjDE"),
            "adjTempo": ratings.get("AdjTempo"),
            "effFgPct": ff.get("eFG_Pct"),
            "defEffFgPct": ff.get("DeFG_Pct"),
            "trnvrPct": ff.get("TO_Pct"),
            "ftRate": ff.get("FT_Rate"),
            "defFtRate": ff.get("DFT_Rate"),
            "offRebPct": ff.get("OR_Pct"),
            "defRebPct": ff.get("DOR_Pct"),
            "effHeight": ht.get("HgtEff"),
            "expRtg": ht.get("Exp"),
            "benchRtg": ht.get("Bench"),
            "contRtg": ht.get("Continuity"),
            "threesPct": misc.get("FG3Pct"),
            "ftPct": misc.get("FTPct"),
            "blockPct": misc.get("BlockPct"),
            "stlRate": misc.get("StlRate"),
            "nonStlTrnvrRate": misc.get("OppNSTRate"),
            "astRate": misc.get("ARate"),
            "threesRate": misc.get("F3GRate"),
            "oppThreesPct": misc.get("OppFG3Pct"),
            "oppThreesRate": misc.get("OppF3GRate"),
        })
    return rows, skipped


def normalize(rows):
    """Z-score every stat across all teams in the snapshot (same method as the old ETL)."""
    params = {}
    for field in KENPOM_STATS:
        sign = -1 if field in INVERT_FIELDS else 1
        values = [sign * r[field] for r in rows if r[field] is not None]
        if len(values) > 1:
            std = statistics.stdev(values)
            params[field] = (sign, statistics.fmean(values), std if std > 0 else 1.0)
            if std == 0:
                logger.warning(f"Zero std dev for {field}, using std=1.0")

    out = []
    for r in rows:
        n = {"kpid": r["kpid"], "team": r["team"], "data_through": r["data_through"]}
        for field in KENPOM_STATS:
            if field in params and r[field] is not None:
                sign, mean, std = params[field]
                n[field] = (sign * r[field] - mean) / std
            else:
                n[field] = None
        out.append(n)
    return out


def write_snapshot(conn, table, season, snapshot_date, loaded_at, rows):
    cols = ["season", "snapshot_date", "kpid", "loaded_at", "team", "data_through"] + KENPOM_STATS
    sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})"
    conn.executemany(sql, [
        (season, snapshot_date, r["kpid"], loaded_at, r["team"], r["data_through"], *[r[s] for s in KENPOM_STATS])
        for r in rows
    ])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay", help="ingest a saved payload instead of calling KenPom")
    args = parser.parse_args()

    logger.info(f"Starting KenPom snapshot for season {SEASON}")
    conn = connect_collect()
    now = utc_now()

    with RunLog(conn, "10_kenpom_snapshot", logger) as run:
        if args.replay:
            payload = load_payload(args.replay)
            logger.info(f"Replaying payload {args.replay}")
        else:
            payload = pull_live()
            path = save_payload("kenpom", payload, now)
            logger.info(f"Saved raw payload: {path}")

        rows, skipped = build_rows(payload)
        total = len(payload["teams"])
        logger.info(f"{len(rows)}/{total} teams have data; {len(skipped)} skipped")
        through = sorted({r["data_through"] for r in rows})
        run.detail = {"teams": total, "with_data": len(rows), "skipped": skipped[:20], "data_through": through}
        logger.info(f"KenPom DataThrough: {through}")

        if total == 0 or len(rows) / total < MIN_SUCCESS_RATIO:
            raise RuntimeError(f"Only {len(rows)}/{total} teams returned data; nothing written")

        norm_rows = normalize(rows)
        snapshot_date = now.strftime("%Y-%m-%d")
        loaded_at = fmt_ts(now)

        with conn:  # one transaction: both tables or neither
            for table, data in (("kenpom_raw", rows), ("kenpom_norm", norm_rows)):
                conn.execute(
                    f"DELETE FROM {table} WHERE season = ? AND snapshot_date = ?",
                    (SEASON, snapshot_date),
                )
                write_snapshot(conn, table, SEASON, snapshot_date, loaded_at, data)

        run.rows_written = len(rows) + len(norm_rows)
        logger.info(f"Wrote snapshot {snapshot_date}: {len(rows)} raw + {len(norm_rows)} normalized rows")

    conn.close()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        if not getattr(e, "_etl_logged", False):  # failed before RunLog started
            logger.error("10_kenpom_snapshot failed", exc_info=True)
        sys.exit(1)
