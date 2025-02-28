import json
import csv
from datetime import datetime

def json_to_csv(json_file, csv_file):
    """
    Converts a JSON file to a CSV file, generating a sequential ID.

    Args:
        json_file (str): The path to the input JSON file.
        csv_file (str): The path to the output CSV file.
    """

    try:
        with open(json_file, 'r', encoding='utf-8') as f_json:
            try:
                data = json.load(f_json)
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON: {e}")
                return  # Exit if JSON is invalid

    except FileNotFoundError:
        print(f"Error: File not found: {json_file}")
        return  # Exit if file doesn't exist

    csv_header = ["id", "created_at", "hdg_id", "enum", "data_type", "desc1", "desc2", "formatter"]

    try:
        with open(csv_file, 'w', newline='', encoding='utf-8') as f_csv:
            writer = csv.writer(f_csv)
            writer.writerow(csv_header)

            row_id = 1  # Initialize the sequential row ID
            for item in data:
                # Assign the 'id' from JSON to 'hdg_id'
                hdg_id = item.get("id", "")

                row = [
                    row_id,                   # CSV 'id' is now sequential
                    datetime.utcnow().isoformat() + 'Z',
                    hdg_id,                    # CSV 'hdg_id' is the JSON 'id'
                    item.get("enum", ""),
                    item.get("data_type", ""),
                    item.get("desc1", ""),
                    item.get("desc2", ""),
                    item.get("formatter", "")
                ]
                writer.writerow(row)
                row_id += 1  # Increment the row ID for the next row

    except Exception as e:
        print(f"An error occurred while writing the CSV: {e}")  # Catch other potential errors

    print(f"Successfully converted '{json_file}' to '{csv_file}'")

# Example usage:
json_file_path = "data.json"
csv_file_path = "output.csv"
json_to_csv(json_file_path, csv_file_path)