import sqlite3
import os
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

async def get_games_by_date(date: str) -> List[Dict[str, Any]]:
    """Get games for a specific date with FanDuel odds"""
    db_path = os.environ.get('DB_PATH') or os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'master.db'))
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = """
    SELECT 
        home_team,
        away_team,
        commence_time,
        home_score,
        away_score,
        pt_diff,
        pt_total,
        fd_home_hhPrice,
        fd_away_hhPrice,
        fd_home_spread,
        fd_home_spreadPrice,
        fd_away_spread,
        fd_away_spreadPrice,
        fd_over,
        fd_overPrice,
        fd_under,
        fd_underPrice
    FROM gamesMM
    WHERE game_date = ?
    ORDER BY commence_time ASC
    """
    
    cursor.execute(query, (date,))
    rows = cursor.fetchall()
    conn.close()
    
    games = []
    for row in rows:
        games.append({
            'home_team': row['home_team'],
            'away_team': row['away_team'],
            'commence_time': row['commence_time'],
            'home_score': row['home_score'],
            'away_score': row['away_score'],
            'pt_diff': row['pt_diff'],
            'pt_total': row['pt_total'],
            'fd_home_hhPrice': row['fd_home_hhPrice'],
            'fd_away_hhPrice': row['fd_away_hhPrice'],
            'fd_home_spread': row['fd_home_spread'],
            'fd_home_spreadPrice': row['fd_home_spreadPrice'],
            'fd_away_spread': row['fd_away_spread'],
            'fd_away_spreadPrice': row['fd_away_spreadPrice'],
            'fd_over': row['fd_over'],
            'fd_overPrice': row['fd_overPrice'],
            'fd_under': row['fd_under'],
            'fd_underPrice': row['fd_underPrice']
        })
    
    return games