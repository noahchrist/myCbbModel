import os
from dotenv import load_dotenv
from logger import get_logger
from dbConnection import get_db_connection

logger = get_logger("4_analyzePerformance")

load_dotenv()

logger.info("Starting Analyze Performance ETL...")

def calculate_units_won(units_bet, price):
    """Calculate units won based on bet amount and price"""
    if price >= 0:
        return round(units_bet * (price / 100), 2)
    else:
        return round(units_bet * (100 / abs(price)), 2)

def analyze_completed_games():
    """Analyze performance of completed games and update records"""
    logger.info("Analyzing completed games")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get incomplete predictions with their game data
        cursor.execute("""
            SELECT mp.prediction_id, mp.model_id, mp.game_id, mp.predicted_pt_diff, mp.predicted_pt_total,
                   g.fd_home_spread, g.fd_home_spread_price, g.fd_away_spread_price,
                   g.fd_over, g.fd_over_price, g.fd_under_price, mp.units_bet,
                   g.is_completed, g.home_score, g.away_score, g.pt_diff, g.pt_total
            FROM model_predictions mp
            JOIN games g ON mp.game_id = g.game_id
            WHERE mp.is_completed = false AND g.is_completed = true
        """)
        
        completed_predictions = cursor.fetchall()
        logger.info(f"Found {len(completed_predictions)} completed games to analyze")
        
        for prediction in completed_predictions:
            (pred_id, model_id, game_id, pred_pt_diff, pred_pt_total,
             fd_home_spread, fd_home_spread_price, fd_away_spread_price,
             fd_over, fd_over_price, fd_under_price, units_bet,
             _, home_score, away_score, actual_pt_diff, actual_pt_total) = prediction
            
            # Convert Decimal to float
            fd_home_spread = float(fd_home_spread) if fd_home_spread else None
            fd_over = float(fd_over) if fd_over else None
            pred_pt_diff = float(pred_pt_diff) if pred_pt_diff else None
            pred_pt_total = float(pred_pt_total) if pred_pt_total else None
            units_bet = float(units_bet) if units_bet else 0
            
            # Determine bet type based on which prediction exists
            if pred_pt_diff is not None and fd_home_spread is not None:
                # Spread bet analysis
                actual_cover = actual_pt_diff + fd_home_spread
                predicted_cover = pred_pt_diff + fd_home_spread
                
                if (actual_cover > 0 and predicted_cover > 0) or (actual_cover < 0 and predicted_cover < 0):
                    w_l = True
                    if predicted_cover > 0:
                        units_won = calculate_units_won(units_bet, fd_home_spread_price)
                    else:
                        units_won = calculate_units_won(units_bet, fd_away_spread_price)
                else:
                    w_l = False
                    units_won = -units_bet
                    
            elif pred_pt_total is not None and fd_over is not None:
                # Total bet analysis
                if pred_pt_total > fd_over:
                    if actual_pt_total > fd_over:
                        w_l = True
                        units_won = calculate_units_won(units_bet, fd_over_price)
                    else:
                        w_l = False
                        units_won = -units_bet
                else:
                    if actual_pt_total < fd_over:
                        w_l = True
                        units_won = calculate_units_won(units_bet, fd_under_price)
                    else:
                        w_l = False
                        units_won = -units_bet
            else:
                logger.warning(f"Prediction {pred_id} has no valid bet type")
                continue
            
            # Update prediction with results
            cursor.execute("""
                UPDATE model_predictions 
                SET is_completed = true, is_won = %s, units_won = %s
                WHERE prediction_id = %s
            """, (w_l, units_won, pred_id))
            
            logger.info(f"Updated prediction {pred_id}: {'W' if w_l else 'L'} ({units_won:+.2f} units)")
        
        # Recalculate stats for all models
        cursor.execute("SELECT model_id FROM model_details")
        all_model_ids = [row[0] for row in cursor.fetchall()]
        
        for model_id in all_model_ids:
            # Calculate overall stats from ALL completed predictions
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_games,
                    SUM(CASE WHEN is_won = true THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN is_won = false THEN 1 ELSE 0 END) as losses,
                    SUM(units_bet) as total_units_bet,
                    SUM(units_won) as total_units_won
                FROM model_predictions 
                WHERE model_id = %s AND is_completed = true
            """, (model_id,))
            
            stats = cursor.fetchone()
            total_games, wins, losses, total_units_bet, total_units_won = stats or (0, 0, 0, 0, 0)
            
            wins = wins or 0
            losses = losses or 0
            total_wl = f"{wins}-{losses}"
            
            # Update model_details with fresh calculations
            cursor.execute("""
                UPDATE model_details 
                SET total_wl = %s, total_units_bet = %s, total_units_won = %s
                WHERE model_id = %s
            """, (total_wl, total_units_bet or 0, total_units_won or 0, model_id))
            
            logger.info(f"Recalculated model {model_id}: {total_wl} ({total_units_won or 0:+.2f} units)")
        
        conn.commit()
        logger.info("Completed game analysis finished")
        
    except Exception:
        logger.error("Analyze Performance ETL failed", exc_info=True)
    finally:
        conn.close()

def main():
    """Main function to analyze completed games"""
    logger.info("Starting daily model operations")
    analyze_completed_games()
    logger.info("Daily model operations completed")

if __name__ == "__main__":
    main()
