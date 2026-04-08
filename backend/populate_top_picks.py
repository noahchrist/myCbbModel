#!/usr/bin/env python3
"""
Backfill Top Picks (model 999) into modelPredictions.

Replicates the frontend fetchTopPicks() logic:
  1. For each day, get all completed non-999 predictions
  2. Group by (game_id, pick_text, w_l)  -- pick_text = text after "Pick:" in summary
  3. community_edge = SUM(group edges) / total_distinct_models_today
  4. Filter: community_edge >= 3.0
  5. Sort DESC, take top 5
  6. Insert as modelId=999 rows with unitsBet=1.0

Usage:
  python populate_top_picks.py [--db-path /path/to/master.db] [--dry-run] [--force]

Options:
  --db-path   Path to SQLite DB (falls back to DB_PATH env var or .env)
  --dry-run   Print what would be inserted without writing to DB
  --force     Recompute and replace model 999 rows even for dates already populated
"""

import sqlite3
import os
import sys
import argparse
from dotenv import load_dotenv

load_dotenv()


def calc_units_won(pick, w_l, row):
    """Calculate unitsWon for a 1-unit flat bet given pick direction and result."""
    if w_l == 'l':
        return -1.0

    # Determine the applicable price from FD odds columns
    if 'Over' in pick:
        price = row['fd_overPrice']
    elif 'Under' in pick:
        price = row['fd_underPrice']
    else:
        # Spread pick — check if the home team name appears in the pick text
        home_team = row['home_team'] or ''
        if home_team and home_team in pick:
            price = row['fd_home_spreadPrice']
        else:
            price = row['fd_away_spreadPrice']

    if price is None:
        return 0.0
    price = int(price)
    if price < 0:
        return round(100 / abs(price), 4)
    else:
        return round(price / 100, 4)


def get_pick_text(summary):
    """Extract pick text from summary string (text after 'Pick:')."""
    if summary and 'Pick:' in summary:
        return summary.split('Pick:')[1].strip()
    return ''


def compute_top_picks_for_date(rows):
    """
    Given all non-999 completed predictions for a single date,
    return list of top-pick dicts (matches frontend fetchTopPicks logic).
    """
    if not rows:
        return []

    total_models = len(set(r['modelId'] for r in rows))

    # Group by (game_id, pick_text, w_l)
    pick_map = {}
    for row in rows:
        pick = get_pick_text(row['summary'])
        if not pick or not row['game_id']:
            continue
        w_l = row['w_l'] or 'pending'
        key = (row['game_id'], pick, w_l)
        if key not in pick_map:
            pick_map[key] = {'total_edge': 0.0, 'model_count': 0, 'sample_row': row}
        pick_map[key]['total_edge'] += row['edge'] or 0.0
        pick_map[key]['model_count'] += 1

    # Compute community edge, filter >= 3.0
    picks = []
    for (game_id, pick, w_l), data in pick_map.items():
        community_edge = data['total_edge'] / total_models
        if community_edge >= 3.0:
            picks.append({
                'game_id': game_id,
                'pick': pick,
                'w_l': w_l,
                'community_edge': round(community_edge, 4),
                'model_count': data['model_count'],
                'total_models': total_models,
                'row': data['sample_row'],
            })

    # Sort DESC by community_edge, take top 5
    picks.sort(key=lambda x: x['community_edge'], reverse=True)
    return picks[:5]


