# app_modules/supabase_handler.py
from supabase import create_client, Client
from postgrest.exceptions import APIError # Import specific Supabase error type
# Use relative imports for modules in the same package
from . import config
from . import logger

_supabase_client: Client | None = None

def init_supabase_client() -> Client | None:
    """Initializes and returns the Supabase client."""
    global _supabase_client
    if _supabase_client:
        logger.log_message("Supabase client already initialized.")
        return _supabase_client

    if not config.SUPABASE_URL or not config.SUPABASE_KEY:
        logger.log_error("Supabase URL or Key not configured. Cannot initialize client.", include_traceback=False)
        return None

    try:
        logger.log_message(f"Attempting to initialize Supabase client for URL: {config.SUPABASE_URL[:20]}...") # Log partial URL
        _supabase_client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
        # Optional: Add a simple query to test connection?
        # _supabase_client.table(config.SUPABASE_TABLE).select('id', head=True).execute()
        logger.log_message("Supabase client initialized successfully.")
        return _supabase_client
    except Exception as e:
        logger.log_error(f"Failed to initialize Supabase client: {e}", include_traceback=True)
        return None

def get_supabase_client() -> Client | None:
    """Returns the initialized Supabase client, initializing if needed."""
    if not _supabase_client:
        logger.log_message("Supabase client not initialized. Attempting initialization now.")
        return init_supabase_client()
    return _supabase_client

def save_hdg_data(data_to_insert: dict):
    """Saves a single HDG data record to the Supabase table."""
    supabase = get_supabase_client()
    if not supabase:
        logger.log_error("Supabase client not available. Cannot save data.", include_traceback=False)
        return False # Indicate failure

    if not data_to_insert or not isinstance(data_to_insert, dict):
         logger.log_error(f"Received invalid data for Supabase insertion: {data_to_insert}", include_traceback=False)
         return False

    anlage = data_to_insert.get("anlage", "N/A")
    key = data_to_insert.get("key", "N/A")
    value = data_to_insert.get("value", "N/A") # Get value for logging

    logger.log_message(f"Attempting to save to DB: Anlage={anlage}, Key={key}, Value={value}")
    try:
        # Ensure value is treated correctly, convert if necessary
        # Example: Ensure value is string, handle potential errors during conversion
        # try:
        #     data_to_insert['value'] = str(data_to_insert.get('value'))
        # except Exception as conversion_error:
        #     logger.log_error(f"Error converting value to string for DB save (Anlage={anlage}, Key={key}): {conversion_error}", include_traceback=False)
        #     return False

        # Execute the insert operation
        response = supabase.table(config.SUPABASE_TABLE).insert(data_to_insert).execute()

        # Basic check on response structure (Supabase API v2+)
        if hasattr(response, 'data') and response.data:
            # Optionally log more details from response.data if needed
            logger.log_message(f"Successfully saved to DB: Anlage={anlage}, Key={key}. Records inserted: {len(response.data)}")
            return True # Indicate success
        else:
            # Log unexpected response structure if data is empty or not present
            logger.log_error(f"Supabase insert for Anlage={anlage}, Key={key} completed but returned unexpected response: {response}", include_traceback=False)
            return False

    except APIError as api_err:
         logger.log_error(f"Supabase API error during insert (Anlage={anlage}, Key={key}): {api_err.message} (Code: {api_err.code}, Details: {api_err.details})", include_traceback=False)
         return False
    except Exception as e:
        logger.log_error(f"Unexpected error during Supabase DB insert (Anlage: {anlage}, Key: {key}): {e}", include_traceback=True)
        return False # Indicate failure

def upload_image_to_storage(image_bytes: bytes, bucket_path: str):
    """Uploads image bytes to Supabase storage."""
    supabase = get_supabase_client()
    if not supabase:
        logger.log_error("Supabase client not available. Cannot upload image.", include_traceback=False)
        return False

    if not image_bytes or not isinstance(image_bytes, bytes):
        logger.log_error(f"Invalid image_bytes provided for upload to {bucket_path}.", include_traceback=False)
        return False

    logger.log_message(f"Attempting to upload image to Supabase Storage: {config.SUPABASE_BUCKET}/{bucket_path} ({len(image_bytes)} bytes)...")
    try:
        # Use upsert=False to avoid overwriting if file exists (optional)
        response = supabase.storage.from_(config.SUPABASE_BUCKET).upload(
            bucket_path,
            image_bytes,
            file_options={"content-type": "image/jpeg", "cache-control": "3600", "upsert": "false"}
        )
        # Supabase storage upload via Python client typically raises exception on failure.
        # If it completes without exception, assume success.
        logger.log_message(f"Image uploaded successfully to Supabase Storage: {config.SUPABASE_BUCKET}/{bucket_path}")
        # You might want to log the response object if needed for debugging: logger.log_message(f"Supabase upload response: {response}")
        return True
    except APIError as api_err:
         # Handle specific storage errors if possible based on api_err details
         if 'Duplicate' in str(api_err.message): # Example check
              logger.log_error(f"Supabase Storage: File already exists at path '{bucket_path}' (upsert=false). Details: {api_err}", include_traceback=False)
         else:
              logger.log_error(f"Supabase Storage API error uploading image to '{bucket_path}': {api_err}", include_traceback=False)
         return False
    except Exception as e:
        # Catch other potential errors (network issues, etc.)
        logger.log_error(f"Unexpected error uploading image to Supabase Storage path '{bucket_path}': {e}", include_traceback=True)
        return False