# 🏗️ Urban Maintenance Scout

**Proactively identifying public infrastructure issues with AI.**

An intelligent system that uses computer vision and AI to analyze street-view images and automatically detect infrastructure problems like potholes, damaged signs, drainage issues, and safety hazards.

## 🚀 Features

- **Automated Street View Analysis**: Fetches Google Street View images for any coordinates
- **AI-Powered Detection**: Uses Facebook DETR and optional Grounding DINO for object detection
- **Infrastructure Issue Identification**: Groq LLM analyzes detected objects for maintenance issues
- **Interactive Dashboard**: Streamlit-based web interface with map integration
- **Cloud Storage**: Automatic image upload to Supabase Storage
- **Historical Tracking**: Database storage for all scan results and trend analysis
- **Severity Classification**: Issues categorized as High, Medium, or Low priority
- **Export Functionality**: Download scan results as CSV for reporting

## 🛠️ Tech Stack

- **Frontend**: Streamlit with Folium maps
- **Computer Vision**: Transformers (Facebook DETR), optional Grounding DINO
- **AI Analysis**: Groq API (Llama 3.1 8B)
- **Database**: Supabase (PostgreSQL)
- **Storage**: Supabase Storage
- **APIs**: Google Street View Static API
- **Image Processing**: PIL, OpenCV

## 📋 Prerequisites

### System Dependencies

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev libgomp1

# CentOS/RHEL  
sudo yum install -y mesa-libGL
```

### Python Requirements

- Python 3.8+
- pip package manager

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/LankeSathwik7/urban-maintenance-scout.git
cd urban-maintenance-scout
```

### 2. Create Virtual Environment

```bash
python -m venv urban_scout_env
source urban_scout_env/bin/activate  # Linux/Mac
# or
urban_scout_env\Scripts\activate  # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt

# If you encounter libGL errors, use headless OpenCV:
pip uninstall opencv-python opencv-contrib-python
pip install opencv-python-headless
```

### 4. Environment Configuration

Create a `.env` file in the root directory:

```bash
# Google Street View API
STREET_VIEW_API_KEY=your_google_maps_api_key_here

# Groq API for AI Analysis
GROQ_API_KEY=your_groq_api_key_here

# Supabase Configuration
SUPABASE_URL=your_supabase_project_url
SUPABASE_ANON_KEY=your_supabase_anon_key
```

### 5. Database Setup

1. Create a Supabase project at [supabase.com](https://supabase.com)
2. Create the `scans` table:

```sql
CREATE TABLE scans (
  id SERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  latitude FLOAT8 NOT NULL,
  longitude FLOAT8 NOT NULL,
  image_url TEXT,
  annotated_image_url TEXT,
  detection_results JSONB,
  llm_report TEXT,
  llm_report_structured JSONB
);
```

3. Create a storage bucket named `street-view-images`
4. Set up RLS policies as needed

### 6. API Keys Setup

#### Google Street View API
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Enable Street View Static API
3. Create API credentials
4. Add your API key to `.env`

#### Groq API
1. Sign up at [console.groq.com](https://console.groq.com/)
2. Generate an API key
3. Add to `.env` file

## 🎮 Usage

### Running the Dashboard

```bash
streamlit run app.py
```

The dashboard will be available at `http://localhost:8501`

### Using the Dashboard

1. **Select Location**: 
   - Click on the map to set coordinates
   - Use quick location buttons
   - Enter coordinates manually

2. **Run Scan**: 
   - Click "Scan Location" button
   - Monitor progress through the pipeline
   - View results automatically

3. **Analyze Results**:
   - Browse historical scans
   - View original and annotated images
   - Read AI analysis reports
   - Export data for reporting

## 🧩 Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Streamlit     │    │  Google Street   │    │   Computer      │
│   Dashboard     │───▶│  View API        │───▶│   Vision        │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                                               │
         ▼                                               ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Supabase      │◀───│   Groq LLM       │◀───│   Detection     │
│   Database      │    │   Analysis       │    │   Pipeline      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Key Components

- **`app.py`**: Main Streamlit dashboard
- **`utils/fetcher.py`**: Google Street View image fetching
- **`utils/cv_analysis.py`**: Computer vision pipeline
- **`chains/analyst_chain.py`**: AI analysis with Groq LLM
- **`utils/database.py`**: Supabase database operations
- **`utils/storage.py`**: Image storage management
- **`utils/scan_location.py`**: Main orchestration logic

## 🔧 Configuration

### Adjusting Detection Sensitivity

Edit `utils/cv_analysis.py`:

```python
# Lower threshold = more detections (may include false positives)
# Higher threshold = fewer detections (may miss some objects)
detections = analyze_image_combined(image_path, confidence_threshold=0.3)
```

### Customizing AI Analysis

Edit `chains/analyst_chain.py` prompt template to:
- Add new infrastructure categories
- Adjust severity criteria
- Modify analysis guidelines

### Performance Tuning

- **CPU Usage**: Set `device=-1` in cv_analysis.py for CPU-only processing
- **Memory**: Adjust batch sizes and image resolution
- **Speed**: Use `confidence_threshold=0.5` for faster processing

## 🔍 Troubleshooting

### Common Issues

#### `libGL.so.1: cannot open shared object file`

```bash
# Solution 1: Install system dependencies
sudo apt-get install -y libgl1-mesa-glx

# Solution 2: Use headless OpenCV
pip install opencv-python-headless

# Solution 3: Set environment variables
export QT_QPA_PLATFORM=offscreen
export OPENCV_IO_ENABLE_OPENEXR=0
```

#### Groq API Rate Limits

```python
# Add delay between requests in scan_location.py
import time
time.sleep(1)  # Wait 1 second between API calls
```

#### Supabase Connection Issues

- Verify API keys in `.env`
- Check RLS policies
- Ensure storage bucket exists and is accessible

#### Street View API Errors

- Check API key permissions
- Verify billing is enabled
- Ensure Street View Static API is enabled

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📊 Data Schema

### Scans Table

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL | Primary key |
| `created_at` | TIMESTAMPTZ | Scan timestamp |
| `latitude` | FLOAT8 | Location latitude |
| `longitude` | FLOAT8 | Location longitude |
| `image_url` | TEXT | Original image URL |
| `annotated_image_url` | TEXT | Annotated image URL |
| `detection_results` | JSONB | CV detection data |
| `llm_report` | TEXT | Raw AI analysis |
| `llm_report_structured` | JSONB | Structured AI report |

### Detection Results Format

```json
[
  {
    "label": "car",
    "score": 0.95,
    "box": {
      "xmin": 100,
      "ymin": 150,
      "xmax": 200,
      "ymax": 250
    }
  }
]
```

### AI Report Format

```json
{
  "summary": "Infrastructure condition summary",
  "issues": [
    {
      "type": "pothole",
      "severity": "High",
      "description": "Large pothole poses safety risk"
    }
  ]
}
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

### Development Setup

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
python -m pytest tests/

# Code formatting
black .
flake8 .
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Hugging Face Transformers](https://huggingface.co/transformers/) for computer vision models
- [Groq](https://groq.com/) for fast LLM inference
- [Supabase](https://supabase.com/) for backend services
- [Streamlit](https://streamlit.io/) for the web framework

---

**Made with ❤️ for better urban infrastructure**