from typing import List, Dict, Any
from supabase import Client

async def get_games_by_date(date: str, supabase: Client) -> List[Dict[str, Any]]:
    """Get games for a specific date with FanDuel odds"""
    
    response = supabase.table('games').select('*').eq('game_date', date).order('commence_datetime').execute()
    
    games = []
    for row in response.data:
        games.append({
            'home_team': row['home_team_name'],
            'away_team': row['away_team_name'],
            'commence_time': row['commence_datetime'],
            'home_score': row['home_score'],
            'away_score': row['away_score'],
            'pt_diff': row['pt_diff'],
            'pt_total': row['pt_total'],
            'fd_home_hhPrice': row['fd_home_hh_price'],
            'fd_away_hhPrice': row['fd_away_hh_price'],
            'fd_home_spread': row['fd_home_spread'],
            'fd_home_spreadPrice': row['fd_home_spread_price'],
            'fd_away_spread': row['fd_away_spread'],
            'fd_away_spreadPrice': row['fd_away_spread_price'],
            'fd_over': row['fd_over'],
            'fd_overPrice': row['fd_over_price'],
            'fd_under': row['fd_under'],
            'fd_underPrice': row['fd_under_price']
        })
    
    return games