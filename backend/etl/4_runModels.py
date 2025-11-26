import sqlite3
import pandas as pd
import numpy as np
import joblib
import os
from datetime import datetime
from dotenv import load_dotenv
from logger import get_logger

logger = get_logger("4_runModels")

# ==============================================
# Setup
# ==============================================

load_dotenv()
DB_PATH = os.environ.get('DB_PATH')

if not DB_PATH:
    raise ValueError("Missing DB_PATH in environment variables or .env file")

logger.info("Starting Run Models ETL...")

try:
    def get_multiplier(weight_value, min_mult, max_mult):
        """Convert weight (0-9) to multiplier within given range"""
        return min_mult + (weight_value / 9.0) * (max_mult - min_mult)

    def apply_model_weights(df, weights):
        """Apply model-specific weights to features"""
        df = df.copy()
        
        # General stats (0.9 - 1.1)
        mult = get_multiplier(weights['weightGenOff'], 0.9, 1.1)
        df['home_adjOffEff'] *= mult
        df['away_adjOffEff'] *= mult
        
        mult = get_multiplier(weights['weightGenDef'], 0.9, 1.1)
        df['home_adjDefEff'] *= mult
        df['away_adjDefEff'] *= mult
        
        mult = get_multiplier(weights['weightPace'], 0.9, 1.1)
        df['home_adjTempo'] *= mult
        df['away_adjTempo'] *= mult
        
        # Threes (0.8 - 1.2)
        mult = get_multiplier(weights['weightThrees'], 0.8, 1.2)
        df['home_threesPct'] *= mult
        df['home_threesRate'] *= mult
        df['home_oppThreesPct'] *= mult
        df['home_oppThreesRate'] *= mult
        df['away_threesPct'] *= mult
        df['away_threesRate'] *= mult
        df['away_oppThreesPct'] *= mult
        df['away_oppThreesRate'] *= mult
        
        # Free throws (0.8 - 1.2)
        mult = get_multiplier(weights['weightFts'], 0.8, 1.2)
        df['home_ftRate'] *= mult
        df['home_ftPct'] *= mult
        df['home_defFtRate'] *= mult
        df['away_ftRate'] *= mult
        df['away_ftPct'] *= mult
        df['away_defFtRate'] *= mult
        
        # Defense (0.8 - 1.2)
        mult = get_multiplier(weights['weightPerDef'], 0.8, 1.2)
        df['home_defEffFgPct'] *= mult
        df['home_stlRate'] *= mult
        df['away_defEffFgPct'] *= mult
        df['away_stlRate'] *= mult
        
        mult = get_multiplier(weights['weightIntDef'], 0.8, 1.2)
        df['home_blockPct'] *= mult
        df['away_blockPct'] *= mult
        
        # Rebounding (0.8 - 1.2)
        mult = get_multiplier(weights['weightBoards'], 0.8, 1.2)
        df['home_offRebPct'] *= mult
        df['home_defRebPct'] *= mult
        df['away_offRebPct'] *= mult
        df['away_defRebPct'] *= mult
        
        # Playmaking (0.8 - 1.2)
        mult = get_multiplier(weights['weightPlaymaking'], 0.8, 1.2)
        df['home_astRate'] *= mult
        df['home_trnvrPct'] *= mult
        df['away_astRate'] *= mult
        df['away_trnvrPct'] *= mult
        
        # Intangibles (0.9 - 1.1)
        mult = get_multiplier(weights['weightIntangibles'], 0.9, 1.1)
        df['home_effHeight'] *= mult
        df['home_expRtg'] *= mult
        df['home_benchRtg'] *= mult
        df['home_contRtg'] *= mult
        df['away_effHeight'] *= mult
        df['away_expRtg'] *= mult
        df['away_benchRtg'] *= mult
        df['away_contRtg'] *= mult
        
        return df

    def calculate_edges_and_picks(df_spread, df_total, conn):
        """Calculate edges for both spread and total predictions"""
        edges = []
        cursor = conn.cursor()
        
        # Process spread predictions
        for _, row in df_spread.iterrows():
            cursor.execute("""
            SELECT game_id, fd_home_spread, fd_home_spreadPrice, fd_away_spread, fd_away_spreadPrice,
                   fd_over, fd_overPrice, fd_under, fd_underPrice
            FROM games2026 
            WHERE game_id = ? AND is_completed = 0
            """, (row['game_id'],))
            
            game_odds = cursor.fetchone()
            if game_odds and pd.notna(game_odds[1]):
                game_id, fd_home_spread, fd_home_spreadPrice, fd_away_spread, fd_away_spreadPrice, fd_over, fd_overPrice, fd_under, fd_underPrice = game_odds
                
                pred_diff = row['pred_pt_diff']
                home_spread = fd_home_spread
                edge = abs(pred_diff + home_spread)
                
                # Determine spread pick
                if pred_diff + home_spread > 0:
                    pick_team = row['home_team']
                    pick_spread = home_spread
                else:
                    pick_team = row['away_team']
                    pick_spread = -home_spread
                
                row_with_odds = row.copy()
                row_with_odds['game_id'] = game_id
                row_with_odds['fd_home_spread'] = fd_home_spread
                row_with_odds['fd_home_spreadPrice'] = fd_home_spreadPrice
                row_with_odds['fd_away_spread'] = fd_away_spread
                row_with_odds['fd_away_spreadPrice'] = fd_away_spreadPrice
                row_with_odds['fd_over'] = fd_over
                row_with_odds['fd_overPrice'] = fd_overPrice
                row_with_odds['fd_under'] = fd_under
                row_with_odds['fd_underPrice'] = fd_underPrice
                
                edges.append({
                    'game_id': game_id,
                    'edge': edge,
                    'bet_type': 'spread',
                    'pick_team': pick_team,
                    'pick_spread': pick_spread,
                    'pred_pt_diff': pred_diff,
                    'row_data': row_with_odds
                })
        
        # Process total predictions
        for _, row in df_total.iterrows():
            cursor.execute("""
            SELECT game_id, fd_home_spread, fd_home_spreadPrice, fd_away_spread, fd_away_spreadPrice,
                   fd_over, fd_overPrice, fd_under, fd_underPrice
            FROM games2026 
            WHERE game_id = ? AND is_completed = 0
            """, (row['game_id'],))
            
            game_odds = cursor.fetchone()
            if game_odds and pd.notna(game_odds[5]):  # Check fd_over exists
                game_id, fd_home_spread, fd_home_spreadPrice, fd_away_spread, fd_away_spreadPrice, fd_over, fd_overPrice, fd_under, fd_underPrice = game_odds
                
                pred_total = row['pred_pt_total']
                total_line = fd_over
                edge = abs(pred_total - total_line)
                
                # Determine total pick
                if pred_total > total_line:
                    pick_total = 'Over'
                    pick_line = total_line
                else:
                    pick_total = 'Under'
                    pick_line = total_line
                
                row_with_odds = row.copy()
                row_with_odds['game_id'] = game_id
                row_with_odds['fd_home_spread'] = fd_home_spread
                row_with_odds['fd_home_spreadPrice'] = fd_home_spreadPrice
                row_with_odds['fd_away_spread'] = fd_away_spread
                row_with_odds['fd_away_spreadPrice'] = fd_away_spreadPrice
                row_with_odds['fd_over'] = fd_over
                row_with_odds['fd_overPrice'] = fd_overPrice
                row_with_odds['fd_under'] = fd_under
                row_with_odds['fd_underPrice'] = fd_underPrice
                
                edges.append({
                    'game_id': game_id,
                    'edge': edge,
                    'bet_type': 'total',
                    'pick_total': pick_total,
                    'pick_line': pick_line,
                    'pred_pt_total': pred_total,
                    'row_data': row_with_odds
                })
        
        return sorted(edges, key=lambda x: x['edge'], reverse=True)

    def get_units_to_bet(betting_style, game_rank):
        """Get units to bet based on betting style and game rank (1-5)"""
        betting_units = {
            'Aggressive': [4, 3, 2, 2, 1],
            'Moderate': [2, 2, 2, 1, 1],
            'Reserved': [2, 1, 1, 0.5, 0.5]
        }
        return betting_units.get(betting_style, [1, 1, 1, 1, 1])[game_rank - 1]

    def run_daily_predictions():
        """Main function to run daily predictions for all models"""
        logger.info("Starting daily predictions")
        
        # Get today's date
        today = datetime.now().strftime('%Y-%m-%d')
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Calculate total bias based on 2026 season average vs historical average
        cursor.execute("SELECT AVG(pt_total) FROM games2026 WHERE is_completed = 1")
        current_avg_result = cursor.fetchone()
        current_avg = current_avg_result[0] if current_avg_result and current_avg_result[0] else 139.52
        historical_avg = 139.52
        total_bias = current_avg - historical_avg
        
        logger.info(f"Total bias calculation: Current avg {current_avg:.2f} - Historical avg {historical_avg} = {total_bias:.2f}")
        
        # Load baseline target data from setTarget2026 for today (only upcoming games)
        logger.info(f"Loading baseline target data from setTarget2026 for {today}")
        baseline_df = pd.read_sql("""
            SELECT st.*, g.game_id FROM setTarget2026 st
            INNER JOIN games2026 g ON st.home_kpid = g.home_kpid AND st.away_kpid = g.away_kpid AND st.game_date = g.game_date
            WHERE st.game_date = ? AND g.is_completed = 0
        """, conn, params=(today,))
        
        if len(baseline_df) == 0:
            logger.error(f"No games found in setTarget2026 for {today}")
            conn.close()
            return
        logger.info(f"Loaded {len(baseline_df)} games")
        
        # Get all models
        cursor.execute("""
            SELECT id, modelName, bettingStyle, modelPath,
                   weightGenOff, weightGenDef, weightPace, weightThrees, weightFts,
                   weightPerDef, weightIntDef, weightBoards, weightPlaymaking, weightIntangibles
            FROM modelDetails
            WHERE modelPath IS NOT NULL
        """)
        
        models = cursor.fetchall()
        logger.info(f"Found {len(models)} models to process")
        
        for model_data in models:
            model_id, model_name, betting_style, model_path = model_data[:4]
            weights = {
                'weightGenOff': model_data[4],
                'weightGenDef': model_data[5],
                'weightPace': model_data[6],
                'weightThrees': model_data[7],
                'weightFts': model_data[8],
                'weightPerDef': model_data[9],
                'weightIntDef': model_data[10],
                'weightBoards': model_data[11],
                'weightPlaymaking': model_data[12],
                'weightIntangibles': model_data[13]
            }
            
            logger.info(f"Processing model: {model_name} (ID: {model_id})")
            
            # Create model-specific target set
            logger.info("Creating model-specific target set")
            model_df = baseline_df.copy()
            model_df = apply_model_weights(model_df, weights)
            
            # Load both models and make predictions
            if ';' not in model_path:
                logger.error(f"Model path format incorrect (missing semicolon): {model_path}")
                continue
                
            spread_path, total_path = model_path.split(';')
            
            if not os.path.exists(spread_path) or not os.path.exists(total_path):
                logger.error(f"Model files not found: {spread_path} or {total_path}")
                continue
                
            logger.info("Loading models and making predictions")
            spread_model = joblib.load(spread_path)
            total_model = joblib.load(total_path)
            
            # Get training feature columns from setAlpha to match model training
            df_train = pd.read_sql("SELECT * FROM setAlpha LIMIT 1", conn)
            drop_cols = ["id", "home_score", "away_score", "home_team", "away_team", "home_kpid", "away_kpid", "win_loss", "pt_diff", "pt_total", "date", "season", "game_date"]
            feature_cols = [c for c in df_train.columns if c not in drop_cols]
            
            # Ensure target data has all training features in same order
            for col in feature_cols:
                if col not in model_df.columns:
                    model_df[col] = 0
            
            X = model_df[feature_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
            
            # Make spread predictions
            spread_predictions = spread_model.predict(X)
            spread_jitter = np.random.uniform(-0.4, 0.4, len(spread_predictions))
            spread_predictions += spread_jitter
            
            # Make total predictions
            total_predictions = total_model.predict(X)
            total_jitter = np.random.uniform(-0.4, 0.4, len(total_predictions))
            total_predictions += total_jitter
            
            # Apply bias to total predictions
            total_predictions += total_bias
            logger.info(f"Applied {total_bias:.2f} point bias to total predictions")
            
            # Create separate dataframes for spread and total
            spread_df = model_df.copy()
            spread_df['pred_pt_diff'] = spread_predictions
            
            total_df = model_df.copy()
            total_df['pred_pt_total'] = total_predictions
            
            logger.info(f"Generated {len(spread_predictions)} spread and {len(total_predictions)} total predictions")
            
            # Calculate edges for both types and get top 5 combined
            logger.info("Calculating edges")
            edges = calculate_edges_and_picks(spread_df, total_df, conn)
            top_5_edges = edges[:5]
            
            logger.info(f"Top 5 edges: {[round(e['edge'], 2) for e in top_5_edges]}")
            
            # Clear existing predictions for this model today
            cursor.execute("DELETE FROM modelPredictions WHERE modelId = ? AND datePredicted = ?", 
                          (model_id, datetime.now().date().isoformat()))
            
            # Save top 5 predictions
            logger.info("Saving predictions")
            for i, edge_data in enumerate(top_5_edges, 1):
                row_with_odds = edge_data['row_data']
                units_bet = get_units_to_bet(betting_style, i)
                
                # Generate summary based on bet type
                home_team = row_with_odds['home_team']
                away_team = row_with_odds['away_team']
                
                verbs = ["has", "estimates", "forecasts", "expects", "indicates", "suggests", "outputs", "computes", "rates", "shows", "returns", "signals", "grades", "sees", "likes", "backs", "supports", "thinks", "points to", "calls for", "goes with", "is on", "leans toward"]
                verb = np.random.choice(verbs)
                
                if edge_data['bet_type'] == 'spread':
                    pred_diff = edge_data['pred_pt_diff']
                    if pred_diff > 0:
                        prediction_text = f"{home_team} by {abs(pred_diff):.1f}"
                    else:
                        prediction_text = f"{away_team} by {abs(pred_diff):.1f}"
                    pick_text = f"Pick: {edge_data['pick_team']} {edge_data['pick_spread']:+.1f}"
                else:  # total
                    pred_total = edge_data['pred_pt_total']
                    prediction_text = f"a total of {pred_total:.1f}"
                    pick_text = f"Pick: {edge_data['pick_total']} {edge_data['pick_line']:.1f}"
                
                summary = f"{model_name} {verb} {prediction_text} // {pick_text}"
                
                # Use game_date from row data
                game_date = row_with_odds['game_date']
                
                cursor.execute("""
                    INSERT INTO modelPredictions 
                    (datePredicted, modelId, game_id, game_date, is_completed, home_team, away_team,
                     fd_home_spread, fd_home_spreadPrice, fd_away_spread, fd_away_spreadPrice,
                     fd_over, fd_overPrice, fd_under, fd_underPrice,
                     predicted_pt_diff, predicted_pt_total, bet_type, edge, unitsBet, summary)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    datetime.now().date().isoformat(),
                    model_id,
                    row_with_odds['game_id'],
                    game_date,
                    False,
                    row_with_odds['home_team'],
                    row_with_odds['away_team'],
                    row_with_odds.get('fd_home_spread'),
                    row_with_odds.get('fd_home_spreadPrice'),
                    row_with_odds.get('fd_away_spread'),
                    row_with_odds.get('fd_away_spreadPrice'),
                    row_with_odds.get('fd_over'),
                    row_with_odds.get('fd_overPrice'),
                    row_with_odds.get('fd_under'),
                    row_with_odds.get('fd_underPrice'),
                    edge_data.get('pred_pt_diff'),
                    edge_data.get('pred_pt_total'),
                    edge_data['bet_type'],
                    edge_data['edge'],
                    units_bet,
                    summary
                ))
            
            logger.info(f"Saved 5 predictions for {model_name}")
        
        conn.commit()
        conn.close()
        logger.info("Daily predictions completed")

    run_daily_predictions()

except Exception:
    logger.error("Run Models ETL failed", exc_info=True)
    if 'conn' in locals():
        conn.close()