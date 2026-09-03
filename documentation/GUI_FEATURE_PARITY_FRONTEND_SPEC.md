# 🔄 100% GUI Feature Parity Specification for Frontend
## Exact 1:1 Functional Translation from Desktop GUI (`gui_app.py`) to Web Frontend

**Document Reference:** `SIH-2026-GUI-PARITY`  
**Target:** Frontend Developer  
**Objective:** Replicate **every single capability, interaction, and workflow** that exists in our desktop command center (`gui_app.py`) inside the web frontend.

---

## 🎯 Master Functional Feature Matrix

Below is the complete inventory of all 8 major features developed in our desktop GUI and how the web frontend must implement each one:

| # | Feature in Desktop GUI (`gui_app.py`) | Web Frontend Equivalent | Backend API / WebSocket |
|---|--------------------------------------|-------------------------|--------------------------|
| **1** | **Live Video Stream & Detection Overlays** | HTML5 `<video>` + Canvas Overlay or MJPEG stream | `GET /data/input/{video}` & `WS /ws/live` |
| **2** | **Turn-by-Turn Maneuver HUD (Ribbon)** | Speedometer, Speed Limit, School Beacon, Congestion | `WS /ws/live` (`event_type: "metric"`) |
| **3** | **Interactive Mapbox 4-Layer Map** | Mapbox GL JS / Leaflet canvas with custom markers | `mapbox-gl` with `/ws/live` GPS coords |
| **4** | **Live Forensic Incident Feed** | Real-time sliding event cards with badges & thumbnails | `WS /ws/live` & `GET /api/potholes` |
| **5** | **4-Stage Evidence Inspector Modal** | Modal dialog: Raw photo, Binarized crop, BBox, GPS | `GET /evidence/{filename}` |
| **6** | **15m Spatial Pothole Deduplication** | Clustered map markers with defect count badge | Handled by backend `src/spatial_dedup.py` |
| **7** | **Official PWD Work-Order Docket** | Modal dialog: Budget in ₹ INR, SLA tiers, CSV table | `GET /api/pwd/work-orders` |
| **8** | **1-Click Native Municipal Email Dispatch** | Action button: Dispatches to municipal email with toast | `POST /api/pwd/dispatch` |

---

## 🛠️ Feature-by-Feature Implementation Guide

---

### FEATURE 1: Live Video Stream & Detection Overlays
* **In GUI:** Renders the 1080p camera stream at 30 FPS. Draws colored bounding boxes around vehicles (ByteTrack IDs), pedestrians, potholes (with area $m^2$ and depth $mm$), medians, and signboards.
* **In Web Frontend:**
  1. Use standard HTML5 `<video>` pointing to `http://localhost:8000/data/input/pothole.mp4` (or `dividers_.mp4`).
  2. Overlay an HTML5 `<canvas>` directly over the video with `position: absolute`.
  3. When WebSocket receives detection bounding boxes (`[x1, y1, x2, y2]`), draw them on the canvas:
     - **Green (`#10b981`):** Vehicles with Track ID (e.g., `Car #42`).
     - **Red (`#ef4444`):** P1 Critical Potholes (e.g., `Pothole: 0.09m² | 55mm`).
     - **Yellow (`#f59e0b`):** Concrete Median Curbs.
     - **Cyan (`#06b6d4`):** Pedestrians with crossing vectors.

---

### FEATURE 2: Turn-by-Turn Maneuver HUD (Top Ribbon)
* **In GUI:** Sits directly above the video. Shows live speed, speed limit sign, school zone amber warning, and traffic density.
* **In Web Frontend:**
  Create a `<ManeuverHUD />` component connected to WebSocket `event_type === "metric"`:
  ```json
  {
    "event_type": "metric",
    "speed_kmh": 32.5,
    "speed_limit_kmh": 40,
    "is_school_zone": true,
    "congestion_index": 45.0,
    "latitude": 13.082716,
    "longitude": 80.270708
  }
  ```
  - **Speed Gauge:** Display `data.speed_kmh` (e.g., `32 km/h`).
  - **Speed Limit Sign:** Red circular badge with `data.speed_limit_kmh` (e.g., `40`).
  - **School Zone Beacon:** If `data.is_school_zone === true`, flash an amber warning badge:  
    `⚠️ SCHOOL ZONE DETECTED (<150m) · SPEED BOUNDED TO 25 KM/H`.
  - **Traffic Density Bar:** Progress bar showing `data.congestion_index` ($0\% - 100\%$).

