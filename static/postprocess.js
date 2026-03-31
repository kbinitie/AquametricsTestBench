const ANALYTICS_CHART_WIDTH = 700;
const ANALYTICS_CHART_HEIGHT = 240;
const ANALYTICS_CHART_PADDING = 28;
const SOURCE_COLORS = ["#1d4ed8", "#0f766e", "#2563eb", "#38bdf8", "#1e3a8a", "#7dd3fc"];

function formatValue(value, digits = 2) {
    if (value === null || value === undefined || value === "") {
        return "--";
    }
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric.toFixed(digits) : String(value);
}

function formatTimestamp(timestamp) {
    if (timestamp === null || timestamp === undefined || timestamp === "") {
        return "--";
    }
    return `${timestamp} ms`;
}

function createAnalyticsEmptyState(message) {
    const node = document.createElement("div");
    node.className = "empty-state";
    node.textContent = message;
    return node;
}

function renderMultiSeriesChart(container, seriesList, referenceSeries, unitLabel) {
    container.innerHTML = "";

    const combined = [];
    seriesList.forEach(series => {
        series.points.forEach((point, index) => combined.push({ x: index, y: Number(point.value) }));
    });
    if (referenceSeries) {
        referenceSeries.forEach((point, index) => combined.push({ x: index, y: Number(point.value) }));
    }

    const validPoints = combined.filter(point => Number.isFinite(point.y));
    if (!validPoints.length) {
        container.appendChild(createAnalyticsEmptyState("No data available for this view"));
        return;
    }

    let min = Math.min(...validPoints.map(point => point.y));
    let max = Math.max(...validPoints.map(point => point.y));
    if (min === max) {
        min -= 1;
        max += 1;
    }

    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", `0 0 ${ANALYTICS_CHART_WIDTH} ${ANALYTICS_CHART_HEIGHT}`);
    svg.setAttribute("class", "chart-svg");

    const background = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    background.setAttribute("x", "0");
    background.setAttribute("y", "0");
    background.setAttribute("width", String(ANALYTICS_CHART_WIDTH));
    background.setAttribute("height", String(ANALYTICS_CHART_HEIGHT));
    background.setAttribute("rx", "18");
    background.setAttribute("class", "chart-bg");
    svg.appendChild(background);

    [0, 0.5, 1].forEach(position => {
        const y = ANALYTICS_CHART_PADDING + position * (ANALYTICS_CHART_HEIGHT - ANALYTICS_CHART_PADDING * 2);
        const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
        line.setAttribute("x1", String(ANALYTICS_CHART_PADDING));
        line.setAttribute("x2", String(ANALYTICS_CHART_WIDTH - ANALYTICS_CHART_PADDING));
        line.setAttribute("y1", String(y));
        line.setAttribute("y2", String(y));
        line.setAttribute("class", "chart-grid-line");
        svg.appendChild(line);
    });

    const valueRange = max - min;

    function toY(value) {
        return ANALYTICS_CHART_HEIGHT - ANALYTICS_CHART_PADDING - ((value - min) / valueRange) * (ANALYTICS_CHART_HEIGHT - ANALYTICS_CHART_PADDING * 2);
    }

    function drawSeries(points, stroke, dashed = false) {
        if (!points.length) {
            return;
        }
        const step = points.length === 1 ? 0 : (ANALYTICS_CHART_WIDTH - ANALYTICS_CHART_PADDING * 2) / (points.length - 1);
        const polyline = points
            .map((point, index) => `${ANALYTICS_CHART_PADDING + index * step},${toY(Number(point.value))}`)
            .join(" ");

        const path = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
        path.setAttribute("fill", "none");
        path.setAttribute("stroke", stroke);
        path.setAttribute("stroke-width", dashed ? "3" : "4");
        path.setAttribute("stroke-linecap", "round");
        path.setAttribute("stroke-linejoin", "round");
        if (dashed) {
            path.setAttribute("stroke-dasharray", "8 8");
        }
        path.setAttribute("points", polyline);
        svg.appendChild(path);
    }

    seriesList.forEach((series, index) => {
        drawSeries(series.points, SOURCE_COLORS[index % SOURCE_COLORS.length]);
    });

    if (referenceSeries && referenceSeries.length) {
        drawSeries(referenceSeries, "#f97316", true);
    }

    const minLabel = document.createElementNS("http://www.w3.org/2000/svg", "text");
    minLabel.setAttribute("x", String(ANALYTICS_CHART_PADDING));
    minLabel.setAttribute("y", String(ANALYTICS_CHART_HEIGHT - 8));
    minLabel.setAttribute("class", "chart-label");
    minLabel.textContent = `${formatValue(min)} ${unitLabel}`;
    svg.appendChild(minLabel);

    const maxLabel = document.createElementNS("http://www.w3.org/2000/svg", "text");
    maxLabel.setAttribute("x", String(ANALYTICS_CHART_PADDING));
    maxLabel.setAttribute("y", "18");
    maxLabel.setAttribute("class", "chart-label");
    maxLabel.textContent = `${formatValue(max)} ${unitLabel}`;
    svg.appendChild(maxLabel);

    container.appendChild(svg);

    const legend = document.createElement("div");
    legend.className = "legend-row";
    seriesList.forEach((series, index) => {
        const item = document.createElement("div");
        item.className = "legend-item";
        item.innerHTML = `<span class="legend-swatch" style="background:${SOURCE_COLORS[index % SOURCE_COLORS.length]}"></span>${series.label}`;
        legend.appendChild(item);
    });
    if (referenceSeries && referenceSeries.length) {
        const item = document.createElement("div");
        item.className = "legend-item";
        item.innerHTML = `<span class="legend-swatch dashed"></span>USGS reference`;
        legend.appendChild(item);
    }
    container.appendChild(legend);
}

