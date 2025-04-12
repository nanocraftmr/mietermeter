# app_modules/config.py
import os
from dotenv import load_dotenv

# Load environment variables from .env file located in the parent directory
# Assumes .env is in the same directory as main.py
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path=dotenv_path)

# --- Environment Variables ---
HDGIP1 = os.getenv('HDGIP1')
HDGIP2 = os.getenv('HDGIP2')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
CAMERA_RTSP_URL = os.getenv('CAMERA') # Renamed for clarity

# --- Application Constants ---
LOG_FILE = "hdg_script.log" # Log file will be created in the directory where main.py is run
LOG_RETENTION_DAYS = 7
QUERY_DATA_FILE = "hdg_format/data.json" # Assumes hdg_format dir is relative to where main.py runs
SUPABASE_BUCKET = "hackbunker" # Your Supabase bucket name
SUPABASE_TABLE = "hdg_meter" # Your Supabase table name
MAIN_LOOP_SLEEP_MINUTES = 120
HDG_SOURCES = [
    {"name": "Brenner 1", "ip": HDGIP1},
    {"name": "Brenner 2", "ip": HDGIP2},
]
# Hours of the day (0-23) to take screenshots (e.g., Midnight, Noon)
SCREENSHOT_HOURS = [0, 12]

# --- Validation ---
def check_essential_config():
    """Checks if essential configuration variables are set."""
    essential_vars = {
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_KEY": SUPABASE_KEY,
        "HDGIP1": HDGIP1,
        "HDGIP2": HDGIP2,
        # CAMERA_RTSP_URL is optional for the core loop, checked separately where needed
    }
    missing = [name for name, value in essential_vars.items() if not value]
    if missing:
        # Ensure logger is available before raising, or just print
        print(f"ERROR: Missing essential environment variables: {', '.join(missing)}. Check .env file!")
        raise ValueError(f"Missing essential environment variables: {', '.join(missing)}. Check .env file!")
    return True