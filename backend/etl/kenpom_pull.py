import os
import time
import sqlite3
import logging
import requests
from dotenv import load_dotenv

# ==============================================
# Setup
# ==============================================

# ==============================================
# Logging Setup (must be first)
# ==============================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("kenpom_pull.log"),
        logging.StreamHandler()  # Console output
    ]
)

load_dotenv()
API_KEY = os.getenv("KENPOM_API_KEY")

if not API_KEY:
    raise ValueError("Missing KENPOM_API_KEY in environment variables or .env file")

logging.info(f"API Key loaded: {API_KEY[:10]}...{API_KEY[-10:]}")

DB_PATH = "data/master.db"
TABLE_NAME = "kenpom_raw"
BASE_URL = "https://kenpom.com"

SEASONS = [2012, 2013, 2014, 2015, 2016, 2017, 2018]
DELAY_BETWEEN_TEAMS = 1.0  # seconds

# ==============================================
# SQLite Setup
# ==============================================

try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
except sqlite3.Error as e:
    logging.error(f"Database connection failed: {e}")
    raise

cursor.execute(f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    teamId INTEGER,
    season INTEGER,
    team TEXT,
    kpid INTEGER,
    adjOffEff REAL,
    adjDefEff REAL,
    adjTempo REAL,
    effFgPct REAL,
    defEffFgPct REAL,
    trnvrPct REAL,
    ftRate REAL,
    defFtRate REAL,
    offRebPct REAL,
    defRebPct REAL,
    effHeight REAL,
    expRtg REAL,
    benchRtg REAL,
    contRtg REAL,
    threesPct REAL,
    ftPct REAL,
    blockPct REAL,
    stlRate REAL,
    nonStlTrnvrRate REAL,
    astRate REAL,
    threesRate REAL,
    oppThreesPct REAL,
    oppThreesRate REAL
);
""")
conn.commit()

# ==============================================
# Helper Functions
# ==============================================

def get(endpoint, params=None):
    """Wrapper for KenPom API calls."""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "User-Agent": "KenPom-ETL-Script/1.0"
    }
    
    if params is None:
        params = {}
    params['endpoint'] = endpoint
    
    url = f"{BASE_URL}/api.php"
    
    logging.info(f"Requesting: {url} with endpoint={endpoint}")
    
    r = requests.get(url, headers=headers, params=params)
    logging.info(f"Response status: {r.status_code}")
    
    if r.status_code != 200:
        logging.error(f"HTTP {r.status_code} for {endpoint} - {r.text[:500]}")
        return None
    return r.json()

def insert_record(data):
    """Insert a single record into the database."""
    cursor.execute(f"""
        INSERT INTO {TABLE_NAME} (
            teamId, season, team, kpid, adjOffEff, adjDefEff, adjTempo,
            effFgPct, defEffFgPct, trnvrPct, ftRate, defFtRate, offRebPct, defRebPct,
            effHeight, expRtg, benchRtg, contRtg,
            threesPct, ftPct, blockPct, stlRate, nonStlTrnvrRate,
            astRate, threesRate, oppThreesPct, oppThreesRate
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, data)
    conn.commit()

# ==============================================
# Main Loop
# ==============================================

for season in SEASONS:
    logging.info(f"===== Pulling season {season} =====")
    teams = get("teams", params={"y": season})

    if not teams:
        logging.error(f"No teams found for season {season}. Skipping.")
        continue

    team_list = teams if isinstance(teams, list) else teams.get("teams", [])
    logging.info(f"{len(team_list)} teams found for {season}")

    success_count = 0
    fail_count = 0

    for i, team in enumerate(team_list, 1):
        team_name = team.get("TeamName")
        kpid = team.get("TeamID")
        
        logging.info(f"Processing team {i}/{len(team_list)}: {team_name} (ID: {kpid})")

        try:
            ratings = get("ratings", {"team_id": kpid, "y": season}) or []
            fourfactors = get("four-factors", {"team_id": kpid, "y": season}) or []
            height = get("height", {"team_id": kpid, "y": season}) or []
            misc = get("misc-stats", {"team_id": kpid, "y": season}) or []
            
            # Extract first item from each list response
            ratings_data = ratings[0] if ratings else {}
            fourfactors_data = fourfactors[0] if fourfactors else {}
            height_data = height[0] if height else {}
            misc_data = misc[0] if misc else {}

            row = (
                None,  # teamId - to be populated later
                season,
                team_name,
                kpid,
                ratings_data.get("AdjOE"),
                ratings_data.get("AdjDE"),
                ratings_data.get("AdjTempo"),
                fourfactors_data.get("eFG_Pct"),
                fourfactors_data.get("DeFG_Pct"),
                fourfactors_data.get("TO_Pct"),
                fourfactors_data.get("FT_Rate"),
                fourfactors_data.get("DFT_Rate"),
                fourfactors_data.get("OR_Pct"),
                fourfactors_data.get("DOR_Pct"),
                height_data.get("HgtEff"),
                height_data.get("Exp"),
                height_data.get("Bench"),
                height_data.get("Continuity"),
                misc_data.get("FG3Pct"),
                misc_data.get("FTPct"),
                misc_data.get("BlockPct"),
                misc_data.get("StlRate"),
                misc_data.get("NSTRate"),
                misc_data.get("ARate"),
                misc_data.get("F3GRate"),
                misc_data.get("OppFG3Pct"),
                misc_data.get("OppF3GRate"),
            )

            if any(val is None for val in row[3:]):  # ignore season, team, kpid
                logging.warning(f"Null values found for {team_name} ({season}): {[i for i, val in enumerate(row[3:], 3) if val is None]}")

            insert_record(row)
            success_count += 1
            logging.info(f"✓ Successfully added {team_name} to database")
        except Exception as e:
            logging.error(f"Error processing {team_name} ({season}): {e}")
            fail_count += 1

        time.sleep(DELAY_BETWEEN_TEAMS)

    logging.info(f"🏀 Season {season} COMPLETE: {success_count} teams added, {fail_count} failures")
    logging.info(f"📊 Total records in database for {season}: {success_count}")

conn.close()
logging.info("All seasons complete. Connection closed.")
