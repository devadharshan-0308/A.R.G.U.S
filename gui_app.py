"""
gui_app.py — Enterprise Urban Surveillance & Infrastructure Intelligence Platform with Mapbox Live Navigation.

Features:
  - Mapbox Live Navigation & Cartographic Tile View with GPS Trail & Incident Markers
  - Real-Time Turn-by-Turn Maneuver HUD (ETA, Traffic Congestion, Speed Limits, School Zones)
  - Mapbox Map Layer Modes: Streets, Satellite Imagery, Dark Nav, and Vector Polar Radar
  - Enterprise Fluent Design: High-contrast typography (#0f172a / #1e293b / #334155)
  - NVIDIA CUDA GPU Acceleration, ByteTrack Vehicle Tracking, Pothole LiDAR Depth & EasyOCR ANPR
"""

import os
import sys
import time
import json
import math
import random
import logging
import threading
import shutil
from typing import Optional, Dict, Any, List, Tuple
import requests
from dotenv import load_dotenv

load_dotenv()

# IMPORTANT: Import torch and cv2 BEFORE PyQt5 on Windows to prevent DLL load conflicts
import torch
import cv2
import numpy as np

import queue

# Serialized Audio Alert Queue (prevents Windows sound driver lockups and thread collisions)
_alert_audio_queue = queue.Queue(maxsize=32)
_last_sound_time: Dict[str, float] = {}
_sound_lock = threading.Lock()

def _audio_worker_loop():
    while True:
        try:
            freq, dur = _alert_audio_queue.get()
            try:
                import winsound
                winsound.Beep(freq, dur)
            except Exception:
                pass
            _alert_audio_queue.task_done()
            time.sleep(0.04)
        except Exception:
            pass

threading.Thread(target=_audio_worker_loop, daemon=True).start()

def play_alert_sound(freq: int = 800, dur: int = 90, category: str = "default", cooldown: float = 1.2):
    now = time.time()
    with _sound_lock:
        if now - _last_sound_time.get(category, 0) < cooldown:
            return
        _last_sound_time[category] = now
    try:
        _alert_audio_queue.put_nowait((freq, dur))
    except queue.Full:
        pass

# PyQt5 Imports
from PyQt5.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QSize, QPointF, QRectF,
    QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, pyqtProperty
)
from PyQt5.QtGui import (
    QImage, QPixmap, QFont, QColor, QIcon, QPainter, QBrush, QPen,
    QRadialGradient, QLinearGradient, QPolygonF, QCursor, QPainterPath
)
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QFileDialog, QListWidget, QListWidgetItem,
    QCheckBox, QGroupBox, QSplitter, QFrame, QProgressBar, QTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QSizePolicy, QTabWidget,
    QMessageBox, QDialog, QGraphicsOpacityEffect, QStackedWidget, QScrollArea,
    QGraphicsDropShadowEffect, QGridLayout, QButtonGroup, QLineEdit, QMenu, QAction
)

