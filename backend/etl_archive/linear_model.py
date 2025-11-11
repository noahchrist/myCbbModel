import sqlite3
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import numpy as np
import os
from datetime import datetime

# === CONFIG ===
DB_PATH = "./data/training.db"
TABLE_NAME = "setAlpha"

def main():
    # Get user input for model type
    print("🏀 Linear Regression Model Training")
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
        file_prefix = "linear_spread"
    else:
        TARGET = "pt_total"
        model_name = "Total Points"
        file_prefix = "linear_total"
    
    print(f"\n🚀 Starting Linear Regression {model_name} Model Training")
    print("🔹 Step 1/6: Loading data from database...")
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(f"SELECT * FROM {TABLE_NAME}", conn)
    conn.close()
    print(f"✅ Loaded {len(df):,} rows and {len(df.columns)} columns.")

    # === FEATURE / TARGET SPLIT ===
    print("🔹 Step 2/6: Preparing features and target variable...")
    # Drop ID and non-numeric columns that shouldn't be features
    drop_cols = [
        "id", "home_id", "away_id", "home_score", "away_score", "home_team", "away_team", "win_loss",
        "pt_diff", "pt_total", "date", "season"
    ]
    feature_cols = [c for c in df.columns if c not in drop_cols]
    X = df[feature_cols]
    y = df[TARGET]

    # Ensure numeric dtypes and handle missing values
    X = X.apply(pd.to_numeric, errors="coerce")
    y = pd.to_numeric(y, errors="coerce")
    
    # Check for missing values
    missing_features = X.isnull().sum().sum()
    missing_target = y.isnull().sum()
    if missing_features > 0 or missing_target > 0:
        print(f"⚠️  Found {missing_features} missing feature values, {missing_target} missing target values")
    
    X = X.fillna(0)
    y = y.fillna(0)

    print(f"✅ Prepared {len(feature_cols)} training features.")

    # === SPLIT DATA ===
    print("🔹 Step 3/6: Splitting data into train/test sets...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    print(f"✅ Split complete - Train: {len(X_train):,}, Test: {len(X_test):,}")

    # === TRAIN MODEL ===
    print("🔹 Step 4/6: Training linear regression model...")
    model = LinearRegression()
    model.fit(X_train, y_train)
    print("✅ Model training complete.")

    # === PREDICT & EVALUATE ===
    print("🔹 Step 5/6: Making predictions and evaluating performance...")
    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    mse = mean_squared_error(y_test, y_pred)
    rmse = np.sqrt(mse)
    r2 = r2_score(y_test, y_pred)

    print(f"\n📊 === {model_name.upper()} MODEL EVALUATION ===")
    print(f"R²:   {r2:.4f}")
    print(f"MAE:  {mae:.4f}")
    print(f"RMSE: {rmse:.4f}")

    # === FEATURE IMPORTANCE (COEFFICIENTS) ===
    print("🔹 Step 6/6: Analyzing feature importance and saving results...")
    coef_df = pd.DataFrame({
        "feature": feature_cols,
        "coef": model.coef_
    }).sort_values("coef", ascending=False)

    # Create unique filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs("output", exist_ok=True)
    coef_path = f"output/{timestamp}_{file_prefix}_coefficients.csv"
    coef_df.to_csv(coef_path, index=False)
    print(f"\n🧠 Top 25 positive coefficients:")
    print(coef_df.head(25).to_string(index=False))

    print(f"\n🧩 Coefficients saved to: {coef_path}")
    
    # === SAMPLE PREDICTIONS ===
    print(f"\n🎯 Sample predictions vs actual:")
    sample_df = pd.DataFrame({
        'Actual': y_test.head(10).values,
        'Predicted': y_pred[:10],
        'Difference': np.abs(y_test.head(10).values - y_pred[:10])
    })
    print(sample_df.to_string(index=False))
    
    print(f"\n🎉 Linear regression {model_name.lower()} model training complete!")
    print(f"📁 Results saved to: {coef_path}")

if __name__ == "__main__":
    main()