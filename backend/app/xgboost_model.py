import sqlite3
import pandas as pd
import numpy as np
import os
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from datetime import datetime

# === CONFIG ===
DB_PATH = "./data/training.db"
TABLE_NAME = "setAlpha"
TEST_SIZE = 0.2
RANDOM_STATE = 42

def main():
    # Get user input for model type
    print("🌲 XGBoost Model Training")
    print("Choose prediction target:")
    print("  'spread' - Predict point differential (pt_diff)")
    print("  'total'  - Predict total points (pt_total)")
    
    while True:
        model_type = input("\nEnter 'spread' or 'total': ").strip().lower()
        if model_type in ['spread', 'total']:
            break
        print("❌ Invalid input. Please enter 'spread' or 'total'")
    
    # Set target variable and labels based on user choice
    if model_type == 'spread':
        TARGET = "pt_diff"
        model_name = "Point Spread"
        file_prefix = "xgb_spread"
    else:
        TARGET = "pt_total"
        model_name = "Total Points"
        file_prefix = "xgb_total"
    
    print(f"\n🚀 Starting XGBoost {model_name} Model Training")
    print("🔹 Loading data...")
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(f"SELECT * FROM {TABLE_NAME}", conn)
    conn.close()
    print(f"✅ Loaded {len(df):,} rows and {len(df.columns)} columns.")

    # === FEATURE / TARGET SPLIT ===
    drop_cols = [
        "id", "home_team", "away_team", "home_id", "away_id", "win_loss",
        "pt_diff", "pt_total", "date", "home_score", "away_score", "season"
    ]
    feature_cols = [c for c in df.columns if c not in drop_cols]
    X = df[feature_cols]
    y = df[TARGET]

    # Ensure numeric dtypes
    X = X.apply(pd.to_numeric, errors="coerce").fillna(0)
    y = pd.to_numeric(y, errors="coerce").fillna(0)

    print(f"✅ Using {len(feature_cols)} features for {model_name.lower()} prediction.")

    # === TRAIN / TEST SPLIT ===
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE
    )
    print(f"🔹 Train size: {len(X_train):,}, Test size: {len(X_test):,}")

    # === MODEL SETUP ===
    model = xgb.XGBRegressor(
        n_estimators=800,
        learning_rate=0.03,
        max_depth=6,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_lambda=1.0,
        random_state=RANDOM_STATE,
        n_jobs=-1,
        tree_method="hist",  # efficient on CPU
    )

    # === TRAIN MODEL ===
    print(f"🚀 Training XGBoost {model_name.lower()} model...")
    model.fit(X_train, y_train)
    print("✅ Model training complete.")

    # === PREDICT & EVALUATE ===
    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    mse = mean_squared_error(y_test, y_pred)
    rmse = np.sqrt(mse)
    r2 = r2_score(y_test, y_pred)

    print(f"\n📊 === {model_name.upper()} MODEL EVALUATION ===")
    print(f"R²:   {r2:.4f}")
    print(f"MAE:  {mae:.4f}")
    print(f"RMSE: {rmse:.4f}")

    # === FEATURE IMPORTANCE ===
    importance = model.get_booster().get_score(importance_type="weight")
    imp_df = (
        pd.DataFrame.from_dict(importance, orient="index", columns=["importance"])
        .sort_values("importance", ascending=False)
    )
    imp_df.index.name = "feature"
    imp_df.reset_index(inplace=True)

    # Create unique filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs("output", exist_ok=True)
    out_path = f"output/{timestamp}_{file_prefix}_importance.csv"
    imp_df.to_csv(out_path, index=False)
    print(f"\n🧠 Top 10 important features:")
    print(imp_df.head(10).to_string(index=False))
    
    print(f"\n🎉 XGBoost {model_name.lower()} model training complete!")
    print(f"📁 Feature importance saved to: {out_path}")

if __name__ == "__main__":
    main()
