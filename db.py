"""
SQLite persistence for Aquametrics live sensor readings.
"""

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional


BASE_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = BASE_DIR
DB_PATH = BASE_DIR / "aquametrics.db"


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Open a SQLite connection with row access by column name."""
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db(db_path: Path = DB_PATH) -> None:
    """Create the readings table if it does not exist."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with get_connection(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sensor_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp_ms INTEGER NOT NULL,
                received_at_ms INTEGER NOT NULL,
                sensor_id TEXT NOT NULL DEFAULT '',
                ambient_temp_c REAL,
                water_temp_c REAL,
                turbidity_ntu REAL,
                ph REAL,
                flags_json TEXT NOT NULL DEFAULT '[]'
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_sensor_readings_timestamp
            ON sensor_readings(timestamp_ms DESC, id DESC)
            """
        )
        connection.commit()


def insert_reading(reading: Dict[str, Any], db_path: Path = DB_PATH) -> None:
    """Persist a single analyzed reading."""
    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO sensor_readings (
                timestamp_ms,
                received_at_ms,
                sensor_id,
                ambient_temp_c,
                water_temp_c,
                turbidity_ntu,
                ph,
                flags_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(reading.get("timestamp_ms", 0)),
                int(reading.get("received_at_ms", 0)),
                str(reading.get("sensor_id", "")),
                _as_optional_float(reading.get("ambient_temp_c")),
                _as_optional_float(reading.get("water_temp_c")),
                _as_optional_float(reading.get("turbidity_ntu")),
                _as_optional_float(reading.get("ph")),
                reading.get("flags_json", "[]"),
            ),
        )
        connection.commit()


def fetch_recent_readings(limit: int, db_path: Path = DB_PATH) -> List[Dict[str, Any]]:
    """Fetch the newest readings in ascending time order for charting."""
    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                timestamp_ms,
                received_at_ms,
                sensor_id,
                ambient_temp_c,
                water_temp_c,
                turbidity_ntu,
                ph,
                flags_json
            FROM sensor_readings
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [_row_to_reading(row) for row in reversed(rows)]


def fetch_readings(
    limit: int,
    db_path: Path = DB_PATH,
    start_timestamp_ms: Optional[int] = None,
    end_timestamp_ms: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Fetch readings from a database with optional time range filtering."""
    query = """
        SELECT
            id,
            timestamp_ms,
            received_at_ms,
            sensor_id,
            ambient_temp_c,
            water_temp_c,
            turbidity_ntu,
            ph,
            flags_json
        FROM sensor_readings
    """
    conditions = []
    params: List[Any] = []

    if start_timestamp_ms is not None:
        conditions.append("timestamp_ms >= ?")
        params.append(int(start_timestamp_ms))
    if end_timestamp_ms is not None:
        conditions.append("timestamp_ms <= ?")
        params.append(int(end_timestamp_ms))
    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY id DESC LIMIT ?"
    params.append(int(limit))

    with get_connection(db_path) as connection:
        rows = connection.execute(query, params).fetchall()

    return [_row_to_reading(row) for row in reversed(rows)]


def count_readings(db_path: Path = DB_PATH) -> int:
    """Return the total number of persisted readings."""
    with get_connection(db_path) as connection:
        row = connection.execute("SELECT COUNT(*) AS total FROM sensor_readings").fetchone()
    return int(row["total"]) if row else 0


def list_database_files(root_dir: Path = WORKSPACE_ROOT) -> List[Path]:
    """Discover SQLite database files within the workspace."""
    candidates = sorted(root_dir.rglob("*.db"))
    return [path for path in candidates if _has_sensor_readings_table(path)]


def resolve_database_paths(paths: List[str], root_dir: Path = WORKSPACE_ROOT) -> List[Path]:
    """Resolve API-supplied database paths and ensure they stay within the workspace."""
    resolved_paths: List[Path] = []
    for raw_path in paths:
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = (root_dir / path).resolve()
        else:
            path = path.resolve()

        if root_dir.resolve() not in path.parents and path != root_dir.resolve():
            raise ValueError(f"Database path is outside the workspace: {raw_path}")
        if not path.exists():
            raise ValueError(f"Database not found: {raw_path}")
        if not _has_sensor_readings_table(path):
            raise ValueError(f"Database is missing the sensor_readings table: {raw_path}")
        resolved_paths.append(path)

    return resolved_paths


def _row_to_reading(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "timestamp_ms": row["timestamp_ms"],
        "received_at_ms": row["received_at_ms"],
        "sensor_id": row["sensor_id"],
        "ambient_temp_c": row["ambient_temp_c"],
        "water_temp_c": row["water_temp_c"],
        "turbidity_ntu": row["turbidity_ntu"],
        "ph": row["ph"],
        "flags": json.loads(row["flags_json"]),
    }


def _as_optional_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    return float(value)


def _has_sensor_readings_table(db_path: Path) -> bool:
    try:
        with get_connection(db_path) as connection:
            row = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'sensor_readings'
                """
            ).fetchone()
        return row is not None
    except sqlite3.Error:
        return False
