import sqlite3
import os
from datetime import datetime

# Path setup
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(BACKEND_DIR, "data")
FUTURE_DB = os.path.join(DATA_DIR, "future.db")
PREDICT_DB = os.path.join(DATA_DIR, "predict.db")

def create_targets():
    """Create predictive dataset from today's upcoming games"""
    
    # Get today's date
    today = datetime.now().strftime('%Y-%m-%d')
    table_name = f"targetSet_{datetime.now().strftime('%m%d%Y')}"
    
    print(f"Creating target dataset for {today}")
    print(f"Table name: {table_name}")
    
    # Connect to databases
    future_conn = sqlite3.connect(FUTURE_DB)
    future_cursor = future_conn.cursor()
    
    predict_conn = sqlite3.connect(PREDICT_DB)
    predict_cursor = predict_conn.cursor()
    
    # Check if table already exists
    predict_cursor.execute("""
    SELECT name FROM sqlite_master 
    WHERE type='table' AND name = ?
    """, (table_name,))
    
    if predict_cursor.fetchone():
        response = input(f"\n⚠️  Table {table_name} already exists and will be dropped and recreated.\nThis will remove all existing data. Continue? (y/n): ").lower().strip()
        if response != 'y':
            print("❌ Script cancelled by user")
            predict_conn.close()
            future_conn.close()
            return
        
        # Drop existing table
        predict_cursor.execute(f"DROP TABLE {table_name}")
        print(f"🗑️  Dropped existing table {table_name}")
    
    # Create new table
    predict_cursor.execute(f"""
    CREATE TABLE {table_name} (
        game_id TEXT PRIMARY KEY,
        commence_time DATETIME,
        season TEXT,
        home_team TEXT,
        away_team TEXT,
        home_kpid INTEGER,
        away_kpid INTEGER,
        fd_home_hhPrice INTEGER,
        fd_away_hhPrice INTEGER,
        fd_home_spread REAL,
        fd_home_spreadPrice INTEGER,
        fd_away_spread REAL,
        fd_away_spreadPrice INTEGER,
        fd_over REAL,
        fd_overPrice INTEGER,
        fd_under REAL,
        fd_underPrice INTEGER,
        home_adjOffEff REAL, home_adjDefEff REAL, home_adjTempo REAL, home_effFgPct REAL,
        home_defEffFgPct REAL, home_trnvrPct REAL, home_ftRate REAL, home_defFtRate REAL,
        home_offRebPct REAL, home_defRebPct REAL, home_effHeight REAL, home_expRtg REAL,
        home_benchRtg REAL, home_contRtg REAL, home_threesPct REAL, home_ftPct REAL,
        home_blockPct REAL, home_stlRate REAL, home_nonStlTrnvrRate REAL, home_astRate REAL,
        home_threesRate REAL, home_oppThreesPct REAL, home_oppThreesRate REAL,
        away_adjOffEff REAL, away_adjDefEff REAL, away_adjTempo REAL, away_effFgPct REAL,
        away_defEffFgPct REAL, away_trnvrPct REAL, away_ftRate REAL, away_defFtRate REAL,
        away_offRebPct REAL, away_defRebPct REAL, away_effHeight REAL, away_expRtg REAL,
        away_benchRtg REAL, away_contRtg REAL, away_threesPct REAL, away_ftPct REAL,
        away_blockPct REAL, away_stlRate REAL, away_nonStlTrnvrRate REAL, away_astRate REAL,
        away_threesRate REAL, away_oppThreesPct REAL, away_oppThreesRate REAL,
        is_home INTEGER DEFAULT 1,
        is_neutral INTEGER DEFAULT 0
    )
    """)
    print(f"✅ Created new table {table_name}")
    
    # Get most recent KenPom table
    future_cursor.execute("""
    SELECT name FROM sqlite_master 
    WHERE type='table' AND name LIKE 'kenpom_cleaned_%' 
    ORDER BY name DESC LIMIT 1
    """)
    kenpom_table = future_cursor.fetchone()[0]
    print(f"Using KenPom table: {kenpom_table}")
    
    # Get today's upcoming games
    future_cursor.execute("""
    SELECT game_id, commence_time, season, home_team, away_team, home_kpid, away_kpid,
           fd_home_hhPrice, fd_away_hhPrice, fd_home_spread, fd_home_spreadPrice,
           fd_away_spread, fd_away_spreadPrice, fd_over, fd_overPrice, fd_under, fd_underPrice
    FROM gamesMaster_2026 
    WHERE game_date = ? AND is_completed = 0
    """, (today,))
    
    games = future_cursor.fetchall()
    print(f"Found {len(games)} upcoming games for today")
    
    inserted = 0
    for game in games:
        # Get home team KenPom data
        future_cursor.execute(f"""
        SELECT adjOffEff, adjDefEff, adjTempo, effFgPct, defEffFgPct, trnvrPct, ftRate, defFtRate,
               offRebPct, defRebPct, effHeight, expRtg, benchRtg, contRtg, threesPct, ftPct,
               blockPct, stlRate, nonStlTrnvrRate, astRate, threesRate, oppThreesPct, oppThreesRate
        FROM {kenpom_table} WHERE kpid = ?
        """, (game[5],))
        home_stats = future_cursor.fetchone()
        
        # Get away team KenPom data
        future_cursor.execute(f"""
        SELECT adjOffEff, adjDefEff, adjTempo, effFgPct, defEffFgPct, trnvrPct, ftRate, defFtRate,
               offRebPct, defRebPct, effHeight, expRtg, benchRtg, contRtg, threesPct, ftPct,
               blockPct, stlRate, nonStlTrnvrRate, astRate, threesRate, oppThreesPct, oppThreesRate
        FROM {kenpom_table} WHERE kpid = ?
        """, (game[6],))
        away_stats = future_cursor.fetchone()
        
        if home_stats and away_stats:
            # Insert record (excluding DEFAULT columns)
            predict_cursor.execute(f"""
            INSERT OR REPLACE INTO {table_name} (
                game_id, commence_time, season, home_team, away_team, home_kpid, away_kpid,
                fd_home_hhPrice, fd_away_hhPrice, fd_home_spread, fd_home_spreadPrice,
                fd_away_spread, fd_away_spreadPrice, fd_over, fd_overPrice, fd_under, fd_underPrice,
                home_adjOffEff, home_adjDefEff, home_adjTempo, home_effFgPct, home_defEffFgPct,
                home_trnvrPct, home_ftRate, home_defFtRate, home_offRebPct, home_defRebPct,
                home_effHeight, home_expRtg, home_benchRtg, home_contRtg, home_threesPct,
                home_ftPct, home_blockPct, home_stlRate, home_nonStlTrnvrRate, home_astRate,
                home_threesRate, home_oppThreesPct, home_oppThreesRate,
                away_adjOffEff, away_adjDefEff, away_adjTempo, away_effFgPct, away_defEffFgPct,
                away_trnvrPct, away_ftRate, away_defFtRate, away_offRebPct, away_defRebPct,
                away_effHeight, away_expRtg, away_benchRtg, away_contRtg, away_threesPct,
                away_ftPct, away_blockPct, away_stlRate, away_nonStlTrnvrRate, away_astRate,
                away_threesRate, away_oppThreesPct, away_oppThreesRate
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """, (
                game[0], game[1], game[2], game[3], game[4], game[5], game[6],
                game[7], game[8], game[9], game[10], game[11], game[12],
                game[13], game[14], game[15], game[16],
                home_stats[0], home_stats[1], home_stats[2], home_stats[3], home_stats[4],
                home_stats[5], home_stats[6], home_stats[7], home_stats[8], home_stats[9],
                home_stats[10], home_stats[11], home_stats[12], home_stats[13], home_stats[14],
                home_stats[15], home_stats[16], home_stats[17], home_stats[18], home_stats[19],
                home_stats[20], home_stats[21], home_stats[22],
                away_stats[0], away_stats[1], away_stats[2], away_stats[3], away_stats[4],
                away_stats[5], away_stats[6], away_stats[7], away_stats[8], away_stats[9],
                away_stats[10], away_stats[11], away_stats[12], away_stats[13], away_stats[14],
                away_stats[15], away_stats[16], away_stats[17], away_stats[18], away_stats[19],
                away_stats[20], away_stats[21], away_stats[22]
            ))
            inserted += 1
        else:
            print(f"Missing KenPom data for game: {game[3]} vs {game[4]}")
    
    predict_conn.commit()
    future_conn.close()
    predict_conn.close()
    
    print(f"✅ Created {table_name} with {inserted} records")
    print(f"📁 Data saved to: {PREDICT_DB}")

if __name__ == "__main__":
    create_targets()