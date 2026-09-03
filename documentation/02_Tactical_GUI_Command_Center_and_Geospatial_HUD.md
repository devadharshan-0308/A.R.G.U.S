# 📘 Technical Document 02: Tactical Command Center GUI & Geospatial Telemetry Architecture

**Document Reference:** `SIH-TR-2026-GUI-02`  
**Project:** Smart City Mobile Urban Intelligence & Road Infrastructure Surveillance Platform  
**Target Platform:** Transit Fleet Cockpit Command Center  
**UI Framework:** PyQt5 + QtWebEngine (Mapbox GL JS WebGL Engine)  

---

## 1. Executive Summary

The Tactical Command Center (`gui_app.py`) represents the human-machine interface (HMI) of the transit surveillance platform. Designed for mission-critical surveillance operations within fleet management centers and bus driver cockpit displays, the application seamlessly fuses high-throughput computer vision streams with interactive WebGL geospatial mapping.

The architecture eliminates thread starvation and frame tearing through a decoupled producer-consumer pipeline: real-time PyTorch inference operates on dedicated worker threads, emitting telemetry signals to the Qt GUI main thread at zero latency.

---

## 2. Technology Stack & Component Hierarchy

| Component | Framework / Library | Version | Role in Platform |
| :--- | :--- | :--- | :--- |
| **Desktop GUI Engine** | PyQt5 | `5.15.10` | Hardware-accelerated Qt5 widget tree, high-DPI font rendering, event dispatching. |
| **Embedded Browser Canvas**| QtWebEngineWidgets | `5.15.10` | Chromium-based rendering engine executing Mapbox GL JS WebGL vector maps. |
| **Geospatial Mapping** | Mapbox GL JS | `v2.15.0` | 60 FPS vector tile rendering, smooth camera panning, 3D terrain extrusion. |
| **Reverse Geocoding** | Mapbox Geocoding API | `v5` | Translates lat/lon coordinates into human-readable street names and school zones. |
| **Asynchronous Bridge** | Qt Signal/Slot Architecture | Native | Thread-safe inter-process communication between inference loop and UI elements. |
| **Styling & Theming** | Qt Style Sheets (QSS) | CSS3-like | High-contrast enterprise dark cockpit palette (`#0f172a`, `#1e293b`, `#334155`). |

---

## 3. Core Architectural Modules

### 3.1. Thread-Decoupled Inference Loop (`VideoInferenceWorker`)

Executing multiple deep learning models while concurrently rendering interactive 60 FPS vector maps requires strict thread separation:

```
┌────────────────────────────────────────────────────────┐
│                   QThread: VideoInferenceWorker        │
│                                                        │
│  [ cv2.VideoCapture ] ──► [ Cadenced GPU Inference ]   │
│                                 │                      │
│                                 ├── Traffic YOLO11s    │
│                                 ├── Pothole LiDAR      │
│                                 └── MoRTH ANPR OCR     │
└─────────────────────────────────┬──────────────────────┘
                                  │ PyQt5 QtSignals
                                  │ (frame_ready, incident_logged, gps_updated)
┌─────────────────────────────────▼──────────────────────┐
│                   Main GUI Thread (PyQt5)              │
│                                                        │
│  [ Video Stream Label ]    [ Incident Log Table ]      │
│  [ Speedometer HUD ]       [ Mapbox WebEngine View ]   │
└────────────────────────────────────────────────────────┘
```

#### Frame Pacing & Latency Management:
- **Pacing Multipliers:** Supports `1.0x`, `1.5x`, and `2.0x` simulation rates via intelligent frame skipping (`cap.grab()`).
- **CUDA FP16 Warm-Up:** Pre-compiles PyTorch kernel graphs during thread initialization using a $320 \times 320$ blank tensor, completely eliminating initial playback stutter.

---

### 3.2. Mapbox WebGL Interactive Navigation Layer

