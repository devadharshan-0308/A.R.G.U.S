# 🏛️ Centralized & Onboard Transit UI/UX Master Blueprint
## AI-Powered Mobile Urban Sensing & Municipal Infrastructure Intelligence Platform

**Document Reference:** `SIH-2026-UI-BLUEPRINT`  
**Target Audience:** Frontend UI/UX Developer & Core Systems Architect  
**Design Standard:** Enterprise Tactical Glassmorphism & Municipal Command System  
**Backend Host:** `http://localhost:8000` (FastAPI REST + WebSocket `/ws/live`)  
**Associated Standards:** Indian Road Congress (`IRC:82`, `IRC:119`, `IRC:35`, `IRC:SP:42`, `IRC:67`), MoRTH Motor Vehicles Act  

---

## 1. Architectural Philosophy: Dual-Mode Intelligence System

The Problem Statement establishes two distinct operational environments that the UI must seamlessly support:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        SMART CITY TRANSIT INTELLIGENCE PLATFORM                        │
├───────────────────────────────────────────┬────────────────────────────────────────────┤
│ 🚌 MODE A: ONBOARD EDGE COCKPIT           │ 🏛️ MODE B: CENTRAL MUNICIPAL COMMAND       │
│ • Target: Transit Bus Driver / Conductor  │ • Target: Greater Chennai Corp / Traffic HQ│
│ • Focus: Real-Time Tactical Safety        │ • Focus: City-Wide Fleet GIS & Maintenance │
│ • Latency: < 30ms (Local Video Stream)    │ • Latency: Real-time WebSockets & Analytics│
│ • Screen: In-cabin 10.1" - 15.6" Tablet/HUD│ • Screen: Multi-Monitor Command Wall / Web │
└───────────────────────────────────────────┴────────────────────────────────────────────┘
```

---

## 2. Master Navigation & View Hierarchy

The frontend application should have a top-level **Tactical Switcher** or Sidebar with **5 dedicated views**:

```
[ 🌐 Central GIS Command ]  [ 🚌 Onboard Cockpit ]  [ 📋 PWD Road Maintenance ]  [ 🚦 Traffic & Route Delays ]  [ 🚨 Security & Hit-and-Run ]
```

---

## 3. Detailed View Specifications (Component-by-Component)

### 🗺️ VIEW 1: Central Fleet GIS Command Dashboard (City-Wide Overview)
*The primary executive overview for municipal commissioners and transport planners.*

#### Key Components:
1. **Top Metric Counter Bar (Live KPI Chips):**
   - **Active Fleet Units:** e.g., `12 Buses Online` (MTC Depot 4).
   - **Total Road Defects Active:** Count with breakdown (P1: 54, P2: 26, P3: 5).
   - **City Infrastructure Health Score:** e.g., `78/100` (Computed from distress density per km).
   - **Active Congestion Hotspots:** e.g., `4 Corridors Critical`.
   - **Hit-and-Run / Safety Alerts (24h):** Counter with red pulsing badge.

2. **Full-Screen Interactive GIS Cartographic Map (Mapbox / Leaflet):**
   - **Live Multi-Bus Fleet Markers:** Showing Bus IDs (`TN-MTC-BUS-104`, `TN-MTC-BUS-202`, etc.), orientation arrows, and speed.
   - **Layer 1: Road Condition Clusters:**
     - 🔴 Red Pins: P1 Critical Potholes & Flooding.
     - 🟠 Amber Pins: Missing Median Barriers & Broken Curbs.
     - 🔵 Blue Pins: Faded Zebra Crosswalks & Tilted Signboards.
   - **Layer 2: Real-Time Traffic Congestion Heatmap:**
     - Green: Speed $> 35\text{ km/h}$.
     - Yellow: Speed $20 - 35\text{ km/h}$.
     - Red/Burgundy: Choke points $< 15\text{ km/h}$.
   - **Layer 3: School & Hospital Safety Geo-Fences:**
     - Outlined translucent polygons highlighting designated vulnerable pedestrian corridors.

3. **Floating Fleet Telemetry Sidebar (Right Panel):**
   - List of all transit buses with current driver, route number (e.g., `Route 102: Kelambakkam to Broadway`), current speed, and recent defect scan counter.
   - Clicking a bus smoothly zooms the map to its live position and opens its forward video feed.

---

### 🚌 VIEW 2: Onboard Edge Transit Cockpit (Bus In-Cabin HUD)
*The high-contrast, tactical driver and edge monitoring view currently powered by our `gui_app.py`.*

#### Key Components:
1. **Live Ultra-Low-Latency Video Stream Viewport:**
   - 1080p canvas with real-time bounding box overlays:
     - Vehicles (Cars, Trucks, 2-Wheelers, Auto-Rickshaws) with ByteTrack persistence IDs.
     - Pothole bounding boxes with area in $\text{m}^2$ and estimated depth in $\text{mm}$.
     - Detected concrete curbs with yellow/black alignment indicators.
     - School children / pedestrians highlighted with proximity vectors.

2. **Tactical Turn-by-Turn Maneuver HUD (Top Ribbon):**
   - **Live Speedometer:** Analog/digital gauge displaying current bus speed ($\text{km/h}$).
   - **Corridor Speed Limit Indicator:** Regulatory circular speed sign ($40\text{ km/h}$ standard, drops to $25\text{ km/h}$ in school zones).
   - **⚠️ School Zone Amber Warning Beacon:** Pulses brightly within $150\text{ meters}$ of school grounds.
   - **Traffic Density Barometer:** Percentage gauge ($0\% - 100\%$) indicating forward corridor choke level.

3. **Live Incident Stream (Bottom Drawer):**
   - Horizontal sliding carousel of newly identified hazards as the bus moves.
   - Each card displays timestamp, thumbnail image, defect category, and severity tag.

---

### 📋 VIEW 3: Municipal PWD Civil Maintenance & Work-Order Center
*Translating edge detections into actionable public works civil engineering repair contracts.*

#### Key Components:
1. **Executive Budgetary Summary Card:**
   - **Total Civil Work Orders:** e.g., `85 Orders`.
   - **Estimated Municipal Repair Budget:** Formatted in Indian Rupees (e.g., `₹251,850 INR`).
   - **SLA Countdown Badges:**
     - 🚨 P1 Critical: `54 defects` (24-Hour Legal SLA).
     - ⚠️ P2 High: `26 defects` (48-Hour SLA).
     - ℹ️ P3 Medium: `5 defects` (7-Day Maintenance SLA).

2. **1-Click Municipal Email Dispatcher Action Bar:**
   - **Button 1:** `📊 Export Official PWD CSV Docket` (Direct link to `/data/output/PWD_WORK_ORDER_*.csv`).
   - **Button 2 (Highlight):** `🚀 Dispatch Official Work-Order to Municipal Authorities`
     - Calls backend `POST /api/pwd/dispatch`.
     - Displays spinner: *"Transmitting official docket to Municipal Authorities..."*
     - Shows toast notification: *"✅ Work-Order Docket Successfully Dispatched to Municipal Authorities!"*

3. **Itemized IRC Repair Schedule Table:**
   - Columns:
     1. **Work Order ID:** `PWD-CHN-2026-0001`
     2. **Defect Classification:** Severe Pothole / Broken Median / Faded Crosswalk / Waterlogging
     3. **Indian Road Congress Specification:** `IRC:82-2015`, `IRC:119-2015`, `IRC:35-2015`, `IRC:SP:42-2014`
     4. **Required Civil Repair Action:** e.g., *"Mill and Inlay Bituminous Concrete (BC) with tack coat"*
     5. **Estimated Material Quantity (BOQ):** e.g., `0.007 m³ Bitumen Cold Mix`
     6. **Estimated Cost (INR):** `₹4,500`
     7. **Corridor & GPS:** `13.082716, 80.270708` (with clickable *"Open Google Maps"* link)

---

### 🚦 VIEW 4: Traffic Analytics, Congestion Heatmaps & Route Delay Estimator
*Transit fleet optimization and bottleneck identification.*

#### Key Components:
1. **Origin-Destination & Corridor Delay Matrix:**
   - Compares scheduled stop arrival times against actual AI-calculated transit times.
   - Computes **Headway Variance:** Distance/time spacing between consecutive buses on the same route to prevent "bus bunching."

2. **Vehicle Classification Distribution Charts (Chart.js / Recharts):**
   - Donut chart: Split of Two-Wheelers ($45\%$), Cars ($30\%$), Auto-Rickshaws ($15\%$), Commercial Trucks ($10\%$).
   - Hourly Congestion Timeline: Line chart showing traffic density spikes during 08:00–10:30 AM and 05:00–08:30 PM.

3. **Infrastructure Deficiency Summary:**
   - Ranking list of the worst road corridors in the city (e.g., *Anna Salai Arterial: 32 defects/km*, *GST Road: 18 defects/km*).

---

### 🚨 VIEW 5: High-Priority Safety, Rash Driving & Hit-and-Run Forensic Hub
*Law enforcement and RTO rapid-response evidence locker.*

#### Key Components:
1. **Offending Vehicle Auto-Lock Dossier:**
   - Triggered when a vehicle trajectory cuts dangerously close to pedestrians or flees after a collision.
   - **Synthesized Indian Registration Plate:** `TN-09-AB-1234` (Strict MoRTH format).
   - **State / Union Territory:** Tamil Nadu (RTO Chennai Central).
   - **OCR Confidence Score:** `94.2%`.
   - **Multi-View Visual Proof:**
     - View A: Raw full-frame camera capture.
     - View B: High-contrast binarized license plate crop.
     - View C: Vehicle crop with ByteTrack trajectory path overlay.

2. **Incident Timestamp & Exact Geolocation:**
   - Time: `2026-09-03 23:34:57 IST`.
   - GPS: `13.082716° N, 80.270708° E` (Reverse geocoded to landmark).

3. **Law Enforcement & Police RTO Dispatch Button:**
   - 1-click export of the high-resolution evidentiary packet for traffic police citation and FIR registration.

---

## 4. Design System & Aesthetics (UI Style Guide)

To match the high-tech, mission-critical nature of the platform, the frontend should follow this design system:

| Token | Value | Visual Purpose |
| :--- | :--- | :--- |
| **Background Primary** | `#0b0f19` / `#0f172a` | Deep Slate / Navy cockpit dark mode |
| **Surface Card** | `#1e293b` (with `backdrop-filter: blur(12px)`) | Translucent glassmorphic card |
| **Card Border** | `1px solid rgba(255, 255, 255, 0.08)` | Subtle border for clean visual hierarchy |
| **Accent Emerald** | `#059669` / `#10b981` | PWD / Municipal Authority official actions |
| **Hazard Critical (P1)**| `#dc2626` / `#ef4444` | Critical potholes, accidents, emergency alerts |
| **Hazard High (P2)** | `#d97706` / `#f59e0b` | High-priority repairs, school zone amber warnings |
| **Hazard Medium (P3)** | `#0284c7` / `#38bdf8` | General road distress, signboards, crosswalks |
| **Typography** | `Inter`, `Outfit`, or `JetBrains Mono` for telemetry | Modern, legible, mathematical layout |

---

## 5. Frontend Integration Checklist for Your Friend

Your friend can follow this simple, step-by-step checklist to build the UI:

- [ ] **Step 1: Setup Framework:** Initialize a modern React + Vite or Next.js app with TailwindCSS or Vanilla CSS modules.
- [ ] **Step 2: Connect WebSocket:** Hook into `ws://localhost:8000/ws/live` to listen for real-time events (`pothole`, `violation`, `plate`, `metric`).
- [ ] **Step 3: Setup Mapbox / Leaflet Canvas:** Render the interactive map and add layers for vehicle markers and colored defect pins.
- [ ] **Step 4: Build KPI Counter Row:** Fetch initial metrics from `GET /api/stats`.
- [ ] **Step 5: Build PWD Work-Order Docket View:**
  - Call `GET /api/pwd/work-orders` to render the budget card and repair table.
  - Connect the **`🚀 Dispatch Work-Order`** button to `POST /api/pwd/dispatch`.
- [ ] **Step 6: Build Evidence Modal:** Open image crops directly using `http://localhost:8000` + `incident.evidence_image`.
- [ ] **Step 7: Build Video Stream Runner:** Call `POST /api/pipeline/run` with `pothole.mp4` to demo the live pipeline from the browser.
