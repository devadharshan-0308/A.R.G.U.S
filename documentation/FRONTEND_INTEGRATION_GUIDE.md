# 🌐 Frontend UI Integration & Backend Handshake Specification

**Document Reference:** `SIH-DEV-FRONTEND-2026`  
**Target Audience:** Frontend UI Developer (React / Next.js / Vue / HTML5)  
**Backend Host:** `http://localhost:8000`  
**WebSocket Stream:** `ws://localhost:8000/ws/live`  
**Swagger API Documentation:** `http://localhost:8000/docs`  

---

## 1. Executive Summary for the Frontend Developer

This document provides everything you need to build or connect the user interface (UI) to the **Smart City Mobile Urban Surveillance Platform** backend. 

The edge AI pipeline runs on public transit buses (e.g., MTC Chennai), continuously analyzing road distress, traffic compliance, and civic infrastructure. The backend exposes both a **high-throughput REST API** and a **real-time WebSocket event stream** that pushes instant alerts, GPS telemetry, and incident thumbnails directly to your frontend.

---

## 2. Quickstart: Running the Backend Server

The backend is built with FastAPI and SQLite. Start the server from the project root:

```powershell
# In terminal (with venv activated):
python server.py
```
* **REST API:** `http://localhost:8000`
* **Interactive Swagger UI:** `http://localhost:8000/docs`
* **Real-Time WebSockets:** `ws://localhost:8000/ws/live`
* **CORS:** Enabled for all origins (`allow_origins=["*"]`) — no CORS errors!

---

## 3. What Features & Components MUST Be in the UI

