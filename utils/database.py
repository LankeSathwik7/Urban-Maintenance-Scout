import os
from supabase import create_client, Client
from dotenv import load_dotenv
import json
import traceback

load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_ANON_KEY")

# Validate environment variables
if not url or not key:
    raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY must be set in environment variables")

supabase: Client = create_client(url, key)

def store_scan_data(latitude, longitude, image_url, annotated_image_url, detection_results, llm_report_text, llm_report_structured):
    """
    Stores the scan data into the Supabase 'scans' table.

    Args:
        latitude (float): Latitude of the scan.
        longitude (float): Longitude of the scan.
        image_url (str): The PUBLIC URL of the image from Supabase Storage.
        annotated_image_url (str): The PUBLIC URL of the annotated image.
        detection_results (list): The JSON/list of detections from the CV model.
        llm_report_text (str): The text version of the report.
        llm_report_structured (dict): The structured JSON report.

    Returns:
        dict: The inserted data if successful, None otherwise.
    """
    try:
        print("DEBUG: Preparing data for database insertion...")
        
        # Ensure the structured report is properly formatted
        if isinstance(llm_report_structured, dict):
            # Validate the structure
            if 'summary' not in llm_report_structured:
                llm_report_structured['summary'] = "No summary provided"
            if 'issues' not in llm_report_structured:
                llm_report_structured['issues'] = []
            
            # Store as JSON (Supabase will handle this properly)
            structured_report = llm_report_structured
        else:
            # Try to parse if it's a string
            try:
                structured_report = json.loads(str(llm_report_structured))
            except:
                structured_report = {
                    "summary": "Could not parse structured report",
                    "issues": []
                }

        # Ensure detection_results is properly formatted
        if not isinstance(detection_results, list):
            detection_results = []
        
        # Validate detection results format
        validated_detections = []
        for detection in detection_results:
            try:
                if isinstance(detection, dict):
                    validated_detection = {
                        "label": str(detection.get("label", "unknown")),
                        "score": float(detection.get("score", 0.0)),
                        "box": detection.get("box", {})
                    }
                    validated_detections.append(validated_detection)
            except Exception as e:
                print(f"DEBUG: Error validating detection {detection}: {e}")
                continue
        
        data_to_insert = {
            "latitude": float(latitude),
            "longitude": float(longitude),
            "image_url": str(image_url) if image_url else None,
            "annotated_image_url": str(annotated_image_url) if annotated_image_url else None,
            "detection_results": validated_detections,
            "llm_report": str(llm_report_text) if llm_report_text else None,
            "llm_report_structured": structured_report
        }
        
        print(f"DEBUG: Inserting data: {json.dumps(data_to_insert, indent=2)}")
        
        response = supabase.table("scans").insert(data_to_insert).execute()
        
        if response.data:
            print("Data successfully stored in Supabase!")
            print(f"DEBUG: Inserted record with ID: {response.data[0].get('id', 'unknown')}")
            return response.data[0]
        else:
            print("WARNING: No data returned from insert operation")
            return None
            
    except Exception as e:
        print(f"Error inserting data: {e}")
        print(f"DEBUG: Full traceback: {traceback.format_exc()}")
        return None

def get_all_scans():
    """
    Retrieves all scans from the database, ordered by creation date (newest first).
    
    Returns:
        list: List of scan records, or empty list if error occurs.
    """
    try:
        response = supabase.table('scans').select("*").order('created_at', desc=True).execute()
        scans = response.data or []
        
        # Ensure all scans have integer IDs
        for scan in scans:
            if 'id' in scan:
                scan['id'] = int(scan['id'])
                
        print(f"DEBUG: Retrieved {len(scans)} scans from database")
        return scans
        
    except Exception as e:
        print(f"Error retrieving scans: {e}")
        return []

def get_scan_by_id(scan_id):
    """
    Retrieves a specific scan by ID.
    
    Args:
        scan_id (int): The ID of the scan to retrieve.
        
    Returns:
        dict: The scan record if found, None otherwise.
    """
    try:
        response = supabase.table('scans').select("*").eq('id', scan_id).execute()
        
        if response.data and len(response.data) > 0:
            scan = response.data[0]
            scan['id'] = int(scan['id'])
            return scan
        else:
            print(f"No scan found with ID: {scan_id}")
            return None
            
    except Exception as e:
        print(f"Error retrieving scan {scan_id}: {e}")
        return None

def update_scan_report(scan_id, llm_report_text, llm_report_structured):
    """
    Updates the LLM report for an existing scan.
    
    Args:
        scan_id (int): The ID of the scan to update.
        llm_report_text (str): The text version of the report.
        llm_report_structured (dict): The structured JSON report.
        
    Returns:
        bool: True if successful, False otherwise.
    """
    try:
        # Ensure the structured report is properly formatted
        if isinstance(llm_report_structured, dict):
            structured_report = llm_report_structured
        else:
            try:
                structured_report = json.loads(str(llm_report_structured))
            except:
                structured_report = {
                    "summary": "Could not parse structured report",
                    "issues": []
                }
        
        update_data = {
            "llm_report": str(llm_report_text) if llm_report_text else None,
            "llm_report_structured": structured_report
        }
        
        response = supabase.table("scans").update(update_data).eq('id', scan_id).execute()
        
        if response.data:
            print(f"Successfully updated scan {scan_id}")
            return True
        else:
            print(f"Failed to update scan {scan_id}")
            return False
            
    except Exception as e:
        print(f"Error updating scan {scan_id}: {e}")
        return False

def delete_scan(scan_id):
    """
    Deletes a scan from the database.
    
    Args:
        scan_id (int): The ID of the scan to delete.
        
    Returns:
        bool: True if successful, False otherwise.
    """
    try:
        response = supabase.table("scans").delete().eq('id', scan_id).execute()
        
        if response.data:
            print(f"Successfully deleted scan {scan_id}")
            return True
        else:
            print(f"Failed to delete scan {scan_id} (may not exist)")
            return False
            
    except Exception as e:
        print(f"Error deleting scan {scan_id}: {e}")
        return False

# Test the database connection
if __name__ == "__main__":
    print("Testing database connection...")
    
    # Test retrieving scans
    scans = get_all_scans()
    print(f"Found {len(scans)} existing scans")
    
    # Test inserting a dummy scan
    test_data = {
        "latitude": 40.7128,
        "longitude": -74.0060,
        "image_url": "https://example.com/test.jpg",
        "annotated_image_url": "https://example.com/test_annotated.jpg",
        "detection_results": [
            {
                "label": "car",
                "score": 0.95,
                "box": {"xmin": 100, "ymin": 200, "xmax": 300, "ymax": 400}
            }
        ],
        "llm_report_text": "Test report",
        "llm_report_structured": {
            "summary": "Test summary",
            "issues": []
        }
    }
    
    print("Inserting test data...")
    result = store_scan_data(**test_data)
    
    if result:
        print("Test insertion successful!")
        test_id = result['id']
        
        # Test retrieval
        retrieved = get_scan_by_id(test_id)
        if retrieved:
            print("Test retrieval successful!")
            
            # Clean up - delete test data
            if delete_scan(test_id):
                print("Test cleanup successful!")
            else:
                print("Test cleanup failed!")
        else:
            print("Test retrieval failed!")
    else:
        print("Test insertion failed!")