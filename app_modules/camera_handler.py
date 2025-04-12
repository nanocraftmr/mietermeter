# app_modules/camera_handler.py
import cv2
import time
import datetime
import os
# Use relative imports for modules in the same package
from . import config
from . import logger
from . import supabase_handler

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