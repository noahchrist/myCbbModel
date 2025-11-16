from pydantic import BaseModel
from fastapi import HTTPException
import sqlite3
import os
import random
from datetime import datetime
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
import joblib

class ModelCreate(BaseModel):
    modelName: str
    bettingStyle: str
    tenDigit: int
    weights: dict
    rejectedNames: list

async def get_model_names():
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'master.db'))
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT modelName FROM modelNames WHERE userId IS NULL ORDER BY RANDOM() LIMIT 5")
    names = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    return {"names": names}

async def get_user_models(user_id: str):
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'master.db'))
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute(
        """SELECT m.id, m.modelName, m.dateCreated, m.bettingStyle, m.tenDigit,
           COUNT(p.predictionId) as totalPredictions,
           SUM(CASE WHEN p.unitsWon > 0 THEN 1 ELSE 0 END) as wins,
           SUM(CASE WHEN p.unitsWon < 0 THEN 1 ELSE 0 END) as losses,
           SUM(p.unitsWon) as unitsWon,
           SUM(p.unitsBet) as unitsBet
           FROM modelDetails m
           LEFT JOIN modelPredictions p ON m.id = p.modelId
           WHERE m.userId = ?
           GROUP BY m.id""",
        (user_id,)
    )
    
    models = []
    for row in cursor.fetchall():
        model_id, name, created, style, ten_digit, total, wins, losses, units_won, units_bet = row
        roi = (units_won / units_bet * 100) if units_bet and units_bet > 0 else 0
        
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
            "roi": round(roi, 1)
        })
    
    conn.close()
    return {"models": models}

async def create_model(request: ModelCreate, user_id: str):
    try:
        print(f"Creating model for user: {user_id}")
        print(f"Request data: {request.dict()}")
        
        db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'master.db'))
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
        
        # Load training data and fit model
        print("Loading training data...")
        df_train = pd.read_sql("SELECT * FROM setAlpha", conn)
        print(f"Training data shape: {df_train.shape}")
        
        drop_cols = ["id", "home_id", "away_id", "home_score", "away_score", "home_team", "away_team", "win_loss", "pt_diff", "pt_total", "date", "season"]
        feature_cols = [c for c in df_train.columns if c not in drop_cols]
        print(f"Feature columns: {len(feature_cols)}")
        
        X = df_train[feature_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
        y = pd.to_numeric(df_train["pt_diff"], errors="coerce").fillna(0)
        print(f"X shape: {X.shape}, y shape: {y.shape}")
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=model_seed)
        model = LinearRegression()
        model.fit(X_train, y_train)
        print("Model fitted successfully")
        
        # Save model to joblib file
        model_fits_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'modelFits'))
        model_filename = f"model_{model_seed}.joblib"
        model_path = os.path.join(model_fits_dir, model_filename)
        joblib.dump(model, model_path)
        print(f"Model saved to: {model_path}")
        
        # Insert model details with path
        print("Inserting model details...")
        cursor.execute(
            """INSERT INTO modelDetails 
               (userId, modelName, dateCreated, modelSeed, bettingStyle, tenDigit, modelPath,
                weightGenOff, weightGenDef, weightPace, weightThrees, weightFts, 
                weightPerDef, weightIntDef, weightBoards, weightPlaymaking, weightIntangibles) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, request.modelName, datetime.now().isoformat(), model_seed, 
             request.bettingStyle, request.tenDigit, model_path,
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
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'master.db'))
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
        roi = (units_won / units_bet * 100) if units_bet and units_bet > 0 else 0
        
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

async def get_model_history(model_id: int, user_id: str = None):
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'master.db'))
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Verify model exists (no ownership check for community viewing)
    cursor.execute("SELECT id FROM modelDetails WHERE id = ?", (model_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Model not found")
    
    # Get prediction history
    cursor.execute("""
        SELECT datePredicted, home_team, away_team, fd_home_spread, fd_home_spreadPrice, 
               fd_away_spread, fd_away_spreadPrice, predicted_pt_diff, unitsBet, unitsWon, w_l
        FROM modelPredictions 
        WHERE modelId = ? AND is_completed = 1
        ORDER BY datePredicted DESC
    """, (model_id,))
    
    predictions = []
    for row in cursor.fetchall():
        date, home_team, away_team, home_spread, home_price, away_spread, away_price, pred_diff, units_bet, units_won, w_l = row
        
        # Determine which team was picked and format display
        if pred_diff + home_spread > 0:
            # Picked home team
            team_pick = f"{home_team} {home_spread:+.1f}"
            price = home_price
        else:
            # Picked away team  
            team_pick = f"{away_team} {away_spread:+.1f}"
            price = away_price
        
        predictions.append({
            "date": date,
            "teamPick": team_pick,
            "price": price,
            "unitsWon": units_won,
            "result": w_l
        })
    
    conn.close()
    return {"predictions": predictions}

async def delete_model(model_id: int, user_id: str):
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'master.db'))
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT modelName, modelPath FROM modelDetails WHERE id = ? AND userId = ?", (model_id, user_id))
    result = cursor.fetchone()
    if not result:
        conn.close()
        raise HTTPException(status_code=404, detail="Model not found")
    
    model_name, model_path = result
    
    # Delete joblib file if it exists
    if model_path and os.path.exists(model_path):
        try:
            os.remove(model_path)
            print(f"Deleted model file: {model_path}")
        except Exception as e:
            print(f"Error deleting model file {model_path}: {e}")
    
    cursor.execute("DELETE FROM modelPredictions WHERE modelId = ?", (model_id,))
    cursor.execute("DELETE FROM modelDetails WHERE id = ? AND userId = ?", (model_id, user_id))
    cursor.execute("UPDATE modelNames SET userId = NULL WHERE modelName = ? AND userId = ?", (model_name, user_id))
    
    conn.commit()
    conn.close()
    
    return {"message": "Model deleted successfully"}