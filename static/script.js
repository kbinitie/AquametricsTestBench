/**
 * Frontend JavaScript for Aqua Force Test Bench
 * Handles file upload and displays analysis results
 */

/**
 * Safely format a numeric value to 2 decimal places.
 * Handles strings, numbers, null, undefined, and invalid values gracefully.
 */
function formatNumber(value) {
    if (value === null || value === undefined || value === "") {
        return "";
    }
    const num = Number(value);
    return Number.isFinite(num) ? num.toFixed(2) : value;
}

document.addEventListener('DOMContentLoaded', function() {
    const fileInput = document.getElementById('csvFile');
    const analyzeBtn = document.getElementById('analyzeBtn');
    const loadingDiv = document.getElementById('loading');
    const errorDiv = document.getElementById('error');
    const resultsDiv = document.getElementById('results');
    const summaryDiv = document.getElementById('summary');
    const tableContainer = document.getElementById('tableContainer');
    
    analyzeBtn.addEventListener('click', function() {
        // Get the selected file
        const file = fileInput.files[0];
        
        if (!file) {
            showError('Please select a CSV file first.');
            return;
        }
        
        // Hide previous results and errors
        hideError();
        hideResults();
        showLoading();
        
        // Create FormData to send the file
        const formData = new FormData();
        formData.append('file', file);
        
        // Send POST request to /analyze endpoint
        fetch('/analyze', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            hideLoading();
            
            if (data.error) {
                showError(data.error);
            } else {
                displayResults(data);
            }
        })
        .catch(error => {
            hideLoading();
            showError('An error occurred: ' + error.message);
        });
    });
    
    function showLoading() {
        loadingDiv.style.display = 'block';
    }
    
    function hideLoading() {
        loadingDiv.style.display = 'none';
    }
    
    function showError(message) {
        errorDiv.textContent = message;
        errorDiv.style.display = 'block';
    }
    
    function hideError() {
        errorDiv.style.display = 'none';
    }
    
    function hideResults() {
        resultsDiv.style.display = 'none';
    }
    
    function displayResults(data) {
        // Show summary
        const totalRows = data.total_rows;
        const flaggedRows = data.flagged_rows;
        summaryDiv.innerHTML = `
            <p><strong>Total rows analyzed:</strong> ${totalRows}</p>
            <p><strong>Rows with flags:</strong> ${flaggedRows}</p>
            <p><strong>Rows without issues:</strong> ${totalRows - flaggedRows}</p>
        `;
        
        // Create and populate table
        const table = document.createElement('table');
        table.className = 'results-table';
        
        // Create header row
        const headerRow = document.createElement('tr');
        const headers = ['Timestamp', 'Sensor ID', 'Water Level (cm)', 'Turbidity (NTU)', 
                        'pH', 'Temperature (°C)', 'Flags'];
        headers.forEach(headerText => {
            const th = document.createElement('th');
            th.textContent = headerText;
            headerRow.appendChild(th);
        });
        table.appendChild(headerRow);
        
        // Create data rows
        data.results.forEach(row => {
            const tr = document.createElement('tr');
            
            // Add all data cells
            tr.appendChild(createCell(row.timestamp));
            tr.appendChild(createCell(row.sensor_id));
            tr.appendChild(createCell(formatNumber(row.water_level_cm)));
            tr.appendChild(createCell(formatNumber(row.turbidity_ntu)));
            tr.appendChild(createCell(formatNumber(row.ph)));
            tr.appendChild(createCell(formatNumber(row.temperature_c)));
            
            // Flags cell - show comma-separated flags or "None"
            const flagsCell = document.createElement('td');
            if (row.flags && row.flags.length > 0) {
                flagsCell.textContent = row.flags.join(', ');
                flagsCell.className = 'flagged';
            } else {
                flagsCell.textContent = 'None';
                flagsCell.className = 'no-flags';
            }
            tr.appendChild(flagsCell);
            
            table.appendChild(tr);
        });
        
        tableContainer.innerHTML = '';
        tableContainer.appendChild(table);
        
        // Show results section
        resultsDiv.style.display = 'block';
    }
    
    function createCell(text) {
        const td = document.createElement('td');
        td.textContent = text;
        return td;
    }
});

