import sqlite3
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import numpy as np
import os
from datetime import datetime

# === PATHS ===
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
TRAIN_DB_PATH = os.path.join(BACKEND_DIR, "data", "training.db")
PREDICT_DB_PATH = os.path.join(BACKEND_DIR, "data", "predict.db")
TRAIN_TABLE = "setAlpha"

# === CORE TRAINING + PREDICTION ===
def run_model(model_type, target_table):
    """Train linear regression model, evaluate, then predict using targetSet."""
    if model_type == "spread":
        TARGET = "pt_diff"
        model_name = "Point Spread"
    else:
        TARGET = "pt_total"
        model_name = "Total Points"

    # --- Load training data ---
    conn_train = sqlite3.connect(TRAIN_DB_PATH)
    df_train = pd.read_sql(f"SELECT * FROM {TRAIN_TABLE}", conn_train)
    conn_train.close()

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
    conn_pred = sqlite3.connect(PREDICT_DB_PATH)
    df_target = pd.read_sql(f"SELECT * FROM {target_table}", conn_pred)

    # Match feature columns (fill missing with 0)
    for col in feature_cols:
        if col not in df_target.columns:
            df_target[col] = 0

    X_target = df_target[feature_cols].apply(pd.to_numeric, errors="coerce").fillna(0)

    # --- Make predictions ---
    predictions = model.predict(X_target)
    df_target[f"pred_{TARGET}"] = predictions

    # --- Save predictions ---
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_table = f"predictions_linear_{model_type}_{timestamp}"
    df_target[[
        "game_id", "commence_time", "season", "home_team", "away_team",
        f"pred_{TARGET}"
    ]].to_sql(out_table, conn_pred, if_exists="replace", index=False)

    conn_pred.close()
    print(f"✅ {len(df_target)} {model_name.lower()} predictions saved to table: {out_table}")
    
    return df_target

def display_all_predictions(df_with_spread, df_with_total):
    """Display all predictions sorted by game time with betting picks"""
    print(f"\n🎯 === ALL GAME PREDICTIONS ===")
    
    # Sort by commence_time
    df_combined = df_with_spread.sort_values('commence_time')
    
    for _, row in df_combined.iterrows():
        # Find corresponding total prediction
        total_row = df_with_total[df_with_total['game_id'] == row['game_id']].iloc[0]
        
        print(f"\n{row['home_team']} vs {row['away_team']}")
        
        # Spread prediction and pick
        pred_spread = row['pred_pt_diff']
        if pred_spread > 0:
            print(f"  Prediction: {row['home_team']} by {pred_spread:.1f}")
        else:
            print(f"  Prediction: {row['away_team']} by {abs(pred_spread):.1f}")
        
        # Spread pick vs betting line
        if pd.notna(row['fd_home_spread']):
            home_spread = row['fd_home_spread']
            cover_margin = pred_spread + home_spread  # Key formula
            if cover_margin > 0:  # Home team covers
                print(f"  Pick: {row['home_team']} {home_spread:+.1f}")
            else:  # Away team covers
                print(f"  Pick: {row['away_team']} {-home_spread:+.1f}")
        
        # Total prediction and pick
        pred_total = total_row['pred_pt_total']
        print(f"  Total prediction: {pred_total:.1f}")
        
        # Total pick vs betting line
        if pd.notna(row['fd_over']):
            if pred_total > row['fd_over']:
                print(f"  Pick: Over {row['fd_over']:.1f}")
            else:
                print(f"  Pick: Under {row['fd_over']:.1f}")

# === MAIN ===
def main():
    print("🏀 Linear Regression Model Training + Prediction")
    
    # Get today's date for default table name
    today_table = f"targetSet_{datetime.now().strftime('%m%d%Y')}"
    
    # Prompt user for target table
    print(f"\nDefault target table: {today_table}")
    response = input(f"Use this table? (y/n): ").lower().strip()
    
    if response == 'y':
        target_table = today_table
    else:
        target_table = input("Enter target table name: ").strip()
    
    print(f"\n🎯 Using target table: {target_table}")
    
    # Verify table exists
    conn = sqlite3.connect(PREDICT_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name = ?", (target_table,))
    if not cursor.fetchone():
        print(f"❌ Table {target_table} not found in predict.db")
        conn.close()
        return
    conn.close()
    
    # Run both models and get predictions
    df_spread = run_model("spread", target_table)
    df_total = run_model("total", target_table)
    
    # Display all predictions with picks
    display_all_predictions(df_spread, df_total)
    
    print("\n🎯 Predictions complete and saved to predict.db!")

if __name__ == "__main__":
    main()
