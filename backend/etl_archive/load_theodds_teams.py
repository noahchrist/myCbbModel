import json
import sqlite3
import os

# Find the most recent participants file
data_dir = "data/raw_odds_snapshot"
participants_files = [f for f in os.listdir(data_dir) if f.startswith("participants_") and f.endswith(".json")]

if not participants_files:
    print("❌ No participants JSON files found")
    exit(1)

# Use the most recent file
latest_file = sorted(participants_files)[-1]
file_path = os.path.join(data_dir, latest_file)

print(f"📁 Loading data from: {latest_file}")

# Load JSON data
with open(file_path, 'r') as f:
    teams_data = json.load(f)

print(f"📊 Found {len(teams_data)} teams")

# Connect to database
conn = sqlite3.connect("data/future.db")
cursor = conn.cursor()

# Create table
cursor.execute("""
CREATE TABLE IF NOT EXISTS theodds_teams (
    id TEXT PRIMARY KEY,
    teamName TEXT,
    teamName_cleaned TEXT,
    teamId INTEGER
)
""")

# Clear existing data
cursor.execute("DELETE FROM theodds_teams")

# Insert teams
for team in teams_data:
    cursor.execute("""
        INSERT INTO theodds_teams (id, teamName, teamName_cleaned, teamId)
        VALUES (?, ?, ?, ?)
    """, (team['id'], team['full_name'], None, None))

conn.commit()

# Verify
cursor.execute("SELECT COUNT(*) FROM theodds_teams")
count = cursor.fetchone()[0]

print(f"✅ Loaded {count} teams into theodds_teams table")

conn.close()