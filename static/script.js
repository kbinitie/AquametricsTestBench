/**
 * Frontend JavaScript for Aqua Force Test Bench
 * Handles live polling, chart rendering, and JSON file analysis.
 */

const POLL_INTERVAL_MS = 3000;
const CHART_WIDTH = 640;
const CHART_HEIGHT = 220;
const CHART_PADDING = 24;

function formatNumber(value, digits = 2) {
    if (value === null || value === undefined || value === "") {
        return "--";
    }
    const num = Number(value);
    return Number.isFinite(num) ? num.toFixed(digits) : String(value);
}

function formatReadingTime(timestampMs) {
    if (timestampMs === null || timestampMs === undefined || timestampMs === "") {
        return "No timestamp";
    }
    return `${timestampMs} ms`;
}

function createEmptyState(message) {
    const state = document.createElement("div");
    state.className = "empty-state";
    state.textContent = message;
    return state;
}

function createChart(container, readings, valueKey, color, unitLabel) {
    container.innerHTML = "";

    if (!readings.length) {
        container.appendChild(createEmptyState("Waiting for readings"));
        return;
    }

    const points = readings
        .map((reading, index) => ({
            x: index,
            y: Number(reading[valueKey]),
            flagged: Array.isArray(reading.flags) && reading.flags.length > 0,
        }))
        .filter(point => Number.isFinite(point.y));

    if (!points.length) {
        container.appendChild(createEmptyState("No numeric data available"));
        return;
    }

    let min = Math.min(...points.map(point => point.y));
    let max = Math.max(...points.map(point => point.y));
    if (min === max) {
        min -= 1;
        max += 1;
    }

    const chartRange = max - min;
    const horizontalStep = points.length === 1 ? 0 : (CHART_WIDTH - CHART_PADDING * 2) / (points.length - 1);
    const toX = point => CHART_PADDING + point.x * horizontalStep;
    const toY = point => CHART_HEIGHT - CHART_PADDING - ((point.y - min) / chartRange) * (CHART_HEIGHT - CHART_PADDING * 2);
    const polyline = points.map(point => `${toX(point)},${toY(point)}`).join(" ");

    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", `0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`);
    svg.setAttribute("class", "chart-svg");

    const background = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    background.setAttribute("x", "0");
    background.setAttribute("y", "0");
    background.setAttribute("width", String(CHART_WIDTH));
    background.setAttribute("height", String(CHART_HEIGHT));
    background.setAttribute("rx", "18");
    background.setAttribute("class", "chart-bg");
    svg.appendChild(background);

    [0, 0.5, 1].forEach(position => {
        const y = CHART_PADDING + position * (CHART_HEIGHT - CHART_PADDING * 2);
        const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
        line.setAttribute("x1", String(CHART_PADDING));
        line.setAttribute("x2", String(CHART_WIDTH - CHART_PADDING));
        line.setAttribute("y1", String(y));
        line.setAttribute("y2", String(y));
        line.setAttribute("class", "chart-grid-line");
        svg.appendChild(line);
    });

    const path = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", color);
    path.setAttribute("stroke-width", "4");
    path.setAttribute("stroke-linecap", "round");
    path.setAttribute("stroke-linejoin", "round");
    path.setAttribute("points", polyline);
    svg.appendChild(path);

    points.forEach(point => {
        const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        circle.setAttribute("cx", String(toX(point)));
        circle.setAttribute("cy", String(toY(point)));
        circle.setAttribute("r", point.flagged ? "5" : "3.5");
        circle.setAttribute("fill", point.flagged ? "#f25f5c" : color);
        svg.appendChild(circle);
    });

    const minLabel = document.createElementNS("http://www.w3.org/2000/svg", "text");
    minLabel.setAttribute("x", String(CHART_PADDING));
    minLabel.setAttribute("y", String(CHART_HEIGHT - 6));
    minLabel.setAttribute("class", "chart-label");
    minLabel.textContent = `${formatNumber(min)} ${unitLabel}`;
    svg.appendChild(minLabel);

    const maxLabel = document.createElementNS("http://www.w3.org/2000/svg", "text");
    maxLabel.setAttribute("x", String(CHART_PADDING));
    maxLabel.setAttribute("y", "18");
    maxLabel.setAttribute("class", "chart-label");
    maxLabel.textContent = `${formatNumber(max)} ${unitLabel}`;
    svg.appendChild(maxLabel);

    container.appendChild(svg);
}

