# AquametricsTestBench

A simple full-stack demo application for an Aqua Force-style water monitoring test bench. This application can ingest live JSON readings from an ESP32 sensor node or replay saved JSON files, then visualize temperature, turbidity, and pH as a live dashboard.

## Features

- **Simple Web Interface**: Single-page HTML interface for easy file upload
- **Live Sensor Ingestion**: Accepts live `POST` requests from the ESP32 `sensor.ino` payload format
- **JSON Analysis**: Upload JSON files matching the ESP32 `sensor.ino` payload for automated analysis
- **Live Visualization**: Rolling charts and status cards for the latest readings
- **Persistent Storage**: Live readings are archived in a local SQLite database for later post-processing
- **Post-Processing Dashboard**: Compare multiple archives, inspect cross-source summaries, resample runs into time buckets, align runs side-by-side, and overlay a public reference dataset
- **Flag Detection**: Automatically flags rows with:
  - High turbidity (> 5 NTU) → `HIGH_TURBIDITY`
  - pH out of range (< 6.5 or > 8.5) → `PH_OUT_OF_RANGE`
  - Ambient temperature out of range (< 0°C or > 35°C) → `AMBIENT_TEMP_OUT_OF_RANGE`
  - Water temperature out of range (< 0°C or > 35°C) → `WATER_TEMP_OUT_OF_RANGE`
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

### Step 3: Run the Application

- First Plug in the sensor to your computer's USB-C port.

- Connect to the sensor's WiFi "AquametricsTestBench". The password is aquametrics123.

- After connecting, run the following command in the virtual environment. This should be done immediately after connecting as the sensor ignores requests and prints to Serial monitor instead for debugging purposes.

```bash
python app.py
```

The application will start on `http://0.0.0.0:5000`

### Step 4: Open in Browser

Visit `http://127.0.0.1:5000` in your web browser on the same machine.

To send live data from the ESP32, point `SERVER_URL` in `sensor.ino` to:

```text
http://<your-computer-local-ip>:5000/ingest
```

## JSON File Format

The application expects JSON readings with the following fields (matching `sensor.ino`):

- `timestamp_ms` - Millisecond timestamp from the ESP32 runtime
- `ambient_temp_c` - Ambient temperature in Celsius (float)
- `water_temp_c` - Water temperature in Celsius (float)
- `turbidity_ntu` - Turbidity in NTU units (float)
- `ph` - pH value (float)
- `sensor_id` - Optional identifier if you want to tag the source sensor

Supported upload shapes:

- A single JSON object
- A JSON array of objects
- NDJSON (one JSON object per line)

## Live API Endpoints

- `POST /ingest` accepts one reading object or an array of reading objects in the `sensor.ino` JSON format
- `GET /api/live-readings` returns the current rolling window of readings and dashboard summary data
- `POST /analyze` accepts a `.json` upload for offline replay and analysis

## Post-Processing Dashboard

- `GET /post-process` renders the archive comparison dashboard
- `GET /api/post-process/sources` lists discovered SQLite archives in the workspace
- `POST /api/post-process/analytics` returns aggregate summaries, cross-source comparisons, bucketed/aligned series, and optional reference data
- `POST /api/post-process/export` returns an exportable JSON report for the current analytics view

The current public reference integration uses the USGS Water Services instantaneous values endpoint for water temperature overlays.

## Persistent Storage

Live readings are stored in a SQLite database at `aquametrics.db` in the project root. The live dashboard reads the most recent rolling window from that database, while the full history remains available for later processing or export.

### Example JSON:

```json
[
  {
    "timestamp_ms": 1000,
    "ambient_temp_c": 22.4,
    "water_temp_c": 19.8,
    "turbidity_ntu": 2.1,
    "ph": 7.0
  },
  {
    "timestamp_ms": 6000,
    "ambient_temp_c": 24.1,
    "water_temp_c": 36.2,
    "turbidity_ntu": 6.2,
    "ph": 8.9,
    "sensor_id": "A1"
  }
]
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

1. **Live ingest**: The ESP32 sends JSON readings to `POST /ingest`
2. **Storage**: Flask persists readings into SQLite and serves a rolling window for the live dashboard
3. **Analysis**: Each reading is checked against the configured flag rules
4. **Dashboard**: The frontend polls `GET /api/live-readings` and renders charts plus alert chips
5. **Post-process**: The archive dashboard can compare multiple databases, align runs, and export reports
6. **Replay**: Saved JSON files can still be uploaded to `/analyze` for inspection

## Technology Stack

- **Backend**: Python 3 + Flask
- **Data Analysis**: Python JSON parsing
- **Frontend**: Vanilla HTML, CSS, and JavaScript (no frameworks or build tools)
