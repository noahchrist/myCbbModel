import sqlite3
import logging

# ==============================================
# Logging Setup
# ==============================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("clean_games.log"),
        logging.StreamHandler()  # Console output
    ]
)

# ==============================================
# Setup
# ==============================================

DB_PATH = "data/master.db"
SOURCE_TABLE = "games_raw"
TARGET_TABLE = "games_cleaned"
SEASONS = [2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018]

logging.info(f"Starting game deduplication for seasons {SEASONS}")

# ==============================================
# User Prompt for Table Drop
# ==============================================

user_input = input("Drop existing games_cleaned table and start fresh? (yes/no): ").strip().lower()
if user_input == 'yes':
    drop_table = True
    logging.info("User chose to drop existing table")
else:
    drop_table = False
    logging.info("User chose to keep existing table")

# ==============================================
# Database Connection
# ==============================================

try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    logging.info("Database connection established")
except sqlite3.Error as e:
    logging.error(f"Database connection failed: {e}")
    raise

# ==============================================
# Create Target Table
# ==============================================

if drop_table:
    cursor.execute(f"DROP TABLE IF EXISTS {TARGET_TABLE}")
    logging.info(f"Dropped existing {TARGET_TABLE} table")

# First, get the structure of the source table
cursor.execute(f"PRAGMA table_info({SOURCE_TABLE})")
columns = cursor.fetchall()

# Build CREATE TABLE statement with id as primary key and team ID fields
create_sql = f"CREATE TABLE IF NOT EXISTS {TARGET_TABLE} (\n    id INTEGER PRIMARY KEY AUTOINCREMENT,\n    homeId INTEGER,\n    awayId INTEGER,\n"
for col in columns:
    col_name, col_type = col[1], col[2]
    create_sql += f"    {col_name} {col_type},\n"
create_sql = create_sql.rstrip(',\n') + "\n);"

cursor.execute(create_sql)
conn.commit()
logging.info(f"Created/verified {TARGET_TABLE} table")

# Get column names for processing
cursor.execute(f"PRAGMA table_info({SOURCE_TABLE})")
column_info = cursor.fetchall()
column_names = [col[1] for col in column_info]
logging.info(f"Column names: {column_names}")

# Build team lookups once
cursor.execute("SELECT team_name, id FROM homeTeams")
home_team_lookup = dict(cursor.fetchall())
logging.info(f"Built home team lookup with {len(home_team_lookup)} teams")

cursor.execute("SELECT team_name, id FROM awayTeams")
away_team_lookup = dict(cursor.fetchall())
logging.info(f"Built away team lookup with {len(away_team_lookup)} teams")

# ==============================================
# Process Each Season
# ==============================================

for season in SEASONS:
    logging.info(f"\n===== Processing season {season} =====")
    
    # Get games for this season
    cursor.execute(f"""
        SELECT * FROM {SOURCE_TABLE} 
        WHERE season = ?
        ORDER BY date, team_name, opp_name
    """, (season,))
    
    games = cursor.fetchall()
    logging.info(f"Found {len(games)} total games for {season} season")
    
    if not games:
        logging.warning(f"No games found for {season}, skipping")
        continue
    
    # Get teams that have data for this season in teamsMaster
    cursor.execute("SELECT id FROM teamsMaster WHERE seasons LIKE ?", (f"%{season}%",))
    valid_team_ids = {row[0] for row in cursor.fetchall()}
    logging.info(f"Found {len(valid_team_ids)} teams with data for {season} season")
    
    # Pre-process games with team IDs
    processed_games_data = []
    skipped_games = 0
    
    for game in games:
        game_dict = dict(zip(column_names, game))
        
        team_name = game_dict['team_name']
        opp_name = game_dict['opp_name']
        
        home_team_id = home_team_lookup.get(team_name)
        away_team_id = away_team_lookup.get(opp_name)
        
        if not home_team_id or not away_team_id:
            skipped_games += 1
            continue
        
        # Check if both teams have data for this season in teamsMaster
        if home_team_id not in valid_team_ids or away_team_id not in valid_team_ids:
            skipped_games += 1
            continue
        
        # Skip games with null scores
        pts = game_dict.get('pts')
        opp_pts = game_dict.get('opp_pts')
        if pts is None or opp_pts is None:
            skipped_games += 1
            continue
        
        processed_games_data.append({
            'game': game,
            'game_dict': game_dict,
            'home_id': home_team_id,
            'away_id': away_team_id,
            'date': game_dict['date'],
            'pts': pts,
            'opp_pts': opp_pts,
            'w_l': game_dict.get('W_L') or game_dict.get('w_l') or game_dict.get('WL')
        })
    
    # Deduplication logic
    processed_games = set()
    unique_games = []
    duplicates_removed = 0
    
    for game_data in processed_games_data:
        # Create normalized game key (sorted team IDs)
        teams_sorted = tuple(sorted([game_data['home_id'], game_data['away_id']]))
        scores_sorted = tuple(sorted([game_data['pts'], game_data['opp_pts']]))
        game_key = (game_data['date'], teams_sorted, scores_sorted)
        
        if game_key in processed_games:
            duplicates_removed += 1
            continue
        
        processed_games.add(game_key)
        # Add homeId and awayId to the game data
        game_with_ids = (game_data['home_id'], game_data['away_id']) + game_data['game']
        unique_games.append(game_with_ids)
    
    # Insert unique games
    if unique_games:
        # Build INSERT statement (including homeId and awayId columns)
        all_columns = ['homeId', 'awayId'] + column_names
        placeholders = ",".join(["?"] * len(all_columns))
        insert_sql = f"""
            INSERT INTO {TARGET_TABLE} ({','.join(all_columns)})
            VALUES ({placeholders})
        """
        
        cursor.executemany(insert_sql, unique_games)
        conn.commit()
    
    # Season summary
    logging.info(f"🏀 Season {season} COMPLETE:")
    logging.info(f"  Original games: {len(games)}")
    logging.info(f"  Skipped games (no team/season data): {skipped_games}")
    logging.info(f"  Duplicates removed: {duplicates_removed}")
    logging.info(f"  Unique games added: {len(unique_games)}")
    logging.info(f"  Deduplication ratio: {duplicates_removed/len(games)*100:.1f}% removed")

# ==============================================
# Final Verification
# ==============================================

total_records = 0
for season in SEASONS:
    cursor.execute(f"SELECT COUNT(*) FROM {TARGET_TABLE} WHERE season = ?", (season,))
    season_count = cursor.fetchone()[0]
    total_records += season_count
    logging.info(f"Season {season}: {season_count} records")

logging.info(f"\n🎯 FINAL SUMMARY:")
logging.info(f"  Total records in {TARGET_TABLE}: {total_records}")
logging.info(f"  Seasons processed: {len(SEASONS)}")

conn.close()
logging.info("\n✅ All seasons complete! Database connection closed.")