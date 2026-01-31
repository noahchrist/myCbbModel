import os
import time
import requests
import pandas as pd
import numpy as np
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from dbConnection import get_db_connection
from logger import get_logger

logger = get_logger("2_createSnapshots")

load_dotenv()

API_KEY = os.getenv("KENPOM_API_KEY")
BASE_URL = "https://kenpom.com"
SEASON = 2026
DELAY_BETWEEN_TEAMS = 0.01

INVERT_FIELDS = [
    'adjDefEff', 'defEffFgPct', 'trnvrPct', 'defFtRate', 
    'defRebPct', 'oppThreesPct', 'oppThreesRate'
]

STAT_FIELDS = [
    'adjOffEff', 'adjDefEff', 'adjTempo', 'effFgPct', 'defEffFgPct', 
    'trnvrPct', 'ftRate', 'defFtRate', 'offRebPct', 'defRebPct',
    'effHeight', 'expRtg', 'benchRtg', 'contRtg', 'threesPct', 
    'ftPct', 'blockPct', 'stlRate', 'nonStlTrnvrRate', 'astRate', 
    'threesRate', 'oppThreesPct', 'oppThreesRate'
]

logger.info("Starting Create Snapshots ETL...")

try:
    # ==============================================
    # Fetch KenPom Data
    # ==============================================
    
    logger.info("Fetching KenPom data from API")
    
    def get(endpoint, params=None):
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "User-Agent": "KenPom-Snapshots/1.0"
        }
        
        if params is None:
            params = {}
        params['endpoint'] = endpoint
        
        url = f"{BASE_URL}/api.php"
        r = requests.get(url, headers=headers, params=params)
        
        if r.status_code != 200:
            logger.error(f"HTTP {r.status_code} for {endpoint}")
            return None
        return r.json()
    
    # Get teams
    teams = get("teams", params={"y": SEASON})
    if not teams:
        raise ValueError("No teams found")
    
    team_list = teams if isinstance(teams, list) else teams.get("teams", [])
    logger.info(f"Found {len(team_list)} teams")
    
    # Fetch all team data
    kenpom_data = []
    
    for i, team in enumerate(team_list, 1):
        team_name = team.get("TeamName")
        kpid = team.get("TeamID")
        
        try:
            ratings = get("ratings", {"team_id": kpid, "y": SEASON}) or []
            fourfactors = get("four-factors", {"team_id": kpid, "y": SEASON}) or []
            height = get("height", {"team_id": kpid, "y": SEASON}) or []
            misc = get("misc-stats", {"team_id": kpid, "y": SEASON}) or []
            
            ratings_data = ratings[0] if ratings else {}
            fourfactors_data = fourfactors[0] if fourfactors else {}
            height_data = height[0] if height else {}
            misc_data = misc[0] if misc else {}
            
            kenpom_data.append({
                'kpid': kpid,
                'team': team_name,
                'adjOffEff': ratings_data.get("AdjOE"),
                'adjDefEff': ratings_data.get("AdjDE"),
                'adjTempo': ratings_data.get("AdjTempo"),
                'effFgPct': fourfactors_data.get("eFG_Pct"),
                'defEffFgPct': fourfactors_data.get("DeFG_Pct"),
                'trnvrPct': fourfactors_data.get("TO_Pct"),
                'ftRate': fourfactors_data.get("FT_Rate"),
                'defFtRate': fourfactors_data.get("DFT_Rate"),
                'offRebPct': fourfactors_data.get("OR_Pct"),
                'defRebPct': fourfactors_data.get("DOR_Pct"),
                'effHeight': height_data.get("HgtEff"),
                'expRtg': height_data.get("Exp"),
                'benchRtg': height_data.get("Bench"),
                'contRtg': height_data.get("Continuity"),
                'threesPct': misc_data.get("FG3Pct"),
                'ftPct': misc_data.get("FTPct"),
                'blockPct': misc_data.get("BlockPct"),
                'stlRate': misc_data.get("StlRate"),
                'nonStlTrnvrRate': misc_data.get("OppNSTRate"),
                'astRate': misc_data.get("ARate"),
                'threesRate': misc_data.get("F3GRate"),
                'oppThreesPct': misc_data.get("OppFG3Pct"),
                'oppThreesRate': misc_data.get("OppF3GRate"),
            })
            
            if i % 50 == 0 or i == len(team_list):
                logger.info(f"Progress: {i}/{len(team_list)} teams fetched")
            
            time.sleep(DELAY_BETWEEN_TEAMS)
            
        except Exception as e:
            logger.error(f"Error fetching {team_name}: {e}")
    
    logger.info(f"Fetched data for {len(kenpom_data)} teams")
    
    # ==============================================
    # Normalize KenPom Data
    # ==============================================
    
    logger.info("Normalizing KenPom data")
    
    df = pd.DataFrame(kenpom_data)
    
    # Invert fields
    for field in INVERT_FIELDS:
        if field in df.columns:
            df[field] = -df[field]
            logger.info(f"Inverted {field}")
    
    # Z-score normalize
    for field in STAT_FIELDS:
        if field in df.columns:
            mean_val = df[field].mean()
            std_val = df[field].std()
            
            if std_val > 0:
                df[field] = (df[field] - mean_val) / std_val
            else:
                logger.warning(f"Zero std dev for {field}")
    
    logger.info("Normalization complete")
    
    # ==============================================
    # Connect to Supabase
    # ==============================================
    
    logger.info("Connecting to Supabase")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get today's date in CST
    cst = ZoneInfo("America/Chicago")
    today = datetime.now(cst).date()
    logger.info(f"Creating snapshots for {today}")
    
    # ==============================================
    # Create Daily Snapshots
    # ==============================================
    
    logger.info("Creating daily snapshots")
    
    # Get today's games
    cursor.execute("""
        SELECT game_id, game_date, home_kp_id, away_kp_id, home_team_name, away_team_name
        FROM games
        WHERE game_date = %s AND is_completed = false
    """, (today,))
    
    games = cursor.fetchall()
    logger.info(f"Found {len(games)} upcoming games for {today}")
    
    processed = 0
    
    for game in games:
        game_id, game_date, home_kp_id, away_kp_id, home_team_name, away_team_name = game
        
        home_stats = df[df['kpid'] == home_kp_id]
        away_stats = df[df['kpid'] == away_kp_id]
        
        if home_stats.empty or away_stats.empty:
            logger.warning(f"Missing KenPom data for game {game_id}")
            continue
        
        home_stats = home_stats.iloc[0]
        away_stats = away_stats.iloc[0]
        
        cursor.execute("""
            INSERT INTO daily_snapshots (
                created_datetime, game_id, game_date,
                home_kp_id, away_kp_id, home_team_name, away_team_name,
                is_home, is_neutral,
                home_adj_off_eff, home_eff_fg_pct, home_adj_def_eff, home_def_eff_fg_pct,
                home_adj_tempo, home_threes_pct, home_threes_rate, home_ft_rate,
                home_ft_pct, home_def_ft_rate, home_block_pct, home_opp_threes_pct,
                home_opp_threes_rate, home_stl_rate, home_non_stl_trnvr_rate, home_off_reb_pct,
                home_def_reb_pct, home_ast_rate, home_trnvr_pct, home_eff_height,
                home_exp_rtg, home_bench_rtg, home_cont_rtg,
                away_adj_off_eff, away_eff_fg_pct, away_adj_def_eff, away_def_eff_fg_pct,
                away_adj_tempo, away_threes_pct, away_threes_rate, away_ft_rate,
                away_ft_pct, away_def_ft_rate, away_block_pct, away_opp_threes_pct,
                away_opp_threes_rate, away_stl_rate, away_non_stl_trnvr_rate, away_off_reb_pct,
                away_def_reb_pct, away_ast_rate, away_trnvr_pct, away_eff_height,
                away_exp_rtg, away_bench_rtg, away_cont_rtg
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 
                       %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 
                       %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            datetime.now(), game_id, game_date,
            int(home_kp_id), int(away_kp_id), home_team_name, away_team_name,
            True, False,
            float(home_stats['adjOffEff']), float(home_stats['effFgPct']), float(home_stats['adjDefEff']), float(home_stats['defEffFgPct']),
            float(home_stats['adjTempo']), float(home_stats['threesPct']), float(home_stats['threesRate']), float(home_stats['ftRate']),
            float(home_stats['ftPct']), float(home_stats['defFtRate']), float(home_stats['blockPct']), float(home_stats['oppThreesPct']),
            float(home_stats['oppThreesRate']), float(home_stats['stlRate']), float(home_stats['nonStlTrnvrRate']), float(home_stats['offRebPct']),
            float(home_stats['defRebPct']), float(home_stats['astRate']), float(home_stats['trnvrPct']), float(home_stats['effHeight']),
            float(home_stats['expRtg']), float(home_stats['benchRtg']), float(home_stats['contRtg']),
            float(away_stats['adjOffEff']), float(away_stats['effFgPct']), float(away_stats['adjDefEff']), float(away_stats['defEffFgPct']),
            float(away_stats['adjTempo']), float(away_stats['threesPct']), float(away_stats['threesRate']), float(away_stats['ftRate']),
            float(away_stats['ftPct']), float(away_stats['defFtRate']), float(away_stats['blockPct']), float(away_stats['oppThreesPct']),
            float(away_stats['oppThreesRate']), float(away_stats['stlRate']), float(away_stats['nonStlTrnvrRate']), float(away_stats['offRebPct']),
            float(away_stats['defRebPct']), float(away_stats['astRate']), float(away_stats['trnvrPct']), float(away_stats['effHeight']),
            float(away_stats['expRtg']), float(away_stats['benchRtg']), float(away_stats['contRtg'])
        ))
        
        processed += 1
    
    conn.commit()
    logger.info(f"Created {processed} snapshots")
    
    # ==============================================
    # Update Completed Games
    # ==============================================
    
    logger.info("Updating completed games in snapshots")
    
    cursor.execute("""
        UPDATE daily_snapshots ds
        SET home_score = g.home_score,
            away_score = g.away_score,
            pt_diff = g.pt_diff,
            pt_total = g.pt_total
        FROM games g
        WHERE ds.game_id = g.game_id
        AND g.is_completed = true
        AND ds.home_score IS NULL
    """)
    
    updated = cursor.rowcount
    conn.commit()
    logger.info(f"Updated {updated} completed games")
    
    # ==============================================
    # Final Summary
    # ==============================================
    
    cursor.execute("SELECT COUNT(*) FROM daily_snapshots WHERE game_date = %s", (today,))
    total_today = cursor.fetchone()[0]
    
    logger.info("Pipeline complete - final summary:")
    logger.info(f"Snapshots created: {processed}")
    logger.info(f"Completed games updated: {updated}")
    logger.info(f"Total snapshots for {today}: {total_today}")
    
    conn.close()
    logger.info("Create Snapshots pipeline finished")

except Exception:
    logger.error("Create Snapshots ETL failed", exc_info=True)
    if 'conn' in locals():
        conn.close()
