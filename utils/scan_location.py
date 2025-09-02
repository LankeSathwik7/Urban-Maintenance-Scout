# scan_location.py
from utils.fetcher import fetch_street_view_image
from utils.cv_analysis import analyze_image, draw_bounding_boxes
from utils.database import store_scan_data
from chains.analyst_chain import generate_report

def main(lat, lon):
    print(f"Scanning location: {lat}, {lon}")
    # 1. Fetch Image
    image_path = fetch_street_view_image(lat, lon, "latest_scan.jpg")
    if not image_path:
        return

    # 2. Analyze Image
    detections = analyze_image(image_path)
    print("Detections found:", len(detections))
    draw_bounding_boxes(image_path, detections, "latest_scan_annotated.jpg")

    # 3. NEW: Generate LLM Report
    print("Generating LLM report...")
    llm_report = generate_report(detections)
    print("Report generated!")

    # 4. Store in Database
    store_scan_data(lat, lon, image_path, detections, llm_report)
    print("Scan complete and data stored!")

    # Print the report to the console
    print("\n" + "="*50)
    print("LLM REPORT:")
    print(llm_report)

if __name__ == "__main__":
    # Example coordinates (San Francisco)
    latitude = 37.773972
    longitude = -122.431297
    main(latitude, longitude)