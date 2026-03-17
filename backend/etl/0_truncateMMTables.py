import sqlite3
import os
from dotenv import load_dotenv
from logger import get_logger

logger = get_logger("0_truncateMMTables")

load_dotenv()
DB_PATH = os.environ.get('DB_PATH')

if not DB_PATH:
    raise ValueError("Missing DB_PATH in environment variables or .env file")

TABLES = ["modelPredictionsMM", "setTargetMM", "gamesMM"]

logger.info("Starting one-time MM table truncation...")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

for table in TABLES:
    cursor.execute(f"DELETE FROM {table}")
    deleted = cursor.rowcount
    conn.commit()
    logger.info(f"Truncated {table}: {deleted} rows removed")

conn.close()
logger.info("Truncation complete")
