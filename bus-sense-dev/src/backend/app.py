"""
src/backend/app.py — FastAPI Smart City Ingestion & Alerts Server.

Features:
  - Ingestion Webhook / Stream receiver (`POST /api/events`)
  - Real-time WebSockets (`/ws/live`) for instant map marker and alert broadcasting
  - REST endpoints for Potholes, Violations, License Plates, and Metrics
  - Static file server for image evidence crops (`/evidence/...`)
"""

import os
import json
import base64
import logging
from typing import List, Optional
import cv2
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.backend.database import (
    init_db,
    insert_pothole,
    insert_violation,
    insert_plate,
    insert_traffic_metric,
    get_all_potholes,
    get_all_violations,
    get_all_plates,
    get_recent_metrics,
    get_dashboard_summary
)

logger = logging.getLogger(__name__)

# Ensure evidence directory exists
EVIDENCE_DIR = os.path.join("data", "evidence")
os.makedirs(EVIDENCE_DIR, exist_ok=True)

# Initialize Database
init_db()

app = FastAPI(
    title="Smart City Traffic & Pothole Ingestion API",
    description="Backend API with Maps MCP enrichment, SQLite storage, and Live WebSockets",
    version="1.0.0"
)

# CORS Setup (Allow frontend dashboards to connect seamlessly)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve Evidence Image Crops
app.mount("/evidence", StaticFiles(directory=EVIDENCE_DIR), name="evidence")


# ─── WEBSOCKET CONNECTION MANAGER ───────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Remaining: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()


# ─── DATA MODELS ────────────────────────────────────────────────────────────
class IngestionEvent(BaseModel):
    event_type: str  # "pothole", "violation", "plate", "metric"
    frame_id: int
    timestamp_sec: float
    latitude: float
    longitude: float
    street_name: Optional[str] = "Main Road"
    formatted_address: Optional[str] = None
    is_school_zone: Optional[bool] = False
    is_hospital_zone: Optional[bool] = False
    payload: dict
    image_base64: Optional[str] = None  # Optional JPEG crop


# ─── REST ENDPOINTS ─────────────────────────────────────────────────────────
@app.get("/api/health")
def health():
    return {"status": "ONLINE", "database": "SQLite", "version": "1.0.0"}

@app.get("/api/stats")
def get_stats():
    return get_dashboard_summary()

@app.get("/api/potholes")
def list_potholes(
    severity: Optional[str] = Query(None, description="Filter by severity: 'severe pothole', 'mild pothole', 'shallow pothole'"),
    limit: int = 100
):
    return get_all_potholes(severity=severity, limit=limit)

@app.get("/api/violations")
def list_violations(
    violation_type: Optional[str] = Query(None, description="Filter by violation type"),
    limit: int = 100
):
    return get_all_violations(violation_type=violation_type, limit=limit)

@app.get("/api/plates")
def list_plates(
    q: Optional[str] = Query(None, description="Search by plate text"),
    limit: int = 100
):
    return get_all_plates(search_text=q, limit=limit)

@app.get("/api/metrics")
def list_metrics(limit: int = 100):
    return get_recent_metrics(limit=limit)


# ─── LIVE EVENT RECEIVER & WEBSOCKET BROADCAST ──────────────────────────────
@app.post("/api/events")
async def ingest_event(event: IngestionEvent):
    """
    Ingests an enriched event from the AI pipeline, persists it to SQLite,
    saves image crops if provided, and broadcasts to live WebSockets.
    """
    evidence_filename = None
    if event.image_base64:
        try:
            img_data = base64.b64decode(event.image_base64)
            filename = f"ev_{event.event_type}_{event.frame_id}_{int(event.timestamp_sec * 1000)}.jpg"
            file_path = os.path.join(EVIDENCE_DIR, filename)
            with open(file_path, "wb") as f:
                f.write(img_data)
            evidence_filename = f"/evidence/{filename}"
        except Exception as e:
            logger.warning(f"Failed to save evidence image: {e}")

    broadcast_data = {
        "event_type": event.event_type,
        "frame_id": event.frame_id,
        "timestamp_sec": event.timestamp_sec,
        "latitude": event.latitude,
        "longitude": event.longitude,
        "street_name": event.street_name,
        "formatted_address": event.formatted_address,
        "is_school_zone": event.is_school_zone,
        "is_hospital_zone": event.is_hospital_zone,
        "evidence_image": evidence_filename,
        **event.payload
    }

    # Persist according to event type
    if event.event_type == "pothole":
        insert_pothole({
            **broadcast_data,
            "area_ratio": event.payload.get("area_ratio", 0.0),
            "severity": event.payload.get("severity", "mild pothole")
        })
    elif event.event_type == "violation":
        insert_violation({
            **broadcast_data,
            "violation_type": event.payload.get("violation_type", "SAFETY_ALERT"),
            "severity": event.payload.get("severity", "MEDIUM"),
            "description": event.payload.get("description", ""),
            "plate_text": event.payload.get("plate_text", "")
        })
    elif event.event_type == "plate":
        insert_plate({
            **broadcast_data,
            "plate_text": event.payload.get("plate_text", ""),
            "confidence": event.payload.get("confidence", 0.0)
        })
    elif event.event_type == "metric":
        insert_traffic_metric({
            "frame_id": event.frame_id,
            "timestamp_sec": event.timestamp_sec,
            **event.payload
        })

    # Broadcast live to connected frontend WebSockets
    await manager.broadcast(broadcast_data)

    return {"status": "SUCCESS", "event_type": event.event_type}


@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep-alive loop
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
