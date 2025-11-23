import logging
from logging.handlers import TimedRotatingFileHandler
import os
import gzip
import shutil
from dotenv import load_dotenv
import socket

# ==============================
# Global Settings
# ==============================

IS_SERVER = socket.gethostname().startswith("ip-")

# Load .env from correct location
if IS_SERVER:
    # Load server .env
    load_dotenv("/home/ubuntu/env/weightroom.env")
else:
    # Load local .env (in project root)
    load_dotenv()

# Absolute path recommended (relative paths break when scripts run via cron/EventBridge)
LOG_DIR = os.environ.get("ETL_LOG_DIR")
os.makedirs(LOG_DIR, exist_ok=True)


# ==============================
# Optional compression for rolled logs
# ==============================

def _compress_old_logs(source_path):
    """Compress rotated log files to .gz to save space."""
    if not os.path.exists(source_path):
        return
    with open(source_path, 'rb') as f_in:
        with gzip.open(source_path + ".gz", 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    os.remove(source_path)


class GzipTimedRotatingFileHandler(TimedRotatingFileHandler):
    """TimedRotatingFileHandler that gzips old logs."""
    def rotate(self, source, dest):
        super().rotate(source, dest)
        _compress_old_logs(dest)


# ==============================
# Main Logger Builder
# ==============================

def get_logger(script_name: str) -> logging.Logger:
    """
    Creates a logger for a given ETL script with:
    - Daily midnight rotation
    - Gzip compression of old logs
    - 30-day retention
    - UTC timestamps
    - Safe duplicate handler protection
    """

    log_file = os.path.join(LOG_DIR, f"{script_name}.log")
    logger = logging.getLogger(script_name)
    logger.setLevel(logging.INFO)

    # Prevent duplicate handlers if imported multiple times
    if logger.handlers:
        return logger

    # -------- File Handler (rotating + gzip) --------
    file_handler = GzipTimedRotatingFileHandler(
        log_file,
        when="midnight",
        interval=1,
        backupCount=30,
        utc=True
    )

    # CloudWatch-friendly timestamp format
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] (%(module)s:%(lineno)d): %(message)s",
        "%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(formatter)

    # -------- Optional: Log to STDOUT as well --------
    # (useful for debugging or container logs)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Attach handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