---

### FEATURE 3: Mapbox WebGL Interactive Map with 4 Layers
* **In GUI:** Embedded QtWebEngine running Mapbox GL JS with smooth bus tracking, GPS breadcrumbs, and 4 style buttons.
* **In Web Frontend:**
  Install `mapbox-gl` (`npm install mapbox-gl`):
  ```javascript
  import mapboxgl from 'mapbox-gl';
  mapboxgl.accessToken = 'your_mapbox_token_here';

  const map = new mapboxgl.Map({
    container: 'map',
    style: 'mapbox://styles/mapbox/streets-v12', // Default
    center: [80.270708, 13.082716],
    zoom: 15
  });
  ```
  - **4-Layer Style Switcher Buttons:**
    1. `Streets`: `map.setStyle('mapbox://styles/mapbox/streets-v12')`
    2. `Satellite`: `map.setStyle('mapbox://styles/mapbox/satellite-streets-v12')`
    3. `Dark Tactical`: `map.setStyle('mapbox://styles/mapbox/dark-v11')`
    4. `Polar Radar`: `map.setStyle('mapbox://styles/mapbox/navigation-night-v1')`
  - **Live Bus Marker:** Create a custom pulsing bus icon that updates via:
    ```javascript
    busMarker.setLngLat([data.longitude, data.latitude]);
    map.easeTo({ center: [data.longitude, data.latitude], duration: 300 });
    ```
  - **Color-Coded Defect Pins:**
    - 🔴 Red: P1 Critical Potholes (`#dc2626`)
    - 🟠 Amber: P2 High Defects / Medians (`#d97706`)
    - 🔵 Blue: P3 Medium Defects / Crosswalks (`#0284c7`)

---

### FEATURE 4: Live Forensic Incident Feed (Right Panel)
* **In GUI:** A scrollable list on the right showing newly discovered defects as they happen.
* **In Web Frontend:**
  - Create an `<IncidentFeed />` component that prepends items when WebSocket messages arrive:
    ```javascript
    ws.onmessage = (e) => {
      const item = JSON.parse(e.data);
      if (item.event_type !== 'metric') {
        setIncidents((prev) => [item, ...prev]);
      }
    };
    ```
  - Each item displays:
    - Thumbnail: `<img src={"http://localhost:8000" + item.evidence_image} />`
    - Defect Tag: e.g., `Severe Pothole` or `Missing Median`
    - Severity Badge: `P1 - CRITICAL` (Red) or `P2 - HIGH` (Amber)
    - Street Address: e.g., `Anna Salai Corridor`
    - Timestamp: e.g., `23:34:57`

---

