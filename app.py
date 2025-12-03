"""
Flask application for Aqua Force water monitoring test bench.
Main entry point for the web server.
"""

from flask import Flask, render_template, request, jsonify
import os
from analysis import analyze_readings

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Limit uploads to 16MB


@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')


@app.route('/analyze', methods=['POST'])
def analyze():
    """
    Handle CSV file upload and return analysis results.
    
    Expected request:
    - multipart/form-data with a 'file' field containing a CSV file
    
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
    
    # Check if it's a CSV file (basic check)
    if not file.filename.lower().endswith('.csv'):
        return jsonify({'error': 'File must be a CSV file'}), 400
    
    try:
        # Analyze the uploaded CSV file
        results = analyze_readings(file)
        
        # Return results as JSON
        return jsonify({
            'success': True,
            'total_rows': len(results),
            'flagged_rows': sum(1 for row in results if len(row.get('flags', [])) > 0),
            'results': results
        })
    
    except Exception as e:
        # Return a readable error message
        return jsonify({'error': f'Error processing CSV: {str(e)}'}), 400


if __name__ == '__main__':
    # Run the Flask app on localhost:5000
    app.run(debug=True, host='127.0.0.1', port=5000)

