"""
src/database.py — Zero-Dependency Embedded SQLite Database Layer for ARGUS.

Thread-safe, high-concurrency embedded SQLite storage located at data/app.db.
Persists:
  - Deduplicated Road Potholes & Craters (severity, GPS, IRC classification, SLA)
  - Traffic Safety Violations & Infrastructure Deficiencies (rash driving, speed, dividers, zebra)
  - MoRTH ANPR Recognized License Plates (plate text, vehicle category, confidence)
  - Real-Time Traffic Density & Congestion Metrics (counts, congestion index, classification)
  - Official PWD Civil Maintenance Work Orders (dockets, repair cost, materials)
  - Surveillance Audit Mission Runs (telemetry summaries, peak density, total budgets)
"""

import os
import sqlite3
import logging
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "app.db"))


def get_db_connection() -> sqlite3.Connection:
    """Create a thread-safe connection to the SQLite database with WAL mode."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_db():
    """Initialize database tables, indexes, and initial configuration."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Potholes & Surface Distress Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS potholes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        incident_id TEXT UNIQUE,
        frame_id INTEGER,
        timestamp_sec REAL,
        latitude REAL,
        longitude REAL,
        street_name TEXT,
        formatted_address TEXT,
        severity TEXT,
        confidence REAL,
        area_ratio REAL,
        is_school_zone BOOLEAN DEFAULT 0,
        is_hospital_zone BOOLEAN DEFAULT 0,
        evidence_image TEXT,
        irc_code TEXT DEFAULT 'IRC:82-2015',
        repair_cost_inr INTEGER DEFAULT 1650,
        sla_hours INTEGER DEFAULT 48,
        status TEXT DEFAULT 'REPORTED',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. Safety Rule Violations & Infrastructure Defects Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS violations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        incident_id TEXT,
        frame_id INTEGER,
        timestamp_sec REAL,
        latitude REAL,
        longitude REAL,
        street_name TEXT,
        formatted_address TEXT,
        violation_type TEXT,
        severity TEXT,
        description TEXT,
        plate_text TEXT,
        confidence REAL,
        is_school_zone BOOLEAN DEFAULT 0,
        evidence_image TEXT,
        repair_action TEXT,
        estimated_cost_inr INTEGER DEFAULT 0,
        status TEXT DEFAULT 'FLAGGED',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 3. MoRTH ANPR License Plates Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS plates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        track_id INTEGER,
        plate_text TEXT,
        vehicle_type TEXT DEFAULT 'Car',
        confidence REAL,
        frame_id INTEGER,
        timestamp_sec REAL,
        latitude REAL,
        longitude REAL,
        street_name TEXT,
        is_violator BOOLEAN DEFAULT 0,
        violation_details TEXT,
        evidence_image TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 4. Traffic Flow & Corridor Congestion Metrics
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS traffic_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        frame_id INTEGER,
        timestamp_sec REAL,
        corridor_id TEXT DEFAULT 'bus1',
        total_vehicles INTEGER DEFAULT 0,
        pedestrians INTEGER DEFAULT 0,
        cars INTEGER DEFAULT 0,
        motorcycles INTEGER DEFAULT 0,
        buses INTEGER DEFAULT 0,
        trucks INTEGER DEFAULT 0,
        congestion_index INTEGER DEFAULT 0,
        congestion_label TEXT DEFAULT 'FREE FLOW',
        street_name TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 5. Autonomous PWD Civil Work-Orders Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pwd_work_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id TEXT UNIQUE,
        docket_id TEXT,
        defect_type TEXT,
        severity TEXT,
        irc_code TEXT,
        location TEXT,
        gps TEXT,
        repair_action TEXT,
        material_spec TEXT,
        estimated_budget_inr REAL,
        sla_target TEXT,
        dispatch_status TEXT DEFAULT 'AUTO_DISPATCHED',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 6. Surveillance Mission Audit Runs Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        corridor_id TEXT,
        video_source TEXT,
        total_frames INTEGER,
        total_potholes INTEGER,
        p1_critical_count INTEGER,
        total_plates INTEGER,
        total_violators INTEGER,
        total_vehicles INTEGER,
        total_pedestrians INTEGER,
        peak_congestion INTEGER,
        avg_congestion INTEGER,
        pwd_budget_inr REAL,
        total_pwd_orders INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Create Indexes for lightning fast queries and lookups
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_potholes_sev ON potholes(severity);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_potholes_loc ON potholes(street_name);")
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_violations_incident_id ON violations(incident_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_violations_type ON violations(violation_type);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_violations_sev ON violations(severity);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_plates_text ON plates(plate_text);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_plates_track ON plates(track_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_time ON traffic_metrics(timestamp_sec);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pwd_order ON pwd_work_orders(order_id);")

    conn.commit()
    conn.close()
    logger.info("ARGUS Embedded SQLite database initialized successfully at: %s", DB_PATH)


# ─── INSERTION OPERATIONS ─────────────────────────────────────────────────────

def _parse_float(val: Any, default: float = 0.0) -> float:
    """Robustly parse float from string, int, or float, handling 's', '%', etc."""
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        cleaned = val.replace("s", "").replace("%", "").strip()
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return default
    return default


def insert_pothole(data: Dict[str, Any]) -> int:
    """Insert or update a detected pothole defect."""
    conn = get_db_connection()
    cursor = conn.cursor()
    inc_id = data.get("id") or data.get("incident_id") or f"POT-{int(_parse_float(data.get('timestamp_sec') or data.get('time_sec'))*1000)}"

    sev_str = str(data.get("severity", "P3 - MEDIUM")).upper()
    if "CRITICAL" in sev_str or "P1" in sev_str or "SEVERE" in sev_str:
        sla = 24
        cost = 3800
        irc = "IRC:82-2015 (Volumetric Crater)"
    elif "HIGH" in sev_str or "P2" in sev_str or "WARNING" in sev_str:
        sla = 48
        cost = 1650
        irc = "IRC:82-2015 (High Severity)"
    else:
        sla = 72
        cost = 850
        irc = "IRC:SP:77-2008 (Minor Raveling)"

    conf = _parse_float(data.get("confidence"), 0.85)
    if "%" in str(data.get("confidence", "")) or conf > 1.0:
        conf /= 100.0

    cursor.execute("""
    INSERT INTO potholes (
        incident_id, frame_id, timestamp_sec, latitude, longitude,
        street_name, formatted_address, severity, confidence, area_ratio,
        is_school_zone, is_hospital_zone, evidence_image, irc_code,
        repair_cost_inr, sla_hours, status
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(incident_id) DO UPDATE SET
        severity=excluded.severity,
        confidence=MAX(potholes.confidence, excluded.confidence),
        status=excluded.status
    """, (
        inc_id,
        data.get("frame_id", 0),
        data.get("timestamp_sec", data.get("time_sec", 0.0)),
        data.get("latitude", data.get("lat", 13.0350)),
        data.get("longitude", data.get("lon", 80.1542)),
        data.get("street_name", data.get("location", "Anna Salai Corridor")),
        data.get("formatted_address", data.get("location", "Anna Salai Corridor, Chennai")),
        data.get("severity", "P2 - HIGH"),
        conf,
        data.get("area_ratio", 0.02),
        1 if data.get("is_school_zone") else 0,
        1 if data.get("is_hospital_zone") else 0,
        data.get("evidence_image", ""),
        irc,
        cost,
        sla,
        data.get("status", "REPORTED")
    ))
    row_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return row_id


def insert_violation(data: Dict[str, Any]) -> int:
    """Upsert a traffic violation or road infrastructure deficiency."""
    conn = get_db_connection()
    cursor = conn.cursor()
    ts_val = _parse_float(data.get("timestamp_sec") or data.get("time_sec"), 0.0)
    inc_id = data.get("id") or data.get("incident_id") or f"VIOL-{int(ts_val*1000)}"

    conf = _parse_float(data.get("confidence"), 0.85)
    if "%" in str(data.get("confidence", "")) or conf > 1.0:
        conf /= 100.0

    v_type = data.get("type") or data.get("violation_type", "SAFETY_VIOLATION")

    cursor.execute("""
    INSERT OR REPLACE INTO violations (
        incident_id, frame_id, timestamp_sec, latitude, longitude,
        street_name, formatted_address, violation_type, severity,
        description, plate_text, confidence, is_school_zone,
        evidence_image, repair_action, estimated_cost_inr, status
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        inc_id,
        data.get("frame_id", 0),
        ts_val,
        data.get("latitude", data.get("lat", 13.0350)),
        data.get("longitude", data.get("lon", 80.1542)),
        data.get("street_name", data.get("location", "Anna Salai Corridor")),
        data.get("formatted_address", data.get("location", "Anna Salai Corridor, Chennai")),
        v_type,
        data.get("severity", "WARNING"),
        data.get("description") or data.get("title", "Safety Rule Violation"),
        data.get("plate_text", data.get("plate", "")),
        conf,
        1 if data.get("is_school_zone") else 0,
        data.get("evidence_image", ""),
        data.get("repair_action", ""),
        data.get("estimated_cost_inr", 0),
        data.get("status", "FLAGGED")
    ))
    row_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return row_id


def insert_plate(data: Dict[str, Any]) -> int:
    """Insert a recognized vehicle license plate."""
    conn = get_db_connection()
    cursor = conn.cursor()

    plate_text = str(data.get("plate_text") or data.get("plate") or "").strip().upper()
    if not plate_text or "UNSCANNED" in plate_text or "NOT SCANNED" in plate_text:
        conn.close()
        return 0

    conf = _parse_float(data.get("confidence"), 0.90)
    if "%" in str(data.get("confidence", "")) or conf > 1.0:
        conf /= 100.0

    ts_val = _parse_float(data.get("timestamp_sec") or data.get("time_sec"), 0.0)

    # Avoid inserting redundant exact duplicate within 3 seconds
    cursor.execute("""
    SELECT id FROM plates 
    WHERE plate_text = ? AND ABS(timestamp_sec - ?) < 3.0
    LIMIT 1;
    """, (plate_text, ts_val))
    existing = cursor.fetchone()
    if existing:
        conn.close()
        return existing[0]

    cursor.execute("""
    INSERT INTO plates (
        track_id, plate_text, vehicle_type, confidence, frame_id,
        timestamp_sec, latitude, longitude, street_name, is_violator,
        violation_details, evidence_image
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("track_id", 0),
        plate_text,
        data.get("vehicle_type", "Car"),
        conf,
        data.get("frame_id", 0),
        ts_val,
        data.get("latitude", data.get("lat", 13.0350)),
        data.get("longitude", data.get("lon", 80.1542)),
        data.get("street_name", data.get("location", "Anna Salai Corridor")),
        1 if data.get("is_violator") else 0,
        data.get("violation_details", data.get("violation", "")),
        data.get("evidence_image", "")
    ))
    row_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return row_id


def insert_traffic_metric(data: Dict[str, Any]) -> int:
    """Insert real-time traffic volume and corridor congestion metrics."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO traffic_metrics (
        frame_id, timestamp_sec, corridor_id, total_vehicles, pedestrians,
        cars, motorcycles, buses, trucks, congestion_index,
        congestion_label, street_name
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("frame_id", 0),
        data.get("timestamp_sec", 0.0),
        data.get("corridor_id", "bus1"),
        data.get("total_vehicles", 0),
        data.get("pedestrians", 0),
        data.get("cars", 0),
        data.get("motorcycles", 0),
        data.get("buses", 0),
        data.get("trucks", 0),
        data.get("congestion_index", 0),
        data.get("congestion_label", "FREE FLOW"),
        data.get("street_name", data.get("street", "Corridor Sector"))
    ))
    row_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return row_id


def insert_pwd_work_order(data: Dict[str, Any]) -> int:
    """Insert or update an official PWD Civil Work Order."""
    conn = get_db_connection()
    cursor = conn.cursor()
    order_id = data.get("order_id") or data.get("Order ID") or f"PWD-{int(data.get('estimated_budget_inr', 1000))}"

    cursor.execute("""
    INSERT INTO pwd_work_orders (
        order_id, docket_id, defect_type, severity, irc_code,
        location, gps, repair_action, material_spec, estimated_budget_inr,
        sla_target, dispatch_status
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(order_id) DO UPDATE SET
        dispatch_status=excluded.dispatch_status
    """, (
        order_id,
        data.get("docket_id", "DOCKET-AUTOGEN"),
        data.get("defect_type", data.get("Defect Type", "Pothole")),
        data.get("severity", data.get("Severity", "P2 - HIGH")),
        data.get("irc_code", data.get("IRC Code", "IRC:82-2015")),
        data.get("location", data.get("Location", "Corridor")),
        data.get("gps", data.get("Corridor GPS Pinpoint", "13.0350, 80.1542")),
        data.get("repair_action", data.get("Repair Action (IRC Spec)", "Surface Infill")),
        data.get("material_spec", data.get("Material Spec", "Cold-mix Asphalt")),
        data.get("estimated_budget_inr", data.get("Est. Budget (INR)", 1650)),
        data.get("sla_target", data.get("SLA Resolution", "48 Hours")),
        data.get("dispatch_status", "AUTO_DISPATCHED")
    ))
    row_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return row_id


def insert_audit_run(summary: Dict[str, Any], corridor_id: str = "bus1", video_source: str = "") -> int:
    """Insert summary metrics for an entire surveillance audit run."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO audit_runs (
        corridor_id, video_source, total_frames, total_potholes,
        p1_critical_count, total_plates, total_violators, total_vehicles,
        total_pedestrians, peak_congestion, avg_congestion,
        pwd_budget_inr, total_pwd_orders
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        corridor_id,
        video_source,
        summary.get("total_frames", summary.get("frames_processed", 0)),
        summary.get("total_potholes", 0),
        summary.get("p1_critical_potholes", 0),
        summary.get("unique_plates", 0),
        summary.get("unique_violators", 0),
        summary.get("total_vehicles", 0),
        summary.get("total_pedestrians_tracked", summary.get("pedestrians", 0)),
        summary.get("peak_congestion_index", 0),
        summary.get("avg_congestion_index", 0),
        summary.get("total_pwd_budget_inr", 0.0),
        summary.get("total_pwd_orders", 0)
    ))
    row_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return row_id


def sync_all_incidents(incidents: List[Dict[str, Any]], summary: Optional[Dict[str, Any]] = None, corridor_id: str = "bus1"):
    """
    Batch synchronizes in-memory detection incidents from a video run into SQLite.
    Guarantees that every detection is committed and persistent on disk.
    """
    if not incidents and not summary:
        return

    init_db()
    for inc in incidents:
        t = str(inc.get("type", "")).upper()
        if "POTHOLE" in t:
            insert_pothole(inc)
        elif "PLATE" in t:
            insert_plate(inc)
        else:
            insert_violation(inc)

    if summary:
        insert_audit_run(summary, corridor_id=corridor_id)


# ─── QUERY OPERATIONS ─────────────────────────────────────────────────────────

def get_database_stats() -> Dict[str, Any]:
    """Retrieve record counts, disk footprint, and table metadata."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    counts = {}
    table_names = ["potholes", "violations", "plates", "traffic_metrics", "pwd_work_orders", "audit_runs"]
    for t in table_names:
        cursor.execute(f"SELECT COUNT(*) FROM {t};")
        counts[t] = cursor.fetchone()[0]

    # Database file size
    size_bytes = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
    size_kb = round(size_bytes / 1024.0, 1)

    # Last active timestamp
    cursor.execute("SELECT MAX(created_at) FROM potholes;")
    last_pothole = cursor.fetchone()[0]

    conn.close()
    return {
        "db_path": DB_PATH,
        "size_kb": size_kb,
        "counts": counts,
        "total_records": sum(counts.values()),
        "last_updated": last_pothole or "Active Session"
    }


def get_table_data(table_name: str, limit: int = 150, offset: int = 0, search: Optional[str] = None) -> Tuple[List[str], List[Dict[str, Any]], int]:
    """
    Query rows from a given database table with optional search filter.
    Returns: (column_names, rows_as_dicts, total_matching_count)
    """
    valid_tables = ["potholes", "violations", "plates", "traffic_metrics", "pwd_work_orders", "audit_runs"]
    if table_name not in valid_tables:
        return ([], [], 0)

    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get column names
    cursor.execute(f"PRAGMA table_info({table_name});")
    cols = [r["name"] for r in cursor.fetchall()]

    where_clause = ""
    params: List[Any] = []
    if search and search.strip():
        term = f"%{search.strip()}%"
        # Search text columns
        text_cols = [c for c in cols if any(k in c.lower() for k in ("id", "type", "text", "street", "address", "severity", "code", "desc", "loc"))]
        if text_cols:
            where_clause = " WHERE " + " OR ".join([f"{c} LIKE ?" for c in text_cols])
            params = [term] * len(text_cols)

    # Total matching count
    count_sql = f"SELECT COUNT(*) FROM {table_name}{where_clause};"
    cursor.execute(count_sql, params)
    total_count = cursor.fetchone()[0]

    # Rows
    data_sql = f"SELECT * FROM {table_name}{where_clause} ORDER BY id DESC LIMIT ? OFFSET ?;"
    cursor.execute(data_sql, params + [limit, offset])
    rows = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return (cols, rows, total_count)


def get_all_potholes(severity: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
    """Fetch stored potholes."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    if severity and severity != "All Defects":
        cursor.execute("SELECT * FROM potholes WHERE UPPER(severity) LIKE ? ORDER BY id DESC LIMIT ?", (f"%{severity}%", limit))
    else:
        cursor.execute("SELECT * FROM potholes ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_all_plates(search_text: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
    """Fetch stored license plates."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    if search_text:
        cursor.execute("SELECT * FROM plates WHERE plate_text LIKE ? ORDER BY id DESC LIMIT ?", (f"%{search_text.upper()}%", limit))
    else:
        cursor.execute("SELECT * FROM plates ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_all_violations(limit: int = 200) -> List[Dict[str, Any]]:
    """Fetch stored violations and infrastructure defects."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM violations ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_all_pwd_work_orders(limit: int = 200) -> List[Dict[str, Any]]:
    """Fetch stored PWD civil work orders."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pwd_work_orders ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_latest_audit_run() -> Optional[Dict[str, Any]]:
    """Retrieve the most recent audit mission run summary."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM audit_runs ORDER BY id DESC LIMIT 1;")
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def clear_all_tables():
    """Wipe database records for a fresh test run."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    for t in ["potholes", "violations", "plates", "traffic_metrics", "pwd_work_orders", "audit_runs"]:
        cursor.execute(f"DELETE FROM {t};")
    conn.commit()
    conn.close()
