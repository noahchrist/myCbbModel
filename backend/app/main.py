from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from dotenv import load_dotenv
import os

import sys
print("USING PYTHON:", sys.executable)


from .auth import get_current_user, sync_user_in_local_db, UserCreate
from .games import get_games_by_date
from .models import (
    get_model_names, get_user_models, create_model,
    get_community_models, delete_model, get_model_history, get_todays_top_picks, get_model_daily_picks,
    get_top_picks_performance, get_all_models_performance, get_season_summary, ModelCreate
)

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL") or os.environ.get("VITE_SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if SUPABASE_SERVICE_ROLE_KEY:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

app = FastAPI()

origins = [
    "http://localhost:5173",
    "https://weightroom.io",
    "https://www.weightroom.io",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create dependency function
def get_user_dependency():
    async def _get_current_user(request: Request):
        return await get_current_user(request, supabase)
    return _get_current_user

# Auth endpoints
@app.get("/me")
async def me(request: Request, user_id: str = Depends(get_user_dependency())):
    try:
        auth_header = request.headers.get("Authorization")
        if auth_header:
            token = auth_header.split(" ", 1)[1]
            user_data = supabase.auth.get_user(jwt=token)
            
            email = user_data.user.email if user_data.user else None
            display_name = user_data.user.user_metadata.get('display_name') if user_data.user and user_data.user.user_metadata else None
            sync_user_in_local_db(user_id, email, display_name)
        else:
            sync_user_in_local_db(user_id)
    except Exception as e:
        print(f"Error in GET /me: {e}")
        sync_user_in_local_db(user_id)
    
    return {"supabase_user_id": user_id}

# Game endpoints
@app.get("/games/{date}")
async def games_by_date(date: str):
    return await get_games_by_date(date)

# Model endpoints
@app.get("/model-names")
async def model_names():
    return await get_model_names()

@app.get("/user-models")
async def user_models(user_id: str = Depends(get_user_dependency())):
    return await get_user_models(user_id)

@app.post("/create-model")
async def create_new_model(request: ModelCreate, user_id: str = Depends(get_user_dependency())):
    return await create_model(request, user_id)

@app.get("/community-models")
async def community_models():
    return await get_community_models()

@app.get("/todays-top-picks")
async def todays_top_picks(date: str):
    return await get_todays_top_picks(date)

@app.get("/model-history/{model_id}")
async def model_history(model_id: int, request: Request):
    # Try to get user_id, but don't require it for community models
    try:
        user_id = await get_user_dependency()(request)
    except:
        user_id = None
    return await get_model_history(model_id, user_id)

@app.delete("/delete-model/{model_id}")
async def delete_user_model(model_id: int, user_id: str = Depends(get_user_dependency())):
    return await delete_model(model_id, user_id)

@app.get("/model-daily-picks/{model_id}")
async def model_daily_picks(model_id: int, date: str, user_id: str = Depends(get_user_dependency())):
    return await get_model_daily_picks(date, model_id, user_id)

@app.get("/top-picks-performance")
async def top_picks_performance():
    return await get_top_picks_performance()

@app.get("/all-models-performance")
async def all_models_performance():
    return await get_all_models_performance()

@app.get("/season-summary")
async def season_summary():
    return await get_season_summary()