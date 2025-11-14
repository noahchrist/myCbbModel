import os
import time
import sqlite3
import logging
import requests
import numpy as np
from datetime import datetime, timedelta
from dotenv import load_dotenv

# ==============================================
# Path Setup
# ==============================================

# Get the directory where this script is located (backend/etl/)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Get the backend directory (one level up from etl/)
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)

# Define paths relative to backend directory
DATA_DIR = os.path.join(BACKEND_DIR, "data")
LOGS_DIR = os.path.join(BACKEND_DIR, "logs")
DB_PATH = os.path.join(DATA_DIR, "master.db")
LOG_PATH = os.path.join(LOGS_DIR, "kenpom_2026_complete.log")

# ==============================================
# Setup & Logging
# ==============================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler()
    ]
)

load_dotenv()
API_KEY = os.getenv("KENPOM_API_KEY")

if not API_KEY:
    raise ValueError("Missing KENPOM_API_KEY in environment variables or .env file")

logging.info("🚀 STARTING KENPOM 2026 COMPLETE PIPELINE")
logging.info(f"API Key loaded: {API_KEY[:10]}...{API_KEY[-10:]}")

BASE_URL = "https://kenpom.com"
SEASON = 2026
DELAY_BETWEEN_TEAMS = 0.1

# Table names
RAW_TABLE = "kenpom_raw_temp"
CLEANED_TABLE = "kenpom2026"

# ==============================================
# User Confirmation
# ==============================================

print(f"\n📅 Current Date: {datetime.now().strftime('%Y-%m-%d')}")
print(f"📊 Target table: {CLEANED_TABLE}")

# Check if cleaned table exists and get last update time
conn_check = sqlite3.connect(DB_PATH)
cursor_check = conn_check.cursor()

cursor_check.execute("SELECT name FROM sqlite_master WHERE type='table' AND name = ?", (CLEANED_TABLE,))
existing_table = cursor_check.fetchone()

if existing_table:
    # Try to get last update time from loaddatetime field
    try:
        cursor_check.execute(f"SELECT MAX(loaddatetime) FROM {CLEANED_TABLE}")
        last_update = cursor_check.fetchone()[0]
        if last_update:
            print(f"⚠️  Warning: Table {CLEANED_TABLE} exists and will be rewritten")
            print(f"📅 Last updated: {last_update}")
        else:
            print(f"⚠️  Warning: Table {CLEANED_TABLE} exists and will be rewritten")
            print(f"📅 Last updated: Unknown")
    except:
        print(f"⚠️  Warning: Table {CLEANED_TABLE} exists and will be rewritten")
        print(f"📅 Last updated: Unknown")
else:
    print("✅ No existing table found - will create new table")

conn_check.close()

response = input("\nDo you want to continue? (y/n): ").lower().strip()
if response != 'y':
    print("❌ Script cancelled by user")
    exit(0)

print("✅ Continuing with KenPom data pull...\n")

# Fields to invert (multiply by -1) before normalization
INVERT_FIELDS = [
    'adjDefEff', 'defEffFgPct', 'trnvrPct', 'defFtRate', 
    'defRebPct', 'oppThreesPct', 'oppThreesRate'
]

# All stat fields (excluding id, teamId, season, team, kpid)
STAT_FIELDS = [
    'adjOffEff', 'adjDefEff', 'adjTempo', 'effFgPct', 'defEffFgPct', 
    'trnvrPct', 'ftRate', 'defFtRate', 'offRebPct', 'defRebPct',
    'effHeight', 'expRtg', 'benchRtg', 'contRtg', 'threesPct', 
    'ftPct', 'blockPct', 'stlRate', 'nonStlTrnvrRate', 'astRate', 
    'threesRate', 'oppThreesPct', 'oppThreesRate'
]

# ==============================================
# Database Setup
# ==============================================

logging.info("📁 STEP 1: DATABASE SETUP")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Drop temp and target tables if they exist
cursor.execute(f"DROP TABLE IF EXISTS {RAW_TABLE}")
cursor.execute(f"DROP TABLE IF EXISTS {CLEANED_TABLE}")
logging.info(f"Dropped existing tables if present")

