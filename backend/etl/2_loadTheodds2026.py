import requests
import sqlite3
import logging
import os
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
LOG_PATH = os.path.join(LOGS_DIR, "theodds_2026.log")

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
API_KEY = os.getenv("THEODDS_API_KEY")

if not API_KEY:
    raise ValueError("Missing THEODDS_API_KEY in environment variables or .env file")

logging.info("🚀 STARTING THE ODDS API 2026 DAILY PULL")
logging.info(f"API Key loaded: {API_KEY[:10]}...{API_KEY[-10:]}")

# ==============================================
# Configuration
# ==============================================

BASE_URL = "https://api.the-odds-api.com/v4"
SPORT_KEY = "basketball_ncaab"

# Ensure directories exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

# Database setup
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Configure datetime adapters to suppress Python 3.12+ deprecation warnings
# Store datetime without timezone since we're converting to EST
sqlite3.register_adapter(datetime, lambda dt: dt.replace(tzinfo=None).isoformat())
sqlite3.register_adapter(datetime.date, lambda d: d.isoformat())
sqlite3.register_converter("DATETIME", lambda b: datetime.fromisoformat(b.decode()))
sqlite3.register_converter("DATE", lambda b: datetime.fromisoformat(b.decode()).date())

# Create games2026 table if it doesn't exist
cursor.execute("""
CREATE TABLE IF NOT EXISTS games2026 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    load_datetime DATETIME,
    game_id TEXT UNIQUE,
    season TEXT DEFAULT '2026',
    commence_time DATETIME,
    game_date DATE,
    is_completed BOOLEAN DEFAULT 0,
    home_kpid INTEGER,
    away_kpid INTEGER,
    home_team TEXT,
    home_score INTEGER,
    away_team TEXT,
    away_score INTEGER,
    pt_diff INTEGER,
    pt_total INTEGER,
    fd_home_hhPrice INTEGER,
    fd_away_hhPrice INTEGER,
    fd_home_spread REAL,
    fd_home_spreadPrice INTEGER,
    fd_away_spread REAL,
    fd_away_spreadPrice INTEGER,
    fd_over REAL,
    fd_overPrice INTEGER,
    fd_under REAL,
    fd_underPrice INTEGER,
    dk_home_hhPrice INTEGER,
    dk_away_hhPrice INTEGER,
    dk_home_spread REAL,
    dk_home_spreadPrice INTEGER,
    dk_away_spread REAL,
    dk_away_spreadPrice INTEGER,
    dk_over REAL,
    dk_overPrice INTEGER,
    dk_under REAL,
    dk_underPrice INTEGER
)
""")
conn.commit()
logging.info("✅ Database table games2026 ready")

# ==============================================
# User Confirmation
# ==============================================

print(f"\n📅 Current Date: {datetime.now().strftime('%Y-%m-%d')}")
print(f"🏀 THE ODDS API 2026 DAILY PULL")

# Check existing data in games2026
cursor.execute("SELECT COUNT(*) FROM games2026")
total_games = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM games2026 WHERE is_completed = 1")
completed_games = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM games2026 WHERE is_completed = 0")
upcoming_games = cursor.fetchone()[0]

# Check for today's games (odds)
today = datetime.now().date()
cursor.execute("SELECT COUNT(*) FROM games2026 WHERE game_date = ?", (today,))
todays_games = cursor.fetchone()[0]

# Check for yesterday's games (scores)
yesterday = (datetime.now() - timedelta(days=1)).date()
cursor.execute("SELECT COUNT(*) FROM games2026 WHERE game_date = ?", (yesterday,))
yesterdays_games = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM games2026 WHERE game_date = ? AND is_completed = 1", (yesterday,))
yesterdays_completed = cursor.fetchone()[0]

print(f"\n📊 Current Database Status:")
print(f"  Total games in database: {total_games}")
print(f"  Completed games (with scores): {completed_games}")
print(f"  Upcoming games (odds only): {upcoming_games}")
print(f"  Today's games ({today}): {todays_games}")
print(f"  Yesterday's games ({yesterday}): {yesterdays_games} ({yesterdays_completed} completed)")

if todays_games > 0:
    print(f"\n⚠️  Today's odds already loaded")
if yesterdays_completed > 0:
    print(f"✅ Yesterday's scores already loaded")
if total_games == 0:
    print(f"\n🆕 No existing data - this will be the initial load")

response = input("\nDo you want to continue with the API pull? (y/n): ").lower().strip()
if response != 'y':
    print("❌ Script cancelled by user")
    conn.close()
    exit(0)