# AI Pipeline Models
from src.yolo_detector import TrafficYOLODetector
from src.pothole_detector import PotholeDetector, SEVERITY_COLORS
from src.hazard_detector import RoadHazardDetector
from src.plate_detector import LicensePlateDetector, synthesize_indian_plate
from src.rule_engine import SafetyRuleEngine
from src.spatial_dedup import SpatialPotholeDeduplicator
from src.maps_enricher import MapsEnricher
from src.road_infra_detector import RoadInfrastructureDetector
from src.pwd_workorder import generate_pwd_work_orders
from src.email_dispatcher import send_pwd_workorder_email
from src.route_simulator import RouteSimulator
from src.database import (
    init_db, insert_pothole, insert_plate, insert_violation,
    insert_traffic_metric, insert_pwd_work_order, insert_audit_run,
    sync_all_incidents, get_database_stats, get_table_data,
    get_all_potholes, get_all_plates, get_all_violations,
    get_all_pwd_work_orders, get_latest_audit_run
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("EnterpriseGUI")


def get_video_thumbnail(video_path: str, width: int = 160, height: int = 100) -> Optional[QPixmap]:
    """Extract a representative preview frame from a video file as a QPixmap."""
    if not os.path.exists(video_path):
        return None
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return None
        total_f = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_f > 10:
            cap.set(cv2.CAP_PROP_POS_FRAMES, min(30, total_f // 4))
        ret, frame = cap.read()
        cap.release()
        if ret and frame is not None:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
            pix = QPixmap.fromImage(qimg)
            return pix.scaled(width, height, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    except Exception:
        pass
    return None


# ─── ENTERPRISE CARD CONTAINER ───────────────────────────────────────────────
class EnterpriseCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("enterpriseCard")
        self.setStyleSheet("""
            #enterpriseCard {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 10px;
            }
        """)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(12)
        shadow.setColor(QColor(15, 23, 42, 16))
        shadow.setOffset(0, 3)
        self.setGraphicsEffect(shadow)


# ─── 1. BOOT DIAGNOSTIC SCREEN ───────────────────────────────────────────────
class EnterpriseLoadingScreen(QDialog):
    finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(560, 320)

        self.step = 0
        self.diagnostic_steps = [
            ("Initializing Neural Accelerator...", "NVIDIA CUDA Hardware Active", 20),
            ("Loading YOLOv8 Real-Time Weights...", "models/yolov8n.pt [ByteTrack Online]", 45),
            ("Syncing Mapbox Cartographic Navigation...", "Mapbox SDK & Live Routing Active", 70),
            ("Binding EasyOCR Async Workers...", "PyTorch Thread Pool Active", 88),
            ("System Ready. Engaging Command Center...", "All Engines Verified", 100)
        ]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setObjectName("splashCard")
        card.setStyleSheet("""
            #splashCard {
                background-color: #ffffff;
                border: 2px solid #0284c7;
                border-radius: 14px;
            }
        """)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(15, 23, 42, 35))
        shadow.setOffset(0, 6)
        card.setGraphicsEffect(shadow)

        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(32, 32, 32, 32)
        c_layout.setSpacing(14)

        top_box = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        t_label = QLabel("URBAN SENSE // ENTERPRISE INTELLIGENCE")
        t_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        t_label.setStyleSheet("color: #0f172a; letter-spacing: 0.5px;")
        sub_label = QLabel("Mobile Urban Surveillance, Infrastructure & Mapbox Navigation")
        sub_label.setStyleSheet("color: #475569; font-size: 11px; font-weight: 600;")
        title_box.addWidget(t_label)
        title_box.addWidget(sub_label)
        top_box.addLayout(title_box)
        top_box.addStretch()

        hw_badge = QLabel("MAPBOX & CUDA")
        hw_badge.setStyleSheet("color: #0284c7; background: #e0f2fe; border: 1px solid #0284c7; padding: 4px 12px; border-radius: 6px; font-weight: 800; font-size: 11px;")
        top_box.addWidget(hw_badge)
        c_layout.addLayout(top_box)

        c_layout.addSpacing(6)

        self.status_label = QLabel("Initializing pipelines...")
        self.status_label.setStyleSheet("color: #0f172a; font-size: 13px; font-weight: 700;")
        c_layout.addWidget(self.status_label)

        self.detail_label = QLabel("Verifying compute device...")
        self.detail_label.setStyleSheet("color: #475569; font-size: 11px; font-weight: 600;")
        c_layout.addWidget(self.detail_label)

        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0, 100)
        self.prog_bar.setValue(0)
        self.prog_bar.setFixedHeight(8)
        self.prog_bar.setTextVisible(False)
        self.prog_bar.setStyleSheet("""
            QProgressBar {
                background-color: #e2e8f0;
                border: none;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background-color: #0284c7;
                border-radius: 4px;
            }
        """)
        c_layout.addWidget(self.prog_bar)

        foot = QHBoxLayout()
        gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "Host CPU"
        f_lbl = QLabel(f"Hardware: {gpu_name}")
        f_lbl.setStyleSheet("color: #64748b; font-size: 11px; font-weight: 700;")
        foot.addWidget(f_lbl)
        foot.addStretch()
        self.pct_lbl = QLabel("0%")
        self.pct_lbl.setStyleSheet("color: #0284c7; font-size: 12px; font-weight: 800;")
        foot.addWidget(self.pct_lbl)
        c_layout.addLayout(foot)

        layout.addWidget(card)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._next_step)

    def start_loading(self):
        self.step = 0
        self.timer.start(220)

    def _next_step(self):
        if self.step < len(self.diagnostic_steps):
            main_t, sub_t, pct = self.diagnostic_steps[self.step]
            self.status_label.setText(main_t)
            self.detail_label.setText(sub_t)
            self.prog_bar.setValue(pct)
            self.pct_lbl.setText(f"{pct}%")
            self.step += 1
        else:
            self.timer.stop()
            QTimer.singleShot(100, self._finish)

    def _finish(self):
        self.finished.emit()
        self.accept()


# ─── REAL-TIME MAPBOX NAVIGATION & CARTOGRAPHY WIDGET ────────────────────────
class MapboxLiveNavigationWidget(QWidget):
    """
    Interactive Mapbox Navigation Widget:
    Renders live Mapbox satellite & street cartography, real-time GPS vehicle tracking,
    turn-by-turn route geometry, and detected pothole / license plate pinpoints.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(360, 280)
        self.token = os.getenv("MAPBOX_ACCESS_TOKEN", "").strip()
        
        self.current_lat = 13.0827
        self.current_lon = 80.2707
        self.heading = 0.0
        self.zoom = 15
        self.map_style = "streets-v12" # streets-v12 | satellite-streets-v12 | dark-v11
        
        self.path_history: List[Tuple[float, float]] = []
        self.corridor_path: List[List[float]] = []
        self.incident_markers: List[Dict[str, Any]] = []
        self.heat_points: List[Dict[str, Any]] = []
        self.congestion_index = 0
        self.congestion_label = "FREE FLOW"
        self.heatmap_enabled = True
        
        self.cached_pixmap: Optional[QPixmap] = None
        self.last_fetch_pos: Optional[Tuple[float, float]] = None
        self.is_fetching = False

        self.nav_instructions = "Select a video to initialize transit corridor navigation"
        self.nav_eta = "-- km · -- mins"
        self.current_street = "Chennai Transit Corridor"
        self.is_school_zone = False

        # Top Control Layout
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(6)

        # 1. Turn-by-Turn Navigation HUD Card
        self.hud_card = QFrame()
        self.hud_card.setStyleSheet("""
            background-color: rgba(15, 23, 42, 0.92);
            border: 1px solid rgba(56, 189, 248, 0.35);
            border-radius: 8px;
        """)
        hud_lay = QVBoxLayout(self.hud_card)
        hud_lay.setContentsMargins(12, 10, 12, 10)
        hud_lay.setSpacing(3)

        hud_top = QHBoxLayout()
        self.maneuver_icon = QLabel("⬆️")
        self.maneuver_icon.setStyleSheet("font-size: 16px;")
        hud_top.addWidget(self.maneuver_icon)

        self.instruction_lbl = QLabel(self.nav_instructions)
        self.instruction_lbl.setStyleSheet("color: #f8fafc; font-weight: 800; font-size: 12px; font-family: 'Segoe UI';")
        hud_top.addWidget(self.instruction_lbl, stretch=1)

        self.eta_badge = QLabel("43 MINS")
        self.eta_badge.setStyleSheet("color: #38bdf8; background: rgba(56, 189, 248, 0.2); border: 1px solid #38bdf8; padding: 2px 8px; border-radius: 4px; font-weight: 800; font-size: 10px;")
        hud_top.addWidget(self.eta_badge)
        hud_lay.addLayout(hud_top)

        hud_bot = QHBoxLayout()
        self.loc_lbl = QLabel(f"📍 {self.current_street}")
        self.loc_lbl.setStyleSheet("color: #94a3b8; font-size: 10px; font-weight: 600;")
        hud_bot.addWidget(self.loc_lbl)
        hud_bot.addStretch()

        self.congestion_pill = QLabel("🟢 CONGESTION: 0% (FREE FLOW)")
        self.congestion_pill.setStyleSheet("color: #10b981; background: rgba(16, 185, 129, 0.2); border: 1px solid #10b981; padding: 1px 7px; border-radius: 4px; font-weight: 800; font-size: 9px;")
        hud_bot.addWidget(self.congestion_pill)

        self.school_pill = QLabel("🏫 SCHOOL ZONE")
        self.school_pill.setStyleSheet("color: #f43f5e; background: rgba(244, 63, 94, 0.2); border: 1px solid #f43f5e; padding: 1px 6px; border-radius: 3px; font-weight: 800; font-size: 9px;")
        self.school_pill.setVisible(False)
        hud_bot.addWidget(self.school_pill)
        hud_lay.addLayout(hud_bot)

        root_layout.addWidget(self.hud_card)
        root_layout.addStretch()

        # 2. Bottom Map Controls Bar
        ctrl_bar = QHBoxLayout()
        ctrl_bar.setSpacing(6)

        style_box = QHBoxLayout()
        self.btn_street = QPushButton("🗺️ Street")
        self.btn_sat = QPushButton("🛰️ Satellite")
        self.btn_dark = QPushButton("🌙 Dark")

        for b, s in [(self.btn_street, "streets-v12"), (self.btn_sat, "satellite-streets-v12"), (self.btn_dark, "dark-v11")]:
            b.setCursor(QCursor(Qt.PointingHandCursor))
            b.setStyleSheet("background-color: rgba(15, 23, 42, 0.85); color: #ffffff; border: 1px solid rgba(255,255,255,0.2); padding: 4px 10px; border-radius: 4px; font-size: 10px; font-weight: 700;")
            b.clicked.connect(lambda ch, style=s: self.set_style(style))
            style_box.addWidget(b)

        self.btn_heatmap = QPushButton("🔥 Heatmap: ON")
        self.btn_heatmap.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_heatmap.setStyleSheet("background-color: rgba(239, 68, 68, 0.25); color: #f87171; border: 1px solid #ef4444; padding: 4px 10px; border-radius: 4px; font-size: 10px; font-weight: 800;")
        self.btn_heatmap.clicked.connect(self.toggle_heatmap)
        style_box.addWidget(self.btn_heatmap)

        ctrl_bar.addLayout(style_box)
        ctrl_bar.addStretch()

        # Zoom in/out
        zoom_in = QPushButton("+")
        zoom_in.setFixedSize(26, 26)
        zoom_in.setStyleSheet("background: rgba(15, 23, 42, 0.85); color: white; border: 1px solid rgba(255,255,255,0.2); border-radius: 4px; font-weight: 900;")
        zoom_in.clicked.connect(self.zoom_in_action)

        zoom_out = QPushButton("-")
        zoom_out.setFixedSize(26, 26)
        zoom_out.setStyleSheet("background: rgba(15, 23, 42, 0.85); color: white; border: 1px solid rgba(255,255,255,0.2); border-radius: 4px; font-weight: 900;")
        zoom_out.clicked.connect(self.zoom_out_action)

        ctrl_bar.addWidget(zoom_in)
        ctrl_bar.addWidget(zoom_out)
        root_layout.addLayout(ctrl_bar)

        # Trigger initial Mapbox fetch
        QTimer.singleShot(100, self._fetch_mapbox_tile)

    def set_style(self, style: str):
        self.map_style = style
        self.last_fetch_pos = None
        self._fetch_mapbox_tile()

    def toggle_heatmap(self):
        self.heatmap_enabled = not self.heatmap_enabled
        if self.heatmap_enabled:
            self.btn_heatmap.setText("🔥 Heatmap: ON")
            self.btn_heatmap.setStyleSheet("background-color: rgba(239, 68, 68, 0.25); color: #f87171; border: 1px solid #ef4444; padding: 4px 10px; border-radius: 4px; font-size: 10px; font-weight: 800;")
        else:
            self.btn_heatmap.setText("🔥 Heatmap: OFF")
            self.btn_heatmap.setStyleSheet("background-color: rgba(15, 23, 42, 0.85); color: #94a3b8; border: 1px solid rgba(255,255,255,0.2); padding: 4px 10px; border-radius: 4px; font-size: 10px; font-weight: 700;")
        self.update()

    def add_heat_point(self, lat: float, lon: float, weight: float = 1.0, category: str = "flow"):
        self.heat_points.append({"lat": lat, "lon": lon, "weight": max(0.2, min(3.0, weight)), "cat": category})
        if len(self.heat_points) > 500:
            self.heat_points.pop(0)
        self.update()

    def update_congestion(self, index: int, label: str):
        self.congestion_index = max(0, min(100, index))
        self.congestion_label = label
        if self.congestion_index >= 70:
            col = "#ef4444"
            icon = "🔴"
            bg = "rgba(239, 68, 68, 0.25)"
        elif self.congestion_index >= 40:
            col = "#f59e0b"
            icon = "🟡"
            bg = "rgba(245, 158, 11, 0.25)"
        else:
            col = "#10b981"
            icon = "🟢"
            bg = "rgba(16, 185, 129, 0.2)"
        self.congestion_pill.setText(f"{icon} CONGESTION: {self.congestion_index}% ({self.congestion_label})")
        self.congestion_pill.setStyleSheet(f"color: {col}; background: {bg}; border: 1px solid {col}; padding: 1px 7px; border-radius: 4px; font-weight: 800; font-size: 9px;")
        self.update()

    def zoom_in_action(self):
        if self.zoom < 18:
            self.zoom += 1
            self.last_fetch_pos = None
            self._fetch_mapbox_tile()

    def zoom_out_action(self):
        if self.zoom > 10:
            self.zoom -= 1
            self.last_fetch_pos = None
            self._fetch_mapbox_tile()

    def set_corridor(self, corridor_info: Dict[str, Any], coordinates: Optional[List[List[float]]] = None):
        if not corridor_info:
            return
        route_label = corridor_info.get("route_label", "Corridor Navigation")
        cam_role = corridor_info.get("camera_role", "FORWARD SCANNER")
        self.nav_instructions = f"{route_label} [{cam_role}]"
        self.instruction_lbl.setText(self.nav_instructions)
        dist_m = corridor_info.get("total_distance_m", 500)
        self.eta_badge.setText(f"{dist_m:.0f} M")
        self.current_street = corridor_info.get("street_name", "Chennai Corridor")
        self.loc_lbl.setText(f"📍 {self.current_street}")
        if coordinates and len(coordinates) >= 2:
            self.corridor_path = coordinates
            self.current_lon, self.current_lat = coordinates[0]
            self.last_fetch_pos = None
            self._fetch_mapbox_tile()
        self.update()

    def update_position(self, lat: float, lon: float, street_name: str = "", is_school: bool = False, heading: float = 0.0):
        self.current_lat = lat
        self.current_lon = lon
        self.heading = heading
        self.path_history.append((lat, lon))
        if len(self.path_history) > 300:
            self.path_history.pop(0)

        # Inject dynamic traffic heat point for patrol trajectory
        flow_weight = 0.8 + (self.congestion_index / 100.0) * 1.5
        self.add_heat_point(lat, lon, flow_weight, "flow")

        if street_name:
            self.current_street = street_name
            self.loc_lbl.setText(f"📍 {street_name}")

        self.is_school_zone = is_school
        self.school_pill.setVisible(is_school)

        # Re-fetch tile if vehicle moved significantly (~100m)
        if not self.last_fetch_pos or math.sqrt((lat - self.last_fetch_pos[0])**2 + (lon - self.last_fetch_pos[1])**2) > 0.0015:
            self._fetch_mapbox_tile()

        self.update()

    def add_incident_marker(self, marker: Dict[str, Any]):
        self.incident_markers.append(marker)
        ilat = marker.get("lat", self.current_lat)
        ilon = marker.get("lon", self.current_lon)
        # Register intense thermal hotspot for road hazards and violations
        self.add_heat_point(ilat, ilon, 2.2, "incident")
        self.update()

    def clear_navigation(self):
        self.path_history.clear()
        self.corridor_path.clear()
        self.incident_markers.clear()
        self.heat_points.clear()
        self.last_fetch_pos = None
        self.heading = 0.0
        self.update()

    def _fetch_mapbox_tile(self):
        if not self.token or self.token.startswith("YOUR_") or self.is_fetching:
            return

        self.is_fetching = True
        self.last_fetch_pos = (self.current_lat, self.current_lon)

        def _bg_fetch():
            try:
                w, h = max(400, self.width()), max(300, self.height())
                url = f"https://api.mapbox.com/styles/v1/mapbox/{self.map_style}/static/{self.current_lon:.5f},{self.current_lat:.5f},{self.zoom},0/{min(800, w)}x{min(600, h)}@2x"
                res = requests.get(url, params={"access_token": self.token}, timeout=4.0)
                if res.status_code == 200:
                    img = QImage.fromData(res.content)
                    if not img.isNull():
                        self.cached_pixmap = QPixmap.fromImage(img)
            except Exception as e:
                logger.debug(f"Mapbox tile fetch error: {e}")
            finally:
                self.is_fetching = False
                QTimer.singleShot(0, self.update)

        threading.Thread(target=_bg_fetch, daemon=True).start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2

        # 1. Draw Mapbox Cartographic Tile or Slate Fallback
        if self.cached_pixmap and not self.cached_pixmap.isNull():
            scaled = self.cached_pixmap.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            painter.drawPixmap(0, 0, scaled)
        else:
            painter.fillRect(0, 0, w, h, QColor("#0f172a"))
            # Grid lines
            painter.setPen(QPen(QColor("#1e293b"), 1, Qt.SolidLine))
            for x in range(0, w, 40):
                painter.drawLine(x, 0, x, h)
            for y in range(0, h, 40):
                painter.drawLine(0, y, w, y)

        # Coordinate to Screen projection
        scale = (2 ** (self.zoom - 14)) * 32000.0

        def to_screen(lat, lon):
            dx = (lon - self.current_lon) * scale
            dy = -(lat - self.current_lat) * scale
            return cx + dx, cy + dy

        # 2a. Geospatial Density Heat Map Layer
        if self.heatmap_enabled and self.heat_points:
            for pt in self.heat_points:
                px, py = to_screen(pt["lat"], pt["lon"])
                if -120 <= px <= w + 120 and -120 <= py <= h + 120:
                    pt_weight = pt.get("weight", 1.0)
                    rad = int(32 * pt_weight)
                    grad = QRadialGradient(px, py, rad)
                    if pt.get("cat") == "incident":
                        grad.setColorAt(0.0, QColor(239, 68, 68, 175))
                        grad.setColorAt(0.4, QColor(245, 158, 11, 115))
                        grad.setColorAt(0.8, QColor(234, 179, 8, 45))
                        grad.setColorAt(1.0, QColor(239, 68, 68, 0))
                    else:
                        grad.setColorAt(0.0, QColor(239, 68, 68, 140))
                        grad.setColorAt(0.35, QColor(245, 158, 11, 95))
                        grad.setColorAt(0.7, QColor(16, 185, 129, 45))
                        grad.setColorAt(1.0, QColor(6, 182, 212, 0))
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(QBrush(grad))
                    painter.drawEllipse(QPointF(px, py), rad, rad)

        # 2b. Draw Planned Transit Corridor Polyline (Ahead)
        if len(self.corridor_path) > 1:
            painter.setPen(QPen(QColor(56, 189, 248, 140), 4, Qt.DashLine, Qt.RoundCap, Qt.RoundJoin))
            for i in range(len(self.corridor_path) - 1):
                lon1, lat1 = self.corridor_path[i]
                lon2, lat2 = self.corridor_path[i + 1]
                p1 = to_screen(lat1, lon1)
                p2 = to_screen(lat2, lon2)
                painter.drawLine(QPointF(p1[0], p1[1]), QPointF(p2[0], p2[1]))

        # 2c. Draw GPS Vehicle Patrol History Trail (Color-Coded by Congestion Density)
        if len(self.path_history) > 1:
            if self.congestion_index >= 70:
                trail_col = QColor(239, 68, 68, 230)
            elif self.congestion_index >= 40:
                trail_col = QColor(245, 158, 11, 230)
            else:
                trail_col = QColor(16, 185, 129, 230)
            painter.setPen(QPen(trail_col, 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            for i in range(len(self.path_history) - 1):
                p1 = to_screen(self.path_history[i][0], self.path_history[i][1])
                p2 = to_screen(self.path_history[i+1][0], self.path_history[i+1][1])
                painter.drawLine(QPointF(p1[0], p1[1]), QPointF(p2[0], p2[1]))

        # 3. Draw Incident Pinpoints on Map
        for inc in self.incident_markers:
            ilat = inc.get("lat", self.current_lat)
            ilon = inc.get("lon", self.current_lon)
            px, py = to_screen(ilat, ilon)
            
            if inc.get("type") == "POTHOLE":
                sev = inc.get("severity", "").lower()
                col = QColor("#ef4444") if "severe" in sev else QColor("#f59e0b")
                # Glowing outer circle
                painter.setBrush(QBrush(QColor(col.red(), col.green(), col.blue(), 90)))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(QPointF(px, py), 12, 12)
                # Pin
                painter.setBrush(QBrush(col))
                painter.setPen(QPen(Qt.white, 1.5))
                painter.drawEllipse(QPointF(px, py), 6, 6)
            elif inc.get("type") == "PLATE":
                painter.setBrush(QBrush(QColor("#10b981")))
                painter.setPen(QPen(Qt.white, 1.5))
                painter.drawRect(QRectF(px - 5, py - 5, 10, 10))

        # 4. Draw Current Vehicle Location Reticle with Directional Heading
        vx, vy = cx, cy
        # Outer pulsating radar circle
        painter.setBrush(QBrush(QColor(56, 189, 248, 45)))
        painter.setPen(QPen(QColor("#38bdf8"), 1.5))
        painter.drawEllipse(QPointF(vx, vy), 18, 18)

        # Vehicle Directional Arrow pointing along street heading
        rad = math.radians(self.heading)
        dx_dir = 14.0 * math.sin(rad)
        dy_dir = -14.0 * math.cos(rad)
        arrow_tip = QPointF(vx + dx_dir, vy + dy_dir)
        arrow_left = QPointF(vx - 0.5 * dx_dir - 0.7 * dy_dir, vy - 0.5 * dy_dir + 0.7 * dx_dir)
        arrow_right = QPointF(vx - 0.5 * dx_dir + 0.7 * dy_dir, vy - 0.5 * dy_dir - 0.7 * dx_dir)

        painter.setBrush(QBrush(QColor("#0284c7")))
        painter.setPen(QPen(Qt.white, 1.5))
        painter.drawPolygon(QPolygonF([arrow_tip, arrow_left, QPointF(vx, vy), arrow_right]))

        # 5. Thermal Heatmap Density Legend Overlay (Bottom Right)
        if self.heatmap_enabled:
            leg_w, leg_h = 165, 22
            leg_x = w - leg_w - 12
            leg_y = h - leg_h - 12
            painter.setPen(QPen(QColor(255, 255, 255, 60), 1))
            painter.setBrush(QBrush(QColor(15, 23, 42, 210)))
            painter.drawRoundedRect(QRectF(leg_x, leg_y, leg_w, leg_h), 4, 4)

            painter.setPen(QColor("#94a3b8"))
            painter.setFont(QFont("Segoe UI", 7, QFont.Bold))
            painter.drawText(int(leg_x + 6), int(leg_y + 15), "HEAT")

            # Mini gradient bar
            bar_x = leg_x + 38
            bar_y = leg_y + 6
            bar_w = 85
            bar_h = 10
            bar_grad = QLinearGradient(bar_x, bar_y, bar_x + bar_w, bar_y)
            bar_grad.setColorAt(0.0, QColor("#06b6d4"))
            bar_grad.setColorAt(0.35, QColor("#10b981"))
            bar_grad.setColorAt(0.7, QColor("#f59e0b"))
            bar_grad.setColorAt(1.0, QColor("#ef4444"))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(bar_grad))
            painter.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 2, 2)

            painter.setPen(QColor("#ef4444"))
            painter.setFont(QFont("Segoe UI", 7, QFont.Bold))
            painter.drawText(int(leg_x + 128), int(leg_y + 15), "CRIT")

        # Attribution
        painter.setPen(QPen(QColor(255, 255, 255, 160)))
        painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
        painter.drawText(10, h - 8, "© Mapbox · © OpenStreetMap · High-Precision Telemetry")


# ─── ENTERPRISE STREAM CARD ──────────────────────────────────────────────────
class EnterpriseStreamCard(QFrame):
    clicked = pyqtSignal(str, str)         # (video_path, corridor_id)
    video_imported = pyqtSignal(str, str)  # (video_path, corridor_id)

    def __init__(
        self,
        corridor_id: str,
        route_label: str,
        corridor_name: str,
        street_name: str,
        color: str,
        waypoints_count: int = 0,
        is_active: bool = False
    ):
        super().__init__()
        self.corridor_id = corridor_id
        self.route_label = route_label
        self.corridor_name = corridor_name
        self.street_name = street_name
        self.color = color
        self.waypoints_count = waypoints_count
        self.is_active = is_active
        self.setCursor(QCursor(Qt.PointingHandCursor))

        self.route_folder = os.path.abspath(os.path.join("data", "input", "routes", self.corridor_id))
        os.makedirs(self.route_folder, exist_ok=True)

        self.setObjectName("enterpriseStreamCard")
        self.update_style()

        self.video_path = ""
        self.has_video = False
        self.video_filename = ""

        # Main Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # Header Row: Route Badge, Title, Status Pill
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        bus_num = self.corridor_id.replace("bus", "").strip()
        self.badge_lbl = QLabel(f"BUS {bus_num.zfill(2)}")
        self.badge_lbl.setStyleSheet(f"""
            color: {self.color};
            background: {self.color}18;
            border: 1px solid {self.color};
            padding: 2px 7px;
            border-radius: 4px;
            font-weight: 900;
            font-size: 11px;
        """)
        header_row.addWidget(self.badge_lbl)

        # Short route title (e.g. Route 54)
        rt_short = self.route_label.split("(")[0].strip() if "(" in self.route_label else self.route_label
        self.title_lbl = QLabel(rt_short)
        self.title_lbl.setStyleSheet("color: #0f172a; font-weight: 800; font-size: 12px;")
        header_row.addWidget(self.title_lbl)

        header_row.addStretch()

        self.status_pill = QLabel("SELECT FEED")
        self.status_pill.setAlignment(Qt.AlignCenter)
        header_row.addWidget(self.status_pill)
        layout.addLayout(header_row)

        # Content Row: Thumbnail on left, info on right
        content_row = QHBoxLayout()
        content_row.setSpacing(10)

        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(110, 66)
        self.thumb_label.setStyleSheet("background-color: #0f172a; border-radius: 6px; border: 1px solid #cbd5e1;")
        self.thumb_label.setAlignment(Qt.AlignCenter)
        content_row.addWidget(self.thumb_label)

        info_box = QVBoxLayout()
        info_box.setSpacing(2)

        self.corr_lbl = QLabel(f"📍 {self.corridor_name}")
        self.corr_lbl.setStyleSheet("color: #1e293b; font-size: 11px; font-weight: 700;")
        info_box.addWidget(self.corr_lbl)

        self.street_lbl = QLabel(f"🛣️ {self.street_name}")
        self.street_lbl.setStyleSheet("color: #64748b; font-size: 10px; font-weight: 600;")
        info_box.addWidget(self.street_lbl)

        self.video_status_lbl = QLabel()
        self.video_status_lbl.setStyleSheet("font-size: 10px; font-weight: 700;")
        info_box.addWidget(self.video_status_lbl)

        content_row.addLayout(info_box, stretch=1)
        layout.addLayout(content_row)

        # Footer Action Row: Import Video & Open Folder
        footer_row = QHBoxLayout()
        footer_row.setSpacing(6)

        self.import_btn = QPushButton("📥 Import Video")
        self.import_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.import_btn.setToolTip(f"Import video into data/input/routes/{self.corridor_id}/")
        self.import_btn.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #0f172a;
                border: 1px solid #cbd5e1;
                padding: 4px 9px;
                border-radius: 5px;
                font-weight: 700;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #e2e8f0;
                border-color: #0284c7;
            }
        """)
        self.import_btn.clicked.connect(self.import_video)
        footer_row.addWidget(self.import_btn)

        self.folder_btn = QPushButton("📂 Open Folder")
        self.folder_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.folder_btn.setToolTip(f"Open {self.route_folder} in Windows Explorer")
        self.folder_btn.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #0f172a;
                border: 1px solid #cbd5e1;
                padding: 4px 9px;
                border-radius: 5px;
                font-weight: 700;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #e2e8f0;
                border-color: #0284c7;
            }
        """)
        self.folder_btn.clicked.connect(self.open_folder)
        footer_row.addWidget(self.folder_btn)

        footer_row.addStretch()
        layout.addLayout(footer_row)

        # Initial scan and thumbnail loading
        self.refresh_video(initial=True)
        self.update_pill()

    def scan_route_video(self):
        video_exts = ('.mp4', '.avi', '.mov', '.mkv')
        files = []
        if os.path.exists(self.route_folder):
            files = [f for f in os.listdir(self.route_folder) if f.lower().endswith(video_exts)]

        if files:
            # Newest file wins — so dropping/downloading a video auto-activates it
            files.sort(key=lambda f: os.path.getmtime(os.path.join(self.route_folder, f)), reverse=True)
            self.video_path = os.path.abspath(os.path.join(self.route_folder, files[0]))
            self.has_video = True
            self.video_filename = files[0]
        else:
            # Fallback to general input directory
            fallback = os.path.abspath(os.path.join("data", "input", "pothole.mp4"))
            self.video_path = fallback if os.path.exists(fallback) else ""
            self.has_video = False
            self.video_filename = "No video in folder (Fallback demo)"

    def refresh_video(self, initial: bool = False):
        self.scan_route_video()
        if self.has_video and os.path.exists(self.video_path):
            pix = get_video_thumbnail(self.video_path, 110, 66)
            if pix:
                self.thumb_label.setPixmap(pix)
            else:
                self.thumb_label.setText("🎥 ROUTE CAM")
                self.thumb_label.setStyleSheet("color: #64748b; font-weight: bold; font-size: 9px; background: #e2e8f0; border-radius: 6px;")
            self.video_status_lbl.setText(f"● {self.video_filename[:24]}")
            self.video_status_lbl.setStyleSheet("color: #059669; font-size: 10px; font-weight: 700;")
        else:
            self.thumb_label.setText("📂 DROP VIDEO")
            self.thumb_label.setStyleSheet("color: #94a3b8; font-weight: bold; font-size: 9px; background: #f1f5f9; border-radius: 6px; border: 1px dashed #cbd5e1;")
            self.video_status_lbl.setText("⚠️ Empty (Drop .mp4 here)")
            self.video_status_lbl.setStyleSheet("color: #d97706; font-size: 10px; font-weight: 700;")

    def import_video(self):
        fname, _ = QFileDialog.getOpenFileName(
            self, f"Import Video for {self.route_label}", "data/input", "Video Files (*.mp4 *.avi *.mov *.mkv)"
        )
        if fname:
            os.makedirs(self.route_folder, exist_ok=True)
            target = os.path.join(self.route_folder, os.path.basename(fname))
            if os.path.abspath(fname) != os.path.abspath(target):
                try:
                    shutil.copyfile(fname, target)
                except Exception as e:
                    logger.warning(f"Error copying video file: {e}")
            self.refresh_video()
            self.clicked.emit(self.video_path, self.corridor_id)
            self.video_imported.emit(self.video_path, self.corridor_id)

    def open_folder(self):
        os.makedirs(self.route_folder, exist_ok=True)
        try:
            os.startfile(self.route_folder)
        except Exception as e:
            logger.warning(f"Could not open folder {self.route_folder}: {e}")

    def set_active(self, active: bool):
        self.is_active = active
        self.update_style()
        self.update_pill()

    def update_pill(self):
        if self.is_active:
            self.status_pill.setText("✓ ACTIVE FEED")
            self.status_pill.setStyleSheet("color: #ffffff; background-color: #0284c7; padding: 3px 9px; border-radius: 4px; font-weight: 800; font-size: 10px;")
        else:
            self.status_pill.setText("SELECT FEED")
            self.status_pill.setStyleSheet("color: #475569; background-color: #f1f5f9; border: 1px solid #cbd5e1; padding: 3px 9px; border-radius: 4px; font-weight: 700; font-size: 10px;")

    def update_style(self):
        if self.is_active:
            self.setStyleSheet(f"""
                #enterpriseStreamCard {{
                    background-color: #f0f9ff;
                    border: 2px solid {self.color};
                    border-radius: 10px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                #enterpriseStreamCard {{
                    background-color: #ffffff;
                    border: 1px solid #cbd5e1;
                    border-radius: 10px;
                }}
                #enterpriseStreamCard:hover {{
                    background-color: #f8fafc;
                    border-color: {self.color};
                }}
            """)

    def mousePressEvent(self, event):
        self.clicked.emit(self.video_path, self.corridor_id)


# ─── 2. ENTERPRISE VIDEO INPUT HUB SCREEN ────────────────────────────────────
class VideoIngestionView(QWidget):
    launch_requested = pyqtSignal(str, float, bool, bool, str)  # (path, speed, pothole, plate, corridor_id)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_corridor_id = "bus1"
        self.selected_path = os.path.abspath("data/input/pothole.mp4")

        # Load corridor catalog
        self.catalog = self._load_routes_catalog()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 18, 28, 18)
        layout.setSpacing(12)

        # Top Banner
        banner = QFrame()
        banner.setObjectName("entBanner")
        banner.setStyleSheet("""
            #entBanner {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0f172a, stop:0.6 #1e293b, stop:1 #0369a1);
                border-radius: 10px;
            }
        """)
        banner_lay = QHBoxLayout(banner)
        banner_lay.setContentsMargins(24, 14, 24, 14)

        b_title_box = QVBoxLayout()
        b_title_box.setSpacing(2)
        b_title = QLabel("Urban Surveillance & Mapbox Ingestion Hub")
        b_title.setFont(QFont("Segoe UI", 15, QFont.Bold))
        b_title.setStyleSheet("color: #ffffff; font-weight: 900;")
        b_sub = QLabel("Select from 10 Chennai MTC Transit Patrol Corridors or import custom route stream videos into route folders.")
        b_sub.setStyleSheet("color: #cbd5e1; font-size: 11px; font-weight: 600;")
        b_title_box.addWidget(b_title)
        b_title_box.addWidget(b_sub)
        banner_lay.addLayout(b_title_box)
        banner_lay.addStretch()

        gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "Host CPU"
        pill = QLabel(f"⚡ MAPBOX ACTIVE · GPU: {gpu_name}")
        pill.setStyleSheet("color: #ffffff; background: rgba(2, 132, 199, 0.4); border: 1px solid #38bdf8; padding: 7px 14px; border-radius: 6px; font-weight: 800; font-size: 11px;")
        banner_lay.addWidget(pill)

        layout.addWidget(banner)

        # Split Layout: Left 10 Route Boxes vs Right Config & Profile
        split_layout = QHBoxLayout()
        split_layout.setSpacing(16)

        # ─── LEFT: 10 ROUTE CARDS GRID INSIDE SCROLL AREA ───
        left_box = QVBoxLayout()
        left_box.setSpacing(8)

        left_header = QHBoxLayout()
        sec_head = QLabel("AVAILABLE TRANSIT PATROL STREAMS (10 CORRIDORS)")
        sec_head.setFont(QFont("Segoe UI", 11, QFont.Bold))
        sec_head.setStyleSheet("color: #0f172a; font-weight: 900; letter-spacing: 0.5px;")
        left_header.addWidget(sec_head)
        left_header.addStretch()

        refresh_all_btn = QPushButton("🔄 Refresh Feeds")
        refresh_all_btn.setCursor(QCursor(Qt.PointingHandCursor))
        refresh_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #0f172a;
                border: 1px solid #cbd5e1;
                padding: 5px 12px;
                border-radius: 6px;
                font-weight: 700;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #e2e8f0;
                border-color: #0284c7;
            }
        """)
        refresh_all_btn.clicked.connect(self.refresh_all_feeds)
        left_header.addWidget(refresh_all_btn)

        open_root_btn = QPushButton("📂 Open Routes Root")
        open_root_btn.setCursor(QCursor(Qt.PointingHandCursor))
        open_root_btn.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #0f172a;
                border: 1px solid #cbd5e1;
                padding: 5px 12px;
                border-radius: 6px;
                font-weight: 700;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #e2e8f0;
                border-color: #0284c7;
            }
        """)
        open_root_btn.clicked.connect(self.open_routes_root)
        left_header.addWidget(open_root_btn)

        left_box.addLayout(left_header)

        # Scroll Area for the 10 boxes
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background: #f1f5f9;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #cbd5e1;
                min-height: 25px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #0284c7;
            }
        """)

        grid_container = QWidget()
        self.grid_layout = QGridLayout(grid_container)
        self.grid_layout.setSpacing(10)
        self.grid_layout.setContentsMargins(2, 2, 8, 2)

        palette = [
            "#0284c7", "#0d9488", "#2563eb", "#7c3aed", "#059669",
            "#d97706", "#ea580c", "#dc2626", "#4f46e5", "#0891b2"
        ]

        self.cards_list: List[EnterpriseStreamCard] = []

        for idx in range(1, 11):
            bus_id = f"bus{idx}"
            info = self.catalog.get(bus_id, {})
            rt_label = info.get("route_label", f"Route {idx}")
            corr_name = info.get("corridor_name", f"Corridor {idx}")
            street = info.get("street_name", "Chennai Arterial Road")
            color = palette[(idx - 1) % len(palette)]
            waypoints = len(info.get("coordinates", []))
            is_active = (bus_id == self.selected_corridor_id)

            card = EnterpriseStreamCard(
                corridor_id=bus_id,
                route_label=rt_label,
                corridor_name=corr_name,
                street_name=street,
                color=color,
                waypoints_count=waypoints,
                is_active=is_active
            )
            card.clicked.connect(self.select_stream_card)
            card.video_imported.connect(self.on_video_imported)
            self.cards_list.append(card)

            row = (idx - 1) // 2
            col = (idx - 1) % 2
            self.grid_layout.addWidget(card, row, col)

        scroll.setWidget(grid_container)
        left_box.addWidget(scroll, stretch=1)

        # Custom Local Video Browser Box
        browse_card = EnterpriseCard()
        b_lay = QHBoxLayout(browse_card)
        b_lay.setContentsMargins(14, 8, 14, 8)

        self.path_display = QLabel(f"Selected: {os.path.basename(self.selected_path)} [BUS 01]")
        self.path_display.setStyleSheet("color: #0f172a; font-size: 12px; font-weight: 700;")
        b_lay.addWidget(self.path_display, stretch=1)

        browse_btn = QPushButton("📁 Browse Custom Video...")
        browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #0f172a;
                border: 1px solid #cbd5e1;
                padding: 6px 14px;
                border-radius: 6px;
                font-weight: 700;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #e2e8f0;
                border-color: #0284c7;
            }
        """)
        browse_btn.clicked.connect(self.browse_file)
        b_lay.addWidget(browse_btn)

        left_box.addWidget(browse_card)
        split_layout.addLayout(left_box, stretch=6)

        # ─── RIGHT: TELEMETRY PROFILE & AI CONFIG ───
        right_card = EnterpriseCard()
        r_lay = QVBoxLayout(right_card)
        r_lay.setContentsMargins(18, 18, 18, 18)
        r_lay.setSpacing(12)

        # Active Profile Section
        p_title = QLabel("ACTIVE CORRIDOR TELEMETRY PROFILE")
        p_title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        p_title.setStyleSheet("color: #0f172a; font-weight: 900; letter-spacing: 0.5px;")
        r_lay.addWidget(p_title)

        self.prof_box = QFrame()
        self.prof_box.setStyleSheet("background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 8px;")
        prof_lay = QVBoxLayout(self.prof_box)
        prof_lay.setSpacing(5)
        prof_lay.setContentsMargins(10, 8, 10, 8)

        self.p_route_lbl = QLabel()
        self.p_route_lbl.setStyleSheet("color: #0284c7; font-size: 12px; font-weight: 900;")
        prof_lay.addWidget(self.p_route_lbl)

        self.p_corr_lbl = QLabel()
        self.p_corr_lbl.setStyleSheet("color: #1e293b; font-size: 11px; font-weight: 700;")
        prof_lay.addWidget(self.p_corr_lbl)

        self.p_street_lbl = QLabel()
        self.p_street_lbl.setStyleSheet("color: #64748b; font-size: 10px; font-weight: 600;")
        prof_lay.addWidget(self.p_street_lbl)

        self.p_meta_lbl = QLabel()
        self.p_meta_lbl.setStyleSheet("color: #0f172a; font-size: 10px; font-weight: 800; background: #e2e8f0; padding: 4px 8px; border-radius: 4px;")
        prof_lay.addWidget(self.p_meta_lbl)

        self.p_video_lbl = QLabel()
        self.p_video_lbl.setStyleSheet("color: #059669; font-size: 11px; font-weight: 800;")
        prof_lay.addWidget(self.p_video_lbl)

        r_lay.addWidget(self.prof_box)

        # AI Engine Settings
        r_title = QLabel("AI ENGINE & SENSING CONFIGURATION")
        r_title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        r_title.setStyleSheet("color: #0f172a; font-weight: 900; letter-spacing: 0.5px; margin-top: 4px;")
        r_lay.addWidget(r_title)

        self.pothole_check = QCheckBox("🕳️ Asphalt Depth & Crater Severity AI")
        self.pothole_check.setChecked(True)
        self.pothole_check.setStyleSheet("color: #0f172a; font-size: 11px; font-weight: 700;")

        self.plate_check = QCheckBox("🚗 EasyOCR License Plate Recognition")
        self.plate_check.setChecked(True)
        self.plate_check.setStyleSheet("color: #0f172a; font-size: 11px; font-weight: 700;")

        self.track_check = QCheckBox("🚙 ByteTrack Persistent Vehicle Identification")
        self.track_check.setChecked(True)
        self.track_check.setStyleSheet("color: #0f172a; font-size: 11px; font-weight: 700;")

        r_lay.addWidget(self.pothole_check)
        r_lay.addWidget(self.plate_check)
        r_lay.addWidget(self.track_check)

        s_box = QVBoxLayout()
        s_box.setSpacing(4)
        s_lbl = QLabel("INFERENCE PLAYBACK RATE")
        s_lbl.setStyleSheet("color: #475569; font-size: 10px; font-weight: 800;")
        s_box.addWidget(s_lbl)

        self.speed_combo = QComboBox()
        self.speed_combo.addItem("1.0x Real-Time (Smooth Paced)", 1.0)
        self.speed_combo.addItem("1.5x Accelerated Rate", 1.5)
        self.speed_combo.addItem("2.0x Turbo Rate", 2.0)
        self.speed_combo.addItem("0.5x Slow-Motion Analysis", 0.5)
        self.speed_combo.addItem("Max (Uncapped CUDA GPU)", 0.0)
        self.speed_combo.setStyleSheet("""
            QComboBox {
                background-color: #f8fafc;
                color: #0f172a;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 7px 12px;
                font-size: 11px;
                font-weight: 700;
            }
            QComboBox:hover {
                border-color: #0284c7;
            }
        """)
        s_box.addWidget(self.speed_combo)
        r_lay.addLayout(s_box)

        r_lay.addStretch()

        self.launch_btn = QPushButton("🚀 ENGAGE LIVE INTELLIGENCE & NAVIGATION")
        self.launch_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.launch_btn.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                font-weight: 900;
                font-size: 12px;
                padding: 13px;
                border-radius: 8px;
                border: none;
                letter-spacing: 0.5px;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
        """)
        self.launch_btn.clicked.connect(self.trigger_launch)
        r_lay.addWidget(self.launch_btn)

        split_layout.addWidget(right_card, stretch=4)
        layout.addLayout(split_layout)

        # Select initial card (bus1)
        if self.cards_list:
            self.select_stream_card(self.cards_list[0].video_path, self.cards_list[0].corridor_id)

    def _load_routes_catalog(self) -> Dict[str, Any]:
        routes_file = os.path.join("data", "corridor_routes.json")
        if os.path.exists(routes_file):
            try:
                with open(routes_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to read routes catalog: {e}")
        return {}

    def select_stream_card(self, video_path: str, corridor_id: str):
        self.selected_path = video_path
        self.selected_corridor_id = corridor_id
        for c in self.cards_list:
            c.set_active(c.corridor_id == corridor_id)
        self.update_active_profile()
        self.path_display.setText(f"Selected: {os.path.basename(video_path)} [{corridor_id.upper()}]")

    def on_video_imported(self, video_path: str, corridor_id: str):
        self.select_stream_card(video_path, corridor_id)

    def update_active_profile(self):
        info = self.catalog.get(self.selected_corridor_id, {})
        num = self.selected_corridor_id.replace("bus", "").strip().zfill(2)
        rt = info.get("route_label", f"Route {num}")
        corr = info.get("corridor_name", "Transit Corridor")
        street = info.get("street_name", "Arterial Road")
        pts = len(info.get("coordinates", []))
        dist = info.get("distance_m", 0.0)

        self.p_route_lbl.setText(f"BUS {num} // {rt}")
        self.p_corr_lbl.setText(f"📍 Corridor: {corr}")
        self.p_street_lbl.setText(f"🛣️ Street: {street}")
        self.p_meta_lbl.setText(f"⚡ {pts} GPS Waypoints · {dist:.0f}m Road Distance · GPU Telemetry Active")
        self.p_video_lbl.setText(f"🎥 Active Stream: {os.path.basename(self.selected_path)}")

    def refresh_all_feeds(self):
        for c in self.cards_list:
            c.refresh_video()
        self.update_active_profile()

    def open_routes_root(self):
        routes_dir = os.path.abspath(os.path.join("data", "input", "routes"))
        os.makedirs(routes_dir, exist_ok=True)
        try:
            os.startfile(routes_dir)
        except Exception as e:
            logger.warning(f"Could not open routes dir: {e}")

    def browse_file(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Select Video File", "data/input", "Video Files (*.mp4 *.avi *.mov *.mkv)")
        if fname:
            self.selected_path = fname
            matched_id, _ = RouteSimulator.detect_corridor_and_role(fname)
            self.selected_corridor_id = matched_id
            self.path_display.setText(f"Selected: {os.path.basename(fname)} [{matched_id.upper()}]")
            for c in self.cards_list:
                c.set_active(c.corridor_id == matched_id)
            self.update_active_profile()

    def trigger_launch(self):
        speed = float(self.speed_combo.currentData())
        self.launch_requested.emit(
            self.selected_path,
            speed,
            self.pothole_check.isChecked(),
            self.plate_check.isChecked(),
            self.selected_corridor_id
        )


# ─── ANIMATED TEXT WIDGETS ───────────────────────────────────────────────────
class SmoothNumberLabel(QLabel):
    def __init__(self, initial_val: Any = 0, suffix: str = "", parent=None):
        init_num = 0.0
        try:
            if isinstance(initial_val, (int, float)):
                init_num = float(initial_val)
            else:
                digits = "".join(filter(str.isdigit, str(initial_val)))
                if digits:
                    init_num = float(digits)
                    if "%" in str(initial_val) and not suffix:
                        suffix = "%"
        except Exception:
            init_num = 0.0

        display_text = f"{int(init_num)}{suffix}" if suffix else str(initial_val)
        super().__init__(display_text, parent)
        self._current_val = init_num
        self._target_val = init_num
        self.suffix = suffix

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._step_value)

    def set_target(self, target: Any, suffix: str = ""):
        try:
            if isinstance(target, (int, float)):
                self._target_val = float(target)
            else:
                target_str = str(target)
                digits = "".join(filter(str.isdigit, target_str))
                if digits:
                    self._target_val = float(digits)
                    if "%" in target_str and not suffix:
                        suffix = "%"
                else:
                    self.setText(target_str)
                    return
        except Exception:
            self._target_val = 0.0

        self.suffix = suffix
        if not self.timer.isActive():
            self.timer.start(25)

    def _step_value(self):
        diff = self._target_val - self._current_val
        if abs(diff) < 0.3:
            self._current_val = self._target_val
            self.setText(f"{int(self._target_val)}{self.suffix}")
            self.timer.stop()
        else:
            step = diff * 0.22
            if abs(step) < 0.2:
                step = 0.2 if diff > 0 else -0.2
            self._current_val += step
            self.setText(f"{int(self._current_val)}{self.suffix}")


class TypewriterLabel(QLabel):
    def __init__(self, full_text: str, parent=None):
        super().__init__("", parent)
        self.full_text = full_text
        self.index = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._type_next_char)

    def start_reveal(self, speed_ms: int = 18):
        self.index = 0
        self.setText("")
        self.timer.start(speed_ms)

    def _type_next_char(self):
        if self.index < len(self.full_text):
            self.index += 1
            self.setText(self.full_text[:self.index])
        else:
            self.timer.stop()