To deliver a complete, award-winning Smart India Hackathon dashboard, your UI should feature the following **6 primary layout modules**:

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ [TOP BAR] Bus ID: TN-MTC-BUS-104 · Corridor: Anna Salai Arterial · GPS: 13.0827°N, 80.2707°E · ● ONLINE │
├───────────────────────────────────────────────────────┬─────────────────────────────────────────────────┤
│ [MODULE 1: VIDEO & MANEUVER HUD]                      │ [MODULE 2: INTERACTIVE GEOSPATIAL MAP]          │
│ • Live Stream Player / Canvas (1080p Video Feed)       │ • Mapbox / Leaflet / Google Maps View           │
│ • Turn-by-Turn Telemetry:                             │ • Real-time Bus GPS Marker with Heading Bearing │
│   - Current Speed: 32 km/h                            │ • Color-Coded Defect Pins:                      │
│   - Corridor Speed Limit: 40 km/h                     │   - 🔴 Red: P1 Critical Defects                 │
│   - ⚠️ School Zone Amber Warning (<150m)              │   - 🟠 Amber: P2 High Defects                   │
│   - Traffic Congestion Index: 45% (Medium)            │   - 🔵 Blue: P3 Minor/Medium                    │
│ • Playback Controls: Play / Pause / Load Stream       │ • 4 Layer Toggles: Streets / Satellite / Dark   │
├───────────────────────────────────────────────────────┴─────────────────────────────────────────────────┤
│ [MODULE 3: MUNICIPAL PWD WORK-ORDER & DISPATCH COCKPIT] (CIVIL ENGINEERING LAYER)                       │
│ • KPI Cards: Total Orders (85) | Budget (₹251,850 INR) | P1 Critical (54) | P2 High (26) | P3 Med (5)  │
│ • Actions:                                                                                              │
│   [ 📊 Download PWD CSV Spreadsheet ]                                                                  │
│   [ 🚀 Dispatch Work-Order to Municipal Authorities (1-Click) ] ──► Triggers Email & Shows Success Toast│
│ • Tabular Schedule: Work-Order ID | Defect Type | IRC Code | Repair Action | Material BOQ | Cost (INR)  │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ [MODULE 4: LIVE FORENSIC INCIDENT STREAM]             │ [MODULE 5: TRAFFIC & ANPR RECOGNITION]          │
│ • Real-time event cards sliding in via WebSocket:     │ • MoRTH Vehicle Plate Cards:                    │
│   - Timestamp & Frame Index                           │   - Synthesized Plate: "TN-09-AB-1234"          │
│   - Defect Type (Pothole / Broken Median / Crosswalk) │   - State: "Tamil Nadu" · Confidence: 94.2%     │
│   - Street & Landmark                                 │   - High-contrast Plate Crop Thumbnail          │
│   - Thumbnail Image Crop                              │ • Vehicle Classification Counts:                │
│ • Click card to open Evidence Inspector Modal         │   - Cars, Buses, Trucks, 2-Wheelers, Autos      │
└───────────────────────────────────────────────────────┴─────────────────────────────────────────────────┘
```

---

## 4. Complete Backend REST API Reference

All endpoints return JSON and adhere to standard HTTP status codes.

### 4.1. Health & System Status
* **`GET /api/health`**
  ```json
  {
    "status": "ONLINE",
    "database": "SQLite",
    "version": "1.0.0"
  }
  ```

* **`GET /api/stats`**  
  *Returns aggregated platform statistics for KPI counter cards.*
  ```json
  {
    "total_potholes": 85,
    "severe_potholes": 54,
    "mild_potholes": 26,
    "shallow_potholes": 5,
    "total_violations": 12,
    "unique_plates": 34,
    "total_metrics_recorded": 1240
  }
  ```

---

### 4.2. PWD Civil Maintenance & Email Dispatch (Crucial!)

* **`GET /api/pwd/work-orders`**  
  *Returns the latest Indian Road Congress (IRC) work-order docket, budget, and all defect records parsed from the most recent CSV docket.*
  ```json
  {
    "status": "SUCCESS",
    "csv_filename": "PWD_WORK_ORDER_20260903_233457.csv",
    "csv_url": "/data/output/PWD_WORK_ORDER_20260903_233457.csv",
    "total_orders": 85,
    "total_budget_inr": 251850,
    "total_budget_formatted": "₹251,850 INR",
    "priority_breakdown": {
      "P1 - CRITICAL": 54,
      "P2 - HIGH": 26,
      "P3 - MEDIUM": 5
    },
    "orders": [
      {
        "Work_Order_ID": "PWD-CHN-2026-0001",
        "Timestamp": "2026-09-03 23:34:57",
        "Defect_Type": "Severe Pothole",
        "Severity": "P1 - CRITICAL",
        "IRC_Specification": "IRC:82-2015",
        "Repair_Action": "Mill and Inlay Bituminous Concrete",
        "Estimated_Material_Qty": "0.007 m3 Bitumen Cold Mix",
        "Estimated_Cost_INR": "4500",
        "SLA_Hours": "24",
        "Corridor": "Anna Salai Corridor",
        "Latitude": "13.082716",
        "Longitude": "80.270708",
        "Google_Maps_URL": "https://maps.google.com/?q=13.082716,80.270708",
        "Reporting_Bus_ID": "TN-MTC-BUS-104"
      }
    ]
  }
  ```

* **`POST /api/pwd/dispatch`**  
  *Triggers 1-click email transmission of the official PWD Work-Order and CSV spreadsheet directly to municipal engineering authorities (`devadharshan03082006@gmail.com`).*
  * **Request:** Empty POST `{}`
  * **Response:**
    ```json
    {
      "status": "SUCCESS",
      "message": "Work-order docket & CSV successfully dispatched to Municipal Authorities!"
    }
    ```
  * **Frontend Action:** When the user clicks the Dispatch button:
    1. Show a loading spinner / *"Transmitting to Municipal Authorities..."*
    2. On success, trigger a green toast / alert: *"✅ Work-Order Docket Successfully Dispatched!"*

---

### 4.3. Potholes & Road Distress Feed
* **`GET /api/potholes?severity=severe pothole&limit=50`**
  ```json
  [
    {
      "id": 1,
      "frame_id": 142,
      "timestamp_sec": 4.73,
      "latitude": 13.082716,
      "longitude": 80.270708,
      "street_name": "Anna Salai",
      "formatted_address": "Anna Salai, Triplicane, Chennai, Tamil Nadu 600002",
      "is_school_zone": 0,
      "is_hospital_zone": 0,
      "area_ratio": 0.084,
      "severity": "severe pothole",
      "evidence_image": "/evidence/ev_pothole_142_4733.jpg",
      "created_at": "2026-09-03 23:34:58"
    }
  ]
  ```

---

### 4.4. Traffic Safety & Infrastructure Compliance
* **`GET /api/violations?limit=50`**
  ```json
  [
    {
      "id": 1,
      "frame_id": 210,
      "timestamp_sec": 7.0,
      "latitude": 13.082730,
      "longitude": 80.270715,
      "street_name": "Anna Salai",
      "violation_type": "MISSING_MEDIAN_BARRIER",
      "severity": "HIGH",
      "description": "Concrete median divider discontinuity detected under IRC:119-2015",
      "evidence_image": "/evidence/ev_violation_210_7000.jpg"
    }
  ]
  ```

---

### 4.5. MoRTH License Plates (ANPR)
* **`GET /api/plates?q=TN-09&limit=50`**
  ```json
  [
    {
      "id": 1,
      "frame_id": 85,
      "timestamp_sec": 2.83,
      "latitude": 13.082710,
      "longitude": 80.270702,
      "street_name": "Anna Salai",
      "plate_text": "TN-09-AB-1234",
      "confidence": 0.942,
      "evidence_image": "/evidence/ev_plate_85_2833.jpg"
    }
  ]
  ```

---

### 4.6. Video Pipeline Trigger (Run from UI)
* **`GET /api/videos`**: Lists all available test videos in `data/input/`.
* **`POST /api/pipeline/run`**: Triggers the AI pipeline on a selected video.
  ```json
  // Request Body
  {
    "video_name": "pothole.mp4",
    "enable_potholes": true
  }
  ```
* **`GET /api/pipeline/status`**: Polls the background execution state:
  ```json
  {
    "is_running": true,
    "current_video": "pothole.mp4",
    "exit_code": null,
    "last_run": null
  }
  ```

---

## 5. Live WebSocket Integration (`ws://localhost:8000/ws/live`)

