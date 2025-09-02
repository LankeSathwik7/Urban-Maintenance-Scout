from transformers import pipeline
from PIL import Image, ImageDraw
import os

def analyze_image(image_path):
    """
    Analyzes an image for objects using a pre-trained model from Hugging Face.

    Args:
        image_path (str): Path to the image file.

    Returns:
        list: A list of dictionaries containing detected objects, scores, and bounding boxes.
    """
    # Use the Hugging Face pipeline for object detection
    object_detector = pipeline("object-detection", model="facebook/detr-resnet-50")

    # Open and analyze the image
    image = Image.open(image_path)
    results = object_detector(image)

    # The results are a list of dicts: [{'score': 0.95, 'label': 'person', 'box': {'xmin': 10, 'ymin': 20, 'xmax': 30, 'ymax': 40}},...]
    return results

def draw_bounding_boxes(image_path, detections, output_path="annotated_image.jpg"):
    """
    Draws bounding boxes on the image and saves it.

    Args:
        image_path (str): Path to the original image.
        detections (list): List of detection results from analyze_image.
        output_path (str): Path to save the annotated image.
    """
    image = Image.open(image_path)
    draw = ImageDraw.Draw(image)

    for detection in detections:
        box = detection['box']
        label = detection['label']
        score = detection['score']

        # Draw rectangle
        draw.rectangle([(box['xmin'], box['ymin']), (box['xmax'], box['ymax'])], outline="red", width=3)
        # Draw label background and text
        draw.text((box['xmin'], box['ymin']), f"{label} {score:.2f}", fill="red")

    image.save(output_path)
    print(f"Annotated image saved to {output_path}")

if __name__ == "__main__":
    # Test with the image we just fetched
    img_path = "street_view.jpg"
    detections = analyze_image(img_path)
    print("Detections:", detections)
    # Draw the boxes on the image
    draw_bounding_boxes(img_path, detections)