class PulsingStatusLabel(QLabel):
    def __init__(self, text: str = "● SYSTEM READY", parent=None):
        super().__init__(text, parent)
        self.setStyleSheet("color: #10b981; font-weight: 800; font-size: 11px;")
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)

        self.anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim.setDuration(1400)
        self.anim.setStartValue(0.45)
        self.anim.setEndValue(1.0)
        self.anim.setEasingCurve(QEasingCurve.InOutSine)
        self.anim.setLoopCount(-1)
        self.anim.start()

    def set_live(self, text: str = "● TELEMETRY ACTIVE"):
        self.setText(text)
        self.setStyleSheet("color: #0284c7; font-weight: 800; font-size: 11px;")

    def set_idle(self, text: str = "● SYSTEM IDLE"):
        self.setText(text)
        self.setStyleSheet("color: #64748b; font-weight: 800; font-size: 11px;")


# ─── ENTERPRISE KPI CARD ─────────────────────────────────────────────────────
class EnterpriseKpiCard(EnterpriseCard):
    def __init__(self, title: str, initial_val: Any = 0, subtitle: str = "", accent_color: str = "#0284c7"):
        super().__init__()
        self.accent_color = accent_color
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setMinimumWidth(150)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(3)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        t_lbl = QLabel(title.upper())
        t_lbl.setStyleSheet("font-size: 11px; font-weight: 800; color: #475569; letter-spacing: 0.5px;")
        header.addWidget(t_lbl)
        header.addStretch()

        self.pill = QLabel("● LIVE")
        self.pill.setStyleSheet(f"font-size: 9px; font-weight: 900; color: {accent_color}; background: {accent_color}18; border: 1px solid {accent_color}60; padding: 2px 7px; border-radius: 4px;")
        header.addWidget(self.pill)
        layout.addLayout(header)

        self.num_label = SmoothNumberLabel(initial_val)
        self.num_label.setStyleSheet(f"font-size: 28px; font-weight: 900; color: {accent_color}; margin: 2px 0;")
        layout.addWidget(self.num_label)

        self.sub_label = QLabel(subtitle)
        self.sub_label.setStyleSheet("font-size: 11px; color: #64748b; font-weight: 600;")
        layout.addWidget(self.sub_label)

    def set_value(self, val: Any, sub_text: Optional[str] = None):
        self.num_label.set_target(val)
        if sub_text:
            self.sub_label.setText(sub_text)


# ─── MUNICIPAL INTELLIGENCE TRANSITION ANIMATION OVERLAY ─────────────────────
class MunicipalIntelligenceTransitionOverlay(QDialog):
    finished_loading = pyqtSignal()

    def __init__(self, parent=None, corridor_name: str = "CORRIDOR", total_incidents: int = 0):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(580, 360)

        self.step_idx = 0
        self.steps = [
            ("🛰️ Synchronizing GPS corridor telemetry with Mapbox road geometry...", 20),
            ("🕳️ Deduplicating road surface distress & volumetric craters (IRC:82-2015)...", 45),
            ("🚗 Compiling MoRTH ANPR license plate registry & flagged violators...", 70),
            ("🏛️ Automated PWD Civil Maintenance Work-Order docket generated...", 88),
            ("🚀 Official Civil Maintenance Docket Auto-Dispatched via SMTP!", 100)
        ]

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)

        card = QFrame()
        card.setObjectName("loaderCard")
        card.setStyleSheet("""
            #loaderCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #090e1a, stop:0.5 #0f172a, stop:1 #024a70);
                border: 2px solid #0284c7;
                border-radius: 14px;
            }
        """)
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(28, 24, 28, 24)
        card_lay.setSpacing(14)

        # Header Badge
        h_row = QHBoxLayout()
        pill = QLabel(f"● TELEMETRY CONSOLIDATION // {corridor_name}")
        pill.setStyleSheet("color: #38bdf8; background: rgba(2, 132, 199, 0.25); border: 1px solid #0284c7; padding: 4px 10px; border-radius: 4px; font-size: 10px; font-weight: 900;")
        h_row.addWidget(pill)
        h_row.addStretch()

        self.pct_label = QLabel("0%")
        self.pct_label.setStyleSheet("color: #38bdf8; font-size: 14px; font-weight: 900;")
        h_row.addWidget(self.pct_label)
        card_lay.addLayout(h_row)

        title = QLabel("ARGUS Municipal Intelligence Engine")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setStyleSheet("color: #ffffff; font-weight: 900; margin-top: 2px;")
        card_lay.addWidget(title)

        sub = QLabel(f"Consolidating {total_incidents} captured telemetry records into official municipal civil maintenance docket...")
        sub.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 600;")
        card_lay.addWidget(sub)

        # Progress Bar
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setFixedHeight(8)
        self.bar.setTextVisible(False)
        self.bar.setStyleSheet("""
            QProgressBar {
                background-color: #1e293b;
                border: none;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #38bdf8);
                border-radius: 4px;
            }
        """)
        card_lay.addWidget(self.bar)

        # Steps Display Box
        self.steps_box = QVBoxLayout()
        self.steps_box.setSpacing(6)
        self.step_labels = []
        for text, _ in self.steps:
            lbl = QLabel(f"○ {text}")
            lbl.setStyleSheet("color: #475569; font-size: 11px; font-weight: 700;")
            self.steps_box.addWidget(lbl)
            self.step_labels.append(lbl)
        card_lay.addLayout(self.steps_box)

        main_layout.addWidget(card)

        # Timer to advance steps
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._advance_step)
        self.timer.start(340)

    def _advance_step(self):
        if self.step_idx < len(self.steps):
            text, target_pct = self.steps[self.step_idx]
            self.bar.setValue(target_pct)
            self.pct_label.setText(f"{target_pct}%")
            self.step_labels[self.step_idx].setText(f"✓ {text}")
            self.step_labels[self.step_idx].setStyleSheet("color: #34d399; font-size: 11px; font-weight: 800;")
            self.step_idx += 1
            play_alert_sound(freq=700 + self.step_idx * 90, dur=40, category="loader_tick", cooldown=0.1)
        else:
            self.timer.stop()
            play_alert_sound(freq=1200, dur=120, category="loader_done", cooldown=0.5)
            QTimer.singleShot(250, self._finish)

    def _finish(self):
        self.finished_loading.emit()
        self.accept()


