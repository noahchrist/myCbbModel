"""Odds + scores pulls from The Odds API -> collect.db.

  games           one row per game; identity upserted from the odds feed, final score
                  written once from the scores feed
  odds_snapshots  append-only, change-only: a pull adds a row for a game only when its lines
                  differ from the game's latest row (so the first row ~ opening line seen, the
                  last row before tip-off ~ closing line)

Two jobs share this script (see run_odds.sh / run_daily.sh):
    python 20_odds_snapshot.py --mode odds     # frequent; spreads+totals, costs 2 credits
    python 20_odds_snapshot.py --mode scores   # daily; costs 2 credits
    python 20_odds_snapshot.py                 # both
    python 20_odds_snapshot.py --odds-file A --scores-file B    # re-ingest saved payloads, no network
    --key-env THEODDS_API_KEY_FREE             # use the free key (testing)
"""
import argparse
import json
import os
import sys
import time
from datetime import timedelta
from zoneinfo import ZoneInfo

import requests

from logger import get_logger
from common import (
    BOOKS, BOOK_FIELDS, ODDS_COLUMNS, SEASON, RunLog, connect_collect, fmt_ts,
    load_payload, load_theodds_name_map, parse_ts, save_payload, utc_now,
)

logger = get_logger("20_odds_snapshot")

BASE_URL = "https://api.the-odds-api.com/v4"
SPORT_KEY = "basketball_ncaab"
LOW_CREDIT_WARNING = 1000
MIN_CREDITS_FOR_SCORES = 5
# The odds job stops pulling below this so the daily scores job can keep running.
ODDS_CREDIT_FLOOR = 100

EASTERN = ZoneInfo("America/New_York")


# ==============================================
# API
# ==============================================

class OddsApi:
    def __init__(self, api_key):
        self.api_key = api_key
        self.requests_made = 0
        self.remaining = None
        self.last_cost = None

    def get(self, endpoint, params):
        params = dict(params, apiKey=self.api_key)
        logger.info(f"Requesting: {endpoint} { {k: v for k, v in params.items() if k != 'apiKey'} }")
        last_error = None
        for attempt in range(1, 4):
            try:
                r = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=30)
                if r.status_code < 500:
                    break
                last_error = f"HTTP {r.status_code}"
            except requests.RequestException as e:
                last_error = str(e)
            logger.warning(f"{endpoint} attempt {attempt} failed: {last_error}")
            time.sleep(3 * attempt)
        else:
            raise RuntimeError(f"{endpoint} failed after 3 attempts: {last_error}")

        self.requests_made += 1
        if "x-requests-remaining" in r.headers:
            self.remaining = r.headers["x-requests-remaining"]
            self.last_cost = r.headers.get("x-requests-last")
            logger.info(f"API usage - remaining: {self.remaining}, last cost: {self.last_cost}")
        r.raise_for_status()
        return r.json()


# ==============================================
# Parsing
# ==============================================

def game_date_et(commence_utc):
    """ET calendar date of the game; tip-offs before 4 AM ET belong to the previous day."""
    et = commence_utc.astimezone(EASTERN)
    if et.hour < 4:
        et -= timedelta(days=1)
    return et.date().isoformat()


def extract_book(bookmakers, book_key, prefix, home_team, cutoff=None):
    """Flatten one bookmaker's h2h/spreads/totals into prefixed column names.

    cutoff (the game's tip-off): a market whose own last_update is after it is a live in-game
    quote and is dropped, so only pre-game lines are ever stored.
    """
    out = {}
    for book in bookmakers:
        if book.get("key") != book_key:
            continue
        kept = 0
        for market in book.get("markets", []):
            if cutoff is not None and market.get("last_update") and parse_ts(market["last_update"]) > cutoff:
                continue
            kept += 1
            for o in market.get("outcomes", []):
                if market["key"] == "h2h":
                    side = "home" if o["name"] == home_team else "away"
                    out[f"{prefix}_{side}_hhPrice"] = o["price"]
                elif market["key"] == "spreads":
                    side = "home" if o["name"] == home_team else "away"
                    out[f"{prefix}_{side}_spread"] = o.get("point")
                    out[f"{prefix}_{side}_spreadPrice"] = o["price"]
                elif market["key"] == "totals":
                    side = "over" if o["name"] == "Over" else "under"
                    out[f"{prefix}_{side}"] = o.get("point")
                    out[f"{prefix}_{side}Price"] = o["price"]
        if kept:
            out[f"{prefix}_last_update"] = book.get("last_update")
        break
    return out


