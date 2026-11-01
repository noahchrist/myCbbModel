import gzip
import json
import os
import sqlite3
from datetime import datetime, timezone

import logger as _logger  # noqa: F401  (importing it loads the right .env for server/local)

# ==============================================
# Settings
# ==============================================

# Hardcoded once per season (KenPom "y" value and games.season).
SEASON = 2027

# master.db is the app's database; we only read teamsMaster from it.
# Everything we collect goes to collect.db next to it.
DB_PATH = os.environ.get("DB_PATH")
if not DB_PATH:
    raise ValueError("Missing DB_PATH in environment variables or .env file")

DATA_DIR = os.path.dirname(os.path.abspath(DB_PATH))
COLLECT_DB_PATH = os.environ.get("COLLECT_DB_PATH") or os.path.join(DATA_DIR, "collect.db")
RAW_DIR = os.environ.get("RAW_PAYLOAD_DIR") or os.path.join(DATA_DIR, "raw")

KENPOM_STATS = [
    "adjOffEff", "adjDefEff", "adjTempo", "effFgPct", "defEffFgPct",
    "trnvrPct", "ftRate", "defFtRate", "offRebPct", "defRebPct",
    "effHeight", "expRtg", "benchRtg", "contRtg", "threesPct",
    "ftPct", "blockPct", "stlRate", "nonStlTrnvrRate", "astRate",
    "threesRate", "oppThreesPct", "oppThreesRate",
]

BOOKS = {"fd": "fanduel", "dk": "draftkings"}
BOOK_FIELDS = [
    ("home_hhPrice", "INTEGER"), ("away_hhPrice", "INTEGER"),
    ("home_spread", "REAL"), ("home_spreadPrice", "INTEGER"),
    ("away_spread", "REAL"), ("away_spreadPrice", "INTEGER"),
    ("over", "REAL"), ("overPrice", "INTEGER"),
    ("under", "REAL"), ("underPrice", "INTEGER"),
]
ODDS_COLUMNS = [f"{p}_{f}" for p in BOOKS for f, _ in BOOK_FIELDS]


# ==============================================
# Time helpers (everything stored as UTC, "YYYY-MM-DDTHH:MM:SSZ")
# ==============================================

TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def fmt_ts(dt):
    return dt.astimezone(timezone.utc).strftime(TS_FORMAT)


def parse_ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


# ==============================================
# Schema
# ==============================================

def _schema_sql():
    stat_cols = ",\n    ".join(f"{s} REAL" for s in KENPOM_STATS)
    book_cols = ",\n    ".join(
        f"{p}_{f} {t}" for p in BOOKS for f, t in BOOK_FIELDS
    )
    update_cols = ",\n    ".join(f"{p}_last_update TEXT" for p in BOOKS)

    snap_cols = ", ".join(f"o.{c}" for c in ODDS_COLUMNS)

    return f"""
CREATE TABLE IF NOT EXISTS kenpom_raw (
    season INTEGER NOT NULL,
    snapshot_date TEXT NOT NULL,
    kpid INTEGER NOT NULL,
    loaded_at TEXT NOT NULL,
    team TEXT,
    data_through TEXT,
    {stat_cols},
    PRIMARY KEY (season, snapshot_date, kpid)
);

CREATE TABLE IF NOT EXISTS kenpom_norm (
    season INTEGER NOT NULL,
    snapshot_date TEXT NOT NULL,
    kpid INTEGER NOT NULL,
    loaded_at TEXT NOT NULL,
    team TEXT,
    data_through TEXT,
    {stat_cols},
    PRIMARY KEY (season, snapshot_date, kpid)
);

CREATE TABLE IF NOT EXISTS games (
    game_id TEXT PRIMARY KEY,
    season INTEGER NOT NULL,
    commence_time_utc TEXT NOT NULL,
    game_date_et TEXT NOT NULL,
    home_team TEXT,
    away_team TEXT,
    home_kpid INTEGER,
    away_kpid INTEGER,
    is_completed INTEGER NOT NULL DEFAULT 0,
    home_score INTEGER,
    away_score INTEGER,
    pt_diff INTEGER,
    pt_total INTEGER,
    first_seen_at TEXT NOT NULL,
    scored_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_games_date ON games (game_date_et);

CREATE TABLE IF NOT EXISTS odds_snapshots (
    game_id TEXT NOT NULL,
    pulled_at TEXT NOT NULL,
    {book_cols},
    {update_cols},
    PRIMARY KEY (game_id, pulled_at)
);

CREATE TABLE IF NOT EXISTS etl_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    script TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    rows_written INTEGER,
    detail TEXT,
    error TEXT
);

-- Latest odds per game, with the column names the app used on games2026.
DROP VIEW IF EXISTS games_current;
CREATE VIEW games_current AS
SELECT g.game_id, g.season, g.commence_time_utc, g.game_date_et AS game_date,
       g.is_completed, g.home_kpid, g.away_kpid, g.home_team, g.away_team,
       g.home_score, g.away_score, g.pt_diff, g.pt_total,
       o.pulled_at AS load_datetime, {snap_cols}
FROM games g
LEFT JOIN odds_snapshots o
  ON o.game_id = g.game_id
 AND o.pulled_at = (SELECT MAX(pulled_at) FROM odds_snapshots WHERE game_id = g.game_id);

-- Last snapshot taken before tip-off.
DROP VIEW IF EXISTS odds_closing;
CREATE VIEW odds_closing AS
SELECT g.commence_time_utc, o.*
FROM games g
JOIN odds_snapshots o
  ON o.game_id = g.game_id
 AND o.pulled_at = (SELECT MAX(pulled_at) FROM odds_snapshots
                    WHERE game_id = g.game_id AND pulled_at <= g.commence_time_utc);
"""


