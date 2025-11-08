import sqlite3
import logging
import os

# ==============================================
# Logging Setup
# ==============================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("create_training_dataset.log"),
        logging.StreamHandler()
    ]
)

# ==============================================
# Setup
# ==============================================

SOURCE_DB = "data/master.db"
TARGET_DB = "data/training.db"
TARGET_TABLE = "setAlpha"

logging.info("Starting training dataset creation")

# ==============================================
# Create Training Database
# ==============================================

# Remove existing training.db if it exists
if os.path.exists(TARGET_DB):
    os.remove(TARGET_DB)
    logging.info("Removed existing training.db")

# Create new training database
training_conn = sqlite3.connect(TARGET_DB)
training_cursor = training_conn.cursor()

# Connect to source database
source_conn = sqlite3.connect(SOURCE_DB)
source_cursor = source_conn.cursor()

logging.info("Connected to databases")

# ==============================================
# Create setAlpha Table
# ==============================================

training_cursor.execute(f"""
CREATE TABLE {TARGET_TABLE} (
    id INTEGER PRIMARY KEY,
    home_id INTEGER,
    away_id INTEGER,
    is_home INTEGER,
    is_neutral INTEGER,
    date TEXT,
    season INTEGER,
    home_team TEXT,
    home_score INTEGER,
    away_team TEXT,
    away_score INTEGER,
    win_loss TEXT,
    pt_diff INTEGER,
    pt_total INTEGER,
    home_adjOffEff REAL,
    home_effFgPct REAL,
    home_adjDefEff REAL,
    home_defEffFgPct REAL,
    home_adjTempo REAL,
    home_threesPct REAL,
    home_threesRate REAL,
    home_ftRate REAL,
    home_ftPct REAL,
    home_defFtRate REAL,
    home_blockPct REAL,
    home_oppThreesPct REAL,
    home_oppThreesRate REAL,
    home_stlRate REAL,
    home_nonStlTrnvrRate REAL,
    home_offRebPct REAL,
    home_defRebPct REAL,
    home_astRate REAL,
    home_trnvrPct REAL,
    home_effHeight REAL,
    home_expRtg REAL,
    home_benchRtg REAL,
    home_contRtg REAL,
    away_adjOffEff REAL,
    away_effFgPct REAL,
    away_adjDefEff REAL,
    away_defEffFgPct REAL,
    away_adjTempo REAL,
    away_threesPct REAL,
    away_threesRate REAL,
    away_ftRate REAL,
    away_ftPct REAL,
    away_defFtRate REAL,
    away_blockPct REAL,
    away_oppThreesPct REAL,
    away_oppThreesRate REAL,
    away_stlRate REAL,
    away_nonStlTrnvrRate REAL,
    away_offRebPct REAL,
    away_defRebPct REAL,
    away_astRate REAL,
    away_trnvrPct REAL,
    away_effHeight REAL,
    away_expRtg REAL,
    away_benchRtg REAL,
    away_contRtg REAL
)
""")

training_conn.commit()
logging.info(f"Created {TARGET_TABLE} table")

# Attach source database to access its tables
training_cursor.execute(f"ATTACH DATABASE '{SOURCE_DB}' AS source")
logging.info("Attached source database")

# ==============================================
# Insert Training Data
# ==============================================

