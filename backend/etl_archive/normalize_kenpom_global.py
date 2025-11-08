import sqlite3
import logging
import numpy as np

# ==============================================
# Logging Setup
# ==============================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("normalize_kenpom_global.log"),
        logging.StreamHandler()
    ]
)

# ==============================================
# Setup
# ==============================================

DB_PATH = "data/master.db"
SOURCE_TABLE = "kenpom_raw"
TARGET_TABLE = "kenpom_cleaned_global"
SEASONS = [2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018]

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

logging.info("Starting KenPom global normalization")

# ==============================================
# Database Connection
# ==============================================

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# ==============================================
# Create Target Table
# ==============================================

# Drop existing table if it exists
cursor.execute(f"DROP TABLE IF EXISTS {TARGET_TABLE}")

# Get source table structure
cursor.execute(f"PRAGMA table_info({SOURCE_TABLE})")
columns = cursor.fetchall()

# Create target table with same structure
create_sql = f"CREATE TABLE {TARGET_TABLE} (\n"
for col in columns:
    col_name, col_type = col[1], col[2]
    if col_name == 'id':
        create_sql += f"    {col_name} INTEGER PRIMARY KEY AUTOINCREMENT,\n"
    else:
        create_sql += f"    {col_name} {col_type},\n"
create_sql = create_sql.rstrip(',\n') + "\n);"

cursor.execute(create_sql)
conn.commit()
logging.info(f"Created {TARGET_TABLE} table")

# ==============================================
# Get All Data and Calculate Global Stats
# ==============================================

# Get all records across all seasons
cursor.execute(f"SELECT * FROM {SOURCE_TABLE}")
all_records = cursor.fetchall()

logging.info(f"Found {len(all_records)} total records across all seasons")

# Get column names
cursor.execute(f"PRAGMA table_info({SOURCE_TABLE})")
col_info = cursor.fetchall()
col_names = [col[1] for col in col_info]

# Create dictionary mapping column names to indices
col_indices = {name: idx for idx, name in enumerate(col_names)}

# Calculate global statistics for each field
global_stats = {}
for field in STAT_FIELDS:
    if field in col_indices:
        col_idx = col_indices[field]
        values = [record[col_idx] for record in all_records if record[col_idx] is not None]
        
        # Invert if needed
        if field in INVERT_FIELDS:
            values = [-v for v in values]
            logging.info(f"Inverted {field} globally")
        
        if len(values) > 1:
            mean_val = np.mean(values)
            std_val = np.std(values, ddof=1)  # Sample standard deviation
            
            if std_val > 0:
                global_stats[field] = {
                    'mean': mean_val,
                    'std': std_val,
                    'count': len(values)
                }
                logging.info(f"{field}: mean={mean_val:.3f}, std={std_val:.3f}, n={len(values)}")
            else:
                logging.warning(f"{field} has zero standard deviation globally")
                global_stats[field] = {'mean': mean_val, 'std': 1.0, 'count': len(values)}
        else:
            logging.warning(f"Insufficient data for {field} globally")

logging.info("Global statistics calculated for all fields")

# ==============================================
# Process and Insert Normalized Records
# ==============================================

total_records = 0

for season in SEASONS:
    logging.info(f"Processing season {season}")
    
    # Get records for this season
    season_records = [record for record in all_records if record[col_indices['season']] == season]
    
    if not season_records:
        logging.warning(f"No records found for season {season}")
        continue
    
    logging.info(f"Processing {len(season_records)} records for season {season}")
    
    # Insert normalized records
    for record in season_records:
        new_record = list(record)
        
        # Normalize each stat field using global statistics
        for field in STAT_FIELDS:
            if field in col_indices and field in global_stats:
                col_idx = col_indices[field]
                original_value = record[col_idx]
                
                if original_value is not None:
                    # Apply inversion if needed
                    value = -original_value if field in INVERT_FIELDS else original_value
                    
                    # Z-score normalize using global stats
                    mean_val = global_stats[field]['mean']
                    std_val = global_stats[field]['std']
                    z_score = (value - mean_val) / std_val
                    
                    new_record[col_idx] = z_score
        
        # Insert record (excluding original id, let it auto-increment)
        placeholders = ",".join(["?"] * (len(new_record) - 1))
        insert_sql = f"""
            INSERT INTO {TARGET_TABLE} ({','.join(col_names[1:])})
            VALUES ({placeholders})
        """
        cursor.execute(insert_sql, new_record[1:])
    
    conn.commit()
    total_records += len(season_records)
    logging.info(f"Season {season} complete: {len(season_records)} records normalized and inserted")

# ==============================================
# Final Verification
# ==============================================

cursor.execute(f"SELECT COUNT(*) FROM {TARGET_TABLE}")
final_count = cursor.fetchone()[0]

logging.info(f"✅ Global normalization complete:")
logging.info(f"  Total records processed: {total_records}")
logging.info(f"  Records in {TARGET_TABLE}: {final_count}")

if final_count == total_records:
    logging.info("🎯 Perfect! All records successfully normalized")
else:
    logging.warning(f"⚠️  Mismatch: processed {total_records}, inserted {final_count}")

# Sample verification - should show overall mean ~0, but season means may vary
cursor.execute(f"""
    SELECT season, COUNT(*), 
           AVG(adjOffEff) as avg_off, AVG(adjDefEff) as avg_def
    FROM {TARGET_TABLE} 
    GROUP BY season 
    ORDER BY season
""")
sample_stats = cursor.fetchall()

logging.info("Sample verification by season (global normalization):")
for season, count, avg_off, avg_def in sample_stats:
    logging.info(f"  Season {season}: {count} records, avgOff={avg_off:.3f}, avgDef={avg_def:.3f}")

# Overall verification
cursor.execute(f"""
    SELECT AVG(adjOffEff) as overall_avg_off, AVG(adjDefEff) as overall_avg_def
    FROM {TARGET_TABLE}
""")
overall_avg = cursor.fetchone()
logging.info(f"Overall averages: Off={overall_avg[0]:.3f}, Def={overall_avg[1]:.3f} (should be ~0)")

conn.close()
logging.info("Database connection closed")