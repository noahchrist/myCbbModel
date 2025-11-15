import sqlite3
import os
from datetime import datetime

# Anchor paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(BACKEND_DIR, 'data', 'master.db')

def compile_target_tables():
    """Compile all setTarget tables into setTarget2026 with game_date column"""
    print("🔄 Compiling setTarget tables...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all setTarget table names
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'setTarget_%'")
    target_tables = [row[0] for row in cursor.fetchall()]
    
    if not target_tables:
        print("❌ No setTarget tables found")
        conn.close()
        return
    
    print(f"📊 Found {len(target_tables)} setTarget tables")
    
    # Drop existing setTarget2026 if it exists
    cursor.execute("DROP TABLE IF EXISTS setTarget2026")
    
    # Get schema from first table and create setTarget2026
    first_table = target_tables[0]
    cursor.execute(f"PRAGMA table_info({first_table})")
    columns = cursor.fetchall()
    
    # Build CREATE TABLE statement with game_date after season
    create_cols = []
    for col in columns:
        col_name, col_type = col[1], col[2]
        create_cols.append(f"{col_name} {col_type}")
        if col_name == 'season':
            create_cols.append("game_date DATE")
    
    create_sql = f"CREATE TABLE setTarget2026 ({', '.join(create_cols)})"
    cursor.execute(create_sql)
    print("✅ Created setTarget2026 table")
    
    # Insert data from each table
    total_rows = 0
    for table_name in target_tables:
        # Extract date from table name (setTarget_MMDDYYYY)
        date_part = table_name.replace('setTarget_', '')
        try:
            # Parse MMDDYYYY format
            date_obj = datetime.strptime(date_part, '%m%d%Y')
            game_date = date_obj.strftime('%Y-%m-%d')
        except ValueError:
            print(f"⚠️ Could not parse date from {table_name}, skipping")
            continue
        
        # Get column names (excluding game_date which we'll add)
        cursor.execute(f"PRAGMA table_info({table_name})")
        table_cols = [col[1] for col in cursor.fetchall()]
        
        # Insert with game_date
        col_list = ', '.join(table_cols)
        placeholders = ', '.join(['?' for _ in table_cols] + ['?'])
        
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
        
        for row in rows:
            cursor.execute(f"""
                INSERT INTO setTarget2026 ({col_list}, game_date) 
                VALUES ({placeholders})
            """, list(row) + [game_date])
        
        print(f"📥 Loaded {len(rows)} rows from {table_name} (date: {game_date})")
        total_rows += len(rows)
    
    conn.commit()
    conn.close()
    
    print(f"🎉 Compilation complete! Total rows: {total_rows}")
    print("✅ setTarget2026 table created with game_date column")

if __name__ == "__main__":
    compile_target_tables()