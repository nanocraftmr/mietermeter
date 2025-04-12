# app_modules/utils.py
import uuid
import re
import json
import os
# Use relative imports for modules in the same package
from . import config
from . import logger

def get_mac_address():
    """Retrieves the MAC address of the machine."""
    try:
        mac = uuid.getnode()
        mac_address = ':'.join(('%012X' % mac)[i:i+2] for i in range(0, 12, 2))
        # Check for common invalid MAC addresses
        if mac_address in ["00:00:00:00:00:00", "FF:FF:FF:FF:FF:FF"]:
             raise ValueError(f"Invalid MAC address found ({mac_address})")
        logger.log_message(f"Successfully retrieved MAC address: {mac_address}")
        return mac_address
    except Exception as e:
        logger.log_error(f"Could not determine MAC address: {e}", include_traceback=False)
        return "unknown_mac"

def extract_ip_from_rtsp_url(rtsp_url):
    """Extracts the IP address from an RTSP URL (if present)."""
    if not rtsp_url:
        return None
    # Regex to find IP address after '@' and before potential ':' or '/'
    match = re.search(r"@([\d\.]+)(?::|/)", rtsp_url)
    return match.group(1) if match else None

def load_query_data():
    """Loads the query IDs from the JSON file specified in config."""
    # Ensure path is relative to the script execution directory
    file_path = os.path.abspath(config.QUERY_DATA_FILE)
    logger.log_message(f"Attempting to load query data from: {file_path}")
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
            if not isinstance(data, list):
                 logger.log_error(f"Query data in '{file_path}' is not a JSON list.", include_traceback=False)
                 return None
            logger.log_message(f"Successfully loaded {len(data)} items from query data file.")
            return data
    except FileNotFoundError:
        logger.log_error(f"Query data file not found: '{file_path}'. Create it first!", include_traceback=False)
        return None
    except json.JSONDecodeError as e:
        logger.log_error(f"Invalid JSON in '{file_path}': {e}. Please fix it!", include_traceback=False)
        return None
    except Exception as e:
        logger.log_error(f"Failed to load query data from '{file_path}': {e}", include_traceback=True)
        return None