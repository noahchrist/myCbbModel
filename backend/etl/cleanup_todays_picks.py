import sqlite3
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()
DB_PATH = os.environ.get('DB_PATH')

if not DB_PATH:
    raise ValueError("Missing DB_PATH in environment variables or .env file")

def cleanup_todays_picks():
    """Remove today's picks that don't meet betting style edge thresholds"""
    
    # Get today's date in Eastern time
    eastern = ZoneInfo("America/New_York")
    today = datetime.now(eastern).strftime('%Y-%m-%d')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Edge thresholds by betting style
    edge_thresholds = {
        'Aggressive': 3.0,
        'Moderate': 4.0,
        'Reserved': 5.0
    }
    
    print(f"Cleaning up picks for {today}")
    
    # Get all models with their betting styles
    cursor.execute("SELECT id, bettingStyle FROM modelDetails")
    models = cursor.fetchall()
    
    total_removed = 0
    
    for model_id, betting_style in models:
        min_edge = edge_thresholds.get(betting_style, 4.0)
        
        # Get today's picks for this model that don't meet threshold
        cursor.execute("""
            SELECT predictionId, edge FROM modelPredictions 
            WHERE modelId = ? AND datePredicted = ? AND edge < ?
        """, (model_id, today, min_edge))
        
        picks_to_remove = cursor.fetchall()
        
        if picks_to_remove:
            # Remove picks that don't meet threshold
            cursor.execute("""
                DELETE FROM modelPredictions 
                WHERE modelId = ? AND datePredicted = ? AND edge < ?
            """, (model_id, today, min_edge))
            
            removed_count = len(picks_to_remove)
            total_removed += removed_count
            print(f"Model {model_id} ({betting_style}): Removed {removed_count} picks below {min_edge} edge")
    
    conn.commit()
    conn.close()
    
    print(f"Total picks removed: {total_removed}")

if __name__ == "__main__":
    cleanup_todays_picks()