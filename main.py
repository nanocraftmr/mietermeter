import os
from dotenv import load_dotenv
import json
from supabase import create_client, Client
import datetime
import traceback
import time  # Import the time module

load_dotenv()

HDGIP1 = os.getenv('HDGIP1')
HDGIP2 = os.getenv('HDGIP2')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

from worker import hdg

# --- Logging Configuration ---
LOG_FILE = "hdg_script.log"  # File to store logs
def log_message(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as log_file:
        log_file.write(f"[{timestamp}] {message}\n")
    print(message)  # Also print to console
def log_error(message):
    log_message(f"ERROR: {message}")  # Use log_message for consistency

def main():
    log_message("Script started")

    while True:  # Run indefinitely
        next_run = calculate_next_run()
        sleep_duration = (next_run - datetime.datetime.now()).total_seconds()
        if sleep_duration > 0:
            log_message(f"Sleeping for {sleep_duration:.2f} seconds until {next_run}")
            time.sleep(sleep_duration)
        else:
            log_message("Already past the scheduled time, running immediately.")

        try:
            with open("hdg_format/data.json", "r") as f:
                query_data = json.load(f)
        except FileNotFoundError:
            log_error("Error: 'data.json' not found.  Please create the file.")
            continue
        except json.JSONDecodeError:
            log_error("Error: 'data.json' is not a valid JSON file. Please check its format.")
            continue
        except Exception as e:
            log_error(f"Error loading JSON: {e}")
            continue

        if not all([SUPABASE_URL, SUPABASE_KEY, HDGIP1, HDGIP2]):
            log_error("Error: One or more environment variables (SUPABASE_URL, SUPABASE_KEY, HDGIP1, HDGIP2) are not set.")
            continue


        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

        for item in query_data:
            query_id = str(item.get("id"))

            if query_id:
                try:
                    # Fetch data from HDGIP1
                    result1 = hdg.fetch_hdg_data(HDGIP1, query_id)
                    value1 = result1[0]['text']
                    log_message(f"Result -- anlage: Brenner 1, ip: {HDGIP1}, key: {query_id}, value: {value1}")

                    # Upload to Supabase for Brenner 1
                    data1 = {
                        "anlage": "Brenner 1",
                        "key": query_id,
                        "value": value1,
                        "ip": HDGIP1
                    }
                    try:
                        data, count = supabase.table("hdg_meter").insert(data1).execute()
                        log_message(f"Successfully uploaded to Supabase: Brenner 1, ID {query_id}")
                    except Exception as supa_e:
                        log_error(f"Supabase Error (Brenner 1 - ID {query_id}): {supa_e}\n{traceback.format_exc()}")

                except Exception as e:
                    log_error(f"Brenner 1 - Error fetching data for ID {query_id}: {e}\n{traceback.format_exc()}")

                try:
                    # Fetch data from HDGIP2
                    result2 = hdg.fetch_hdg_data(HDGIP2, query_id)
                    value2 = result2[0]['text']
                    log_message(f"Result -- anlage: Brenner 2, ip: {HDGIP2}, key: {query_id}, value: {value2}")

                    # Upload to Supabase for Brenner 2
                    data2 = {
                        "anlage": "Brenner 2",
                        "key": query_id,
                        "value": value2,
                        "ip": HDGIP2
                    }
                    try:
                        data, count = supabase.table("hdg_meter").insert(data2).execute()
                        log_message(f"Successfully uploaded to Supabase: Brenner 2, ID {query_id}")
                    except Exception as supa_e:
                        log_error(f"Supabase Error (Brenner 2 - ID {query_id}): {supa_e}\n{traceback.format_exc()}")

                except Exception as e:
                    log_error(f"Brenner 2 - Error fetching data for ID {query_id}: {e}\n{traceback.format_exc()}")

            else:
                log_message(f"Warning: Skipping item because 'id' is missing or invalid: {item}")

        log_message("Data processing complete.")


def calculate_next_run():
    """Calculates the next scheduled run time (8 AM and 8 PM)."""
    now = datetime.datetime.now()
    next_run_am = now.replace(hour=8, minute=0, second=0, microsecond=0)
    next_run_pm = now.replace(hour=20, minute=0, second=0, microsecond=0)

    if now > next_run_pm:
        next_run_am += datetime.timedelta(days=1)  # If already past 8pm, add 1 day
    elif now > next_run_am:
        # If we passed the 8am time and are between 8am and 8pm
        pass # The next time to run will be 8pm
    else:
        next_run_pm = next_run_pm.replace(day=next_run_am.day)

    return min(next_run_am, next_run_pm)



if __name__ == "__main__":
    main()