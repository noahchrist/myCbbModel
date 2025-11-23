@echo off
echo Starting myCbbModel Backend Environment...
echo.

REM Navigate to backend directory
cd /d "c:\Users\jason\OneDrive\Desktop\Christensen\Projects\myCbbModel\backend"

REM Check if virtual environment exists, create if not
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    echo Virtual environment created.
    echo.
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install/update dependencies
echo Installing dependencies...
pip install -r requirements.txt

REM Create data directory if it doesn't exist
if not exist "data" (
    echo Creating data directory...
    mkdir data
)

REM Check if .env file exists
if not exist ".env" (
    echo WARNING: .env file not found. Please create it with your Supabase credentials.
    echo.
)

REM Start the FastAPI server
echo.
echo Starting FastAPI server...
echo Server will be available at: http://localhost:8000
echo API docs available at: http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop the server
echo.

python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

pause