print("✅ Continuing with The Odds API pull...\n")

# Track API usage
total_requests = 0
usage_info = {}

def get_data(endpoint, params=None):
    """Generic GET request helper with usage tracking."""
    global total_requests, usage_info
    
    url = f"{BASE_URL}/{endpoint}"
    params = params or {}
    params["apiKey"] = API_KEY
    
    logging.info(f"🔹 Requesting: {endpoint}")
    logging.info(f"📋 Parameters: {params}")
    
    r = requests.get(url, params=params)
    total_requests += 1
    
    # Log usage info from headers
    if 'x-requests-remaining' in r.headers:
        remaining = r.headers['x-requests-remaining']
        used = r.headers.get('x-requests-used', 'unknown')
        last_cost = r.headers.get('x-requests-last', 'unknown')
        
        usage_info = {
            'remaining': remaining,
            'used': used,
            'last_cost': last_cost
        }
        
        logging.info(f"📊 API Usage - Used: {used}, Remaining: {remaining}, Last Cost: {last_cost}")
    
    r.raise_for_status()
    data = r.json()
    
    record_count = len(data) if isinstance(data, list) else "1 object"
    logging.info(f"✅ {endpoint} returned {record_count} records")
    
    return data

def get_team_kpid(team_name):
    """Get kpid for team from teamsMaster table."""
    cursor.execute("SELECT kpid FROM teamsMaster WHERE theoddsTeamName = ?", (team_name,))
    result = cursor.fetchone()
    return result[0] if result else None

def convert_to_est_and_game_date(utc_time_str):
    """Convert UTC time to EST and determine game date (before 4 AM = previous day)."""
    utc_time = datetime.fromisoformat(utc_time_str.replace('Z', '+00:00'))
    # Convert to EST (UTC-5, assuming standard time)
    est_time = utc_time - timedelta(hours=5)
    
    # If before 4 AM, consider it previous day's game
    if est_time.hour < 4:
        game_date = (est_time - timedelta(days=1)).date()
    else:
        game_date = est_time.date()
    
    return est_time, game_date

def extract_fanduel_odds(bookmakers, home_team):
    """Extract FanDuel odds from bookmakers data."""
    fd_data = {}
    for book in bookmakers:
        if book.get('key') == 'fanduel':
            for market in book.get('markets', []):
                if market['key'] == 'h2h':
                    for outcome in market['outcomes']:
                        if outcome['name'] == home_team:
                            fd_data['fd_home_hhPrice'] = outcome['price']
                        else:
                            fd_data['fd_away_hhPrice'] = outcome['price']
                elif market['key'] == 'spreads':
                    for outcome in market['outcomes']:
                        if outcome['name'] == home_team:
                            fd_data['fd_home_spread'] = outcome.get('point')
                            fd_data['fd_home_spreadPrice'] = outcome['price']
                        else:
                            fd_data['fd_away_spread'] = outcome.get('point')
                            fd_data['fd_away_spreadPrice'] = outcome['price']
                elif market['key'] == 'totals':
                    for outcome in market['outcomes']:
                        if outcome['name'] == 'Over':
                            fd_data['fd_over'] = outcome.get('point')
                            fd_data['fd_overPrice'] = outcome['price']
                        else:
                            fd_data['fd_under'] = outcome.get('point')
                            fd_data['fd_underPrice'] = outcome['price']
            break
    return fd_data

def extract_draftkings_odds(bookmakers, home_team):
    """Extract DraftKings odds from bookmakers data."""
    dk_data = {}
    for book in bookmakers:
        if book.get('key') == 'draftkings':
            for market in book.get('markets', []):
                if market['key'] == 'h2h':
                    for outcome in market['outcomes']:
                        if outcome['name'] == home_team:
                            dk_data['dk_home_hhPrice'] = outcome['price']
                        else:
                            dk_data['dk_away_hhPrice'] = outcome['price']
                elif market['key'] == 'spreads':
                    for outcome in market['outcomes']:
                        if outcome['name'] == home_team:
                            dk_data['dk_home_spread'] = outcome.get('point')
                            dk_data['dk_home_spreadPrice'] = outcome['price']
                        else:
                            dk_data['dk_away_spread'] = outcome.get('point')
                            dk_data['dk_away_spreadPrice'] = outcome['price']
                elif market['key'] == 'totals':
                    for outcome in market['outcomes']:
                        if outcome['name'] == 'Over':
                            dk_data['dk_over'] = outcome.get('point')
                            dk_data['dk_overPrice'] = outcome['price']
                        else:
                            dk_data['dk_under'] = outcome.get('point')
                            dk_data['dk_underPrice'] = outcome['price']
            break
    return dk_data

