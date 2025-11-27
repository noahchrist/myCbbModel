import sqlite3
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from logger import get_logger

logger = get_logger("3_createBaselineTargets")

# ==============================================
# Setup
# ==============================================

load_dotenv()
DB_PATH = os.environ.get('DB_PATH')

if not DB_PATH:
    raise ValueError("Missing DB_PATH in environment variables or .env file")

logger.info("Starting Create Baseline Targets ETL...")

try:
    # ==============================================
    # Database Setup
    # ==============================================
    
    logger.info("Setting up database connection")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get today's date in Eastern US time
    eastern = ZoneInfo("America/New_York")
    today = datetime.now(eastern).strftime('%Y-%m-%d')
    logger.info(f"Creating target dataset for {today} (Eastern time)")
    
    # Create setTarget2026 table with game_id as primary key
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
    logger.info("Created setTarget2026 table with game_id as primary key")
    
    # Check for existing games today
    cursor.execute("SELECT COUNT(*) FROM setTarget2026 WHERE game_date = ?", (today,))
    result = cursor.fetchone()
    existing_count = result[0] if result else 0
    
    if existing_count > 0:
        logger.info(f"Found {existing_count} games already loaded for {today}")
        logger.info("Will update incomplete games and add any missing games")
    
    # Use kenpom2026 table
    kenpom_table = "kenpom2026"
    logger.info(f"Using KenPom table: {kenpom_table}")
    
    # Get today's upcoming games with named columns
    cursor.execute("""
    SELECT game_id, commence_time, season, game_date, home_team, away_team, home_kpid, away_kpid
    FROM games2026 
    WHERE game_date = ? AND is_completed = 0
    """, (today,))
    
    # Convert to list of dictionaries for safer column access
    columns = ['game_id', 'commence_time', 'season', 'game_date', 'home_team', 'away_team', 'home_kpid', 'away_kpid']
    games = [dict(zip(columns, row)) for row in cursor.fetchall()]
    logger.info(f"Found {len(games)} upcoming games for today")
    
    processed = 0
    updated = 0
    inserted = 0
    
    for game in games:
        game_id = game['game_id']
        
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
            
        # Extract team identifiers and names from game dictionary
        home_kpid = game['home_kpid']
        away_kpid = game['away_kpid']
        home_team = game['home_team']
        away_team = game['away_team']
        
        # Query KenPom stats for home team with named column mapping
        cursor.execute(f"""
        SELECT adjOffEff, adjDefEff, adjTempo, effFgPct, defEffFgPct, trnvrPct, ftRate, defFtRate,
               offRebPct, defRebPct, effHeight, expRtg, benchRtg, contRtg, threesPct, ftPct,
               blockPct, stlRate, nonStlTrnvrRate, astRate, threesRate, oppThreesPct, oppThreesRate
        FROM {kenpom_table} WHERE kpid = ?
        """, (home_kpid,))
        home_stats_raw = cursor.fetchone()
        
        # Query KenPom stats for away team with named column mapping
        cursor.execute(f"""
        SELECT adjOffEff, adjDefEff, adjTempo, effFgPct, defEffFgPct, trnvrPct, ftRate, defFtRate,
               offRebPct, defRebPct, effHeight, expRtg, benchRtg, contRtg, threesPct, ftPct,
               blockPct, stlRate, nonStlTrnvrRate, astRate, threesRate, oppThreesPct, oppThreesRate
        FROM {kenpom_table} WHERE kpid = ?
        """, (away_kpid,))
        away_stats_raw = cursor.fetchone()
        
        # Convert stats tuples to dictionaries for safer column access
        home_stats_columns = ['adjOffEff', 'adjDefEff', 'adjTempo', 'effFgPct', 'defEffFgPct', 'trnvrPct', 'ftRate', 'defFtRate',
                             'offRebPct', 'defRebPct', 'effHeight', 'expRtg', 'benchRtg', 'contRtg', 'threesPct', 'ftPct',
                             'blockPct', 'stlRate', 'nonStlTrnvrRate', 'astRate', 'threesRate', 'oppThreesPct', 'oppThreesRate']
        
        home_stats = dict(zip(home_stats_columns, home_stats_raw)) if home_stats_raw else None
        away_stats = dict(zip(home_stats_columns, away_stats_raw)) if away_stats_raw else None
        
        if home_stats and away_stats:
            if existing_game:
                # Update existing incomplete game record with current KenPom data
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
                    # Game metadata using named access
                    game['home_kpid'], game['away_kpid'], game['game_date'], int(game['season']), game['home_team'], game['away_team'],
                    # Home team stats using named dictionary access
                    home_stats['adjOffEff'], home_stats['effFgPct'], home_stats['adjDefEff'], home_stats['defEffFgPct'],
                    home_stats['adjTempo'], home_stats['threesPct'], home_stats['threesRate'], home_stats['ftRate'],
                    home_stats['ftPct'], home_stats['defFtRate'], home_stats['blockPct'], home_stats['oppThreesPct'],
                    home_stats['oppThreesRate'], home_stats['stlRate'], home_stats['nonStlTrnvrRate'], home_stats['offRebPct'],
                    home_stats['defRebPct'], home_stats['astRate'], home_stats['trnvrPct'], home_stats['effHeight'],
                    home_stats['expRtg'], home_stats['benchRtg'], home_stats['contRtg'],
                    # Away team stats using named dictionary access
                    away_stats['adjOffEff'], away_stats['effFgPct'], away_stats['adjDefEff'], away_stats['defEffFgPct'],
                    away_stats['adjTempo'], away_stats['threesPct'], away_stats['threesRate'], away_stats['ftRate'],
                    away_stats['ftPct'], away_stats['defFtRate'], away_stats['blockPct'], away_stats['oppThreesPct'],
                    away_stats['oppThreesRate'], away_stats['stlRate'], away_stats['nonStlTrnvrRate'], away_stats['offRebPct'],
                    away_stats['defRebPct'], away_stats['astRate'], away_stats['trnvrPct'], away_stats['effHeight'],
                    away_stats['expRtg'], away_stats['benchRtg'], away_stats['contRtg'], game['game_date'],
                    game_id
                ))
                updated += 1
            else:
                # Insert new game record with KenPom data for upcoming game
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
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    # Game metadata - scores/results are None for upcoming games
                    game_id, game['home_kpid'], game['away_kpid'], 1, 0, game['game_date'], int(game['season']), game['home_team'], None, game['away_team'], None,
                    None, None, None,
                    # Home team KenPom stats using named dictionary access
                    home_stats['adjOffEff'], home_stats['effFgPct'], home_stats['adjDefEff'], home_stats['defEffFgPct'],
                    home_stats['adjTempo'], home_stats['threesPct'], home_stats['threesRate'], home_stats['ftRate'],
                    home_stats['ftPct'], home_stats['defFtRate'], home_stats['blockPct'], home_stats['oppThreesPct'],
                    home_stats['oppThreesRate'], home_stats['stlRate'], home_stats['nonStlTrnvrRate'], home_stats['offRebPct'],
                    home_stats['defRebPct'], home_stats['astRate'], home_stats['trnvrPct'], home_stats['effHeight'],
                    home_stats['expRtg'], home_stats['benchRtg'], home_stats['contRtg'],
                    # Away team KenPom stats using named dictionary access
                    away_stats['adjOffEff'], away_stats['effFgPct'], away_stats['adjDefEff'], away_stats['defEffFgPct'],
                    away_stats['adjTempo'], away_stats['threesPct'], away_stats['threesRate'], away_stats['ftRate'],
                    away_stats['ftPct'], away_stats['defFtRate'], away_stats['blockPct'], away_stats['oppThreesPct'],
                    away_stats['oppThreesRate'], away_stats['stlRate'], away_stats['nonStlTrnvrRate'], away_stats['offRebPct'],
                    away_stats['defRebPct'], away_stats['astRate'], away_stats['trnvrPct'], away_stats['effHeight'],
                    away_stats['expRtg'], away_stats['benchRtg'], away_stats['contRtg'], game['game_date']
                ))
                inserted += 1
            
            processed += 1
        else:
            logger.warning(f"Missing KenPom data for game {game_id}: {game['home_team']} vs {game['away_team']}")
    
    conn.commit()
    
    # ==============================================
    # Final Summary
    # ==============================================
    
    logger.info("Starting final verification")
    
    # Get final counts
    cursor.execute("SELECT COUNT(*) FROM setTarget2026 WHERE game_date = ?", (today,))
    total_today = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM setTarget2026")
    total_all = cursor.fetchone()[0]
    
    logger.info("Pipeline complete - final summary:")
    logger.info(f"Games processed: {processed}")
    logger.info(f"Records updated: {updated}")
    logger.info(f"Records inserted: {inserted}")
    logger.info(f"Total games for {today}: {total_today}")
    logger.info(f"Total games in setTarget2026: {total_all}")
    
    conn.close()
    logger.info("Create Baseline Targets pipeline finished")

except Exception:
    logger.error("Create Baseline Targets ETL failed", exc_info=True)
    if 'conn' in locals():
        conn.close()