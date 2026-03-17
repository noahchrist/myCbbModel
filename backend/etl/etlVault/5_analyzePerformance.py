import sqlite3
import os
from datetime import datetime
from dotenv import load_dotenv
from logger import get_logger

logger = get_logger("5_analyzePerformance")

# ==============================================
# Setup
# ==============================================

load_dotenv()
DB_PATH = os.environ.get('DB_PATH')

if not DB_PATH:
    raise ValueError("Missing DB_PATH in environment variables or .env file")

logger.info("Starting Analyze Performance ETL...")

def calculate_units_won(units_bet, price):
    """Calculate units won based on bet amount and price"""
    if price >= 0:
        # Positive odds: bet 100 to win price
        return round(units_bet * (price / 100), 2)
    else:
        # Negative odds: bet abs(price) to win 100
        return round(units_bet * (100 / abs(price)), 2)

def analyze_completed_games():
    """Analyze performance of completed games and update records"""
    logger.info("Analyzing completed games")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        
        # Get incomplete predictions with their game data
        cursor.execute("""
            SELECT mp.predictionId, mp.modelId, mp.game_id, mp.predicted_pt_diff, mp.predicted_pt_total,
                   mp.bet_type, mp.fd_home_spread, mp.fd_home_spreadPrice, mp.fd_away_spreadPrice,
                   mp.fd_over, mp.fd_overPrice, mp.fd_underPrice, mp.unitsBet,
                   g.is_completed, g.home_score, g.away_score, g.pt_diff, g.pt_total
            FROM modelPredictions mp
            JOIN games2026 g ON mp.game_id = g.game_id
            WHERE mp.is_completed = 0 AND g.is_completed = 1
        """)
        
        completed_predictions = cursor.fetchall()
        logger.info(f"Found {len(completed_predictions)} completed games to analyze")
        
        for prediction in completed_predictions:
            (pred_id, model_id, game_id, pred_pt_diff, pred_pt_total, bet_type,
             fd_home_spread, fd_home_spread_price, fd_away_spread_price,
             fd_over, fd_over_price, fd_under_price, units_bet,
             _, home_score, away_score, actual_pt_diff, actual_pt_total) = prediction
            
            # Update prediction with game results
            cursor.execute("""
                UPDATE modelPredictions 
                SET is_completed = 1, home_score = ?, away_score = ?, pt_diff = ?, pt_total = ?
                WHERE predictionId = ?
            """, (home_score, away_score, actual_pt_diff, actual_pt_total, pred_id))
            
            # Determine win/loss based on bet type
            if bet_type == 'spread':
                # Spread bet analysis
                actual_cover = actual_pt_diff + fd_home_spread
                predicted_cover = pred_pt_diff + fd_home_spread
                
                if (actual_cover > 0 and predicted_cover > 0) or (actual_cover < 0 and predicted_cover < 0):
                    # Correct prediction
                    w_l = 'w'
                    # Use correct spread price based on which team was picked
                    if predicted_cover > 0:
                        # Picked home team, use home spread price
                        units_won = calculate_units_won(units_bet, fd_home_spread_price)
                    else:
                        # Picked away team, use away spread price
                        units_won = calculate_units_won(units_bet, fd_away_spread_price)
                else:
                    # Incorrect prediction
                    w_l = 'l'
                    units_won = -units_bet
                    
            else:  # total bet
                # Total bet analysis
                if pred_pt_total > fd_over:
                    # Predicted Over
                    if actual_pt_total > fd_over:
                        # Correct Over prediction
                        w_l = 'w'
                        units_won = calculate_units_won(units_bet, fd_over_price)
                    else:
                        # Incorrect Over prediction
                        w_l = 'l'
                        units_won = -units_bet
                else:
                    # Predicted Under
                    if actual_pt_total < fd_over:
                        # Correct Under prediction
                        w_l = 'w'
                        units_won = calculate_units_won(units_bet, fd_under_price)
                    else:
                        # Incorrect Under prediction
                        w_l = 'l'
                        units_won = -units_bet
            
            # Update prediction with results
            cursor.execute("""
                UPDATE modelPredictions 
                SET w_l = ?, unitsWon = ?
                WHERE predictionId = ?
            """, (w_l, units_won, pred_id))
            
            logger.info(f"Updated prediction {pred_id}: {w_l} ({units_won:+.2f} units)")
        
        # Recalculate stats for active models only (exclude soft-deleted)
        cursor.execute("SELECT id FROM modelDetails WHERE modelPath IS NOT NULL")
        all_model_ids = [row[0] for row in cursor.fetchall()]
        
        for model_id in all_model_ids:
            # Calculate overall stats from ALL completed predictions
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_games,
                    SUM(CASE WHEN w_l = 'w' THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN w_l = 'l' THEN 1 ELSE 0 END) as losses,
                    SUM(unitsBet) as total_units_bet,
                    SUM(unitsWon) as total_units_won
                FROM modelPredictions 
                WHERE modelId = ? AND is_completed = 1
            """, (model_id,))
            
            stats = cursor.fetchone()
            total_games, wins, losses, total_units_bet, total_units_won = stats or (0, 0, 0, 0, 0)
            
            w_l_overall = f"{wins or 0}-{losses or 0}"
            
            # Update modelDetails with fresh calculations
            cursor.execute("""
                UPDATE modelDetails 
                SET w_l_overall = ?, unitsBetOverall = ?, unitsWonOverall = ?
                WHERE id = ?
            """, (w_l_overall, total_units_bet or 0, total_units_won or 0, model_id))
            
            logger.info(f"Recalculated model {model_id}: {w_l_overall} ({total_units_won or 0:+.2f} units)")
        
        conn.commit()
        logger.info("Completed game analysis finished")
        
    except Exception:
        logger.error("Analyze Performance ETL failed", exc_info=True)
    finally:
        conn.close()

def main():
    """Main function to analyze completed games"""
    logger.info("Starting daily model operations")
    
    # Analyze completed games
    analyze_completed_games()
    
    logger.info("Daily model operations completed")

if __name__ == "__main__":
    main()