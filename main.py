import os
from dotenv import load_dotenv
import json
from supabase import create_client, Client
import datetime
import traceback
import time

load_dotenv()

HDGIP1 = os.getenv('HDGIP1')
HDGIP2 = os.getenv('HDGIP2')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

from worker import hdg

# Set up logging
LOG_FILE = "hdg_script.log"
def log_message(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as log_file:
        log_file.write(f"[{timestamp}] {message}\n")
    print(message)
    
def log_error(message):
    log_message(f"ERROR: {message}")

def main():
    log_message("Script started")

    # Run forever
    while True:
        try:
            # Try to load the list of IDs we need to fetch
            with open("hdg_format/data.json", "r") as f:
                query_data = json.load(f)
        except FileNotFoundError:
            log_error("Can't find 'data.json'. Create it first!")
            time.sleep(60)  # Wait a bit before retrying
            continue
        except json.JSONDecodeError:
            log_error("Bad JSON in data.json. Fix it!")
            time.sleep(60)
            continue
        except Exception as e:
            log_error(f"Problem with JSON: {e}")
            time.sleep(60)
            continue

        # Make sure we have everything we need
        if not all([SUPABASE_URL, SUPABASE_KEY, HDGIP1, HDGIP2]):
            log_error("Missing some env vars. Check .env file!")
            time.sleep(60)
            continue

        # Connect to Supabase
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

        # Process each ID
        for item in query_data:
            query_id = str(item.get("id"))

            if query_id:
                # Get data from Brenner 1
                try:
                    result1 = hdg.fetch_hdg_data(HDGIP1, query_id)
                    value1 = result1[0]['text']
                    log_message(f"Result -- anlage: Brenner 1, ip: {HDGIP1}, key: {query_id}, value: {value1}")

                    # Save to database
                    data1 = {
                        "anlage": "Brenner 1",
                        "key": query_id,
                        "value": value1,
                        "ip": HDGIP1
                    }
                    try:
                        data, count = supabase.table("hdg_meter").insert(data1).execute()
                        log_message(f"Saved to DB: Brenner 1, ID {query_id}")
                    except Exception as supa_e:
                        log_error(f"DB error (Brenner 1 - ID {query_id}): {supa_e}\n{traceback.format_exc()}")

                except Exception as e:
                    log_error(f"Brenner 1 - Failed to get data for ID {query_id}: {e}\n{traceback.format_exc()}")

                # Get data from Brenner 2
                try:
                    result2 = hdg.fetch_hdg_data(HDGIP2, query_id)
                    value2 = result2[0]['text']
                    log_message(f"Result -- anlage: Brenner 2, ip: {HDGIP2}, key: {query_id}, value: {value2}")

                    # Save to database
                    data2 = {
                        "anlage": "Brenner 2",
                        "key": query_id,
                        "value": value2,
                        "ip": HDGIP2
                    }
                    try:
                        data, count = supabase.table("hdg_meter").insert(data2).execute()
                        log_message(f"Saved to DB: Brenner 2, ID {query_id}")
                    except Exception as supa_e:
                        log_error(f"DB error (Brenner 2 - ID {query_id}): {supa_e}\n{traceback.format_exc()}")

                except Exception as e:
                    log_error(f"Brenner 2 - Failed to get data for ID {query_id}: {e}\n{traceback.format_exc()}")

            else:
                log_message(f"Skipping item with missing ID: {item}")

        log_message("All done! Waiting 10 minutes before next run...")
        
        # Wait 10 minutes before doing it all again
        time.sleep(600)  # 10 minutes in seconds


if __name__ == "__main__":
    main()