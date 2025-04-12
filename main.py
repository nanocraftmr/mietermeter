# main.py
import time
import datetime
import sys

# Import from our application modules package
from app_modules import config
from app_modules import logger
from app_modules import utils
from app_modules import camera_handler
from app_modules import supabase_handler

from supabase import Client
from typing import Optional
_supabase_client: Optional[Client] = None

# Try importing from the worker package (requires worker/__init__.py)
try:
    from worker import hdg
except ImportError:
    logger.log_error("Failed to import 'hdg' from 'worker' package. Ensure 'worker/__init__.py' exists and 'worker/hdg.py' is correct.", include_traceback=False)
    sys.exit("Critical Error: Cannot import HDG worker module.")


def process_hdg_source(source_config: dict, query_id: str, mac_address: str):
    """Fetches data from a single HDG source and saves it via Supabase handler."""
    source_name = source_config.get("name", "Unknown Anlage")
    ip_address = source_config.get("ip")

    if not ip_address:
        logger.log_error(f"IP address missing for source '{source_name}' in config. Skipping.", include_traceback=False)
        return # Skip this source if IP is missing

    logger.log_message(f"Processing: Anlage={source_name}, IP={ip_address}, QueryID={query_id}")

    try:
        # --- Fetch data using the external worker ---
        # This relies on your worker/hdg.py providing fetch_hdg_data
        result = hdg.fetch_hdg_data(ip_address, query_id)
        logger.log_message(f"Raw result from worker ({source_name}, ID {query_id}): {result}")

        # --- Validate and Extract Data ---
        # Adjust validation based on the *actual* structure returned by your worker
        if not isinstance(result, list) or not result or not isinstance(result[0], dict) or 'text' not in result[0]:
             logger.log_error(f"Unexpected result format from fetch_hdg_data for {source_name} (ID {query_id}). Expected list with dict containing 'text'. Got: {result}", include_traceback=False)
             return # Skip saving if format is wrong

        value = result[0]['text'] # Extract the relevant value

        # Optional: Add specific validation or type conversion for 'value' here if needed
        # e.g., if value needs to be numeric:
        # try:
        #     numeric_value = float(value)
        # except (ValueError, TypeError):
        #     logger.log_error(f"Value '{value}' from {source_name} (ID {query_id}) is not a valid number. Skipping save.", include_traceback=False)
        #     return

        logger.log_message(f"Extracted -- Anlage: {source_name}, Key: {query_id}, Value: {value}")

        # --- Prepare data for Supabase ---
        data_to_save = {
            "anlage": source_name,
            "key": query_id,        # Ensure this matches your table column name
            "value": value,         # Ensure value type matches table column type
            "ip": ip_address,       # Ensure this matches your table column name
            "mac": mac_address      # Ensure this matches your table column name
        }

        # --- Save data using the Supabase handler ---
        success = supabase_handler.save_hdg_data(data_to_save)
        if not success:
             logger.log_error(f"Failed attempt to save data for {source_name} (ID {query_id}) to Supabase.", include_traceback=False)
        # Detailed error logging happens within save_hdg_data

    # Catch specific errors if your worker raises them, otherwise catch general exceptions
    except AttributeError:
         logger.log_error(f"Function 'fetch_hdg_data' not found in imported 'worker.hdg' module. Check 'worker/hdg.py'.", include_traceback=True)
    except Exception as e:
        # Log errors during fetch or processing for a specific source/ID
        logger.log_error(f"Failed to get or process data from {source_name} (ID {query_id}): {e}", include_traceback=True)


