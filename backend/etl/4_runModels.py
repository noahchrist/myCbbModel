import sqlite3
import pandas as pd
import numpy as np
import joblib
import os
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

# Anchor paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.environ.get('DB_PATH')

def get_multiplier(weight_value, min_mult, max_mult):
    """Convert weight (0-9) to multiplier in given range"""
    return min_mult + (weight_value / 9) * (max_mult - min_mult)

def apply_model_weights(df, weights):
    """Apply model weights to target dataset"""
    print(f"Applying model weights: {weights}")
    
    # General Offense (0.9 - 1.1)
    mult = get_multiplier(weights['weightGenOff'], 0.9, 1.1)
    df['home_adjOffEff'] *= mult
    df['home_effFgPct'] *= mult
    df['away_adjOffEff'] *= mult
    df['away_effFgPct'] *= mult
    
    # General Defense (0.9 - 1.1)
    mult = get_multiplier(weights['weightGenDef'], 0.9, 1.1)
    df['home_adjDefEff'] *= mult
    df['home_defEffFgPct'] *= mult
    df['away_adjDefEff'] *= mult
    df['away_defEffFgPct'] *= mult
    
    # Pace (0.9 - 1.1)
    mult = get_multiplier(weights['weightPace'], 0.9, 1.1)
    df['home_adjTempo'] *= mult
    df['away_adjTempo'] *= mult
    
    # Threes (0.8 - 1.2)
    mult = get_multiplier(weights['weightThrees'], 0.8, 1.2)
    df['home_threesPct'] *= mult
    df['home_threesRate'] *= mult
    df['away_threesPct'] *= mult
    df['away_threesRate'] *= mult
    
    # Free Throws (0.8 - 1.2)
    mult = get_multiplier(weights['weightFts'], 0.8, 1.2)
    df['home_ftRate'] *= mult
    df['home_ftPct'] *= mult
    df['away_ftRate'] *= mult
    df['away_ftPct'] *= mult
    
    # Perimeter Defense (0.8 - 1.2)
    mult = get_multiplier(weights['weightPerDef'], 0.8, 1.2)
    df['home_oppThreesPct'] *= mult
    df['home_oppThreesRate'] *= mult
    df['home_stlRate'] *= mult
    df['home_nonStlTrnvrRate'] *= mult
    df['away_oppThreesPct'] *= mult
    df['away_oppThreesRate'] *= mult
    df['away_stlRate'] *= mult
    df['away_nonStlTrnvrRate'] *= mult
    
    # Interior Defense (0.8 - 1.2)
    mult = get_multiplier(weights['weightIntDef'], 0.8, 1.2)
    df['home_defFtRate'] *= mult
    df['home_blockPct'] *= mult
    df['away_defFtRate'] *= mult
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