def connect_collect():
    """Open collect.db (creating tables if needed) in WAL mode."""
    os.makedirs(os.path.dirname(COLLECT_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(COLLECT_DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.executescript(_schema_sql())
    conn.commit()
    return conn


def load_theodds_name_map():
    """theoddsTeamName -> kpid, read from master.db's teamsMaster (read-only)."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "SELECT theoddsTeamName, kpid FROM teamsMaster WHERE theoddsTeamName IS NOT NULL"
        ).fetchall()
    finally:
        conn.close()
    return dict(rows)


# ==============================================
# Raw payload archive
# ==============================================

def save_payload(kind, obj, when):
    """Write obj as gzipped JSON under RAW_DIR/<kind>/<YYYY-MM>/ and return the path."""
    folder = os.path.join(RAW_DIR, kind, when.strftime("%Y-%m"))
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{kind}_{when.strftime('%Y%m%dT%H%M%SZ')}.json.gz")
    tmp = path + ".tmp"
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        json.dump(obj, f)
    os.replace(tmp, path)
    return path


def load_payload(path):
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as f:
        return json.load(f)


# ==============================================
# Run log (etl_runs) — a failed run is recorded and re-raised
# ==============================================

class RunLog:
    def __init__(self, conn, script, log):
        self.conn = conn
        self.script = script
        self.log = log
        self.rows_written = 0
        self.detail = {}

    def __enter__(self):
        # The lock in run_daily.sh means any earlier 'running' row for this script was killed.
        self.conn.execute(
            "UPDATE etl_runs SET status = 'abandoned' WHERE script = ? AND status = 'running'",
            (self.script,),
        )
        cur = self.conn.execute(
            "INSERT INTO etl_runs (script, started_at, status) VALUES (?, ?, 'running')",
            (self.script, fmt_ts(utc_now())),
        )
        self.run_id = cur.lastrowid
        self.conn.commit()
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            self.conn.rollback()
            self.log.error(f"{self.script} failed", exc_info=(exc_type, exc, tb))
            exc._etl_logged = True
        self.conn.execute(
            "UPDATE etl_runs SET finished_at = ?, status = ?, rows_written = ?, detail = ?, error = ? "
            "WHERE run_id = ?",
            (
                fmt_ts(utc_now()),
                "failed" if exc_type else "ok",
                self.rows_written,
                json.dumps(self.detail),
                repr(exc) if exc_type else None,
                self.run_id,
            ),
        )
        self.conn.commit()
        return False  # re-raise so the script exits non-zero
