import time
import datetime
import sys
import threading

from app_modules import config
from app_modules import logger
from app_modules import utils
from app_modules import camera_handler
from app_modules import supabase_handler

try:
    from worker import hdg
except ImportError:
    logger.log_error("Failed to import 'hdg' from 'worker' package.", include_traceback=False)
    sys.exit("Critical Error: Cannot import HDG worker module.")

def process_hdg_source(source_config: dict, query_id: str, mac_address: str):
    source_name = source_config.get("name", "Unknown Anlage")
    ip_address = source_config.get("ip")
    if not ip_address:
        logger.log_error(f"IP missing for '{source_name}'")
        return

    logger.log_message(f"Processing: {source_name}, {ip_address}, {query_id}")
    try:
        result = hdg.fetch_hdg_data(ip_address, query_id)
        logger.log_message(f"Raw result ({source_name}): {result}")

        if not isinstance(result, list) or not result or not isinstance(result[0], dict) or 'text' not in result[0]:
            logger.log_error(f"Unexpected result format from {source_name}: {result}")
            return

        value = result[0]['text']

        data_to_save = {
            "anlage": source_name,
            "key": query_id,
            "value": value,
            "ip": ip_address,
            "mac": mac_address
        }

        if not supabase_handler.save_hdg_data(data_to_save):
            logger.log_error(f"Failed to save data for {source_name} ({query_id})")

    except AttributeError:
        logger.log_error("Function 'fetch_hdg_data' not found.", include_traceback=True)
    except Exception as e:
        logger.log_error(f"Error from {source_name} ({query_id}): {e}", include_traceback=True)

def screenshot_worker(mac_address: str):
    logger.log_message("Screenshot thread started.")
    last_taken = {8: None, 20: None}
    while True:
        now = datetime.datetime.now()
        hour = now.hour
        if hour in (8, 20):
            if last_taken[hour] is None or last_taken[hour].date() != now.date():
                logger.log_message(f"Taking scheduled screenshot for {hour}:00...")
                camera_handler.take_and_upload_screenshot(mac_address)
                last_taken[hour] = now
        time.sleep(60)

def main_loop():
    logger.log_message("=" * 30 + " Script Start " + "=" * 30)
    logger.log_message(f"Time: {datetime.datetime.now()}")

    try:
        config.check_essential_config()
    except ValueError as e:
        logger.log_error(f"Configuration error: {e}")
        sys.exit("Missing essential config")

    mac_address = utils.get_mac_address()
    logger.log_message(f"MAC: {mac_address}")

    if not supabase_handler.init_supabase_client():
        logger.log_error("Supabase init failed.")

    if config.CAMERA_RTSP_URL:
        threading.Thread(target=screenshot_worker, args=(mac_address,), daemon=True).start()
    else:
        logger.log_message("No CAMERA_RTSP_URL configured. Skipping screenshot thread.")

    cycle_count = 0
    while True:
        cycle_count += 1
        logger.log_message(f"--- Cycle {cycle_count} @ {datetime.datetime.now()} ---")

        query_data = utils.load_query_data()
        if not isinstance(query_data, list):
            logger.log_error("Invalid query data. Retrying in 10 minutes.")
            time.sleep(600)
            continue

        for idx, item in enumerate(query_data, 1):
            query_id = item.get("id")
            if query_id:
                for source in config.HDG_SOURCES:
                    process_hdg_source(source, str(query_id), mac_address)
                    time.sleep(1)

        logger.cleanup_old_logs()
        time.sleep(min(300, config.MAIN_LOOP_SLEEP_MINUTES * 60))