document.addEventListener("DOMContentLoaded", function() {
    const fileInput = document.getElementById("jsonFile");
    const analyzeBtn = document.getElementById("analyzeBtn");
    const loadingDiv = document.getElementById("loading");
    const errorDiv = document.getElementById("error");
    const resultsDiv = document.getElementById("results");
    const summaryDiv = document.getElementById("summary");
    const tableContainer = document.getElementById("tableContainer");
    const readingCount = document.getElementById("readingCount");
    const flaggedCount = document.getElementById("flaggedCount");
    const latestWaterTemp = document.getElementById("latestWaterTemp");
    const latestTurbidity = document.getElementById("latestTurbidity");
    const lastUpdatedText = document.getElementById("lastUpdatedText");
    const connectionText = document.getElementById("connectionText");
    const connectionDot = document.getElementById("connectionDot");
    const alertList = document.getElementById("alertList");
    const ambientChart = document.getElementById("ambientChart");
    const waterChart = document.getElementById("waterChart");
    const turbidityChart = document.getElementById("turbidityChart");
    const phChart = document.getElementById("phChart");

    function showLoading() {
        loadingDiv.style.display = "block";
    }

    function hideLoading() {
        loadingDiv.style.display = "none";
    }

    function showError(message) {
        errorDiv.textContent = message;
        errorDiv.style.display = "block";
    }

    function hideError() {
        errorDiv.style.display = "none";
    }

    function hideResults() {
        resultsDiv.style.display = "none";
    }

    function setConnectionState(isConnected) {
        connectionText.textContent = isConnected ? "Live feed active" : "Waiting for live data";
        connectionDot.classList.toggle("is-live", isConnected);
    }

    function renderAlerts(summary) {
        alertList.innerHTML = "";

        if (!summary || !summary.latest || !summary.latest_flags || !summary.latest_flags.length) {
            const item = document.createElement("div");
            item.className = "alert-chip ok";
            item.textContent = "Latest reading is within configured ranges.";
            alertList.appendChild(item);
            return;
        }

        summary.latest_flags.forEach(flag => {
            const item = document.createElement("div");
            item.className = "alert-chip";
            item.textContent = flag;
            alertList.appendChild(item);
        });
    }

    function renderLiveDashboard(data) {
        const readings = data.results || [];
        const summary = data.summary || {};
        const latest = summary.latest || null;

        readingCount.textContent = String(summary.persisted_total || 0);
        flaggedCount.textContent = String(summary.flagged_count || 0);
        latestWaterTemp.textContent = latest ? `${formatNumber(latest.water_temp_c)} °C` : "--";
        latestTurbidity.textContent = latest ? `${formatNumber(latest.turbidity_ntu)} NTU` : "--";
        lastUpdatedText.textContent = latest
            ? `Latest reading at ${formatReadingTime(latest.timestamp_ms)}`
            : "No readings received yet.";
        setConnectionState(readings.length > 0);
        renderAlerts(summary);

        createChart(ambientChart, readings, "ambient_temp_c", "#60a5fa", "°C");
        createChart(waterChart, readings, "water_temp_c", "#2563eb", "°C");
        createChart(turbidityChart, readings, "turbidity_ntu", "#0f172a", "NTU");
        createChart(phChart, readings, "ph", "#38bdf8", "pH");
    }

    function displayUploadedResults(data) {
        const totalRows = data.total_rows;
        const flaggedRows = data.flagged_rows;
        summaryDiv.innerHTML = `
            <p><strong>Total readings analyzed:</strong> ${totalRows}</p>
            <p><strong>Flagged readings:</strong> ${flaggedRows}</p>
            <p><strong>Healthy readings:</strong> ${totalRows - flaggedRows}</p>
        `;

        const list = document.createElement("div");
        list.className = "reading-list";

        (data.results || []).slice(-12).reverse().forEach(row => {
            const card = document.createElement("article");
            card.className = "reading-card";
            card.innerHTML = `
                <div class="reading-topline">
                    <span>${formatReadingTime(row.timestamp_ms)}</span>
                    <span>${row.sensor_id || "sensor"}</span>
                </div>
                <div class="reading-stats">
                    <span>Ambient ${formatNumber(row.ambient_temp_c)} °C</span>
                    <span>Water ${formatNumber(row.water_temp_c)} °C</span>
                    <span>Turbidity ${formatNumber(row.turbidity_ntu)} NTU</span>
                    <span>pH ${formatNumber(row.ph)}</span>
                </div>
                <div class="reading-flags ${row.flags && row.flags.length ? "has-flags" : "no-flags"}">
                    ${row.flags && row.flags.length ? row.flags.join(", ") : "No flags"}
                </div>
            `;
            list.appendChild(card);
        });

        tableContainer.innerHTML = "";
        tableContainer.appendChild(list);
        resultsDiv.style.display = "block";
    }

    async function fetchLiveData() {
        try {
            const response = await fetch("/api/live-readings");
            const data = await response.json();
            if (data.error) {
                showError(data.error);
                return;
            }
            hideError();
            renderLiveDashboard(data);
        } catch (error) {
            showError("Unable to load live readings: " + error.message);
            setConnectionState(false);
        }
    }

    analyzeBtn.addEventListener("click", async function() {
        const file = fileInput.files[0];

        if (!file) {
            showError("Please select a JSON file first.");
            return;
        }

        hideError();
        hideResults();
        showLoading();

        const formData = new FormData();
        formData.append("file", file);

        try {
            const response = await fetch("/analyze", {
                method: "POST",
                body: formData
            });
            const data = await response.json();
            hideLoading();

            if (data.error) {
                showError(data.error);
                return;
            }

            displayUploadedResults(data);
        } catch (error) {
            hideLoading();
            showError("An error occurred: " + error.message);
        }
    });

    fetchLiveData();
    window.setInterval(fetchLiveData, POLL_INTERVAL_MS);
});
