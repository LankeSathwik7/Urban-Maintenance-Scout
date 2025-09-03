from transformers import pipeline
from PIL import Image, ImageDraw, ImageFont
import os
import torch
import numpy as np

import sys
import os
sys.path.append(os.path.join(os.getcwd(), "GroundingDINO"))

# Grounding DINO imports
try:
    from groundingdino.util.inference import load_model, load_image, predict
    import torch
    has_dino = True
    print("Grounding DINO successfully imported")
except ImportError:
    print("Grounding DINO not installed. Only Facebook DETR will be used.")
    has_dino = False

def analyze_image_combined(image_path, confidence_threshold=0.3, text_queries=None):
    """
    Combines Facebook DETR and Grounding DINO for urban infrastructure detection.
    
    Args:
        image_path (str): Path to the image.
        confidence_threshold (float): Minimum confidence for detections.
        text_queries (list): List of text queries for Grounding DINO.
    
    Returns:
        list: Unified detection results.
    """
    print(f"DEBUG: analyze_image_combined called with {image_path}")
    combined_detections = []

    # --- 1. Facebook DETR Detection ---
    try:
        print("DEBUG: Loading Facebook DETR...")
        object_detector = pipeline(
            "object-detection",
            model="facebook/detr-resnet-50",
            device=0 if torch.cuda.is_available() else -1
        )
        
        print("DEBUG: Opening image...")
        image = Image.open(image_path)
        
        print("DEBUG: Running DETR detection...")
        fb_results = object_detector(image)
        print(f"DEBUG: DETR found {len(fb_results)} raw detections")

        fb_filtered = []
        for r in fb_results:
            try:
                if r["score"] >= confidence_threshold:
                    detection = {
                        "label": r["label"],
                        "score": float(r["score"]),
                        "box": {
                            "xmin": int(r["box"]["xmin"]),
                            "ymin": int(r["box"]["ymin"]),
                            "xmax": int(r["box"]["xmax"]),
                            "ymax": int(r["box"]["ymax"])
                        }
                    }
                    fb_filtered.append(detection)
            except Exception as e:
                print(f"DEBUG: Error processing DETR result {r}: {e}")
                continue
                
        print(f"DEBUG: DETR filtered to {len(fb_filtered)} detections above threshold")
        combined_detections.extend(fb_filtered)
        
    except Exception as e:
        print(f"Facebook DETR detection failed: {e}")
        # Try fallback if DETR fails
        try:
            print("DEBUG: Trying simplified DETR approach...")
            from transformers import DetrImageProcessor, DetrForObjectDetection
            import torch
            
            processor = DetrImageProcessor.from_pretrained("facebook/detr-resnet-50")
            model = DetrForObjectDetection.from_pretrained("facebook/detr-resnet-50")
            
            image = Image.open(image_path)
            inputs = processor(images=image, return_tensors="pt")
            outputs = model(**inputs)
            
            # Convert outputs to COCO API
            target_sizes = torch.tensor([image.size[::-1]])
            results = processor.post_process_object_detection(outputs, target_sizes=target_sizes, threshold=confidence_threshold)[0]
            
            for score, label, box in zip(results["scores"], results["labels"], results["boxes"]):
                combined_detections.append({
                    "label": model.config.id2label[label.item()],
                    "score": float(score),
                    "box": {
                        "xmin": int(box[0]),
                        "ymin": int(box[1]),
                        "xmax": int(box[2]),
                        "ymax": int(box[3])
                    }
                })
            print(f"DEBUG: Fallback DETR found {len(results['scores'])} detections")
            
        except Exception as e2:
            print(f"Fallback DETR also failed: {e2}")

    # --- 2. Grounding DINO Detection ---
    if has_dino:
        try:
            print("DEBUG: Attempting Grounding DINO detection...")
            # Check if model file exists
            model_config_path = "GroundingDINO/weights/groundingdino_swint_ogc.pth"
            
            if not os.path.exists(model_config_path):
                print(f"DEBUG: Model file not found at {model_config_path}")
                # Try alternative paths
                alt_paths = [
                    "weights/groundingdino_swint_ogc.pth",
                    "groundingdino_swint_ogc.pth",
                    "GroundingDINO/groundingdino_swint_ogc.pth"
                ]
                
                for alt_path in alt_paths:
                    if os.path.exists(alt_path):
                        model_config_path = alt_path
                        break
                else:
                    print("DEBUG: No Grounding DINO model file found, skipping...")
                    raise FileNotFoundError("Model file not found")

            # Load model
            config_path = "GroundingDINO/groundingdino/config/GroundingDINO_SwinT_OGC.py"
            model = load_model(config_path, model_config_path)
            
            dino_image, _ = load_image(image_path)

            if text_queries is None:
                text_queries = [
                    "pothole", "crack in road", "faded road marking", "damaged sidewalk",
                    "overgrown vegetation", "broken street light", "damaged traffic sign",
                    "damaged utility pole", "road obstruction", "safety hazard",
                    "damaged bench", "truck", "traffic congestion",
                    "standing water", "damaged barrier", "exposed wires", "illegal parking",
                    "construction zone", "damaged curb", "broken pavement"
                ]

            text_prompt = ". ".join(text_queries) + "."
            
            boxes, logits, phrases = predict(
                model=model,
                image=dino_image,
                caption=text_prompt,
                box_threshold=confidence_threshold,
                text_threshold=0.25
            )

            # Convert to our format
            h, w, _ = dino_image.shape
            for box, logit, phrase in zip(boxes, logits, phrases):
                # Convert normalized coordinates to pixel coordinates
                x_center, y_center, width, height = box
                xmin = int((x_center - width/2) * w)
                ymin = int((y_center - height/2) * h)
                xmax = int((x_center + width/2) * w)
                ymax = int((y_center + height/2) * h)
                
                combined_detections.append({
                    "label": phrase,
                    "score": float(logit),
                    "box": {
                        "xmin": xmin,
                        "ymin": ymin,
                        "xmax": xmax,
                        "ymax": ymax
                    }
                })

            print(f"DEBUG: Grounding DINO found {len(boxes)} detections")

        except Exception as e:
            print(f"Grounding DINO detection failed: {e}")

    # --- 3. Remove Duplicate Detections ---
    def iou(box1, box2):
        """Calculate Intersection over Union of two boxes"""
        try:
            x1 = max(box1['xmin'], box2['xmin'])
            y1 = max(box1['ymin'], box2['ymin'])
            x2 = min(box1['xmax'], box2['xmax'])
            y2 = min(box1['ymax'], box2['ymax'])
            
            if x2 <= x1 or y2 <= y1:
                return 0.0
                
            inter_area = (x2 - x1) * (y2 - y1)
            box1_area = (box1['xmax'] - box1['xmin']) * (box1['ymax'] - box1['ymin'])
            box2_area = (box2['xmax'] - box2['xmin']) * (box2['ymax'] - box2['ymin'])
            union_area = box1_area + box2_area - inter_area
            
            return inter_area / (union_area + 1e-6)
        except Exception as e:
            print(f"DEBUG: Error calculating IoU: {e}")
            return 0.0

    print(f"DEBUG: Removing duplicates from {len(combined_detections)} total detections...")
    final_detections = []
    
    for det in combined_detections:
        keep = True
        for i, existing in enumerate(final_detections):
            try:
                # Check if labels are similar and IoU is high
                if (det['label'].lower() == existing['label'].lower() or 
                    any(word in det['label'].lower() for word in existing['label'].lower().split()) or
                    any(word in existing['label'].lower() for word in det['label'].lower().split())):
                    
                    if iou(det['box'], existing['box']) > 0.5:
                        # Keep the one with higher score
                        if det['score'] > existing['score']:
                            final_detections[i] = det
                        keep = False
                        break
            except Exception as e:
                print(f"DEBUG: Error comparing detections: {e}")
                continue
                
        if keep:
            final_detections.append(det)

    print(f"DEBUG: Final detection count after deduplication: {len(final_detections)}")
    return final_detections