def calculate_edges_and_picks(df, conn):
    """Calculate edges and determine picks using betting odds from games2026"""
    edges = []
    cursor = conn.cursor()
    
    for _, row in df.iterrows():
        # Get betting odds from games2026 using team matching
        cursor.execute("""
        SELECT game_id, fd_home_spread, fd_home_spreadPrice, fd_away_spread, fd_away_spreadPrice
        FROM games2026 
        WHERE home_kpid = ? AND away_kpid = ? AND game_date = ? AND is_completed = 0
        """, (row['home_kpid'], row['away_kpid'], row['game_date']))
        
        game_odds = cursor.fetchone()
        if game_odds and pd.notna(game_odds[1]):
            game_id, fd_home_spread, fd_home_spreadPrice, fd_away_spread, fd_away_spreadPrice = game_odds
            
            pred_diff = row['pred_pt_diff']
            home_spread = fd_home_spread
            edge = abs(pred_diff + home_spread)
            
            # Determine pick
            if pred_diff + home_spread > 0:
                pick_team = row['home_team']
                pick_spread = home_spread
            else:
                pick_team = row['away_team']
                pick_spread = -home_spread
            
            # Add betting odds to row data
            row_with_odds = row.copy()
            row_with_odds['game_id'] = game_id
            row_with_odds['fd_home_spread'] = fd_home_spread
            row_with_odds['fd_home_spreadPrice'] = fd_home_spreadPrice
            row_with_odds['fd_away_spread'] = fd_away_spread
            row_with_odds['fd_away_spreadPrice'] = fd_away_spreadPrice
            
            edges.append({
                'game_id': game_id,
                'edge': edge,
                'pick_team': pick_team,
                'pick_spread': pick_spread,
                'pred_pt_diff': pred_diff,
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
    print("🏀 Starting daily predictions...")
    
    # Get today's date
    today = datetime.now().strftime('%Y-%m-%d')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Load baseline target data from setTarget2026 for today
    print(f"📊 Loading baseline target data from setTarget2026 for {today}")
    baseline_df = pd.read_sql("SELECT * FROM setTarget2026 WHERE game_date = ?", conn, params=(today,))
    
    if len(baseline_df) == 0:
        print(f"❌ No games found in setTarget2026 for {today}")
        conn.close()
        return
    print(f"Loaded {len(baseline_df)} games")
    
    # Get all models
    cursor.execute("""
        SELECT id, modelName, bettingStyle, modelPath,
               weightGenOff, weightGenDef, weightPace, weightThrees, weightFts,
               weightPerDef, weightIntDef, weightBoards, weightPlaymaking, weightIntangibles
        FROM modelDetails
        WHERE modelPath IS NOT NULL
    """)
    
    models = cursor.fetchall()
    print(f"🎯 Found {len(models)} models to process")
    
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
        
        print(f"\n🔧 Processing model: {model_name} (ID: {model_id})")
        
        # Create model-specific target set
        print("📈 Creating model-specific target set...")
        model_df = baseline_df.copy()
        model_df = apply_model_weights(model_df, weights)
        
        # Load model and make predictions
        if not os.path.exists(model_path):
            print(f"❌ Model file not found: {model_path}")
            continue
            
        print("🤖 Loading model and making predictions...")
        model = joblib.load(model_path)
        
        # Get training feature columns from setAlpha to match model training
        df_train = pd.read_sql("SELECT * FROM setAlpha LIMIT 1", conn)
        drop_cols = ["id", "home_score", "away_score", "home_team", "away_team", "win_loss", "pt_diff", "pt_total", "date", "season", "game_date"]
        feature_cols = [c for c in df_train.columns if c not in drop_cols]
        
        # Ensure target data has all training features in same order
        for col in feature_cols:
            if col not in model_df.columns:
                model_df[col] = 0
        
        X = model_df[feature_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
        predictions = model.predict(X)
        
        # Add jitter
        jitter = np.random.uniform(-0.4, 0.4, len(predictions))
        predictions += jitter
        
        model_df['pred_pt_diff'] = predictions
        print(f"✅ Generated {len(predictions)} predictions")
        
        # Calculate edges and get top 5
        print("📊 Calculating edges...")
        edges = calculate_edges_and_picks(model_df, conn)
        top_5_edges = edges[:5]
        
        print(f"🎯 Top 5 edges: {[round(e['edge'], 2) for e in top_5_edges]}")
        
        # Clear existing predictions for this model today
        cursor.execute("DELETE FROM modelPredictions WHERE modelId = ? AND datePredicted = ?", 
                      (model_id, datetime.now().date().isoformat()))
        
        # Save top 5 predictions
        print("💾 Saving predictions...")
        for i, edge_data in enumerate(top_5_edges, 1):
            row = edge_data['row_data']
            units_bet = get_units_to_bet(betting_style, i)
            
            # Generate summary
            pred_diff = edge_data['pred_pt_diff']
            home_team = row['home_team']
            away_team = row['away_team']
            
            verbs = ["has", "estimates", "forecasts", "expects", "indicates", "suggests", "outputs", "computes", "rates", "shows", "returns", "signals", "grades", "sees", "likes", "backs", "supports", "thinks", "points to", "calls for", "goes with", "is on", "leans toward"]
            verb = np.random.choice(verbs)
            
            if pred_diff > 0:
                prediction_text = f"{home_team} by {abs(pred_diff):.1f}"
            else:
                prediction_text = f"{away_team} by {abs(pred_diff):.1f}"
            
            pick_text = f"Pick: {edge_data['pick_team']} {edge_data['pick_spread']:+.1f}"
            summary = f"{model_name} {verb} {prediction_text} // {pick_text}"
            
            # Use game_date from row data
            game_date = row['game_date']
            
            cursor.execute("""
                INSERT INTO modelPredictions 
                (datePredicted, modelId, game_id, game_date, is_completed, home_team, away_team,
                 fd_home_spread, fd_home_spreadPrice, fd_away_spread, fd_away_spreadPrice,
                 predicted_pt_diff, edge, unitsBet, summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().date().isoformat(),
                model_id,
                row['game_id'],
                game_date,
                False,
                row['home_team'],
                row['away_team'],
                row['fd_home_spread'],
                row.get('fd_home_spreadPrice'),
                row['fd_away_spread'],
                row.get('fd_away_spreadPrice'),
                edge_data['pred_pt_diff'],
                edge_data['edge'],
                units_bet,
                summary
            ))
        
        print(f"✅ Saved 5 predictions for {model_name}")
    
    conn.commit()
    conn.close()
    print("\n🎉 Daily predictions completed!")

if __name__ == "__main__":
    run_daily_predictions()