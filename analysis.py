import io
import json
from typing import List, Dict, Any

HIGH_TURBIDITY_THRESHOLD = 5.0    # NTU
PH_MIN = 6.5
PH_MAX = 8.5
TEMP_MIN = 0.0                    # °C
TEMP_MAX = 35.0                   # °C
REQUIRED_SENSOR_FIELDS = [
    "timestamp_ms",
    "ambient_temp_c",
    "water_temp_c",
    "turbidity_ntu",
    "ph",
]


def _to_float(value, field_name: str):
    """Safely convert a value to float. Raise a ValueError with context if it fails."""
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid numeric value for {field_name}: {value!r}")


def _coerce_json_payload(text: str) -> List[Dict[str, Any]]:
    """
    Parse supported JSON upload formats into a list of reading dicts.

    Supported formats:
    - a single JSON object
    - a JSON array of objects
    - newline-delimited JSON (one object per line)
    """
    stripped = text.strip()
    if not stripped:
        raise ValueError("JSON file is empty.")

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        readings: List[Dict[str, Any]] = []
        for line_number, line in enumerate(stripped.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number}: {exc.msg}") from exc
            if not isinstance(item, dict):
                raise ValueError(f"Each JSON reading must be an object. Line {line_number} was {type(item).__name__}.")
            readings.append(item)
        if not readings:
            raise ValueError("JSON file is empty.")
        return readings

    if isinstance(parsed, dict):
        return [parsed]
    if isinstance(parsed, list):
        if not all(isinstance(item, dict) for item in parsed):
            raise ValueError("JSON array must contain only objects.")
        return parsed

    raise ValueError("JSON upload must be an object, an array of objects, or NDJSON.")


def analyze_payload(payload: Any) -> List[Dict[str, Any]]:
    """Analyze one or more sensor readings already loaded in memory."""
    readings = payload if isinstance(payload, list) else [payload]
    results: List[Dict[str, Any]] = []

    for index, row in enumerate(readings, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"Reading {index} is not a JSON object.")

        flags = []
        missing = [col for col in REQUIRED_SENSOR_FIELDS if col not in row]
        if missing:
            flags.append(f"INVALID_READING: Missing required fields: {', '.join(missing)}")
            ambient_temp = water_temp = turbidity = ph = None  # type: ignore[assignment]
        else:
            try:
                ambient_temp = _to_float(row.get("ambient_temp_c"), "ambient_temp_c")
                water_temp = _to_float(row.get("water_temp_c"), "water_temp_c")
                turbidity = _to_float(row.get("turbidity_ntu"), "turbidity_ntu")
                ph = _to_float(row.get("ph"), "ph")
            except ValueError as e:
                flags.append(f"INVALID_READING: {e}")
                ambient_temp = water_temp = turbidity = ph = None  # type: ignore[assignment]

        if turbidity is not None and turbidity > HIGH_TURBIDITY_THRESHOLD:
            flags.append("HIGH_TURBIDITY")

        if ph is not None and (ph < PH_MIN or ph > PH_MAX):
            flags.append("PH_OUT_OF_RANGE")

        if ambient_temp is not None and (ambient_temp < TEMP_MIN or ambient_temp > TEMP_MAX):
            flags.append("AMBIENT_TEMP_OUT_OF_RANGE")

        if water_temp is not None and (water_temp < TEMP_MIN or water_temp > TEMP_MAX):
            flags.append("WATER_TEMP_OUT_OF_RANGE")

        results.append({
            "timestamp_ms": row.get("timestamp_ms", ""),
            "sensor_id": row.get("sensor_id", ""),
            "ambient_temp_c": row.get("ambient_temp_c", ""),
            "water_temp_c": row.get("water_temp_c", ""),
            "turbidity_ntu": row.get("turbidity_ntu", ""),
            "ph": row.get("ph", ""),
            "flags": flags,
        })

    return results


def analyze_readings(file_obj) -> List[Dict[str, Any]]:
    """
    Analyze sensor readings from a JSON file-like object.

    `file_obj` can be a Werkzeug FileStorage (from Flask) or any file-like with .read()/.readline().
    Returns a list of dicts with the original data plus a 'flags' list.
    """
    stream = getattr(file_obj, "stream", file_obj)

    try:
        stream.seek(0)
    except (AttributeError, OSError):
        stream = io.BytesIO(stream.read())
        stream.seek(0)

    if isinstance(stream.read(0), bytes):  # type: ignore[arg-type]
        stream.seek(0)
        text_stream = io.TextIOWrapper(stream, encoding="utf-8", newline="")
    else:
        stream.seek(0)
        text_stream = stream

    readings = _coerce_json_payload(text_stream.read())
    return analyze_payload(readings)
