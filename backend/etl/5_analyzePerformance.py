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
            FROM modelPredictionsMM mp
            JOIN gamesMM g ON mp.game_id = g.game_id
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
                UPDATE modelPredictionsMM 
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
                UPDATE modelPredictionsMM 
                SET w_l = ?, unitsWon = ?
                WHERE predictionId = ?
            """, (w_l, units_won, pred_id))
            
            logger.info(f"Updated prediction {pred_id}: {w_l} ({units_won:+.2f} units)")
        
        # Recalculate stats for active models only (exclude soft-deleted)
        cursor.execute("SELECT id FROM modelDetailsMM WHERE modelPath IS NOT NULL")
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
                FROM modelPredictionsMM 
                WHERE modelId = ? AND is_completed = 1
            """, (model_id,))
            
            stats = cursor.fetchone()
            total_games, wins, losses, total_units_bet, total_units_won = stats or (0, 0, 0, 0, 0)
            
            w_l_overall = f"{wins or 0}-{losses or 0}"
            
            # Update modelDetailsMM with fresh calculations
            cursor.execute("""
                UPDATE modelDetailsMM 
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

def persist_community_picks_mm():
    """Persist community picks (modelId=999) for each newly completed date in modelPredictionsMM."""
    logger.info("Persisting community picks for MM tables")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Total active model count (excludes community picks placeholder)
        cursor.execute("SELECT COUNT(*) FROM modelDetailsMM WHERE modelPath IS NOT NULL AND id != 999")
        total_model_count = cursor.fetchone()[0] or 0

        if total_model_count == 0:
            logger.info("No active models in modelDetailsMM, skipping community picks")
            return

        # Dates with completed regular-model predictions
        cursor.execute("""
            SELECT DISTINCT game_date FROM modelPredictionsMM
            WHERE is_completed = 1 AND modelId != 999
            ORDER BY game_date
        """)
        completed_dates = [row[0] for row in cursor.fetchall()]
        logger.info(f"Found {len(completed_dates)} completed dates to process")

        new_dates_count = 0

        for date in completed_dates:
            # Idempotency check
            cursor.execute("""
                SELECT COUNT(*) FROM modelPredictionsMM WHERE modelId = 999 AND game_date = ?
            """, (date,))
            if cursor.fetchone()[0] > 0:
                logger.info(f"Community picks already persisted for {date}, skipping")
                continue

            # Load all completed predictions for this date
            cursor.execute("""
                SELECT game_id, summary, edge, home_team, away_team, w_l, modelId,
                       fd_home_spreadPrice, fd_away_spreadPrice, fd_overPrice, fd_underPrice,
                       fd_home_spread, fd_away_spread, fd_over, fd_under,
                       bet_type, home_score, away_score, pt_diff, pt_total
                FROM modelPredictionsMM
                WHERE game_date = ? AND is_completed = 1 AND modelId != 999
            """, (date,))

            bets = []
            for row in cursor.fetchall():
                (game_id, summary, edge, home_team, away_team, w_l, model_id,
                 home_spread_price, away_spread_price, over_price, under_price,
                 fd_home_spread, fd_away_spread, fd_over, fd_under,
                 bet_type, home_score, away_score, pt_diff, pt_total) = row

                pick = summary.split("Pick:")[1].strip() if summary and "Pick:" in summary else ""
                bets.append({
                    "gameId": game_id, "pick": pick, "edge": edge or 0,
                    "homeTeam": home_team, "awayTeam": away_team, "wl": w_l,
                    "betType": bet_type,
                    "prices": {
                        "homeSpread": home_spread_price, "awaySpread": away_spread_price,
                        "over": over_price, "under": under_price
                    },
                    "fdHomeSpread": fd_home_spread, "fdAwaySpread": fd_away_spread,
                    "fdOver": fd_over, "fdUnder": fd_under,
                    "homeScore": home_score, "awayScore": away_score,
                    "ptDiff": pt_diff, "ptTotal": pt_total
                })

            # Aggregate by unique pick (same logic as frontend fetchTopPicks)
            pick_map = {}
            row_data_map = {}

            for bet in bets:
                if not bet["pick"] or not bet["gameId"]:
                    continue
                unique_key = f"{bet['gameId']}:{bet['pick']}:{bet['wl'] or 'pending'}"

                if 'Over' in bet["pick"] or 'Under' in bet["pick"]:
                    price = bet["prices"]["over"] if 'Over' in bet["pick"] else bet["prices"]["under"]
                else:
                    price = bet["prices"]["homeSpread"] if bet["homeTeam"] in bet["pick"] else bet["prices"]["awaySpread"]

                if unique_key in pick_map:
                    pick_map[unique_key]["totalEdge"] += bet["edge"]
                    pick_map[unique_key]["modelCount"] += 1
                else:
                    pick_map[unique_key] = {"totalEdge": bet["edge"], "modelCount": 1,
                                            "price": price, "result": bet["wl"]}
                    row_data_map[unique_key] = bet

            # Filter avg_edge >= 3.0, sort desc, top 5
            top_picks = []
            for key, data in pick_map.items():
                avg_edge = data["totalEdge"] / total_model_count
                if avg_edge >= 3.0:
                    top_picks.append({
                        "key": key, "avgEdge": avg_edge,
                        "price": data["price"], "result": data["result"],
                        "rowData": row_data_map[key]
                    })
            top_picks.sort(key=lambda x: x["avgEdge"], reverse=True)
            top_picks = top_picks[:5]

            for community_pick in top_picks:
                row = community_pick["rowData"]
                price = community_pick["price"]
                result = community_pick["result"]
                avg_edge = community_pick["avgEdge"]

                if result == 'w':
                    units_won = round(price / 100, 2) if price and price > 0 else round(100 / abs(price), 2) if price else 0
                elif result == 'l':
                    units_won = -1.0
                else:
                    units_won = None

                bet_type = 'total' if ('Over' in row["pick"] or 'Under' in row["pick"]) else 'spread'
                summary = f"Community // Pick: {row['pick']}"

                cursor.execute("""
                    INSERT INTO modelPredictionsMM
                    (datePredicted, modelId, game_id, game_date, is_completed,
                     home_team, away_team,
                     fd_home_spread, fd_home_spreadPrice, fd_away_spread, fd_away_spreadPrice,
                     fd_over, fd_overPrice, fd_under, fd_underPrice,
                     predicted_pt_diff, predicted_pt_total, bet_type, edge, unitsBet,
                     summary, w_l, unitsWon, home_score, away_score, pt_diff, pt_total)
                    VALUES (?, 999, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                            NULL, NULL, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    date, row["gameId"], date,
                    row["homeTeam"], row["awayTeam"],
                    row["fdHomeSpread"], row["prices"]["homeSpread"],
                    row["fdAwaySpread"], row["prices"]["awaySpread"],
                    row["fdOver"], row["prices"]["over"],
                    row["fdUnder"], row["prices"]["under"],
                    bet_type, avg_edge, summary, result, units_won,
                    row["homeScore"], row["awayScore"], row["ptDiff"], row["ptTotal"]
                ))

            logger.info(f"Persisted {len(top_picks)} community picks for {date}")
            new_dates_count += 1

        conn.commit()
        logger.info(f"Community picks persisted for {new_dates_count} new dates")

    except Exception:
        logger.error("Community picks persistence failed", exc_info=True)
    finally:
        conn.close()


def main():
    """Main function to analyze completed games"""
    logger.info("Starting daily model operations")

    analyze_completed_games()
    persist_community_picks_mm()

    logger.info("Daily model operations completed")

if __name__ == "__main__":
    main()