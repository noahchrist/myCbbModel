# Backend Setup Instructions

## Prerequisites
- Python 3.8+
- SQLite database with required tables

## Setup Commands

1. **Navigate to backend directory:**
```cmd
cd c:\Users\jason\OneDrive\Desktop\Christensen\Projects\myCbbModel\backend
```

2. **Create virtual environment:**
```cmd
python -m venv venv
```

3. **Install dependencies:**
```cmd
pip install -r requirements.txt
```

4. **Create data directory:**
```cmd
mkdir data
```

5. **Update .env file with your credentials:**
```
SUPABASE_URL=your_supabase_url_here
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here
DB_PATH=./data/master.db
```

## Run Server

**Start the server in a new terminal:**
```cmd
cd c:\Users\jason\OneDrive\Desktop\Christensen\Projects\myCbbModel\backend && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Database Schema Required

The app expects these SQLite tables in `data/master.db`:

- **games2026**: Game data with FanDuel odds
- **users**: `id` (supabase user id), `displayName`
- **models**: User betting models
- **predictions**: Model betting history

## API Endpoints

- `GET /games/{date}` - Get games for date
- `GET /me` - Get current user
- `GET /user-models` - Get user's models
- `GET /community-models` - Get all public models
- `POST /create-model` - Create new model

Server available at: `http://localhost:8000`
API docs at: `http://localhost:8000/docs`