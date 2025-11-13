from fastapi import Request, HTTPException, Depends
from pydantic import BaseModel
from supabase import Client
import sqlite3
import os
import random

class UserCreate(BaseModel):
    displayName: str

async def get_current_user(request: Request, supabase: Client):
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    
    token = auth_header.split(" ", 1)[1]
    
    try:
        claims = supabase.auth.get_claims(token)
        user_id = claims.get("claims", {}).get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

def sync_user_in_local_db(supabase_user_id: str, email: str = None, display_name: str = None):
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
                final_display_name = display_name
                print(f"Using custom display name: {final_display_name}")
            elif email:
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