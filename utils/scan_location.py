import os
import sys

# Add the current directory to Python path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from utils.fetcher import fetch_street_view_image, validate_coordinates
from utils.cv_analysis import analyze_image_combined, draw_bounding_boxes
from utils.database import store_scan_data
from utils.storage import upload_image_to_supabase
from chains.analyst_chain import generate_report
import json
import traceback

def main(lat, lon):
    """
    Main scanning function that orchestrates the entire process.
    
    Args:
        lat (float): Latitude of the location to scan
        lon (float): Longitude of the location to scan
        
    Returns:
        bool: True if scan completed successfully, False otherwise
    """
    print(f"🚀 Starting scan for location: {lat}, {lon}")
    
    try:
        # Validate coordinates first
        if not validate_coordinates(lat, lon):
            print("❌ Invalid coordinates provided")
            return False
        
        # 1. Fetch Street View Image
        print("📷 Step 1: Fetching street view image...")
        image_path = fetch_street_view_image(lat, lon, "latest_scan.jpg")
        if not image_path:
            print("❌ Failed to fetch street view image")
            return False
        print("✅ Street view image fetched successfully")
        
        # 2. Upload original image to Supabase Storage and get URL
        print("☁️ Step 2: Uploading original image to cloud storage...")
        public_image_url = upload_image_to_supabase(image_path)
        if not public_image_url:
            print("❌ Failed to upload original image to storage")
            return False
        print(f"✅ Original image uploaded: {public_image_url}")
        
        # 3. Analyze Image with Computer Vision
        print("🔍 Step 3: Analyzing image with computer vision...")
        detections = analyze_image_combined(image_path, confidence_threshold=0.3)
        print(f"✅ Computer vision analysis complete. Found {len(detections)} objects")
        
        # Print detected objects for debugging
        if detections:
            print("Detected objects:")
            for i, det in enumerate(detections):
                print(f"  {i+1}. {det['label']} (confidence: {det['score']:.2f})")
        else:
            print("  No objects detected")
        
        # 4. Create annotated image
        print("🎨 Step 4: Creating annotated image...")
        annotated_image_path = "latest_scan_annotated.jpg"
        annotation_success = draw_bounding_boxes(image_path, detections, annotated_image_path)
        
        if annotation_success:
            print("✅ Annotated image created successfully")
        else:
            print("⚠️ Warning: Failed to create annotated image, using original")
            annotated_image_path = image_path
        
        # 5. Upload annotated image
        print("☁️ Step 5: Uploading annotated image to cloud storage...")
        if annotation_success:
            public_annotated_image_url = upload_image_to_supabase(annotated_image_path)
        else:
            public_annotated_image_url = public_image_url  # Use original if annotation failed
        
        if public_annotated_image_url:
            print(f"✅ Annotated image uploaded: {public_annotated_image_url}")
        else:
            print("⚠️ Warning: Failed to upload annotated image")
            public_annotated_image_url = public_image_url
        
        # 6. Generate AI Analysis Report
        print("🤖 Step 6: Generating AI analysis report...")
        llm_report = generate_report(detections)
        
        if llm_report and isinstance(llm_report, dict):
            print("✅ AI analysis report generated successfully")
            
            # Print summary for debugging
            summary = llm_report.get('summary', 'No summary available')
            issues = llm_report.get('issues', [])
            print(f"Summary: {summary}")
            print(f"Issues found: {len(issues)}")
            
            for i, issue in enumerate(issues):
                issue_type = issue.get('type', 'Unknown')
                severity = issue.get('severity', 'Unknown')
                description = issue.get('description', 'No description')
                print(f"  {i+1}. {issue_type} ({severity}): {description}")
        else:
            print("⚠️ Warning: AI analysis failed, using fallback report")
            llm_report = {
                "summary": "AI analysis encountered an error, but object detection was successful.",
                "issues": []
            }
        
        # 7. Prepare data for database storage
        print("💾 Step 7: Preparing data for database storage...")
        llm_report_text = json.dumps(llm_report, indent=2)
        
        # 8. Store everything in Database
        print("💾 Step 8: Storing scan data in database...")
        
        database_result = store_scan_data(
            latitude=lat,
            longitude=lon,
            image_url=public_image_url,
            annotated_image_url=public_annotated_image_url,
            detection_results=detections,
            llm_report_text=llm_report_text,
            llm_report_structured=llm_report
        )
        
        if database_result:
            scan_id = database_result.get('id', 'unknown')
            print(f"✅ Scan data stored successfully with ID: {scan_id}")
        else:
            print("❌ Failed to store scan data in database")
            return False
        
        # 9. Cleanup temporary files
        print("🧹 Step 9: Cleaning up temporary files...")
        try:
            if os.path.exists(image_path):
                os.remove(image_path)
                print(f"Removed {image_path}")
            
            if annotation_success and os.path.exists(annotated_image_path):
                os.remove(annotated_image_path)
                print(f"Removed {annotated_image_path}")
                
        except Exception as cleanup_error:
            print(f"⚠️ Warning: Cleanup failed: {cleanup_error}")
        
        print("🎉 Scan completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Critical error during scan: {e}")
        print(f"DEBUG: Full traceback: {traceback.format_exc()}")
        
        # Cleanup on error
        try:
            temp_files = ["latest_scan.jpg", "latest_scan_annotated.jpg"]
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    print(f"Cleaned up {temp_file}")
        except:
            pass
            
        return False