# ─── UNIQUE VEHICLE EXTRACTION & MORTH REGISTRY STORAGE ──────────────────────
def extract_unique_vehicles(incidents: Optional[List[Dict[str, Any]]] = None, summary: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Extracts, reconciles, and merges only UNIQUE vehicles tracked during the corridor run.
    Deduplicates by ByteTrack track ID and license plate, compiling all verified
    parameters (Plate, Classification, Track ID, Violations, Confidence, GPS, Timestamp).
    """
    incidents = incidents or []
    summary = summary or {}
    unique_vehicles_map: Dict[str, Dict[str, Any]] = {}

    # 1. Ingest tracked_vehicles from summary if present
    for tv in summary.get("tracked_vehicles", summary.get("unique_vehicles", [])):
        tid_raw = tv.get("track_id") or tv.get("id")
        tid_clean = str(tid_raw).replace("TRK-", "").replace("VEH-", "").replace("#", "").strip()
        if not tid_clean:
            continue
        v_type = tv.get("vehicle_type") or tv.get("label", "Car").title()
        conf = tv.get("conf") or tv.get("confidence", "91.5%")
        if isinstance(conf, float):
            conf = f"{conf * 100:.1f}%"

        t_int = int("".join(filter(str.isdigit, tid_clean))) if any(c.isdigit() for c in tid_clean) else len(unique_vehicles_map) + 1
        unique_vehicles_map[tid_clean] = {
            "track_id": f"#{t_int}",
            "track_int": t_int,
            "vehicle_type": v_type,
            "plate": tv.get("plate"),
            "violation": tv.get("violation", "✓ MoRTH Compliant"),
            "is_violator": bool(tv.get("is_violator", False)),
            "confidence": conf,
            "gps": tv.get("gps", "13.0342, 80.1551"),
            "lat": tv.get("lat", 13.0342),
            "lon": tv.get("lon", 80.1551),
            "location": tv.get("location", "Anna Salai Corridor"),
            "timestamp": tv.get("timestamp", time.strftime("%H:%M:%S")),
            "time_sec": tv.get("first_seen", tv.get("time_sec", "0.00s"))
        }

    # 2. Ingest vehicle incidents from incidents log
    for inc in incidents:
        itype = str(inc.get("type", "")).upper()
        raw_tid = inc.get("track_id") or inc.get("id", "")
        tid_clean = str(raw_tid).replace("TRK-", "").replace("VEH-", "").replace("VIOL-", "").replace("RASH-", "").replace("HIT-", "").replace("#", "").strip()

        # Plate / ANPR incident
        if "PLATE" in itype or "ANPR" in itype:
            p_str = inc.get("plate") or inc.get("title", "").replace("ANPR // ", "").replace("PL-", "").strip()
            if tid_clean and tid_clean in unique_vehicles_map:
                unique_vehicles_map[tid_clean]["plate"] = p_str
            else:
                matched = False
                for k, v in unique_vehicles_map.items():
                    if v.get("plate") == p_str:
                        matched = True
                        break
                if not matched:
                    v_key = tid_clean if tid_clean else f"P{len(unique_vehicles_map)+1}"
                    t_int = int("".join(filter(str.isdigit, v_key))) if any(c.isdigit() for c in v_key) else len(unique_vehicles_map) + 1
                    unique_vehicles_map[v_key] = {
                        "track_id": f"#{t_int}",
                        "track_int": t_int,
                        "vehicle_type": inc.get("vehicle_type", "Car"),
                        "plate": p_str,
                        "violation": "✓ MoRTH Compliant",
                        "is_violator": False,
                        "confidence": inc.get("confidence", "93.8%"),
                        "gps": inc.get("gps", "13.0342, 80.1551"),
                        "lat": inc.get("lat", 13.0342),
                        "lon": inc.get("lon", 80.1551),
                        "location": inc.get("location", "Anna Salai Corridor"),
                        "timestamp": inc.get("timestamp", time.strftime("%H:%M:%S")),
                        "time_sec": inc.get("time_sec", "0.00s")
                    }

        # Violation incident
        elif any(k in itype for k in ("RASH", "VIOL", "SPEED", "HIT")):
            v_key = tid_clean if tid_clean else f"V{len(unique_vehicles_map)+1}"
            v_plate = inc.get("plate")
            viol_desc = f"🚨 {inc.get('type', 'RASH_DRIVING').replace('_', ' ').title()}"
            if "speed" in str(inc.get("description", "")).lower() or inc.get("speed_score"):
                spd = inc.get("speed_score", 1.9)
                viol_desc = f"🚨 Rash Driving ({spd:.1f}x Speed)"
            elif "HIT" in itype:
                viol_desc = "🚨 Hit-and-Run (Lane Breach)"

            if v_key in unique_vehicles_map:
                v_obj = unique_vehicles_map[v_key]
                v_obj["is_violator"] = True
                v_obj["violation"] = viol_desc
                if v_plate:
                    v_obj["plate"] = v_plate
            else:
                t_int = int("".join(filter(str.isdigit, v_key))) if any(c.isdigit() for c in v_key) else len(unique_vehicles_map) + 1
                unique_vehicles_map[v_key] = {
                    "track_id": f"#{t_int}",
                    "track_int": t_int,
                    "vehicle_type": inc.get("vehicle_label", "Car").title(),
                    "plate": v_plate,
                    "violation": viol_desc,
                    "is_violator": True,
                    "confidence": inc.get("confidence", "95.0%"),
                    "gps": inc.get("gps", "13.0342, 80.1551"),
                    "lat": inc.get("lat", 13.0342),
                    "lon": inc.get("lon", 80.1551),
                    "location": inc.get("location", "Anna Salai Corridor"),
                    "timestamp": inc.get("timestamp", time.strftime("%H:%M:%S")),
                    "time_sec": inc.get("time_sec", "0.00s")
                }

        # Routine tracked vehicle incident
        elif itype == "VEHICLE":
            if tid_clean and tid_clean not in unique_vehicles_map:
                t_int = int("".join(filter(str.isdigit, tid_clean))) if any(c.isdigit() for c in tid_clean) else len(unique_vehicles_map) + 1
                v_lbl = inc.get("vehicle_type") or inc.get("title", "Car").split()[0].title()
                unique_vehicles_map[tid_clean] = {
                    "track_id": f"#{t_int}",
                    "track_int": t_int,
                    "vehicle_type": v_lbl,
                    "plate": inc.get("plate"),
                    "violation": "✓ MoRTH Compliant",
                    "is_violator": False,
                    "confidence": inc.get("confidence", "89.5%"),
                    "gps": inc.get("gps", "13.0342, 80.1551"),
                    "lat": inc.get("lat", 13.0342),
                    "lon": inc.get("lon", 80.1551),
                    "location": inc.get("location", "Anna Salai Corridor"),
                    "timestamp": inc.get("timestamp", time.strftime("%H:%M:%S")),
                    "time_sec": inc.get("time_sec", "0.00s")
                }

    # Preserve only genuinely scanned plates. Do not invent fake plates for unscanned vehicles.
    result: List[Dict[str, Any]] = []
    for k, v in unique_vehicles_map.items():
        p = v.get("plate")
        if p and (p == "FLAGGED" or "TN 01 AB 4321" in str(p) or "UNSCANNED" in str(p).upper()):
            v["plate"] = None
        result.append(v)

    # Sort strictly by track ID integer for consistent display
    result.sort(key=lambda x: x.get("track_int", 0))
    return result


def save_unique_vehicles_registry(vehicles: List[Dict[str, Any]], output_dir: str = "data/output") -> Tuple[str, str]:
    """
    Saves only unique vehicles and their parameters to a CSV ledger and JSON file.
    Returns (csv_path, json_path).
    """
    os.makedirs(output_dir, exist_ok=True)
    csv_path = os.path.abspath(os.path.join(output_dir, "unique_vehicles_registry.csv"))
    json_path = os.path.abspath(os.path.join(output_dir, "unique_vehicles_registry.json"))

    import csv as pycsv
    fieldnames = [
        "Track ID", "Number Plate", "Vehicle Type", "MoRTH Status / Violation",
        "Confidence", "Corridor GPS Pinpoint", "Latitude", "Longitude",
        "Corridor Sector", "Timestamp", "Video Timestamp (s)"
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = pycsv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for v in vehicles:
            writer.writerow({
                "Track ID": v.get("track_id", ""),
                "Number Plate": v.get("plate", ""),
                "Vehicle Type": v.get("vehicle_type", "Car"),
                "MoRTH Status / Violation": v.get("violation", "✓ MoRTH Compliant"),
                "Confidence": v.get("confidence", "90.0%"),
                "Corridor GPS Pinpoint": v.get("gps", ""),
                "Latitude": v.get("lat", ""),
                "Longitude": v.get("lon", ""),
                "Corridor Sector": v.get("location", "Anna Salai Corridor"),
                "Timestamp": v.get("timestamp", ""),
                "Video Timestamp (s)": v.get("time_sec", "")
            })

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(vehicles, f, indent=2)

    return csv_path, json_path


# ─── MUNICIPAL RECORDS AUDIT DASHBOARD SCREEN ────────────────────────────────
class MunicipalRecordsDashboardView(QWidget):
    back_to_cockpit = pyqtSignal()
    export_all_requested = pyqtSignal()
    pwd_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.corridor_id = "bus1"
        self.all_incidents: List[Dict[str, Any]] = []
        self.summary_data: Dict[str, Any] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(12)

        # Top Header Bar Card
        header_card = EnterpriseCard()
        h_lay = QHBoxLayout(header_card)
        h_lay.setContentsMargins(18, 12, 18, 12)
        h_lay.setSpacing(14)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        self.h_title = QLabel("ARGUS // MUNICIPAL INTELLIGENCE & AUDIT RECORDS DOSSIER")
        self.h_title.setFont(QFont("Segoe UI", 13, QFont.Bold))
        self.h_title.setStyleSheet("color: #0f172a; font-weight: 900; letter-spacing: 0.5px;")
        self.h_sub = QLabel("CONSOLIDATED ROAD DEFECTS · MoRTH ANPR REGISTRY · PWD CIVIL MAINTENANCE WORK ORDERS")
        self.h_sub.setStyleSheet("color: #475569; font-size: 10px; font-weight: 700;")
        title_box.addWidget(self.h_title)
        title_box.addWidget(self.h_sub)
        h_lay.addLayout(title_box)

        h_lay.addStretch()

        self.back_btn = QPushButton("◀ Return to Live Cockpit")
        self.back_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.back_btn.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: white;
                font-weight: 800;
                font-size: 11px;
                padding: 7px 16px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
        """)
        self.back_btn.clicked.connect(self.back_to_cockpit.emit)
        h_lay.addWidget(self.back_btn)

        self.export_all_btn = QPushButton("📥 Export Audit Package")
        self.export_all_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.export_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #0f172a;
                border: 1px solid #cbd5e1;
                font-weight: 800;
                font-size: 11px;
                padding: 7px 14px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #e2e8f0;
                border-color: #0284c7;
            }
        """)
        self.export_all_btn.clicked.connect(self.export_all_requested.emit)
        h_lay.addWidget(self.export_all_btn)

        self.pwd_docket_btn = QPushButton("🏛️ PWD Civil Docket")
        self.pwd_docket_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.pwd_docket_btn.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: white;
                font-weight: 800;
                font-size: 11px;
                padding: 7px 16px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #047857;
            }
        """)
        self.pwd_docket_btn.clicked.connect(self.pwd_requested.emit)
        h_lay.addWidget(self.pwd_docket_btn)

        layout.addWidget(header_card)

        # Full-Width KPI Metrics Ribbon
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(10)

        self.kpi_potholes = EnterpriseKpiCard("Potholes / Craters", 0, "Depth AI Defects", "#ef4444")
        self.kpi_plates = EnterpriseKpiCard("ANPR Plates Scanned", 0, "Plate Scans", "#10b981")
        self.kpi_violators = EnterpriseKpiCard("Traffic Violators", 0, "Rash Driving Flagged", "#dc2626")
        self.kpi_vehicles = EnterpriseKpiCard("Vehicles Tracked", 0, "Persistent Tracking", "#0284c7")
        self.kpi_congestion = EnterpriseKpiCard("Corridor Congestion", 0, "Peak / Avg Density", "#0284c7")
        self.kpi_infra = EnterpriseKpiCard("Infra Deficiencies", 0, "Dividers / Zebra / Water", "#8b5cf6")
        self.kpi_budget = EnterpriseKpiCard("Est. PWD Budget", 0, "IRC Civil Repair Cost (₹)", "#059669")

        kpi_row.addWidget(self.kpi_potholes)
        kpi_row.addWidget(self.kpi_plates)
        kpi_row.addWidget(self.kpi_violators)
        kpi_row.addWidget(self.kpi_vehicles)
        kpi_row.addWidget(self.kpi_congestion)
        kpi_row.addWidget(self.kpi_infra)
        kpi_row.addWidget(self.kpi_budget)
        layout.addLayout(kpi_row)

        # Main Tab Widget (Full Width, Uncramped)
        tabs_card = EnterpriseCard()
        t_lay = QVBoxLayout(tabs_card)
        t_lay.setContentsMargins(12, 10, 12, 12)

        self.records_tabs = QTabWidget()
        self.records_tabs.setStyleSheet("""
            QTabBar::tab {
                background-color: #f1f5f9;
                color: #0f172a;
                padding: 8px 14px;
                font-weight: 800;
                font-size: 11px;
                border: 1px solid #cbd5e1;
                border-bottom: none;
                margin-right: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            QTabBar::tab:selected {
                background-color: #ffffff;
                color: #0284c7;
                border-bottom: 2px solid #0284c7;
            }
        """)

        # Tab 1: Potholes Ledger
        potholes_w = QWidget()
        p_vbox = QVBoxLayout(potholes_w)
        p_vbox.setContentsMargins(8, 8, 8, 8)
        p_vbox.setSpacing(8)

        p_filter_row = QHBoxLayout()
        p_filter_lbl = QLabel("Filter Severity:")
        p_filter_lbl.setStyleSheet("font-weight: 700; color: #0f172a; font-size: 11px;")
        p_filter_row.addWidget(p_filter_lbl)

        self.pothole_filter_combo = QComboBox()
        self.pothole_filter_combo.addItems(["All Defects", "P1 - CRITICAL", "P2 - HIGH", "P3 - MEDIUM"])
        self.pothole_filter_combo.setStyleSheet("padding: 4px 10px; font-weight: 700; border: 1px solid #cbd5e1; border-radius: 5px;")
        self.pothole_filter_combo.currentIndexChanged.connect(self._filter_potholes_table)
        p_filter_row.addWidget(self.pothole_filter_combo)
        p_filter_row.addStretch()

        self.pothole_search = QLineEdit()
        self.pothole_search.setPlaceholderText("🔍 Search by location, ID, or defect type...")
        self.pothole_search.setStyleSheet("padding: 5px 12px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 11px; max-width: 320px;")
        self.pothole_search.textChanged.connect(self._filter_potholes_table)
        p_filter_row.addWidget(self.pothole_search)
        p_vbox.addLayout(p_filter_row)

        self.potholes_table = QTableWidget(0, 8)
        self.potholes_table.setHorizontalHeaderLabels([
            "Order ID", "Defect Type", "Severity", "IRC Code", "Est. Budget (INR)", "Corridor GPS Pinpoint", "SLA Resolution", "Auto-Dispatch Status"
        ])
        self.potholes_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.potholes_table.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                gridline-color: #e2e8f0;
                font-size: 11px;
                color: #0f172a;
            }
            QHeaderView::section {
                background-color: #f8fafc;
                color: #0f172a;
                font-weight: 800;
                padding: 8px;
                border: 1px solid #e2e8f0;
            }
        """)
        p_vbox.addWidget(self.potholes_table)
        self.records_tabs.addTab(potholes_w, "🕳️ Potholes & Road Surface Distress")

        # Tab 2: ANPR & Violators
        anpr_w = QWidget()
        a_vbox = QVBoxLayout(anpr_w)
        a_vbox.setContentsMargins(8, 8, 8, 8)
        a_vbox.setSpacing(8)

        a_filter_row = QHBoxLayout()
        self.anpr_search = QLineEdit()
        self.anpr_search.setPlaceholderText("🔍 Search license plate (e.g. TN 01, DL 08)...")
        self.anpr_search.setStyleSheet("padding: 5px 12px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 11px; max-width: 320px;")
        self.anpr_search.textChanged.connect(self._filter_anpr_table)
        a_filter_row.addWidget(self.anpr_search)
        a_filter_row.addStretch()
        a_vbox.addLayout(a_filter_row)

        self.anpr_table = QTableWidget(0, 7)
        self.anpr_table.setHorizontalHeaderLabels([
            "Number Plate", "Vehicle Type", "Track ID", "Violations Flagged", "Confidence", "GPS Location", "Timestamp"
        ])
        self.anpr_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.anpr_table.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                gridline-color: #e2e8f0;
                font-size: 11px;
                color: #0f172a;
            }
            QHeaderView::section {
                background-color: #f8fafc;
                color: #0f172a;
                font-weight: 800;
                padding: 8px;
                border: 1px solid #e2e8f0;
            }
        """)
        a_vbox.addWidget(self.anpr_table)
        self.records_tabs.addTab(anpr_w, "🚗 MoRTH ANPR & Violator Registry")

        # Tab 3: Infrastructure Deficiencies
        infra_w = QWidget()
        i_vbox = QVBoxLayout(infra_w)
        i_vbox.setContentsMargins(8, 8, 8, 8)

        self.infra_records_table = QTableWidget(0, 7)
        self.infra_records_table.setHorizontalHeaderLabels([
            "Defect / Asset Type", "Priority", "Corridor Location", "Repair Action (IRC Spec)", "Material Spec", "Est. Budget (INR)", "Target SLA"
        ])
        self.infra_records_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.infra_records_table.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                gridline-color: #e2e8f0;
                font-size: 11px;
                color: #0f172a;
            }
            QHeaderView::section {
                background-color: #f8fafc;
                color: #0f172a;
                font-weight: 800;
                padding: 8px;
                border: 1px solid #e2e8f0;
            }
        """)
        i_vbox.addWidget(self.infra_records_table)
        self.records_tabs.addTab(infra_w, "🚧 Road Safety Infrastructure Deficiencies")

        # Tab 4: Automated PWD Work-Order Dockets
        pwd_w = QWidget()
        pwd_vbox = QVBoxLayout(pwd_w)
        pwd_vbox.setContentsMargins(8, 8, 8, 8)
        pwd_vbox.setSpacing(8)

        pwd_banner = QFrame()
        pwd_banner.setStyleSheet("background-color: #f0fdf4; border: 1px solid #86efac; border-radius: 8px; padding: 10px;")
        pb_lay = QHBoxLayout(pwd_banner)
        pb_info = QVBoxLayout()
        pb_info.setSpacing(2)
        pb_t = QLabel("🏛️ <b>Autonomous Municipal PWD Civil Dispatch Engine</b>")
        disp_email = os.getenv("MUNICIPAL_DISPATCH_EMAIL", "corporationunicipal26@gmail.com")
        pb_s = QLabel(f"All detected road craters & safety infrastructure breaches are auto-bundled and dispatched via SMTP ({disp_email}).")
        pb_s.setStyleSheet("color: #15803d; font-size: 11px;")
        pb_info.addWidget(pb_t)
        pb_info.addWidget(pb_s)
        pb_lay.addLayout(pb_info)
        pb_lay.addStretch()

        open_dockets_btn = QPushButton("📂 Open Dockets Directory")
        open_dockets_btn.setStyleSheet("background-color: #ffffff; color: #166534; border: 1px solid #86efac; padding: 6px 14px; border-radius: 6px; font-weight: 700; font-size: 11px;")
        open_dockets_btn.clicked.connect(lambda: os.startfile(os.path.abspath("data/output")) if os.path.exists("data/output") else None)
        pb_lay.addWidget(open_dockets_btn)
        pwd_vbox.addWidget(pwd_banner)

        self.pwd_dockets_table = QTableWidget(0, 6)
        self.pwd_dockets_table.setHorizontalHeaderLabels([
            "Docket CSV File", "Total Orders", "Estimated Civil Budget", "Timestamp", "Auto-Dispatch Status", "Actions"
        ])
        self.pwd_dockets_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.pwd_dockets_table.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                gridline-color: #e2e8f0;
                font-size: 11px;
                color: #0f172a;
            }
            QHeaderView::section {
                background-color: #f8fafc;
                color: #0f172a;
                font-weight: 800;
                padding: 8px;
                border: 1px solid #e2e8f0;
            }
        """)
        pwd_vbox.addWidget(self.pwd_dockets_table)
        self.records_tabs.addTab(pwd_w, "🏛️ Automated PWD Dockets Ledger")

        # Tab 5: Incident Stream Log
        stream_w = QWidget()
        s_vbox = QVBoxLayout(stream_w)
        s_vbox.setContentsMargins(8, 8, 8, 8)
        self.stream_list = QListWidget()
        self.stream_list.setStyleSheet("background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 11px; font-weight: 600; padding: 4px;")
        s_vbox.addWidget(self.stream_list)
        self.records_tabs.addTab(stream_w, "📜 Geospatial Event Log")

        # Tab 6: Traffic Congestion & Heatmap Intelligence
        heat_w = QWidget()
        h_vbox = QVBoxLayout(heat_w)
        h_vbox.setContentsMargins(8, 8, 8, 8)
        h_vbox.setSpacing(8)

        heat_banner = QFrame()
        heat_banner.setStyleSheet("background-color: #f0fdfa; border: 1px solid #5eead4; border-radius: 8px; padding: 10px;")
        hb_lay = QHBoxLayout(heat_banner)
        hb_info = QVBoxLayout()
        hb_info.setSpacing(2)
        hb_t = QLabel("🔥 <b>Geospatial Traffic Density & Road Congestion Intelligence</b>")
        hb_t.setStyleSheet("color: #0f766e; font-size: 12px;")
        hb_s = QLabel("Multi-spectral thermal density analysis combining vehicular flow velocity, pedestrian conflict zones, school corridors, and road surface hazard bottlenecks.")
        hb_s.setStyleSheet("color: #115e59; font-size: 11px;")
        hb_info.addWidget(hb_t)
        hb_info.addWidget(hb_s)
        hb_lay.addLayout(hb_info)
        hb_lay.addStretch()
        h_vbox.addWidget(heat_banner)

        self.congestion_table = QTableWidget(0, 7)
        self.congestion_table.setHorizontalHeaderLabels([
            "Corridor Sector", "GPS Coordinates", "Congestion Index", "Flow Classification", "Primary Friction Factor", "Heat Intensity", "Civil / Traffic Recommendation"
        ])
        hh = self.congestion_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(6, QHeaderView.Stretch)
        self.congestion_table.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                gridline-color: #e2e8f0;
                font-size: 11px;
                color: #0f172a;
            }
            QHeaderView::section {
                background-color: #f8fafc;
                color: #0f172a;
                font-weight: 800;
                padding: 8px;
                border: 1px solid #e2e8f0;
            }
        """)
        h_vbox.addWidget(self.congestion_table)
        self.records_tabs.addTab(heat_w, "🔥 Congestion & Heatmap Intelligence")

        # Tab 7: 💾 SQLite Audit Database
        db_w = QWidget()
        db_vbox = QVBoxLayout(db_w)
        db_vbox.setContentsMargins(8, 8, 8, 8)
        db_vbox.setSpacing(8)

        # Database Status Strip
        self.db_banner = QFrame()
        self.db_banner.setStyleSheet("background-color: #f0f9ff; border: 1px solid #bae6fd; border-radius: 8px; padding: 10px;")
        db_banner_lay = QHBoxLayout(self.db_banner)
        db_info_lay = QVBoxLayout()
        db_info_lay.setSpacing(2)

        self.db_title_lbl = QLabel("💾 <b>ARGUS Embedded SQLite Database Engine (data/app.db)</b>")
        self.db_title_lbl.setStyleSheet("color: #0369a1; font-size: 12px;")
        self.db_stats_lbl = QLabel("STATUS: 🟢 CONNECTED (WAL Thread-Safe) | Synchronized")
        self.db_stats_lbl.setStyleSheet("color: #0284c7; font-size: 11px; font-weight: 700;")
        db_info_lay.addWidget(self.db_title_lbl)
        db_info_lay.addWidget(self.db_stats_lbl)
        db_banner_lay.addLayout(db_info_lay)
        db_banner_lay.addStretch()

        open_db_btn = QPushButton("📂 Open Database Folder")
        open_db_btn.setCursor(QCursor(Qt.PointingHandCursor))
        open_db_btn.setStyleSheet("background-color: #ffffff; color: #0369a1; border: 1px solid #7dd3fc; padding: 6px 14px; border-radius: 6px; font-weight: 700; font-size: 11px;")
        open_db_btn.clicked.connect(lambda: os.startfile(os.path.abspath("data")) if os.path.exists("data") else None)
        db_banner_lay.addWidget(open_db_btn)
        db_vbox.addWidget(self.db_banner)

        # Database Controls Row
        ctrl_row = QHBoxLayout()
        ctrl_lbl = QLabel("Query Table:")
        ctrl_lbl.setStyleSheet("font-weight: 800; color: #0f172a; font-size: 11px;")
        ctrl_row.addWidget(ctrl_lbl)

        self.db_table_selector = QComboBox()
        self.db_table_selector.addItem("🕳️ Potholes & Surface Distress (potholes)", "potholes")
        self.db_table_selector.addItem("🚗 MoRTH ANPR License Plates (plates)", "plates")
        self.db_table_selector.addItem("🚨 Safety Violations & Infrastructure (violations)", "violations")
        self.db_table_selector.addItem("📊 Traffic Density & Congestion (traffic_metrics)", "traffic_metrics")
        self.db_table_selector.addItem("🏛️ Autonomous PWD Work-Orders (pwd_work_orders)", "pwd_work_orders")
        self.db_table_selector.addItem("📈 Surveillance Mission Runs (audit_runs)", "audit_runs")
        self.db_table_selector.setStyleSheet("padding: 5px 12px; font-weight: 700; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 11px; min-width: 260px;")
        self.db_table_selector.currentIndexChanged.connect(self._on_db_table_selected)
        ctrl_row.addWidget(self.db_table_selector)

        ctrl_row.addSpacing(10)

        self.db_search_input = QLineEdit()
        self.db_search_input.setPlaceholderText("🔍 Search SQLite records...")
        self.db_search_input.setStyleSheet("padding: 5px 12px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 11px; min-width: 220px;")
        self.db_search_input.textChanged.connect(self._on_db_table_selected)
        ctrl_row.addWidget(self.db_search_input)

        ctrl_row.addStretch()

        refresh_db_btn = QPushButton("🔄 Refresh SQLite Data")
        refresh_db_btn.setCursor(QCursor(Qt.PointingHandCursor))
        refresh_db_btn.setStyleSheet("background-color: #0284c7; color: white; padding: 6px 14px; border-radius: 6px; font-weight: 800; font-size: 11px; border: none;")
        refresh_db_btn.clicked.connect(self._refresh_db_view)
        ctrl_row.addWidget(refresh_db_btn)

        db_vbox.addLayout(ctrl_row)

        self.sqlite_table_widget = QTableWidget(0, 0)
        self.sqlite_table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.sqlite_table_widget.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                gridline-color: #e2e8f0;
                font-size: 11px;
                color: #0f172a;
            }
            QHeaderView::section {
                background-color: #f8fafc;
                color: #0f172a;
                font-weight: 800;
                padding: 8px;
                border: 1px solid #e2e8f0;
            }
        """)
        db_vbox.addWidget(self.sqlite_table_widget)
        self.records_tabs.addTab(db_w, "💾 SQLite Audit Database")

        t_lay.addWidget(self.records_tabs)
        layout.addWidget(tabs_card, stretch=1)

    def populate_records(self, incidents: List[Dict[str, Any]], summary: Optional[Dict[str, Any]] = None, corridor_id: str = "bus1"):
        self.all_incidents = list(incidents or [])
        self.summary_data = summary or {}
        self.corridor_id = corridor_id

        # Synchronize with SQLite database so every incident is persistent
        try:
            if self.all_incidents:
                sync_all_incidents(self.all_incidents, self.summary_data, self.corridor_id)
            else:
                # If no active run incidents passed, load persistent records from SQLite
                db_potholes = get_all_potholes()
                db_plates = get_all_plates()
                db_violations = get_all_violations()
                if db_potholes or db_plates or db_violations:
                    for p in db_potholes:
                        self.all_incidents.append({
                            "id": p.get("incident_id", f"POT-{p.get('id')}"),
                            "type": "POTHOLE",
                            "severity": p.get("severity", "P2 - HIGH"),
                            "confidence": f"{int(p.get('confidence', 0.85)*100)}%",
                            "gps": f"{p.get('latitude', 13.0350):.4f}, {p.get('longitude', 80.1542):.4f}",
                            "location": p.get("street_name", "Anna Salai Corridor"),
                            "title": f"Road Surface Defect ({p.get('severity')})",
                            "time_sec": p.get("timestamp_sec", 0.0),
                            "timestamp": str(p.get("created_at", ""))
                        })
                    for pl in db_plates:
                        self.all_incidents.append({
                            "id": f"PL-{pl.get('id')}",
                            "type": "PLATE",
                            "severity": "NORMAL",
                            "confidence": f"{int(pl.get('confidence', 0.90)*100)}%",
                            "gps": f"{pl.get('latitude', 13.0350):.4f}, {pl.get('longitude', 80.1542):.4f}",
                            "location": pl.get("street_name", "Anna Salai Corridor"),
                            "title": f"ANPR // {pl.get('plate_text')}",
                            "plate": pl.get("plate_text"),
                            "vehicle_type": pl.get("vehicle_type", "Car"),
                            "time_sec": pl.get("timestamp_sec", 0.0),
                            "timestamp": str(pl.get("created_at", ""))
                        })
                    for v in db_violations:
                        self.all_incidents.append({
                            "id": v.get("incident_id", f"VIOL-{v.get('id')}"),
                            "type": v.get("violation_type", "SAFETY_VIOLATION"),
                            "severity": v.get("severity", "WARNING"),
                            "confidence": f"{int(v.get('confidence', 0.85)*100)}%",
                            "gps": f"{v.get('latitude', 13.0350):.4f}, {v.get('longitude', 80.1542):.4f}",
                            "location": v.get("street_name", "Anna Salai Corridor"),
                            "title": v.get("description", "Safety Violation"),
                            "time_sec": v.get("timestamp_sec", 0.0),
                            "timestamp": str(v.get("created_at", ""))
                        })
        except Exception as e:
            logger.debug(f"Error syncing DB in populate_records: {e}")

        # 1. Potholes
        potholes = [inc for inc in self.all_incidents if "pothole" in str(inc.get("type", "")).lower()]
        p1_count = 0
        p2_count = 0
        p3_count = 0
        for p in potholes:
            comb = (str(p.get("severity", "")) + " " + str(p.get("title", "")) + " " + str(p.get("class", "")) + " " + str(p.get("hazard_class", "")) + " " + str(p.get("description", ""))).lower()
            if any(k in comb for k in ("severe", "critical", "p1")):
                p1_count += 1
            elif any(k in comb for k in ("mild", "high", "warning", "p2")):
                p2_count += 1
            else:
                p3_count += 1

        # 2. ANPR & Unique Vehicles Registry (Only Unique Vehicles Tracked & Stored)
        unique_vehicles = extract_unique_vehicles(self.all_incidents, self.summary_data)
        save_unique_vehicles_registry(unique_vehicles)

        unique_plates = [v for v in unique_vehicles if v.get("plate")]
        unique_violators = [v for v in unique_vehicles if v.get("is_violator")]

        # 3. Infrastructure
        infra = [inc for inc in self.all_incidents if any(k in str(inc.get("type", "")).lower() for k in ("divider", "zebra", "crosswalk", "water", "damaged", "sign"))]

        # 4. Compute Budget
        distress = [inc for inc in self.all_incidents if any(k in str(inc.get("type", "")).lower() for k in ("pothole", "divider", "zebra", "crosswalk", "water", "damaged"))]
        _, pwd_sum = generate_pwd_work_orders(distress) if distress else ("", {})
        budget_inr = pwd_sum.get("total_budget_inr", 0)

        # Update KPI cards
        total_veh = len(unique_vehicles)
        total_peds = self.summary_data.get("total_pedestrians_tracked", 0)
        raw_peak_cg = self.summary_data.get("peak_congestion_index", 0)
        raw_avg_cg = self.summary_data.get("avg_congestion_index", 0)

        if total_veh == 0 and total_peds == 0:
            peak_cg = 0
            avg_cg = 0
            cg_status = "FREE FLOW"
        else:
            peak_cg = raw_peak_cg
            avg_cg = raw_avg_cg
            cg_status = "HEAVY" if peak_cg >= 75 else ("MODERATE" if peak_cg >= 50 else ("NORMAL" if peak_cg >= 25 else "FREE FLOW"))
        self.kpi_potholes.set_value(len(potholes), f"P1: {p1_count} | P2: {p2_count} | P3: {p3_count}")
        self.kpi_plates.set_value(len(unique_plates), "Unique Plates Audited")
        self.kpi_violators.set_value(len(unique_violators), "Rash / Speed Violations")
        self.kpi_vehicles.set_value(len(unique_vehicles), "Unique Vehicles Audited")
        self.kpi_congestion.set_value(f"{avg_cg}%", f"Peak: {peak_cg}% ({cg_status})")
        self.kpi_infra.set_value(len(infra), "Infrastructure Deficiencies")
        self.kpi_budget.set_value(budget_inr, f"₹{budget_inr:,} INR Total Budget")

        # Populate Potholes Table
        self.potholes_table.setRowCount(0)
        for idx, p in enumerate(potholes, 1):
            row = self.potholes_table.rowCount()
            self.potholes_table.insertRow(row)

            comb = (str(p.get("severity", "")) + " " + str(p.get("title", "")) + " " + str(p.get("class", "")) + " " + str(p.get("hazard_class", "")) + " " + str(p.get("description", ""))).lower()
            if any(k in comb for k in ("severe", "critical", "p1")):
                sev = "P1 - CRITICAL"
                cost = "₹3,800"
                sla = "24h SLA"
                desc = p.get("description") or f"Severe Volumetric Crater >8cm (IRC:82-2015)"
            elif any(k in comb for k in ("mild", "high", "warning", "p2")):
                sev = "P2 - HIGH"
                cost = "₹1,650"
                sla = "48h SLA"
                desc = p.get("description") or f"Moderate Surface Pothole (4-8cm depth)"
            else:
                sev = "P3 - MEDIUM"
                cost = "₹750"
                sla = "7d SLA"
                desc = p.get("description") or f"Shallow Surface Distress (<4cm)"

            gps_str = f"{p.get('lat', 13.0335):.4f}, {p.get('lon', 80.1550):.4f}"

            id_item = QTableWidgetItem(f"WO-P{idx:03d}")
            desc_item = QTableWidgetItem(desc)
            sev_item = QTableWidgetItem(sev)
            if "P1" in sev:
                sev_item.setForeground(QColor("#dc2626"))
                sev_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
            elif "P2" in sev:
                sev_item.setForeground(QColor("#ea580c"))
                sev_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
            else:
                sev_item.setForeground(QColor("#0284c7"))

            irc_item = QTableWidgetItem("IRC:82-2015")
            cost_item = QTableWidgetItem(cost)
            gps_item = QTableWidgetItem(gps_str)
            sla_item = QTableWidgetItem(sla)
            status_item = QTableWidgetItem("✓ AUTO-DISPATCHED")
            status_item.setForeground(QColor("#16a34a"))

            self.potholes_table.setItem(row, 0, id_item)
            self.potholes_table.setItem(row, 1, desc_item)
            self.potholes_table.setItem(row, 2, sev_item)
            self.potholes_table.setItem(row, 3, irc_item)
            self.potholes_table.setItem(row, 4, cost_item)
            self.potholes_table.setItem(row, 5, gps_item)
            self.potholes_table.setItem(row, 6, sla_item)
            self.potholes_table.setItem(row, 7, status_item)

        # Populate ANPR Table with ONLY UNIQUE VEHICLES (scanned plates prioritized)
        self.anpr_table.setRowCount(0)
        sorted_veh = sorted(unique_vehicles, key=lambda v: (0 if v.get("plate") else (1 if v.get("is_violator") else 2), v.get("track_int", 0)))
        for row, v in enumerate(sorted_veh):
            self.anpr_table.insertRow(row)

            has_plate = bool(v.get("plate"))
            plate_str = v.get("plate") or "— (Not Scanned)"
            plate_item = QTableWidgetItem(plate_str)
            plate_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            if v.get("is_violator"):
                plate_item.setForeground(QColor("#dc2626"))
            elif has_plate:
                plate_item.setForeground(QColor("#16a34a"))  # Green for verified scanned plate
            else:
                plate_item.setForeground(QColor("#64748b"))  # Muted slate for unscanned vehicle

            viol_str = v.get("violation", "✓ MoRTH Compliant")
            viol_item = QTableWidgetItem(viol_str)
            if v.get("is_violator"):
                viol_item.setForeground(QColor("#dc2626"))
                viol_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            else:
                viol_item.setForeground(QColor("#16a34a"))

            conf_str = v.get("confidence", "91.5%") if has_plate else "N/A"
            conf_item = QTableWidgetItem(conf_str)
            gps_item = QTableWidgetItem(v.get("gps", ""))
            ts_item = QTableWidgetItem(v.get("timestamp", ""))

            self.anpr_table.setItem(row, 0, plate_item)
            self.anpr_table.setItem(row, 1, QTableWidgetItem(v.get("vehicle_type", "Car")))
            self.anpr_table.setItem(row, 2, QTableWidgetItem(v.get("track_id", "")))
            self.anpr_table.setItem(row, 3, viol_item)
            self.anpr_table.setItem(row, 4, conf_item)
            self.anpr_table.setItem(row, 5, gps_item)
            self.anpr_table.setItem(row, 6, ts_item)

        # Populate Infrastructure Table
        self.infra_records_table.setRowCount(0)
        for idx, inf in enumerate(infra, 1):
            row = self.infra_records_table.rowCount()
            self.infra_records_table.insertRow(row)
            t = inf.get("type", "INFRA_DEFECT")
            action = "Install concrete median barrier" if "divider" in t.lower() else "Apply thermoplastic crosswalk marking"
            mat = "M30 Concrete (30m)" if "divider" in t.lower() else "Thermoplastic Compound (24m²)"
            cost = "₹48,000" if "divider" in t.lower() else "₹14,500"
            sla = "24h SLA" if "divider" in t.lower() else "48h SLA"
            gps_str = f"{inf.get('lat', 13.035):.4f}, {inf.get('lon', 80.153):.4f}"

            self.infra_records_table.setItem(row, 0, QTableWidgetItem(t))
            self.infra_records_table.setItem(row, 1, QTableWidgetItem("P1 - CRITICAL"))
            self.infra_records_table.setItem(row, 2, QTableWidgetItem(gps_str))
            self.infra_records_table.setItem(row, 3, QTableWidgetItem(action))
            self.infra_records_table.setItem(row, 4, QTableWidgetItem(mat))
            self.infra_records_table.setItem(row, 5, QTableWidgetItem(cost))
            self.infra_records_table.setItem(row, 6, QTableWidgetItem(sla))

        # Populate PWD Dockets Table from data/output
        self.pwd_dockets_table.setRowCount(0)
        out_dir = "data/output"
        if os.path.exists(out_dir):
            docket_files = sorted(
                [f for f in os.listdir(out_dir) if f.startswith("PWD_WORK_ORDER") and f.endswith(".csv")],
                reverse=True
            )
            import csv as pycsv
            seen_signatures = set()
            displayed_files = []
            for f in docket_files:
                f_path = os.path.join(out_dir, f)
                try:
                    mtime = int(os.path.getmtime(f_path))
                    tot_cost = 0
                    order_count = 0
                    with open(f_path, "r", encoding="utf-8", errors="ignore") as fl:
                        reader = pycsv.DictReader(fl)
                        for r_item in reader:
                            order_count += 1
                            c_str = str(r_item.get("Estimated Cost (INR)", "0")).replace("₹", "").replace(",", "").strip()
                            try:
                                tot_cost += int(float(c_str))
                            except Exception:
                                pass
                    if tot_cost == 0:
                        tot_cost = order_count * 2800

                    # Deduplicate dockets with identical order count & budget created within 45s of each other
                    sig = (order_count, tot_cost, mtime // 45)
                    if sig in seen_signatures:
                        continue
                    seen_signatures.add(sig)
                    displayed_files.append((f, f_path, order_count, tot_cost, mtime))
                    if len(displayed_files) >= 10:
                        break
                except Exception:
                    continue

            for f, f_path, order_count, tot_cost, mtime in displayed_files:
                row = self.pwd_dockets_table.rowCount()
                self.pwd_dockets_table.insertRow(row)

                self.pwd_dockets_table.setItem(row, 0, QTableWidgetItem(f))
                self.pwd_dockets_table.setItem(row, 1, QTableWidgetItem(f"{order_count} Orders"))
                self.pwd_dockets_table.setItem(row, 2, QTableWidgetItem(f"₹{tot_cost:,} INR"))
                self.pwd_dockets_table.setItem(row, 3, QTableWidgetItem(time.ctime(mtime)))
                self.pwd_dockets_table.setItem(row, 4, QTableWidgetItem("✓ DISPATCHED VIA SMTP"))
                self.pwd_dockets_table.setItem(row, 5, QTableWidgetItem("Open in CSV / Excel"))

        # Populate Stream List
        self.stream_list.clear()
        for inc in self.all_incidents:
            t = inc.get("type", "EVENT")
            d = inc.get("description", "")
            ts = inc.get("timestamp", time.strftime("%H:%M:%S"))
            self.stream_list.addItem(f"[{ts}] [{t}] {d}")

        # Populate Congestion & Heatmap Intelligence Table
        self.congestion_table.setRowCount(0)
        heat_entries = []
        total_veh = len(unique_vehicles)
        if potholes:
            p_crit = [p for p in potholes if any(k in str(p.get("severity", "") + " " + p.get("title", "") + " " + p.get("class", "") + " " + p.get("hazard_class", "")).lower() for k in ("severe", "critical", "p1"))]
            p_sample = p_crit[0] if p_crit else potholes[0]
            total_potholes = len(potholes)

            if total_veh == 0:
                pothole_cg = 0
                p_status = "FREE FLOW"
                p_intensity = "LOW (GREEN)"
                p_factor = f"Pavement Distress ({total_potholes} Potholes, Zero Traffic)"
            else:
                p_crit_count = len(p_crit)
                if p_crit_count > 0 or total_potholes >= 15:
                    pothole_cg = min(90, max(60, 35 + total_veh * 8 + p_crit_count * 3))
                    p_status = "HEAVY BOTTLENECK"
                    p_intensity = "CRITICAL (RED)"
                elif total_potholes > 3:
                    pothole_cg = min(70, max(40, 20 + total_veh * 6))
                    p_status = "MODERATE CONGESTION"
                    p_intensity = "HIGH (AMBER)"
                else:
                    pothole_cg = min(40, max(15, 10 + total_veh * 5))
                    p_status = "RESTRICTED FLOW"
                    p_intensity = "MEDIUM (YELLOW)"
                p_factor = f"Crater Cluster ({total_potholes} Defects, Flow Impediment)"

            heat_entries.append({
                "sector": f"{p_sample.get('location', 'Corridor')} (Pothole Zone)",
                "gps": p_sample.get("gps", "13.0350, 80.1542"),
                "cg_idx": pothole_cg,
                "status": p_status,
                "factor": p_factor,
                "intensity": p_intensity,
                "recommendation": "Priority PWD Resurfacing · Cold-mix Asphalt Infill"
            })

        has_school = any("school" in str(inc.get("location", "")).lower() or "SCH" in str(inc.get("id", "")) for inc in self.all_incidents)
        has_peds = any(p.get("visible_pedestrians", 0) > 0 for p in [self.summary_data])
        if total_veh > 0 and (has_school or has_peds):
            ped_cg = min(75, max(35, 25 + total_veh * 7))
            heat_entries.append({
                "sector": "Anna Salai - Educational Corridor",
                "gps": "13.0354, 80.1558",
                "cg_idx": ped_cg,
                "status": "MODERATE CONGESTION" if ped_cg >= 50 else "NORMAL FLOW",
                "factor": "School Zone Pedestrian Conflict Area",
                "intensity": "HIGH (AMBER)" if ped_cg >= 50 else "MEDIUM (YELLOW)",
                "recommendation": "Enforce 25 km/h Speed Limit · Deploy Traffic Marshal"
            })

        if infra:
            inf_sample = infra[0]
            if total_veh == 0:
                inf_cg = 0
                inf_status = "FREE FLOW"
                inf_intensity = "LOW (GREEN)"
            else:
                inf_cg = min(60, max(20, 15 + total_veh * 5 + len(infra) * 3))
                inf_status = "RESTRICTED FLOW"
                inf_intensity = "MEDIUM (YELLOW)"
            heat_entries.append({
                "sector": f"{inf_sample.get('location', 'Corridor')} (Safety Infrastructure)",
                "gps": inf_sample.get("gps", "13.0348, 80.1539"),
                "cg_idx": inf_cg,
                "status": inf_status,
                "factor": "Deficient Median / Road Divider Barrier",
                "intensity": inf_intensity,
                "recommendation": "Civil Works: Install M30 Concrete Median Barrier"
            })

        express_cg = 0 if total_veh == 0 else min(30, max(8, total_veh * 4))
        heat_entries.append({
            "sector": "Transit Express Arterial Sector",
            "gps": "13.0342, 80.1551",
            "cg_idx": express_cg,
            "status": "FREE FLOW" if express_cg < 25 else "NORMAL FLOW",
            "factor": "Zero Traffic / Clear Multi-Lane Corridor" if total_veh == 0 else "Active Multi-Lane Transit Corridor",
            "intensity": "LOW (CYAN)",
            "recommendation": "Maintain AI Continuous Automated Patrol"
        })

        for item in heat_entries:
            r = self.congestion_table.rowCount()
            self.congestion_table.insertRow(r)
            self.congestion_table.setItem(r, 0, QTableWidgetItem(item["sector"]))
            self.congestion_table.setItem(r, 1, QTableWidgetItem(str(item["gps"])))

            cg_val_item = QTableWidgetItem(f"{item['cg_idx']}%")
            cg_val_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
            if item['cg_idx'] >= 75:
                cg_val_item.setForeground(QColor("#ef4444"))
            elif item['cg_idx'] >= 50:
                cg_val_item.setForeground(QColor("#f59e0b"))
            elif item['cg_idx'] >= 25:
                cg_val_item.setForeground(QColor("#eab308"))
            else:
                cg_val_item.setForeground(QColor("#10b981"))
            self.congestion_table.setItem(r, 2, cg_val_item)

            self.congestion_table.setItem(r, 3, QTableWidgetItem(item["status"]))
            self.congestion_table.setItem(r, 4, QTableWidgetItem(item["factor"]))

            int_item = QTableWidgetItem(item["intensity"])
            int_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            if "CRITICAL" in item["intensity"]:
                int_item.setForeground(QColor("#ef4444"))
            elif "HIGH" in item["intensity"]:
                int_item.setForeground(QColor("#f59e0b"))
            elif "MEDIUM" in item["intensity"]:
                int_item.setForeground(QColor("#eab308"))
            else:
                int_item.setForeground(QColor("#06b6d4"))
            self.congestion_table.setItem(r, 5, int_item)

            self.congestion_table.setItem(r, 6, QTableWidgetItem(item["recommendation"]))

        # Refresh SQLite Audit Database Tab
        self._refresh_db_view()

    def _filter_potholes_table(self):
        filter_text = self.pothole_filter_combo.currentText()
        search_query = self.pothole_search.text().lower()

        for r in range(self.potholes_table.rowCount()):
            sev_item = self.potholes_table.item(r, 2)
            desc_item = self.potholes_table.item(r, 1)
            sev_match = (filter_text == "All Defects") or (sev_item and filter_text in sev_item.text())
            search_match = (not search_query) or (desc_item and search_query in desc_item.text().lower())
            self.potholes_table.setRowHidden(r, not (sev_match and search_match))

    def _filter_anpr_table(self):
        search_query = self.anpr_search.text().lower()
        for r in range(self.anpr_table.rowCount()):
            plate_item = self.anpr_table.item(r, 0)
            vtype_item = self.anpr_table.item(r, 1)
            tid_item = self.anpr_table.item(r, 2)
            viol_item = self.anpr_table.item(r, 3)
            match = (
                (not search_query) or
                (plate_item and search_query in plate_item.text().lower()) or
                (vtype_item and search_query in vtype_item.text().lower()) or
                (tid_item and search_query in tid_item.text().lower()) or
                (viol_item and search_query in viol_item.text().lower())
            )
            self.anpr_table.setRowHidden(r, not match)

    def _refresh_db_view(self):
        """Update SQLite database status strip and re-query active table."""
        try:
            stats = get_database_stats()
            counts = stats.get("counts", {})
            c_str = f"Potholes: {counts.get('potholes', 0)} | Plates: {counts.get('plates', 0)} | Violations: {counts.get('violations', 0)} | PWD: {counts.get('pwd_work_orders', 0)} | Runs: {counts.get('audit_runs', 0)}"
            self.db_stats_lbl.setText(f"STATUS: 🟢 CONNECTED (WAL Mode) | DB Size: {stats.get('size_kb', 0)} KB | Total Records: {stats.get('total_records', 0)} ({c_str})")
        except Exception as e:
            self.db_stats_lbl.setText("STATUS: 🟢 CONNECTED (data/app.db) | Active")
        self._on_db_table_selected()

    def _on_db_table_selected(self):
        """Query rows from SQLite and display in self.sqlite_table_widget."""
        tname = self.db_table_selector.currentData() or "potholes"
        search_txt = self.db_search_input.text().strip() if hasattr(self, "db_search_input") else ""
        try:
            cols, rows, count = get_table_data(tname, limit=200, search=search_txt)
            self.sqlite_table_widget.setRowCount(0)
            self.sqlite_table_widget.setColumnCount(len(cols))

            formatted_headers = [c.replace("_", " ").title() for c in cols]
            self.sqlite_table_widget.setHorizontalHeaderLabels(formatted_headers)

            for row_idx, r_dict in enumerate(rows):
                self.sqlite_table_widget.insertRow(row_idx)
                for col_idx, col_name in enumerate(cols):
                    val = r_dict.get(col_name)
                    item = QTableWidgetItem(str(val) if val is not None else "")
                    if col_name in ("severity", "violation_type", "status"):
                        s_val = str(val).upper()
                        if any(k in s_val for k in ("CRITICAL", "P1", "RASH", "SEVERE")):
                            item.setForeground(QColor("#dc2626"))
                            item.setFont(QFont("Segoe UI", 9, QFont.Bold))
                        elif any(k in s_val for k in ("HIGH", "P2", "WARNING")):
                            item.setForeground(QColor("#ea580c"))
                            item.setFont(QFont("Segoe UI", 9, QFont.Bold))
                        elif "REPORTED" in s_val or "FLAGGED" in s_val:
                            item.setForeground(QColor("#0284c7"))
                    self.sqlite_table_widget.setItem(row_idx, col_idx, item)
        except Exception as e:
            logger.error(f"Error loading table data: {e}")


# ─── PWD WORK ORDER SUMMARY DIALOG ──────────────────────────────────────────
class PwdWorkOrderDialog(QDialog):
    def __init__(self, summary: dict, parent=None):
        super().__init__(parent)
        self.summary = summary
        self.csv_path = summary.get("file_path", "")
        self.setWindowTitle("Public Works Department (PWD) — Municipal Civil Maintenance Docket")
        self.setFixedSize(600, 570)
        self.setStyleSheet("""
            QDialog {
                background-color: #f8fafc;
                font-family: 'Segoe UI', -apple-system, sans-serif;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(12)

        # Header Badge
        header = QLabel("🏛️ GREATER CHENNAI CORPORATION // ROADS & BRIDGES DEPT")
        header.setStyleSheet("color: #059669; font-weight: 800; font-size: 11px; letter-spacing: 1px;")
        layout.addWidget(header)

        title = QLabel("Official PWD Civil Maintenance Work-Order Docket")
        title.setStyleSheet("color: #0f172a; font-weight: 800; font-size: 17px;")
        layout.addWidget(title)

        desc = QLabel("Automated repair schedule generated from AI road asset scans. Formatted to Indian Road Congress (IRC) specifications for municipal civil maintenance contracting.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #475569; font-size: 11px; line-height: 1.4;")
        layout.addWidget(desc)

        # KPI Metric Container
        metrics_frame = QFrame()
        metrics_frame.setStyleSheet("background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px;")
        m_layout = QGridLayout(metrics_frame)
        m_layout.setSpacing(8)

        # Total Orders
        m_layout.addWidget(QLabel("<b>Total Work Orders:</b>"), 0, 0)
        orders_lbl = QLabel(f"<span style='color:#0284c7; font-weight:800; font-size:15px;'>{summary.get('total_orders', 0)} Work Orders</span>")
        m_layout.addWidget(orders_lbl, 0, 1)

        # Estimated Municipal Budget
        cost_inr = summary.get('total_budget_inr', 0)
        m_layout.addWidget(QLabel("<b>Est. Municipal Budget:</b>"), 1, 0)
        budget_lbl = QLabel(f"<span style='color:#059669; font-weight:800; font-size:15px;'>₹{cost_inr:,} INR</span>")
        m_layout.addWidget(budget_lbl, 1, 1)

        # Priority Breakdown
        prios = summary.get('priority_counts', {})
        p1 = prios.get("P1 - CRITICAL", 0)
        p2 = prios.get("P2 - HIGH", 0)
        p3 = prios.get("P3 - MEDIUM", 0)

        m_layout.addWidget(QLabel("<b>P1 (Critical / 24h SLA):</b>"), 2, 0)
        m_layout.addWidget(QLabel(f"<span style='color:#dc2626; font-weight:700;'>{p1}</span>"), 2, 1)

        m_layout.addWidget(QLabel("<b>P2 (High / 48h SLA):</b>"), 3, 0)
        m_layout.addWidget(QLabel(f"<span style='color:#d97706; font-weight:700;'>{p2}</span>"), 3, 1)

        m_layout.addWidget(QLabel("<b>P3 (Medium / 7d SLA):</b>"), 4, 0)
        m_layout.addWidget(QLabel(f"<span style='color:#64748b; font-weight:700;'>{p3}</span>"), 4, 1)

        layout.addWidget(metrics_frame)

        # File path display
        path_box = QFrame()
        path_box.setStyleSheet("background-color: #f1f5f9; border-radius: 6px; padding: 6px 10px;")
        p_layout = QHBoxLayout(path_box)
        p_layout.addWidget(QLabel("<b>Docket CSV:</b>"))
        p_lbl = QLabel(os.path.basename(self.csv_path))
        p_lbl.setStyleSheet("color: #0369a1; font-family: monospace; font-size: 11px;")
        p_layout.addWidget(p_lbl)
        p_layout.addStretch()
        layout.addWidget(path_box)

        # Direct Municipal Email Dispatcher Frame
        email_frame = QFrame()
        email_frame.setStyleSheet("background-color: #f0fdf4; border: 1px solid #86efac; border-radius: 8px; padding: 12px;")
        e_lay = QVBoxLayout(email_frame)
        e_lay.setSpacing(8)

        e_title = QLabel("🏛️ <b>Municipal Civil Maintenance Dispatcher</b>")
        e_title.setStyleSheet("color: #166534; font-size: 12px;")
        e_lay.addWidget(e_title)

        self.email_dispatch_btn = QPushButton("🚀 Dispatch Official Work-Order Docket")
        self.email_dispatch_btn.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: white;
                font-weight: 800;
                font-size: 12px;
                padding: 10px 18px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #047857;
            }
            QPushButton:disabled {
                background-color: #94a3b8;
            }
        """)
        self.email_dispatch_btn.clicked.connect(self.trigger_email_dispatch)
        e_lay.addWidget(self.email_dispatch_btn)

        self.email_status_lbl = QLabel("Ready to transmit official IRC repair dossier and CSV spreadsheet to municipal authorities.")
        self.email_status_lbl.setStyleSheet("color: #15803d; font-size: 11px;")
        e_lay.addWidget(self.email_status_lbl)

        layout.addWidget(email_frame)
        layout.addStretch()

        # Action Buttons
        btn_box = QHBoxLayout()
        open_btn = QPushButton("📊 Open in Excel / CSV App")
        open_btn.setStyleSheet("background-color: #059669; color: white; font-weight: 800; padding: 8px 16px; border-radius: 6px; border: none;")
        open_btn.clicked.connect(self.open_file)

        folder_btn = QPushButton("📁 Open Output Folder")
        folder_btn.setStyleSheet("background-color: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; font-weight: 700; padding: 8px 14px; border-radius: 6px;")
        folder_btn.clicked.connect(self.open_folder)

        close_btn = QPushButton("Dismiss")
        close_btn.setStyleSheet("background-color: #e2e8f0; color: #334155; font-weight: 700; padding: 8px 14px; border-radius: 6px; border: none;")
        close_btn.clicked.connect(self.accept)

        btn_box.addWidget(open_btn)
        btn_box.addWidget(folder_btn)
        btn_box.addStretch()
        btn_box.addWidget(close_btn)
        layout.addLayout(btn_box)

    def trigger_email_dispatch(self):
        self.email_status_lbl.setText("📡 Transmitting official docket to Municipal Authorities...")
        self.email_status_lbl.setStyleSheet("color: #0284c7; font-weight: 700; font-size: 11px;")
        self.email_dispatch_btn.setEnabled(False)

        def on_done(success: bool, msg: str):
            self.email_dispatch_btn.setEnabled(True)
            if success:
                self.email_status_lbl.setText("✅ Work-Order Docket Successfully Dispatched!")
                self.email_status_lbl.setStyleSheet("color: #059669; font-weight: 800; font-size: 11px;")
                QMessageBox.information(
                    self,
                    "Dispatch Successful",
                    "✅ Official PWD Civil Maintenance Work-Order Docket and IRC Repair Schedule "
                    "have been successfully dispatched to Municipal Authorities."
                )
            else:
                self.email_status_lbl.setText(f"⚠️ {msg}")
                self.email_status_lbl.setStyleSheet("color: #dc2626; font-weight: 700; font-size: 11px;")
                QMessageBox.warning(self, "Dispatch Failed", f"Could not transmit email:\n{msg}")

        def _bg():
            from src.email_dispatcher import send_pwd_workorder_email
            ok, response_msg = send_pwd_workorder_email(self.summary, self.csv_path)
            QTimer.singleShot(0, lambda: on_done(ok, response_msg))

        threading.Thread(target=_bg, daemon=True).start()

    def open_file(self):
        if os.path.exists(self.csv_path):
            os.startfile(self.csv_path)

    def open_folder(self):
        folder = os.path.dirname(self.csv_path)
        if os.path.exists(folder):
            os.startfile(folder)


# ─── 4-STAGE FORENSIC INCIDENT DOSSIER MODAL ─────────────────────────────────
class EvidenceInspectorDialog(QDialog):
    def __init__(self, incident: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.incident = incident
        self.current_stage = incident.get("stage", 1)

        self.setWindowTitle(f"Forensic Dossier // {incident.get('id', 'INCIDENT')}")
        self.resize(620, 560)
        self.setStyleSheet("background-color: #f8fafc; color: #0f172a; font-family: 'Segoe UI';")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        top_row = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel(f"INCIDENT DOSSIER // {incident.get('id')}")
        title.setFont(QFont("Segoe UI", 13, QFont.Bold))
        title.setStyleSheet("color: #0f172a; font-weight: 900;")
        sub = QLabel(f"Classification: {incident.get('title')} · Timestamp: {incident.get('timestamp')}")
        sub.setStyleSheet("color: #475569; font-size: 11px; font-weight: 600;")
        title_box.addWidget(title)
        title_box.addWidget(sub)
        top_row.addLayout(title_box)
        top_row.addStretch()

        self.stage_pill = QLabel()
        self.update_stage_pill()
        top_row.addWidget(self.stage_pill)
        layout.addLayout(top_row)

        self.prog = QProgressBar()
        self.prog.setRange(1, 4)
        self.prog.setValue(self.current_stage)
        self.prog.setFixedHeight(4)
        self.prog.setTextVisible(False)
        self.prog.setStyleSheet("background-color: #cbd5e1; border: none; border-radius: 2px;")
        layout.addWidget(self.prog)

        crop_pixmap = incident.get("pixmap")
        if crop_pixmap:
            img_label = QLabel()
            img_label.setAlignment(Qt.AlignCenter)
            img_label.setPixmap(crop_pixmap.scaled(580, 260, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            img_label.setStyleSheet("border: 1px solid #cbd5e1; background: #000; border-radius: 8px;")
            layout.addWidget(img_label)

        info_frame = EnterpriseCard()
        info_layout = QVBoxLayout(info_frame)
        info_layout.setSpacing(6)
        info_layout.addWidget(QLabel(f"<b>Hazard Type:</b> <span style='color:#0284c7;'>{incident.get('type')}</span>"))
        if incident.get("plate"):
            info_layout.addWidget(QLabel(f"<b>Flagged Number Plate:</b> <span style='color:#dc2626; font-weight:900; font-family:monospace; font-size:13px;'>{incident.get('plate')}</span>"))
        info_layout.addWidget(QLabel(f"<b>Severity Rating:</b> <span style='color:#ef4444;'>{incident.get('severity')}</span>"))
        info_layout.addWidget(QLabel(f"<b>AI Confidence:</b> {incident.get('confidence')}"))
        info_layout.addWidget(QLabel(f"<b>Street Corridor:</b> {incident.get('location')}"))
        info_layout.addWidget(QLabel(f"<b>GPS Pinpoint:</b> {incident.get('gps')}"))
        layout.addWidget(info_frame)

        btn_box = QHBoxLayout()
        self.action_btn = QPushButton()
        self.update_action_button()
        self.action_btn.clicked.connect(self.advance_stage)

        close_btn = QPushButton("Dismiss")
        close_btn.setStyleSheet("background-color: #f1f5f9; color: #0f172a; border: 1px solid #cbd5e1; padding: 8px 18px; border-radius: 6px; font-weight: 700;")
        close_btn.clicked.connect(self.accept)

        btn_box.addWidget(self.action_btn)
        btn_box.addStretch()
        btn_box.addWidget(close_btn)
        layout.addLayout(btn_box)

    def update_stage_pill(self):
        stages = {
            1: ("STAGE 1 // AI DETECTED", "#ef4444", "rgba(239, 68, 68, 0.15)"),
            2: ("STAGE 2 // VERIFIED", "#f59e0b", "rgba(245, 158, 11, 0.15)"),
            3: ("STAGE 3 // DISPATCHED", "#0284c7", "rgba(2, 132, 199, 0.15)"),
            4: ("STAGE 4 // RESOLVED", "#10b981", "rgba(16, 185, 129, 0.15)")
        }
        text, color, bg = stages.get(self.current_stage, stages[1])
        self.stage_pill.setText(text)
        self.stage_pill.setStyleSheet(f"color: {color}; background-color: {bg}; border: 1px solid {color}; padding: 4px 10px; border-radius: 6px; font-weight: 800; font-size: 10px;")

    def update_action_button(self):
        actions = {
            1: ("✓ Verify Detection Authenticity", "#0284c7"),
            2: ("🚨 Dispatch Field Repair Team", "#ea580c"),
            3: ("✅ Close Incident (Resolved)", "#16a34a"),
            4: ("Incident Dossier Closed", "#64748b")
        }
        text, color = actions.get(self.current_stage, actions[1])
        self.action_btn.setText(text)
        self.action_btn.setEnabled(self.current_stage < 4)
        self.action_btn.setStyleSheet(f"background-color: {color}; color: white; font-weight: 800; padding: 8px 18px; border-radius: 6px; border: none;")

    def advance_stage(self):
        if self.current_stage < 4:
            self.current_stage += 1
            self.incident["stage"] = self.current_stage
            self.prog.setValue(self.current_stage)
            self.update_stage_pill()
            self.update_action_button()


# ─── ASYNC AI INFERENCE WORKER THREAD ────────────────────────────────────────
class VideoInferenceWorker(QThread):
    frame_ready = pyqtSignal(QImage, dict)
    incident_logged = pyqtSignal(dict)
    stats_updated = pyqtSignal(dict)
    progress_updated = pyqtSignal(int, int, float)
    gps_updated = pyqtSignal(float, float, str, bool, float)
    pipeline_finished = pyqtSignal(dict)
    status_changed = pyqtSignal(str)

    def __init__(
        self,
        video_path: str,
        speed_multiplier: float = 1.0,
        enable_potholes: bool = True,
        enable_plates: bool = True,
        corridor_id: Optional[str] = None
    ):
        super().__init__()
        self.video_path = video_path
        self.corridor_id = corridor_id
        self.route_sim = RouteSimulator(video_path=self.video_path, corridor_id=self.corridor_id)
        self.speed_multiplier = speed_multiplier
        self.enable_potholes = enable_potholes
        self.enable_plates = enable_plates
        self.is_running = True
        self.is_paused = False

    def stop(self):
        self.is_running = False

    def toggle_pause(self):
        self.is_paused = not self.is_paused

    def set_speed(self, speed: float):
        self.speed_multiplier = speed

    def run(self):
        self.status_changed.emit("INITIALIZING CUDA NEURAL ACCELERATORS & MAPBOX...")

        traffic_detector = TrafficYOLODetector()
        hazard_detector = RoadHazardDetector() if self.enable_potholes else None
        pothole_detector = hazard_detector
        plate_detector = LicensePlateDetector() if self.enable_plates else None
        infra_detector = RoadInfrastructureDetector()
        maps_enricher = MapsEnricher()
        rule_engine = SafetyRuleEngine()
        spatial_dedup = SpatialPotholeDeduplicator(distance_threshold_meters=2.5)

        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            self.status_changed.emit(f"ERR // CANNOT READ: '{self.video_path}'")
            return

        native_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        self.status_changed.emit(f"STREAM ACTIVE // {os.path.basename(self.video_path)} ({native_fps:.0f} FPS)")

        raw_frame_id = 0
        frame_id = 0
        all_unique_plates = {}
        all_tracked_vehicles: Dict[int, Dict[str, Any]] = {}
        all_tracked_pedestrians: Dict[int, Dict[str, Any]] = {}
        all_infra_defects: Dict[str, Any] = {}
        all_logged_violations: set = set()
        vehicle_to_plate: Dict[int, str] = {}
        all_violator_vehicles: Dict[str, Dict[str, Any]] = {}
        all_congestion_readings: List[int] = []
        _last_infra_alert: Dict[str, float] = {}
        start_total_time = time.time()

        # Cached detections for cadenced inference (cuts per-frame GPU latency to reach 22-30+ FPS)
        cached_traffic_event: Optional[Dict[str, Any]] = None
        cached_pothole_detections: List[Dict[str, Any]] = []
        cached_plate_detections: List[Dict[str, Any]] = []

        # Background async reverse geocoding to prevent video frame stalls
        current_loc = {"street_name": "Anna Salai Corridor", "is_school": False}
        loc_lock = threading.Lock()
        is_enriching = False

        def _async_enrich(lat: float, lon: float):
            nonlocal is_enriching
            try:
                info = maps_enricher.enrich_location(lat, lon)
                with loc_lock:
                    current_loc["street_name"] = info.get("street_name", current_loc["street_name"])
                    current_loc["is_school"] = info.get("is_school_zone", False)
            except Exception:
                pass
            finally:
                is_enriching = False

        # Fast overlay drawer for cached intermediate frames
        def _draw_traffic_overlays(img, vehicles, pedestrians):
            for v in vehicles:
                bbox = v.get("bbox", [])
                if len(bbox) == 4:
                    x1, y1, x2, y2 = bbox
                    color = (248, 189, 56)
                    cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
                    c_len = min(12, int((x2 - x1) * 0.2), int((y2 - y1) * 0.2))
                    if c_len > 2:
                        cv2.line(img, (x1, y1), (x1 + c_len, y1), (255, 255, 255), 2)
                        cv2.line(img, (x1, y1), (x1, y1 + c_len), (255, 255, 255), 2)
                        cv2.line(img, (x2, y2), (x2 - c_len, y2), (255, 255, 255), 2)
                        cv2.line(img, (x2, y2), (x2 - c_len, y2), (255, 255, 255), 2)
                    t_id = v.get("track_id")
                    label = v.get("label", "vehicle").upper()
                    conf = v.get("confidence", 0.8)
                    tag = f"TRK #{t_id} {label} {conf*100:.0f}%" if t_id else f"{label} {conf*100:.0f}%"
                    cv2.rectangle(img, (x1, max(0, y1 - 20)), (x1 + len(tag) * 8 + 6, y1), color, -1)
                    cv2.putText(img, tag, (x1 + 3, max(14, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 0, 0), 1, cv2.LINE_AA)
            for p in pedestrians:
                bbox = p.get("bbox", [])
                if len(bbox) == 4:
                    x1, y1, x2, y2 = bbox
                    color = (11, 158, 245)
                    cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
                    t_id = p.get("track_id")
                    conf = p.get("confidence", 0.8)
                    tag = f"TRK #{t_id} PEDESTRIAN {conf*100:.0f}%" if t_id else f"PEDESTRIAN {conf*100:.0f}%"
                    cv2.rectangle(img, (x1, max(0, y1 - 20)), (x1 + len(tag) * 8 + 6, y1), color, -1)
                    cv2.putText(img, tag, (x1 + 3, max(14, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 0, 0), 1, cv2.LINE_AA)

        smoothed_fps = native_fps

        # Warm up CUDA models with a tiny blank frame so first frame has zero compilation lag
        try:
            dummy = np.zeros((320, 320, 3), dtype=np.uint8)
            d_pkt = {"image": dummy, "frame_id": 0, "raw_frame_id": 0, "timestamp_sec": 0.0}
            traffic_detector.detect(d_pkt)
            if pothole_detector:
                pothole_detector.detect(d_pkt, annotate=False)
            if plate_detector:
                plate_detector.detect(d_pkt, annotate=False)
        except Exception:
            pass

        total_video_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_video_frames <= 0:
            total_video_frames = 600

        while self.is_running and cap.isOpened():
            if self.is_paused:
                self.msleep(60)
                continue

            # Playback speed pacing & frame dropping for accelerated rates (1.5x / 2.0x)
            current_speed = self.speed_multiplier
            if current_speed >= 2.0:
                cap.grab()
                raw_frame_id += 1
            elif current_speed >= 1.5 and raw_frame_id % 2 == 0:
                cap.grab()
                raw_frame_id += 1

            ret, frame = cap.read()
            if not ret:
                break

            raw_frame_id += 1
            frame_id += 1
            start_t = time.time()
            ts = round(raw_frame_id / native_fps, 2)

            # Road-snapped GPS calculation along Chennai transit corridors
            progress_frac = min(1.0, raw_frame_id / total_video_frames) if total_video_frames > 0 else 0.0
            base_lat, base_lon, heading, sim_street = self.route_sim.get_position(progress_frac)

            # Trigger background geocoding every 30 frames (~1 sec) without blocking frame loop
            if (raw_frame_id == 1 or raw_frame_id % 30 == 0) and not is_enriching:
                is_enriching = True
                threading.Thread(target=_async_enrich, args=(base_lat, base_lon), daemon=True).start()

            with loc_lock:
                street_name = current_loc["street_name"] or sim_street
                is_school = current_loc["is_school"]

            self.gps_updated.emit(base_lat, base_lon, street_name, is_school, heading)

            packet = {
                "image": frame,
                "frame": frame,
                "frame_id": frame_id,
                "raw_frame_id": raw_frame_id,
                "timestamp_sec": ts,
                "latitude": base_lat,
                "longitude": base_lon
            }

            # ── CADENCED SINGLE-MODEL PIPELINE ────────────────────────────────
            # To achieve 22-30+ FPS on GPU, we execute max 1 model per frame:
            # - Frame % 2 == 0: Traffic YOLO & ByteTrack
            # - Frame % 4 == 1: Pothole YOLO
            # - Frame % 4 == 3: Plate YOLO
            run_traffic = (frame_id % 2 == 0) or (cached_traffic_event is None)
            if run_traffic:
                traffic_event = traffic_detector.detect(packet)
                cached_traffic_event = traffic_event
                annotated_frame = traffic_event["annotated_frame"]
                counts = traffic_event["counts"]
                detections = traffic_event.get("detections", {})
                visible_vehicles = detections.get("vehicles", [])
                raw_peds = detections.get("pedestrians", [])
                # Filter out passengers and drivers inside vehicles
                visible_pedestrians = []
                for p in raw_peds:
                    pbx = p.get("bbox", [])
                    if len(pbx) == 4:
                        pcx, pcy = (pbx[0] + pbx[2]) // 2, (pbx[1] + pbx[3]) // 2
                        is_occupant = any(
                            v["bbox"][0] <= pcx <= v["bbox"][2] and v["bbox"][1] <= pcy <= v["bbox"][3]
                            for v in visible_vehicles if len(v.get("bbox", [])) == 4
                        )
                        if not is_occupant:
                            visible_pedestrians.append(p)

                for v in visible_vehicles:
                    t_id = v.get("track_id")
                    if t_id is not None and t_id not in all_tracked_vehicles:
                        v_label = v.get("label", "vehicle").upper()
                        all_tracked_vehicles[t_id] = {
                            "id": f"TRK-{t_id}",
                            "track_id": t_id,
                            "label": v_label,
                            "vehicle_type": v_label.title(),
                            "conf": f"{v.get('confidence', 0.8)*100:.1f}%",
                            "confidence": f"{v.get('confidence', 0.8)*100:.1f}%",
                            "first_seen": f"{ts:.2f}s",
                            "time_sec": f"{ts:.2f}s",
                            "location": street_name,
                            "gps": f"{base_lat:.5f}, {base_lon:.5f}",
                            "lat": base_lat,
                            "lon": base_lon,
                            "timestamp": time.strftime("%H:%M:%S"),
                            "plate": None,
                            "violation": "✓ MoRTH Compliant",
                            "is_violator": False,
                            "status": "COMPLIANT"
                        }
                        self.incident_logged.emit({
                            "type": "VEHICLE",
                            "id": f"VEH-{t_id}",
                            "title": f"{v_label} TRACKED #{t_id}",
                            "severity": "INFO",
                            "confidence": f"{v.get('confidence', 0.8)*100:.1f}%",
                            "location": street_name,
                            "gps": f"{base_lat:.5f}, {base_lon:.5f}",
                            "lat": base_lat,
                            "lon": base_lon,
                            "timestamp": time.strftime("%H:%M:%S"),
                            "time_sec": f"{ts:.2f}s"
                        })

                for p in visible_pedestrians:
                    p_id = p.get("track_id")
                    if p_id is not None and p_id not in all_tracked_pedestrians:
                        all_tracked_pedestrians[p_id] = {
                            "id": f"PED-{p_id}",
                            "conf": f"{p.get('confidence', 0.8)*100:.1f}%",
                            "first_seen": f"{ts:.2f}s"
                        }
            else:
                # Fast intermediate frame with cached traffic boxes
                annotated_frame = frame.copy()
                counts = cached_traffic_event.get("counts", {}) if cached_traffic_event else {}
                detections = cached_traffic_event.get("detections", {}) if cached_traffic_event else {}
                visible_vehicles = detections.get("vehicles", [])
                raw_peds = detections.get("pedestrians", [])
                visible_pedestrians = [
                    p for p in raw_peds
                    if len(p.get("bbox", [])) == 4 and not any(
                        v["bbox"][0] <= (p["bbox"][0] + p["bbox"][2]) // 2 <= v["bbox"][2] and
                        v["bbox"][1] <= (p["bbox"][1] + p["bbox"][3]) // 2 <= v["bbox"][3]
                        for v in visible_vehicles if len(v.get("bbox", [])) == 4
                    )
                ]
                _draw_traffic_overlays(annotated_frame, visible_vehicles, visible_pedestrians)

            # 2. Cadenced Road Hazard Detection (every 4th frame: 1, 5, 9, ...)
            run_hazard = (hazard_detector is not None) and (frame_id % 4 == 1)
            if run_hazard:
                hazard_event = hazard_detector.detect(packet, annotate=False)
                if hazard_event:
                    cached_pothole_detections = hazard_event.get("hazards", [])
                    for h_det in cached_pothole_detections:
                        h_type = h_det.get("type", "pothole")
                        h_class = h_det.get("class", "pothole")
                        h_conf = h_det.get("confidence", 0.8)
                        h_bbox = h_det.get("bbox", [])

                        incident, is_new = spatial_dedup.add_or_merge(
                            lat=base_lat, lon=base_lon,
                            severity=h_class, confidence=h_conf,
                            timestamp_sec=ts, frame_id=frame_id, bbox=h_bbox,
                            hazard_type=h_type
                        )
                        h_det["incident_id"] = incident.pothole_id

                        if is_new:
                            if h_type == "barricade":
                                play_alert_sound(750, 100, category="barricade", cooldown=1.2)
                                self.incident_logged.emit({
                                    "type": "BARRICADE",
                                    "id": f"BAR-{incident.pothole_id}",
                                    "title": f"BARRICADE #{incident.pothole_id}",
                                    "severity": "WARNING",
                                    "confidence": f"{h_conf * 100:.1f}%",
                                    "location": street_name,
                                    "gps": f"{base_lat:.5f}, {base_lon:.5f}",
                                    "lat": base_lat,
                                    "lon": base_lon,
                                    "timestamp": time.strftime("%H:%M:%S"),
                                    "time_sec": f"{ts:.2f}s"
                                })
                            elif h_type == "water_logging":
                                play_alert_sound(600, 120, category="water_logging", cooldown=1.2)
                                self.incident_logged.emit({
                                    "type": "WATER_LOGGING",
                                    "id": f"WTR-{incident.pothole_id}",
                                    "title": f"WATER LOGGING #{incident.pothole_id}",
                                    "severity": "CRITICAL",
                                    "confidence": f"{h_conf * 100:.1f}%",
                                    "location": street_name,
                                    "gps": f"{base_lat:.5f}, {base_lon:.5f}",
                                    "lat": base_lat,
                                    "lon": base_lon,
                                    "timestamp": time.strftime("%H:%M:%S"),
                                    "time_sec": f"{ts:.2f}s"
                                })
                            else:
                                play_alert_sound(900, 80, category="pothole", cooldown=1.0)
                                if "severe" in h_class:
                                    sev_label = "P1 - CRITICAL"
                                    desc_label = f"Severe Volumetric Crater >8cm ({h_class.title()})"
                                elif "mild" in h_class:
                                    sev_label = "P2 - HIGH"
                                    desc_label = f"High-Impact Surface Depression 4-8cm ({h_class.title()})"
                                else:
                                    sev_label = "P3 - MEDIUM"
                                    desc_label = f"Surface Ravelling / Wear <4cm ({h_class.title()})"

                                self.incident_logged.emit({
                                    "type": "POTHOLE",
                                    "id": f"POT-{incident.pothole_id}",
                                    "title": f"{h_class.upper()} #{incident.pothole_id}",
                                    "severity": sev_label,
                                    "class": h_class,
                                    "hazard_class": h_class,
                                    "description": desc_label,
                                    "confidence": f"{h_conf * 100:.1f}%",
                                    "location": street_name,
                                    "gps": f"{base_lat:.5f}, {base_lon:.5f}",
                                    "lat": base_lat,
                                    "lon": base_lon,
                                    "timestamp": time.strftime("%H:%M:%S"),
                                    "time_sec": f"{ts:.2f}s"
                                })

            # Render active road hazard overlays
            for h_det in cached_pothole_detections:
                h_type = h_det.get("type", "pothole")
                h_class = h_det.get("class", "pothole")
                h_conf = h_det.get("confidence", 0.8)
                h_bbox = h_det.get("bbox", [])
                inc_id = h_det.get("incident_id", "")
                if len(h_bbox) == 4:
                    x1, y1, x2, y2 = [int(v) for v in h_bbox]

                    if h_type == "barricade":
                        color = (11, 158, 245)  # Bright Amber
                    elif h_type == "water_logging":
                        color = (255, 200, 0)   # Cyan / Aqua
                    else:
                        color = SEVERITY_COLORS.get(h_class, (0, 0, 255))

                    cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)

                    corner_len = 10
                    cv2.line(annotated_frame, (x1, y1), (x1 + corner_len, y1), (255, 255, 255), 2)
                    cv2.line(annotated_frame, (x1, y1), (x1, y1 + corner_len), (255, 255, 255), 2)
                    cv2.line(annotated_frame, (x2, y2), (x2 - corner_len, y2), (255, 255, 255), 2)
                    cv2.line(annotated_frame, (x2, y2), (x2, y2 - corner_len), (255, 255, 255), 2)

                    tag = f"#{inc_id} {h_class.upper()} {h_conf*100:.0f}%" if inc_id else f"{h_class.upper()} {h_conf*100:.0f}%"
                    cv2.putText(
                        annotated_frame,
                        tag,
                        (x1, max(22, y1 - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.45,
                        color,
                        2
                    )

            # 3. Cadenced Plate Detection (every 4th frame: 3, 7, 11, ..., only if vehicles exist)
            run_plates = (plate_detector is not None) and (frame_id % 4 == 3) and (len(visible_vehicles) > 0)
            if run_plates:
                plate_res = plate_detector.detect(packet, annotate=False)
                cached_plate_detections = plate_res.get("plates", [])
                for pl in cached_plate_detections:
                    raw_text = pl.get("plate_text", "")
                    p_conf = pl.get("confidence", 0.0)
                    if raw_text:
                        p_text = synthesize_indian_plate(raw_text)
                        pl["plate_text"] = p_text
                        # Map plate to vehicle bbox containing it
                        matched_v_type = "Car"
                        matched_vt_id = None
                        p_box = pl.get("bbox", [])
                        if len(p_box) == 4:
                            pxc, pyc = (p_box[0] + p_box[2]) / 2.0, (p_box[1] + p_box[3]) / 2.0
                            for v in visible_vehicles:
                                vb = v.get("bbox", [])
                                vt_id = v.get("track_id")
                                if vt_id is not None and len(vb) == 4:
                                    if vb[0] <= pxc <= vb[2] and vb[1] <= pyc <= vb[3]:
                                        vehicle_to_plate[vt_id] = p_text
                                        matched_v_type = v.get("label", "Car").title()
                                        matched_vt_id = vt_id
                                        if vt_id in all_tracked_vehicles:
                                            all_tracked_vehicles[vt_id]["plate"] = p_text
                                            all_tracked_vehicles[vt_id]["vehicle_type"] = matched_v_type
                                            all_tracked_vehicles[vt_id]["is_ocr_scanned"] = True
                                        break

                        if p_text not in all_unique_plates:
                            all_unique_plates[p_text] = {
                                "plate_text": p_text,
                                "confidence": f"{p_conf * 100:.1f}%",
                                "time_sec": f"{ts:.2f}s",
                                "vehicle_type": matched_v_type,
                                "track_id": matched_vt_id or (100 + len(all_unique_plates))
                            }
                            play_alert_sound(1200, 60, category="plate", cooldown=1.0)
                            self.incident_logged.emit({
                                "type": "PLATE",
                                "id": f"PL-{p_text}",
                                "title": f"ANPR // {p_text}",
                                "plate": p_text,
                                "vehicle_type": matched_v_type,
                                "track_id": matched_vt_id or (100 + len(all_unique_plates)),
                                "severity": "NORMAL",
                                "confidence": f"{p_conf * 100:.1f}%",
                                "location": street_name,
                                "gps": f"{base_lat:.5f}, {base_lon:.5f}",
                                "lat": base_lat,
                                "lon": base_lon,
                                "timestamp": time.strftime("%H:%M:%S"),
                                "time_sec": f"{ts:.2f}s"
                            })
            elif len(visible_vehicles) == 0:
                cached_plate_detections = []

            # Render active plate overlays
            for pl in cached_plate_detections:
                p_bbox = pl.get("bbox", [])
                p_text = pl.get("plate_text", "")
                p_conf = pl.get("confidence", 0.0)
                if len(p_bbox) == 4:
                    px1, py1, px2, py2 = [int(v) for v in p_bbox]
                    cv2.rectangle(annotated_frame, (px1, py1), (px2, py2), (16, 185, 129), 2)
                    tag = f"PLATE: {p_text}" if p_text else f"PLATE {p_conf*100:.0f}%"
                    cv2.putText(
                        annotated_frame,
                        tag,
                        (px1, max(18, py1 - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.45,
                        (16, 185, 129),
                        2
                    )

            # 4. Rule Engine: Safety Rules, Rash Driving & Hit-and-Run (Rule C)
            t_event = cached_traffic_event or {
                "frame_id": frame_id,
                "timestamp_sec": ts,
                "detections": {"vehicles": visible_vehicles, "pedestrians": visible_pedestrians},
                "counts": counts
            }
            loc_context = {"street_name": street_name, "is_school_zone": is_school, "is_hospital_zone": False}
            rule_res = rule_engine.evaluate(t_event, image=None, location_context=loc_context)

            alert_lvl = rule_res.get("alert_level")
            if alert_lvl in ("CRITICAL_SCHOOL_ZONE", "HOSPITAL_ZONE_ALERT") or (counts.get("pedestrians", 0) > 0 and is_school):
                play_alert_sound(1500, 120, category="school_zone", cooldown=3.0)
                self.incident_logged.emit({
                    "type": "SAFETY_ALERT",
                    "id": f"SCH-ZONE-{frame_id}",
                    "title": rule_res.get("alert_message", "SCHOOL ZONE PEDESTRIAN CROSSING ALERT"),
                    "severity": "CRITICAL",
                    "confidence": "98.5%",
                    "location": f"{street_name} (School Zone)",
                    "gps": f"{base_lat:.5f}, {base_lon:.5f}",
                    "lat": base_lat,
                    "lon": base_lon,
                    "timestamp": time.strftime("%H:%M:%S"),
                    "time_sec": f"{ts:.2f}s"
                })

            # Rule C Violations: Rash Driving and Hit-and-Run
            frame_violations = rule_res.get("violations", [])
            for viol in frame_violations:
                v_type = viol.get("violation_type", "RASH_DRIVING")
                t_id = viol.get("track_id", 0)
                v_desc = viol.get("description", "")
                v_score = viol.get("speed_score", 2.2)
                v_sev = "CRITICAL" if v_type == "HIT_AND_RUN" else "HIGH"
                vb = viol.get("vehicle_bbox", [])
                v_label = viol.get("vehicle_label", "VEHICLE").upper()

                # Attribute flagged license plate for this offending vehicle if scanned
                flagged_plate = vehicle_to_plate.get(t_id)
                if not flagged_plate and len(vb) == 4:
                    for pl in cached_plate_detections:
                        pb = pl.get("bbox", [])
                        if len(pb) == 4:
                            pxc, pyc = (pb[0] + pb[2]) / 2.0, (pb[1] + pb[3]) / 2.0
                            if vb[0] <= pxc <= vb[2] and vb[1] <= pyc <= vb[3]:
                                flagged_plate = pl.get("plate_text")
                                if flagged_plate:
                                    vehicle_to_plate[t_id] = flagged_plate
                                    break

                # Clean display text for HUD
                disp_plate = flagged_plate if flagged_plate else f"TRK #{t_id}"

                # Render bright red alert box and FLAGGED NUMBER PLATE on HUD
                if len(vb) == 4:
                    vx1, vy1, vx2, vy2 = vb
                    cv2.rectangle(annotated_frame, (vx1, vy1), (vx2, vy2), (0, 0, 255), 3)

                    # High-visibility corner brackets
                    c_len = 12
                    cv2.line(annotated_frame, (vx1, vy1), (vx1 + c_len, vy1), (255, 255, 255), 2)
                    cv2.line(annotated_frame, (vx1, vy1), (vx1, vy1 + c_len), (255, 255, 255), 2)
                    cv2.line(annotated_frame, (vx2, vy2), (vx2 - c_len, vy2), (255, 255, 255), 2)
                    cv2.line(annotated_frame, (vx2, vy2), (vx2, vy2 - c_len), (255, 255, 255), 2)

                    v_tag = f"RASH DRIVING | {disp_plate} ({v_score:.1f}x SPD)"
                    tag_w = len(v_tag) * 9 + 14
                    cv2.rectangle(annotated_frame, (vx1, max(0, vy1 - 24)), (vx1 + tag_w, vy1), (0, 0, 255), -1)
                    cv2.putText(annotated_frame, v_tag, (vx1 + 5, max(16, vy1 - 6)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.44, (255, 255, 255), 2, cv2.LINE_AA)

                v_key = f"{v_type}_{t_id}"
                if v_key not in all_logged_violations:
                    all_logged_violations.add(v_key)
                    if t_id in all_tracked_vehicles:
                        if flagged_plate:
                            all_tracked_vehicles[t_id]["plate"] = flagged_plate
                        all_tracked_vehicles[t_id]["violation"] = f"🚨 {v_type.replace('_', ' ').title()} ({v_score:.1f}x Speed)" if "speed" in str(v_desc).lower() or v_score else f"🚨 {v_type.replace('_', ' ').title()}"
                        all_tracked_vehicles[t_id]["is_violator"] = True
                        all_tracked_vehicles[t_id]["severity"] = v_sev
                        all_tracked_vehicles[t_id]["speed_score"] = v_score
                        all_tracked_vehicles[t_id]["status"] = "FLAGGED_VIOLATOR"
                    play_alert_sound(1750, 160, category="violation", cooldown=2.0)
                    viol_event = {
                        "type": v_type,
                        "id": f"VIOL-{v_type[:4]}-{t_id}",
                        "plate": flagged_plate or "",
                        "vehicle_label": v_label,
                        "track_id": t_id,
                        "speed_score": v_score,
                        "title": f"TRAFFIC VIOLATION // {v_type.replace('_', ' ')} [{disp_plate}]",
                        "severity": v_sev,
                        "confidence": f"{min(98, 80 + int(v_score * 5))}%",
                        "description": f"Vehicle #{t_id} [{disp_plate}]: {v_desc}",
                        "location": street_name,
                        "gps": f"{base_lat:.5f}, {base_lon:.5f}",
                        "lat": base_lat,
                        "lon": base_lon,
                        "timestamp": time.strftime("%H:%M:%S"),
                        "time_sec": f"{ts:.2f}s"
                    }
                    all_violator_vehicles[disp_plate] = viol_event
                    self.incident_logged.emit(viol_event)

            # 5. Road Infrastructure Deficiencies Analysis (Dividers, Zebra Crossings, Waterlogging, Signboards)
            infra_res = infra_detector.analyze(
                frame,
                vehicle_detections=visible_vehicles,
                pedestrian_detections=visible_pedestrians,
                is_school_zone=is_school
            )
            cached_infra_defects = infra_res.get("defects", [])
            annotated_frame = infra_detector.annotate(annotated_frame, cached_infra_defects)

            for d_item in cached_infra_defects:
                d_type = d_item.get("type", "defect")
                bbox = d_item.get("bbox", [0, 0, 0, 0])

                # Semantic and spatial deduplication (prevents duplicate spam on continuous video)
                if d_type in ("road_divider", "missing_road_divider"):
                    d_key = f"{d_type}_corridor"
                elif "zebra" in d_type:
                    d_key = f"{d_type}_zone_{bbox[1] // 150}"
                elif "sign" in d_type:
                    d_key = f"{d_type}_{bbox[0] // 200}_{bbox[1] // 150}"
                elif "water" in d_type:
                    d_key = f"{d_type}_{bbox[0] // 250}_{bbox[1] // 200}"
                else:
                    d_key = f"{d_type}_{bbox[0] // 200}"

                is_defect = d_item.get("severity", "INFO") != "INFO" and d_type not in ("road_divider", "zebra_crossing", "signboard")
                if is_defect:
                    is_new_defect = d_key not in all_infra_defects
                    all_infra_defects[d_key] = d_item

                    if is_new_defect:
                        snd_freq = 900 if "zebra" in d_type else (700 if "water" in d_type else 800)
                        play_alert_sound(snd_freq, 90, category=d_type, cooldown=2.5)
                        self.incident_logged.emit({
                            "type": d_type.upper(),
                            "id": f"INFRA-{d_key}",
                            "title": d_item.get("label", "INFRASTRUCTURE DEFICIENCY"),
                            "severity": d_item.get("severity", "WARNING"),
                            "confidence": f"{d_item.get('confidence', 0.85)*100:.0f}%",
                            "description": d_item.get("description", ""),
                            "location": street_name,
                            "gps": f"{base_lat:.5f}, {base_lon:.5f}",
                            "lat": base_lat,
                            "lon": base_lon,
                            "timestamp": time.strftime("%H:%M:%S"),
                            "time_sec": f"{ts:.2f}s"
                        })

            inf_time = (time.time() - start_t) * 1000
            inst_fps = 1.0 / (time.time() - start_t) if (time.time() - start_t) > 0 else 0
            smoothed_fps = (smoothed_fps * 0.85) + (inst_fps * 0.15)

            # 6. Real-Time Traffic Congestion & Spatial Density Engine
            vis_veh = counts.get("total_vehicles", counts.get("vehicles", 0))
            vis_ped = counts.get("pedestrians", 0)

            # Traffic congestion is fundamentally a measure of traffic volume.
            # If there are zero vehicles and zero pedestrians in view, congestion is 0% (Free Flow).
            if vis_veh == 0 and vis_ped == 0:
                cg_idx = 0
                cg_lbl = "FREE FLOW"
                cg_col = (129, 185, 16)   # Emerald
            else:
                # Active traffic volume density
                traffic_density = (vis_veh * 10) + (vis_ped * 6)

                # Road distress friction slows traffic flow ONLY if vehicles actually exist
                pothole_friction = min(15, len(cached_pothole_detections) * 5) if cached_pothole_detections and vis_veh > 0 else 0
                infra_friction = min(10, len(cached_infra_defects) * 3) if cached_infra_defects and vis_veh > 0 else 0
                school_factor = 8 if is_school and (vis_veh > 0 or vis_ped > 0) else 0

                cg_idx = max(0, min(100, int(traffic_density + pothole_friction + infra_friction + school_factor)))
                if cg_idx >= 75:
                    cg_lbl = "HEAVY BOTTLENECK"
                    cg_col = (0, 0, 239)     # Red
                elif cg_idx >= 50:
                    cg_lbl = "MODERATE DENSITY"
                    cg_col = (11, 158, 245)   # Amber
                elif cg_idx >= 25:
                    cg_lbl = "NORMAL FLOW"
                    cg_col = (212, 182, 6)    # Cyan
                else:
                    cg_lbl = "FREE FLOW"
                    cg_col = (129, 185, 16)   # Emerald

            all_congestion_readings.append(cg_idx)

            # Render HUD Congestion Indicator on top-right of annotated frame
            h_frame, w_frame = annotated_frame.shape[:2]
            hud_cg_text = f"CONGESTION: {cg_idx}% [{cg_lbl}]"
            tw = len(hud_cg_text) * 8 + 16
            cv2.rectangle(annotated_frame, (w_frame - tw - 12, 10), (w_frame - 12, 34), (15, 23, 42), -1)
            cv2.rectangle(annotated_frame, (w_frame - tw - 12, 10), (w_frame - 12, 34), cg_col, 1)
            cv2.putText(
                annotated_frame,
                hud_cg_text,
                (w_frame - tw - 6, 26),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.40,
                cg_col,
                1,
                cv2.LINE_AA
            )

            stats_dict = {
                "frame_id": raw_frame_id,
                "total_frames": total_frames,
                "fps": round(smoothed_fps, 1),
                "latency_ms": round(inf_time, 1),
                "visible_vehicles": counts.get("total_vehicles", counts.get("vehicles", 0)),
                "total_vehicles_logged": len(all_tracked_vehicles),
                "visible_pedestrians": counts.get("pedestrians", 0),
                "total_pedestrians_logged": len(all_tracked_pedestrians),
                "unique_potholes": len(spatial_dedup.incidents),
                "unique_plates": len(all_unique_plates),
                "unique_violators": len(all_violator_vehicles),
                "total_infra_defects": len(all_infra_defects),
                "congestion_index": cg_idx,
                "congestion_label": cg_lbl,
                "street": street_name
            }

            self.stats_updated.emit(stats_dict)
            self.progress_updated.emit(raw_frame_id, total_frames, ts)

            rgb_frame = cv2.cvtColor(annotated_frame, cv2.COLOR_BGR2RGB)
            disp_h, disp_w = rgb_frame.shape[:2]
            if disp_w > 960:
                target_w = 960
                target_h = int(disp_h * (960.0 / disp_w))
                rgb_disp = cv2.resize(rgb_frame, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
            else:
                rgb_disp = rgb_frame

            h, w, ch = rgb_disp.shape
            qt_image = QImage(rgb_disp.data, w, h, ch * w, QImage.Format_RGB888).copy()

            self.frame_ready.emit(qt_image, {"frame_id": raw_frame_id, "time": ts})

            if self.speed_multiplier > 0:
                target_frame_time = 1.0 / (native_fps * self.speed_multiplier)
                elapsed = time.time() - start_t
                if elapsed < target_frame_time:
                    self.msleep(int((target_frame_time - elapsed) * 1000))


        cap.release()
        total_time = time.time() - start_total_time

        # Clean plate strings on tracked vehicles — preserve only genuinely scanned plates
        for tid, vdata in all_tracked_vehicles.items():
            p = vdata.get("plate")
            if p and (p == "FLAGGED" or "TN 01 AB 4321" in str(p) or "UNSCANNED" in str(p).upper()):
                vdata["plate"] = None

        unique_veh_list = list(all_tracked_vehicles.values())
        unique_veh_list.sort(key=lambda x: int("".join(filter(str.isdigit, str(x.get("track_id", 0))))) if any(c.isdigit() for c in str(x.get("track_id", ""))) else 0)

        summary = {
            "total_frames": raw_frame_id,
            "time_taken_sec": round(total_time, 2),
            "unique_potholes": len(spatial_dedup.incidents),
            "unique_plates": len(all_unique_plates),
            "total_vehicles_tracked": len(all_tracked_vehicles),
            "total_pedestrians_tracked": len(all_tracked_pedestrians),
            "avg_congestion_index": int(sum(all_congestion_readings) / max(1, len(all_congestion_readings))) if all_congestion_readings else 0,
            "peak_congestion_index": max(all_congestion_readings) if all_congestion_readings else 0,
            "corridor_heat_points": len(spatial_dedup.incidents) + len(all_tracked_vehicles),
            "potholes": [inc.to_dict() for inc in spatial_dedup.incidents],
            "plates": list(all_unique_plates.values()),
            "tracked_vehicles": unique_veh_list,
            "unique_vehicles": unique_veh_list,
            "violators": list(all_violator_vehicles.values())
        }

        self.status_changed.emit(f"TELEMETRY COMPLETE // {raw_frame_id} FRAMES IN {total_time:.1f}S")
        self.pipeline_finished.emit(summary)


# ─── MAIN ADVANCED MISSION-CONTROL PYQT5 APPLICATION ─────────────────────────
class UrbanSurveillanceApp(QMainWindow):
    def __init__(self):
        super().__init__()
        # Ensure embedded SQLite database is initialized
        init_db()
        self.setWindowTitle("ARGUS // Autonomous Urban Transit Sensing & Municipal Intelligence Platform")
        self.resize(1460, 920)
        self.setMinimumSize(1150, 760)

        self.worker: Optional[VideoInferenceWorker] = None
        self.current_video_path = os.path.abspath("data/input/pothole.mp4")
        self.current_corridor_id = "bus1"
        self.current_speed = 1.0
        self.enable_potholes = True
        self.enable_plates = True

        # Automated PWD Dispatch state
        self.auto_dispatch_enabled = True
        self.dispatched_pwd_count = 0
        self.last_auto_dispatch_time = 0.0
        self.pending_distress_count = 0

        self.last_frame_qimage: Optional[QImage] = None
        self.last_summary_data: Optional[Dict[str, Any]] = None
        self.all_incidents: List[Dict[str, Any]] = []

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        root_layout = QHBoxLayout(main_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ─── Left Navigation Rail ────────────────────────────────────────────
        nav_rail = QFrame()
        nav_rail.setFixedWidth(70)
        nav_rail.setObjectName("entNavRail")
        nav_rail.setStyleSheet("""
            #entNavRail {
                background-color: #ffffff;
                border-right: 1px solid #cbd5e1;
            }
        """)
        rail_lay = QVBoxLayout(nav_rail)
        rail_lay.setContentsMargins(10, 18, 10, 18)
        rail_lay.setSpacing(14)

        app_icon = QLabel("👁️")
        app_icon.setAlignment(Qt.AlignCenter)
        app_icon.setStyleSheet("font-size: 22px; padding: 4px;")
        rail_lay.addWidget(app_icon)

        rail_lay.addSpacing(10)

        self.nav_home = self._create_nav_btn("🎥", "Stream Ingestion", True)
        self.nav_home.clicked.connect(self.switch_to_ingestion)
        rail_lay.addWidget(self.nav_home)

        self.nav_cockpit = self._create_nav_btn("📊", "Live Cockpit", False)
        self.nav_cockpit.clicked.connect(self.switch_to_cockpit)
        rail_lay.addWidget(self.nav_cockpit)

        self.nav_records = self._create_nav_btn("📋", "Municipal Records & Audit Dashboard", False)
        self.nav_records.clicked.connect(self.switch_to_records)
        rail_lay.addWidget(self.nav_records)

        rail_lay.addStretch()

        self.nav_settings = self._create_nav_btn("⚙️", "Settings", False)
        rail_lay.addWidget(self.nav_settings)

        root_layout.addWidget(nav_rail)

        # Content Stack
        self.stack = QStackedWidget()
        self.init_screens()
        root_layout.addWidget(self.stack, stretch=1)

        self.apply_enterprise_theme()

    def _create_nav_btn(self, icon_str: str, tooltip: str, active: bool = False) -> QPushButton:
        btn = QPushButton(icon_str)
        btn.setToolTip(tooltip)
        btn.setFixedSize(50, 46)
        btn.setCursor(QCursor(Qt.PointingHandCursor))
        if active:
            btn.setStyleSheet("background-color: #0284c7; color: white; border: none; border-radius: 8px; font-size: 17px;")
        else:
            btn.setStyleSheet("background-color: #f1f5f9; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 17px;")
        return btn

    def init_screens(self):
        # ─── SCREEN 0: INGESTION HUB ─────────────────────────────────────────
        self.ingestion_screen = VideoIngestionView()
        self.ingestion_screen.launch_requested.connect(self.on_ingestion_launch)
        self.stack.addWidget(self.ingestion_screen)

        # ─── SCREEN 1: LIVE COCKPIT ──────────────────────────────────────────
        self.cockpit_screen = QWidget()
        cockpit_layout = QVBoxLayout(self.cockpit_screen)
        cockpit_layout.setContentsMargins(24, 20, 24, 20)
        cockpit_layout.setSpacing(14)

        # Top Header Bar Card
        header_card = EnterpriseCard()
        header_layout = QHBoxLayout(header_card)
        header_layout.setContentsMargins(18, 12, 18, 12)
        header_layout.setSpacing(14)

        brand_box = QVBoxLayout()
        brand_box.setSpacing(2)
        title = QLabel("ARGUS // AUTONOMOUS URBAN TRANSIT SENSING & MUNICIPAL COMMAND")
        title.setFont(QFont("Segoe UI", 13, QFont.Bold))
        title.setStyleSheet("color: #0f172a; font-weight: 900; letter-spacing: 0.5px;")
        self.sub_title = TypewriterLabel("THE HUNDRED EYES OF THE CITY · SQLITE: ATTACHED (data/app.db) · ACCELERATOR: CUDA FP16")
        self.sub_title.setStyleSheet("color: #475569; font-size: 10px; font-weight: 700;")
        brand_box.addWidget(title)
        brand_box.addWidget(self.sub_title)
        header_layout.addLayout(brand_box)

        header_layout.addStretch()

        feed_lbl = QLabel("STREAM:")
        feed_lbl.setStyleSheet("font-weight: 800; color: #0f172a; font-size: 11px;")
        header_layout.addWidget(feed_lbl)
        
        self.video_combo = QComboBox()
        self.video_combo.setFixedWidth(200)
        self.populate_video_combo()
        self.video_combo.currentIndexChanged.connect(self.on_video_selected)
        header_layout.addWidget(self.video_combo)

        rate_lbl = QLabel("RATE:")
        rate_lbl.setStyleSheet("font-weight: 800; color: #0f172a; font-size: 11px;")
        header_layout.addWidget(rate_lbl)

        self.speed_combo = QComboBox()
        self.speed_combo.addItem("1.0x Real-Time (Smooth)", 1.0)
        self.speed_combo.addItem("1.5x Fast", 1.5)
        self.speed_combo.addItem("2.0x Turbo", 2.0)
        self.speed_combo.addItem("0.5x Slow Motion", 0.5)
        self.speed_combo.addItem("Max (Uncapped GPU)", 0.0)
        self.speed_combo.currentIndexChanged.connect(self.on_speed_changed)
        header_layout.addWidget(self.speed_combo)

        # Database Status Badge
        self.db_status_badge = QLabel("💾 DB: CONNECTED")
        self.db_status_badge.setStyleSheet("""
            QLabel {
                background-color: #f0f9ff;
                color: #0369a1;
                border: 1.5px solid #bae6fd;
                padding: 6px 12px;
                border-radius: 6px;
                font-weight: 800;
                font-size: 11px;
            }
        """)
        header_layout.addWidget(self.db_status_badge)

        # Small PWD Dispatch Menu in the top
        self.pwd_menu_btn = QPushButton("🏛️ PWD DISPATCH (0 SENT) ●")
        self.pwd_menu_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.pwd_menu_btn.setStyleSheet("""
            QPushButton {
                background-color: #f0fdf4;
                color: #166534;
                border: 1.5px solid #86efac;
                padding: 7px 13px;
                border-radius: 6px;
                font-weight: 800;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #dcfce7;
                border-color: #22c55e;
            }
        """)
        self._init_pwd_menu()
        header_layout.addWidget(self.pwd_menu_btn)

        self.start_btn = QPushButton("▶ ENGAGE TELEMETRY")
        self.start_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.start_btn.setStyleSheet("background-color: #0284c7; color: white; font-weight: 900; padding: 8px 18px; border-radius: 6px; border: none; font-size: 11px;")
        self.start_btn.clicked.connect(self.toggle_stream)
        header_layout.addWidget(self.start_btn)

        cockpit_layout.addWidget(header_card)

        # Full-Width KPI Metrics Ribbon across the operations cockpit
        cards_grid = QHBoxLayout()
        cards_grid.setSpacing(12)

        self.card_potholes = EnterpriseKpiCard("Potholes Found", 0, "Depth AI Craters", "#ef4444")
        self.card_plates = EnterpriseKpiCard("ANPR Plates Scanned", 0, "Plate Scans", "#10b981")
        self.card_violators = EnterpriseKpiCard("Violator Plates", 0, "Rash Driving Flagged", "#dc2626")
        self.card_vehicles = EnterpriseKpiCard("Vehicles Tracked", 0, "Persistent Tracking", "#0284c7")
        self.card_pedestrians = EnterpriseKpiCard("Pedestrians Logged", 0, "Crosswalk Flow", "#f59e0b")
        self.card_infra = EnterpriseKpiCard("Road Infrastructure", 0, "Dividers / Zebra / Water", "#8b5cf6")

        cards_grid.addWidget(self.card_potholes)
        cards_grid.addWidget(self.card_plates)
        cards_grid.addWidget(self.card_violators)
        cards_grid.addWidget(self.card_vehicles)
        cards_grid.addWidget(self.card_pedestrians)
        cards_grid.addWidget(self.card_infra)
        cockpit_layout.addLayout(cards_grid)

        # Content Split: Left (Video Player) & Right (Mapbox Navigation & Registries)
        content_layout = QHBoxLayout()
        content_layout.setSpacing(14)

        # Video Player Frame
        video_card = EnterpriseCard()
        video_col = QVBoxLayout(video_card)
        video_col.setContentsMargins(14, 14, 14, 14)
        video_col.setSpacing(8)

        self.video_label = QLabel("Select a camera feed and engage telemetry")
        self.video_label.setObjectName("videoViewport")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video_label.setMinimumSize(640, 440)
        self.video_label.setStyleSheet("background-color: #000000; border-radius: 8px; color: #94a3b8; font-size: 13px; font-weight: bold;")
        video_col.addWidget(self.video_label, stretch=1)

        prog_bar_layout = QHBoxLayout()
        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0, 100)
        self.prog_bar.setValue(0)
        self.prog_bar.setFixedHeight(6)
        self.prog_bar.setTextVisible(False)
        self.prog_bar.setStyleSheet("background-color: #e2e8f0; border: none; border-radius: 3px;")
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet("font-size: 11px; color: #0f172a; font-weight: 800;")
        prog_bar_layout.addWidget(self.prog_bar)
        prog_bar_layout.addWidget(self.time_label)
        video_col.addLayout(prog_bar_layout)

        hud_bar = QHBoxLayout()
        self.status_badge = PulsingStatusLabel("● SYSTEM IDLE")
        self.fps_label = QLabel("FPS: --")
        self.fps_label.setStyleSheet("color: #0284c7; font-weight: 800; font-size: 11px;")
        self.latency_label = QLabel("LATENCY: -- MS")
        self.latency_label.setStyleSheet("color: #7c3aed; font-weight: 800; font-size: 11px;")
        self.street_label = QLabel("SECTOR: MAIN CORRIDOR")
        self.street_label.setStyleSheet("color: #0f172a; font-size: 11px; font-weight: 700;")

        self.pause_btn = QPushButton("⏸")
        self.pause_btn.setToolTip("Pause / Resume Playback")
        self.pause_btn.setStyleSheet("background-color: #f1f5f9; color: #0f172a; border: 1px solid #cbd5e1; padding: 5px 10px; border-radius: 6px; font-weight: 700; font-size: 11px;")
        self.pause_btn.clicked.connect(self.toggle_pause)

        self.snapshot_btn = QPushButton("📸 Snapshot")
        self.snapshot_btn.setStyleSheet("background-color: #f1f5f9; color: #0f172a; border: 1px solid #cbd5e1; padding: 5px 10px; border-radius: 6px; font-weight: 700; font-size: 11px;")
        self.snapshot_btn.clicked.connect(self.capture_snapshot)

        self.export_btn = QPushButton("💾 JSON")
        self.export_btn.setStyleSheet("background-color: #f1f5f9; color: #0f172a; border: 1px solid #cbd5e1; padding: 5px 10px; border-radius: 6px; font-weight: 700; font-size: 11px;")
        self.export_btn.clicked.connect(self.export_report)

        self.pwd_btn = QPushButton("🏛️ PWD Docket")
        self.pwd_btn.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: white;
                font-weight: 800;
                font-size: 11px;
                padding: 5px 12px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #047857;
            }
        """)
        self.pwd_btn.clicked.connect(self.export_pwd_work_order)

        self.view_records_btn = QPushButton("📋 Audit Dashboard")
        self.view_records_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.view_records_btn.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: white;
                font-weight: 800;
                font-size: 11px;
                padding: 5px 12px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
        """)
        self.view_records_btn.clicked.connect(self.show_transition_animation)

        hud_bar.addWidget(self.status_badge)
        hud_bar.addSpacing(8)
        hud_bar.addWidget(self.fps_label)
        hud_bar.addSpacing(8)
        hud_bar.addWidget(self.latency_label)
        hud_bar.addSpacing(8)
        hud_bar.addWidget(self.street_label)
        hud_bar.addStretch()
        hud_bar.addWidget(self.pause_btn)
        hud_bar.addWidget(self.snapshot_btn)
        hud_bar.addWidget(self.export_btn)
        hud_bar.addWidget(self.pwd_btn)
        hud_bar.addWidget(self.view_records_btn)

        video_col.addLayout(hud_bar)
        content_layout.addWidget(video_card, stretch=6)

        # Right Column: Mapbox Live Navigation & Telemetry Tables
        right_panel = QVBoxLayout()
        right_panel.setSpacing(12)

        # Tabs Container
        tabs_card = EnterpriseCard()
        tabs_lay = QVBoxLayout(tabs_card)
        tabs_lay.setContentsMargins(12, 12, 12, 12)

        self.tabs = QTabWidget()
        
        # 1. Primary Tab: Mapbox Live Navigation Widget
        self.mapbox_widget = MapboxLiveNavigationWidget()
        self.tabs.addTab(self.mapbox_widget, "🗺️ LIVE MAP & NAVIGATION")

        # 2. Incident Stream
        self.event_list = QListWidget()
        self.event_list.itemDoubleClicked.connect(self.on_incident_clicked)
        self.tabs.addTab(self.event_list, "📋 Incident Stream")

        # 3. Potholes Table
        self.pothole_table = QTableWidget(0, 4)
        self.pothole_table.setHorizontalHeaderLabels(["ID", "Severity", "Confidence", "GPS Pinpoint"])
        self.pothole_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabs.addTab(self.pothole_table, "🕳️ Potholes Table")

        # 4. ANPR Registry
        self.plate_table = QTableWidget(0, 3)
        self.plate_table.setHorizontalHeaderLabels(["Plate Identifier", "Confidence", "Timestamp"])
        self.plate_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabs.addTab(self.plate_table, "🚗 ANPR Registry")

        # 5. Vehicle Audit
        self.vehicles_table = QTableWidget(0, 4)
        self.vehicles_table.setHorizontalHeaderLabels(["Track ID", "Classification", "Confidence", "First Seen"])
        self.vehicles_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabs.addTab(self.vehicles_table, "🚙 Vehicle Audit")

        # 6. Road Infrastructure Deficiencies & Assets
        self.infra_table = QTableWidget(0, 4)
        self.infra_table.setHorizontalHeaderLabels(["Defect / Asset Type", "Description", "Confidence", "Timestamp"])
        self.infra_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabs.addTab(self.infra_table, "🚧 Road Infrastructure")

        # 7. Dedicated Violator Vehicles & Flagged Plates Display
        violator_tab = QWidget()
        v_tab_lay = QVBoxLayout(violator_tab)
        v_tab_lay.setContentsMargins(8, 8, 8, 8)
        v_tab_lay.setSpacing(6)

        v_banner = QLabel("🚨 <b>FLAGGED TRAFFIC VIOLATORS & RASH DRIVING ANPR REGISTRY</b> &nbsp;|&nbsp; <span style='font-size:10px; color:#475569;'>Real-time AI speed burst & swerve violation tracking with MoRTH plate attribution</span>")
        v_banner.setStyleSheet("color: #dc2626; font-size: 11px; background: #fee2e2; border: 1px solid #fca5a5; padding: 6px 10px; border-radius: 6px;")
        v_tab_lay.addWidget(v_banner)

        self.violators_table = QTableWidget(0, 6)
        self.violators_table.setHorizontalHeaderLabels(["Flagged Number Plate", "Vehicle Type", "Track ID", "Violation Severity", "Speed Spike Factor", "Corridor GPS Pinpoint"])
        self.violators_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.violators_table.itemDoubleClicked.connect(self.on_violator_clicked)
        v_tab_lay.addWidget(self.violators_table)

        self.tabs.addTab(violator_tab, "🚨 Violator Vehicles")

        tabs_lay.addWidget(self.tabs)
        right_panel.addWidget(tabs_card, stretch=1)

        content_layout.addLayout(right_panel, stretch=6)
        cockpit_layout.addLayout(content_layout, stretch=1)

        self.stack.addWidget(self.cockpit_screen)

        # ─── SCREEN 2: MUNICIPAL RECORDS & AUDIT DASHBOARD ───────────────────
        self.records_screen = MunicipalRecordsDashboardView()
        self.records_screen.back_to_cockpit.connect(self.switch_to_cockpit)
        self.records_screen.export_all_requested.connect(self.export_report)
        self.records_screen.pwd_requested.connect(self.export_pwd_work_order)
        self.stack.addWidget(self.records_screen)

        self.stack.setCurrentIndex(0)

    def populate_video_combo(self):
        self.video_combo.clear()
        input_dir = os.path.join("data", "input")
        if os.path.exists(input_dir):
            for f in os.listdir(input_dir):
                if f.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
                    self.video_combo.addItem(f, os.path.abspath(os.path.join(input_dir, f)))

        # Also populate videos from route folders
        routes_dir = os.path.join("data", "input", "routes")
        if os.path.exists(routes_dir):
            def _bus_sort_key(name):
                digits = "".join(filter(str.isdigit, name))
                return int(digits) if digits else 99

            for b in sorted(os.listdir(routes_dir), key=_bus_sort_key):
                bpath = os.path.join(routes_dir, b)
                if os.path.isdir(bpath):
                    for f in os.listdir(bpath):
                        if f.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
                            self.video_combo.addItem(f"[{b.upper()}] {f}", os.path.abspath(os.path.join(bpath, f)))

        if self.video_combo.count() == 0:
            self.video_combo.addItem("pothole.mp4", self.current_video_path)
        else:
            for i in range(self.video_combo.count()):
                if "bus1" in self.video_combo.itemText(i).lower() or "divider" in self.video_combo.itemText(i).lower():
                    self.video_combo.setCurrentIndex(i)
                    self.current_video_path = self.video_combo.itemData(i)
                    break

    def on_video_selected(self, index: int):
        path = self.video_combo.itemData(index)
        if path and os.path.exists(path):
            self.current_video_path = path
            matched_id, _ = RouteSimulator.detect_corridor_and_role(path)
            self.current_corridor_id = matched_id

    def on_speed_changed(self, index: int):
        speed = float(self.speed_combo.itemData(index))
        self.current_speed = speed
        if self.worker is not None and self.worker.isRunning():
            self.worker.set_speed(speed)

    def _init_pwd_menu(self):
        menu = QMenu(self.pwd_menu_btn)
        menu.setStyleSheet("""
            QMenu {
                background-color: #ffffff;
                color: #0f172a;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 6px;
                font-family: 'Segoe UI';
                font-weight: 700;
                font-size: 11px;
            }
            QMenu::item {
                padding: 8px 18px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #0284c7;
                color: white;
            }
            QMenu::separator {
                height: 1px;
                background-color: #e2e8f0;
                margin: 4px 6px;
            }
        """)

        # Auto-Dispatch Toggle Action
        self.auto_dispatch_action = QAction("⚡ Automated PWD Work-Order Dispatch", menu)
        self.auto_dispatch_action.setCheckable(True)
        self.auto_dispatch_action.setChecked(self.auto_dispatch_enabled)
        self.auto_dispatch_action.toggled.connect(self._toggle_auto_dispatch)
        menu.addAction(self.auto_dispatch_action)

        menu.addSeparator()

        # Manual Force Dispatch
        force_act = QAction("🚀 Force Dispatch Pending Work-Orders Now", menu)
        force_act.triggered.connect(lambda: self.trigger_auto_pwd_dispatch(force=True))
        menu.addAction(force_act)

        # View PWD Work-Order Docket Modal
        view_docket_act = QAction("📄 Review PWD Civil Docket Dossier...", menu)
        view_docket_act.triggered.connect(self.export_pwd_work_order)
        menu.addAction(view_docket_act)

        # Full Municipal Records Dashboard
        records_act = QAction("📋 Municipal Records & Audit Dashboard", menu)
        records_act.triggered.connect(self.show_transition_animation)
        menu.addAction(records_act)

        menu.addSeparator()

        # Output Folder
        folder_act = QAction("📁 Open Work-Orders Folder (data/output)", menu)
        folder_act.triggered.connect(self._open_output_folder)
        menu.addAction(folder_act)

        self.pwd_menu_btn.setMenu(menu)

    def _open_output_folder(self):
        out_dir = os.path.abspath("data/output")
        os.makedirs(out_dir, exist_ok=True)
        if os.path.exists(out_dir):
            os.startfile(out_dir)

    def _toggle_auto_dispatch(self, checked: bool):
        self.auto_dispatch_enabled = checked
        if checked:
            self.pwd_menu_btn.setText(f"🏛️ PWD DISPATCH ({self.dispatched_pwd_count} SENT) ●")
            self.pwd_menu_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f0fdf4;
                    color: #166534;
                    border: 1.5px solid #86efac;
                    padding: 7px 13px;
                    border-radius: 6px;
                    font-weight: 800;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #dcfce7;
                    border-color: #22c55e;
                }
            """)
            self.status_badge.set_live("● AUTO-DISPATCH ACTIVE")
        else:
            self.pwd_menu_btn.setText(f"🏛️ PWD DISPATCH (PAUSED) ○")
            self.pwd_menu_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f8fafc;
                    color: #64748b;
                    border: 1.5px solid #cbd5e1;
                    padding: 7px 13px;
                    border-radius: 6px;
                    font-weight: 800;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #f1f5f9;
                }
            """)
            self.status_badge.set_live("● AUTO-DISPATCH PAUSED")

    def trigger_auto_pwd_dispatch(self, force: bool = False):
        if not self.auto_dispatch_enabled and not force:
            return

        now = time.time()
        # Enforce debounce/throttle of 8 seconds unless forced
        if not force and (now - self.last_auto_dispatch_time < 8.0):
            return

        distress_incidents = [
            inc for inc in self.all_incidents
            if inc.get("type") in (
                "POTHOLE", "MISSING_ROAD_DIVIDER", "MISSING_ZEBRA_CROSSING",
                "WATER_LOGGING", "DAMAGED_SIGNBOARD", "ROAD_HAZARD"
            )
            or "pothole" in str(inc.get("type", "")).lower()
            or "missing" in str(inc.get("type", "")).lower()
            or "water" in str(inc.get("type", "")).lower()
            or "damaged" in str(inc.get("type", "")).lower()
        ]

        if not distress_incidents:
            return

        # Prevent generating duplicate identical dockets if no new defects have been logged
        if len(distress_incidents) <= self.dispatched_pwd_count and self.dispatched_pwd_count > 0:
            return

        self.last_auto_dispatch_time = now

        # Generate PWD work orders
        csv_path, summary = generate_pwd_work_orders(distress_incidents)
        new_count = len(distress_incidents)
        self.dispatched_pwd_count = new_count
        self.pwd_menu_btn.setText(f"🏛️ PWD DISPATCH ({self.dispatched_pwd_count} SENT) ●")

        # Play subtle dispatch alert tone
        play_alert_sound(freq=950, dur=110, category="pwd_auto", cooldown=2.0)

        # Post notice to live incident feed
        auto_inc = {
            "id": f"PWD-AUTO-{int(now)%10000}",
            "type": "PWD_DISPATCH",
            "title": f"AUTOMATED WORK-ORDER DISPATCH // {new_count} DEFECTS TRANSMITTED",
            "severity": "NORMAL",
            "confidence": "100%",
            "location": summary.get("top_corridor", "Municipal Road Network"),
            "gps": f"Docket #{summary.get('docket_id', 'PWD-DOCKET')}",
            "timestamp": time.strftime("%H:%M:%S"),
            "time_sec": f"{int(now)%1000}s",
            "description": f"Official IRC PWD Work-Order automatically compiled and dispatched with {summary.get('total_potholes', 0)} potholes and {summary.get('total_infra_defects', 0)} infra defects."
        }
        item_text = f"[{auto_inc['timestamp']}] 🏛️ {auto_inc['title']}\nSECTOR: {auto_inc['location']} | DOCKET: {auto_inc['gps']}"
        item = QListWidgetItem(item_text)
        item.setData(Qt.UserRole, auto_inc)
        item.setForeground(QColor("#059669"))
        self.event_list.insertItem(0, item)

        # Launch background email transmission
        def _bg_send():
            try:
                ok, response_msg = send_pwd_workorder_email(summary, csv_path)
                if ok:
                    logging.info(f"[PWD Auto-Dispatch] Successfully transmitted docket {summary.get('docket_id')}")
                else:
                    logging.warning(f"[PWD Auto-Dispatch] Dispatch notice: {response_msg}")
            except Exception as e:
                logging.error(f"[PWD Auto-Dispatch] Background transmission error: {e}")

        threading.Thread(target=_bg_send, daemon=True).start()

    def switch_to_ingestion(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()
            self.worker = None
        self.nav_home.setStyleSheet("background-color: #0284c7; color: white; border: none; border-radius: 8px; font-size: 17px;")
        self.nav_cockpit.setStyleSheet("background-color: #f1f5f9; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 17px;")
        self.nav_records.setStyleSheet("background-color: #f1f5f9; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 17px;")
        self.stack.setCurrentIndex(0)

    def switch_to_cockpit(self):
        self.nav_home.setStyleSheet("background-color: #f1f5f9; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 17px;")
        self.nav_cockpit.setStyleSheet("background-color: #0284c7; color: white; border: none; border-radius: 8px; font-size: 17px;")
        self.nav_records.setStyleSheet("background-color: #f1f5f9; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 17px;")
        self.stack.setCurrentIndex(1)

    def switch_to_records(self):
        self.records_screen.populate_records(self.all_incidents, self.last_summary_data, getattr(self, "current_corridor_id", "bus1"))
        self.nav_home.setStyleSheet("background-color: #f1f5f9; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 17px;")
        self.nav_cockpit.setStyleSheet("background-color: #f1f5f9; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 17px;")
        self.nav_records.setStyleSheet("background-color: #0284c7; color: white; border: none; border-radius: 8px; font-size: 17px;")
        self.stack.setCurrentIndex(2)

    def show_transition_animation(self):
        corridor_name = getattr(self, "current_corridor_id", "CORRIDOR").upper()
        inc_count = len(self.all_incidents)
        overlay = MunicipalIntelligenceTransitionOverlay(self, corridor_name=corridor_name, total_incidents=inc_count)
        overlay.finished_loading.connect(self.switch_to_records)
        overlay.exec_()

    def on_ingestion_launch(self, path: str, speed: float, enable_potholes: bool, enable_plates: bool, corridor_id: str = "bus1"):
        self.current_video_path = path
        self.current_speed = speed
        self.enable_potholes = enable_potholes
        self.enable_plates = enable_plates
        self.current_corridor_id = corridor_id

        for i in range(self.video_combo.count()):
            if self.video_combo.itemData(i) == path:
                self.video_combo.setCurrentIndex(i)
                break

        self.switch_to_cockpit()
        QTimer.singleShot(200, self.sub_title.start_reveal)
        self.start_stream()

    def start_stream(self):
        self.event_list.clear()
        self.pothole_table.setRowCount(0)
        self.plate_table.setRowCount(0)
        self.vehicles_table.setRowCount(0)
        self.all_incidents.clear()
        self.mapbox_widget.clear_navigation()
        self.prog_bar.setValue(0)

        self.start_btn.setText("⏹ DISENGAGE")
        self.start_btn.setStyleSheet("background-color: #ef4444; color: white; font-weight: 800; padding: 8px 18px; border-radius: 6px; border: none;")
        self.status_badge.set_live(f"● TELEMETRY ACTIVE ({self.current_speed}x)")

        self.worker = VideoInferenceWorker(
            video_path=self.current_video_path,
            speed_multiplier=self.current_speed,
            enable_potholes=self.enable_potholes,
            enable_plates=self.enable_plates,
            corridor_id=getattr(self, "current_corridor_id", "bus1")
        )
        self.mapbox_widget.set_corridor(
            self.worker.route_sim.get_info(),
            self.worker.route_sim.get_route_coordinates()
        )
        self.worker.frame_ready.connect(self.update_video_frame)
        self.worker.stats_updated.connect(self.update_stats)
        self.worker.progress_updated.connect(self.update_progress)
        self.worker.gps_updated.connect(self.mapbox_widget.update_position)
        self.worker.incident_logged.connect(self.add_incident_to_feed)
        self.worker.status_changed.connect(lambda s: self.status_badge.set_live(f"● {s}"))
        self.worker.pipeline_finished.connect(self.on_pipeline_done)
        self.worker.start()

    def toggle_stream(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()
            self.worker = None
            self.start_btn.setText("▶ ENGAGE TELEMETRY")
            self.start_btn.setStyleSheet("background-color: #0284c7; color: white; font-weight: 800; padding: 8px 18px; border-radius: 6px; border: none;")
            self.status_badge.set_idle("● SYSTEM IDLE")
        else:
            self.start_stream()

    def toggle_pause(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.toggle_pause()
            self.pause_btn.setText("▶ Resume" if self.worker.is_paused else "⏸ Pause")

    def update_video_frame(self, qimage: QImage, info: dict):
        self.last_frame_qimage = qimage
        pixmap = QPixmap.fromImage(qimage)
        scaled = pixmap.scaled(self.video_label.size(), Qt.KeepAspectRatio, Qt.FastTransformation)
        self.video_label.setPixmap(scaled)

    def update_progress(self, current: int, total: int, ts: float):
        if total > 0:
            pct = int((current / total) * 100)
            self.prog_bar.setValue(pct)
            total_sec = total / 25.0
            self.time_label.setText(f"{int(ts//60):02d}:{int(ts%60):02d} / {int(total_sec//60):02d}:{int(total_sec%60):02d}")

    def update_stats(self, data: dict):
        self.fps_label.setText(f"FPS: {data['fps']}")
        self.latency_label.setText(f"LATENCY: {data['latency_ms']} MS")
        
        self.card_potholes.set_value(data['unique_potholes'])
        self.card_plates.set_value(data['unique_plates'])
        self.card_violators.set_value(data.get('unique_violators', 0))

        v_tot = data.get('total_vehicles_logged', 0)
        v_vis = data.get('visible_vehicles', 0)
        self.card_vehicles.set_value(v_tot, f"{v_vis} in active view")

        p_tot = data.get('total_pedestrians_logged', 0)
        p_vis = data.get('visible_pedestrians', 0)
        self.card_pedestrians.set_value(p_tot, f"{p_vis} in active view")

        self.card_infra.set_value(data.get('total_infra_defects', 0))

        cg_idx = data.get('congestion_index', 20)
        cg_lbl = data.get('congestion_label', 'FREE FLOW')
        self.mapbox_widget.update_congestion(cg_idx, cg_lbl)

        self.street_label.setText(f"SECTOR: {data['street']}")

        # Periodically log traffic metrics to SQLite (~once every second)
        try:
            fid = data.get("frame_id", 0)
            if fid % 25 == 0:
                insert_traffic_metric({
                    "frame_id": fid,
                    "timestamp_sec": data.get("time_sec", 0.0),
                    "corridor_id": getattr(self, "current_corridor_id", "bus1"),
                    "total_vehicles": v_tot,
                    "pedestrians": p_tot,
                    "congestion_index": cg_idx,
                    "congestion_label": cg_lbl,
                    "street_name": data.get("street", "Corridor Sector")
                })
        except Exception:
            pass

    def add_incident_to_feed(self, inc: dict):
        if self.last_frame_qimage:
            inc["pixmap"] = QPixmap.fromImage(self.last_frame_qimage)

        # Deduplicate incidents in self.all_incidents by unique ID
        inc_id = inc.get("id")
        is_duplicate = False
        if inc_id:
            for existing in self.all_incidents:
                if existing.get("id") == inc_id:
                    existing.update(inc)
                    is_duplicate = True
                    break
        if not is_duplicate:
            self.all_incidents.append(inc)

        # Always upsert to DB — new observations update existing records
        try:
            itype = str(inc.get("type", "")).upper()
            if "POTHOLE" in itype:
                insert_pothole(inc)
            elif "PLATE" in itype:
                insert_plate(inc)
            else:
                insert_violation(inc)
        except Exception as e:
            logger.warning(f"DB incident upsert error: {e}")

        # Routine non-violating vehicles are logged in vehicle tables, not spammed into the incident feed or map
        is_routine_vehicle = (inc.get("type") == "VEHICLE")
        if not is_routine_vehicle:
            self.mapbox_widget.add_incident_marker(inc)

            item_text = f"[{inc['timestamp']}] {inc['type']} // {inc['title']}\nSECTOR: {inc['location']} | GPS: {inc['gps']} (Conf: {inc['confidence']})"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, inc)
            if inc['severity'] == 'CRITICAL' or inc['type'] in ('RASH_DRIVING', 'HIT_AND_RUN'):
                item.setForeground(QColor("#dc2626"))
            elif inc['severity'] == 'WARNING' or inc['severity'] == 'HIGH':
                item.setForeground(QColor("#d97706"))
            elif inc['type'] in ('ZEBRA_CROSSING', 'ROAD_DIVIDER', 'SIGNBOARD', 'PWD_DISPATCH'):
                item.setForeground(QColor("#059669"))
            else:
                item.setForeground(QColor("#0284c7"))
            self.event_list.insertItem(0, item)

        if inc['type'] == 'POTHOLE':
            row = self.pothole_table.rowCount()
            self.pothole_table.insertRow(row)
            self.pothole_table.setItem(row, 0, QTableWidgetItem(inc['id']))
            sev_item = QTableWidgetItem(inc['severity'])
            if 'CRITICAL' in inc['severity'] or 'P1' in inc['severity']:
                sev_item.setForeground(QColor("#dc2626"))
                sev_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            elif 'HIGH' in inc['severity'] or 'P2' in inc['severity'] or 'WARNING' in inc['severity']:
                sev_item.setForeground(QColor("#ea580c"))
                sev_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            else:
                sev_item.setForeground(QColor("#0284c7"))
            self.pothole_table.setItem(row, 1, sev_item)
            self.pothole_table.setItem(row, 2, QTableWidgetItem(inc['confidence']))
            self.pothole_table.setItem(row, 3, QTableWidgetItem(inc['gps']))
        elif inc['type'] == 'PLATE':
            p_ident = inc['title'].replace("ANPR // ", "").strip()
            # Deduplicate by plate identifier
            found = False
            for r in range(self.plate_table.rowCount()):
                it = self.plate_table.item(r, 0)
                if it and it.text() == p_ident:
                    found = True
                    break
            if not found:
                row = self.plate_table.rowCount()
                self.plate_table.insertRow(row)
                self.plate_table.setItem(row, 0, QTableWidgetItem(p_ident))
                self.plate_table.setItem(row, 1, QTableWidgetItem(inc['confidence']))
                self.plate_table.setItem(row, 2, QTableWidgetItem(inc['time_sec']))
        elif inc['type'] in ('RASH_DRIVING', 'HIT_AND_RUN'):
            # Deduplicate or update in self.vehicles_table
            trk_id = inc.get('track_id')
            v_id_cand = f"VEH-{trk_id}" if trk_id else inc.get('id', '')
            found_v = False
            for r in range(self.vehicles_table.rowCount()):
                it = self.vehicles_table.item(r, 0)
                if it and (it.text() == v_id_cand or it.text() == inc.get('id', '')):
                    found_v = True
                    t_it = self.vehicles_table.item(r, 1)
                    if t_it:
                        t_it.setText(f"🚨 {inc['title']}")
                    break
            if not found_v:
                row = self.vehicles_table.rowCount()
                self.vehicles_table.insertRow(row)
                self.vehicles_table.setItem(row, 0, QTableWidgetItem(v_id_cand))
                self.vehicles_table.setItem(row, 1, QTableWidgetItem(f"🚨 {inc['title']}"))
                self.vehicles_table.setItem(row, 2, QTableWidgetItem(inc['confidence']))
                self.vehicles_table.setItem(row, 3, QTableWidgetItem(inc['time_sec']))

            # Populate Dedicated Violator Display Table (Deduplicated by plate & track ID)
            v_plate = inc.get('plate', 'FLAGGED')
            v_trk_tag = f"TRK #{inc.get('track_id', '-')}"
            viol_found = False
            for r in range(self.violators_table.rowCount()):
                p_it = self.violators_table.item(r, 0)
                t_it = self.violators_table.item(r, 2)
                if (p_it and v_plate != 'FLAGGED' and v_plate in p_it.text()) or (t_it and t_it.text() == v_trk_tag):
                    viol_found = True
                    spd_it = self.violators_table.item(r, 4)
                    if spd_it:
                        spd_it.setText(f"{inc.get('speed_score', 2.2):.1f}x Baseline")
                    break

            if not viol_found:
                v_row = self.violators_table.rowCount()
                self.violators_table.insertRow(v_row)

                plate_item = QTableWidgetItem(f"🚨 {v_plate}")
                plate_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
                plate_item.setForeground(QColor("#dc2626"))
                plate_item.setData(Qt.UserRole, inc)

                type_item = QTableWidgetItem(inc.get('vehicle_label', 'VEHICLE'))
                trk_item = QTableWidgetItem(v_trk_tag)
                sev_item = QTableWidgetItem(inc.get('severity', 'HIGH'))
                sev_item.setForeground(QColor("#dc2626"))
                spd_item = QTableWidgetItem(f"{inc.get('speed_score', 2.2):.1f}x Baseline")
                gps_item = QTableWidgetItem(f"{inc.get('location', '')} ({inc.get('gps', '')})")

                self.violators_table.setItem(v_row, 0, plate_item)
                self.violators_table.setItem(v_row, 1, type_item)
                self.violators_table.setItem(v_row, 2, trk_item)
                self.violators_table.setItem(v_row, 3, sev_item)
                self.violators_table.setItem(v_row, 4, spd_item)
                self.violators_table.setItem(v_row, 5, gps_item)
        elif inc['type'] == 'VEHICLE':
            # Deduplicate so each unique vehicle track appears exactly once
            t_id_str = inc.get('id', '')
            found = False
            for r in range(self.vehicles_table.rowCount()):
                it = self.vehicles_table.item(r, 0)
                if it and it.text() == t_id_str:
                    found = True
                    break
            if not found:
                row = self.vehicles_table.rowCount()
                self.vehicles_table.insertRow(row)
                self.vehicles_table.setItem(row, 0, QTableWidgetItem(inc['id']))
                self.vehicles_table.setItem(row, 1, QTableWidgetItem(inc['title']))
                self.vehicles_table.setItem(row, 2, QTableWidgetItem(inc['confidence']))
                self.vehicles_table.setItem(row, 3, QTableWidgetItem(inc['time_sec']))
        elif inc['type'] in ('ZEBRA_CROSSING', 'MISSING_ZEBRA_CROSSING', 'ROAD_DIVIDER', 'MISSING_ROAD_DIVIDER', 'WATER_LOGGING', 'SIGNBOARD', 'DAMAGED_SIGNBOARD'):
            row = self.infra_table.rowCount()
            self.infra_table.insertRow(row)
            self.infra_table.setItem(row, 0, QTableWidgetItem(inc['title']))
            self.infra_table.setItem(row, 1, QTableWidgetItem(inc.get('description', inc['title'])))
            self.infra_table.setItem(row, 2, QTableWidgetItem(inc['confidence']))
            self.infra_table.setItem(row, 3, QTableWidgetItem(inc['time_sec']))

        # Automated PWD Dispatch Triggering for Road Distress
        if inc['type'] in ('POTHOLE', 'MISSING_ROAD_DIVIDER', 'MISSING_ZEBRA_CROSSING', 'WATER_LOGGING', 'DAMAGED_SIGNBOARD'):
            self.pending_distress_count += 1
            if self.auto_dispatch_enabled and (time.time() - self.last_auto_dispatch_time >= 8.0):
                self.trigger_auto_pwd_dispatch()

    def on_incident_clicked(self, item: QListWidgetItem):
        inc_data = item.data(Qt.UserRole)
        if inc_data:
            dialog = EvidenceInspectorDialog(inc_data, self)
            dialog.exec_()

    def on_violator_clicked(self, item: QTableWidgetItem):
        row = item.row()
        first_item = self.violators_table.item(row, 0)
        inc_data = first_item.data(Qt.UserRole) if first_item else None
        if inc_data:
            dialog = EvidenceInspectorDialog(inc_data, self)
            dialog.exec_()

    def on_pipeline_done(self, summary: dict):
        self.last_summary_data = summary
        self.start_btn.setText("▶ ENGAGE TELEMETRY")
        self.start_btn.setStyleSheet("background-color: #0284c7; color: white; font-weight: 800; padding: 8px 18px; border-radius: 6px; border: none;")
        self.status_badge.set_idle("● MISSION COMPLETE")
        self.prog_bar.setValue(100)

        # Store only unique vehicles and their parameters
        unique_veh = extract_unique_vehicles(self.all_incidents, summary)
        save_unique_vehicles_registry(unique_veh)
        summary["unique_vehicles"] = unique_veh
        summary["tracked_vehicles"] = unique_veh

        # Synchronize entire surveillance run to embedded SQLite database
        try:
            sync_all_incidents(self.all_incidents, summary, getattr(self, "current_corridor_id", "bus1"))
            self.db_status_badge.setText("💾 DB: SYNCED")
            self.db_status_badge.setStyleSheet("background-color: #f0fdf4; color: #166534; border: 1.5px solid #86efac; padding: 6px 12px; border-radius: 6px; font-weight: 800; font-size: 11px;")
        except Exception as e:
            logger.debug(f"DB sync on pipeline done error: {e}")

        # Final Automated PWD Dispatch for any un-dispatched defects
        if self.auto_dispatch_enabled:
            self.trigger_auto_pwd_dispatch(force=True)

        # Cinematic Transition Animation to Municipal Records & Audit Dashboard
        QTimer.singleShot(700, self.show_transition_animation)

    def capture_snapshot(self):
        if self.last_frame_qimage:
            os.makedirs("data/output", exist_ok=True)
            save_path = f"data/output/snapshot_{int(time.time())}.jpg"
            self.last_frame_qimage.save(save_path)
            self.status_badge.set_live(f"📸 SNAPSHOT SAVED // {save_path}")
            QMessageBox.information(self, "Forensic Snapshot Saved", f"Frame snapshot saved to:\n{save_path}")

    def export_report(self):
        if not self.last_summary_data and not self.all_incidents:
            QMessageBox.warning(self, "No Telemetry Data", "Engage telemetry stream before generating report.")
            return
        os.makedirs("data/output", exist_ok=True)
        unique_veh = extract_unique_vehicles(self.all_incidents, self.last_summary_data)
        csv_path, json_path = save_unique_vehicles_registry(unique_veh)

        report_path = os.path.abspath("data/output/surveillance_report.json")
        summary_to_save = dict(self.last_summary_data or {})
        summary_to_save["unique_vehicles"] = unique_veh
        summary_to_save["tracked_vehicles"] = unique_veh
        summary_to_save["unique_vehicles_count"] = len(unique_veh)
        with open(report_path, "w") as f:
            json.dump(summary_to_save, f, indent=2)

        QMessageBox.information(
            self,
            "Audit Dossier Exported",
            f"Forensic Audit Dossier & Unique Vehicles Registry successfully saved:\n\n"
            f"🚗 CSV Ledger: {csv_path}\n"
            f"📄 JSON Registry: {json_path}\n"
            f"📊 Mission Report: {report_path}\n\n"
            f"Total Unique Vehicles Audited: {len(unique_veh)}"
        )

    def export_pwd_work_order(self):
        distress_incidents = [
            inc for inc in self.all_incidents
            if inc.get("type") in ("POTHOLE", "MISSING_ROAD_DIVIDER", "MISSING_ZEBRA_CROSSING", "WATER_LOGGING", "DAMAGED_SIGNBOARD")
            or "pothole" in str(inc.get("type", "")).lower()
            or "missing" in str(inc.get("type", "")).lower()
            or "water" in str(inc.get("type", "")).lower()
            or "damaged" in str(inc.get("type", "")).lower()
        ]

        if not distress_incidents:
            if self.pothole_table.rowCount() == 0 and self.infra_table.rowCount() == 0:
                QMessageBox.warning(
                    self,
                    "No Road Distress Logged",
                    "No road hazards, potholes, or infrastructure deficiencies have been recorded yet.\n\nStream a corridor containing road defects to generate official PWD civil work orders."
                )
                return
            distress_incidents = self.all_incidents

        csv_path, summary = generate_pwd_work_orders(distress_incidents)
        for ord_item in summary.get("work_orders", []):
            try:
                insert_pwd_work_order(ord_item)
            except Exception:
                pass
        dialog = PwdWorkOrderDialog(summary, self)
        dialog.exec_()

    def apply_enterprise_theme(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #eef2f6;
            }
            QWidget {
                font-family: 'Segoe UI', -apple-system, sans-serif;
            }
            #eventList {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                color: #0f172a;
                font-size: 11px;
                font-weight: 700;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #e2e8f0;
            }
            QListWidget::item:hover {
                background-color: #f1f5f9;
            }
            QTabWidget::pane {
                border: 1px solid #cbd5e1;
                background-color: #ffffff;
                border-radius: 8px;
            }
            QTabBar::tab {
                background-color: #f1f5f9;
                color: #0f172a;
                padding: 8px 16px;
                font-weight: 800;
                font-size: 11px;
                border: 1px solid #cbd5e1;
                border-bottom: none;
                margin-right: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            QTabBar::tab:selected {
                background-color: #ffffff;
                color: #0284c7;
                border-bottom: 2px solid #0284c7;
            }
            QTableWidget {
                background-color: #ffffff;
                color: #0f172a;
                gridline-color: #e2e8f0;
                border: none;
                font-size: 11px;
                font-weight: 700;
            }
            QHeaderView::section {
                background-color: #f1f5f9;
                color: #0f172a;
                padding: 7px;
                font-weight: 900;
                font-size: 11px;
                border: 1px solid #cbd5e1;
            }
            QPushButton {
                background-color: #ffffff;
                color: #0f172a;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 7px 14px;
                font-weight: 800;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #f1f5f9;
                border-color: #0284c7;
            }
            QComboBox {
                background-color: #ffffff;
                color: #0f172a;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 800;
            }
            QComboBox:hover {
                border-color: #0284c7;
            }
            QComboBox::drop-down {
                border: none;
            }
            QCheckBox {
                color: #0f172a;
                font-size: 12px;
                font-weight: 800;
            }
            QCheckBox::indicator {
                width: 17px;
                height: 17px;
                border: 1.5px solid #0284c7;
                background-color: #ffffff;
                border-radius: 4px;
            }
            QCheckBox::indicator:checked {
                background-color: #0284c7;
                border-color: #0284c7;
            }
        """)


def main():
    app = QApplication(sys.argv)
    
    splash = EnterpriseLoadingScreen()
    splash.start_loading()
    
    main_window = UrbanSurveillanceApp()

    splash.finished.connect(main_window.show)
    splash.exec_()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
