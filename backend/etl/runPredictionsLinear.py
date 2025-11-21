import sqlite3
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import numpy as np
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# === PATHS ===
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
MASTER_DB_PATH = os.environ.get('DB_PATH')
TRAIN_TABLE = "setAlpha"

# === CORE TRAINING + PREDICTION ===
def run_model(model_type, target_table, game_date=None, total_bias=0):
    """Train linear regression model, evaluate, then predict using targetSet."""
    if model_type == "spread":
        TARGET = "pt_diff"
        model_name = "Point Spread"
    else:
        TARGET = "pt_total"
        model_name = "Total Points"

    # --- Load training data ---
    conn = sqlite3.connect(MASTER_DB_PATH)
    df_train = pd.read_sql(f"SELECT * FROM {TRAIN_TABLE}", conn)

    drop_cols = [
        "id", "home_id", "away_id", "home_score", "away_score", "home_team", "away_team",
        "win_loss", "pt_diff", "pt_total", "date", "season"
    ]
    feature_cols = [c for c in df_train.columns if c not in drop_cols]
    X = df_train[feature_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
    y = pd.to_numeric(df_train[TARGET], errors="coerce").fillna(0)

    # --- Split and train model ---
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = LinearRegression()
    model.fit(X_train, y_train)

    # --- Evaluate model ---
    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    mse = mean_squared_error(y_test, y_pred)
    rmse = np.sqrt(mse)
    r2 = r2_score(y_test, y_pred)

    print(f"\n📊 === {model_name.upper()} MODEL EVALUATION ===")
    print(f"R²:   {r2:.4f}")
    print(f"MAE:  {mae:.4f}")
    print(f"RMSE: {rmse:.4f}")

    # --- Load target set ---
    if game_date and target_table == "setTarget2026":
        df_target = pd.read_sql("SELECT * FROM setTarget2026 WHERE game_date = ?", conn, params=(game_date,))
    else:
        df_target = pd.read_sql(f"SELECT * FROM {target_table}", conn)

    # Match feature columns (fill missing with 0)
    for col in feature_cols:
        if col not in df_target.columns:
            df_target[col] = 0

    X_target = df_target[feature_cols].apply(pd.to_numeric, errors="coerce").fillna(0)

    # --- Make predictions ---
    predictions = model.predict(X_target)
    
    # Apply bias for total predictions
    if model_type == "total" and total_bias != 0:
        predictions = predictions + total_bias
        print(f"  Applied {total_bias} point bias to total predictions")
    
    df_target[f"pred_{TARGET}"] = predictions

    conn.close()
    print(f"✅ {len(df_target)} {model_name.lower()} predictions generated")
    
    return df_target

def display_all_predictions(df_with_spread, df_with_total):
    """Display all predictions sorted by biggest edge with betting picks"""
    print(f"\n🎯 === ALL GAME PREDICTIONS ===")
    
    # Calculate edges for each game
    game_edges = []
    conn = sqlite3.connect(MASTER_DB_PATH)
    
    for _, row in df_with_spread.iterrows():
        # Find corresponding total prediction
        total_row = df_with_total[df_with_total['game_id'] == row['game_id']].iloc[0]
        
        # Get betting odds from games2026
        cursor = conn.cursor()
        cursor.execute("""
        SELECT fd_home_spread, fd_over FROM games2026 
        WHERE game_id = ?
        """, (row['game_id'],))
        odds_result = cursor.fetchone()
        
        spread_edge = 0
        total_edge = 0
        
        # Calculate spread edge
        if odds_result and pd.notna(odds_result[0]):
            pred_spread = row['pred_pt_diff']
            home_spread = odds_result[0]
            spread_edge = abs(pred_spread + home_spread)
        
        # Calculate total edge
        if odds_result and pd.notna(odds_result[1]):
            pred_total = total_row['pred_pt_total']
            betting_total = odds_result[1]
            total_edge = abs(pred_total - betting_total)
        
        max_edge = max(spread_edge, total_edge)
        game_edges.append((max_edge, row, total_row, odds_result))
    
    conn.close()
    
    # Sort by biggest edge
    game_edges.sort(key=lambda x: x[0], reverse=True)
    
    for max_edge, row, total_row, odds_result in game_edges:
        print(f"\n{row['home_team']} vs {row['away_team']}")
        
        # Spread prediction and pick
        pred_spread = row['pred_pt_diff']
        if pred_spread > 0:
            print(f"  Prediction: {row['home_team']} by {pred_spread:.1f}")
        else:
            print(f"  Prediction: {row['away_team']} by {abs(pred_spread):.1f}")
        
        # Spread pick vs betting line
        if odds_result and pd.notna(odds_result[0]):
            home_spread = odds_result[0]
            cover_margin = pred_spread + home_spread
            if cover_margin > 0:
                print(f"  Pick: {row['home_team']} {home_spread:+.1f}")
            else:
                print(f"  Pick: {row['away_team']} {-home_spread:+.1f}")
            
            # Spread edge calculation
            spread_edge = abs(cover_margin)
            print(f"  Spread edge: {spread_edge:.1f} points")
        
        # Total prediction and pick
        pred_total = total_row['pred_pt_total']
        print(f"  Total prediction: {pred_total:.1f}")
        
        # Total pick vs betting line
        if odds_result and pd.notna(odds_result[1]):
            betting_total = odds_result[1]
            if pred_total > betting_total:
                print(f"  Pick: Over {betting_total:.1f}")
            else:
                print(f"  Pick: Under {betting_total:.1f}")
            
            # Total edge calculation
            total_edge = abs(pred_total - betting_total)
            print(f"  Total edge: {total_edge:.1f} points")

# === MAIN ===
def main():
    print("🏀 Linear Regression Model Training + Prediction")
    
    # Get current season average from completed games
    conn = sqlite3.connect(MASTER_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT AVG(pt_total) FROM games2026 WHERE is_completed = 1")
    current_avg = cursor.fetchone()[0]
    conn.close()
    
    # Prompt for total prediction bias
    print("\n📊 Total Prediction Bias")
    if current_avg:
        difference = current_avg - 139.52
        print(f"Historical avg: 139.52 pts, Current avg: {current_avg:.2f} pts ({difference:+.2f} difference)")
    else:
        print("Historical avg: 139.52 pts, Current avg: No completed games yet")
    bias_input = input("Add bias to total predictions? (Enter number or 0 for none): ").strip()
    
    try:
        total_bias = float(bias_input) if bias_input else 0
    except ValueError:
        total_bias = 0
    
    if total_bias != 0:
        print(f"✅ Will add {total_bias} points to total predictions")
    else:
        print("✅ No bias will be applied")
    
    # Get today's date
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Check if games exist for today in setTarget2026
    conn = sqlite3.connect(MASTER_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM setTarget2026 WHERE game_date = ?", (today,))
    game_count = cursor.fetchone()[0]
    
    if game_count == 0:
        print(f"❌ No games found in setTarget2026 for {today}")
        conn.close()
        return
    
    print(f"\n🎯 Using setTarget2026 for {today} ({game_count} games)")
    conn.close()
    
    # Run both models and get predictions
    df_spread = run_model("spread", "setTarget2026", today)
    df_total = run_model("total", "setTarget2026", today, total_bias)
    
    # Display all predictions with picks (sorted by biggest edge)
    display_all_predictions(df_spread, df_total)
    
    print("\n🎯 Predictions complete!")

if __name__ == "__main__":
    main()
