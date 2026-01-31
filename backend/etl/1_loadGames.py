import requests
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dbConnection import get_db_connection
from logger import get_logger

logger = get_logger("1_loadGames")

load_dotenv()

# Supabase games table schema:
# CREATE TABLE public.games (
#   game_id text NOT NULL UNIQUE,
#   created_datetime timestamp with time zone NOT NULL,
#   commence_datetime timestamp with time zone,
#   game_date date NOT NULL,
#   is_completed boolean,
#   home_kp_id integer,
#   away_kp_id integer,
#   home_team_name text,
#   home_score integer,
#   away_team_name text,
#   away_score integer,
#   pt_diff integer,
#   pt_total integer,
#   fd_home_hh_price integer,
#   fd_away_hh_price integer,
#   fd_home_spread numeric,
#   fd_home_spread_price integer,
#   fd_away_spread numeric,
#   fd_away_spread_price integer,
#   fd_over numeric,
#   fd_over_price integer,
#   fd_under numeric,
#   fd_under_price integer,
#   CONSTRAINT games_pkey PRIMARY KEY (game_id)
# );

API_KEY = os.getenv("THEODDS_API_KEY")
BASE_URL = "https://api.the-odds-api.com/v4"
SPORT_KEY = "basketball_ncaab"

logger.info("Starting The Odds API ETL...")

try:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    total_requests = 0
    usage_info = {}
    
    def get_data(endpoint, params=None):
        """Generic GET request helper with usage tracking."""
        global total_requests, usage_info
        
        url = f"{BASE_URL}/{endpoint}"
        params = params or {}
        params["apiKey"] = API_KEY
        
        logger.info(f"Requesting: {endpoint}")
        
        r = requests.get(url, params=params)
        total_requests += 1
        
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
        """Get kp_id for team from teams_master table."""
        cursor.execute("SELECT kp_id FROM teams_master WHERE theodds_team_name = %s", (team_name,))
        result = cursor.fetchone()
        return result[0] if result else None
    
    def get_game_date(utc_time_str):
        """Convert UTC time to game date (CST date, or previous day if before 5 AM CST)."""
        utc_time = datetime.fromisoformat(utc_time_str.replace('Z', '+00:00'))
        cst_time = utc_time.astimezone(ZoneInfo("America/Chicago"))
        
        # If before 5 AM CST, consider it previous day's game
        if cst_time.hour < 5:
            game_date = (cst_time - timedelta(days=1)).date()
        else:
            game_date = cst_time.date()
        
        return game_date
    
    def extract_fanduel_odds(bookmakers, home_team):
        """Extract FanDuel odds from bookmakers data."""
        fd_data = {}
        for book in bookmakers:
            if book.get('key') == 'fanduel':
                for market in book.get('markets', []):
                    if market['key'] == 'h2h':
                        for outcome in market['outcomes']:
                            if outcome['name'] == home_team:
                                fd_data['fd_home_hh_price'] = outcome['price']
                            else:
                                fd_data['fd_away_hh_price'] = outcome['price']
                    elif market['key'] == 'spreads':
                        for outcome in market['outcomes']:
                            if outcome['name'] == home_team:
                                fd_data['fd_home_spread'] = outcome.get('point')
                                fd_data['fd_home_spread_price'] = outcome['price']
                            else:
                                fd_data['fd_away_spread'] = outcome.get('point')
                                fd_data['fd_away_spread_price'] = outcome['price']
                    elif market['key'] == 'totals':
                        for outcome in market['outcomes']:
                            if outcome['name'] == 'Over':
                                fd_data['fd_over'] = outcome.get('point')
                                fd_data['fd_over_price'] = outcome['price']
                            else:
                                fd_data['fd_under'] = outcome.get('point')
                                fd_data['fd_under_price'] = outcome['price']
                break
        return fd_data
    
    # ==============================================
    # Data Pull - Odds
    # ==============================================
    
    logger.info("Starting odds data pull")
    
    odds_data = get_data(f"sports/{SPORT_KEY}/odds", {
        "regions": "us",
        "markets": "h2h,spreads,totals",
        "bookmakers": "fanduel",
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
            commence_time = game['commence_time']
            game_date = get_game_date(commence_time)
            
            home_kpid = get_team_kpid(home_team)
            away_kpid = get_team_kpid(away_team)
            
            fd_odds = extract_fanduel_odds(game.get('bookmakers', []), home_team)
            
            cursor.execute("""
                INSERT INTO games (
                    game_id, created_datetime, commence_datetime, game_date, is_completed,
                    home_kp_id, away_kp_id, home_team_name, away_team_name,
                    fd_home_hh_price, fd_away_hh_price, fd_home_spread, fd_home_spread_price,
                    fd_away_spread, fd_away_spread_price, fd_over, fd_over_price,
                    fd_under, fd_under_price
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (game_id) DO UPDATE SET
                    created_datetime = EXCLUDED.created_datetime,
                    commence_datetime = EXCLUDED.commence_datetime,
                    game_date = EXCLUDED.game_date,
                    home_kp_id = EXCLUDED.home_kp_id,
                    away_kp_id = EXCLUDED.away_kp_id,
                    home_team_name = EXCLUDED.home_team_name,
                    away_team_name = EXCLUDED.away_team_name,
                    fd_home_hh_price = EXCLUDED.fd_home_hh_price,
                    fd_away_hh_price = EXCLUDED.fd_away_hh_price,
                    fd_home_spread = EXCLUDED.fd_home_spread,
                    fd_home_spread_price = EXCLUDED.fd_home_spread_price,
                    fd_away_spread = EXCLUDED.fd_away_spread,
                    fd_away_spread_price = EXCLUDED.fd_away_spread_price,
                    fd_over = EXCLUDED.fd_over,
                    fd_over_price = EXCLUDED.fd_over_price,
                    fd_under = EXCLUDED.fd_under,
                    fd_under_price = EXCLUDED.fd_under_price
                WHERE games.is_completed = false
            """, (
                game_id, datetime.now(), commence_time, game_date, False,
                home_kpid, away_kpid, home_team, away_team,
                fd_odds.get('fd_home_hh_price'), fd_odds.get('fd_away_hh_price'),
                fd_odds.get('fd_home_spread'), fd_odds.get('fd_home_spread_price'),
                fd_odds.get('fd_away_spread'), fd_odds.get('fd_away_spread_price'),
                fd_odds.get('fd_over'), fd_odds.get('fd_over_price'),
                fd_odds.get('fd_under'), fd_odds.get('fd_under_price')
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
    
    scores_data = get_data(f"sports/{SPORT_KEY}/scores", {
        "daysFrom": 2
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
                
                cursor.execute("""
                    UPDATE games 
                    SET home_score = %s, away_score = %s, pt_diff = %s, pt_total = %s, is_completed = %s
                    WHERE game_id = %s
                """, (home_score, away_score, pt_diff, pt_total, True, game_id))
                
                if cursor.rowcount > 0:
                    scores_processed += 1
                else:
                    logger.info(f"Adding new completed game: {game_id}")
                    
                    home_kpid = get_team_kpid(home_team)
                    away_kpid = get_team_kpid(away_team)
                    game_date = get_game_date(game['commence_time'])
                    
                    cursor.execute("""
                        INSERT INTO games (
                            game_id, created_datetime, commence_datetime, game_date, is_completed,
                            home_kp_id, away_kp_id, home_team_name, away_team_name,
                            home_score, away_score, pt_diff, pt_total
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (game_id) DO UPDATE SET
                            game_date = EXCLUDED.game_date,
                            home_score = EXCLUDED.home_score,
                            away_score = EXCLUDED.away_score,
                            pt_diff = EXCLUDED.pt_diff,
                            pt_total = EXCLUDED.pt_total,
                            is_completed = EXCLUDED.is_completed
                    """, (
                        game_id, datetime.now(), game['commence_time'], game_date, True,
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
    
    cursor.execute("SELECT COUNT(*) FROM games")
    total_games = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM games WHERE is_completed = true")
    completed_games = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM games WHERE is_completed = false OR is_completed IS NULL")
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
    logger.info("The Odds API pipeline finished")

except Exception:
    logger.error("The Odds API ETL failed", exc_info=True)
    if 'conn' in locals():
        conn.close()
