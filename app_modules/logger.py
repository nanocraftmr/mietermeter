# app_modules/logger.py
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
    """Removes log entries older than LOG_RETENTION_DAYS."""
    log_message(f"Attempting log cleanup (removing entries older than {config.LOG_RETENTION_DAYS} days from {LOG_FILE_PATH})...")
    try:
        cutoff = datetime.datetime.now() - datetime.timedelta(days=config.LOG_RETENTION_DAYS)
        new_lines = []
        processed_lines = 0
        kept_lines = 0

        try:
            with open(LOG_FILE_PATH, "r") as f:
                for line in f:
                    processed_lines += 1
                    # Extract the date from the log entry using regex
                    match = re.match(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]", line)
                    if match:
                        try:
                            log_time = datetime.datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
                            if log_time >= cutoff:
                                new_lines.append(line)
                                kept_lines += 1
                            # Else: log entry is too old, discard it
                        except ValueError:
                             # Keep lines with unexpected date format within the brackets
                            new_lines.append(line)
                            kept_lines += 1
                    else:
                        # Keep lines that don't match the timestamp format (e.g., multi-line tracebacks)
                        new_lines.append(line)
                        kept_lines += 1
        except FileNotFoundError:
            log_message(f"Log file '{LOG_FILE_PATH}' not found for cleanup. Nothing to do.")
            return # No file to clean

        # Write the filtered lines back to the log file
        with open(LOG_FILE_PATH, "w") as f:
            f.writelines(new_lines)

        removed_lines = processed_lines - kept_lines
        if removed_lines > 0:
            log_message(f"Log cleanup complete. Processed: {processed_lines}, Kept: {kept_lines}, Removed: {removed_lines}.")
        else:
            log_message(f"Log cleanup complete. No old entries found to remove.")


    except Exception as e:
        # Use log_error without traceback for cleanup errors to avoid recursion if logging fails
        log_error(f"Failed during log cleanup: {e}", include_traceback=True)