# ==============================================
# Writes
# ==============================================

UPSERT_GAME = """
INSERT INTO games (game_id, season, commence_time_utc, game_date_et, home_team, away_team,
                   home_kpid, away_kpid, first_seen_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(game_id) DO UPDATE SET
    commence_time_utc = excluded.commence_time_utc,
    game_date_et      = excluded.game_date_et,
    home_kpid         = COALESCE(excluded.home_kpid, games.home_kpid),
    away_kpid         = COALESCE(excluded.away_kpid, games.away_kpid)
"""

SNAPSHOT_COLUMNS = ["game_id", "pulled_at"] + ODDS_COLUMNS + [f"{p}_last_update" for p in BOOKS]
INSERT_SNAPSHOT = (
    f"INSERT OR IGNORE INTO odds_snapshots ({','.join(SNAPSHOT_COLUMNS)}) "
    f"VALUES ({','.join('?' * len(SNAPSHOT_COLUMNS))})"
)


def upsert_game(conn, game, name_map, now, unmapped):
    home, away = game["home_team"], game["away_team"]
    home_kpid, away_kpid = name_map.get(home), name_map.get(away)
    for name, kpid in ((home, home_kpid), (away, away_kpid)):
        if kpid is None:
            unmapped.add(name)
    commence = parse_ts(game["commence_time"])
    conn.execute(UPSERT_GAME, (
        game["id"], SEASON, fmt_ts(commence), game_date_et(commence), home, away,
        home_kpid, away_kpid, fmt_ts(now),
    ))
    return commence


def latest_odds(conn, game_id):
    row = conn.execute(
        f"SELECT {','.join(SNAPSHOT_COLUMNS[2:])} FROM odds_snapshots WHERE game_id = ? "
        "ORDER BY pulled_at DESC LIMIT 1", (game_id,)).fetchone()
    return row


def ingest_odds(conn, odds_data, name_map, now):
    """Returns (rows written, new games, already tipped, unchanged, unmapped)."""
    unmapped, snapshots, started, unchanged, new_games = set(), 0, 0, 0, 0
    with conn:
        for game in odds_data:
            commence = upsert_game(conn, game, name_map, now, unmapped)

            # After tip-off the feed carries live lines. Keep a quote only if the book last
            # updated it before the game started (so a pull a few seconds after tip can still
            # capture the true closing line); live quotes are dropped.
            odds = {}
            for prefix, book_key in BOOKS.items():
                odds.update(extract_book(game.get("bookmakers", []), book_key, prefix,
                                         game["home_team"], cutoff=commence))
            if commence <= now and not any(odds.get(c) is not None for c in ODDS_COLUMNS):
                started += 1
                continue
            values = [odds.get(c) for c in SNAPSHOT_COLUMNS[2:]]
            prev = latest_odds(conn, game["id"])
            if commence <= now and prev is not None:
                # Post-tip pull: dropped (live) markets must not blank the stored pre-game line.
                values = [v if v is not None else p for v, p in zip(values, prev)]
            n = len(ODDS_COLUMNS)
            if prev is not None and tuple(values[:n]) == tuple(prev[:n]):
                unchanged += 1
                continue
            if prev is None:
                new_games += 1
            conn.execute(INSERT_SNAPSHOT, (game["id"], fmt_ts(now), *values))
            snapshots += 1
    return snapshots, new_games, started, unchanged, unmapped


def ingest_scores(conn, scores_data, name_map, now):
    unmapped, scored = set(), 0
    with conn:
        for game in scores_data:
            if not game.get("completed"):
                continue
            home, away = game["home_team"], game["away_team"]
            by_name = {s["name"]: s["score"] for s in game.get("scores") or []}
            if by_name.get(home) is None or by_name.get(away) is None:
                continue
            home_score, away_score = int(by_name[home]), int(by_name[away])

            upsert_game(conn, game, name_map, now, unmapped)
            conn.execute(
                "UPDATE games SET home_score = ?, away_score = ?, pt_diff = ?, pt_total = ?, "
                "is_completed = 1, scored_at = COALESCE(scored_at, ?) WHERE game_id = ?",
                (home_score, away_score, home_score - away_score, home_score + away_score,
                 fmt_ts(now), game["id"]),
            )
            scored += 1
    return scored, unmapped