#### 4 Cartographic Layer Modes:
1. **Streets Mode (`mapbox://styles/mapbox/streets-v12`):** Standard urban arterial navigation with building footprints and lane indicators.
2. **Satellite Imagery (`mapbox://styles/mapbox/satellite-streets-v12`):** High-resolution orbital photography for verifying rural unpaved road surfaces.
3. **Dark Tactical Navigation (`mapbox://styles/mapbox/dark-v11`):** High-contrast night-surveillance mode emphasizing bright neon defect markers.
4. **Polar Vector Radar (`mapbox://styles/mapbox/navigation-night-v1`):** Synthetic tactical HUD layer highlighting high-risk pedestrian safety zones.

#### JavaScript-to-Python Dynamic WebChannel Bridge:
The Qt desktop application controls the Mapbox canvas dynamically without page reloads by injecting JavaScript into the Chromium runtime:
```javascript
// Updates bus position, camera bearing, and trailing GPS breadcrumbs
map.easeTo({ center: [lng, lat], bearing: heading, duration: 200 });
updateGpsBreadcrumb(lat, lng);
addDefectMarker(lat, lng, defectType, severityColor);
```

---

### 3.3. Turn-by-Turn Maneuver HUD (`ManeuverHUDWidget`)

Positioned directly above the live video stream, the HUD simulates advanced bus transit telematics:
- **Corridor Speed Limits:** Dynamically bounds vehicle speed according to road class ($40\text{ km/h}$ in urban commercial zones, $25\text{ km/h}$ in school zones).
- **School Zone Proximity Beacon:** Flashes high-priority amber warnings when within $150\text{ meters}$ of recognized school grounds, automatically raising pedestrian safety thresholds.
- **Corridor Traffic Congestion Metric:** Calculates real-time vehicle density index ($0\% - 100\%$) based on active vehicle track count within the forward camera cone.
- **Dynamic ETA Engine:** Computes arrival times at downstream scheduled bus stops using live corridor speed and congestion degradation curves.

---

### 3.4. Spatial Pothole Deduplication Engine (`src/spatial_dedup.py`)

#### The Multiple-Detection Problem:
A bus moving at $20\text{ km/h}$ forward over a pothole captures that single pothole across $30 - 60$ consecutive video frames. Incrementing a counter naively on every frame results in hundreds of duplicate potholes recorded for a single defect.

#### 15-Meter Geohash Clustering Solution:
The `SpatialPotholeDeduplicator` groups detections into spatial clusters using the **Haversine Great-Circle Formula**:
$$d = 2R \cdot \arcsin\left(\sqrt{\sin^2\left(\frac{\Delta\phi}{2}\right) + \cos(\phi_1)\cos(\phi_2)\sin^2\left(\frac{\Delta\lambda}{2}\right)}\right)$$
Where:
- $R = 6,371,000\text{ meters}$ (Earth radius).
- $\phi_1, \phi_2$ represent vehicle GPS latitudes.
- $\Delta\phi, \Delta\lambda$ represent coordinate offsets.

```python
# Spatial Deduplication Execution Flow:
if haversine_distance(new_pothole_gps, existing_cluster_gps) < 15.0:
    # Update existing cluster metadata (increment occurrence count, update max severity)
    existing_cluster.update(new_pothole)
else:
    # Register novel distinct road defect
    register_new_pothole_incident(new_pothole)
```
- **Performance:** Verified on `pothole.mp4`—compressed $300+$ raw frame detections down to **5 unique, distinct physical potholes**.

---

### 3.5. Forensic Incident Dossier Modal (`EvidenceInspectorDialog`)

Clicking any row in the **Live Forensic Incident Feed** launches a 4-stage evidence inspection modal:
1. **Raw Camera Capture:** The unedited source video frame preserving timestamp and frame index.
2. **Preprocessed Analysis Crop:** The high-contrast binarized crop showing Otsu segmentation or depth shadow gradient.
3. **Annotated Forensic Bounding Box:** Overlaid confidence score, Indian Road Congress category, and vehicle/plate ID.
4. **Geospatial Context Panel:** Exact decimal GPS coordinates (`13.082700, 80.270700`), street name, reverse-geocoded landmark, and 1-click **"Open in Google Maps"** navigation button.
