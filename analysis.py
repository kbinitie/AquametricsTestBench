import csv
import io
from typing import List, Dict, Any

# Simple thresholds for flagging issues
LOW_LEVEL_THRESHOLD = 20.0        # cm
HIGH_LEVEL_THRESHOLD = 200.0      # cm
HIGH_TURBIDITY_THRESHOLD = 5.0    # NTU
PH_MIN = 6.5
PH_MAX = 8.5
TEMP_MIN = 0.0                    # °C
TEMP_MAX = 35.0                   # °C


def _to_float(value, field_name: str):
    """Safely convert a value to float. Raise a ValueError with context if it fails."""
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid numeric value for {field_name}: {value!r}")


def analyze_readings(file_obj) -> List[Dict[str, Any]]:
    """
    Analyze water sensor readings from a CSV file-like object.

    Expected columns:
      - timestamp
      - sensor_id
      - water_level_cm
      - turbidity_ntu
      - ph
      - temperature_c

    `file_obj` can be a Werkzeug FileStorage (from Flask) or any file-like with .read()/.readline().
    Returns a list of dicts with the original data plus a 'flags' list.
    """
    # If we get a Flask FileStorage object, use its underlying stream
    stream = getattr(file_obj, "stream", file_obj)

    # Ensure we start from the beginning
    try:
        stream.seek(0)
    except (AttributeError, OSError):
        # If we can't seek, wrap in a buffer
        stream = io.BytesIO(stream.read())
        stream.seek(0)

    # Wrap bytes stream in a text wrapper if needed
    if isinstance(stream.read(0), bytes):  # type: ignore[arg-type]
        stream.seek(0)
        text_stream = io.TextIOWrapper(stream, encoding="utf-8", newline="")
    else:
        stream.seek(0)
        text_stream = stream

    reader = csv.DictReader(text_stream)

    required_columns = [
        "timestamp",
        "sensor_id",
        "water_level_cm",
        "turbidity_ntu",
        "ph",
        "temperature_c",
    ]

    # Make sure all required columns exist
    if reader.fieldnames is None:
        raise ValueError("CSV has no header row.")
    missing = [col for col in required_columns if col not in reader.fieldnames]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    results: List[Dict[str, Any]] = []

    for row in reader:
        flags = []

        # Parse numeric fields with validation
        try:
            water_level = _to_float(row.get("water_level_cm"), "water_level_cm")
            turbidity = _to_float(row.get("turbidity_ntu"), "turbidity_ntu")
            ph = _to_float(row.get("ph"), "ph")
            temperature = _to_float(row.get("temperature_c"), "temperature_c")
        except ValueError as e:
            # If a row is bad, we can either skip it or mark it as invalid.
            # Here we mark it with a flag and keep it.
            flags.append(f"INVALID_ROW: {e}")
            water_level = turbidity = ph = temperature = None  # type: ignore[assignment]

        # Apply flag rules only if we got valid numbers
        if water_level is not None:
            if water_level < LOW_LEVEL_THRESHOLD:
                flags.append("LOW_LEVEL")
            if water_level > HIGH_LEVEL_THRESHOLD:
                flags.append("OVERFLOW_RISK")

        if turbidity is not None and turbidity > HIGH_TURBIDITY_THRESHOLD:
            flags.append("HIGH_TURBIDITY")

        if ph is not None and (ph < PH_MIN or ph > PH_MAX):
            flags.append("PH_OUT_OF_RANGE")

        if temperature is not None:
            if temperature < TEMP_MIN or temperature > TEMP_MAX:
                flags.append("TEMP_OUT_OF_RANGE")

        result_row = {
            "timestamp": row.get("timestamp", ""),
            "sensor_id": row.get("sensor_id", ""),
            "water_level_cm": row.get("water_level_cm", ""),
            "turbidity_ntu": row.get("turbidity_ntu", ""),
            "ph": row.get("ph", ""),
            "temperature_c": row.get("temperature_c", ""),
            "flags": flags,
        }

        results.append(result_row)

    return results