def main():
    logging.info("🚀 Starting The Odds API daily pull")
    logging.info(f"📅 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    total_records = 0
    
    # ==============================================
    # Pull and Load Odds Data
    # ==============================================
    
    try:
        logging.info("💰 Fetching current odds...")
        odds_params = {
            "regions": "us",
            "markets": "h2h,spreads,totals",
            "oddsFormat": "american",
            "dateFormat": "iso",
        }
        odds = get_data(f"sports/{SPORT_KEY}/odds", odds_params)
        
        # Process odds data
        odds_loaded = 0
        for game in odds:
            game_id = game['id']
            home_team = game['home_team']
            away_team = game['away_team']
            
            # Convert time and get game date
            est_time, game_date = convert_to_est_and_game_date(game['commence_time'])
            
            # Get team kpids
            home_kpid = get_team_kpid(home_team)
            away_kpid = get_team_kpid(away_team)
            
            # Extract odds
            fd_odds = extract_fanduel_odds(game.get('bookmakers', []), home_team)
            dk_odds = extract_draftkings_odds(game.get('bookmakers', []), home_team)
            
            # Check if game exists and is completed
            cursor.execute("SELECT is_completed FROM games2026 WHERE game_id = ?", (game_id,))
            existing = cursor.fetchone()
            
            if existing and existing[0] == 1:
                # Game is completed - skip odds update to preserve scores
                continue
            elif existing:
                # Game exists but not completed - update odds only
                cursor.execute("""
                UPDATE games2026 SET
                    load_datetime = ?, fd_home_hhPrice = ?, fd_away_hhPrice = ?,
                    fd_home_spread = ?, fd_home_spreadPrice = ?, fd_away_spread = ?, fd_away_spreadPrice = ?,
                    fd_over = ?, fd_overPrice = ?, fd_under = ?, fd_underPrice = ?,
                    dk_home_hhPrice = ?, dk_away_hhPrice = ?, dk_home_spread = ?, dk_home_spreadPrice = ?,
                    dk_away_spread = ?, dk_away_spreadPrice = ?, dk_over = ?, dk_overPrice = ?, dk_under = ?, dk_underPrice = ?
                WHERE game_id = ?
                """, (
                    datetime.now(),
                    fd_odds.get('fd_home_hhPrice'), fd_odds.get('fd_away_hhPrice'),
                    fd_odds.get('fd_home_spread'), fd_odds.get('fd_home_spreadPrice'),
                    fd_odds.get('fd_away_spread'), fd_odds.get('fd_away_spreadPrice'),
                    fd_odds.get('fd_over'), fd_odds.get('fd_overPrice'),
                    fd_odds.get('fd_under'), fd_odds.get('fd_underPrice'),
                    dk_odds.get('dk_home_hhPrice'), dk_odds.get('dk_away_hhPrice'),
                    dk_odds.get('dk_home_spread'), dk_odds.get('dk_home_spreadPrice'),
                    dk_odds.get('dk_away_spread'), dk_odds.get('dk_away_spreadPrice'),
                    dk_odds.get('dk_over'), dk_odds.get('dk_overPrice'),
                    dk_odds.get('dk_under'), dk_odds.get('dk_underPrice'),
                    game_id
                ))
            else:
                # New game - insert full record
                cursor.execute("""
                INSERT INTO games2026 (
                    load_datetime, game_id, season, commence_time, game_date,
                    home_team, away_team, home_kpid, away_kpid,
                    fd_home_hhPrice, fd_away_hhPrice, fd_home_spread, fd_home_spreadPrice,
                    fd_away_spread, fd_away_spreadPrice, fd_over, fd_overPrice,
                    fd_under, fd_underPrice, dk_home_hhPrice, dk_away_hhPrice,
                    dk_home_spread, dk_home_spreadPrice, dk_away_spread, dk_away_spreadPrice,
                    dk_over, dk_overPrice, dk_under, dk_underPrice
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    datetime.now(), game_id, '2026', est_time, game_date,
                    home_team, away_team, home_kpid, away_kpid,
                    fd_odds.get('fd_home_hhPrice'), fd_odds.get('fd_away_hhPrice'),
                    fd_odds.get('fd_home_spread'), fd_odds.get('fd_home_spreadPrice'),
                    fd_odds.get('fd_away_spread'), fd_odds.get('fd_away_spreadPrice'),
                    fd_odds.get('fd_over'), fd_odds.get('fd_overPrice'),
                    fd_odds.get('fd_under'), fd_odds.get('fd_underPrice'),
                    dk_odds.get('dk_home_hhPrice'), dk_odds.get('dk_away_hhPrice'),
                    dk_odds.get('dk_home_spread'), dk_odds.get('dk_home_spreadPrice'),
                    dk_odds.get('dk_away_spread'), dk_odds.get('dk_away_spreadPrice'),
                    dk_odds.get('dk_over'), dk_odds.get('dk_overPrice'),
                    dk_odds.get('dk_under'), dk_odds.get('dk_underPrice')
                ))
            odds_loaded += 1
        
        conn.commit()
        logging.info(f"📊 Loaded {odds_loaded} odds records into games2026")
        total_records += odds_loaded
        
    except Exception as e:
        logging.error(f"❌ Failed to pull/load odds: {e}")
    
    # ==============================================
    # Pull and Load Scores Data (Previous 2 Days)
    # ==============================================
    
    try:
        logging.info("📊 Fetching recent scores (1 day)...")
        scores_params = {"daysFrom": 2}
        scores = get_data(f"sports/{SPORT_KEY}/scores", scores_params)
        
        # Process scores data - only completed games (yesterday's games)
        scores_loaded = 0
        for game in scores:
            # Only process completed games
            if not game.get('completed', True):
                continue
                
            game_id = game['id']
            home_team = game['home_team']
            away_team = game['away_team']
            
            # Extract scores
            home_score = None
            away_score = None
            for score in game.get('scores', []):
                if score['name'] == home_team:
                    home_score = int(score['score'])
                elif score['name'] == away_team:
                    away_score = int(score['score'])
            
            # Calculate pt_diff and pt_total
            pt_diff = None
            pt_total = None
            if home_score is not None and away_score is not None:
                pt_diff = home_score - away_score
                pt_total = home_score + away_score
            
            # Check if game exists
            cursor.execute("SELECT id FROM games2026 WHERE game_id = ?", (game_id,))
            existing = cursor.fetchone()
            
            if existing:
                # Update existing record
                cursor.execute("""
                UPDATE games2026 
                SET is_completed = 1, home_score = ?, away_score = ?, pt_diff = ?, pt_total = ?
                WHERE game_id = ?
                """, (home_score, away_score, pt_diff, pt_total, game_id))
            else:
                # Create new record for completed game
                est_time, game_date = convert_to_est_and_game_date(game['commence_time'])
                home_kpid = get_team_kpid(home_team)
                away_kpid = get_team_kpid(away_team)
                
                cursor.execute("""
                INSERT INTO games2026 (
                    load_datetime, game_id, season, commence_time, game_date,
                    is_completed, home_team, away_team, home_kpid, away_kpid,
                    home_score, away_score, pt_diff, pt_total
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    datetime.now(), game_id, '2026', est_time, game_date,
                    1, home_team, away_team, home_kpid, away_kpid,
                    home_score, away_score, pt_diff, pt_total
                ))
            
            scores_loaded += 1
        
        conn.commit()
        logging.info(f"📊 Loaded {scores_loaded} scores records into games2026")
        total_records += scores_loaded
        
    except Exception as e:
        logging.error(f"❌ Failed to pull/load scores: {e}")
    
    # ==============================================
    # Final Summary
    # ==============================================
    
    # Get final counts
    cursor.execute("SELECT COUNT(*) FROM games2026")
    total_games = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM games2026 WHERE is_completed = 1")
    completed_games = cursor.fetchone()[0]
    
    logging.info(f"\n🎉 Daily pull complete!")
    logging.info(f"📊 Total records processed: {total_records}")
    logging.info(f"🔧 API requests made: {total_requests}")
    logging.info(f"🏀 Total games in database: {total_games}")
    logging.info(f"✅ Completed games: {completed_games}")
    logging.info(f"📁 Data saved to: {DB_PATH}")
    
    if usage_info:
        logging.info(f"\n💳 API Usage Summary:")
        logging.info(f"  Credits used this month: {usage_info.get('used', 'unknown')}")
        logging.info(f"  Credits remaining: {usage_info.get('remaining', 'unknown')}")
        logging.info(f"  Last request cost: {usage_info.get('last_cost', 'unknown')}")
    
    conn.close()
    logging.info("🏁 THE ODDS API 2026 DAILY PULL FINISHED")

if __name__ == "__main__":
    main()