### FEATURE 5: 4-Stage Forensic Evidence Inspector Modal
* **In GUI:** Clicking any incident opens `EvidenceInspectorDialog` with 4 evidence panels.
* **In Web Frontend:**
  When an incident card is clicked, open `<EvidenceModal incident={selectedIncident} />`:
  1. **Panel 1 (Raw Snapshot):** Unmodified camera frame.
  2. **Panel 2 (Preprocessed Crop):** High-contrast binarization / depth mask.
  3. **Panel 3 (Forensic Annotation):** Bounding box overlay with confidence score and defect dimensions.
  4. **Panel 4 (Geospatial Metadata):**
     - Exact Latitude / Longitude: `13.082716, 80.270708`
     - Street Name: `Anna Salai, Chennai`
     - **Clickable Google Maps Button:**
       ```jsx
       <a 
         href={`https://maps.google.com/?q=${incident.latitude},${incident.longitude}`}
         target="_blank" 
         rel="noreferrer"
         className="btn-google-maps"
       >
         📍 Open in Google Maps
       </a>
       ```

---

### FEATURE 6: Spatial Pothole Deduplication (15m Geohash)
* **In GUI:** Prevents the same pothole from being counted 50 times across consecutive video frames.
* **In Web Frontend:**
  - The backend (`src/spatial_dedup.py`) **already handles this automatically**.
  - In the frontend UI, you will receive deduplicated unique defects.
  - On the map, you can use Mapbox Clustering (`cluster: true`) to display cluster bubbles if defects are close to each other.

---

### FEATURE 7: Official PWD Work-Order Docket Dashboard
* **In GUI:** Clicking `📋 PWD Work-Order (CSV)` opens the official municipal repair docket.
* **In Web Frontend:**
  Create a `<PwdWorkOrderModal />` that fetches from `GET http://localhost:8000/api/pwd/work-orders`:
  ```json
  {
    "total_orders": 85,
    "total_budget_inr": 251850,
    "total_budget_formatted": "₹251,850 INR",
    "priority_breakdown": {
      "P1 - CRITICAL": 54,
      "P2 - HIGH": 26,
      "P3 - MEDIUM": 5
    },
    "csv_url": "/data/output/PWD_WORK_ORDER_20260903_233457.csv",
    "orders": [...]
  }
  ```
  - **Render 4 Metric Cards:**
    - Total Orders: `85 Work Orders`
    - Estimated Budget: `₹251,850 INR`
    - P1 Critical (24h SLA): `54`
    - P2 High (48h SLA): `26`
    - P3 Medium (7d SLA): `5`
  - **Action Button 1 (Download CSV):**
    ```jsx
    <a href={"http://localhost:8000" + data.csv_url} download className="btn-csv">
      📊 Open in Excel / Download CSV
    </a>
    ```
  - **Itemized Repair Table:** Table rendering all orders with columns:
    `Work_Order_ID`, `Defect_Type`, `IRC_Specification`, `Repair_Action`, `Estimated_Material_Qty`, `Estimated_Cost_INR`, `SLA_Hours`.

---

### FEATURE 8: 1-Click Native Municipal Email Dispatcher
* **In GUI:** A clean emerald button **`🚀 Dispatch Official Work-Order Docket`** transmits the docket to `devadharshan03082006@gmail.com` without asking for any email, then shows a success popup.
* **In Web Frontend:**
  Add this exact button inside `<PwdWorkOrderModal />`:
  ```jsx
  const [dispatching, setDispatching] = useState(false);
  const [statusMessage, setStatusMessage] = useState(null);

  async function handleDispatch() {
    setDispatching(true);
    setStatusMessage("📡 Transmitting official docket to Municipal Authorities...");
    try {
      const res = await fetch("http://localhost:8000/api/pwd/dispatch", { method: "POST" });
      const result = await res.json();
      if (result.status === "SUCCESS") {
        setStatusMessage("✅ Work-Order Docket Successfully Dispatched!");
        // Trigger browser notification or sweetalert toast:
        alert("✅ Official PWD Civil Maintenance Work-Order Docket and IRC Repair Schedule have been successfully dispatched to Municipal Authorities.");
      } else {
        setStatusMessage("⚠️ " + result.message);
      }
    } catch (err) {
      setStatusMessage("⚠️ Network error: " + err.message);
    } finally {
      setDispatching(false);
    }
  }

  return (
    <div className="dispatch-panel">
      <button 
        onClick={handleDispatch} 
        disabled={dispatching} 
        className="btn-dispatch"
      >
        {dispatching ? "📡 Transmitting..." : "🚀 Dispatch Official Work-Order Docket"}
      </button>
      {statusMessage && <p className="status-text">{statusMessage}</p>}
    </div>
  );
  ```

---

## 🚀 Summary Checklist for Full Parity

To verify that the frontend matches the GUI 100%:
- [ ] Video plays with bounding box canvas overlay.
- [ ] HUD displays Speed, Speed Limit, School Zone beacon, and Congestion.
- [ ] Mapbox renders live bus GPS position and defect pins with 4 map layer styles.
- [ ] Incident feed receives live WebSocket cards with thumbnail images.
- [ ] Evidence Inspector Modal opens on card click with Google Maps link.
- [ ] PWD Work-Order dialog displays ₹ INR budget and itemized IRC repair schedule.
- [ ] CSV download button downloads the active docket.
- [ ] 1-Click Dispatch button successfully calls `POST /api/pwd/dispatch` and displays the success toast.
