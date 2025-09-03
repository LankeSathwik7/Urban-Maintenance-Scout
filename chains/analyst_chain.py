from langchain.prompts import PromptTemplate
from langchain_groq import ChatGroq
import json
import ast
import re
import os
from dotenv import load_dotenv
from PIL import Image
import requests
from io import BytesIO

load_dotenv()

# --- Initialize Groq LLM (Llama 3.1 8B Instant, fast + cheap) ---
llm = ChatGroq(
    model="llama-3.1-8b-instant",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.1
)

# --- Prompt Template ---
prompt_template = """
You are an expert urban planning and public works analyst. Your task is to review computer vision detection data from a street view image and identify potential public infrastructure issues.

DETECTION DATA:
{detections_json}

**Instructions:**

**CRITICAL RULES:**
1. Be conservative - when in doubt, report NO issues
2. Do NOT infer or assume problems that aren't explicitly shown

1. Analyze ALL detected objects in the context of public infrastructure maintenance.
2. Focus specifically on issues related to:
   - Road and sidewalk conditions (potholes, cracks, deterioration)
   - Signage and traffic control devices (visibility, damage, obstruction)
   - Drainage systems (clogged drains, standing water)
   - Vegetation management (overgrowth obstructing paths or signs)
   - Utility infrastructure (damaged poles, exposed wires)
   - Public safety hazards (obstructed visibility, damaged barriers)
   - Public amenities (damaged benches, broken lighting)
   - Traffic issues (congestion, illegal parking, trucks in residential zones)

3. CRITICAL RULE: The summary MUST match the issues array. If you find no issues, the summary must state "No infrastructure issues detected." If you find issues, list them in both the summary AND the issues array.

4. For each identified issue:
   - Categorize it (e.g., 'pothole', 'faded_marking', 'overgrown_vegetation', 'damaged_sign', 'illegal_parking')
   - Assign a severity level: 'High', 'Medium', or 'Low'
   - Provide a concise description of the issue and its potential impact

5. Common objects that are NOT issues and do not report them:
   - Normal cars parked legally
   - Standard trees and vegetation (unless overgrown/obstructing)
   - Regular buildings and architecture
   - People walking normally
   - Traffic lights and signs in good condition

**Output MUST be valid JSON only, in this exact schema:**
{{
  "summary": "A one-sentence overview that accurately reflects the issues array below.",
  "issues": [
    {{
      "type": "issue_category",
      "severity": "High/Medium/Low",
      "description": "Specific description of the issue and its impact."
    }}
  ]
}}

**Examples:**

If NO issues are found:
{{
  "summary": "No infrastructure issues detected in this urban scene.",
  "issues": []
}}

If issues ARE found:
{{
  "summary": "Two infrastructure issues identified: a pothole requiring repair and faded road markings.",
  "issues": [
    {{
      "type": "pothole",
      "severity": "High", 
      "description": "Large pothole in road surface poses risk to vehicle damage and traffic safety."
    }},
    {{
      "type": "faded_marking",
      "severity": "Medium",
      "description": "Road lane markings are severely faded, potentially causing driver confusion."
    }}
  ]
}}

Remember: BE CONSERVATIVE. Only report actual infrastructure problems, not normal urban elements.

JSON Output:
"""

prompt = PromptTemplate(
    input_variables=["detections_json"],
    template=prompt_template,
)

# Use the recommended syntax instead of LLMChain
analysis_chain = prompt | llm

