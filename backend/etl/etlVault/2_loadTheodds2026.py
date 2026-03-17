import requests
import sqlite3
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from logger import get_logger

logger = get_logger("2_loadTheodds2026")

# ==============================================
# Setup
# ==============================================

load_dotenv()
API_KEY = os.getenv("THEODDS_API_KEY")
DB_PATH = os.environ.get('DB_PATH')

if not API_KEY:
    raise ValueError("Missing THEODDS_API_KEY in environment variables or .env file")

if not DB_PATH:
    raise ValueError("Missing DB_PATH in environment variables or .env file")

BASE_URL = "https://api.the-odds-api.com/v4"
SPORT_KEY = "basketball_ncaab"

logger.info("Starting The Odds API 2026 ETL...")

try:
    # ==============================================
    # Database Setup
    # ==============================================
    
    logger.info("Setting up database")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Configure datetime adapters to suppress Python 3.12+ deprecation warnings
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
    logger.info("Database table games2026 ready")
    
    # Track API usage
    total_requests = 0
    usage_info = {}
    
    def get_data(endpoint, params=None):
        """Generic GET request helper with usage tracking."""
        global total_requests, usage_info
        
        url = f"{BASE_URL}/{endpoint}"
        params = params or {}
        params["apiKey"] = API_KEY
        
        logger.info(f"Requesting: {endpoint}")
        logger.info(f"Parameters: {params}")
        
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
            
            logger.info(f"API Usage - Used: {used}, Remaining: {remaining}, Last Cost: {last_cost}")
        
        r.raise_for_status()
        data = r.json()
        
        record_count = len(data) if isinstance(data, list) else "1 object"
        logger.info(f"{endpoint} returned {record_count} records")
        
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
    
    # ==============================================
    # Data Pull - Odds
    # ==============================================
    
    logger.info("Starting odds data pull")
    
    # Get odds data
    odds_data = get_data(f"sports/{SPORT_KEY}/odds", {
        "regions": "us",
        "markets": "h2h,spreads,totals",
        "bookmakers": "fanduel,draftkings",
        "oddsFormat": "american"
    })
    
    logger.info(f"Processing {len(odds_data)} games with odds")
    
    odds_processed = 0
    odds_errors = 0
    
    for game in odds_data:
        try:
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
            
            # Insert or update game
            cursor.execute("""
                INSERT OR REPLACE INTO games2026 (
                    load_datetime, game_id, commence_time, game_date,
                    home_kpid, away_kpid, home_team, away_team,
                    fd_home_hhPrice, fd_away_hhPrice, fd_home_spread, fd_home_spreadPrice,
                    fd_away_spread, fd_away_spreadPrice, fd_over, fd_overPrice,
                    fd_under, fd_underPrice, dk_home_hhPrice, dk_away_hhPrice,
                    dk_home_spread, dk_home_spreadPrice, dk_away_spread, dk_away_spreadPrice,
                    dk_over, dk_overPrice, dk_under, dk_underPrice
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now(ZoneInfo("America/New_York")), game_id, est_time, game_date,
                home_kpid, away_kpid, home_team, away_team,
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
            
            odds_processed += 1
            
        except Exception as e:
            logger.error(f"Error processing odds for game {game.get('id', 'unknown')}: {e}")
            odds_errors += 1
    
    conn.commit()
    logger.info(f"Odds processing complete: {odds_processed} processed, {odds_errors} errors")
    
    # ==============================================
    # Data Pull - Scores
    # ==============================================
    
    logger.info("Starting scores data pull")
    
    # Get scores data
    scores_data = get_data(f"sports/{SPORT_KEY}/scores", {
        "daysFrom": 3
    })
    
    logger.info(f"Processing {len(scores_data)} games with scores")
    
    scores_processed = 0
    scores_errors = 0
    
    for game in scores_data:
        try:
            if not game.get('completed'):
                continue
                
            game_id = game['id']
            home_team = game['home_team']
            away_team = game['away_team']
            
            # Get scores
            home_score = None
            away_score = None
            
            for score in game.get('scores', []):
                if score['name'] == home_team:
                    home_score = score['score']
                elif score['name'] == away_team:
                    away_score = score['score']
            
            if home_score is not None and away_score is not None:
                pt_diff = int(home_score) - int(away_score)
                pt_total = int(home_score) + int(away_score)
                
                # Update existing game with scores
                cursor.execute("""
                    UPDATE games2026 
                    SET home_score = ?, away_score = ?, pt_diff = ?, pt_total = ?, is_completed = 1
                    WHERE game_id = ?
                """, (home_score, away_score, pt_diff, pt_total, game_id))
                
                if cursor.rowcount > 0:
                    scores_processed += 1
                else:
                    # Game doesn't exist, insert it with scores
                    logger.info(f"Adding new completed game: {game_id}")
                    
                    # Convert time and get game date
                    est_time, game_date = convert_to_est_and_game_date(game['commence_time'])
                    
                    # Get team kpids
                    home_kpid = get_team_kpid(home_team)
                    away_kpid = get_team_kpid(away_team)
                    
                    cursor.execute("""
                        INSERT INTO games2026 (
                            load_datetime, game_id, commence_time, game_date, is_completed,
                            home_kpid, away_kpid, home_team, away_team,
                            home_score, away_score, pt_diff, pt_total
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        datetime.now(ZoneInfo("America/New_York")), game_id, est_time, game_date, 1,
                        home_kpid, away_kpid, home_team, away_team,
                        home_score, away_score, pt_diff, pt_total
                    ))
                    
                    scores_processed += 1
            
        except Exception as e:
            logger.error(f"Error processing scores for game {game.get('id', 'unknown')}: {e}")
            scores_errors += 1
    
    conn.commit()
    logger.info(f"Scores processing complete: {scores_processed} processed, {scores_errors} errors")
    
    # ==============================================
    # Final Summary
    # ==============================================
    
    logger.info("Starting final verification")
    
    # Get final counts
    cursor.execute("SELECT COUNT(*) FROM games2026")
    total_games = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM games2026 WHERE is_completed = 1")
    completed_games = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM games2026 WHERE is_completed = 0")
    upcoming_games = cursor.fetchone()[0]
    
    logger.info("Pipeline complete - final summary:")
    logger.info(f"Total API requests made: {total_requests}")
    logger.info(f"Odds processed: {odds_processed}")
    logger.info(f"Scores processed: {scores_processed}")
    logger.info(f"Total games in database: {total_games}")
    logger.info(f"Completed games: {completed_games}")
    logger.info(f"Upcoming games: {upcoming_games}")
    
    if usage_info:
        logger.info(f"API usage remaining: {usage_info.get('remaining', 'unknown')}")
    
    conn.close()
    logger.info("The Odds API 2026 pipeline finished")

except Exception:
    logger.error("The Odds API ETL failed", exc_info=True)
    if 'conn' in locals():
        conn.close()