"""Daily odds + scores pull from The Odds API -> collect.db.

  games           one row per game; identity upserted from the odds feed, final score
                  written once from the scores feed
  odds_snapshots  append-only; every pull adds one row per game still to be played

Usage:
    python 20_odds_snapshot.py                                  # live pull (costs ~5 credits)
    python 20_odds_snapshot.py --odds-file A --scores-file B    # re-ingest saved payloads, no network
"""
import argparse
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
LOW_CREDIT_WARNING = 50
MIN_CREDITS_FOR_SCORES = 5

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


def extract_book(bookmakers, book_key, prefix, home_team):
    """Flatten one bookmaker's h2h/spreads/totals into prefixed column names."""
    out = {}
    for book in bookmakers:
        if book.get("key") != book_key:
            continue
        out[f"{prefix}_last_update"] = book.get("last_update")
        for market in book.get("markets", []):
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


def ingest_odds(conn, odds_data, name_map, now):
    unmapped, snapshots, started = set(), 0, 0
    with conn:
        for game in odds_data:
            commence = upsert_game(conn, game, name_map, now, unmapped)

            # Once a game has tipped the feed can carry live lines; keep only pre-game odds.
            if commence <= now:
                started += 1
                continue

            odds = {}
            for prefix, book_key in BOOKS.items():
                odds.update(extract_book(game.get("bookmakers", []), book_key, prefix, game["home_team"]))
            conn.execute(INSERT_SNAPSHOT, (
                game["id"], fmt_ts(now), *[odds.get(c) for c in SNAPSHOT_COLUMNS[2:]]
            ))
            snapshots += 1
    return snapshots, started, unmapped


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
    parser.add_argument("--odds-file", help="saved odds payload (skips the odds API call)")
    parser.add_argument("--scores-file", help="saved scores payload (skips the scores API call)")
    parser.add_argument("--now", help="override run time (UTC ISO), for replaying old payloads")
    args = parser.parse_args()

    logger.info(f"Starting odds snapshot for season {SEASON}")
    conn = connect_collect()
    now = parse_ts(args.now) if args.now else utc_now()
    name_map = load_theodds_name_map()

    api = None
    if not (args.odds_file and args.scores_file):
        api_key = os.environ.get("THEODDS_API_KEY")
        if not api_key:
            raise ValueError("Missing THEODDS_API_KEY in environment variables or .env file")
        api = OddsApi(api_key)

    with RunLog(conn, "20_odds_snapshot", logger) as run:
        # ---- odds ----
        if args.odds_file:
            odds_data = load_payload(args.odds_file)
        else:
            odds_data = api.get(f"sports/{SPORT_KEY}/odds", {
                "regions": "us",
                "markets": "h2h,spreads,totals",
                "bookmakers": ",".join(BOOKS.values()),
                "oddsFormat": "american",
            })
            logger.info(f"Saved raw odds payload: {save_payload('odds', odds_data, now)}")

        snapshots, started, unmapped = ingest_odds(conn, odds_data, name_map, now)
        logger.info(f"Odds: {len(odds_data)} games in feed, {snapshots} snapshots written, "
                    f"{started} already tipped (skipped)")

        # ---- scores ----
        if args.scores_file:
            scores_data = load_payload(args.scores_file)
        elif api.remaining is not None and int(api.remaining) < MIN_CREDITS_FOR_SCORES:
            raise RuntimeError(f"Only {api.remaining} API credits left; skipping scores")
        else:
            scores_data = api.get(f"sports/{SPORT_KEY}/scores", {"daysFrom": 3})
            logger.info(f"Saved raw scores payload: {save_payload('scores', scores_data, now)}")

        scored, unmapped_scores = ingest_scores(conn, scores_data, name_map, now)
        unmapped |= unmapped_scores
        logger.info(f"Scores: {scored} completed games written")

        if unmapped:
            logger.warning(f"{len(unmapped)} team names not in teamsMaster (kpid NULL): {sorted(unmapped)}")
        if api and api.remaining is not None and int(api.remaining) < LOW_CREDIT_WARNING:
            logger.warning(f"Low API credits: {api.remaining} remaining")

        run.rows_written = snapshots + scored
        run.detail = {
            "games_in_feed": len(odds_data), "snapshots": snapshots, "already_tipped": started,
            "scored": scored, "unmapped_teams": sorted(unmapped),
            "credits_remaining": api.remaining if api else None,
        }

    conn.close()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        if not getattr(e, "_etl_logged", False):  # failed before RunLog started
            logger.error("20_odds_snapshot failed", exc_info=True)
        sys.exit(1)
