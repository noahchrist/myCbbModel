import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    """
    Get Supabase Postgres connection using session pooler.
    Works from local development and AWS Lightsail.
    """
    password = os.getenv('SUPABASE_PASSWORD')
    
    if not password:
        raise ValueError("SUPABASE_PASSWORD not found in environment variables")
    
    conn_string = f"postgresql://postgres.guohwckbrahxhmijawoh:{password}@aws-1-us-east-1.pooler.supabase.com:5432/postgres"
    
    return psycopg2.connect(conn_string)

def test_connection():
    """Test database connection"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"✓ Connected: {version[0][:80]}...")
        conn.close()
        return True
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return False

if __name__ == "__main__":
    test_connection()