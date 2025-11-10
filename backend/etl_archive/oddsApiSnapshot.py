"""
oddsApiSnapshot.py
Pulls a one-time snapshot of The Odds API data for NCAA Basketball (v4).
API Reference: https://the-odds-api.com/liveapi/guides/v4/
Fetches:
 - /sports/basketball_ncaab/participants  (team list)
 - /sports/basketball_ncaab/events        (today's schedule)
 - /sports/basketball_ncaab/odds          (current odds)
 - /sports/basketball_ncaab/scores        (yesterday's results)
 - /account/usage                         (API usage stats)
Saves each as both JSON and CSV for easy inspection.
"""

import requests
import json
import pandas as pd
import logging
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

# === CONFIG ===
load_dotenv()
API_KEY = os.getenv("THEODDS_API_KEY")
BASE_URL = "https://api.the-odds-api.com/v4"
SPORT_KEY = "basketball_ncaab"

if not API_KEY:
    raise ValueError("Missing ODDS_API_KEY in environment variables or .env file")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/odds_api_snapshot.log"),
        logging.StreamHandler()
    ]
)

OUTPUT_DIR = "data/raw_odds_snapshot"
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs("logs", exist_ok=True)

# Track API usage
total_requests = 0


def save_json_and_csv(data, name):
    """Save JSON and (if possible) flattened CSV versions."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = os.path.join(OUTPUT_DIR, f"{name}_{timestamp}.json")
    csv_path = os.path.join(OUTPUT_DIR, f"{name}_{timestamp}.csv")

    # Save JSON with readable formatting
    with open(json_path, "w") as f:
        json.dump(data, f, indent=2, default=str)

    # Try flattening JSON to CSV
    try:
        if isinstance(data, list) and len(data) > 0:
            df = pd.json_normalize(data)
            df.to_csv(csv_path, index=False)
            logging.info(f"📊 Saved {len(data)} records to CSV: {csv_path}")
        else:
            logging.warning(f"⚠️ No data to save as CSV for {name}")
    except Exception as e:
        logging.warning(f"⚠️ Could not flatten {name} to CSV: {e}")

    logging.info(f"✅ Saved {name} → {json_path}")
    return len(data) if isinstance(data, list) else 1


def get_data(endpoint, params=None):
    """Generic GET request helper with usage tracking."""
    global total_requests
    url = f"{BASE_URL}/{endpoint}"
    params = params or {}
    params["apiKey"] = API_KEY
    
    logging.info(f"🔹 Requesting: {url}")
    logging.info(f"📋 Parameters: {params}")
    
    r = requests.get(url, params=params)
    total_requests += 1
    
    # Log usage info from headers
    if 'x-requests-remaining' in r.headers:
        remaining = r.headers['x-requests-remaining']
        used = r.headers.get('x-requests-used', 'unknown')
        logging.info(f"📊 API Usage - Used: {used}, Remaining: {remaining}")
    
    r.raise_for_status()
    data = r.json()
    
    record_count = len(data) if isinstance(data, list) else "1 object"
    logging.info(f"✅ {endpoint} returned {record_count} records")
    
    return data


def main():
    logging.info("🚀 Starting The Odds API snapshot pull")
    logging.info(f"📅 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    total_records = 0
    

    #ONLY NEEDED ONE DATA PULL - ODDS INCLUDE PARTICIPANTS
    # # 1️⃣ Participants (team list)
    # try:
    #     logging.info("📋 Fetching participants (team list)...")
    #     participants = get_data(f"sports/{SPORT_KEY}/participants")
    #     records = save_json_and_csv(participants, "participants")
    #     total_records += records
    # except Exception as e:
    #     logging.error(f"❌ Failed to pull participants: {e}")


    #REDUNDANT DATA PULL - EVENTS ARE INCLUDED IN ODDS RESPONSE
    # # 2️⃣ Events (today's games)
    # try:
    #     logging.info("🏀 Fetching today's events...")
    #     events = get_data(f"sports/{SPORT_KEY}/events")
    #     records = save_json_and_csv(events, "events_today")
    #     total_records += records
    # except Exception as e:
    #     logging.error(f"❌ Failed to pull events: {e}")

    # 3️⃣ Odds (today's markets)
    try:
        logging.info("💰 Fetching current odds...")
        odds_params = {
            "regions": "us",
            "markets": "h2h,spreads,totals",
            "oddsFormat": "american",
            "dateFormat": "iso",
        }
        odds = get_data(f"sports/{SPORT_KEY}/odds", odds_params)
        records = save_json_and_csv(odds, "odds_today")
        total_records += records
    except Exception as e:
        logging.error(f"❌ Failed to pull odds: {e}")

    # 4️⃣ Scores (recent completed games)
    try:
        logging.info("📊 Fetching recent scores...")
        scores_params = {"daysFrom": 3}  # Last 3 days for more data
        scores = get_data(f"sports/{SPORT_KEY}/scores", scores_params)
        records = save_json_and_csv(scores, "scores_recent")
        total_records += records
    except Exception as e:
        logging.error(f"❌ Failed to pull scores: {e}")

    logging.info(f"\n🎉 Snapshot complete! Total records saved: {total_records}")
    logging.info(f"📁 Data saved to: {OUTPUT_DIR}")
    logging.info(f"🔧 API requests made: {total_requests}")


if __name__ == "__main__":
    main()
