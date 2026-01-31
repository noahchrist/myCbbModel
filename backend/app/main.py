from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from dotenv import load_dotenv
import os

import sys
print("USING PYTHON:", sys.executable)


from .auth import get_current_user, get_user_display_name
from .games import get_games_by_date
from .models import get_model_names, create_model, delete_model, get_model_data, ModelCreate
from .community import get_community_models, get_top_picks

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
    auth_header = request.headers.get("Authorization")
    token = auth_header.split(" ", 1)[1]
    
    display_name = await get_user_display_name(supabase, token)
    
    return {
        "user_id": user_id,
        "display_name": display_name
    }

# Game endpoints
@app.get("/games/{date}")
async def games_by_date(date: str):
    return await get_games_by_date(date, supabase)

# Model endpoints
@app.get("/model-names")
async def model_names():
    return await get_model_names(supabase)

@app.post("/create-model")
async def create_new_model(request: ModelCreate, user_id: str = Depends(get_user_dependency())):
    return await create_model(request, user_id, supabase)

@app.delete("/delete-model/{model_id}")
async def delete_user_model(model_id: int, user_id: str = Depends(get_user_dependency())):
    return await delete_model(model_id, user_id, supabase)

@app.get("/model-data/{model_id}")
async def model_data(model_id: int, date: str = None, user_id: str = Depends(get_user_dependency())):
    return await get_model_data(model_id, user_id, supabase, date)

# Community endpoints
@app.get("/community-models")
async def community_models():
    return await get_community_models(supabase)

@app.get("/top-picks")
async def top_picks(date: str = None):
    return await get_top_picks(supabase, date)