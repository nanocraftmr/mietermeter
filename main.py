import os
from dotenv import load_dotenv
import json
from supabase import create_client, Client
import datetime
import traceback
import time
import cv2
import uuid
import re

load_dotenv()

HDGIP1 = os.getenv('HDGIP1')
HDGIP2 = os.getenv('HDGIP2')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
CAMERA = os.getenv('CAMERA')

from worker import hdg

def get_mac_address():
    mac = uuid.getnode()
    return ':'.join(('%012X' % mac)[i:i+2] for i in range(0, 12, 2))

# Set up logging
LOG_FILE = "hdg_script.log"
def log_message(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as log_file:
        log_file.write(f"[{timestamp}] {message}\n")
    print(message)
    
def log_error(message):
    log_message(f"ERROR: {message}")

def extract_ip_from_rtsp_url(rtsp_url):
    """Extrahiert die IP-Adresse aus einer RTSP-URL."""
    match = re.search(r"@([\d.]+)", rtsp_url)
    if match:
        return match.group(1)
    else:
        return None

def take_camera_screenshot(mac_address, supabase: Client):
    try:
        # Öffne den RTSP Stream
        cap = cv2.VideoCapture(CAMERA)
        
        if not cap.isOpened():
            log_error("Kann RTSP Stream nicht öffnen")
            return
            
        # Warte kurz, damit der Stream sich stabilisieren kann
        time.sleep(2)
        
        # Lese ein Frame
        ret, frame = cap.read()
        
        if ret:
            # Erstelle den Ordnernamen basierend auf der Raspberry Pi MAC-Adresse
            folder_name = mac_address # Entferne Doppelpunkte
            
            # Erstelle den Dateinamen
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{mac_address}_{timestamp}.jpg"
            
            # Definiere den vollständigen Pfad im Bucket
            bucket_path = f"{folder_name}/{filename}"
            
            # Konvertiere den Frame in Bytes
            ret, buffer = cv2.imencode('.jpg', frame)
            if not ret:
                log_error("Fehler beim Konvertieren des Frames in JPG")
                return
            image_bytes = buffer.tobytes()
            
            # Lade das Bild in den Supabase Bucket hoch
            try:
                response = supabase.storage.from_("hackbunker").upload(
                    bucket_path,
                    image_bytes,
                    file_options={"content-type": "image/jpeg"}
                )
                log_message(f"Bild hochgeladen nach: {bucket_path}")
            except Exception as upload_error:
                log_error(f"Fehler beim Hochladen in Supabase Bucket: {upload_error}")
        else:
            log_error("Konnte kein Frame vom Stream lesen")
            
        # Schließe den Stream
        cap.release()
        
    except Exception as e:
        log_error(f"Fehler beim Erstellen des Screenshots: {e}\n{traceback.format_exc()}")

def main():
    log_message("Script started")
    
    # Get MAC address of eth0
    try:
        mac_address = get_mac_address()

    except:
        mac_address = "unknown"
        log_error("Could not get MAC address from eth0")
    
    # Connect to Supabase
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
    # Erstelle einen Screenshot beim Start
    if CAMERA:
        take_camera_screenshot(mac_address, supabase)
    else:
        log_error("CAMERA Umgebungsvariable nicht gesetzt")

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
                        "ip": HDGIP1,
                        "mac": mac_address
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
                        "ip": HDGIP2,
                        "mac": mac_address
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
        
        time.sleep(120*60)  # 120 minutes in seconds


if __name__ == "__main__":
    main()