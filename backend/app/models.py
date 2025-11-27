from pydantic import BaseModel
from fastapi import HTTPException
import sqlite3
import os
import random
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
import joblib
from dotenv import load_dotenv

load_dotenv()

class ModelCreate(BaseModel):
    modelName: str
    bettingStyle: str
    tenDigit: int
    weights: dict
    rejectedNames: list

async def get_model_names():
    db_path = os.environ.get('DB_PATH') or os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'master.db'))
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT modelName FROM modelNames WHERE userId IS NULL ORDER BY RANDOM() LIMIT 5")
    names = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    return {"names": names}

async def get_user_models(user_id: str):
    db_path = os.environ.get('DB_PATH') or os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'master.db'))
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute(
        """SELECT m.id, m.modelName, m.dateCreated, m.bettingStyle, m.tenDigit,
           COUNT(p.predictionId) as totalPredictions,
           SUM(CASE WHEN p.unitsWon > 0 THEN 1 ELSE 0 END) as wins,
           SUM(CASE WHEN p.unitsWon < 0 THEN 1 ELSE 0 END) as losses,
           SUM(p.unitsWon) as unitsWon,
           SUM(p.unitsBet) as unitsBet,
           m.weightGenOff, m.weightGenDef, m.weightPace, m.weightThrees, m.weightFts,
           m.weightPerDef, m.weightIntDef, m.weightBoards, m.weightPlaymaking, m.weightIntangibles
           FROM modelDetails m
           LEFT JOIN modelPredictions p ON m.id = p.modelId
           WHERE m.userId = ?
           GROUP BY m.id""",
        (user_id,)
    )
    
    models = []
    for row in cursor.fetchall():
        model_id, name, created, style, ten_digit, total, wins, losses, units_won, units_bet, w_gen_off, w_gen_def, w_pace, w_threes, w_fts, w_per_def, w_int_def, w_boards, w_playmaking, w_intangibles = row
        roi = (units_won / units_bet * 100) if units_bet and units_won and units_bet > 0 else 0
        
        models.append({
            "id": model_id,
            "modelName": name,
            "dateCreated": created,
            "bettingStyle": style,
            "tenDigit": ten_digit,
            "featuredPick": "TBD",
            "wins": wins or 0,
            "losses": losses or 0,
            "unitsWon": round(units_won or 0, 2),
            "roi": round(roi, 1),
            "weights": {
                "weightGenOff": w_gen_off or 0,
                "weightGenDef": w_gen_def or 0,
                "weightPace": w_pace or 0,
                "weightThrees": w_threes or 0,
                "weightFts": w_fts or 0,
                "weightPerDef": w_per_def or 0,
                "weightIntDef": w_int_def or 0,
                "weightBoards": w_boards or 0,
                "weightPlaymaking": w_playmaking or 0,
                "weightIntangibles": w_intangibles or 0
            }
        })
    
    conn.close()
    return {"models": models}