def populate_top_picks(db_path, dry_run=False, force=False):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # All dates with completed non-999 predictions
    cursor.execute("""
        SELECT DISTINCT game_date
        FROM modelPredictions
        WHERE modelId != 999 AND is_completed = 1
        ORDER BY game_date
    """)
    all_dates = [row[0] for row in cursor.fetchall()]
    print(f"Dates with completed predictions: {len(all_dates)}")

    # Dates already populated for model 999
    cursor.execute("SELECT DISTINCT game_date FROM modelPredictions WHERE modelId = 999")
    existing_dates = set(row[0] for row in cursor.fetchall())
    print(f"Dates already populated for model 999: {len(existing_dates)}")

    if force:
        dates_to_process = all_dates
        print(f"--force: reprocessing all {len(dates_to_process)} dates")
    else:
        dates_to_process = [d for d in all_dates if d not in existing_dates]
        print(f"New dates to process: {len(dates_to_process)}")

    if not dates_to_process:
        print("Nothing to do.")
        conn.close()
        return

    total_inserted = 0
    total_deleted = 0

    for date in dates_to_process:
        # Fetch all completed non-999 predictions for this date
        cursor.execute("""
            SELECT game_id, modelId, game_date, is_completed,
                   home_team, home_score, away_team, away_score, pt_diff, pt_total,
                   fd_home_spread, fd_home_spreadPrice,
                   fd_away_spread, fd_away_spreadPrice,
                   fd_over, fd_overPrice, fd_under, fd_underPrice,
                   edge, w_l, summary, bet_type
            FROM modelPredictions
            WHERE game_date = ? AND modelId != 999 AND is_completed = 1
        """, (date,))
        rows = [dict(r) for r in cursor.fetchall()]

        if not rows:
            continue

        top_picks = compute_top_picks_for_date(rows)

        if not top_picks:
            print(f"{date}: no qualifying picks (0 above 3.0 threshold)")
            continue

        print(f"{date}: {len(top_picks)} top picks "
              f"(edges: {', '.join(str(p['community_edge']) for p in top_picks)}) "
              f"[{top_picks[0]['total_models']} models active]")

        if not dry_run:
            # If force, delete existing model 999 rows for this date first
            if force and date in existing_dates:
                cursor.execute(
                    "DELETE FROM modelPredictions WHERE modelId = 999 AND game_date = ?",
                    (date,)
                )
                total_deleted += cursor.rowcount

            for p in top_picks:
                row = p['row']
                units_won = calc_units_won(p['pick'], p['w_l'], row)

                cursor.execute("""
                    INSERT INTO modelPredictions
                    (datePredicted, modelId, game_id, game_date, is_completed,
                     home_team, home_score, away_team, away_score, pt_diff, pt_total,
                     fd_home_spread, fd_home_spreadPrice,
                     fd_away_spread, fd_away_spreadPrice,
                     fd_over, fd_overPrice, fd_under, fd_underPrice,
                     edge, unitsBet, unitsWon, w_l, summary, bet_type)
                    VALUES (?, 999, ?, ?, ?,
                            ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, ?,
                            ?, ?, ?, ?,
                            ?, 1.0, ?, ?, ?, ?)
                """, (
                    date,                        # datePredicted = game_date (retroactive)
                    row['game_id'],
                    date,                        # game_date
                    row['is_completed'],
                    row['home_team'],
                    row['home_score'],
                    row['away_team'],
                    row['away_score'],
                    row['pt_diff'],
                    row['pt_total'],
                    row['fd_home_spread'],
                    row['fd_home_spreadPrice'],
                    row['fd_away_spread'],
                    row['fd_away_spreadPrice'],
                    row['fd_over'],
                    row['fd_overPrice'],
                    row['fd_under'],
                    row['fd_underPrice'],
                    p['community_edge'],
                    units_won,
                    p['w_l'],
                    f"Community Pick | Pick: {p['pick']}",
                    row['bet_type'],
                ))
                total_inserted += 1

            conn.commit()

    conn.close()

    if dry_run:
        print(f"\nDRY RUN complete — would have inserted picks for "
              f"{len(dates_to_process)} dates")
    else:
        if total_deleted:
            print(f"\nDeleted {total_deleted} existing model 999 rows (--force)")
        print(f"Inserted {total_inserted} model 999 predictions across "
              f"{len(dates_to_process)} dates")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Backfill Top Picks (model 999) into modelPredictions'
    )
    parser.add_argument('--db-path', help='Path to SQLite database')
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Print what would be inserted without writing to DB'
    )
    parser.add_argument(
        '--force', action='store_true',
        help='Recompute and replace model 999 rows for all dates (including already populated)'
    )
    args = parser.parse_args()

    db_path = args.db_path or os.environ.get('DB_PATH')
    if not db_path:
        print("Error: DB_PATH not set. Use --db-path or set DB_PATH in environment/.env")
        sys.exit(1)

    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    print(f"Database: {db_path}")
    if args.dry_run:
        print("Mode: DRY RUN (no changes will be made)")
    elif args.force:
        print("Mode: FORCE (will replace existing model 999 rows)")
    else:
        print("Mode: INSERT (skipping dates already populated)")
    print()

    populate_top_picks(db_path, dry_run=args.dry_run, force=args.force)
