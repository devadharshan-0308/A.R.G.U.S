"""
src/backend/database.py — SQLite Database Layer for Smart City Ingestion.

Zero-dependency SQLite storage for:
  - Deduplicated Potholes (locations, severity, image evidence)
  - Safety Rule Violations (pedestrian alerts, speeding, school zone warnings)
  - Recognized License Plates (plate text, vehicle tracking)
  - Traffic Density Metrics (counts over time)
"""

import os
import sqlite3
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

DB_PATH = os.path.join("data", "app.db")

def get_db_connection():
    """Create a thread-safe connection to the SQLite database."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database tables and indexes."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Potholes Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS potholes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        frame_id INTEGER,
        timestamp_sec REAL,
        latitude REAL,
        longitude REAL,
        street_name TEXT,
        formatted_address TEXT,
        severity TEXT,
        area_ratio REAL,
        is_school_zone BOOLEAN,
        is_hospital_zone BOOLEAN,
        evidence_image TEXT,
        status TEXT DEFAULT 'REPORTED',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. Safety Violations Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS violations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        is_school_zone BOOLEAN,
        evidence_image TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 3. License Plates Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS plates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        frame_id INTEGER,
        timestamp_sec REAL,
        latitude REAL,
        longitude REAL,
        street_name TEXT,
        plate_text TEXT,
        confidence REAL,
        evidence_image TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 4. Traffic Flow Metrics
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS traffic_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        frame_id INTEGER,
        timestamp_sec REAL,
        total_vehicles INTEGER,
        pedestrians INTEGER,
        cars INTEGER,
        motorcycles INTEGER,
        buses INTEGER,
        trucks INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Create Indexes for fast querying
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_potholes_sev ON potholes(severity);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_violations_type ON violations(violation_type);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_plates_text ON plates(plate_text);")

    conn.commit()
    conn.close()
    logger.info("Database initialized successfully at %s", DB_PATH)

# CRUD Helper Operations
def insert_pothole(data: Dict[str, Any]) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO potholes (
        frame_id, timestamp_sec, latitude, longitude, street_name,
        formatted_address, severity, area_ratio, is_school_zone,
        is_hospital_zone, evidence_image, status
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("frame_id"),
        data.get("timestamp_sec"),
        data.get("latitude"),
        data.get("longitude"),
        data.get("street_name"),
        data.get("formatted_address"),
        data.get("severity"),
        data.get("area_ratio"),
        data.get("is_school_zone", False),
        data.get("is_hospital_zone", False),
        data.get("evidence_image"),
        data.get("status", "REPORTED")
    ))
    row_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return row_id

def insert_violation(data: Dict[str, Any]) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO violations (
        frame_id, timestamp_sec, latitude, longitude, street_name,
        formatted_address, violation_type, severity, description,
        plate_text, is_school_zone, evidence_image
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("frame_id"),
        data.get("timestamp_sec"),
        data.get("latitude"),
        data.get("longitude"),
        data.get("street_name"),
        data.get("formatted_address"),
        data.get("violation_type"),
        data.get("severity"),
        data.get("description"),
        data.get("plate_text"),
        data.get("is_school_zone", False),
        data.get("evidence_image")
    ))
    row_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return row_id

def insert_plate(data: Dict[str, Any]) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO plates (
        frame_id, timestamp_sec, latitude, longitude,
        street_name, plate_text, confidence, evidence_image
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("frame_id"),
        data.get("timestamp_sec"),
        data.get("latitude"),
        data.get("longitude"),
        data.get("street_name"),
        data.get("plate_text"),
        data.get("confidence"),
        data.get("evidence_image")
    ))
    row_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return row_id

def insert_traffic_metric(data: Dict[str, Any]) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO traffic_metrics (
        frame_id, timestamp_sec, total_vehicles, pedestrians,
        cars, motorcycles, buses, trucks
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("frame_id"),
        data.get("timestamp_sec"),
        data.get("total_vehicles", 0),
        data.get("pedestrians", 0),
        data.get("cars", 0),
        data.get("motorcycles", 0),
        data.get("buses", 0),
        data.get("trucks", 0)
    ))
    row_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return row_id

def get_all_potholes(severity: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    if severity:
        cursor.execute("SELECT * FROM potholes WHERE severity = ? ORDER BY id DESC LIMIT ?", (severity, limit))
    else:
        cursor.execute("SELECT * FROM potholes ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def get_all_violations(violation_type: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    if violation_type:
        cursor.execute("SELECT * FROM violations WHERE violation_type = ? ORDER BY id DESC LIMIT ?", (violation_type, limit))
    else:
        cursor.execute("SELECT * FROM violations ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def get_all_plates(search_text: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    if search_text:
        cursor.execute("SELECT * FROM plates WHERE plate_text LIKE ? ORDER BY id DESC LIMIT ?", (f"%{search_text}%", limit))
    else:
        cursor.execute("SELECT * FROM plates ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def get_recent_metrics(limit: int = 100) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM traffic_metrics ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    rows.reverse()  # Chronological order
    return rows

def get_dashboard_summary() -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM potholes;")
    total_potholes = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM potholes WHERE severity = 'severe pothole';")
    severe_potholes = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM violations;")
    total_violations = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT plate_text) FROM plates WHERE plate_text != '';")
    unique_plates = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM violations WHERE is_school_zone = 1;")
    school_zone_alerts = cursor.fetchone()[0]

    cursor.execute("""
    SELECT 
        COALESCE(SUM(total_vehicles), 0),
        COALESCE(SUM(pedestrians), 0),
        COALESCE(SUM(cars), 0),
        COALESCE(SUM(motorcycles), 0),
        COALESCE(SUM(buses), 0),
        COALESCE(SUM(trucks), 0)
    FROM traffic_metrics;
    """)
    t_row = cursor.fetchone()
    traffic_totals = {
        "total_vehicles": t_row[0],
        "total_pedestrians": t_row[1],
        "total_cars": t_row[2],
        "total_motorcycles": t_row[3],
        "total_buses": t_row[4],
        "total_trucks": t_row[5]
    }

    conn.close()
    return {
        "total_potholes": total_potholes,
        "severe_potholes": severe_potholes,
        "total_violations": total_violations,
        "unique_plates_scanned": unique_plates,
        "school_zone_critical_alerts": school_zone_alerts,
        "traffic_totals": traffic_totals,
        "status": "ONLINE"
    }
