import os
from supabase import create_client, Client
from dotenv import load_dotenv
import json

load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_ANON_KEY")
supabase: Client = create_client(url, key)

def store_scan_data(latitude, longitude, image_path, detection_results, llm_report=""):
    """
    Stores the scan data into the Supabase 'scans' table.

    Args:
        latitude (float): Latitude of the scan.
        longitude (float): Longitude of the scan.
        image_path (str): Local path to the image (we'll handle URL later).
        detection_results (list): The JSON/list of detections from the CV model.
        llm_report (str): The generated report from the LLM. Optional.

    Returns:
        dict: The data that was inserted, or an error.
    """
    # For now, we'll just store the local path. In a real app, you'd upload the image to Supabase Storage.
    # This is a placeholder.
    image_url_placeholder = f"Local: {image_path}"

    data_to_insert = {
        "latitude": latitude,
        "longitude": longitude,
        "image_url": image_url_placeholder,
        "detection_results": detection_results,
        "llm_report": llm_report
    }

    try:
        response = supabase.table("scans").insert(data_to_insert).execute()
        print("Data successfully stored in Supabase!")
        return response.data
    except Exception as e:
        print(f"Error inserting data: {e}")
        return None