import pandas as pd
import numpy as np
import joblib
import os
import warnings
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from logger import get_logger
from dbConnection import get_db_connection

warnings.filterwarnings('ignore', message='pandas only supports SQLAlchemy')

logger = get_logger("3_runModels")

load_dotenv()

MODEL_PATH = os.environ.get('MODEL_PATH')
if not MODEL_PATH:
    raise ValueError("Missing MODEL_PATH in environment variables")

logger.info("Starting Run Models ETL...")

try:
    def get_multiplier(weight_value, min_mult, max_mult):
        """Convert weight (0-9) to multiplier within given range"""
        return min_mult + (weight_value / 9.0) * (max_mult - min_mult)

    def apply_model_weights(df, weights):
        """Apply model-specific weights to features"""
        df = df.copy()
        
        # General stats (0.9 - 1.1)
        mult = get_multiplier(weights['weight_gen_off'], 0.9, 1.1)
        df['home_adjOffEff'] *= mult
        df['away_adjOffEff'] *= mult
        
        mult = get_multiplier(weights['weight_gen_def'], 0.9, 1.1)
        df['home_adjDefEff'] *= mult
        df['away_adjDefEff'] *= mult
        
        mult = get_multiplier(weights['weight_pace'], 0.9, 1.1)
        df['home_adjTempo'] *= mult
        df['away_adjTempo'] *= mult
        
        # Threes (0.8 - 1.2)
        mult = get_multiplier(weights['weight_threes'], 0.8, 1.2)
        df['home_threesPct'] *= mult
        df['home_threesRate'] *= mult
        df['home_oppThreesPct'] *= mult
        df['home_oppThreesRate'] *= mult
        df['away_threesPct'] *= mult
        df['away_threesRate'] *= mult
        df['away_oppThreesPct'] *= mult
        df['away_oppThreesRate'] *= mult
        
        # Free throws (0.8 - 1.2)
        mult = get_multiplier(weights['weight_fts'], 0.8, 1.2)
        df['home_ftRate'] *= mult
        df['home_ftPct'] *= mult
        df['home_defFtRate'] *= mult
        df['away_ftRate'] *= mult
        df['away_ftPct'] *= mult
        df['away_defFtRate'] *= mult
        
        # Defense (0.8 - 1.2)
        mult = get_multiplier(weights['weight_per_def'], 0.8, 1.2)
        df['home_defEffFgPct'] *= mult
        df['home_stlRate'] *= mult
        df['away_defEffFgPct'] *= mult
        df['away_stlRate'] *= mult
        
        mult = get_multiplier(weights['weight_int_def'], 0.8, 1.2)
        df['home_blockPct'] *= mult
        df['away_blockPct'] *= mult
        
        # Rebounding (0.8 - 1.2)
        mult = get_multiplier(weights['weight_boards'], 0.8, 1.2)
        df['home_offRebPct'] *= mult
        df['home_defRebPct'] *= mult
        df['away_offRebPct'] *= mult
        df['away_defRebPct'] *= mult
        
        # Playmaking (0.8 - 1.2)
        mult = get_multiplier(weights['weight_playmaking'], 0.8, 1.2)
        df['home_astRate'] *= mult
        df['home_trnvrPct'] *= mult
        df['away_astRate'] *= mult
        df['away_trnvrPct'] *= mult
        
        # Intangibles (0.9 - 1.1)
        mult = get_multiplier(weights['weight_intangibles'], 0.9, 1.1)
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
            game_id = str(row['game_id']) if not isinstance(row['game_id'], pd.Series) else str(row['game_id'].iloc[0])
            
            cursor.execute("""
            SELECT game_id, fd_home_spread, fd_home_spread_price, fd_away_spread, fd_away_spread_price,
                   fd_over, fd_over_price, fd_under, fd_under_price
            FROM games 
            WHERE game_id = %s AND is_completed = false
            """, (game_id,))
            
            game_odds = cursor.fetchone()
            if game_odds and game_odds[1] is not None:
                game_id, fd_home_spread, fd_home_spread_price, fd_away_spread, fd_away_spread_price, fd_over, fd_over_price, fd_under, fd_under_price = game_odds
                
                # Convert Decimal to float
                fd_home_spread = float(fd_home_spread)
                fd_away_spread = float(fd_away_spread)
                fd_over = float(fd_over) if fd_over else None
                fd_under = float(fd_under) if fd_under else None
                
                pred_diff = row['pred_pt_diff']
                edge = abs(pred_diff + fd_home_spread)
                
                if pred_diff + fd_home_spread > 0:
                    pick_team = row['home_team_name']
                    pick_spread = fd_home_spread
                else:
                    pick_team = row['away_team_name']
                    pick_spread = -fd_home_spread
                
                row_with_odds = {k: (v.iloc[0] if isinstance(v, pd.Series) else v) for k, v in row.items()}
                row_with_odds.update({
                    'game_id': game_id, 'fd_home_spread': fd_home_spread, 'fd_home_spread_price': fd_home_spread_price,
                    'fd_away_spread': fd_away_spread, 'fd_away_spread_price': fd_away_spread_price,
                    'fd_over': fd_over, 'fd_over_price': fd_over_price, 'fd_under': fd_under, 'fd_under_price': fd_under_price
                })
                
                edges.append({
                    'game_id': game_id, 'edge': edge, 'bet_type': 'spread',
                    'pick_team': pick_team, 'pick_spread': pick_spread, 'pred_pt_diff': pred_diff, 'row_data': row_with_odds
                })
        
        # Process total predictions
        for _, row in df_total.iterrows():
            game_id = str(row['game_id']) if not isinstance(row['game_id'], pd.Series) else str(row['game_id'].iloc[0])
            
            cursor.execute("""
            SELECT game_id, fd_home_spread, fd_home_spread_price, fd_away_spread, fd_away_spread_price,
                   fd_over, fd_over_price, fd_under, fd_under_price
            FROM games 
            WHERE game_id = %s AND is_completed = false
            """, (game_id,))
            
            game_odds = cursor.fetchone()
            if game_odds and game_odds[5] is not None:
                game_id, fd_home_spread, fd_home_spread_price, fd_away_spread, fd_away_spread_price, fd_over, fd_over_price, fd_under, fd_under_price = game_odds
                
                # Convert Decimal to float
                fd_home_spread = float(fd_home_spread) if fd_home_spread else None
                fd_away_spread = float(fd_away_spread) if fd_away_spread else None
                fd_over = float(fd_over)
                fd_under = float(fd_under) if fd_under else None
                
                pred_total = row['pred_pt_total']
                edge = abs(pred_total - fd_over)
                pick_total = 'Over' if pred_total > fd_over else 'Under'
                
                row_with_odds = {k: (v.iloc[0] if isinstance(v, pd.Series) else v) for k, v in row.items()}
                row_with_odds.update({
                    'game_id': game_id, 'fd_home_spread': fd_home_spread, 'fd_home_spread_price': fd_home_spread_price,
                    'fd_away_spread': fd_away_spread, 'fd_away_spread_price': fd_away_spread_price,
                    'fd_over': fd_over, 'fd_over_price': fd_over_price, 'fd_under': fd_under, 'fd_under_price': fd_under_price
                })
                
                edges.append({
                    'game_id': game_id, 'edge': edge, 'bet_type': 'total',
                    'pick_total': pick_total, 'pick_line': fd_over, 'pred_pt_total': pred_total, 'row_data': row_with_odds
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
        
        # Get today's date in Central time
        central = ZoneInfo("America/Chicago")
        today = datetime.now(central).strftime('%Y-%m-%d')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Calculate total bias - use server's current average for consistency
        # TODO: Update this when Supabase has full season history
        current_avg = 149.81  # Server's current average as of 2026-02-04
        historical_avg = 139.52
        total_bias = (current_avg - historical_avg) * 0.8
        
        logger.info(f"Total bias: {total_bias:.2f}")
        
        # Load baseline target data
        logger.info(f"Loading target data for {today}")
        baseline_df = pd.read_sql("""
            SELECT ds.*, g.game_id FROM daily_snapshots ds
            INNER JOIN games g ON ds.home_kp_id = g.home_kp_id AND ds.away_kp_id = g.away_kp_id AND ds.game_date = g.game_date
            WHERE ds.game_date = %s AND g.is_completed = false
        """, conn, params=(today,))
        
        if len(baseline_df) == 0:
            logger.error(f"No games found for {today}")
            conn.close()
            return
        logger.info(f"Loaded {len(baseline_df)} games")
        
        # Rename columns to match training data (camelCase)
        column_mapping = {
            'home_adj_off_eff': 'home_adjOffEff',
            'home_eff_fg_pct': 'home_effFgPct',
            'home_adj_def_eff': 'home_adjDefEff',
            'home_def_eff_fg_pct': 'home_defEffFgPct',
            'home_adj_tempo': 'home_adjTempo',
            'home_threes_pct': 'home_threesPct',
            'home_threes_rate': 'home_threesRate',
            'home_ft_rate': 'home_ftRate',
            'home_ft_pct': 'home_ftPct',
            'home_def_ft_rate': 'home_defFtRate',
            'home_block_pct': 'home_blockPct',
            'home_opp_threes_pct': 'home_oppThreesPct',
            'home_opp_threes_rate': 'home_oppThreesRate',
            'home_stl_rate': 'home_stlRate',
            'home_non_stl_trnvr_rate': 'home_nonStlTrnvrRate',
            'home_off_reb_pct': 'home_offRebPct',
            'home_def_reb_pct': 'home_defRebPct',
            'home_ast_rate': 'home_astRate',
            'home_trnvr_pct': 'home_trnvrPct',
            'home_eff_height': 'home_effHeight',
            'home_exp_rtg': 'home_expRtg',
            'home_bench_rtg': 'home_benchRtg',
            'home_cont_rtg': 'home_contRtg',
            'away_adj_off_eff': 'away_adjOffEff',
            'away_eff_fg_pct': 'away_effFgPct',
            'away_adj_def_eff': 'away_adjDefEff',
            'away_def_eff_fg_pct': 'away_defEffFgPct',
            'away_adj_tempo': 'away_adjTempo',
            'away_threes_pct': 'away_threesPct',
            'away_threes_rate': 'away_threesRate',
            'away_ft_rate': 'away_ftRate',
            'away_ft_pct': 'away_ftPct',
            'away_def_ft_rate': 'away_defFtRate',
            'away_block_pct': 'away_blockPct',
            'away_opp_threes_pct': 'away_oppThreesPct',
            'away_opp_threes_rate': 'away_oppThreesRate',
            'away_stl_rate': 'away_stlRate',
            'away_non_stl_trnvr_rate': 'away_nonStlTrnvrRate',
            'away_off_reb_pct': 'away_offRebPct',
            'away_def_reb_pct': 'away_defRebPct',
            'away_ast_rate': 'away_astRate',
            'away_trnvr_pct': 'away_trnvrPct',
            'away_eff_height': 'away_effHeight',
            'away_exp_rtg': 'away_expRtg',
            'away_bench_rtg': 'away_benchRtg',
            'away_cont_rtg': 'away_contRtg',
            'is_home': 'is_home',
            'is_neutral': 'is_neutral'
        }
        baseline_df.rename(columns=column_mapping, inplace=True)
        
        # Get all models
        cursor.execute("""
            SELECT model_id, model_name, betting_style, model_seed,
                   weight_gen_off, weight_gen_def, weight_pace, weight_threes, weight_fts,
                   weight_per_def, weight_int_def, weight_boards, weight_playmaking, weight_intangibles
            FROM model_details
        """)
        
        models = cursor.fetchall()
        logger.info(f"Found {len(models)} models")
        
        for model_data in models:
            model_id, model_name, betting_style, model_seed = model_data[:4]
            
            # Construct model paths from model_seed
            spread_path = os.path.join(MODEL_PATH, f"modelSpread_{model_seed}.joblib")
            total_path = os.path.join(MODEL_PATH, f"modelTotal_{model_seed}.joblib")
            
            weights = {
                'weight_gen_off': model_data[4], 'weight_gen_def': model_data[5], 'weight_pace': model_data[6],
                'weight_threes': model_data[7], 'weight_fts': model_data[8], 'weight_per_def': model_data[9],
                'weight_int_def': model_data[10], 'weight_boards': model_data[11], 'weight_playmaking': model_data[12],
                'weight_intangibles': model_data[13]
            }
            
            logger.info(f"Processing {model_name} (ID: {model_id})")
            
            model_df = baseline_df.copy()
            model_df = apply_model_weights(model_df, weights)
            
            if not os.path.exists(spread_path) or not os.path.exists(total_path):
                logger.error(f"Model files not found for seed {model_seed}")
                continue
                
            spread_model = joblib.load(spread_path)
            total_model = joblib.load(total_path)
            
            # Get feature columns (matching training data order from setAlpha)
            feature_cols = ['is_home', 'is_neutral',
                          'home_adjOffEff', 'home_effFgPct', 'home_adjDefEff', 'home_defEffFgPct',
                          'home_adjTempo', 'home_threesPct', 'home_threesRate', 'home_ftRate', 'home_ftPct',
                          'home_defFtRate', 'home_blockPct', 'home_oppThreesPct', 'home_oppThreesRate',
                          'home_stlRate', 'home_nonStlTrnvrRate', 'home_offRebPct', 'home_defRebPct',
                          'home_astRate', 'home_trnvrPct', 'home_effHeight', 'home_expRtg', 'home_benchRtg',
                          'home_contRtg', 'away_adjOffEff', 'away_effFgPct', 'away_adjDefEff',
                          'away_defEffFgPct', 'away_adjTempo', 'away_threesPct', 'away_threesRate',
                          'away_ftRate', 'away_ftPct', 'away_defFtRate', 'away_blockPct', 'away_oppThreesPct',
                          'away_oppThreesRate', 'away_stlRate', 'away_nonStlTrnvrRate', 'away_offRebPct',
                          'away_defRebPct', 'away_astRate', 'away_trnvrPct', 'away_effHeight', 'away_expRtg',
                          'away_benchRtg', 'away_contRtg']
            
            for col in feature_cols:
                if col not in model_df.columns:
                    model_df[col] = 0
            
            X = model_df[feature_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
            
            spread_predictions = spread_model.predict(X)
            total_predictions = total_model.predict(X) + total_bias
            
            spread_df = model_df.copy()
            spread_df['pred_pt_diff'] = spread_predictions
            
            total_df = model_df.copy()
            total_df['pred_pt_total'] = total_predictions
            
            edges = calculate_edges_and_picks(spread_df, total_df, conn)
            top_5_edges = edges[:5]
            
            edge_thresholds = {'Aggressive': 3.0, 'Moderate': 4.0, 'Reserved': 5.0}
            min_edge = edge_thresholds.get(betting_style, 4.0)
            qualified_edges = [e for e in top_5_edges if e['edge'] >= min_edge]
            
            logger.info(f"Qualified edges: {[round(e['edge'], 2) for e in qualified_edges]}")
            
            # Clear existing predictions
            cursor.execute("DELETE FROM model_predictions WHERE model_id = %s AND created_datetime::date = %s", 
                          (model_id, today))
            
            # Save predictions
            for i, edge_data in enumerate(qualified_edges, 1):
                row_with_odds = edge_data['row_data']
                units_bet = get_units_to_bet(betting_style, i)
                
                verbs = ["has", "estimates", "forecasts", "expects", "indicates", "suggests", "outputs", "computes", 
                        "rates", "shows", "returns", "signals", "grades", "sees", "likes", "backs", "supports", 
                        "thinks", "points to", "calls for", "goes with", "is on", "leans toward"]
                verb = np.random.choice(verbs)
                
                home_team = row_with_odds['home_team_name']
                away_team = row_with_odds['away_team_name']
                
                if edge_data['bet_type'] == 'spread':
                    pred_diff = edge_data['pred_pt_diff']
                    prediction_text = f"{home_team} by {abs(pred_diff):.1f}" if pred_diff > 0 else f"{away_team} by {abs(pred_diff):.1f}"
                    pick_text = f"Pick: {edge_data['pick_team']} {edge_data['pick_spread']:+.1f}"
                else:
                    prediction_text = f"a total of {edge_data['pred_pt_total']:.1f}"
                    pick_text = f"Pick: {edge_data['pick_total']} {edge_data['pick_line']:.1f}"
                
                summary = f"{model_name} {verb} {prediction_text} // {pick_text}"
                
                cursor.execute("""
                    INSERT INTO model_predictions 
                    (created_datetime, model_id, user_id, game_id, game_date, is_completed,
                     predicted_pt_diff, predicted_pt_total, predicted_edge, prediction_summary, units_bet)
                    VALUES (NOW(), %s, (SELECT user_id FROM model_details WHERE model_id = %s), %s, %s, false, %s, %s, %s, %s, %s)
                """, (model_id, model_id, row_with_odds['game_id'], row_with_odds['game_date'],
                      edge_data.get('pred_pt_diff'), edge_data.get('pred_pt_total'), edge_data['edge'], summary, units_bet))
            
            logger.info(f"Saved {len(qualified_edges)} predictions")
        
        conn.commit()
        conn.close()
        logger.info("Completed")

    run_daily_predictions()

except Exception:
    logger.error("Run Models ETL failed", exc_info=True)
    if 'conn' in locals():
        conn.close()
