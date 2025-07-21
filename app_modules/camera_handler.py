import time
import datetime
import sys
import threading
import cv2
import os

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

# To prevent multiple screenshots if the loop runs very fast near the designated hour
_last_screenshot_hour = -1
_last_screenshot_day = -1

def take_and_upload_screenshot(mac_address: str):
    """Takes a screenshot from the configured camera and uploads it to Supabase."""
    global _last_screenshot_hour, _last_screenshot_day

    if not config.CAMERA_RTSP_URL:
        logger.log_message("CAMERA_RTSP_URL not configured in .env. Skipping screenshot.")
        return

    # Check if we already took a screenshot this hour to avoid duplicates
    now = datetime.datetime.now()
    current_hour = now.hour
    current_day = now.day
    if current_hour == _last_screenshot_hour and current_day == _last_screenshot_day:
        logger.log_message(f"Screenshot already taken for hour {current_hour}. Skipping.")
        return

    logger.log_message(f"Attempting to take screenshot from {config.CAMERA_RTSP_URL}...")
    cap = None # Initialize cap to None
    try:
        # Open the RTSP stream
        # Consider adding environment variable for backend preference if needed e.g., cv2.CAP_FFMPEG
        cap = cv2.VideoCapture(config.CAMERA_RTSP_URL)

        # Check if camera opened successfully
        if not cap.isOpened():
            logger.log_error(f"Cannot open RTSP stream: {config.CAMERA_RTSP_URL}", include_traceback=False)
            return

        # Set buffer size (optional, might help with latency on some systems)
        # cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # Allow time for the stream buffer to potentially fill or connection to establish
        # Reading immediately might grab an old frame on some streams
        time.sleep(2) # Adjust timeout if needed based on camera/network

        # Attempt to grab and retrieve a frame
        ret, frame = cap.read()

        # Check if frame was read successfully
        if ret and frame is not None:
            logger.log_message("Frame captured successfully.")

            # Encode frame to JPG bytes
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 90] # Adjust quality 0-100
            ret_enc, buffer = cv2.imencode('.jpg', frame, encode_param)

            if not ret_enc:
                logger.log_error("Failed to encode frame to JPG format.", include_traceback=False)
                return

            image_bytes = buffer.tobytes()

            # Prepare storage path
            # Use the full MAC address with colons for the folder name
            folder_name = mac_address
            timestamp = now.strftime("%Y%m%d_%H%M%S")
            filename = f"{mac_address}_{timestamp}.jpg"
            # Ensure bucket path uses forward slashes, even on Windows
            bucket_path = f"{folder_name}/{filename}"

            # Upload using the Supabase handler
            success = supabase_handler.upload_image_to_storage(image_bytes, bucket_path)
            if success:
                 logger.log_message(f"Screenshot uploaded successfully for MAC: {mac_address} to {bucket_path}")
                 # Update last screenshot time only on successful upload
                 _last_screenshot_hour = current_hour
                 _last_screenshot_day = current_day
            # else: Error logging is handled within upload_image_to_storage

        elif frame is None:
             logger.log_error("Captured frame is empty (None). Check camera connection, RTSP URL, credentials, and network.", include_traceback=False)
        else: # ret was False
            logger.log_error("Failed to read frame from the RTSP stream (ret=False). Check camera connection/stream.", include_traceback=False)

    except cv2.error as cv_err:
         logger.log_error(f"OpenCV error during screenshot capture: {cv_err}", include_traceback=True)
    except Exception as e:
        logger.log_error(f"Unexpected error during screenshot process: {e}", include_traceback=True)
    finally:
        # Ensure the capture device is released
        if cap is not None and cap.isOpened():
            cap.release()
            logger.log_message("Camera resource released.")
        # Consider cv2.destroyAllWindows() if you were displaying images

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
