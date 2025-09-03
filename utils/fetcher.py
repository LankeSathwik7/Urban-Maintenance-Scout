import requests
import os
from dotenv import load_dotenv

load_dotenv()  # Load secrets from .env file

def fetch_street_view_image(latitude, longitude, save_path="street_view.jpg", size="600x400", fov="90", heading="0", pitch="0"):
    """
    Fetches a Street View image for the given latitude and longitude.

    Args:
        latitude (float): The latitude of the location.
        longitude (float): The longitude of the location.
        save_path (str): The path to save the image to.
        size (str): Size of the image (e.g., "600x400", "800x600").
        fov (str): Field of view in degrees (default: "90").
        heading (str): Compass heading in degrees (0=north, 90=east, 180=south, 270=west).
        pitch (str): Up/down angle in degrees (-90 to 90, default: "0").

    Returns:
        str: The path to the saved image, or None if the request failed.
    """
    base_url = "https://maps.googleapis.com/maps/api/streetview"
    
    api_key = os.getenv("STREET_VIEW_API_KEY")
    if not api_key:
        print("Error: STREET_VIEW_API_KEY not found in environment variables")
        return None

    params = {
        "size": size,
        "location": f"{latitude},{longitude}",
        "fov": fov,
        "heading": heading,
        "pitch": pitch,
        "key": api_key
    }

    print(f"DEBUG: Fetching Street View image for coordinates ({latitude}, {longitude})")
    print(f"DEBUG: Request URL: {base_url}")
    print(f"DEBUG: Parameters: {params}")

    try:
        response = requests.get(base_url, params=params, timeout=30)
        
        print(f"DEBUG: Response status code: {response.status_code}")
        print(f"DEBUG: Response headers: {dict(response.headers)}")

        if response.status_code == 200:
            # Check if we actually got an image (not an error page)
            content_type = response.headers.get('content-type', '').lower()
            if 'image' in content_type:
                # Save the image to a file
                with open(save_path, 'wb') as f:
                    f.write(response.content)
                
                # Verify the file was saved and has content
                if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
                    print(f"Image successfully saved to {save_path} (size: {os.path.getsize(save_path)} bytes)")
                    return save_path
                else:
                    print(f"Error: File was not saved properly to {save_path}")
                    return None
            else:
                print(f"Error: Response is not an image (content-type: {content_type})")
                print(f"Response content preview: {response.text[:200]}")
                return None
        else:
            print(f"Error: Unable to download image. Status code: {response.status_code}")
            print(f"Response content: {response.text}")
            
            # Handle specific error cases
            if response.status_code == 403:
                print("This might be an API key issue. Check if your STREET_VIEW_API_KEY is valid and has Street View API enabled.")
            elif response.status_code == 400:
                print("Bad request. Check if the coordinates are valid and the parameters are correct.")
                
            return None
            
    except requests.exceptions.Timeout:
        print("Error: Request timed out after 30 seconds")
        return None
    except requests.exceptions.ConnectionError:
        print("Error: Connection error. Check your internet connection.")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error: Request failed with exception: {e}")
        return None
    except Exception as e:
        print(f"Error: Unexpected error occurred: {e}")
        return None

def fetch_multiple_angles(latitude, longitude, base_save_path="street_view", angles=[0, 90, 180, 270]):
    """
    Fetches Street View images from multiple angles for the same location.
    
    Args:
        latitude (float): The latitude of the location.
        longitude (float): The longitude of the location.
        base_save_path (str): Base path for saving images (angle will be appended).
        angles (list): List of heading angles to capture.
        
    Returns:
        list: List of paths to saved images, or empty list if all failed.
    """
    saved_images = []
    
    for angle in angles:
        save_path = f"{base_save_path}_{angle}.jpg"
        result = fetch_street_view_image(
            latitude=latitude,
            longitude=longitude,
            save_path=save_path,
            heading=str(angle)
        )
        
        if result:
            saved_images.append(result)
        else:
            print(f"Failed to fetch image at angle {angle}")
    
    return saved_images

def validate_coordinates(latitude, longitude):
    """
    Validates that coordinates are within valid ranges.
    
    Args:
        latitude (float): The latitude to validate.
        longitude (float): The longitude to validate.
        
    Returns:
        bool: True if coordinates are valid, False otherwise.
    """
    try:
        lat = float(latitude)
        lon = float(longitude)
        
        if not (-90 <= lat <= 90):
            print(f"Invalid latitude: {lat}. Must be between -90 and 90.")
            return False
            
        if not (-180 <= lon <= 180):
            print(f"Invalid longitude: {lon}. Must be between -180 and 180.")
            return False
            
        return True
    except (ValueError, TypeError):
        print(f"Invalid coordinate format: latitude={latitude}, longitude={longitude}")
        return False

# Test the function
if __name__ == "__main__":
    print("Testing Street View image fetcher...")
    
    # Test coordinates (Golden Gate Bridge)
    test_locations = [
        (37.8199, -122.4783, "Golden Gate Bridge"),
        (40.7128, -74.0060, "New York City"),
        (51.5074, -0.1278, "London"),
    ]
    
    for lat, lon, name in test_locations:
        print(f"\nTesting {name} ({lat}, {lon})...")
        
        if validate_coordinates(lat, lon):
            result = fetch_street_view_image(lat, lon, f"test_{name.lower().replace(' ', '_')}.jpg")
            if result:
                print(f"✅ Successfully fetched image for {name}")
            else:
                print(f"❌ Failed to fetch image for {name}")
        else:
            print(f"❌ Invalid coordinates for {name}")
    
    # Test multiple angles for one location
    print(f"\nTesting multiple angles for Golden Gate Bridge...")
    images = fetch_multiple_angles(37.8199, -122.4783, "test_multi")
    print(f"Successfully fetched {len(images)} images from different angles")