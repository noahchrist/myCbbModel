from pydantic import BaseModel
from fastapi import HTTPException
import sqlite3
import os
import random
from datetime import datetime

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
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'master.db'))
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    while True:
        model_seed = random.randint(100, 999)
        cursor.execute("SELECT modelSeed FROM modelDetails WHERE modelSeed = ?", (model_seed,))
        if not cursor.fetchone():
            break
    
    cursor.execute(
        """INSERT INTO modelDetails 
           (userId, modelName, dateCreated, modelSeed, bettingStyle, tenDigit, 
            weightGenOff, weightGenDef, weightPace, weightThrees, weightFts, 
            weightPerDef, weightIntDef, weightBoards, weightPlaymaking, weightIntangibles) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, request.modelName, datetime.now().isoformat(), model_seed, 
         request.bettingStyle, request.tenDigit,
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
    
    return {"message": "Model created successfully", "modelSeed": model_seed}

async def get_community_models():
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'master.db'))
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute(
        """SELECT m.modelName, u.displayName, m.dateCreated, m.bettingStyle, m.tenDigit,
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
        name, user, created, style, ten_digit, total, wins, losses, units_won, units_bet = row
        roi = (units_won / units_bet * 100) if units_bet and units_bet > 0 else 0
        
        models.append({
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
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'master.db'))
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT modelName FROM modelDetails WHERE id = ? AND userId = ?", (model_id, user_id))
    result = cursor.fetchone()
    if not result:
        conn.close()
        raise HTTPException(status_code=404, detail="Model not found")
    
    model_name = result[0]
    
    cursor.execute("DELETE FROM modelPredictions WHERE modelId = ?", (model_id,))
    cursor.execute("DELETE FROM modelDetails WHERE id = ? AND userId = ?", (model_id, user_id))
    cursor.execute("UPDATE modelNames SET userId = NULL WHERE modelName = ? AND userId = ?", (model_name, user_id))
    
    conn.commit()
    conn.close()
    
    return {"message": "Model deleted successfully"}