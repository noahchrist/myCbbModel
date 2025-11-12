from fastapi import FastAPI, Query, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Any
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL") or os.environ.get("VITE_SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if SUPABASE_SERVICE_ROLE_KEY:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

app = FastAPI()

async def get_current_user(request: Request):
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    
    token = auth_header.split(" ", 1)[1]
    
    if not SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(status_code=500, detail="Auth not configured")
    
    try:
        claims = supabase.auth.get_claims(token)
        user_id = claims.get("claims", {}).get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

def sync_user_in_local_db(supabase_user_id: str, email: str = None, display_name: str = None):
    import random
    
    try:
        print(f"sync_user_in_local_db called: user_id={supabase_user_id}, email={email}, display_name={display_name}")
        db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'master.db'))
        
        if not os.path.exists(db_path):
            print("Database file does not exist")
            return
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM users WHERE id = ?", (supabase_user_id,))
        row = cursor.fetchone()
        print(f"Existing user check: {row}")
        
        if row is None:
            if display_name:
                # Use custom display name
                final_display_name = display_name
                print(f"Using custom display name: {final_display_name}")
            elif email:
                # Fallback to email prefix + random digits
                email_prefix = email.split('@')[0]
                random_digits = random.randint(1000, 9999)
                final_display_name = f"{email_prefix}{random_digits}"
                print(f"Using generated display name: {final_display_name}")
            else:
                print("No display name or email provided")
                return
            
            print(f"Inserting user: {supabase_user_id}, {final_display_name}")
            cursor.execute(
                "INSERT INTO users (id, displayName) VALUES (?, ?)",
                (supabase_user_id, final_display_name)
            )
            conn.commit()
            print("User inserted successfully")
        else:
            print("User already exists")
        
        conn.close()
    except Exception as e:
        print(f"Error in sync_user_in_local_db: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")

# Allow your Vite dev server to talk to backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # frontend dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/me")
async def me(request: Request, user_id: str = Depends(get_current_user)):
    try:
        auth_header = request.headers.get("Authorization")
        token = auth_header.split(" ", 1)[1]
        user_data = supabase.auth.get_user(jwt=token)

        email = user_data.user.email if user_data.user else None
        display_name = user_data.user.user_metadata.get('display_name') if user_data.user and user_data.user.user_metadata else None
        print(f"Extracted email: {email}, display_name: {display_name}")
        print(f"About to call sync_user_in_local_db with: user_id={user_id}, email={email}, display_name={display_name}")
        sync_user_in_local_db(user_id, email, display_name)
    except Exception as e:
        print(f"Error in GET /me: {e}")
        sync_user_in_local_db(user_id)
    
    return {"supabase_user_id": user_id}

class UserCreate(BaseModel):
    displayName: str

@app.post("/me")
async def create_user(request: UserCreate, user_id: str = Depends(get_current_user)):
    try:
        auth_header = request.headers.get("Authorization")
        token = auth_header.split(" ", 1)[1]
        user_data = supabase.auth.get_user(jwt=token)
        email = user_data.user.email if user_data.user else None
        sync_user_in_local_db(user_id, email, request.displayName)
    except Exception:
        sync_user_in_local_db(user_id, display_name=request.displayName)
    
    return {"supabase_user_id": user_id, "displayName": request.displayName}



@app.get("/games/{date}")
async def get_games_by_date(date: str) -> List[Dict[str, Any]]:
    """Get games for a specific date with FanDuel odds"""
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'master.db'))
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = """
    SELECT 
        home_team,
        away_team,
        commence_time,
        home_score,
        away_score,
        pt_diff,
        pt_total,
        fd_home_hhPrice,
        fd_away_hhPrice,
        fd_home_spread,
        fd_home_spreadPrice,
        fd_away_spread,
        fd_away_spreadPrice,
        fd_over,
        fd_overPrice,
        fd_under,
        fd_underPrice
    FROM games2026 
    WHERE game_date = ?
    ORDER BY commence_time ASC
    """
    
    cursor.execute(query, (date,))
    rows = cursor.fetchall()
    conn.close()
    
    games = []
    for row in rows:
        games.append({
            'home_team': row['home_team'],
            'away_team': row['away_team'],
            'commence_time': row['commence_time'],
            'home_score': row['home_score'],
            'away_score': row['away_score'],
            'pt_diff': row['pt_diff'],
            'pt_total': row['pt_total'],
            'fd_home_hhPrice': row['fd_home_hhPrice'],
            'fd_away_hhPrice': row['fd_away_hhPrice'],
            'fd_home_spread': row['fd_home_spread'],
            'fd_home_spreadPrice': row['fd_home_spreadPrice'],
            'fd_away_spread': row['fd_away_spread'],
            'fd_away_spreadPrice': row['fd_away_spreadPrice'],
            'fd_over': row['fd_over'],
            'fd_overPrice': row['fd_overPrice'],
            'fd_under': row['fd_under'],
            'fd_underPrice': row['fd_underPrice']
        })
    
    return games

@app.get("/protected-test")
async def protected_test(user_id: str = Depends(get_current_user)):
    return {"message": "This is a protected endpoint", "user_id": user_id}

