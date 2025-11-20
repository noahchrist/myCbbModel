import sqlite3
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Anchor paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.environ.get('DB_PATH') or os.path.join(BACKEND_DIR, 'data', 'master.db')

def calculate_units_won(units_bet, spread_price):
    """Calculate units won based on bet amount and spread price"""
    if spread_price >= 0:
        # Positive odds: bet 100 to win spread_price
        return round(units_bet * (spread_price / 100), 2)
    else:
        # Negative odds: bet abs(spread_price) to win 100
        return round(units_bet * (100 / abs(spread_price)), 2)

def analyze_completed_games():
    """Analyze performance of completed games and update records"""
    print("🔍 Analyzing completed games...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get incomplete predictions with their game data
    cursor.execute("""
        SELECT mp.predictionId, mp.modelId, mp.game_id, mp.predicted_pt_diff, 
               mp.fd_home_spread, mp.fd_home_spreadPrice, mp.fd_away_spreadPrice, mp.unitsBet,
               g.is_completed, g.home_score, g.away_score, g.pt_diff
        FROM modelPredictions mp
        JOIN games2026 g ON mp.game_id = g.game_id
        WHERE mp.is_completed = 0 AND g.is_completed = 1
    """)
    
    completed_predictions = cursor.fetchall()
    print(f"📊 Found {len(completed_predictions)} completed games to analyze")
    
    for prediction in completed_predictions:
        pred_id, model_id, game_id, pred_pt_diff, fd_home_spread, fd_home_spread_price, fd_away_spread_price, units_bet, _, home_score, away_score, actual_pt_diff = prediction
        
        # Update prediction with game results
        cursor.execute("""
            UPDATE modelPredictions 
            SET is_completed = 1, home_score = ?, away_score = ?, pt_diff = ?
            WHERE predictionId = ?
        """, (home_score, away_score, actual_pt_diff, pred_id))
        
        # Determine win/loss
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
        
        # Update prediction with results
        cursor.execute("""
            UPDATE modelPredictions 
            SET w_l = ?, unitsWon = ?
            WHERE predictionId = ?
        """, (w_l, units_won, pred_id))
        
        print(f"✅ Updated prediction {pred_id}: {w_l} ({units_won:+.2f} units)")
    
    # Update model overall stats
    cursor.execute("SELECT DISTINCT modelId FROM modelPredictions WHERE is_completed = 1")
    model_ids = [row[0] for row in cursor.fetchall()]
    
    for model_id in model_ids:
        # Calculate overall stats
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
        total_games, wins, losses, total_units_bet, total_units_won = stats
        
        w_l_overall = f"{wins}-{losses}"
        
        # Update modelDetails
        cursor.execute("""
            UPDATE modelDetails 
            SET w_l_overall = ?, unitsBetOverall = ?, unitsWonOverall = ?
            WHERE id = ?
        """, (w_l_overall, total_units_bet, total_units_won, model_id))
        
        print(f"📈 Updated model {model_id}: {w_l_overall} ({total_units_won:+.2f} units)")
    
    conn.commit()
    conn.close()
    print("✅ Completed game analysis finished")

def main():
    """Main function to run daily predictions and analyze completed games"""
    print("🚀 Starting daily model operations...")
    
    # Analyze completed games
    analyze_completed_games()
    
    print("🎉 Daily model operations completed!")

if __name__ == "__main__":
    main()