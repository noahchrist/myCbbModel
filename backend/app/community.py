from fastapi import HTTPException
from supabase import Client
from typing import Optional

async def get_community_models(supabase: Client):
    """Get all community models sorted by ROI"""
    try:
        response = supabase.table('model_details').select('''
            model_id, model_name, user_id, created_datetime, betting_style, ten_digit,
            total_wl, total_units_bet, total_units_won, model_path
        ''').order('total_units_won', desc=True).execute()
        
        models = []
        for row in response.data:
            # Parse wins/losses from total_wl (format: "1-0")
            wins, losses = 0, 0
            if row.get('total_wl'):
                try:
                    wins, losses = map(int, row['total_wl'].split('-'))
                except:
                    wins, losses = 0, 0
            
            units_bet = row.get('total_units_bet', 0) or 0
            units_won = row.get('total_units_won', 0) or 0
            roi = (units_won / units_bet * 100) if units_bet > 0 else 0
            
            models.append({
                "id": row['model_id'],
                "modelName": row['model_name'],
                "userId": row.get('user_id'),
                "dateCreated": row['created_datetime'],
                "bettingStyle": row['betting_style'],
                "tenDigit": row['ten_digit'],
                "wins": wins,
                "losses": losses,
                "unitsBet": round(units_bet, 2),
                "unitsWon": round(units_won, 2),
                "roi": round(roi, 1),
                "isActive": row['model_path'] is not None
            })
        
        return {"models": models}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching community models: {str(e)}")

async def get_top_picks(supabase: Client, date: Optional[str] = None):
    """
    Get top community picks.
    TODO: Implement logic to store and retrieve pre-calculated top picks from database.
    Currently returns empty - will be overhauled to use stored picks.
    """
    # Placeholder - will implement proper top picks storage and retrieval
    return {"picks": [], "message": "Top picks calculation to be implemented"}