# Create temp raw table
logging.info(f"📊 Creating temp table: {RAW_TABLE}")
cursor.execute(f"""
CREATE TABLE {RAW_TABLE} (
    kpid INTEGER PRIMARY KEY,
    season INTEGER,
    team TEXT,
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
logging.info("✅ STEP 1 COMPLETE: Database setup finished")
conn.commit()
logging.info("✅ STEP 1 COMPLETE: Database setup finished")

# ==============================================
# Helper Functions
# ==============================================

def get(endpoint, params=None):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "User-Agent": "KenPom-2026-Complete/1.0"
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
        INSERT INTO {RAW_TABLE} (
            kpid, season, team, adjOffEff, adjDefEff, adjTempo,
            effFgPct, defEffFgPct, trnvrPct, ftRate, defFtRate, offRebPct, defRebPct,
            effHeight, expRtg, benchRtg, contRtg,
            threesPct, ftPct, blockPct, stlRate, nonStlTrnvrRate,
            astRate, threesRate, oppThreesPct, oppThreesRate
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, data)
    conn.commit()

# ==============================================
# STEP 2: Data Pull from KenPom API
# ==============================================

logging.info("🌐 STEP 2: KENPOM API DATA PULL")
logging.info(f"Pulling 2026 season data...")

teams = get("teams", params={"y": SEASON})

if not teams:
    logging.error("❌ No teams found for 2026 season")
    conn.close()
    exit(1)

team_list = teams if isinstance(teams, list) else teams.get("teams", [])
logging.info(f"📋 Found {len(team_list)} teams for {SEASON}")

success_count = 0
fail_count = 0

for i, team in enumerate(team_list, 1):
    team_name = team.get("TeamName")
    kpid = team.get("TeamID")
    
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
            kpid,
            SEASON,
            team_name,
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
            misc_data.get("OppNSTRate"),
            misc_data.get("ARate"),
            misc_data.get("F3GRate"),
            misc_data.get("OppFG3Pct"),
            misc_data.get("OppF3GRate"),
        )

        insert_record(row)
        success_count += 1
    except Exception as e:
        logging.error(f"❌ Error processing {team_name}: {e}")
        fail_count += 1

    if i % 50 == 0 or i == len(team_list):
        logging.info(f"📊 Progress: {i}/{len(team_list)} teams processed ({success_count} success, {fail_count} failed)")
    
    time.sleep(DELAY_BETWEEN_TEAMS)

logging.info(f"✅ STEP 2 COMPLETE: API data pull finished")
logging.info(f"  📊 {success_count} teams added successfully")
logging.info(f"  ❌ {fail_count} teams failed")

# ==============================================
# STEP 3: Data Validation
# ==============================================

logging.info("🔍 STEP 3: DATA VALIDATION")

# Verify all records have kpids
cursor.execute(f"SELECT COUNT(*) FROM {RAW_TABLE} WHERE kpid IS NULL")
null_kpids = cursor.fetchone()[0]

if null_kpids > 0:
    logging.warning(f"⚠️ {null_kpids} records have NULL kpids")
else:
    logging.info("✅ All records have valid kpids")

logging.info(f"✅ STEP 3 COMPLETE: Data validation finished")

# ==============================================
# STEP 4: Normalization
# ==============================================

logging.info("🔄 STEP 4: DATA NORMALIZATION")

# Get source table structure
cursor.execute(f"PRAGMA table_info({RAW_TABLE})")
columns = cursor.fetchall()

# Create target table with loaddatetime field
create_sql = f"CREATE TABLE {CLEANED_TABLE} (\n"
for col in columns:
    col_name, col_type = col[1], col[2]
    if col_name == 'kpid':
        create_sql += f"    {col_name} {col_type} PRIMARY KEY,\n"
        create_sql += f"    loaddatetime TEXT,\n"  # Add loaddatetime after kpid
    else:
        create_sql += f"    {col_name} {col_type},\n"
create_sql = create_sql.rstrip(',\n') + "\n);"

cursor.execute(create_sql)
conn.commit()
logging.info(f"📊 Created {CLEANED_TABLE} table")

# Get all records for 2026 season
cursor.execute(f"SELECT * FROM {RAW_TABLE} WHERE season = 2026")
records = cursor.fetchall()

if not records:
    logging.error("❌ No 2026 records found for normalization")
    conn.close()
    exit(1)

logging.info(f"📊 Found {len(records)} records for normalization")

# Get column names
cursor.execute(f"PRAGMA table_info({RAW_TABLE})")
col_info = cursor.fetchall()
col_names = [col[1] for col in col_info]
col_indices = {name: idx for idx, name in enumerate(col_names)}

# Extract stat values for normalization
logging.info("📈 Calculating normalization statistics...")
stat_data = {}
for field in STAT_FIELDS:
    if field in col_indices:
        col_idx = col_indices[field]
        values = [record[col_idx] for record in records if record[col_idx] is not None]
        
        # Invert if needed
        if field in INVERT_FIELDS:
            values = [-v for v in values]
            logging.info(f"  🔄 Inverted {field}")
        
        stat_data[field] = values

# Calculate z-scores for each stat field
normalized_stats = {}
for field, values in stat_data.items():
    if len(values) > 1:
        mean_val = np.mean(values)
        std_val = np.std(values, ddof=1)
        
        if std_val > 0:
            normalized_stats[field] = {'mean': mean_val, 'std': std_val}
        else:
            normalized_stats[field] = {'mean': mean_val, 'std': 1.0}
            logging.warning(f"⚠️ Zero std dev for {field}, using std=1.0")

logging.info("📊 Inserting normalized records...")
current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# Insert normalized records
for i, record in enumerate(records, 1):
    if i % 50 == 0 or i == len(records):
        logging.info(f"  📊 Normalization progress: {i}/{len(records)} records processed")
    
    new_record = list(record)
    
    # Normalize each stat field
    for field in STAT_FIELDS:
        if field in col_indices and field in normalized_stats:
            col_idx = col_indices[field]
            original_value = record[col_idx]
            
            if original_value is not None:
                # Apply inversion if needed
                value = -original_value if field in INVERT_FIELDS else original_value
                
                # Z-score normalize
                mean_val = normalized_stats[field]['mean']
                std_val = normalized_stats[field]['std']
                z_score = (value - mean_val) / std_val
                
                new_record[col_idx] = z_score
    
    # Insert record with loaddatetime
    new_record.insert(1, current_datetime)  # Insert loaddatetime after kpid
    col_names_with_datetime = col_names[:1] + ['loaddatetime'] + col_names[1:]
    placeholders = ",".join(["?"] * len(new_record))
    insert_sql = f"INSERT INTO {CLEANED_TABLE} ({','.join(col_names_with_datetime)}) VALUES ({placeholders})"
    cursor.execute(insert_sql, new_record)

conn.commit()

# Drop the temporary raw table
logging.info(f"🗑️ Dropping temporary raw table: {RAW_TABLE}")
cursor.execute(f"DROP TABLE {RAW_TABLE}")
conn.commit()
logging.info("✅ Temporary raw table dropped")

# ==============================================
# Final Verification & Summary
# ==============================================

logging.info("📋 STEP 5: FINAL VERIFICATION")

# Verification
cursor.execute(f"SELECT COUNT(*) FROM {CLEANED_TABLE}")
final_count = cursor.fetchone()[0]

# Sample verification
cursor.execute(f"SELECT AVG(adjOffEff), AVG(adjDefEff) FROM {CLEANED_TABLE}")
avg_stats = cursor.fetchone()

logging.info("🎉 PIPELINE COMPLETE - FINAL SUMMARY:")
logging.info(f"  📊 Raw records processed: {len(records)}")
logging.info(f"  📊 Cleaned records created: {final_count}")
logging.info(f"  📊 Data validation complete")
logging.info(f"  📊 Average normalized stats: Off={avg_stats[0]:.3f}, Def={avg_stats[1]:.3f}")
logging.info(f"  📁 Final table: {CLEANED_TABLE}")
logging.info(f"  📅 Load datetime: {current_datetime}")

if final_count == len(records):
    logging.info("✅ SUCCESS: All records processed successfully!")
else:
    logging.warning(f"⚠️ WARNING: Record count mismatch")

conn.close()
logging.info("🏁 KENPOM 2026 COMPLETE PIPELINE FINISHED")