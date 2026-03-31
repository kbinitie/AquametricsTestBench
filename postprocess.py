"""
Post-processing utilities for comparing persisted sensor archives.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from db import DB_PATH, count_readings, fetch_readings, list_database_files, resolve_database_paths


DEFAULT_ANALYTICS_LIMIT = 240
DEFAULT_BUCKET_MINUTES = 5
DEFAULT_ALIGNMENT_MODE = "elapsed"
USGS_PROVIDER = "usgs_water_services"
USGS_WATER_TEMP_PARAMETER = "00010"
SUPPORTED_ALIGNMENT_MODES = {"elapsed", "timestamp"}
METRIC_DEFINITIONS = [
    ("ambient_temp_c", "Ambient Temp", "°C"),
    ("water_temp_c", "Water Temp", "°C"),
    ("turbidity_ntu", "Turbidity", "NTU"),
    ("ph", "pH", ""),
]


@dataclass
class SourceBundle:
    name: str
    path: Path
    readings: List[Dict[str, Any]]


def list_sources() -> List[Dict[str, Any]]:
    """Return discovered database sources for the post-processing dashboard."""
    sources = []
    for path in list_database_files():
        sources.append({
            "name": path.stem,
            "path": str(path),
            "readings": count_readings(path),
            "is_default": path == DB_PATH,
        })
    return sources


def build_postprocess_payload(
    database_paths: Optional[List[str]] = None,
    limit: int = DEFAULT_ANALYTICS_LIMIT,
    start_timestamp_ms: Optional[int] = None,
    end_timestamp_ms: Optional[int] = None,
    reference_config: Optional[Dict[str, Any]] = None,
    bucket_minutes: int = DEFAULT_BUCKET_MINUTES,
    alignment_mode: str = DEFAULT_ALIGNMENT_MODE,
) -> Dict[str, Any]:
    """Build the analytics response payload for the post-processing dashboard."""
    selected_paths = resolve_database_paths(database_paths or [str(DB_PATH)])
    alignment_mode = _normalize_alignment_mode(alignment_mode)
    bucket_minutes = _normalize_bucket_minutes(bucket_minutes)

    bundles = _load_sources(selected_paths, limit, start_timestamp_ms, end_timestamp_ms)
    reference = fetch_reference_series(reference_config) if reference_config else None
    serialized_sources = [
        _serialize_source(bundle, bucket_minutes=bucket_minutes, alignment_mode=alignment_mode)
        for bundle in bundles
    ]

    return {
        "sources": serialized_sources,
        "combined_summary": _build_combined_summary(bundles),
        "comparisons": _build_comparisons(serialized_sources),
        "reference": reference,
        "analysis_config": {
            "bucket_minutes": bucket_minutes,
            "alignment_mode": alignment_mode,
        },
    }


def export_postprocess_report(
    database_paths: Optional[List[str]] = None,
    limit: int = DEFAULT_ANALYTICS_LIMIT,
    start_timestamp_ms: Optional[int] = None,
    end_timestamp_ms: Optional[int] = None,
    reference_config: Optional[Dict[str, Any]] = None,
    bucket_minutes: int = DEFAULT_BUCKET_MINUTES,
    alignment_mode: str = DEFAULT_ALIGNMENT_MODE,
) -> Dict[str, Any]:
    """Build a report-shaped JSON payload for export."""
    analytics = build_postprocess_payload(
        database_paths=database_paths,
        limit=limit,
        start_timestamp_ms=start_timestamp_ms,
        end_timestamp_ms=end_timestamp_ms,
        reference_config=reference_config,
        bucket_minutes=bucket_minutes,
        alignment_mode=alignment_mode,
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "report_type": "aquametrics_postprocess_report",
        "analytics": analytics,
    }


def fetch_reference_series(reference_config: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch a public reference series. Currently supports USGS water temperature."""
    provider = (reference_config.get("provider") or USGS_PROVIDER).strip()
    if provider != USGS_PROVIDER:
        raise ValueError(f"Unsupported reference provider: {provider}")

    site = str(reference_config.get("site") or "").strip()
    if not site:
        raise ValueError("Reference site is required for USGS data.")

    period = str(reference_config.get("period") or "P7D").strip()
    points = _fetch_usgs_water_temperature(site=site, period=period)
    return {
        "provider": USGS_PROVIDER,
        "metric": "water_temp_c",
        "label": f"USGS site {site}",
        "site": site,
        "period": period,
        "points": points,
    }


