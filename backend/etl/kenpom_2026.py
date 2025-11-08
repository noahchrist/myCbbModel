import os
import time
import sqlite3
import logging
import requests
import numpy as np
from datetime import datetime, timedelta
from dotenv import load_dotenv

# ==============================================
# Setup & Logging
# ==============================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/kenpom_2026_complete.log"),
        logging.StreamHandler()
    ]
)

load_dotenv()
API_KEY = os.getenv("KENPOM_API_KEY")

if not API_KEY:
    raise ValueError("Missing KENPOM_API_KEY in environment variables or .env file")

logging.info("🚀 STARTING KENPOM 2026 COMPLETE PIPELINE")
logging.info(f"API Key loaded: {API_KEY[:10]}...{API_KEY[-10:]}")

DB_PATH = "data/future.db"
BASE_URL = "https://kenpom.com"
SEASON = 2026
DELAY_BETWEEN_TEAMS = 0.2

# Generate table names with current date
current_date = datetime.now().strftime("%m%d%Y")
RAW_TABLE = f"kenpom_raw_{current_date}"
CLEANED_TABLE = f"kenpom_cleaned_{current_date}"

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
os.makedirs("data", exist_ok=True)
os.makedirs("logs", exist_ok=True)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Clean up old tables (older than 7 days)
logging.info("🧹 Cleaning up old tables...")
cutoff_date = datetime.now() - timedelta(days=7)
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'kenpom_raw_%' OR name LIKE 'kenpom_cleaned_%'")
existing_tables = cursor.fetchall()

cleaned_count = 0
for (table_name,) in existing_tables:
    try:
        if 'kenpom_raw_' in table_name:
            date_str = table_name.replace("kenpom_raw_", "")
        elif 'kenpom_cleaned_' in table_name:
            date_str = table_name.replace("kenpom_cleaned_", "")
        else:
            continue
            
        table_date = datetime.strptime(date_str, "%m%d%Y")
        if table_date < cutoff_date:
            cursor.execute(f"DROP TABLE {table_name}")
            cleaned_count += 1
            logging.info(f"  Dropped old table: {table_name}")
    except ValueError:
        continue

logging.info(f"✅ Cleaned up {cleaned_count} old tables")

# Drop today's tables if they exist (replace)
cursor.execute(f"DROP TABLE IF EXISTS {RAW_TABLE}")
cursor.execute(f"DROP TABLE IF EXISTS {CLEANED_TABLE}")

# Create today's raw table
logging.info(f"📊 Creating table: {RAW_TABLE}")
cursor.execute(f"""
CREATE TABLE {RAW_TABLE} (
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
            teamId, season, team, kpid, adjOffEff, adjDefEff, adjTempo,
            effFgPct, defEffFgPct, trnvrPct, ftRate, defFtRate, offRebPct, defRebPct,
            effHeight, expRtg, benchRtg, contRtg,
            threesPct, ftPct, blockPct, stlRate, nonStlTrnvrRate,
            astRate, threesRate, oppThreesPct, oppThreesRate
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
    
    if i % 50 == 0 or i == len(team_list):
        logging.info(f"📊 Progress: {i}/{len(team_list)} teams processed ({success_count} success, {fail_count} failed)")

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

    time.sleep(DELAY_BETWEEN_TEAMS)

logging.info(f"✅ STEP 2 COMPLETE: API data pull finished")
logging.info(f"  📊 {success_count} teams added successfully")
logging.info(f"  ❌ {fail_count} teams failed")

# ==============================================
# STEP 3: Team ID Matching
# ==============================================

logging.info("🔗 STEP 3: TEAM ID MATCHING")

# Get teams from teamsMaster that have 2026 season
cursor.execute("SELECT id, teamName, altNames FROM teamsMaster WHERE seasons LIKE '%2026%'")
teams_master = cursor.fetchall()

# Build lookup dictionary
team_lookup = {}
for team_id, team_name, alt_names in teams_master:
    team_lookup[team_name] = team_id
    
    if alt_names:
        alt_list = [name.strip() for name in alt_names.split(',')]
        for alt_name in alt_list:
            if alt_name:
                team_lookup[alt_name] = team_id

logging.info(f"🔍 Built lookup with {len(team_lookup)} name variations for {len(teams_master)} teams")

# Get teams from current kenpom table
cursor.execute(f"SELECT id, team FROM {RAW_TABLE} WHERE teamId IS NULL")
raw_teams = cursor.fetchall()

matched = 0
unmatched = []

for record_id, team_name in raw_teams:
    if team_name in team_lookup:
        cursor.execute(f"UPDATE {RAW_TABLE} SET teamId = ? WHERE id = ?", (team_lookup[team_name], record_id))
        matched += 1
    else:
        unmatched.append(team_name)

conn.commit()

logging.info(f"✅ STEP 3 COMPLETE: Team ID matching finished")
logging.info(f"  ✅ Matched: {matched} teams")
logging.info(f"  ❌ Unmatched: {len(unmatched)} teams")

if unmatched:
    logging.warning("Unmatched teams:")
    for team in unmatched:
        logging.warning(f"  - {team}")

# ==============================================
# STEP 4: Normalization
# ==============================================

logging.info("🔄 STEP 4: DATA NORMALIZATION")

# Get source table structure
cursor.execute(f"PRAGMA table_info({RAW_TABLE})")
columns = cursor.fetchall()

# Create target table with same structure
create_sql = f"CREATE TABLE {CLEANED_TABLE} (\n"
for col in columns:
    col_name, col_type = col[1], col[2]
    if col_name == 'id':
        create_sql += f"    {col_name} INTEGER PRIMARY KEY AUTOINCREMENT,\n"
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
    
    # Insert record (excluding original id, let it auto-increment)
    placeholders = ",".join(["?"] * (len(new_record) - 1))
    insert_sql = f"INSERT INTO {CLEANED_TABLE} ({','.join(col_names[1:])}) VALUES ({placeholders})"
    cursor.execute(insert_sql, new_record[1:])

conn.commit()

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
logging.info(f"  📊 Teams matched: {matched}/{len(kenpom_teams)}")
logging.info(f"  📊 Average normalized stats: Off={avg_stats[0]:.3f}, Def={avg_stats[1]:.3f}")
logging.info(f"  📁 Raw table: {RAW_TABLE}")
logging.info(f"  📁 Cleaned table: {CLEANED_TABLE}")

if final_count == len(records):
    logging.info("✅ SUCCESS: All records processed successfully!")
else:
    logging.warning(f"⚠️ WARNING: Record count mismatch")

conn.close()
logging.info("🏁 KENPOM 2026 COMPLETE PIPELINE FINISHED")