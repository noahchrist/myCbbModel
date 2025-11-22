import os
import time
import sqlite3
import requests
import numpy as np
from datetime import datetime, timedelta
from dotenv import load_dotenv
from logger import get_logger

logger = get_logger("1_loadKenpom2026")

# ==============================================
# Setup
# ==============================================

load_dotenv()
API_KEY = os.getenv("KENPOM_API_KEY")
DB_PATH = os.getenv('DB_PATH')

if not API_KEY:
    raise ValueError("Missing KENPOM_API_KEY in environment variables or .env file")

if not DB_PATH:
    raise ValueError("Missing DB_PATH in environment variables or .env file")

BASE_URL = "https://kenpom.com"
SEASON = 2026
DELAY_BETWEEN_TEAMS = 0.1

# Table names
RAW_TABLE = "kenpom_raw_temp"
CLEANED_TABLE = "kenpom2026"

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

logger.info("Starting KenPom 2026 ETL...")

try:
    # ==============================================
    # Database Setup
    # ==============================================
    
    logger.info("Setting up database")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Drop temp and target tables if they exist
    cursor.execute(f"DROP TABLE IF EXISTS {RAW_TABLE}")
    cursor.execute(f"DROP TABLE IF EXISTS {CLEANED_TABLE}")
    logger.info("Dropped existing tables if present")
    
    # Create temp raw table
    logger.info(f"Creating temp table: {RAW_TABLE}")
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
    logger.info("Database setup complete")

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
            logger.error(f"HTTP {r.status_code} for {endpoint}")
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
    # Data Pull from KenPom API
    # ==============================================
    
    logger.info("Starting KenPom API data pull")
    logger.info(f"Pulling 2026 season data...")
    
    teams = get("teams", params={"y": SEASON})
    
    if not teams:
        logger.error("No teams found for 2026 season")
        conn.close()
        exit(1)
    
    team_list = teams if isinstance(teams, list) else teams.get("teams", [])
    logger.info(f"Found {len(team_list)} teams for {SEASON}")
    
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
            logger.error(f"Error processing {team_name}: {e}")
            fail_count += 1
    
        if i % 50 == 0 or i == len(team_list):
            logger.info(f"Progress: {i}/{len(team_list)} teams processed ({success_count} success, {fail_count} failed)")
        
        time.sleep(DELAY_BETWEEN_TEAMS)
    
    logger.info(f"API data pull finished")
    logger.info(f"{success_count} teams added successfully")
    logger.info(f"{fail_count} teams failed")

    # ==============================================
    # Data Validation
    # ==============================================
    
    logger.info("Starting data validation")
    
    # Verify all records have kpids
    cursor.execute(f"SELECT COUNT(*) FROM {RAW_TABLE} WHERE kpid IS NULL")
    null_kpids = cursor.fetchone()[0]
    
    if null_kpids > 0:
        logger.warning(f"{null_kpids} records have NULL kpids")
    else:
        logger.info("All records have valid kpids")
    
    logger.info("Data validation finished")

    # ==============================================
    # Normalization
    # ==============================================
    
    logger.info("Starting data normalization")

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
    logger.info(f"Created {CLEANED_TABLE} table")

    # Get all records for 2026 season
    cursor.execute(f"SELECT * FROM {RAW_TABLE} WHERE season = 2026")
    records = cursor.fetchall()
    
    if not records:
        logger.error("No 2026 records found for normalization")
        conn.close()
        exit(1)
    
    logger.info(f"Found {len(records)} records for normalization")

    # Get column names
    cursor.execute(f"PRAGMA table_info({RAW_TABLE})")
    col_info = cursor.fetchall()
    col_names = [col[1] for col in col_info]
    col_indices = {name: idx for idx, name in enumerate(col_names)}

    # Extract stat values for normalization
    logger.info("Calculating normalization statistics...")
    stat_data = {}
    for field in STAT_FIELDS:
        if field in col_indices:
            col_idx = col_indices[field]
            values = [record[col_idx] for record in records if record[col_idx] is not None]
            
            # Invert if needed
            if field in INVERT_FIELDS:
                values = [-v for v in values]
                logger.info(f"Inverted {field}")
            
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
                logger.warning(f"Zero std dev for {field}, using std=1.0")
    
    logger.info("Inserting normalized records...")
    current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Insert normalized records
    for i, record in enumerate(records, 1):
        if i % 50 == 0 or i == len(records):
            logger.info(f"Normalization progress: {i}/{len(records)} records processed")
        
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
    logger.info(f"Dropping temporary raw table: {RAW_TABLE}")
    cursor.execute(f"DROP TABLE {RAW_TABLE}")
    conn.commit()
    logger.info("Temporary raw table dropped")

    # ==============================================
    # Final Verification & Summary
    # ==============================================
    
    logger.info("Starting final verification")
    
    # Verification
    cursor.execute(f"SELECT COUNT(*) FROM {CLEANED_TABLE}")
    final_count = cursor.fetchone()[0]
    
    # Sample verification
    cursor.execute(f"SELECT AVG(adjOffEff), AVG(adjDefEff) FROM {CLEANED_TABLE}")
    avg_stats = cursor.fetchone()
    
    logger.info("Pipeline complete - final summary:")
    logger.info(f"Raw records processed: {len(records)}")
    logger.info(f"Cleaned records created: {final_count}")
    logger.info(f"Data validation complete")
    logger.info(f"Average normalized stats: Off={avg_stats[0]:.3f}, Def={avg_stats[1]:.3f}")
    logger.info(f"Final table: {CLEANED_TABLE}")
    logger.info(f"Load datetime: {current_datetime}")
    
    if final_count == len(records):
        logger.info("SUCCESS: All records processed successfully!")
    else:
        logger.warning("WARNING: Record count mismatch")
    
    conn.close()
    logger.info("KenPom 2026 complete pipeline finished")

except Exception:
    logger.error("KenPom ETL failed", exc_info=True)
    if 'conn' in locals():
        conn.close()