def draw_bounding_boxes(image_path, detections, output_path="annotated_image.jpg"):
    """
    Draws bounding boxes on the image and saves it.

    Args:
        image_path (str): Path to the original image.
        detections (list): List of detection results from analyze_image.
        output_path (str): Path to save the annotated image.
    """
    try:
        print(f"DEBUG: Drawing bounding boxes for {len(detections)} detections")
        image = Image.open(image_path)
        draw = ImageDraw.Draw(image)

        # Try to load a font, fall back to default if not available
        try:
            font = ImageFont.truetype("arial.ttf", 16)
        except:
            try:
                # Try some common font paths
                font_paths = [
                    "/System/Library/Fonts/Arial.ttf",  # macOS
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux
                    "C:/Windows/Fonts/arial.ttf",  # Windows
                ]
                font = None
                for font_path in font_paths:
                    if os.path.exists(font_path):
                        font = ImageFont.truetype(font_path, 16)
                        break
                
                if font is None:
                    font = ImageFont.load_default()
            except:
                font = None

        colors = ['red', 'blue', 'green', 'yellow', 'purple', 'orange', 'cyan', 'magenta']
        
        for i, detection in enumerate(detections):
            try:
                box = detection['box']
                label = detection['label']
                score = detection['score']
                color = colors[i % len(colors)]

                # Ensure box coordinates are valid integers
                xmin = max(0, int(box['xmin']))
                ymin = max(0, int(box['ymin']))
                xmax = min(image.width, int(box['xmax']))
                ymax = min(image.height, int(box['ymax']))

                # Skip invalid boxes
                if xmin >= xmax or ymin >= ymax:
                    print(f"DEBUG: Skipping invalid box: {box}")
                    continue

                # Draw rectangle
                draw.rectangle([(xmin, ymin), (xmax, ymax)], outline=color, width=3)
                
                # Draw label with background
                text = f"{label} {score:.2f}"
                
                if font:
                    # Calculate text bounding box
                    bbox = draw.textbbox((xmin, ymin), text, font=font)
                    # Draw text background
                    draw.rectangle(bbox, fill=color)
                    # Draw text
                    draw.text((xmin, ymin), text, fill="white", font=font)
                else:
                    # Fallback without font
                    draw.text((xmin, ymin), text, fill=color)
                    
            except Exception as e:
                print(f"DEBUG: Error drawing detection {detection}: {e}")
                continue

        image.save(output_path)
        print(f"Annotated image saved to {output_path}")
        return True
        
    except Exception as e:
        print(f"Error drawing bounding boxes: {e}")
        return False

if __name__ == "__main__":
    # Test the detection system
    test_image_path = "test_street_view.jpg"
    
    # Download a test image if it doesn't exist
    if not os.path.exists(test_image_path):
        import requests
        try:
            test_image_url = "https://www.unionmutual.com/wp-content/uploads/2016/07/Potholes-resized-for-blog.jpg"
            response = requests.get(test_image_url)
            with open(test_image_path, "wb") as f:
                f.write(response.content)
            print(f"Downloaded test image to {test_image_path}")
        except Exception as e:
            print(f"Could not download test image: {e}")
            exit(1)
    
    # Test detection
    detections = analyze_image_combined(test_image_path)
    print("Unified Detections:", detections)
    
    # Draw the boxes on the image
    success = draw_bounding_boxes(test_image_path, detections, "test_annotated.jpg")
    if success:
        print("Test completed successfully!")