async def create_model(request: ModelCreate, user_id: str):
    try:
        print(f"Creating model for user: {user_id}")
        print(f"Request data: {request.dict()}")
        
        db_path = os.environ.get('DB_PATH') or os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'master.db'))
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check user role and model count
        cursor.execute("SELECT role FROM users WHERE id = ?", (user_id,))
        user_role = cursor.fetchone()
        is_admin = user_role and user_role[0] == 'admin'
        print(f"User role: {user_role}, is_admin: {is_admin}")
        
        if not is_admin:
            cursor.execute("SELECT COUNT(*) FROM modelDetails WHERE userId = ?", (user_id,))
            model_count = cursor.fetchone()[0]
            print(f"Current model count: {model_count}")
            if model_count >= 2:
                conn.close()
                raise HTTPException(status_code=400, detail="You are only allowed 2 models, either delete or edit an existing model")
        
        # Generate unique model seed
        while True:
            model_seed = random.randint(100, 999)
            cursor.execute("SELECT modelSeed FROM modelDetails WHERE modelSeed = ?", (model_seed,))
            if not cursor.fetchone():
                break
        print(f"Generated model seed: {model_seed}")
        
        # Load training data and fit models
        print("Loading training data...")
        df_train = pd.read_sql("SELECT * FROM setAlpha", conn)
        print(f"Training data shape: {df_train.shape}")
        
        drop_cols = ["id", "home_id", "away_id", "home_score", "away_score", "home_team", "away_team", "win_loss", "pt_diff", "pt_total", "date", "season"]
        feature_cols = [c for c in df_train.columns if c not in drop_cols]
        print(f"Feature columns: {len(feature_cols)}")
        
        X = df_train[feature_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
        
        # Fit spread model (pt_diff)
        y_spread = pd.to_numeric(df_train["pt_diff"], errors="coerce").fillna(0)
        X_train, X_test, y_train_spread, y_test_spread = train_test_split(X, y_spread, test_size=0.2, random_state=model_seed)
        model_spread = LinearRegression()
        model_spread.fit(X_train, y_train_spread)
        print("Spread model fitted successfully")
        
        # Fit total model (pt_total)
        y_total = pd.to_numeric(df_train["pt_total"], errors="coerce").fillna(0)
        _, _, y_train_total, y_test_total = train_test_split(X, y_total, test_size=0.2, random_state=model_seed)
        model_total = LinearRegression()
        model_total.fit(X_train, y_train_total)
        print("Total model fitted successfully")
        
        # Save models to joblib files
        model_fits_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'modelFits'))
        spread_filename = f"modelSpread_{model_seed}.joblib"
        total_filename = f"modelTotal_{model_seed}.joblib"
        spread_path = os.path.join(model_fits_dir, spread_filename)
        total_path = os.path.join(model_fits_dir, total_filename)
        
        joblib.dump(model_spread, spread_path)
        joblib.dump(model_total, total_path)
        print(f"Spread model saved to: {spread_path}")
        print(f"Total model saved to: {total_path}")
        
        # Insert model details with both paths separated by semicolon
        print("Inserting model details...")
        combined_paths = f"{spread_path};{total_path}"
        cursor.execute(
            """INSERT INTO modelDetails 
               (userId, modelName, dateCreated, modelSeed, bettingStyle, tenDigit, modelPath,
                weightGenOff, weightGenDef, weightPace, weightThrees, weightFts, 
                weightPerDef, weightIntDef, weightBoards, weightPlaymaking, weightIntangibles) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, request.modelName, datetime.now(ZoneInfo("America/New_York")).isoformat(), model_seed, 
             request.bettingStyle, request.tenDigit, combined_paths,
             request.weights['weightGenOff'], request.weights['weightGenDef'], 
             request.weights['weightPace'], request.weights['weightThrees'], 
             request.weights['weightFts'], request.weights['weightPerDef'], 
             request.weights['weightIntDef'], request.weights['weightBoards'], 
             request.weights['weightPlaymaking'], request.weights['weightIntangibles'])
        )
        
        cursor.execute("UPDATE modelNames SET userId = ? WHERE modelName = ?", (user_id, request.modelName))
        
        for rejected_name in request.rejectedNames:
            cursor.execute(
                "UPDATE modelNames SET timesRejected = timesRejected + 1 WHERE modelName = ?", 
                (rejected_name,)
            )
        
        conn.commit()
        conn.close()
        print("Model created successfully")
        
        return {"message": "Model created successfully", "modelSeed": model_seed}
        
    except Exception as e:
        print(f"Error creating model: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        if 'conn' in locals():
            conn.close()
        raise HTTPException(status_code=500, detail=f"Error creating model: {str(e)}")

async def get_community_models():
    db_path = os.environ.get('DB_PATH') or os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'master.db'))
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute(
        """SELECT m.id, m.modelName, u.displayName, m.dateCreated, m.bettingStyle, m.tenDigit,
           COUNT(p.predictionId) as totalPredictions,
           SUM(CASE WHEN p.unitsWon > 0 THEN 1 ELSE 0 END) as wins,
           SUM(CASE WHEN p.unitsWon < 0 THEN 1 ELSE 0 END) as losses,
           SUM(p.unitsWon) as unitsWon,
           SUM(p.unitsBet) as unitsBet
           FROM modelDetails m
           LEFT JOIN users u ON m.userId = u.id
           LEFT JOIN modelPredictions p ON m.id = p.modelId
           GROUP BY m.id
           ORDER BY SUM(p.unitsWon) DESC"""
    )
    
    models = []
    for row in cursor.fetchall():
        model_id, name, user, created, style, ten_digit, total, wins, losses, units_won, units_bet = row
        roi = (units_won / units_bet * 100) if units_bet and units_won and units_bet > 0 else 0
        
        models.append({
            "id": model_id,
            "modelName": name,
            "userName": user or "Anonymous",
            "dateCreated": created,
            "bettingStyle": style,
            "tenDigit": ten_digit,
            "wins": wins or 0,
            "losses": losses or 0,
            "unitsWon": round(units_won or 0, 2),
            "roi": round(roi, 1)
        })
    
    conn.close()
    return {"models": models}

async def delete_model(model_id: int, user_id: str):
    try:
        db_path = os.environ.get('DB_PATH') or os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'master.db'))
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get model details
        cursor.execute("SELECT modelName, modelPath FROM modelDetails WHERE id = ? AND userId = ?", (model_id, user_id))
        result = cursor.fetchone()
        if not result:
            conn.close()
            raise HTTPException(status_code=404, detail="Model not found")
        
        model_name, combined_paths = result
        
        # Delete joblib files
        if combined_paths:
            if ';' in combined_paths:
                # New format with both spread and total paths
                spread_path, total_path = combined_paths.split(';')
                
                if spread_path and os.path.exists(spread_path):
                    os.remove(spread_path)
                    print(f"Deleted spread model file: {spread_path}")
                
                if total_path and os.path.exists(total_path):
                    os.remove(total_path)
                    print(f"Deleted total model file: {total_path}")
            elif os.path.exists(combined_paths):
                # Old single-path format
                os.remove(combined_paths)
                print(f"Deleted model file: {combined_paths}")
        
        # Delete from database tables
        cursor.execute("DELETE FROM modelPredictions WHERE modelId = ?", (model_id,))
        cursor.execute("DELETE FROM modelDetails WHERE id = ? AND userId = ?", (model_id, user_id))
        cursor.execute("UPDATE modelNames SET userId = NULL WHERE modelName = ? AND userId = ?", (model_name, user_id))
        
        conn.commit()
        conn.close()
        
        return {"message": "Model deleted successfully"}
        
    except Exception as e:
        print(f"Error deleting model: {str(e)}")
        if 'conn' in locals():
            conn.close()
        raise HTTPException(status_code=500, detail=f"Error deleting model: {str(e)}")

async def get_model_history(model_id: int, user_id: str = None):
    db_path = os.environ.get('DB_PATH')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Verify model exists (no ownership check for community viewing)
    cursor.execute("SELECT id FROM modelDetails WHERE id = ?", (model_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Model not found")
    
    # Get prediction history with all needed fields
    cursor.execute("""
        SELECT datePredicted, home_team, away_team, bet_type, predicted_pt_diff, predicted_pt_total,
               fd_home_spread, fd_home_spreadPrice, fd_away_spread, fd_away_spreadPrice,
               fd_over, fd_overPrice, fd_under, fd_underPrice, unitsBet, unitsWon, w_l
        FROM modelPredictions 
        WHERE modelId = ? AND is_completed = 1
        ORDER BY datePredicted DESC
    """, (model_id,))
    
    predictions = []
    for row in cursor.fetchall():
        date, home_team, away_team, bet_type, pred_diff, pred_total, home_spread, home_price, away_spread, away_price, over_line, over_price, under_line, under_price, units_bet, units_won, w_l = row
        
        if bet_type == 'spread':
            # Determine which team was picked
            if pred_diff + home_spread > 0:
                team_pick = f"{home_team} {home_spread:+.1f}"
                price = home_price
            else:
                team_pick = f"{away_team} {away_spread:+.1f}"
                price = away_price
        else:  # bet_type == 'total'
            # Determine over/under pick
            if pred_total > over_line:
                team_pick = f"Over {over_line}"
                price = over_price
            else:
                team_pick = f"Under {under_line}"
                price = under_price
        
        predictions.append({
            "date": date,
            "teamPick": team_pick,
            "price": price,
            "unitsWon": units_won,
            "result": w_l
        })
    
    conn.close()
    return {"predictions": predictions}

async def get_todays_top_picks(date: str):
    db_path = os.environ.get('DB_PATH')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all predictions for the specified date with game_id, summary, teams, edge, w_l, and all prices
    cursor.execute("""
        SELECT game_id, summary, edge, home_team, away_team, w_l,
               fd_home_spreadPrice, fd_away_spreadPrice, fd_overPrice, fd_underPrice
        FROM modelPredictions 
        WHERE datePredicted = ?
    """, (date,))
    
    bets = []
    for row in cursor.fetchall():
        game_id, summary, edge, home_team, away_team, w_l, home_spread_price, away_spread_price, over_price, under_price = row
        
        # Extract pick from summary (text after 'Pick:')
        pick = ""
        if summary and "Pick:" in summary:
            pick = summary.split("Pick:")[1].strip()
        
        bets.append({
            "gameId": game_id,
            "pick": pick,
            "edge": edge,
            "homeTeam": home_team,
            "awayTeam": away_team,
            "wl": w_l,
            "prices": {
                "homeSpread": home_spread_price,
                "awaySpread": away_spread_price,
                "over": over_price,
                "under": under_price
            }
        })
    
    conn.close()
    return {"bets": bets}