def scan_with_retry(lat, lon, max_retries=2):
    """
    Attempts to scan a location with retry logic.
    
    Args:
        lat (float): Latitude of the location to scan
        lon (float): Longitude of the location to scan
        max_retries (int): Maximum number of retry attempts
        
    Returns:
        bool: True if scan completed successfully, False otherwise
    """
    for attempt in range(max_retries + 1):
        if attempt > 0:
            print(f"🔄 Retry attempt {attempt}/{max_retries}")
        
        success = main(lat, lon)
        if success:
            return True
        
        if attempt < max_retries:
            print("⏱️ Waiting before retry...")
            import time
            time.sleep(2)  # Wait 2 seconds before retry
    
    print(f"❌ All {max_retries + 1} attempts failed")
    return False

def scan_multiple_locations(locations):
    """
    Scans multiple locations in batch.
    
    Args:
        locations (list): List of tuples (lat, lon, name)
        
    Returns:
        dict: Results summary
    """
    results = {
        'successful': [],
        'failed': [],
        'total': len(locations)
    }
    
    print(f"📍 Starting batch scan of {len(locations)} locations...")
    
    for i, (lat, lon, name) in enumerate(locations):
        print(f"\n--- Scanning location {i+1}/{len(locations)}: {name} ---")
        
        success = main(lat, lon)
        if success:
            results['successful'].append((lat, lon, name))
            print(f"✅ {name} completed successfully")
        else:
            results['failed'].append((lat, lon, name))
            print(f"❌ {name} failed")
    
    # Print summary
    print(f"\n📊 Batch scan summary:")
    print(f"   Total locations: {results['total']}")
    print(f"   Successful: {len(results['successful'])}")
    print(f"   Failed: {len(results['failed'])}")
    
    if results['failed']:
        print("❌ Failed locations:")
        for lat, lon, name in results['failed']:
            print(f"   - {name} ({lat}, {lon})")
    
    return results

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Urban Maintenance Scout - Location Scanner')
    parser.add_argument('--lat', type=float, required=True, help='Latitude of the location to scan')
    parser.add_argument('--lon', type=float, required=True, help='Longitude of the location to scan')
    parser.add_argument('--retry', type=int, default=2, help='Number of retry attempts (default: 2)')
    parser.add_argument('--batch', type=str, help='Path to CSV file with locations (columns: lat,lon,name)')
    
    args = parser.parse_args()
    
    if args.batch:
        # Batch mode
        try:
            import pandas as pd
            df = pd.read_csv(args.batch)
            locations = [(row['lat'], row['lon'], row.get('name', f'Location_{i}')) 
                        for i, row in df.iterrows()]
            scan_multiple_locations(locations)
        except Exception as e:
            print(f"Error processing batch file: {e}")
    else:
        # Single location mode
        success = scan_with_retry(args.lat, args.lon, args.retry)
        exit(0 if success else 1)