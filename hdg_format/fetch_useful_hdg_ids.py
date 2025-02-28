import os
from dotenv import load_dotenv
import json
from supabase import create_client, Client
import datetime
import traceback

def main():
    # Load our environment vars
    load_dotenv()
    
    # Grab our Supabase credentials
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY')
    
    # Make sure we have what we need to connect
    if not all([SUPABASE_URL, SUPABASE_KEY]):
        print("Error: Missing Supabase credentials in .env file. Need both URL and KEY.")
        return
    
    try:
        # Connect to Supabase
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Get all the meter readings
        response = supabase.table("hdg_meter").select("*").order('created_at').execute()
        
        # Extract the actual data
        all_data = response.data
        
        if not all_data:
            print("No records found in the hdg_meter table.")
            return
        
        print(f"Looking through hdg_meter records...")
        
        # Group readings by their key
        grouped_by_key = {}
        for record in all_data:
            key = record['key']
            if key not in grouped_by_key:
                grouped_by_key[key] = []
            grouped_by_key[key].append(record)
        
        # Find keys where the values actually change over time
        changing_keys = []
        
        for key, records in sorted(grouped_by_key.items()):
            # Skip null or zero readings
            valid_records = [r for r in records if r.get('value') is not None and r.get('value') != "0.0"]
            
            if not valid_records:
                continue
                
            # See if this key has multiple different values
            distinct_values = set(r['value'] for r in valid_records)
            
            # If more than one value, it's changing!
            if len(distinct_values) > 1:
                changing_keys.append(key)
                print(f"Found changing key: {key}")
        
        # Format for our data.json
        data_json = [{"id": key} for key in changing_keys]
        
        # Save the results in the same folder as this script
        with open("output_hdg_ids.json", "w") as json_file:
            json.dump(data_json, json_file, indent=2)
        
        # Backup existing data.json if we have one
        try:
            if os.path.exists("hdg_format/data.json"):
                with open("hdg_format/data.json", "r") as f:
                    existing_data = json.load(f)
                # Add timestamp to backup name
                backup_filename = f"hdg_format/data.json.backup.{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
                with open(backup_filename, "w") as f:
                    json.dump(existing_data, f, indent=2)
                print(f"Backed up old data.json to {backup_filename}")
        except Exception as e:
            print(f"Warning: Couldn't backup data.json: {e}")
        
        print(f"\nDone!")
        print(f"- Found {len(changing_keys)} keys that change over time")
        print(f"- Saved results to output.json in current folder")
        print(f"- To use with main.py, copy output.json to hdg_format/data.json")
            
    except Exception as e:
        print(f"Error: {e}")
        print(traceback.format_exc())

if __name__ == "__main__":
    main()