# --- JSON Extraction Helper ---
def extract_report_dict(text: str):
    """
    Extract exactly one properly-formed JSON dict (with summary/issues).
    Always returns a valid dict.
    """
    print(f"DEBUG: Raw LLM response: {text}")
    
    # Clean the text first
    text = text.strip()
    
    # Try direct JSON parsing first
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and "summary" in parsed and "issues" in parsed:
            print("DEBUG: Successfully parsed direct JSON")
            return parsed
    except Exception as e:
        print(f"DEBUG: Direct JSON parsing failed: {e}")

    # Try to find JSON block in the text
    json_patterns = [
        r'\{[\s\S]*?"summary"[\s\S]*?"issues"[\s\S]*?\}',
        r'\{[\s\S]*?\}',
    ]
    
    for pattern in json_patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            try:
                parsed = json.loads(match)
                if isinstance(parsed, dict) and "summary" in parsed and "issues" in parsed:
                    print("DEBUG: Successfully parsed JSON from regex match")
                    return parsed
            except Exception as e:
                print(f"DEBUG: Regex JSON parsing failed: {e}")
                # Try with ast.literal_eval as fallback
                try:
                    parsed = ast.literal_eval(match)
                    if isinstance(parsed, dict) and "summary" in parsed and "issues" in parsed:
                        print("DEBUG: Successfully parsed with ast.literal_eval")
                        return parsed
                except Exception as e2:
                    print(f"DEBUG: AST parsing also failed: {e2}")
                    continue

    # If all parsing fails, try to extract at least the summary
    summary_match = re.search(r'"summary":\s*"([^"]*)"', text)
    if summary_match:
        summary = summary_match.group(1)
        print(f"DEBUG: Extracted partial summary: {summary}")
        return {
            "summary": summary,
            "issues": []
        }

    # Ultimate fallback
    print("DEBUG: All parsing methods failed, using fallback")
    return {
        "summary": "Could not parse AI analysis. The detection data may not contain recognizable infrastructure issues.",
        "issues": []
    }

# Fallback object detection using Hugging Face Transformers
def analyze_image_fallback(image_path, confidence_threshold=0.5):
    """
    Fallback object detection using Hugging Face Transformers.
    """
    try:
        from transformers import pipeline
        
        # Use CPU explicitly to avoid CUDA issues
        object_detector = pipeline("object-detection", 
                                  model="facebook/detr-resnet-50",
                                  device=-1)  # -1 for CPU

        # Open and analyze the image
        image = Image.open(image_path)
        results = object_detector(image)

        # Filter results based on confidence threshold
        filtered_results = [
            {
                "label": detection["label"],
                "score": float(detection["score"]),
                "box": {
                    "xmin": int(detection["box"]["xmin"]),
                    "ymin": int(detection["box"]["ymin"]),
                    "xmax": int(detection["box"]["xmax"]),
                    "ymax": int(detection["box"]["ymax"])
                }
            }
            for detection in results 
            if detection['score'] >= confidence_threshold
        ]
        
        print(f"DEBUG: Fallback detection found {len(filtered_results)} objects")
        return filtered_results
        
    except Exception as e:
        print(f"Error analyzing image with fallback model: {e}")
        return []

# --- Main Report Generator ---
def generate_report(detections):
    """
    Generates a structured JSON report from detection results.

    Args:
        detections (list): Detection output from object detection model.

    Returns:
        dict: Parsed JSON report.
    """
    print(f"DEBUG: generate_report called with {len(detections)} detections")
    
    if not detections:
        print("DEBUG: No detections provided")
        return {
            "summary": "No objects detected. This may be due to poor image quality or empty scene.",
            "issues": []
        }

    # Ensure detections are properly formatted
    formatted_detections = []
    for detection in detections:
        try:
            formatted_detection = {
                "label": str(detection.get("label", "unknown")),
                "score": float(detection.get("score", 0.0)),
                "box": detection.get("box", {})
            }
            formatted_detections.append(formatted_detection)
        except Exception as e:
            print(f"DEBUG: Error formatting detection: {e}")
            continue

    detections_json = json.dumps(formatted_detections, indent=2)
    print(f"DEBUG: Formatted detections JSON: {detections_json}")

    try:
        # Invoke the chain
        print("DEBUG: Invoking LLM chain...")
        response = analysis_chain.invoke({"detections_json": detections_json})
        
        # Extract content from response
        if hasattr(response, 'content'):
            report_text = response.content
        else:
            report_text = str(response)
            
        print(f"DEBUG: LLM response received: {report_text[:200]}...")
        
        # Extract and return the structured report
        result = extract_report_dict(report_text)
        print(f"DEBUG: Final parsed result: {result}")

        # After getting the LLM response, add this:
        print(f"DEBUG: Raw LLM Response:")
        print("="*50)
        print(report_text)
        print("="*50)

        # Also add validation after parsing:
        result = extract_report_dict(report_text)
        if result['issues'] and 'no' in result['summary'].lower():
            print("WARNING: Summary/issues mismatch detected!")
            result['summary'] = f"Found {len(result['issues'])} infrastructure issues requiring attention."

        return result
        
    except Exception as e:
        print(f"⚠️ Error invoking LLM chain: {e}")
        return {
            "summary": f"Error: LLM chain failed - {str(e)}", 
            "issues": []
        }

