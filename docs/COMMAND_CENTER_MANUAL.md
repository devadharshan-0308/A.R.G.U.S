# 🏙️ Mobile Urban Intelligence & Surveillance Command Platform
### *Enterprise Operational Intelligence, AI-Powered Computer Vision & Real-Time GIS Dispatch*

---

## 📌 1. Executive Summary

This platform is a **real-time urban intelligence and emergency surveillance command system** designed for municipal transit authorities, police patrol squads, disaster management units, and smart city operators.

The system ingests live video telemetry from mobile surveillance vehicles, buses, and tethered drones, runs hardware-accelerated **edge AI models (YOLOv8 + OCR + Depth Estimation)**, enriches coordinates with geospatial context, and visualizes incidents across a **dark cinematic GIS operations center**.

---

## 🏛️ 2. High-Level System Architecture

```
[ Mobile Patrols / Transit Cameras / Drones ]
                   │
                   ▼ (RTSP / Video Streams)
┌─────────────────────────────────────────────────────────────┐
│           PYTHON AI INFERENCE PIPELINE (src/main.py)         │
│  ├── YOLOv8 Vehicle & Pedestrian Detector (yolo_detector.py) │
│  ├── Optical ANPR / License Plate OCR (plate_detector.py)   │
│  ├── Road Structural Pothole AI (pothole_detector.py)       │
│  ├── Geofenced Safety Rule Engine (rule_engine.py)           │
│  ├── Spatial Deduplication Engine (spatial_dedup.py)        │
│  └── Maps Geocoding & POI Enricher (maps_enricher.py)       │
└──────────────────────────┬──────────────────────────────────┘
                           │ (HTTP POST JSON + B64 Evidence Crop)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│            FASTAPI INGESTION & ALERT BACKEND (server.py)    │
│  ├── SQLite Storage Engine (src/backend/database.py)        │
│  ├── Live WebSockets Ingestion Broadcast (/ws/live)         │
│  ├── REST API Endpoints (/api/stats, /api/potholes, ...)    │
│  └── Static Evidence File Server (/evidence/*.jpg)          │
└──────────────────────────┬──────────────────────────────────┘
                           │ (WebSocket Stream + REST API)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│       NEXT-GEN URBAN COMMAND CENTER (frontend/src/)         │
│  ├── 1. Overview & 60% Hero GIS Leaflet Radar Map           │
│  ├── 2. Live Intelligence Stream & Confidence Badges        │
│  ├── 3. Camera Matrix (4K Quad Multi-Feed Inspector)        │
│  ├── 4. ANPR License Plate Watchlist & Stolen Hotlist       │
│  ├── 5. 3-Column Incident Command Workspace & Audit Trail   │
│  ├── 6. AI Detection Center & Neural Architecture Hub       │
│  ├── 7. Road Health Index (RHI) & Automated PWD Work-Orders │
│  ├── 8. Field Patrol Operations & Fleet Dispatch Simulator  │
│  ├── 9. Device Hardware Telemetry (FPS, NVMe, Thermals)     │
│  ├── 10. Prioritized Emergency Alert Triage Queue           │
│  ├── 11. Urban Surge Analytics & Risk Density Heatmaps      │
│  └── 12. Global Spotlight Command Palette (Ctrl + K)        │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 3. Quickstart & One-Click Launch

### Prerequisites
* **Python 3.10+** (with PyTorch, Ultralytics, OpenCV, FastAPI, Uvicorn installed)
* **Node.js 18+** & **npm**

### Launching the Full Stack (Single Command on Windows)
Simply double click or run:
```bash
start.bat
```
This automatically boots:
1. **FastAPI Backend Server** at `http://localhost:8000` (API Docs: `http://localhost:8000/docs`)
2. **Command Center Dashboard** at `http://localhost:5173`

---

## 🎯 4. Complete Operational Views Guide

### 1. **Command Overview & Hero Radar**
* **Top KPI Strip**: Real-time counters for Active Incidents, AI Detections Today, Connected Devices, and Monitored Areas with 21st.dev glowing borders.
* **Hero Radar GIS Map**: Interactive Leaflet dark radar with School/Hospital geofenced safety zones, custom pulse markers, and layer toggles.
* **Live Ingestion Feed**: Real-time event stream with confidence scores and geocoded street tags.

### 2. **Camera Matrix (4K Feeds)**
* Multi-camera stream switcher (`MOB-042`, `MOB-019`, `DRONE-03`, `MOB-088`).
* Live AI bounding box overlays with optical flow speed and scanline sweep effects.
* One-click toggle between **Single Focused Camera** and **Quad Matrix (4x)** simultaneous view.

### 3. **ANPR License Plate & Hotlist Center**
* Real-time license plate OCR tracking (`TN-07-BV-9021`).
* One-click **Hotlist** tagging for stolen vehicles, speeding infractors, and transit violations.
* Chronological passage history and speed logs across city corridors.

### 4. **3-Column Incident Workspace & Evidence Studio**
* **Left**: Chronological step-by-step audit trace (`Detection` → `Maps Geocoding` → `Auto-Triage` → `Field Dispatch` → `Resolution`).
* **Center**: High-res evidence photo with SHA-256 integrity hash and geocoded coordinates.
* **Right**: AI recommended corrective action, field team selector, and status progression controls.
* **One-Click Dossier Export**: Formats the incident into an official municipal citation and engineering report with QR verification and digital signature blocks.

### 5. **Road Health Index (RHI) Civil Engineering Hub**
* Real-time asphalt degradation score (0-100) per corridor (*Anna Salai*, *Poonamallee High Rd*, *OMR IT Highway*).
* Estimated asphalt repair budget calculator and automated Public Works Department (PWD) work-order generator.

### 6. **Field Operations & Animated Dispatch Simulator**
* Live tracking of patrol units (`TEAM-ALPHA`, `TEAM-BRAVO`) with radio frequencies (UHF/VHF) and officer leads.
* Interactive rapid dispatch simulator with live countdown ETA timer and siren routing.

---

## 🏆 5. Live Demonstration & Pitch Walkthrough Script

When presenting this platform to judges or municipal stakeholders, follow this recommended 3-minute demonstration flow:

1. **The Hero Overview (0:00 - 0:45)**:
   * Open `http://localhost:5173`. Highlight the dark cinematic command aesthetic, live system heartbeat, and the 60% Hero GIS Map showing Chennai metro transit corridors.
   * Press **`Ctrl + K`** to demonstrate the global spotlight command palette.

2. **Simulate Live Emergency Ingestion (0:45 - 1:30)**:
   * Click **`⚡ Simulate Emergency Ingestion`** in the top bar.
   * Point out the tactical sonar audio alert, the immediate pulse marker appearing on the radar map, and the incrementing critical alert badge.

3. **Camera Matrix & AI Inspection (1:30 - 2:15)**:
   * Navigate to **Camera Matrix (4K)**. Show the live AI bounding box overlays, and switch between Single Feed and Quad Matrix (4x) layout.
   * Click **Freeze & Inspect Crop** to open the deep AI Evidence Studio with canvas zoom/pan.

4. **ANPR Watchlist & Municipal Road Health (2:15 - 2:45)**:
   * Open **ANPR Watchlist** to showcase stolen vehicle search and passage logs.
   * Open **Road Health (RHI)** to show the automated civil engineering repair budget and PWD work-orders.

5. **Incident Lifecycle & Field Dispatch (2:45 - 3:00)**:
   * Open **Incidents**, select an active incident, and click **Export Dossier** to present the official municipal citation PDF.
   * Click **Dispatch Incident** to demonstrate the animated patrol car dispatch with real-time countdown ETA timer!
