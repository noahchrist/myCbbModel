import sqlite3
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import numpy as np
import os
from dotenv import load_dotenv

load_dotenv()

MASTER_DB_PATH = os.path.expanduser("~/Documents/projectsArchive/myCbbModelArchive/mastercopy013026.db")
TRAIN_TABLE = "setTarget2026"

def evaluate_model(model_type):
    """Train and evaluate model on completed games"""
    if model_type == "spread":
        TARGET = "pt_diff"
        model_name = "Point Spread"
    else:
        TARGET = "pt_total"
        model_name = "Total Points"

    # Load training data (only completed games with scores)
    conn = sqlite3.connect(MASTER_DB_PATH)
    df_train = pd.read_sql(f"SELECT * FROM {TRAIN_TABLE} WHERE pt_diff IS NOT NULL AND pt_total IS NOT NULL", conn)
    conn.close()
    
    print(f"\n📚 Training {model_name} model on {len(df_train)} completed games")

    # Drop non-feature columns (keep is_home and is_neutral as features)
    drop_cols = [
        "game_id", "home_kpid", "away_kpid", "home_score", "away_score", "home_team", "away_team",
        "win_loss", "pt_diff", "pt_total", "date", "season", "game_date"
    ]
    feature_cols = [c for c in df_train.columns if c not in drop_cols]
    X = df_train[feature_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
    y = pd.to_numeric(df_train[TARGET], errors="coerce").fillna(0)
    
    # Check is_home and is_neutral values
    if 'is_home' in feature_cols:
        print(f"  is_home values: {X['is_home'].value_counts().to_dict()}")
    if 'is_neutral' in feature_cols:
        print(f"  is_neutral values: {X['is_neutral'].value_counts().to_dict()}")

    # Split and train
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = LinearRegression()
    model.fit(X_train, y_train)

    # Evaluate
    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    mse = mean_squared_error(y_test, y_pred)
    rmse = np.sqrt(mse)
    r2 = r2_score(y_test, y_pred)

    print(f"\n📊 === {model_name.upper()} MODEL EVALUATION ===")
    print(f"Training samples: {len(X_train)}")
    print(f"Test samples: {len(X_test)}")
    print(f"R²:   {r2:.4f}")
    print(f"MAE:  {mae:.4f}")
    print(f"RMSE: {rmse:.4f}")

def main():
    print("🏀 Linear Regression Model Evaluation (Current Season)")
    print("="*60)
    
    # Evaluate both models
    evaluate_model("spread")
    evaluate_model("total")
    
    print("\n✅ Evaluation complete!")

if __name__ == "__main__":
    main()