# --- Image Analysis Function ---
def analyze_image(image_path, confidence_threshold=0.5):
    """
    Main function to analyze images. Uses fallback method since Grounding DINO
    requires specific setup that might not be available in all environments.
    """
    print(f"DEBUG: analyze_image called with {image_path}")
    return analyze_image_fallback(image_path, confidence_threshold)

# --- Draw Bounding Boxes Function ---
def draw_bounding_boxes(image_path, detections, output_path="annotated_image.jpg"):
    """
    Draws bounding boxes on the image and saves it.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        image = Image.open(image_path)
        draw = ImageDraw.Draw(image)
        
        # Try to load a font, fall back to default if not available
        try:
            font = ImageFont.truetype("arial.ttf", 15)
        except:
            try:
                font = ImageFont.load_default()
            except:
                font = None

        for detection in detections:
            try:
                box = detection['box']
                label = detection['label']
                score = detection['score']

                # Ensure box coordinates are integers
                xmin = int(box['xmin'])
                ymin = int(box['ymin'])
                xmax = int(box['xmax'])
                ymax = int(box['ymax'])

                # Draw rectangle
                draw.rectangle([(xmin, ymin), (xmax, ymax)], outline="red", width=3)
                
                # Draw label
                text = f"{label} {score:.2f}"
                if font:
                    # Calculate text size for background
                    bbox = draw.textbbox((xmin, ymin), text, font=font)
                    draw.rectangle(bbox, fill="red")
                    draw.text((xmin, ymin), text, fill="white", font=font)
                else:
                    draw.text((xmin, ymin), text, fill="red")
                    
            except Exception as e:
                print(f"Error drawing detection {detection}: {e}")
                continue

        image.save(output_path)
        print(f"Annotated image saved to {output_path}")
        return True
        
    except Exception as e:
        print(f"Error drawing bounding boxes: {e}")
        return False

# --- Debugging run ---
if __name__ == "__main__":
    # Test with dummy data
    dummy_detections = [
        {'score': 0.98, 'label': 'car', 'box': {'xmin': 100, 'ymin': 200, 'xmax': 300, 'ymax': 250}},
        {'score': 0.87, 'label': 'traffic light', 'box': {'xmin': 400, 'ymin': 50, 'xmax': 420, 'ymax': 120}},
        {'score': 0.65, 'label': 'stop sign', 'box': {'xmin': 150, 'ymin': 350, 'xmax': 180, 'ymax': 380}}
    ]
    
    print("Testing with dummy data...")
    report = generate_report(dummy_detections)
    print("Generated report:")
    print(json.dumps(report, indent=2))
    
    # Test with a real image (if available)
    try:
        # Download a test image
        test_image_url = "https://www.unionmutual.com/wp-content/uploads/2016/07/Potholes-resized-for-blog.jpg"
        response = requests.get(test_image_url)
        test_image_path = "test_street_view.jpg"
        
        with open(test_image_path, "wb") as f:
            f.write(response.content)
        
        print(f"\nTesting with real image: {test_image_path}")
        # Analyze the image
        detections = analyze_image(test_image_path)
        print(f"Detected {len(detections)} objects")
        
        # Generate report
        report = generate_report(detections)
        print("Generated report:")
        print(json.dumps(report, indent=2))
        
        # Draw bounding boxes
        success = draw_bounding_boxes(test_image_path, detections, "test_annotated.jpg")
        if success:
            print("Bounding boxes drawn successfully")
        
    except Exception as e:
        print(f"Test with real image failed: {e}")