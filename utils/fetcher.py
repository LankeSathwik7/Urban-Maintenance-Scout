import requests
import os
from dotenv import load_dotenv

load_dotenv()  # Load secrets from .env file

def fetch_street_view_image(latitude, longitude, save_path="street_view.jpg"):
    """
    Fetches a Street View image for the given latitude and longitude.

    Args:
        latitude (float): The latitude of the location.
        longitude (float): The longitude of the location.
        save_path (str): The path to save the image to.

    Returns:
        str: The path to the saved image, or None if the request failed.
    """
    base_url = "https://maps.googleapis.com/maps/api/streetview"
    size = "600x400"  # Standard size
    fov = "90"        # Field of view
    heading = "0"     # Compass heading (0=north)
    pitch = "0"       # Up/down angle

    params = {
        "size": size,
        "location": f"{latitude},{longitude}",
        "fov": fov,
        "heading": heading,
        "pitch": pitch,
        "key": os.getenv("STREET_VIEW_API_KEY")  # Get key from .env
    }

    response = requests.get(base_url, params=params)

    if response.status_code == 200:
        # Save the image to a file
        with open(save_path, 'wb') as f:
            f.write(response.content)
        print(f"Image successfully saved to {save_path}")
        return save_path
    else:
        print(f"Error: Unable to download image. Status code: {response.status_code}")
        print(response.text) # Might give more info on the error
        return None

# Test the function right here (you can comment this out later)
if __name__ == "__main__":
    # Test with a famous location (Golden Gate Bridge)
        lat, lon = 37.8199, -122.4783
        fetch_street_view_image(lat, lon)