def _load_sources(
    paths: List[Path],
    limit: int,
    start_timestamp_ms: Optional[int],
    end_timestamp_ms: Optional[int],
) -> List[SourceBundle]:
    bundles = []
    for path in paths:
        bundles.append(SourceBundle(
            name=path.stem,
            path=path,
            readings=fetch_readings(
                limit=limit,
                db_path=path,
                start_timestamp_ms=start_timestamp_ms,
                end_timestamp_ms=end_timestamp_ms,
            ),
        ))
    return bundles


def _serialize_source(bundle: SourceBundle, bucket_minutes: int, alignment_mode: str) -> Dict[str, Any]:
    readings = bundle.readings
    bucket_ms = bucket_minutes * 60 * 1000
    return {
        "name": bundle.name,
        "path": str(bundle.path),
        "summary": _build_source_summary(readings),
        "series": {
            metric_key: _series_for_metric(readings, metric_key)
            for metric_key, _, _ in METRIC_DEFINITIONS
        },
        "resampled_series": {
            metric_key: _resample_metric_series(
                readings=readings,
                metric_key=metric_key,
                bucket_ms=bucket_ms,
                alignment_mode=alignment_mode,
            )
            for metric_key, _, _ in METRIC_DEFINITIONS
        },
        "recent_flags": [reading for reading in readings if reading.get("flags")][-8:],
    }


def _build_source_summary(readings: List[Dict[str, Any]]) -> Dict[str, Any]:
    latest = readings[-1] if readings else None
    return {
        "reading_count": len(readings),
        "flagged_count": sum(1 for row in readings if row.get("flags")),
        "latest_timestamp_ms": latest.get("timestamp_ms") if latest else None,
        "avg_ambient_temp_c": _average_metric(readings, "ambient_temp_c"),
        "avg_water_temp_c": _average_metric(readings, "water_temp_c"),
        "avg_turbidity_ntu": _average_metric(readings, "turbidity_ntu"),
        "avg_ph": _average_metric(readings, "ph"),
    }


def _build_combined_summary(bundles: List[SourceBundle]) -> Dict[str, Any]:
    all_readings = [reading for bundle in bundles for reading in bundle.readings]
    latest = max(all_readings, key=lambda item: item.get("timestamp_ms", 0), default=None)
    return {
        "source_count": len(bundles),
        "reading_count": len(all_readings),
        "flagged_count": sum(1 for row in all_readings if row.get("flags")),
        "latest_timestamp_ms": latest.get("timestamp_ms") if latest else None,
    }


