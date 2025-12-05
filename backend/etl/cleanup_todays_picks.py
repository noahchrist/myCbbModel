import sqlite3
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from logger import get_logger

logger = get_logger("cleanup_todays_picks")

load_dotenv()
DB_PATH = os.environ.get('DB_PATH')

if not DB_PATH:
    raise ValueError("Missing DB_PATH in environment variables or .env file")

logger.info("Starting cleanup of today's picks...")

def cleanup_todays_picks():
    """Remove today's picks that don't meet betting style edge thresholds"""
    
    # Set specific date to clean up
    today = '2024-12-04'
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Edge thresholds by betting style
    edge_thresholds = {
        'Aggressive': 3.0,
        'Moderate': 4.0,
        'Reserved': 5.0
    }
    
    logger.info(f"Cleaning up picks for {today}")
    
    # Get all models with their betting styles
    cursor.execute("SELECT id, bettingStyle FROM modelDetails")
    models = cursor.fetchall()
    
    logger.info(f"Found {len(models)} models to process")
    
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
            logger.info(f"Model {model_id} ({betting_style}): Removed {removed_count} picks below {min_edge} edge")
    
    conn.commit()
    conn.close()
    
    logger.info(f"Total picks removed: {total_removed}")

def main():
    """Main function to cleanup today's picks"""
    logger.info("Starting cleanup of today's picks")
    
    try:
        cleanup_todays_picks()
        logger.info("Cleanup completed successfully")
    except Exception:
        logger.error("Cleanup failed", exc_info=True)
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    main()