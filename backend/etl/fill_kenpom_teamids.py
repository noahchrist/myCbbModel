import sqlite3
import logging

# ==============================================
# Logging Setup
# ==============================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("fill_kenpom_teamids.log"),
        logging.StreamHandler()
    ]
)

# ==============================================
# Database Connection
# ==============================================

conn = sqlite3.connect("data/master.db")
cursor = conn.cursor()

logging.info("Starting teamId assignment for kenpom_raw")

# ==============================================
# Get Teams Data
# ==============================================

# Get all teams from teamsMaster
cursor.execute("SELECT id, teamName, altNames FROM teamsMaster")
teams_master = cursor.fetchall()

# Build lookup dictionary
team_lookup = {}
for team_id, team_name, alt_names in teams_master:
    # Add primary team name
    team_lookup[team_name] = team_id
    
    # Add alternative names (split by comma and strip whitespace)
    if alt_names:
        alt_list = [name.strip() for name in alt_names.split(',')]
        for alt_name in alt_list:
            if alt_name:  # Skip empty strings
                team_lookup[alt_name] = team_id

logging.info(f"Built team lookup with {len(team_lookup)} name variations")

# ==============================================
# Update kenpom_raw teamId
# ==============================================

# Get all kenpom_raw records that need teamId assignment
cursor.execute("SELECT id, team FROM kenpom_raw WHERE teamId IS NULL")
kenpom_records = cursor.fetchall()

logging.info(f"Found {len(kenpom_records)} kenpom_raw records to process")

matched_count = 0
unmatched_count = 0
unmatched_teams = []

for record_id, team_name in kenpom_records:
    if team_name in team_lookup:
        team_id = team_lookup[team_name]
        cursor.execute("UPDATE kenpom_raw SET teamId = ? WHERE id = ?", (team_id, record_id))
        matched_count += 1
    else:
        unmatched_count += 1
        unmatched_teams.append(team_name)
        logging.warning(f"No match found for: {team_name}")

# Commit changes
conn.commit()

# ==============================================
# Summary
# ==============================================

logging.info(f"✓ Assignment complete:")
logging.info(f"  Matched teams: {matched_count}")
logging.info(f"  Unmatched teams: {unmatched_count}")

if unmatched_teams:
    logging.info(f"Unmatched teams: {set(unmatched_teams)}")

# Verification
cursor.execute("SELECT COUNT(*) FROM kenpom_raw WHERE teamId IS NULL")
remaining_null = cursor.fetchone()[0]
logging.info(f"Records still with NULL teamId: {remaining_null}")

conn.close()
logging.info("Database connection closed")