def main_loop():
    """The main execution loop of the application."""
    logger.log_message("=" * 30 + " Script Start " + "=" * 30)
    logger.log_message(f"Current Time: {datetime.datetime.now()}") # Log start time

    # --- Initial Setup ---
    try:
        # Check essential config variables from .env
        config.check_essential_config()
        logger.log_message("Essential configuration variables check passed.")
    except ValueError as e:
        # Logger already prints details in check_essential_config
        logger.log_error(f"Configuration error: {e}. Please check your .env file. Exiting.", include_traceback=False)
        sys.exit("Critical Error: Missing essential configuration.") # Stop execution

    # Get MAC address
    mac_address = utils.get_mac_address()
    logger.log_message(f"Running with MAC Address: {mac_address}")

    # Initialize Supabase client (errors logged within)
    supabase_client = supabase_handler.init_supabase_client()
    if not supabase_client:
         # Allow script to continue? Or exit? Depends on requirements.
         logger.log_error("Failed to initialize Supabase. Database operations will fail.", include_traceback=False)
         # If Supabase is absolutely critical, uncomment the next line:
         # sys.exit("Critical Error: Cannot connect to Supabase.")

    # --- Initial Screenshot (if camera configured) ---
    if config.CAMERA_RTSP_URL:
        logger.log_message("Attempting initial camera screenshot...")
        camera_handler.take_and_upload_screenshot(mac_address)
    else:
        logger.log_message("Camera URL not set in .env, skipping initial screenshot.")

    # --- Main Processing Cycle ---
    cycle_count = 0
    while True:
        cycle_count += 1
        logger.log_message("-" * 20 + f" Starting Cycle {cycle_count} at {datetime.datetime.now()} " + "-" * 20)

        # --- Load Query Data ---
        query_data = utils.load_query_data()
        if query_data is None:
            logger.log_error("Failed to load query data for this cycle. Will retry later.", include_traceback=False)
            # Wait longer before retrying if data file is missing/corrupt
            sleep_duration = 60 * 10 # Wait 10 minutes before retrying data load
            logger.log_message(f"Waiting {sleep_duration // 60} minutes due to query data load failure...")
            time.sleep(sleep_duration)
            continue # Skip rest of the cycle

        # --- Process HDG Sources ---
        if isinstance(query_data, list) and query_data:
            logger.log_message(f"Processing {len(query_data)} query items...")
            item_count = 0
            for item in query_data:
                item_count += 1
                query_id = item.get("id") # Safely get 'id'
                if query_id is not None: # Check if ID exists and is not None
                    query_id_str = str(query_id) # Ensure it's a string
                    logger.log_message(f"--- Item {item_count}/{len(query_data)}, Query ID: {query_id_str} ---")
                    # Process this ID for all configured HDG sources
                    for source_config in config.HDG_SOURCES:
                        process_hdg_source(source_config, query_id_str, mac_address)
                        time.sleep(1) # Small delay between HDG API calls if needed
                else:
                    logger.log_message(f"Skipping item {item_count}/{len(query_data)} due to missing or invalid 'id': {item}")
            logger.log_message(f"Finished processing query items.")
        else:
             logger.log_error(f"Query data loaded but is not a non-empty list. Check content of '{config.QUERY_DATA_FILE}'. Type: {type(query_data)}")

        # --- Periodic Screenshot Logic ---
        now = datetime.datetime.now()
        current_hour = now.hour
        if config.CAMERA_RTSP_URL and current_hour in config.SCREENSHOT_HOURS:
             logger.log_message(f"Current hour ({current_hour}) is a designated screenshot hour. Attempting screenshot.")
             # camera_handler internally checks if screenshot was already taken this hour
             camera_handler.take_and_upload_screenshot(mac_address)
        # else: Not a designated hour or camera not configured

        # --- Cycle End & Wait ---
        logger.log_message(f"Cycle {cycle_count} complete.")
        logger.cleanup_old_logs() # Clean logs at the end of the cycle
        wait_seconds = config.MAIN_LOOP_SLEEP_MINUTES * 60
        logger.log_message(f"Waiting for {config.MAIN_LOOP_SLEEP_MINUTES} minutes ({wait_seconds} seconds) before next cycle...")
        time.sleep(wait_seconds)


# --- Main Execution Block ---
if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        logger.log_message("\n" + "=" * 30 + " Script interrupted by user (Ctrl+C) " + "=" * 30)
        print("Exiting gracefully.")
    except SystemExit as exit_e: # Catch sys.exit calls
         logger.log_error(f"Script exited via sys.exit: {exit_e}", include_traceback=False)
         print(f"Script exited: {exit_e}")
    except Exception as e:
        # Catch any unexpected errors at the top level during main_loop execution
        logger.log_error(f"An unexpected critical error occurred in main_loop: {e}", include_traceback=True)
        print(f"An unexpected critical error occurred: {e}")
        # Optional: exit with an error code
        # sys.exit(1)
    finally:
        logger.log_message("=" * 30 + " Script End " + "=" * 30)