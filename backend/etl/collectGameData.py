#!/usr/bin/env python3
"""
NCAA Basketball Game Data Collection Script

Install dependencies:
pip install kagglehub[pandas-datasets] pandas sqlalchemy

Usage:
python backend/etl/collectGameData.py [--table games_raw] [--db backend/data/master.db] [--if-exists replace]
"""

import argparse
import sys
from pathlib import Path
import pandas as pd
import kagglehub
import sqlite3
from sqlalchemy import create_engine


def normalize_column_names(df_columns):
    """Map source column names to target names with case-insensitive lookup."""
    column_mapping = {}
    target_columns = {
        'team_name': ['team', 'team_name', 'teamname'],
        'date': ['date', 'data', 'game_date', 'gamedate'],
        'site': ['site', 'location', 'venue'],
        'opp_name': ['opp_name', 'opponent', 'opp', 'opposing_team'],
        'w_l': ['w_l', 'wl', 'result', 'win_loss'],
        'pts': ['pts', 'points', 'score', 'team_score'],
        'opp_pts': ['opp_pts', 'opp_points', 'opponent_points', 'opp_score']
    }
    
    for target, candidates in target_columns.items():
        found = False
        for col in df_columns:
            if col.lower().strip() in [c.lower() for c in candidates]:
                column_mapping[col] = target
                found = True
                break
        if not found:
            return None, target
    
    return column_mapping, None


def clean_data(df):
    """Perform light cleaning on the dataframe."""
    # Trim whitespace on string columns
    string_cols = df.select_dtypes(include=['object']).columns
    for col in string_cols:
        df[col] = df[col].astype(str).str.strip()
    
    # Parse date column
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
    
    # Cast numeric columns
    for col in ['pts', 'opp_pts']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    return df


def main():
    parser = argparse.ArgumentParser(description='Collect NCAA basketball game data')
    parser.add_argument('--table', default='games_raw', help='SQLite table name')
    parser.add_argument('--db', default='backend/data/master.db', help='SQLite database path')
    parser.add_argument('--if-exists', default='replace', choices=['replace', 'append'], help='How to handle existing table')
    args = parser.parse_args()

    print("Starting NCAA basketball data collection...")
    
    # Download dataset
    try:
        print("Downloading dataset from Kaggle...")
        path = kagglehub.dataset_download("nateduncan/2011current-ncaa-basketball-games")
        print(f"Dataset downloaded to: {path}")
    except Exception as e:
        print(f"Error downloading dataset: {e}")
        print("Note: You may need to configure Kaggle credentials.")
        print("Visit: https://www.kaggle.com/docs/api#authentication")
        sys.exit(1)
    
    # Find CSV files
    dataset_path = Path(path)
    csv_files = list(dataset_path.glob("*.csv"))
    
    if not csv_files:
        print(f"No CSV files found in {dataset_path}")
        sys.exit(1)
    
    print(f"Found {len(csv_files)} CSV file(s): {[f.name for f in csv_files]}")
    
    # Load and process CSV files
    dataframes = []
    total_rows_before = 0
    
    for csv_file in csv_files:
        print(f"Loading {csv_file.name}...")
        try:
            df = pd.read_csv(csv_file)
            total_rows_before += len(df)
            print(f"  Loaded {len(df)} rows from {csv_file.name}")
            
            # Map column names
            column_mapping, missing_col = normalize_column_names(df.columns)
            if column_mapping is None:
                print(f"Error: Required column '{missing_col}' not found in {csv_file.name}")
                print(f"Available columns: {list(df.columns)}")
                sys.exit(1)
            
            # Select and rename columns
            df_selected = df[list(column_mapping.keys())].rename(columns=column_mapping)
            
            # Reorder columns to match requirements
            target_order = ['team_name', 'date', 'site', 'opp_name', 'w_l', 'pts', 'opp_pts']
            df_selected = df_selected[target_order]
            
            dataframes.append(df_selected)
            
        except Exception as e:
            print(f"Error processing {csv_file.name}: {e}")
            sys.exit(1)
    
    # Concatenate all dataframes
    if len(dataframes) > 1:
        print("Concatenating multiple CSV files...")
        combined_df = pd.concat(dataframes, ignore_index=True)
        # Drop exact duplicates
        combined_df = combined_df.drop_duplicates()
        print(f"Combined {total_rows_before} rows into {len(combined_df)} unique rows")
    else:
        combined_df = dataframes[0]
        print(f"Using single CSV with {len(combined_df)} rows")
    
    # Clean data
    print("Cleaning data...")
    combined_df = clean_data(combined_df)
    
    # Create output directory
    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Created directory: {db_path.parent}")
    
    # Save to SQLite
    print(f"Saving to SQLite database: {args.db}")
    engine = create_engine(f'sqlite:///{args.db}')
    
    try:
        combined_df.to_sql(args.table, engine, if_exists=args.if_exists, index=False)
        print(f"Successfully wrote {len(combined_df)} rows to table '{args.table}'")
    except Exception as e:
        print(f"Error writing to database: {e}")
        sys.exit(1)
    
    # Verify data was written
    try:
        with sqlite3.connect(args.db) as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {args.table}")
            row_count = cursor.fetchone()[0]
            print(f"Verification: {row_count} rows confirmed in database")
    except Exception as e:
        print(f"Warning: Could not verify row count: {e}")
    
    # Print summary
    print("\nData Summary:")
    print(f"Rows saved: {len(combined_df)}")
    print("\nFirst 5 rows:")
    print(combined_df.head().to_string(index=False))
    
    print("\nData collection completed successfully!")


if __name__ == "__main__":
    main()