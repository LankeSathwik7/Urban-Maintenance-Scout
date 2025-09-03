import streamlit as st
import pandas as pd
from supabase import create_client
import os
from dotenv import load_dotenv
import requests
from PIL import Image
import io
import json
import folium
from streamlit_folium import folium_static, st_folium
import time
import traceback

# Import the main scanning function
try:
    from utils.scan_location import main as scan_main
    from utils.database import get_all_scans
except ImportError as e:
    st.error(f"Import error: {e}")
    st.stop()

# --- Page configuration ---
st.set_page_config(
    page_title="Urban Maintenance Scout", 
    layout="wide",
    page_icon="🏗️",
    initial_sidebar_state="expanded"
)

st.title("🏗️ Urban Maintenance Scout Dashboard")
st.markdown("Proactively identifying public infrastructure issues with AI.")

# --- Environment setup ---
@st.cache_resource
def init_connection():
    """Initialize Supabase connection"""
    try:
        load_dotenv()
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_ANON_KEY")
        
        if not url or not key:
            st.error("Missing Supabase configuration. Please check your environment variables.")
            st.stop()
            
        return create_client(url, key)
    except Exception as e:
        st.error(f"Failed to initialize Supabase connection: {e}")
        st.stop()

supabase = init_connection()

# --- Data fetching functions ---
@st.cache_data(ttl=30)  # Cache for 30 seconds
def fetch_all_scans():
    """Fetch all scans from database with error handling"""
    try:
        scans = get_all_scans()
        # Ensure all scans have proper data types
        for scan in scans:
            if 'id' in scan:
                scan['id'] = int(scan['id'])
            if 'latitude' in scan:
                scan['latitude'] = float(scan['latitude'])
            if 'longitude' in scan:
                scan['longitude'] = float(scan['longitude'])
        return scans
    except Exception as e:
        st.error(f"Error fetching scans: {e}")
        return []