insert_sql = """
INSERT INTO setAlpha (
    id, home_id, away_id, is_home, is_neutral, date, season,
    home_team, home_score, away_team, away_score, win_loss, pt_diff, pt_total,
    home_adjOffEff, home_effFgPct, home_adjDefEff, home_defEffFgPct, home_adjTempo,
    home_threesPct, home_threesRate, home_ftRate, home_ftPct, home_defFtRate,
    home_blockPct, home_oppThreesPct, home_oppThreesRate, home_stlRate, home_nonStlTrnvrRate,
    home_offRebPct, home_defRebPct, home_astRate, home_trnvrPct, home_effHeight,
    home_expRtg, home_benchRtg, home_contRtg,
    away_adjOffEff, away_effFgPct, away_adjDefEff, away_defEffFgPct, away_adjTempo,
    away_threesPct, away_threesRate, away_ftRate, away_ftPct, away_defFtRate,
    away_blockPct, away_oppThreesPct, away_oppThreesRate, away_stlRate, away_nonStlTrnvrRate,
    away_offRebPct, away_defRebPct, away_astRate, away_trnvrPct, away_effHeight,
    away_expRtg, away_benchRtg, away_contRtg
)
SELECT 
    gc.id,
    gc.homeId,
    gc.awayId,
    CASE WHEN gc.site = 'Home' THEN 1 ELSE 0 END,
    CASE WHEN gc.site = 'Neutral' THEN 1 ELSE 0 END,
    gc.date,
    gc.season,
    kh.team,
    gc.pts,
    ka.team,
    gc.opp_pts,
    gc.w_l,
    (gc.pts - gc.opp_pts),
    (gc.pts + gc.opp_pts),
    kh.adjOffEff, kh.effFgPct, kh.adjDefEff, kh.defEffFgPct, kh.adjTempo,
    kh.threesPct, kh.threesRate, kh.ftRate, kh.ftPct, kh.defFtRate,
    kh.blockPct, kh.oppThreesPct, kh.oppThreesRate, kh.stlRate, kh.nonStlTrnvrRate,
    kh.offRebPct, kh.defRebPct, kh.astRate, kh.trnvrPct, kh.effHeight,
    kh.expRtg, kh.benchRtg, kh.contRtg,
    ka.adjOffEff, ka.effFgPct, ka.adjDefEff, ka.defEffFgPct, ka.adjTempo,
    ka.threesPct, ka.threesRate, ka.ftRate, ka.ftPct, ka.defFtRate,
    ka.blockPct, ka.oppThreesPct, ka.oppThreesRate, ka.stlRate, ka.nonStlTrnvrRate,
    ka.offRebPct, ka.defRebPct, ka.astRate, ka.trnvrPct, ka.effHeight,
    ka.expRtg, ka.benchRtg, ka.contRtg
FROM source.games_cleaned gc
JOIN source.kenpom_cleaned kh ON gc.homeId = kh.teamId AND gc.season = kh.season
JOIN source.kenpom_cleaned ka ON gc.awayId = ka.teamId AND gc.season = ka.season
"""

training_cursor.execute(insert_sql)

inserted_count = training_cursor.rowcount
training_conn.commit()

logging.info(f"Inserted {inserted_count} records into {TARGET_TABLE}")

# ==============================================
# Verification and Summary
# ==============================================

# Get source counts
source_cursor.execute("SELECT COUNT(*) FROM games_cleaned")
games_count = source_cursor.fetchone()[0]

source_cursor.execute("SELECT COUNT(*) FROM kenpom_cleaned")
kenpom_count = source_cursor.fetchone()[0]

# Get target count
training_cursor.execute(f"SELECT COUNT(*) FROM {TARGET_TABLE}")
training_count = training_cursor.fetchone()[0]

# Check for missing data
training_cursor.execute(f"""
SELECT COUNT(*) FROM {TARGET_TABLE} 
WHERE home_adjOffEff IS NULL OR away_adjOffEff IS NULL
""")
missing_stats = training_cursor.fetchone()[0]

# Sample verification
training_cursor.execute(f"""
SELECT season, COUNT(*) 
FROM {TARGET_TABLE} 
GROUP BY season 
ORDER BY season
""")
season_counts = training_cursor.fetchall()

# ==============================================
# Final Summary
# ==============================================

logging.info(f"✅ Training dataset creation complete:")
logging.info(f"  Source games_cleaned: {games_count} records")
logging.info(f"  Source kenpom_cleaned: {kenpom_count} records")
logging.info(f"  Training dataset: {training_count} records")
logging.info(f"  Records with missing stats: {missing_stats}")

if missing_stats == 0:
    logging.info("🎯 Perfect! No missing statistics")
else:
    logging.warning(f"⚠️  {missing_stats} records have missing KenPom statistics")

logging.info("Records by season:")
for season, count in season_counts:
    logging.info(f"  {season}: {count} games")

# Sample record verification
training_cursor.execute(f"SELECT * FROM {TARGET_TABLE} LIMIT 1")
sample = training_cursor.fetchone()
if sample:
    logging.info(f"Sample record ID {sample[0]}: {sample[7]} vs {sample[9]} on {sample[5]}")

source_conn.close()
training_conn.close()
logging.info(f"Training database saved to {TARGET_DB}")