import os
import time
import sqlite3
import logging
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

# ==============================================
# Setup
# ==============================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/kenpom_2026_daily.log"),
        logging.StreamHandler()
    ]
)

load_dotenv()
API_KEY = os.getenv("KENPOM_API_KEY")

if not API_KEY:
    raise ValueError("Missing KENPOM_API_KEY in environment variables or .env file")

logging.info(f"API Key loaded: {API_KEY[:10]}...{API_KEY[-10:]}")

DB_PATH = "data/future.db"
BASE_URL = "https://kenpom.com"
SEASON = 2026
DELAY_BETWEEN_TEAMS = 0.2

# Generate table name with current date
current_date = datetime.now().strftime("%m%d%Y")
TABLE_NAME = f"kenpom_raw_{current_date}"

# ==============================================
# Database Setup
# ==============================================

os.makedirs("data", exist_ok=True)
os.makedirs("logs", exist_ok=True)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Clean up old tables (older than 7 days)
cutoff_date = datetime.now() - timedelta(days=7)
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'kenpom_raw_%'")
existing_tables = cursor.fetchall()

for (table_name,) in existing_tables:
    try:
        date_str = table_name.replace("kenpom_raw_", "")
        table_date = datetime.strptime(date_str, "%m%d%Y")
        if table_date < cutoff_date:
            cursor.execute(f"DROP TABLE {table_name}")
            logging.info(f"Dropped old table: {table_name}")
    except ValueError:
        continue

# Drop today's table if it exists (replace)
cursor.execute(f"DROP TABLE IF EXISTS {TABLE_NAME}")

# Create today's table
cursor.execute(f"""
CREATE TABLE {TABLE_NAME} (
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
logging.info(f"Created table: {TABLE_NAME}")

# ==============================================
# Helper Functions
# ==============================================

def get(endpoint, params=None):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "User-Agent": "KenPom-2026-Daily/1.0"
    }
    
    if params is None:
        params = {}
    params['endpoint'] = endpoint
    
    url = f"{BASE_URL}/api.php"
    
    r = requests.get(url, headers=headers, params=params)
    
    if r.status_code != 200:
        logging.error(f"HTTP {r.status_code} for {endpoint}")
        return None
    return r.json()

def insert_record(data):
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
# Main Data Pull
# ==============================================

logging.info(f"===== Pulling 2026 season data =====")
teams = get("teams", params={"y": SEASON})

if not teams:
    logging.error("No teams found for 2026 season")
    conn.close()
    exit(1)

team_list = teams if isinstance(teams, list) else teams.get("teams", [])
logging.info(f"{len(team_list)} teams found for {SEASON}")

success_count = 0
fail_count = 0

for i, team in enumerate(team_list, 1):
    team_name = team.get("TeamName")
    kpid = team.get("TeamID")
    
    logging.info(f"Processing {i}/{len(team_list)}: {team_name}")

    try:
        ratings = get("ratings", {"team_id": kpid, "y": SEASON}) or []
        fourfactors = get("four-factors", {"team_id": kpid, "y": SEASON}) or []
        height = get("height", {"team_id": kpid, "y": SEASON}) or []
        misc = get("misc-stats", {"team_id": kpid, "y": SEASON}) or []
        
        ratings_data = ratings[0] if ratings else {}
        fourfactors_data = fourfactors[0] if fourfactors else {}
        height_data = height[0] if height else {}
        misc_data = misc[0] if misc else {}

        row = (
            None,  # teamId - to be populated later
            SEASON,
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
            misc_data.get("OppNSTRate"),  # Changed from NSTRate
            misc_data.get("ARate"),
            misc_data.get("F3GRate"),
            misc_data.get("OppFG3Pct"),
            misc_data.get("OppF3GRate"),
        )

        insert_record(row)
        success_count += 1
        logging.info(f"✓ Added {team_name}")
    except Exception as e:
        logging.error(f"Error processing {team_name}: {e}")
        fail_count += 1

    time.sleep(DELAY_BETWEEN_TEAMS)

logging.info(f"🏀 2026 data pull COMPLETE: {success_count} teams added, {fail_count} failures")
logging.info(f"📊 Data saved to table: {TABLE_NAME}")

conn.close()