# ==============================================
# Main
# ==============================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["odds", "scores", "both"], default="both",
                        help="odds = frequent line pull; scores = daily results pull")
    parser.add_argument("--key-env", default="THEODDS_API_KEY",
                        help="env var holding the API key (THEODDS_API_KEY_FREE for tests)")
    parser.add_argument("--odds-file", help="saved odds payload (skips the odds API call)")
    parser.add_argument("--scores-file", help="saved scores payload (skips the scores API call)")
    parser.add_argument("--now", help="override run time (UTC ISO), for replaying old payloads")
    args = parser.parse_args()

    do_odds = args.mode in ("odds", "both")
    do_scores = args.mode in ("scores", "both")
    script = "20_scores_snapshot" if args.mode == "scores" else "20_odds_snapshot"

    logger.info(f"Starting {script} for season {SEASON} (mode={args.mode})")
    conn = connect_collect()
    now = parse_ts(args.now) if args.now else utc_now()
    name_map = load_theodds_name_map()

    needs_api = (do_odds and not args.odds_file) or (do_scores and not args.scores_file)
    api = None
    if needs_api:
        api_key = os.environ.get(args.key_env)
        if not api_key:
            raise ValueError(f"Missing {args.key_env} in environment variables or .env file")
        api = OddsApi(api_key)

    with RunLog(conn, script, logger) as run:
        detail = {}
        unmapped = set()
        written = 0

        # ---- odds ----
        if do_odds:
            last = conn.execute(
                "SELECT detail FROM etl_runs WHERE script = ? AND status = 'ok' "
                "ORDER BY run_id DESC LIMIT 1", (script,)).fetchone()
            last_credits = json.loads(last[0]).get("credits_remaining") if last and last[0] else None
            if api and last_credits is not None and int(float(last_credits)) < ODDS_CREDIT_FLOOR:
                raise RuntimeError(f"Only {last_credits} credits left; odds job paused to protect scores")

            if args.odds_file:
                odds_data = load_payload(args.odds_file)
            else:
                odds_data = api.get(f"sports/{SPORT_KEY}/odds", {
                    "regions": "us",
                    "markets": "spreads,totals",
                    "bookmakers": ",".join(BOOKS.values()),
                    "oddsFormat": "american",
                })
                logger.info(f"Saved raw odds payload: {save_payload('odds', odds_data, now)}")

            snapshots, new_games, started, unchanged, unm = ingest_odds(conn, odds_data, name_map, now)
            unmapped |= unm
            logger.info(f"Odds: {len(odds_data)} games in feed, {snapshots} rows written "
                        f"({new_games} new games, {unchanged} unchanged), {started} already tipped (skipped)")
            written += snapshots
            detail.update(games_in_feed=len(odds_data), snapshots=snapshots, new_games=new_games,
                          unchanged=unchanged, already_tipped=started)

        # ---- scores ----
        if do_scores:
            if args.scores_file:
                scores_data = load_payload(args.scores_file)
            elif api.remaining is not None and int(float(api.remaining)) < MIN_CREDITS_FOR_SCORES:
                raise RuntimeError(f"Only {api.remaining} API credits left; skipping scores")
            else:
                scores_data = api.get(f"sports/{SPORT_KEY}/scores", {"daysFrom": 3})
                logger.info(f"Saved raw scores payload: {save_payload('scores', scores_data, now)}")

            scored, unm = ingest_scores(conn, scores_data, name_map, now)
            unmapped |= unm
            logger.info(f"Scores: {scored} completed games written")
            written += scored
            detail["scored"] = scored

        if unmapped:
            logger.warning(f"{len(unmapped)} team names not in teamsMaster (kpid NULL): {sorted(unmapped)}")
        if api and api.remaining is not None and int(float(api.remaining)) < LOW_CREDIT_WARNING:
            logger.warning(f"Low API credits: {api.remaining} remaining")

        run.rows_written = written
        detail.update(unmapped_teams=sorted(unmapped), credits_remaining=api.remaining if api else None)
        run.detail = detail

    conn.close()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        if not getattr(e, "_etl_logged", False):  # failed before RunLog started
            logger.error("20_odds_snapshot failed", exc_info=True)
        sys.exit(1)