Whenever the AI models detect a defect, plate, or telemetry event during stream playback, the server broadcasts a JSON payload to all connected WebSocket clients:

### Pothole Event Payload:
```json
{
  "event_type": "pothole",
  "frame_id": 184,
  "timestamp_sec": 6.13,
  "latitude": 13.082718,
  "longitude": 80.270709,
  "street_name": "Anna Salai Arterial",
  "formatted_address": "Anna Salai, Chennai, Tamil Nadu",
  "is_school_zone": false,
  "is_hospital_zone": false,
  "area_ratio": 0.092,
  "severity": "severe pothole",
  "evidence_image": "/evidence/ev_pothole_184_6133.jpg"
}
```

### Traffic Telemetry Metric Payload:
```json
{
  "event_type": "metric",
  "frame_id": 184,
  "timestamp_sec": 6.13,
  "latitude": 13.082718,
  "longitude": 80.270709,
  "speed_kmh": 34.2,
  "speed_limit_kmh": 40,
  "congestion_index": 42.5,
  "vehicle_counts": {
    "car": 6,
    "bus": 2,
    "truck": 1,
    "motorcycle": 8,
    "person": 2
  }
}
```

---

## 6. Ready-to-Copy React / JavaScript Integration Code

### 6.1. WebSocket Auto-Reconnecting Hook (React):
```javascript
import { useEffect, useState } from 'react';

export function useLiveTelemetry() {
  const [incidents, setIncidents] = useState([]);
  const [currentMetrics, setCurrentMetrics] = useState(null);

  useEffect(() => {
    let ws = null;
    let timer = null;

    function connect() {
      ws = new WebSocket('ws://localhost:8000/ws/live');

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.event_type === 'metric') {
          setCurrentMetrics(data);
        } else {
          // Prepend new incident card
          setIncidents((prev) => [data, ...prev.slice(0, 49)]);
        }
      };

      ws.onclose = () => {
        // Auto-reconnect after 2 seconds
        timer = setTimeout(connect, 2000);
      };
    }

    connect();
    return () => {
      if (ws) ws.close();
      if (timer) clearTimeout(timer);
    };
  }, []);

  return { incidents, currentMetrics };
}
```

### 6.2. 1-Click PWD Email Dispatcher Function:
```javascript
export async function dispatchMunicipalWorkOrder() {
  try {
    const res = await fetch('http://localhost:8000/api/pwd/dispatch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    const data = await res.json();
    if (data.status === 'SUCCESS') {
      alert('✅ Work-Order Docket & CSV Successfully Dispatched to Municipal Authorities!');
    } else {
      alert('⚠️ Dispatch Failed: ' + data.message);
    }
  } catch (err) {
    alert('Network Error connecting to backend: ' + err.message);
  }
}
```

---

## 7. Checklist for Frontend Completion

- [ ] Connect WebSocket to `ws://localhost:8000/ws/live` for real-time incident cards.
- [ ] Connect Mapbox / Leaflet map to plot live GPS coordinates and color-coded defect pins.
- [ ] Fetch initial stats from `GET /api/stats` and PWD orders from `GET /api/pwd/work-orders`.
- [ ] Implement **`🚀 Dispatch Work-Order`** button calling `POST /api/pwd/dispatch`.
- [ ] Build **Evidence Inspector Modal** that renders `http://localhost:8000` + `incident.evidence_image`.
- [ ] Add stream trigger button calling `POST /api/pipeline/run` with `pothole.mp4`.
