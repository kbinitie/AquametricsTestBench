# AquametricsTestBench

A simple full-stack demo application for an Aqua Force-style water monitoring test bench. This application allows users to upload CSV datasets of water sensor readings and automatically analyzes them to flag potential issues such as low water levels, high turbidity, pH out of range, and temperature anomalies.

## Features

- **Simple Web Interface**: Single-page HTML interface for easy file upload
- **CSV Analysis**: Upload CSV files with water sensor data for automated analysis
- **Flag Detection**: Automatically flags rows with:
  - Low water level (< 20 cm) → `LOW_LEVEL`
  - Overflow risk (> 200 cm) → `OVERFLOW_RISK`
  - High turbidity (> 5 NTU) → `HIGH_TURBIDITY`
  - pH out of range (< 6.5 or > 8.5) → `PH_OUT_OF_RANGE`
  - Temperature out of range (< 0°C or > 35°C) → `TEMP_OUT_OF_RANGE`
- **Results Display**: Clean table view showing all data with flagged issues highlighted

## How to Set Up and Run Locally

### Prerequisites

- Python 3.7 or higher
- pip (Python package installer)

### Step 1: Create a Virtual Environment (Recommended)

On Windows (PowerShell):
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

On Windows (Command Prompt):
```cmd
python -m venv venv
venv\Scripts\activate.bat
```

On macOS/Linux:
```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- Flask (web framework)
- pandas (data analysis)

### Step 3: Run the Application

```bash
python app.py
```

The application will start on `http://127.0.0.1:5000`

### Step 4: Open in Browser

Visit `http://127.0.0.1:5000` in your web browser.

## CSV File Format

The application expects CSV files with the following columns (case-sensitive):

- `timestamp` - Date/time of the reading (string or ISO format)
- `sensor_id` - Identifier for the sensor (string or integer)
- `water_level_cm` - Water level in centimeters (float)
- `turbidity_ntu` - Turbidity in NTU units (float)
- `ph` - pH value (float)
- `temperature_c` - Temperature in Celsius (float)

### Example CSV:

```csv
timestamp,sensor_id,water_level_cm,turbidity_ntu,ph,temperature_c
2025-01-01T12:00:00Z,A1,18.5,2.1,7.0,22.0
2025-01-01T12:05:00Z,A1,25.0,6.2,7.2,23.0
2025-01-01T12:10:00Z,B2,150.0,3.5,5.8,18.0
```

## Project Structure

```
AquametricsTestBench/
├── app.py              # Flask application (main entry point)
├── analysis.py         # Water sensor data analysis logic
├── requirements.txt    # Python dependencies
├── static/
│   ├── style.css      # Frontend styles
│   └── script.js      # Frontend JavaScript
├── templates/
│   └── index.html     # Main web page
└── README.md          # This file
```

## How It Works

1. **Frontend**: The user selects a CSV file and clicks "Run Analysis"
2. **Backend**: Flask receives the file via POST request to `/analyze`
3. **Analysis**: The CSV is parsed and each row is checked against flag rules
4. **Response**: Results are returned as JSON with original data plus flags
5. **Display**: The frontend renders a table showing all rows with flagged issues highlighted

## Technology Stack

- **Backend**: Python 3 + Flask
- **Data Analysis**: pandas
- **Frontend**: Vanilla HTML, CSS, and JavaScript (no frameworks or build tools)
