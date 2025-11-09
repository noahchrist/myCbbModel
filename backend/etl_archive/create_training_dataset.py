import sqlite3
import os

# ==============================================
# Setup
# ==============================================

DB_PATH = "./data/master.db"
TARGET_TABLE = "setAlpha"

print("Starting training dataset creation")

# ==============================================
# Create Training Database
# ==============================================

# Connect to master database
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Drop setAlpha table if it exists
cursor.execute("DROP TABLE IF EXISTS setAlpha")
conn.commit()
print("Dropped existing setAlpha table if it existed")

print("Connected to master database")

# ==============================================
# Create setAlpha Table
# ==============================================

cursor.execute(f"""
CREATE TABLE {TARGET_TABLE} (
    id INTEGER PRIMARY KEY,
    home_kpid INTEGER,
    away_kpid INTEGER,
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

conn.commit()
print(f"Created {TARGET_TABLE} table")

print("Ready to insert data")

# ==============================================
# Insert Training Data
# ==============================================

insert_sql = """
INSERT INTO setAlpha (
    id, home_kpid, away_kpid, is_home, is_neutral, date, season,
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
FROM games_cleaned gc
JOIN kenpom_cleaned kh ON gc.homeId = kh.kpid AND gc.season = kh.season
JOIN kenpom_cleaned ka ON gc.awayId = ka.kpid AND gc.season = ka.season
"""

print("Starting data insertion...")



cursor.execute(insert_sql)
inserted_count = cursor.rowcount
conn.commit()

print(f"✅ Inserted {inserted_count} records into {TARGET_TABLE}")

# ==============================================
# Verification and Summary
# ==============================================

# Get source counts
cursor.execute("SELECT COUNT(*) FROM games_cleaned")
games_count = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM kenpom_cleaned")
kenpom_count = cursor.fetchone()[0]

# Get target count
cursor.execute(f"SELECT COUNT(*) FROM {TARGET_TABLE}")
training_count = cursor.fetchone()[0]

# Check for missing data
cursor.execute(f"""
SELECT COUNT(*) FROM {TARGET_TABLE} 
WHERE home_adjOffEff IS NULL OR away_adjOffEff IS NULL
""")
missing_stats = cursor.fetchone()[0]

# Sample verification
cursor.execute(f"""
SELECT season, COUNT(*) 
FROM {TARGET_TABLE} 
GROUP BY season 
ORDER BY season
""")
season_counts = cursor.fetchall()

# ==============================================
# Final Summary
# ==============================================

print(f"✅ Training dataset creation complete:")
print(f"  Source games_cleaned: {games_count} records")
print(f"  Source kenpom_cleaned: {kenpom_count} records")
print(f"  Training dataset: {training_count} records")
print(f"  Records with missing stats: {missing_stats}")

if missing_stats == 0:
    print("🎯 Perfect! No missing statistics")
else:
    print(f"⚠️  {missing_stats} records have missing KenPom statistics")

print("Records by season:")
for season, count in season_counts:
    print(f"  {season}: {count} games")

# Sample record verification
cursor.execute(f"SELECT * FROM {TARGET_TABLE} LIMIT 1")
sample = cursor.fetchone()
if sample:
    print(f"Sample record ID {sample[0]}: {sample[7]} vs {sample[9]} on {sample[5]}")

conn.close()
print(f"Training dataset created in {DB_PATH}")