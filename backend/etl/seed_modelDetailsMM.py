"""
One-time migration script: create MM tables and seed modelDetailsMM with
all active models (reset performance counters to 0-0).

Run once before deploying the MM pipeline:
    python seed_modelDetailsMM.py
"""

import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()
DB_PATH = os.environ.get('DB_PATH')

if not DB_PATH:
    raise ValueError("Missing DB_PATH in environment variables or .env file")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# ----------------------------------------------------------
# Create MM tables
# ----------------------------------------------------------

cursor.execute("""
CREATE TABLE IF NOT EXISTS modelDetailsMM (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    userId TEXT, modelName TEXT, dateCreated DATETIME,
    modelSeed INTEGER UNIQUE, modelPath TEXT, bettingStyle TEXT, tenDigit INTEGER,
    weightGenOff INTEGER, weightGenDef INTEGER, weightPace INTEGER,
    weightThrees INTEGER, weightFts INTEGER, weightPerDef INTEGER,
    weightIntDef INTEGER, weightBoards INTEGER, weightPlaymaking INTEGER,
    weightIntangibles INTEGER,
    w_l_overall TEXT, unitsBetOverall REAL, unitsWonOverall REAL,
    FOREIGN KEY (userId) REFERENCES users(id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS modelPredictionsMM (
    predictionId INTEGER PRIMARY KEY AUTOINCREMENT,
    datePredicted DATE, modelId INTEGER, game_id TEXT, game_date DATE,
    is_completed BOOLEAN, home_team TEXT, home_score INTEGER,
    away_team TEXT, away_score INTEGER, pt_diff REAL,
    fd_home_spread REAL, fd_home_spreadPrice INTEGER,
    fd_away_spread REAL, fd_away_spreadPrice INTEGER,
    predicted_pt_diff REAL, edge REAL, unitsBet REAL, unitsWon REAL,
    w_l TEXT, summary TEXT, bet_type TEXT,
    fd_over REAL, fd_overPrice INTEGER, fd_under REAL, fd_underPrice INTEGER,
    predicted_pt_total REAL, pt_total INTEGER,
    FOREIGN KEY (modelId) REFERENCES modelDetailsMM(id),
    FOREIGN KEY (game_id) REFERENCES gamesMM(game_id)
)
""")

conn.commit()
print("MM tables created (idempotent)")

# ----------------------------------------------------------
# Seed modelDetailsMM from modelDetails (active models only)
# ----------------------------------------------------------

cursor.execute("""
    SELECT id, userId, modelName, dateCreated, modelSeed, modelPath, bettingStyle, tenDigit,
           weightGenOff, weightGenDef, weightPace, weightThrees, weightFts,
           weightPerDef, weightIntDef, weightBoards, weightPlaymaking, weightIntangibles
    FROM modelDetails
    WHERE modelPath IS NOT NULL
""")
active_models = cursor.fetchall()

inserted = 0
skipped = 0

for row in active_models:
    (model_id, user_id, model_name, date_created, model_seed, model_path, betting_style, ten_digit,
     w_gen_off, w_gen_def, w_pace, w_threes, w_fts,
     w_per_def, w_int_def, w_boards, w_playmaking, w_intangibles) = row

    cursor.execute("""
        INSERT OR IGNORE INTO modelDetailsMM
        (id, userId, modelName, dateCreated, modelSeed, modelPath, bettingStyle, tenDigit,
         weightGenOff, weightGenDef, weightPace, weightThrees, weightFts,
         weightPerDef, weightIntDef, weightBoards, weightPlaymaking, weightIntangibles,
         w_l_overall, unitsBetOverall, unitsWonOverall)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '0-0', 0, 0)
    """, (
        model_id, user_id, model_name, date_created, model_seed, model_path, betting_style, ten_digit,
        w_gen_off, w_gen_def, w_pace, w_threes, w_fts,
        w_per_def, w_int_def, w_boards, w_playmaking, w_intangibles
    ))

    if cursor.rowcount > 0:
        inserted += 1
    else:
        skipped += 1

conn.commit()
conn.close()

print(f"Seeded {inserted} models into modelDetailsMM ({skipped} already existed)")
print("Verify with:")
print("  SELECT COUNT(*), SUM(unitsBetOverall), SUM(unitsWonOverall) FROM modelDetailsMM;")
print("  -- Expect: rows=active model count, unitsBet=0, unitsWon=0")
