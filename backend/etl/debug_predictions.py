import pandas as pd
import numpy as np
import joblib
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from dbConnection import get_db_connection

load_dotenv()

def debug_prediction_comparison(model_id=16, game_date='2026-02-04'):
    """Compare prediction logic step-by-step for a specific model and date"""
    
    print("="*80)
    print(f"DEBUGGING MODEL {model_id} FOR {game_date}")
    print("="*80)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Step 1: Check timezone and date
    print("\n1. TIMEZONE CHECK")
    central = ZoneInfo("America/Chicago")
    eastern = ZoneInfo("America/New_York")
    now_central = datetime.now(central)
    now_eastern = datetime.now(eastern)
    print(f"   Central time: {now_central.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"   Eastern time: {now_eastern.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"   Using date: {game_date}")
    
    # Step 2: Check bias calculation
    print("\n2. BIAS CALCULATION")
    cursor.execute("SELECT AVG(pt_total) FROM games WHERE is_completed = true")
    result = cursor.fetchone()
    current_avg = float(result[0]) if result and result[0] else 139.52
    historical_avg = 139.52
    total_bias = (current_avg - historical_avg) * 0.8
    print(f"   Current avg: {current_avg:.2f}")
    print(f"   Historical avg: {historical_avg:.2f}")
    print(f"   Total bias: {total_bias:.2f}")
    print(f"   Server hardcoded: 149.81 -> bias = {(149.81 - 139.52) * 0.8:.2f}")
    
    # Step 3: Get model details
    print("\n3. MODEL DETAILS")
    cursor.execute("""
        SELECT model_id, model_name, betting_style, model_seed,
               weight_gen_off, weight_gen_def, weight_pace, weight_threes, weight_fts,
               weight_per_def, weight_int_def, weight_boards, weight_playmaking, weight_intangibles
        FROM model_details WHERE model_id = %s
    """, (model_id,))
    model_data = cursor.fetchone()
    if not model_data:
        print(f"   ERROR: Model {model_id} not found")
        return
    
    model_id, model_name, betting_style, model_seed = model_data[:4]
    weights = {
        'weight_gen_off': model_data[4], 'weight_gen_def': model_data[5], 'weight_pace': model_data[6],
        'weight_threes': model_data[7], 'weight_fts': model_data[8], 'weight_per_def': model_data[9],
        'weight_int_def': model_data[10], 'weight_boards': model_data[11], 'weight_playmaking': model_data[12],
        'weight_intangibles': model_data[13]
    }
    print(f"   Model: {model_name}")
    print(f"   Seed: {model_seed}")
    print(f"   Betting style: {betting_style}")
    print(f"   Weights: {weights}")
    
    # Step 4: Load games
    print("\n4. GAMES DATA")
    df = pd.read_sql("""
        SELECT ds.*, g.game_id FROM daily_snapshots ds
        INNER JOIN games g ON ds.home_kp_id = g.home_kp_id AND ds.away_kp_id = g.away_kp_id AND ds.game_date = g.game_date
        WHERE ds.game_date = %s AND g.is_completed = false
    """, conn, params=(game_date,))
    print(f"   Found {len(df)} games")
    if len(df) == 0:
        print("   ERROR: No games found")
        return
    
    # Step 5: Show raw data for first game
    print("\n5. RAW DATA (First Game)")
    first_game = df.iloc[0]
    print(f"   Game: {first_game['home_team_name']} vs {first_game['away_team_name']}")
    print(f"   home_adj_off_eff: {first_game['home_adj_off_eff']}")
    print(f"   away_adj_off_eff: {first_game['away_adj_off_eff']}")
    print(f"   is_home: {first_game['is_home']}")
    print(f"   is_neutral: {first_game['is_neutral']}")
    
    # Step 6: Apply column mapping
    print("\n6. COLUMN MAPPING")
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
    df.rename(columns=column_mapping, inplace=True)
    print(f"   Mapped {len(column_mapping)} columns to camelCase")
    print(f"   After mapping - home_adjOffEff: {df.iloc[0]['home_adjOffEff']}")
    
    # Step 7: Apply weights
    print("\n7. WEIGHT APPLICATION (First Game)")
    print(f"   Before weights - home_adjOffEff: {df.iloc[0]['home_adjOffEff']}")
    
    def get_multiplier(weight_value, min_mult, max_mult):
        return min_mult + (weight_value / 9.0) * (max_mult - min_mult)
    
    mult = get_multiplier(weights['weight_gen_off'], 0.9, 1.1)
    print(f"   Gen Off multiplier: {mult:.4f}")
    df['home_adjOffEff'] *= mult
    df['away_adjOffEff'] *= mult
    print(f"   After weights - home_adjOffEff: {df.iloc[0]['home_adjOffEff']}")
    
    # Step 8: Feature columns
    print("\n8. FEATURE COLUMNS")
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
    print(f"   Total features: {len(feature_cols)}")
    print(f"   First 5: {feature_cols[:5]}")
    print(f"   Last 5: {feature_cols[-5:]}")
    
    # Step 9: Load models and predict
    print("\n9. MODEL PREDICTIONS")
    MODEL_PATH = os.environ.get('MODEL_PATH')
    spread_path = os.path.join(MODEL_PATH, f"modelSpread_{model_seed}.joblib")
    total_path = os.path.join(MODEL_PATH, f"modelTotal_{model_seed}.joblib")
    
    if not os.path.exists(spread_path):
        print(f"   ERROR: Spread model not found: {spread_path}")
        return
    if not os.path.exists(total_path):
        print(f"   ERROR: Total model not found: {total_path}")
        return
    
    spread_model = joblib.load(spread_path)
    total_model = joblib.load(total_path)
    
    X = df[feature_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
    
    spread_preds = spread_model.predict(X)
    total_preds_raw = total_model.predict(X)
    total_preds = total_preds_raw + total_bias
    
    print(f"   First game spread prediction: {spread_preds[0]:.2f}")
    print(f"   First game total prediction (raw): {total_preds_raw[0]:.2f}")
    print(f"   First game total prediction (with bias): {total_preds[0]:.2f}")
    
    # Step 10: Get odds and calculate edges
    print("\n10. ODDS AND EDGES")
    for i in range(min(3, len(df))):
        game_id = df.iloc[i]['game_id']
        cursor.execute("""
            SELECT fd_home_spread, fd_over
            FROM games WHERE game_id = %s
        """, (str(game_id),))
        odds = cursor.fetchone()
        if odds:
            fd_spread, fd_over = float(odds[0]), float(odds[1])
            spread_edge = abs(spread_preds[i] + fd_spread)
            total_edge = abs(total_preds[i] - fd_over)
            print(f"   Game {i+1}: {df.iloc[i]['home_team_name']} vs {df.iloc[i]['away_team_name']}")
            print(f"      Spread: pred={spread_preds[i]:.2f}, line={fd_spread:+.1f}, edge={spread_edge:.2f}")
            print(f"      Total: pred={total_preds[i]:.2f}, line={fd_over:.1f}, edge={total_edge:.2f}")
    
    conn.close()
    print("\n" + "="*80)

if __name__ == "__main__":
    debug_prediction_comparison()
