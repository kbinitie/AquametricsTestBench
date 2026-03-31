"""
Flask application for Aqua Force water monitoring test bench.
Main entry point for the web server.
"""

import json
from flask import Flask, render_template, request, jsonify
from time import time

from analysis import analyze_readings, analyze_payload
from db import init_db, insert_reading, fetch_recent_readings, count_readings
from postprocess import build_postprocess_payload, export_postprocess_report, list_sources

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Limit uploads to 16MB

MAX_LIVE_READINGS = 300
init_db()


def _build_live_summary(results):
    latest = results[-1] if results else None
    flagged_count = sum(1 for row in results if row.get('flags'))
    return {
        'reading_count': len(results),
        'flagged_count': flagged_count,
        'healthy_count': len(results) - flagged_count,
        'persisted_total': count_readings(),
        'latest': latest,
        'latest_flags': latest.get('flags', []) if latest else [],
    }


@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')


@app.route('/post-process')
def post_process():
    """Render the post-processing dashboard."""
    return render_template('postprocess.html')


@app.route('/analyze', methods=['POST'])
def analyze():
    """
    Handle JSON file upload and return analysis results.
    
    Expected request:
    - multipart/form-data with a 'file' field containing a JSON file
    
    Returns:
    - JSON with analysis results (list of rows with flags)
    - Error JSON if file is missing or invalid
    """
    # Check if file was uploaded
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    
    # Check if file was actually selected
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Check if it's a JSON file (basic check)
    if not file.filename.lower().endswith('.json'):
        return jsonify({'error': 'File must be a JSON file'}), 400
    
    try:
        # Analyze the uploaded JSON file
        results = analyze_readings(file)
        
        # Return results as JSON
        return jsonify({
            'success': True,
            'mode': 'uploaded_file',
            'total_rows': len(results),
            'flagged_rows': sum(1 for row in results if len(row.get('flags', [])) > 0),
            'results': results,
            'summary': _build_live_summary(results),
        })
    
    except Exception as e:
        # Return a readable error message
        return jsonify({'error': f'Error processing JSON: {str(e)}'}), 400


@app.route('/ingest', methods=['POST'])
def ingest():
    """
    Receive live sensor data in the sensor.ino JSON format.

    Accepts either a single reading object or an array of reading objects.
    Persists every reading for post-processing and serves a rolling dashboard window.
    """
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({'error': 'Request body must be valid JSON'}), 400

    try:
        analyzed = analyze_payload(payload)
    except Exception as e:
        return jsonify({'error': f'Error processing live JSON: {str(e)}'}), 400

    now_ms = int(time() * 1000)
    for reading in analyzed:
        stored = dict(reading)
        stored['received_at_ms'] = now_ms
        stored['flags_json'] = json.dumps(stored.get('flags', []))
        insert_reading(stored)

    current_results = fetch_recent_readings(MAX_LIVE_READINGS)

    return jsonify({
        'success': True,
        'accepted': len(analyzed),
        'summary': _build_live_summary(current_results),
    }), 202


@app.route('/api/live-readings', methods=['GET'])
def get_live_readings():
    """Return the rolling window of persisted live readings for the dashboard."""
    results = fetch_recent_readings(MAX_LIVE_READINGS)

    return jsonify({
        'success': True,
        'mode': 'live_stream',
        'results': results,
        'summary': _build_live_summary(results),
    })


@app.route('/api/post-process/sources', methods=['GET'])
def get_postprocess_sources():
    """List available persisted databases for post-processing."""
    return jsonify({
        'success': True,
        'sources': list_sources(),
    })


@app.route('/api/post-process/analytics', methods=['POST'])
def get_postprocess_analytics():
    """Return aggregate analytics across one or more persisted databases."""
    payload = request.get_json(silent=True) or {}
    database_paths = payload.get('database_paths') or []
    limit = int(payload.get('limit') or 240)
    bucket_minutes = int(payload.get('bucket_minutes') or 5)
    alignment_mode = payload.get('alignment_mode') or 'elapsed'
    start_timestamp_ms = payload.get('start_timestamp_ms')
    end_timestamp_ms = payload.get('end_timestamp_ms')
    reference = payload.get('reference')

    try:
        analytics = build_postprocess_payload(
            database_paths=database_paths,
            limit=limit,
            start_timestamp_ms=int(start_timestamp_ms) if start_timestamp_ms not in (None, "") else None,
            end_timestamp_ms=int(end_timestamp_ms) if end_timestamp_ms not in (None, "") else None,
            reference_config=reference if reference and reference.get('enabled') else None,
            bucket_minutes=bucket_minutes,
            alignment_mode=alignment_mode,
        )
    except Exception as e:
        return jsonify({'error': f'Error building post-processing analytics: {str(e)}'}), 400

    return jsonify({
        'success': True,
        'analytics': analytics,
    })


@app.route('/api/post-process/export', methods=['POST'])
def export_postprocess():
    """Return an export-ready JSON report for post-processing analytics."""
    payload = request.get_json(silent=True) or {}
    database_paths = payload.get('database_paths') or []
    limit = int(payload.get('limit') or 240)
    bucket_minutes = int(payload.get('bucket_minutes') or 5)
    alignment_mode = payload.get('alignment_mode') or 'elapsed'
    start_timestamp_ms = payload.get('start_timestamp_ms')
    end_timestamp_ms = payload.get('end_timestamp_ms')
    reference = payload.get('reference')

    try:
        report = export_postprocess_report(
            database_paths=database_paths,
            limit=limit,
            start_timestamp_ms=int(start_timestamp_ms) if start_timestamp_ms not in (None, "") else None,
            end_timestamp_ms=int(end_timestamp_ms) if end_timestamp_ms not in (None, "") else None,
            reference_config=reference if reference and reference.get('enabled') else None,
            bucket_minutes=bucket_minutes,
            alignment_mode=alignment_mode,
        )
    except Exception as e:
        return jsonify({'error': f'Error exporting post-processing report: {str(e)}'}), 400

    return jsonify({
        'success': True,
        'report': report,
    })


if __name__ == '__main__':
    # Run the Flask app on all interfaces so devices on the local network can POST readings.
    app.run(debug=True, host='0.0.0.0', port=5000)
