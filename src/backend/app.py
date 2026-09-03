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
    title="ARGUS // Municipal Fleet Sensing & Infrastructure Intelligence API",
    description="The Hundred Eyes of the City — Backend API with SQLite storage, Live WebSockets, and PWD Work-Orders",
    version="2.0.0"
)

# CORS Setup (Allow frontend dashboards to connect seamlessly)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve Evidence Image Crops & Input/Output Videos
DATA_DIR = "data"
os.makedirs(os.path.join(DATA_DIR, "input"), exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, "output"), exist_ok=True)
app.mount("/evidence", StaticFiles(directory=EVIDENCE_DIR), name="evidence")
app.mount("/data", StaticFiles(directory=DATA_DIR), name="data")



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

@app.get("/api/videos")
def list_videos():
    input_dir = os.path.join("data", "input")
    output_dir = os.path.join("data", "output")
    
    videos = []
    if os.path.exists(input_dir):
        for f in os.listdir(input_dir):
            if f.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
                f_path = os.path.join(input_dir, f)
                videos.append({
                    "name": f,
                    "type": "input",
                    "url": f"/data/input/{f}",
                    "size_mb": round(os.path.getsize(f_path) / (1024 * 1024), 2)
                })
    if os.path.exists(output_dir):
        for f in os.listdir(output_dir):
            if f.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
                f_path = os.path.join(output_dir, f)
                videos.append({
                    "name": f,
                    "type": "output",
                    "url": f"/data/output/{f}",
                    "size_mb": round(os.path.getsize(f_path) / (1024 * 1024), 2)
                })
    return videos



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


# ─── LIVE AI PIPELINE TRIGGER ENDPOINTS ──────────────────────────────────────
pipeline_state = {
    "is_running": False,
    "current_video": None,
    "exit_code": None,
    "last_run": None
}

class PipelineRunRequest(BaseModel):
    video_name: str = "pothole.mp4"
    enable_potholes: bool = True

@app.get("/api/pipeline/status")
def get_pipeline_status():
    return pipeline_state

@app.post("/api/pipeline/run")
def trigger_pipeline(req: PipelineRunRequest):
    import subprocess
    import threading

    if pipeline_state["is_running"]:
        return {"status": "ALREADY_RUNNING", "message": "Pipeline is currently processing another video."}
    
    input_path = os.path.join("data", "input", req.video_name)
    if not os.path.exists(input_path):
        return {"status": "ERROR", "message": f"Video '{req.video_name}' not found in data/input/ directory."}

    def run_worker():
        pipeline_state["is_running"] = True
        pipeline_state["current_video"] = req.video_name
        try:
            cmd = ["python", "src/main.py", "--input", input_path, "--no-preview"]
            if req.enable_potholes:
                cmd.append("--enable-potholes")
            
            logger.info(f"Triggering AI Pipeline via UI: {' '.join(cmd)}")
            res = subprocess.run(cmd, check=False)
            pipeline_state["exit_code"] = res.returncode
        except Exception as e:
            logger.error(f"Pipeline execution error: {e}")
        finally:
            pipeline_state["is_running"] = False
            pipeline_state["last_run"] = req.video_name

    thread = threading.Thread(target=run_worker, daemon=True)
    thread.start()

    return {"status": "STARTED", "video": req.video_name, "message": f"AI Pipeline started for {req.video_name}"}


@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep-alive loop
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ─── PWD MUNICIPAL CIVIL WORK-ORDER ENDPOINTS ────────────────────────────────
@app.get("/api/pwd/work-orders")
def get_pwd_work_orders():
    """
    Returns the latest PWD civil repair work-order docket, budget summary,
    and items parsed directly from the most recent generated CSV docket.
    """
    import csv
    output_dir = os.path.join("data", "output")
    if not os.path.exists(output_dir):
        return {"status": "EMPTY", "total_orders": 0, "total_budget_inr": 0, "orders": []}

    csv_files = [f for f in os.listdir(output_dir) if f.startswith("PWD_WORK_ORDER_") and f.endswith(".csv")]
    if not csv_files:
        return {"status": "EMPTY", "total_orders": 0, "total_budget_inr": 0, "orders": []}

    csv_files.sort(reverse=True)
    latest_csv = csv_files[0]
    csv_path = os.path.join(output_dir, latest_csv)

    orders = []
    total_budget = 0
    prios = {"P1 - CRITICAL": 0, "P2 - HIGH": 0, "P3 - MEDIUM": 0}

    try:
        with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cost = int(row.get("Estimated_Cost_INR", 0) or 0)
                sev = row.get("Severity", "P3 - MEDIUM")
                prios[sev] = prios.get(sev, 0) + 1
                total_budget += cost
                orders.append(row)
    except Exception as e:
        logger.warning(f"Error reading CSV docket: {e}")

    return {
        "status": "SUCCESS",
        "csv_filename": latest_csv,
        "csv_url": f"/data/output/{latest_csv}",
        "total_orders": len(orders),
        "total_budget_inr": total_budget,
        "total_budget_formatted": f"₹{total_budget:,} INR",
        "priority_breakdown": prios,
        "orders": orders
    }


@app.post("/api/pwd/dispatch")
def dispatch_pwd_docket():
    """
    Triggers the direct native email dispatch of the latest PWD work-order docket
    and CSV spreadsheet to municipal engineering authorities.
    """
    from src.email_dispatcher import send_pwd_workorder_email

    summary_data = get_pwd_work_orders()
    if summary_data.get("total_orders", 0) == 0:
        return {"status": "ERROR", "message": "No active PWD work orders available to dispatch."}

    csv_path = os.path.join("data", "output", summary_data["csv_filename"])
    ok, msg = send_pwd_workorder_email(summary_data, csv_path)
    return {
        "status": "SUCCESS" if ok else "ERROR",
        "message": msg
    }


