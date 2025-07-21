import datetime
import re
import traceback
import os
# Use relative import to get config from the same package
from . import config

# Ensure log file path is relative to the script execution directory (where main.py is)
LOG_FILE_PATH = os.path.abspath(config.LOG_FILE)

def _get_timestamp():
    """Returns the current timestamp in a standard format."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log_message(message):
    """Logs an informational message to console and file."""
    log_entry = f"[{_get_timestamp()}] INFO: {message}"
    print(log_entry)
    try:
        with open(LOG_FILE_PATH, "a") as log_file:
            log_file.write(log_entry + "\n")
    except Exception as e:
        print(f"[{_get_timestamp()}] logger.py ERROR: Failed to write to log file '{LOG_FILE_PATH}': {e}")

def log_error(message, include_traceback=True):
    """Logs an error message to console and file, optionally including traceback."""
    tb_info = ""
    if include_traceback:
        # Capture traceback only if an exception occurred
        exc_info = traceback.format_exc()
        # Avoid printing full traceback if it's just 'NoneType: None\n'
        if "NoneType: None" not in exc_info:
             tb_info = f"\n{exc_info}"

    log_entry = f"[{_get_timestamp()}] ERROR: {message}{tb_info}"
    print(log_entry) # Print errors prominently
    try:
        with open(LOG_FILE_PATH, "a") as log_file:
            log_file.write(log_entry + "\n")
    except Exception as e:
        print(f"[{_get_timestamp()}] logger.py ERROR: Failed to write error to log file '{LOG_FILE_PATH}': {e}")


def cleanup_old_logs():
    """Clears the log file if it exceeds 5 MB."""
    max_log_size = 5 * 1024 * 1024  # 5 MB
    try:
        if os.path.exists(LOG_FILE_PATH) and os.path.getsize(LOG_FILE_PATH) > max_log_size:
            log_message(f"Log file exceeds {max_log_size / (1024 * 1024)} MB. Truncating the file.")
            with open(LOG_FILE_PATH, "w") as f:
                f.truncate()
    except Exception as e:
        log_error(f"Failed during log cleanup: {e}", include_traceback=True)
