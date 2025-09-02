from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_groq import ChatGroq # This is the correct import for Groq
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize the Groq LLM - Using the fast Llama 3.1 8B model
llm = ChatGroq(
    model="llama-3.1-8b-instant",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.1 # Low temperature for more factual, deterministic outputs
)

# Create a powerful, detailed prompt template
prompt_template = """
You are an expert urban planning and public works analyst. Your task is to review computer vision detection data from a street view image and identify potential public infrastructure issues.

DETECTION DATA:
{detections_json}

Based on the objects detected above, analyze the scene and generate a concise professional report.
Focus specifically on issues related to:
- Road and sidewalk maintenance (e.g., potholes, cracks, faded road markings)
- Signage and traffic light visibility/obstruction
- Drainage issues or clogged gutters
- Pedestrian safety hazards
- Vegetation overgrowth obstructing paths or signs

If no relevant issues are found, simply state that.

FORMAT YOUR ANSWER as a bulleted list with this structure:
- **Priority: [High/Medium/Low] - [Issue Name]**: [1-2 sentence description of the issue and its potential impact].

Final Summary: Provide a one-sentence overall summary.
"""

prompt = PromptTemplate(
    input_variables=["detections_json"],
    template=prompt_template,
)

# Create the chain
analysis_chain = LLMChain(llm=llm, prompt=prompt)

def generate_report(detections):
    """
    Generates a professional report from detection data.

    Args:
        detections (list): The list of detection dictionaries.

    Returns:
        str: The LLM-generated report.
    """
    # Convert the list of detections to a JSON string for the prompt
    from json import dumps
    detections_json = dumps(detections, indent=2)

    # Run the chain
    report = analysis_chain.run(detections_json=detections_json)
    return report

if __name__ == "__main__":
    # Test with some dummy data
    test_detections = [
        {'score': 0.98, 'label': 'car', 'box': {'xmin': 100, 'ymin': 200, 'xmax': 300, 'ymax': 250}},
        {'score': 0.87, 'label': 'traffic light', 'box': {'xmin': 400, 'ymin': 50, 'xmax': 420, 'ymax': 120}},
        {'score': 0.65, 'label': 'pothole', 'box': {'xmin': 150, 'ymin': 350, 'xmax': 180, 'ymax': 380}}
    ]
    report = generate_report(test_detections)
    print("Generated Report:\n")
    print(report)