document.addEventListener("DOMContentLoaded", function() {
    const sourceList = document.getElementById("sourceList");
    const limitInput = document.getElementById("limitInput");
    const bucketMinutesInput = document.getElementById("bucketMinutesInput");
    const alignmentModeInput = document.getElementById("alignmentModeInput");
    const startTimestampInput = document.getElementById("startTimestampInput");
    const endTimestampInput = document.getElementById("endTimestampInput");
    const referenceEnabled = document.getElementById("referenceEnabled");
    const referenceSite = document.getElementById("referenceSite");
    const referencePeriod = document.getElementById("referencePeriod");
    const runAnalyticsBtn = document.getElementById("runAnalyticsBtn");
    const exportReportBtn = document.getElementById("exportReportBtn");
    const analyticsLoading = document.getElementById("analyticsLoading");
    const analyticsError = document.getElementById("analyticsError");
    const sourceCount = document.getElementById("sourceCount");
    const windowReadingCount = document.getElementById("windowReadingCount");
    const windowFlaggedCount = document.getElementById("windowFlaggedCount");
    const latestTimestamp = document.getElementById("latestTimestamp");
    const sourceSummaryList = document.getElementById("sourceSummaryList");
    const comparisonTable = document.getElementById("comparisonTable");
    const waterComparisonChart = document.getElementById("waterComparisonChart");
    const turbidityComparisonChart = document.getElementById("turbidityComparisonChart");

    function showError(message) {
        analyticsError.textContent = message;
        analyticsError.style.display = "block";
    }

    function hideError() {
        analyticsError.style.display = "none";
    }

    function showLoading() {
        analyticsLoading.style.display = "block";
    }

    function hideLoading() {
        analyticsLoading.style.display = "none";
    }

    function getSelectedSources() {
        return Array.from(document.querySelectorAll('input[name="sourcePath"]:checked')).map(node => node.value);
    }

    function buildPayload() {
        return {
            database_paths: getSelectedSources(),
            limit: Number(limitInput.value || 240),
            bucket_minutes: Number(bucketMinutesInput.value || 5),
            alignment_mode: alignmentModeInput.value || "elapsed",
            start_timestamp_ms: startTimestampInput.value || null,
            end_timestamp_ms: endTimestampInput.value || null,
            reference: {
                enabled: referenceEnabled.checked,
                provider: "usgs_water_services",
                site: referenceSite.value.trim(),
                period: referencePeriod.value.trim() || "P7D",
            },
        };
    }

    async function loadSources() {
        try {
            const response = await fetch("/api/post-process/sources");
            const data = await response.json();
            if (data.error) {
                showError(data.error);
                return;
            }

            sourceList.innerHTML = "";
            (data.sources || []).forEach((source, index) => {
                const label = document.createElement("label");
                label.className = "source-option";
                label.innerHTML = `
                    <input type="checkbox" name="sourcePath" value="${source.path}" ${index === 0 ? "checked" : ""}>
                    <span class="source-name">${source.name}</span>
                    <span class="source-meta">${source.readings} readings</span>
                `;
                sourceList.appendChild(label);
            });
        } catch (error) {
            showError("Unable to load available databases: " + error.message);
        }
    }

    function renderSummaries(sources) {
        sourceSummaryList.innerHTML = "";
        if (!sources.length) {
            sourceSummaryList.appendChild(createAnalyticsEmptyState("No sources selected"));
            return;
        }

        sources.forEach(source => {
            const summary = source.summary || {};
            const card = document.createElement("article");
            card.className = "reading-card";
            card.innerHTML = `
                <div class="reading-topline">
                    <span>${source.name}</span>
                    <span>${summary.reading_count || 0} readings</span>
                </div>
                <div class="reading-stats">
                    <span>Flagged ${summary.flagged_count || 0}</span>
                    <span>Avg ambient ${formatValue(summary.avg_ambient_temp_c)} °C</span>
                    <span>Avg water ${formatValue(summary.avg_water_temp_c)} °C</span>
                    <span>Avg turbidity ${formatValue(summary.avg_turbidity_ntu)} NTU</span>
                    <span>Avg pH ${formatValue(summary.avg_ph)}</span>
                </div>
                <div class="reading-flags ${source.recent_flags && source.recent_flags.length ? "has-flags" : "no-flags"}">
                    ${source.recent_flags && source.recent_flags.length ? "Recent flagged readings present" : "No recent flagged readings"}
                </div>
            `;
            sourceSummaryList.appendChild(card);
        });
    }

    function renderComparisonTable(comparisons) {
        comparisonTable.innerHTML = "";
        if (!comparisons.length) {
            comparisonTable.appendChild(createAnalyticsEmptyState("No comparison data"));
            return;
        }

        comparisons.forEach(group => {
            const block = document.createElement("div");
            block.className = "comparison-block";

            const title = document.createElement("h3");
            title.textContent = `${group.label} vs ${group.baseline}`;
            block.appendChild(title);

            const table = document.createElement("table");
            table.className = "results-table";
            table.innerHTML = `
                <tr>
                    <th>Source</th>
                    <th>Window avg</th>
                    <th>Avg delta</th>
                    <th>Bucket avg delta</th>
                    <th>Peak abs delta</th>
                    <th>Aligned buckets</th>
                </tr>
            `;

            group.entries.forEach(entry => {
                const row = document.createElement("tr");
                row.innerHTML = `
                    <td>${entry.source}</td>
                    <td>${formatValue(entry.value)}</td>
                    <td>${entry.delta_vs_baseline === null ? "--" : formatValue(entry.delta_vs_baseline)}</td>
                    <td>${entry.avg_bucket_delta_vs_baseline === null ? "--" : formatValue(entry.avg_bucket_delta_vs_baseline)}</td>
                    <td>${entry.max_bucket_delta_vs_baseline === null ? "--" : formatValue(entry.max_bucket_delta_vs_baseline)}</td>
                    <td>${entry.aligned_point_count || 0}</td>
                `;
                table.appendChild(row);
            });

            block.appendChild(table);
            comparisonTable.appendChild(block);
        });
    }

    function renderAnalytics(analytics) {
        const combinedSummary = analytics.combined_summary || {};
        const sources = analytics.sources || [];
        sourceCount.textContent = String(combinedSummary.source_count || 0);
        windowReadingCount.textContent = String(combinedSummary.reading_count || 0);
        windowFlaggedCount.textContent = String(combinedSummary.flagged_count || 0);
        latestTimestamp.textContent = formatTimestamp(combinedSummary.latest_timestamp_ms);

        renderSummaries(sources);
        renderComparisonTable(analytics.comparisons || []);

        const waterSeries = sources.map(source => ({
            label: source.name,
            points: source.resampled_series.water_temp_c || [],
        }));
        const turbiditySeries = sources.map(source => ({
            label: source.name,
            points: source.resampled_series.turbidity_ntu || [],
        }));
        const referenceSeries = analytics.reference ? analytics.reference.points : null;

        renderMultiSeriesChart(waterComparisonChart, waterSeries, referenceSeries, "°C");
        renderMultiSeriesChart(turbidityComparisonChart, turbiditySeries, null, "NTU");
    }

    async function runAnalytics() {
        const payload = buildPayload();
        if (!payload.database_paths.length) {
            showError("Select at least one database to compare.");
            return;
        }

        hideError();
        showLoading();

        try {
            const response = await fetch("/api/post-process/analytics", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const data = await response.json();
            hideLoading();

            if (data.error) {
                showError(data.error);
                return;
            }

            renderAnalytics(data.analytics || {});
        } catch (error) {
            hideLoading();
            showError("Unable to build analytics: " + error.message);
        }
    }

    async function exportReport() {
        const payload = buildPayload();
        if (!payload.database_paths.length) {
            showError("Select at least one database to export.");
            return;
        }

        hideError();

        try {
            const response = await fetch("/api/post-process/export", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const data = await response.json();
            if (data.error) {
                showError(data.error);
                return;
            }

            const blob = new Blob([JSON.stringify(data.report, null, 2)], { type: "application/json" });
            const url = URL.createObjectURL(blob);
            const anchor = document.createElement("a");
            anchor.href = url;
            anchor.download = "aquametrics-postprocess-report.json";
            document.body.appendChild(anchor);
            anchor.click();
            anchor.remove();
            URL.revokeObjectURL(url);
        } catch (error) {
            showError("Unable to export report: " + error.message);
        }
    }

    loadSources().then(runAnalytics);
    runAnalyticsBtn.addEventListener("click", runAnalytics);
    exportReportBtn.addEventListener("click", exportReport);
});