def _build_comparisons(serialized_sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not serialized_sources:
        return []

    baseline = serialized_sources[0]
    comparison_rows = []
    metric_summary_keys = {
        "ambient_temp_c": "avg_ambient_temp_c",
        "water_temp_c": "avg_water_temp_c",
        "turbidity_ntu": "avg_turbidity_ntu",
        "ph": "avg_ph",
    }

    for metric_key, label, unit in METRIC_DEFINITIONS:
        baseline_summary = baseline.get("summary", {})
        baseline_value = baseline_summary.get(metric_summary_keys[metric_key])
        baseline_series = baseline.get("resampled_series", {}).get(metric_key, [])
        entries = []

        for source in serialized_sources:
            summary = source.get("summary", {})
            source_series = source.get("resampled_series", {}).get(metric_key, [])
            value = summary.get(metric_summary_keys[metric_key])
            alignment = _build_alignment_stats(baseline_series, source_series)
            entries.append({
                "source": source.get("name"),
                "value": value,
                "delta_vs_baseline": None if value is None or baseline_value is None else value - baseline_value,
                "avg_bucket_delta_vs_baseline": alignment["avg_delta"],
                "max_bucket_delta_vs_baseline": alignment["max_abs_delta"],
                "aligned_point_count": alignment["point_count"],
            })

        comparison_rows.append({
            "metric": metric_key,
            "label": label,
            "unit": unit,
            "baseline": baseline.get("name"),
            "entries": entries,
        })

    return comparison_rows


def _build_alignment_stats(
    baseline_series: List[Dict[str, Any]],
    source_series: List[Dict[str, Any]],
) -> Dict[str, Optional[float]]:
    if not baseline_series or not source_series:
        return {"avg_delta": None, "max_abs_delta": None, "point_count": 0}

    baseline_index = {point["bucket_start_ms"]: point["value"] for point in baseline_series}
    deltas = []
    for point in source_series:
        bucket_key = point["bucket_start_ms"]
        if bucket_key not in baseline_index:
            continue
        deltas.append(point["value"] - baseline_index[bucket_key])

    if not deltas:
        return {"avg_delta": None, "max_abs_delta": None, "point_count": 0}

    return {
        "avg_delta": mean(deltas),
        "max_abs_delta": max(abs(delta) for delta in deltas),
        "point_count": len(deltas),
    }


def _average_metric(readings: List[Dict[str, Any]], key: str) -> Optional[float]:
    values = [float(reading[key]) for reading in readings if reading.get(key) not in (None, "")]
    return mean(values) if values else None


def _series_for_metric(readings: List[Dict[str, Any]], key: str) -> List[Dict[str, Any]]:
    series = []
    for reading in readings:
        value = reading.get(key)
        if value in (None, ""):
            continue
        series.append({
            "timestamp_ms": reading.get("timestamp_ms"),
            "value": float(value),
            "flags": reading.get("flags", []),
        })
    return series


def _resample_metric_series(
    readings: List[Dict[str, Any]],
    metric_key: str,
    bucket_ms: int,
    alignment_mode: str,
) -> List[Dict[str, Any]]:
    if not readings:
        return []

    first_timestamp_ms = readings[0].get("timestamp_ms") or 0
    buckets: Dict[int, Dict[str, Any]] = {}

    for reading in readings:
        raw_value = reading.get(metric_key)
        timestamp_ms = reading.get("timestamp_ms")
        if raw_value in (None, "") or timestamp_ms in (None, ""):
            continue

        timestamp_ms = int(timestamp_ms)
        value = float(raw_value)
        bucket_key = _bucket_key_for_timestamp(
            timestamp_ms=timestamp_ms,
            first_timestamp_ms=first_timestamp_ms,
            bucket_ms=bucket_ms,
            alignment_mode=alignment_mode,
        )
        bucket = buckets.setdefault(bucket_key, {
            "bucket_start_ms": bucket_key,
            "bucket_label": _bucket_label(bucket_key, alignment_mode),
            "values": [],
            "flag_count": 0,
        })
        bucket["values"].append(value)
        if reading.get("flags"):
            bucket["flag_count"] += 1

    return [
        {
            "bucket_start_ms": bucket_key,
            "bucket_label": bucket["bucket_label"],
            "value": mean(bucket["values"]),
            "sample_count": len(bucket["values"]),
            "flag_count": bucket["flag_count"],
        }
        for bucket_key, bucket in sorted(buckets.items())
    ]


def _bucket_key_for_timestamp(
    timestamp_ms: int,
    first_timestamp_ms: int,
    bucket_ms: int,
    alignment_mode: str,
) -> int:
    if alignment_mode == "elapsed":
        elapsed_ms = max(0, timestamp_ms - int(first_timestamp_ms))
        return (elapsed_ms // bucket_ms) * bucket_ms
    return (timestamp_ms // bucket_ms) * bucket_ms


def _bucket_label(bucket_start_ms: int, alignment_mode: str) -> str:
    if alignment_mode == "elapsed":
        total_seconds = bucket_start_ms // 1000
        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return f"+{hours:02d}:{minutes:02d}:{seconds:02d}"
    return str(bucket_start_ms)


def _normalize_bucket_minutes(bucket_minutes: int) -> int:
    bucket_minutes = int(bucket_minutes)
    if bucket_minutes < 1 or bucket_minutes > 1440:
        raise ValueError("Bucket minutes must be between 1 and 1440.")
    return bucket_minutes


def _normalize_alignment_mode(alignment_mode: str) -> str:
    alignment_mode = str(alignment_mode or DEFAULT_ALIGNMENT_MODE).strip().lower()
    if alignment_mode not in SUPPORTED_ALIGNMENT_MODES:
        raise ValueError(f"Unsupported alignment mode: {alignment_mode}")
    return alignment_mode


def _fetch_usgs_water_temperature(site: str, period: str) -> List[Dict[str, Any]]:
    query = urlencode({
        "format": "json",
        "sites": site,
        "parameterCd": USGS_WATER_TEMP_PARAMETER,
        "period": period,
    })
    url = f"https://waterservices.usgs.gov/nwis/iv/?{query}"

    try:
        with urlopen(url, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise ValueError(f"USGS reference request failed with HTTP {exc.code}.") from exc
    except URLError as exc:
        raise ValueError(f"Unable to reach USGS reference service: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("USGS reference service returned invalid JSON.") from exc

    time_series = payload.get("value", {}).get("timeSeries", [])
    if not time_series:
        return []

    points = []
    for series in time_series:
        for values_group in series.get("values", []):
            for item in values_group.get("value", []):
                raw_value = item.get("value")
                if raw_value in (None, ""):
                    continue
                timestamp = item.get("dateTime", "")
                points.append({
                    "timestamp": timestamp,
                    "value": float(raw_value),
                })
    return points
