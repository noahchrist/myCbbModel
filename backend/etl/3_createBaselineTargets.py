import sqlite3
import os
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Path setup
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(BACKEND_DIR, "data")
MASTER_DB = os.environ.get('DB_PATH') or os.path.join(DATA_DIR, "master.db")

def create_targets():
    """Create predictive dataset from today's upcoming games"""
    
    # Get today's date
    today = datetime.now().strftime('%Y-%m-%d')
    
    logging.info(f"Creating target dataset for {today}")
    logging.info(f"Appending to setTarget2026")
    
    # Connect to master database
    conn = sqlite3.connect(MASTER_DB)
    cursor = conn.cursor()
    
    # Drop and recreate setTarget2026 table with game_id as primary key
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS setTarget2026 (
        game_id TEXT PRIMARY KEY,
        home_kpid INTEGER,
        away_kpid INTEGER,
        is_home INTEGER DEFAULT 1,
        is_neutral INTEGER DEFAULT 0,
        date TEXT,
        season INTEGER,
        home_team TEXT,
        home_score INTEGER,
        away_team TEXT,
        away_score INTEGER,
        win_loss TEXT,
        pt_diff INTEGER,
        pt_total INTEGER,
        home_adjOffEff REAL,
        home_effFgPct REAL,
        home_adjDefEff REAL,
        home_defEffFgPct REAL,
        home_adjTempo REAL,
        home_threesPct REAL,
        home_threesRate REAL,
        home_ftRate REAL,
        home_ftPct REAL,
        home_defFtRate REAL,
        home_blockPct REAL,
        home_oppThreesPct REAL,
        home_oppThreesRate REAL,
        home_stlRate REAL,
        home_nonStlTrnvrRate REAL,
        home_offRebPct REAL,
        home_defRebPct REAL,
        home_astRate REAL,
        home_trnvrPct REAL,
        home_effHeight REAL,
        home_expRtg REAL,
        home_benchRtg REAL,
        home_contRtg REAL,
        away_adjOffEff REAL,
        away_effFgPct REAL,
        away_adjDefEff REAL,
        away_defEffFgPct REAL,
        away_adjTempo REAL,
        away_threesPct REAL,
        away_threesRate REAL,
        away_ftRate REAL,
        away_ftPct REAL,
        away_defFtRate REAL,
        away_blockPct REAL,
        away_oppThreesPct REAL,
        away_oppThreesRate REAL,
        away_stlRate REAL,
        away_nonStlTrnvrRate REAL,
        away_offRebPct REAL,
        away_defRebPct REAL,
        away_astRate REAL,
        away_trnvrPct REAL,
        away_effHeight REAL,
        away_expRtg REAL,
        away_benchRtg REAL,
        away_contRtg REAL,
        game_date DATE
    )
    """)
    logging.info(f"✅ Created setTarget2026 table with game_id as primary key")
    
    # Check for existing games today
    cursor.execute("SELECT COUNT(*) FROM setTarget2026 WHERE game_date = ?", (today,))
    result = cursor.fetchone()
    existing_count = result[0] if result else 0
    
    if existing_count > 0:
        response = input(f"\n⚠️  Found {existing_count} games already loaded for {today}.\nProceed to update odds with latest data? (y/n): ").lower().strip()
        if response != 'y':
            logging.info("❌ Script cancelled by user")
            conn.close()
            return
        
        logging.info(f"📋 Updating {existing_count} existing games for {today}")
        logging.info("Will update incomplete games and add any missing games")
    
    # Use kenpom2026 table
    kenpom_table = "kenpom2026"
    print(f"Using KenPom table: {kenpom_table}")
    
    # Get today's upcoming games
    cursor.execute("""
    SELECT game_id, commence_time, season, game_date, home_team, away_team, home_kpid, away_kpid
    FROM games2026 
    WHERE game_date = ? AND is_completed = 0
    """, (today,))
    
    games = cursor.fetchall()
    print(f"Found {len(games)} upcoming games for today")
    
    processed = 0
    updated = 0
    inserted = 0
    
    for game in games:
        game_id = game[0]
        
        # Check if game already exists in setTarget2026
        cursor.execute("SELECT game_id FROM setTarget2026 WHERE game_id = ?", (game_id,))
        existing_game = cursor.fetchone()
        
        # Check if this game is completed
        cursor.execute("SELECT is_completed FROM games2026 WHERE game_id = ?", (game_id,))
        completion_result = cursor.fetchone()
        is_completed = completion_result[0] if completion_result else 0
        
        if existing_game and is_completed:
            # Game exists and is completed - skip it
            continue
            
        # Get KenPom data for both teams
        cursor.execute(f"""
        SELECT adjOffEff, adjDefEff, adjTempo, effFgPct, defEffFgPct, trnvrPct, ftRate, defFtRate,
               offRebPct, defRebPct, effHeight, expRtg, benchRtg, contRtg, threesPct, ftPct,
               blockPct, stlRate, nonStlTrnvrRate, astRate, threesRate, oppThreesPct, oppThreesRate
        FROM {kenpom_table} WHERE kpid = ?
        """, (game[6],))  # home_kpid
        home_stats = cursor.fetchone()
        
        cursor.execute(f"""
        SELECT adjOffEff, adjDefEff, adjTempo, effFgPct, defEffFgPct, trnvrPct, ftRate, defFtRate,
               offRebPct, defRebPct, effHeight, expRtg, benchRtg, contRtg, threesPct, ftPct,
               blockPct, stlRate, nonStlTrnvrRate, astRate, threesRate, oppThreesPct, oppThreesRate
        FROM {kenpom_table} WHERE kpid = ?
        """, (game[7],))  # away_kpid
        away_stats = cursor.fetchone()
        
        if home_stats and away_stats:
            if existing_game:
                # Update existing record
                cursor.execute("""
                UPDATE setTarget2026 SET
                    home_kpid = ?, away_kpid = ?, date = ?, season = ?, home_team = ?, away_team = ?,
                    home_adjOffEff = ?, home_effFgPct = ?, home_adjDefEff = ?, home_defEffFgPct = ?,
                    home_adjTempo = ?, home_threesPct = ?, home_threesRate = ?, home_ftRate = ?,
                    home_ftPct = ?, home_defFtRate = ?, home_blockPct = ?, home_oppThreesPct = ?,
                    home_oppThreesRate = ?, home_stlRate = ?, home_nonStlTrnvrRate = ?, home_offRebPct = ?,
                    home_defRebPct = ?, home_astRate = ?, home_trnvrPct = ?, home_effHeight = ?,
                    home_expRtg = ?, home_benchRtg = ?, home_contRtg = ?,
                    away_adjOffEff = ?, away_effFgPct = ?, away_adjDefEff = ?, away_defEffFgPct = ?,
                    away_adjTempo = ?, away_threesPct = ?, away_threesRate = ?, away_ftRate = ?,
                    away_ftPct = ?, away_defFtRate = ?, away_blockPct = ?, away_oppThreesPct = ?,
                    away_oppThreesRate = ?, away_stlRate = ?, away_nonStlTrnvrRate = ?, away_offRebPct = ?,
                    away_defRebPct = ?, away_astRate = ?, away_trnvrPct = ?, away_effHeight = ?,
                    away_expRtg = ?, away_benchRtg = ?, away_contRtg = ?, game_date = ?
                WHERE game_id = ?
                """, (
                    game[6], game[7], game[3], int(game[2]), game[4], game[5],
                    home_stats[0], home_stats[3], home_stats[1], home_stats[4],
                    home_stats[2], home_stats[14], home_stats[20], home_stats[6],
                    home_stats[15], home_stats[7], home_stats[16], home_stats[21],
                    home_stats[22], home_stats[17], home_stats[18], home_stats[8],
                    home_stats[9], home_stats[19], home_stats[5], home_stats[10],
                    home_stats[11], home_stats[12], home_stats[13],
                    away_stats[0], away_stats[3], away_stats[1], away_stats[4],
                    away_stats[2], away_stats[14], away_stats[20], away_stats[6],
                    away_stats[15], away_stats[7], away_stats[16], away_stats[21],
                    away_stats[22], away_stats[17], away_stats[18], away_stats[8],
                    away_stats[9], away_stats[19], away_stats[5], away_stats[10],
                    away_stats[11], away_stats[12], away_stats[13], game[3],
                    game_id
                ))
                updated += 1
            else:
                # Insert new record
                cursor.execute("""
                INSERT INTO setTarget2026 (
                    game_id, home_kpid, away_kpid, is_home, is_neutral, date, season, home_team, home_score, away_team, away_score,
                    win_loss, pt_diff, pt_total,
                    home_adjOffEff, home_effFgPct, home_adjDefEff, home_defEffFgPct, home_adjTempo,
                    home_threesPct, home_threesRate, home_ftRate, home_ftPct, home_defFtRate,
                    home_blockPct, home_oppThreesPct, home_oppThreesRate, home_stlRate, home_nonStlTrnvrRate,
                    home_offRebPct, home_defRebPct, home_astRate, home_trnvrPct, home_effHeight,
                    home_expRtg, home_benchRtg, home_contRtg,
                    away_adjOffEff, away_effFgPct, away_adjDefEff, away_defEffFgPct, away_adjTempo,
                    away_threesPct, away_threesRate, away_ftRate, away_ftPct, away_defFtRate,
                    away_blockPct, away_oppThreesPct, away_oppThreesRate, away_stlRate, away_nonStlTrnvrRate,
                    away_offRebPct, away_defRebPct, away_astRate, away_trnvrPct, away_effHeight,
                    away_expRtg, away_benchRtg, away_contRtg, game_date
                ) VALUES (
                    ?, ?, ?, 1, 0, ?, ?, ?, NULL, ?, NULL, NULL, NULL, NULL,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """, (
                    game_id, game[6], game[7], game[3], int(game[2]), game[4], game[5],
                    home_stats[0], home_stats[3], home_stats[1], home_stats[4],
                    home_stats[2], home_stats[14], home_stats[20], home_stats[6],
                    home_stats[15], home_stats[7], home_stats[16], home_stats[21],
                    home_stats[22], home_stats[17], home_stats[18], home_stats[8],
                    home_stats[9], home_stats[19], home_stats[5], home_stats[10],
                    home_stats[11], home_stats[12], home_stats[13],
                    away_stats[0], away_stats[3], away_stats[1], away_stats[4],
                    away_stats[2], away_stats[14], away_stats[20], away_stats[6],
                    away_stats[15], away_stats[7], away_stats[16], away_stats[21],
                    away_stats[22], away_stats[17], away_stats[18], away_stats[8],
                    away_stats[9], away_stats[19], away_stats[5], away_stats[10],
                    away_stats[11], away_stats[12], away_stats[13], game[3]
                ))
                inserted += 1
            processed += 1
        else:
            print(f"Missing KenPom data for game: {game[4]} vs {game[5]}")
    
    conn.commit()
    conn.close()
    
    logging.info(f"✅ Processed {processed} games: {inserted} new, {updated} updated")
    logging.info(f"📁 Data saved to: {MASTER_DB}")

if __name__ == "__main__":
    create_targets()