def parse_llm_report(report_data):
    """Parse LLM report with robust error handling"""
    if not report_data:
        return {"summary": "No report available", "issues": []}
    
    # If it's already a dict, return it
    if isinstance(report_data, dict):
        return report_data
    
    # If it's a string, try to parse it
    if isinstance(report_data, str):
        try:
            return json.loads(report_data)
        except json.JSONDecodeError:
            # Try to extract JSON from string using regex
            import re
            json_match = re.search(r'\{.*\}', report_data, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass
            
            # Fallback - treat as plain text summary
            return {
                "summary": report_data[:200] + "..." if len(report_data) > 200 else report_data,
                "issues": []
            }
    
    # Ultimate fallback
    return {"summary": "Could not parse report data", "issues": []}

# --- Session state initialization ---
if 'scans' not in st.session_state:
    st.session_state.scans = fetch_all_scans()

if 'selected_lat' not in st.session_state:
    st.session_state.selected_lat = 40.7128  # Default to NYC
if 'selected_lon' not in st.session_state:
    st.session_state.selected_lon = -74.0060
if 'map_center' not in st.session_state:
    st.session_state.map_center = [40.7128, -74.0060]
if 'map_zoom' not in st.session_state:
    st.session_state.map_zoom = 12

# Set the latest scan as selected default
if 'selected_scan_id' not in st.session_state:
    if st.session_state.scans:
        st.session_state.selected_scan_id = st.session_state.scans[0]['id']
    else:
        st.session_state.selected_scan_id = None

# --- Sidebar ---
with st.sidebar:
    st.header("🎛️ Control Panel")
    
    # Refresh button
    if st.button("🔄 Refresh Data", help="Refresh scan data from database"):
        fetch_all_scans.clear()  # Clear cache
        st.session_state.scans = fetch_all_scans()
        st.rerun()
    
    # Stats
    st.subheader("📊 Statistics")
    total_scans = len(st.session_state.scans)
    st.metric("Total Scans", total_scans)
    
    if st.session_state.scans:
        # Calculate issues statistics
        total_issues = 0
        high_severity_issues = 0
        
        for scan in st.session_state.scans:
            report = parse_llm_report(scan.get('llm_report_structured'))
            issues = report.get('issues', [])
            total_issues += len(issues)
            high_severity_issues += sum(1 for issue in issues if issue.get('severity') == 'High')
        
        st.metric("Total Issues Found", total_issues)
        st.metric("High Severity Issues", high_severity_issues)
    
    # Export functionality
    st.subheader("💾 Export Data")
    if st.session_state.scans:
        # Prepare data for export
        export_data = []
        for scan in st.session_state.scans:
            report = parse_llm_report(scan.get('llm_report_structured'))
            export_data.append({
                'scan_id': scan['id'],
                'latitude': scan['latitude'],
                'longitude': scan['longitude'],
                'created_at': scan.get('created_at', ''),
                'summary': report.get('summary', ''),
                'issues_count': len(report.get('issues', [])),
                'high_severity_count': sum(1 for issue in report.get('issues', []) if issue.get('severity') == 'High')
            })
        
        df_export = pd.DataFrame(export_data)
        csv = df_export.to_csv(index=False)
        
        st.download_button(
            label="📥 Download as CSV",
            data=csv,
            file_name=f"urban_maintenance_scans_{time.strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

# --- Main Layout ---
col1, col2 = st.columns([2, 1])

with col1:
    st.header("🗺️ Interactive Map")
    
    # Create map
    m = folium.Map(location=st.session_state.map_center, zoom_start=st.session_state.map_zoom)
    
    # Add markers for existing scans
    if st.session_state.scans:
        for scan in st.session_state.scans:
            try:
                # Determine marker color based on issues
                report = parse_llm_report(scan.get('llm_report_structured'))
                issues = report.get('issues', [])
                
                if any(issue.get('severity') == 'High' for issue in issues):
                    color = 'red'
                    icon = 'exclamation-sign'
                elif any(issue.get('severity') == 'Medium' for issue in issues):
                    color = 'orange'
                    icon = 'warning-sign'
                elif issues:
                    color = 'yellow'
                    icon = 'info-sign'
                else:
                    color = 'green'
                    icon = 'ok-sign'
                
                popup_text = f"""
                <b>Scan {scan['id']}</b><br/>
                Issues: {len(issues)}<br/>
                {report.get('summary', '')[:100]}...
                """
                
                folium.Marker(
                    [scan['latitude'], scan['longitude']],
                    popup=folium.Popup(popup_text, max_width=300),
                    icon=folium.Icon(color=color, icon=icon),
                    tooltip=f"Scan {scan['id']} - {len(issues)} issues"
                ).add_to(m)
            except Exception as e:
                st.warning(f"Error adding marker for scan {scan.get('id', 'unknown')}: {e}")
    
    # Add click functionality
    m.add_child(folium.LatLngPopup())
    
    # Display map
    map_data = st_folium(m, width=700, height=500, key="main_map")
    
    # Handle map interactions
    if map_data and map_data.get("last_clicked"):
        st.session_state.selected_lat = map_data["last_clicked"]["lat"]
        st.session_state.selected_lon = map_data["last_clicked"]["lng"]
        st.session_state.map_center = [st.session_state.selected_lat, st.session_state.selected_lon]
    
    if map_data and map_data.get("center"):
        st.session_state.map_center = [map_data["center"]["lat"], map_data["center"]["lng"]]
        st.session_state.map_zoom = map_data["zoom"]

with col2:
    st.header("📍 Scan Location")
    
    # Display current selection
    st.write(f"**Selected Coordinates:**")
    st.write(f"Latitude: `{st.session_state.selected_lat:.6f}`")
    st.write(f"Longitude: `{st.session_state.selected_lon:.6f}`")
    
    # Quick location selection
    st.subheader("🏙️ Quick Locations")
    quick_locations = {
        "New York City": (40.7128, -74.0060),
        "San Francisco": (37.7749, -122.4194),
        "London": (51.5074, -0.1278),
        "Paris": (48.8566, 2.3522),
        "Tokyo": (35.6762, 139.6503)
    }
    
    selected_city = st.selectbox("Choose a city:", ["Custom"] + list(quick_locations.keys()))
    if selected_city != "Custom":
        lat, lon = quick_locations[selected_city]
        st.session_state.selected_lat = lat
        st.session_state.selected_lon = lon
        st.session_state.map_center = [lat, lon]
    
    # Manual coordinate input
    st.subheader("📝 Manual Input")
    manual_lat = st.number_input(
        "Latitude", 
        value=st.session_state.selected_lat, 
        format="%.6f", 
        step=0.000001,
        key="manual_lat"
    )
    manual_lon = st.number_input(
        "Longitude", 
        value=st.session_state.selected_lon, 
        format="%.6f", 
        step=0.000001,
        key="manual_lon"
    )
    
    if manual_lat != st.session_state.selected_lat or manual_lon != st.session_state.selected_lon:
        st.session_state.selected_lat = manual_lat
        st.session_state.selected_lon = manual_lon
        st.session_state.map_center = [manual_lat, manual_lon]
    
    # Scan button with enhanced feedback
    st.subheader("🚀 Start Scan")
    
    if st.button("🔍 Scan Location", type="primary", width='stretch'):
        scan_container = st.container()
        
        with scan_container:
            # Progress tracking
            progress_bar = st.progress(0, text="Initializing scan...")
            status_text = st.empty()
            
            try:
                status_text.text("📷 Fetching street view image...")
                progress_bar.progress(20, text="Fetching street view image...")
                time.sleep(0.5)  # Brief pause for UI feedback
                
                status_text.text("🔍 Analyzing with computer vision...")
                progress_bar.progress(40, text="Analyzing with computer vision...")
                time.sleep(0.5)
                
                status_text.text("🤖 Generating AI report...")
                progress_bar.progress(60, text="Generating AI report...")
                time.sleep(0.5)
                
                status_text.text("☁️ Uploading to cloud storage...")
                progress_bar.progress(80, text="Uploading to cloud storage...")
                
                # Execute the actual scan
                success = scan_main(st.session_state.selected_lat, st.session_state.selected_lon)
                
                if success:
                    progress_bar.progress(100, text="Scan completed successfully!")
                    status_text.text("✅ Scan completed successfully!")
                    
                    # Refresh data and update UI
                    fetch_all_scans.clear()
                    st.session_state.scans = fetch_all_scans()
                    
                    if st.session_state.scans:
                        st.session_state.selected_scan_id = st.session_state.scans[0]['id']
                    
                    st.success("🎉 Scan completed! Check the results below.")
                    time.sleep(1)
                    st.rerun()
                else:
                    progress_bar.progress(0, text="Scan failed")
                    status_text.text("❌ Scan failed!")
                    st.error("Scan failed. Please check the console for details or try again.")
                    
            except Exception as e:
                progress_bar.progress(0, text="Error occurred")
                status_text.text(f"❌ Error: {str(e)}")
                st.error(f"Scan failed with error: {str(e)}")
                st.error("Full traceback:")
                st.code(traceback.format_exc())

# --- Scan Results Section ---
st.header("📋 Scan Results")

if not st.session_state.scans:
    st.info("No scans found in the database. Run a scan first!")
else:
    # Scan selector
    scan_options = {}
    for scan in st.session_state.scans:
        created_at = scan.get('created_at', 'Unknown time')
        if 'T' in str(created_at):
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                formatted_time = dt.strftime('%Y-%m-%d %H:%M')
            except:
                formatted_time = str(created_at)[:19]  # Take first 19 chars
        else:
            formatted_time = str(created_at)
        
        scan_options[f"Scan {scan['id']} - {formatted_time}"] = scan['id']
    
    # Get default selection
    if st.session_state.selected_scan_id in [scan['id'] for scan in st.session_state.scans]:
        default_key = next((key for key, val in scan_options.items() 
                           if val == st.session_state.selected_scan_id), 
                          list(scan_options.keys())[0])
        default_index = list(scan_options.keys()).index(default_key)
    else:
        default_index = 0
    
    selected_scan_key = st.selectbox(
        "Select a scan to view details:",
        list(scan_options.keys()),
        index=default_index,
        key="scan_selector"
    )
    
    selected_scan_id = scan_options[selected_scan_key]
    selected_scan = next((scan for scan in st.session_state.scans if scan['id'] == selected_scan_id), None)
    
    if selected_scan:
        st.session_state.selected_scan_id = selected_scan_id
        
        # Display scan details
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🖼️ Street View Image")
            try:
                image_url = selected_scan.get('image_url')
                if image_url:
                    # Load image with error handling
                    response = requests.get(image_url, timeout=10)
                    if response.status_code == 200:
                        image = Image.open(io.BytesIO(response.content))
                        st.image(image, caption="Original Street View", width='stretch')
                    else:
                        st.error(f"Failed to load image (Status: {response.status_code})")
                        st.write(f"Image URL: {image_url}")
                else:
                    st.warning("No image URL available")
            except Exception as e:
                st.error(f"Could not load image: {e}")
        
        with col2:
            st.subheader("🎯 Annotated Image")
            try:
                annotated_url = selected_scan.get('annotated_image_url')
                if annotated_url and annotated_url != selected_scan.get('image_url'):
                    response = requests.get(annotated_url, timeout=10)
                    if response.status_code == 200:
                        image = Image.open(io.BytesIO(response.content))
                        st.image(image, caption="AI Detections", width='stretch')
                    else:
                        st.warning("Annotated image not available")
                else:
                    st.info("Annotated image same as original")
            except Exception as e:
                st.warning(f"Could not load annotated image: {e}")
        
        # Metrics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("📍 Location", f"{selected_scan['latitude']:.4f}, {selected_scan['longitude']:.4f}")
        
        with col2:
            detection_count = len(selected_scan.get('detection_results', []) or [])
            st.metric("🔍 Objects Detected", detection_count)
        
        with col3:
            report = parse_llm_report(selected_scan.get('llm_report_structured'))
            issues_count = len(report.get('issues', []))
            st.metric("⚠️ Issues Found", issues_count)
        
        # AI Analysis Report
        st.subheader("🤖 AI Analysis Report")
        
        report = parse_llm_report(selected_scan.get('llm_report_structured'))
        
        # Summary
        summary = report.get('summary', 'No summary available')
        st.write(f"**Summary:** {summary}")
        
        # Issues
        issues = report.get('issues', [])
        if issues:
            st.write("**Identified Issues:**")
            
            for i, issue in enumerate(issues):
                severity = issue.get('severity', 'Unknown')
                issue_type = issue.get('type', 'Unknown').replace('_', ' ').title()
                description = issue.get('description', 'No description provided')
                
                # Severity emoji and color
                severity_config = {
                    'High': {'emoji': '🔴', 'color': 'red'},
                    'Medium': {'emoji': '🟡', 'color': 'orange'}, 
                    'Low': {'emoji': '🟢', 'color': 'green'}
                }
                
                config = severity_config.get(severity, {'emoji': '⚪', 'color': 'gray'})
                
                with st.expander(f"{config['emoji']} {issue_type} ({severity} Severity)", expanded=False):
                    st.write(description)
        else:
            st.success("🎉 No infrastructure issues detected in this scan!")
        
        # Raw data
        with st.expander("🔧 View Raw Detection Data", expanded=False):
            detection_results = selected_scan.get('detection_results', [])
            if detection_results:
                df_detections = pd.DataFrame(detection_results)
                st.dataframe(df_detections, width='stretch')
            else:
                st.write("No detection data available")
        
        # with st.expander("📄 View Raw Report Data", expanded=False):
        #     st.json(report)

# --- Footer ---
st.markdown("---")
st.markdown("Built with ❤️ using Streamlit, Supabase, and AI")