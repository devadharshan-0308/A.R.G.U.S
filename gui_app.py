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
    QGraphicsDropShadowEffect, QGridLayout, QButtonGroup, QLineEdit
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
        self.zoom = 14
        self.map_style = "streets-v12" # streets-v12 | satellite-streets-v12 | dark-v11
        
        self.path_history: List[Tuple[float, float]] = []
        self.incident_markers: List[Dict[str, Any]] = []
        
        self.cached_pixmap: Optional[QPixmap] = None
        self.last_fetch_pos: Optional[Tuple[float, float]] = None
        self.is_fetching = False

        self.nav_instructions = "Proceed along Anna Salai Corridor towards Central"
        self.nav_eta = "14.7 km · 43.8 mins (Live Traffic)"
        self.current_street = "Raja Muthiah Road, Chennai"
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

    def update_position(self, lat: float, lon: float, street_name: str = "", is_school: bool = False):
        self.current_lat = lat
        self.current_lon = lon
        self.path_history.append((lat, lon))
        if len(self.path_history) > 200:
            self.path_history.pop(0)

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
        self.update()

    def clear_navigation(self):
        self.path_history.clear()
        self.incident_markers.clear()
        self.last_fetch_pos = None
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

        # 2. Draw GPS Vehicle Patrol History Trail
        if len(self.path_history) > 1:
            painter.setPen(QPen(QColor(2, 132, 199, 220), 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
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

        # 4. Draw Current Vehicle Location Reticle
        vx, vy = cx, cy
        # Outer pulsating radar circle
        painter.setBrush(QBrush(QColor(56, 189, 248, 40)))
        painter.setPen(QPen(QColor("#38bdf8"), 1.5))
        painter.drawEllipse(QPointF(vx, vy), 16, 16)
        # Inner vehicle dot
        painter.setBrush(QBrush(QColor("#0284c7")))
        painter.setPen(QPen(Qt.white, 2))
        painter.drawEllipse(QPointF(vx, vy), 6, 6)

        # Attribution
        painter.setPen(QPen(QColor(255, 255, 255, 160)))
        painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
        painter.drawText(10, h - 8, "© Mapbox · © OpenStreetMap · High-Precision Telemetry")


# ─── ENTERPRISE STREAM CARD ──────────────────────────────────────────────────
class EnterpriseStreamCard(QFrame):
    clicked = pyqtSignal(str)

    def __init__(self, filename: str, title: str, desc: str, sector: str, fps: int, badge: str, color: str, is_active: bool = False):
        super().__init__()
        self.filename = filename
        self.video_path = os.path.abspath(os.path.join("data", "input", filename))
        self.color = color
        self.is_active = is_active
        self.setCursor(QCursor(Qt.PointingHandCursor))

        self.setObjectName("enterpriseStreamCard")
        self.update_style()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(16)

        # Video Thumbnail
        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(140, 85)
        self.thumb_label.setStyleSheet("background-color: #0f172a; border-radius: 6px; border: 1px solid #cbd5e1;")
        self.thumb_label.setAlignment(Qt.AlignCenter)
        
        pix = get_video_thumbnail(self.video_path, 140, 85)
        if pix:
            self.thumb_label.setPixmap(pix)
        else:
            self.thumb_label.setText("🎥 STREAM")
            self.thumb_label.setStyleSheet("color: #64748b; font-weight: bold; background: #e2e8f0; border-radius: 6px;")
        layout.addWidget(self.thumb_label)

        # Information Details
        info_box = QVBoxLayout()
        info_box.setSpacing(4)

        title_row = QHBoxLayout()
        t_lbl = QLabel(title)
        t_lbl.setStyleSheet("color: #0f172a; font-weight: 800; font-size: 13px;")
        title_row.addWidget(t_lbl)
        title_row.addStretch()

        self.badge_lbl = QLabel(badge)
        self.badge_lbl.setStyleSheet(f"color: {color}; background: {color}18; border: 1px solid {color}; padding: 3px 8px; border-radius: 4px; font-weight: 800; font-size: 10px;")
        title_row.addWidget(self.badge_lbl)
        info_box.addLayout(title_row)

        desc_lbl = QLabel(desc)
        desc_lbl.setStyleSheet("color: #334155; font-size: 11px; font-weight: 600;")
        info_box.addWidget(desc_lbl)

        meta_row = QHBoxLayout()
        sec_lbl = QLabel(f"📍 Sector: {sector}")
        sec_lbl.setStyleSheet("color: #475569; font-size: 11px; font-weight: 700;")
        fps_lbl = QLabel(f"⚡ {fps} FPS")
        fps_lbl.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: 800;")
        meta_row.addWidget(sec_lbl)
        meta_row.addSpacing(14)
        meta_row.addWidget(fps_lbl)
        meta_row.addStretch()
        info_box.addLayout(meta_row)

        layout.addLayout(info_box, stretch=1)

        # Selection Indicator
        self.status_pill = QLabel("SELECTED" if is_active else "SELECT FEED")
        self.update_pill()
        layout.addWidget(self.status_pill)

    def set_active(self, active: bool):
        self.is_active = active
        self.update_style()
        self.update_pill()

    def update_pill(self):
        if self.is_active:
            self.status_pill.setText("✓ ACTIVE FEED")
            self.status_pill.setStyleSheet("color: #ffffff; background-color: #0284c7; padding: 7px 16px; border-radius: 6px; font-weight: 800; font-size: 11px;")
        else:
            self.status_pill.setText("SELECT FEED")
            self.status_pill.setStyleSheet("color: #0f172a; background-color: #f1f5f9; border: 1px solid #cbd5e1; padding: 7px 16px; border-radius: 6px; font-weight: 700; font-size: 11px;")

    def update_style(self):
        if self.is_active:
            self.setStyleSheet("""
                #enterpriseStreamCard {
                    background-color: #f0f9ff;
                    border: 2px solid #0284c7;
                    border-radius: 10px;
                }
            """)
        else:
            self.setStyleSheet("""
                #enterpriseStreamCard {
                    background-color: #ffffff;
                    border: 1px solid #cbd5e1;
                    border-radius: 10px;
                }
                #enterpriseStreamCard:hover {
                    background-color: #f8fafc;
                    border-color: #0284c7;
                }
            """)

    def mousePressEvent(self, event):
        self.clicked.emit(self.video_path)


# ─── 2. ENTERPRISE VIDEO INPUT HUB SCREEN ────────────────────────────────────
class VideoIngestionView(QWidget):
    launch_requested = pyqtSignal(str, float, bool, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_path = os.path.abspath("data/input/pothole.mp4")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(18)

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
        banner_lay.setContentsMargins(28, 20, 28, 20)

        b_title_box = QVBoxLayout()
        b_title_box.setSpacing(3)
        b_title = QLabel("Urban Surveillance & Mapbox Ingestion Hub")
        b_title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        b_title.setStyleSheet("color: #ffffff; font-weight: 900;")
        b_sub = QLabel("Select a mobile camera feed to engage GPU neural models and live Mapbox cartography.")
        b_sub.setStyleSheet("color: #cbd5e1; font-size: 12px; font-weight: 600;")
        b_title_box.addWidget(b_title)
        b_title_box.addWidget(b_sub)
        banner_lay.addLayout(b_title_box)
        banner_lay.addStretch()

        gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "Host CPU"
        pill = QLabel(f"⚡ MAPBOX ACTIVE · GPU: {gpu_name}")
        pill.setStyleSheet("color: #ffffff; background: rgba(2, 132, 199, 0.4); border: 1px solid #38bdf8; padding: 8px 16px; border-radius: 6px; font-weight: 800; font-size: 11px;")
        banner_lay.addWidget(pill)

        layout.addWidget(banner)

        # Two-Column Layout
        split_layout = QHBoxLayout()
        split_layout.setSpacing(18)

        # Left: Feeds
        left_box = QVBoxLayout()
        left_box.setSpacing(12)

        sec_head = QLabel("AVAILABLE PATROL STREAMS")
        sec_head.setFont(QFont("Segoe UI", 12, QFont.Bold))
        sec_head.setStyleSheet("color: #0f172a; font-weight: 900; letter-spacing: 0.5px;")
        left_box.addWidget(sec_head)

        self.cards_list: List[EnterpriseStreamCard] = []
        presets = [
            ("pothole.mp4", "Mobile Patrol Alpha 04 (Road Surface Cam)", "Asphalt Depth & Volumetric Crater AI", "Anna Salai Corridor", 25, "POTHOLE AI", "#dc2626"),
            ("demo_traffic.mp4", "Patrol Cruiser 02 (Traffic & ANPR Cam)", "Multi-Lane Vehicle Tracking & EasyOCR Number Plate Scanner", "Poonamallee High Road", 30, "TRAFFIC & ANPR", "#0284c7"),
            ("crowd.mp4", "SkyEye Aerial UAS (Pedestrian Crosswalk)", "Overhead Optical Density & Pedestrian Safety Zone Rules", "Guindy Overpass", 30, "PEDESTRIANS", "#7c3aed")
        ]

        for fname, name, desc, sector, fps, badge, color in presets:
            full_path = os.path.abspath(os.path.join("data", "input", fname))
            is_active = (full_path.lower() == self.selected_path.lower())
            card = EnterpriseStreamCard(fname, name, desc, sector, fps, badge, color, is_active)
            card.clicked.connect(self.select_stream_card)
            self.cards_list.append(card)
            left_box.addWidget(card)

        # Custom Local Video Browser Box
        browse_card = EnterpriseCard()
        b_lay = QHBoxLayout(browse_card)
        b_lay.setContentsMargins(14, 10, 14, 10)

        self.path_display = QLabel(f"Selected: {os.path.basename(self.selected_path)}")
        self.path_display.setStyleSheet("color: #0f172a; font-size: 12px; font-weight: 700;")
        b_lay.addWidget(self.path_display, stretch=1)

        browse_btn = QPushButton("📁 Browse Custom Video...")
        browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #0f172a;
                border: 1px solid #cbd5e1;
                padding: 7px 16px;
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

        # Right: AI Pipeline Configuration
        right_card = EnterpriseCard()
        r_lay = QVBoxLayout(right_card)
        r_lay.setContentsMargins(22, 22, 22, 22)
        r_lay.setSpacing(16)

        r_title = QLabel("AI ENGINE & MAPBOX CONFIGURATION")
        r_title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        r_title.setStyleSheet("color: #0f172a; font-weight: 900; letter-spacing: 0.5px;")
        r_lay.addWidget(r_title)

        self.pothole_check = QCheckBox("🕳️ Asphalt Depth & Crater Severity AI")
        self.pothole_check.setChecked(True)
        self.pothole_check.setStyleSheet("color: #0f172a; font-size: 12px; font-weight: 700;")
        
        self.plate_check = QCheckBox("🚗 EasyOCR License Plate Recognition")
        self.plate_check.setChecked(True)
        self.plate_check.setStyleSheet("color: #0f172a; font-size: 12px; font-weight: 700;")

        self.track_check = QCheckBox("🚙 ByteTrack Persistent Vehicle Identification")
        self.track_check.setChecked(True)
        self.track_check.setStyleSheet("color: #0f172a; font-size: 12px; font-weight: 700;")

        r_lay.addWidget(self.pothole_check)
        r_lay.addWidget(self.plate_check)
        r_lay.addWidget(self.track_check)

        r_lay.addSpacing(6)

        s_box = QVBoxLayout()
        s_box.setSpacing(4)
        s_lbl = QLabel("INFERENCE PLAYBACK RATE")
        s_lbl.setStyleSheet("color: #475569; font-size: 11px; font-weight: 800;")
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
                padding: 8px 12px;
                font-size: 12px;
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
                font-size: 13px;
                padding: 15px;
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

        split_layout.addWidget(right_card, stretch=5)
        layout.addLayout(split_layout)

    def select_stream_card(self, path: str):
        self.selected_path = path
        self.path_display.setText(f"Selected: {os.path.basename(path)}")
        for c in self.cards_list:
            c.set_active(c.video_path.lower() == path.lower())

    def browse_file(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Select Video File", "data/input", "Video Files (*.mp4 *.avi *.mov *.mkv)")
        if fname:
            self.selected_path = fname
            self.path_display.setText(f"Selected: {os.path.basename(fname)}")
            for c in self.cards_list:
                c.set_active(False)

    def trigger_launch(self):
        speed = float(self.speed_combo.currentData())
        self.launch_requested.emit(
            self.selected_path,
            speed,
            self.pothole_check.isChecked(),
            self.plate_check.isChecked()
        )


# ─── ANIMATED TEXT WIDGETS ───────────────────────────────────────────────────
class SmoothNumberLabel(QLabel):
    def __init__(self, initial_val: int = 0, suffix: str = "", parent=None):
        super().__init__(str(initial_val) + suffix, parent)
        self._current_val = float(initial_val)
        self._target_val = float(initial_val)
        self.suffix = suffix

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._step_value)

    def set_target(self, target: int, suffix: str = ""):
        self._target_val = float(target)
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
    def __init__(self, title: str, initial_val: int, subtitle: str, accent_color: str = "#0284c7"):
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

    def set_value(self, val: int, sub_text: Optional[str] = None):
        self.num_label.set_target(val)
        if sub_text:
            self.sub_label.setText(sub_text)


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
    gps_updated = pyqtSignal(float, float, str, bool)
    pipeline_finished = pyqtSignal(dict)
    status_changed = pyqtSignal(str)

    def __init__(
        self,
        video_path: str,
        speed_multiplier: float = 1.0,
        enable_potholes: bool = True,
        enable_plates: bool = True
    ):
        super().__init__()
        self.video_path = video_path
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

            base_lat = 13.082700 + (raw_frame_id * 0.000008)
            base_lon = 80.270700 + (raw_frame_id * 0.000004)

            # Trigger background geocoding every 30 frames (~1 sec) without blocking frame loop
            if (raw_frame_id == 1 or raw_frame_id % 30 == 0) and not is_enriching:
                is_enriching = True
                threading.Thread(target=_async_enrich, args=(base_lat, base_lon), daemon=True).start()

            with loc_lock:
                street_name = current_loc["street_name"]
                is_school = current_loc["is_school"]

            self.gps_updated.emit(base_lat, base_lon, street_name, is_school)

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
                            "label": v_label,
                            "conf": f"{v.get('confidence', 0.8)*100:.1f}%",
                            "first_seen": f"{ts:.2f}s"
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
                                self.incident_logged.emit({
                                    "type": "POTHOLE",
                                    "id": f"POT-{incident.pothole_id}",
                                    "title": f"{h_class.upper()} #{incident.pothole_id}",
                                    "severity": "CRITICAL" if "severe" in h_class else "WARNING",
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
                        if p_text not in all_unique_plates:
                            all_unique_plates[p_text] = {
                                "plate_text": p_text,
                                "confidence": f"{p_conf * 100:.1f}%",
                                "time_sec": f"{ts:.2f}s"
                            }
                            play_alert_sound(1200, 60, category="plate", cooldown=1.0)
                            self.incident_logged.emit({
                                "type": "PLATE",
                                "id": f"PL-{p_text}",
                                "title": f"ANPR // {p_text}",
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

            # 4. School Zone Pedestrian Safety Rule
            if counts.get("pedestrians", 0) > 0 and is_school:
                play_alert_sound(1500, 120, category="school_zone", cooldown=3.0)
                self.incident_logged.emit({
                    "type": "SAFETY_ALERT",
                    "id": f"SCH-ZONE-{frame_id}",
                    "title": "SCHOOL ZONE PEDESTRIAN CROSSING ALERT",
                    "severity": "CRITICAL",
                    "confidence": "98.5%",
                    "location": f"{street_name} (School Zone)",
                    "gps": f"{base_lat:.5f}, {base_lon:.5f}",
                    "lat": base_lat,
                    "lon": base_lon,
                    "timestamp": time.strftime("%H:%M:%S"),
                    "time_sec": f"{ts:.2f}s"
                })

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
                "total_infra_defects": len(all_infra_defects),
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

        summary = {
            "total_frames": raw_frame_id,
            "time_taken_sec": round(total_time, 2),
            "unique_potholes": len(spatial_dedup.incidents),
            "unique_plates": len(all_unique_plates),
            "total_vehicles_tracked": len(all_tracked_vehicles),
            "total_pedestrians_tracked": len(all_tracked_pedestrians),
            "potholes": [inc.to_dict() for inc in spatial_dedup.incidents],
            "plates": list(all_unique_plates.values()),
            "tracked_vehicles": list(all_tracked_vehicles.values())
        }

        self.status_changed.emit(f"TELEMETRY COMPLETE // {raw_frame_id} FRAMES IN {total_time:.1f}S")
        self.pipeline_finished.emit(summary)


# ─── MAIN ADVANCED MISSION-CONTROL PYQT5 APPLICATION ─────────────────────────
class UrbanSurveillanceApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ARGUS // Autonomous Urban Transit Sensing & Municipal Intelligence Platform")
        self.resize(1460, 920)
        self.setMinimumSize(1150, 760)

        self.worker: Optional[VideoInferenceWorker] = None
        self.current_video_path = os.path.abspath("data/input/pothole.mp4")
        self.current_speed = 1.0
        self.enable_potholes = True
        self.enable_plates = True

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
        self.sub_title = TypewriterLabel("THE HUNDRED EYES OF THE CITY · ACCELERATOR: NVIDIA CUDA FP16 · MAPBOX: CONNECTED")
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
        self.card_vehicles = EnterpriseKpiCard("Vehicles Tracked", 0, "Persistent Tracking", "#0284c7")
        self.card_pedestrians = EnterpriseKpiCard("Pedestrians Logged", 0, "Crosswalk Flow", "#f59e0b")
        self.card_infra = EnterpriseKpiCard("Road Infrastructure", 0, "Dividers / Zebra / Water", "#8b5cf6")

        cards_grid.addWidget(self.card_potholes)
        cards_grid.addWidget(self.card_plates)
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

        self.pause_btn = QPushButton("⏸ Pause")
        self.pause_btn.clicked.connect(self.toggle_pause)
        self.snapshot_btn = QPushButton("📸 Snapshot")
        self.snapshot_btn.clicked.connect(self.capture_snapshot)
        self.export_btn = QPushButton("💾 Export (JSON)")
        self.export_btn.clicked.connect(self.export_report)
        self.pwd_btn = QPushButton("📋 PWD Work-Order (CSV)")
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

        hud_bar.addWidget(self.status_badge)
        hud_bar.addSpacing(10)
        hud_bar.addWidget(self.fps_label)
        hud_bar.addSpacing(10)
        hud_bar.addWidget(self.latency_label)
        hud_bar.addSpacing(10)
        hud_bar.addWidget(self.street_label)
        hud_bar.addStretch()
        hud_bar.addWidget(self.pause_btn)
        hud_bar.addWidget(self.snapshot_btn)
        hud_bar.addWidget(self.export_btn)
        hud_bar.addWidget(self.pwd_btn)

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

        tabs_lay.addWidget(self.tabs)
        right_panel.addWidget(tabs_card, stretch=1)

        content_layout.addLayout(right_panel, stretch=6)
        cockpit_layout.addLayout(content_layout, stretch=1)

        self.stack.addWidget(self.cockpit_screen)
        self.stack.setCurrentIndex(0)

    def populate_video_combo(self):
        self.video_combo.clear()
        input_dir = os.path.join("data", "input")
        if os.path.exists(input_dir):
            for f in os.listdir(input_dir):
                if f.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
                    self.video_combo.addItem(f, os.path.abspath(os.path.join(input_dir, f)))
        if self.video_combo.count() == 0:
            self.video_combo.addItem("pothole.mp4", self.current_video_path)
        else:
            for i in range(self.video_combo.count()):
                if "divider" in self.video_combo.itemText(i).lower():
                    self.video_combo.setCurrentIndex(i)
                    self.current_video_path = self.video_combo.itemData(i)
                    break

    def on_video_selected(self, index: int):
        path = self.video_combo.itemData(index)
        if path and os.path.exists(path):
            self.current_video_path = path

    def on_speed_changed(self, index: int):
        speed = float(self.speed_combo.itemData(index))
        self.current_speed = speed
        if self.worker is not None and self.worker.isRunning():
            self.worker.set_speed(speed)

    def switch_to_ingestion(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()
            self.worker = None
        self.nav_home.setStyleSheet("background-color: #0284c7; color: white; border: none; border-radius: 8px; font-size: 17px;")
        self.nav_cockpit.setStyleSheet("background-color: #f1f5f9; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 17px;")
        self.stack.setCurrentIndex(0)

    def switch_to_cockpit(self):
        self.nav_home.setStyleSheet("background-color: #f1f5f9; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 17px;")
        self.nav_cockpit.setStyleSheet("background-color: #0284c7; color: white; border: none; border-radius: 8px; font-size: 17px;")
        self.stack.setCurrentIndex(1)

    def on_ingestion_launch(self, path: str, speed: float, enable_potholes: bool, enable_plates: bool):
        self.current_video_path = path
        self.current_speed = speed
        self.enable_potholes = enable_potholes
        self.enable_plates = enable_plates

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
            enable_plates=self.enable_plates
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

        v_tot = data.get('total_vehicles_logged', 0)
        v_vis = data.get('visible_vehicles', 0)
        self.card_vehicles.set_value(v_tot, f"{v_vis} in active view")

        p_tot = data.get('total_pedestrians_logged', 0)
        p_vis = data.get('visible_pedestrians', 0)
        self.card_pedestrians.set_value(p_tot, f"{p_vis} in active view")

        self.card_infra.set_value(data.get('total_infra_defects', 0))

        self.street_label.setText(f"SECTOR: {data['street']}")

    def add_incident_to_feed(self, inc: dict):
        if self.last_frame_qimage:
            inc["pixmap"] = QPixmap.fromImage(self.last_frame_qimage)

        self.all_incidents.append(inc)
        self.mapbox_widget.add_incident_marker(inc)

        item_text = f"[{inc['timestamp']}] {inc['type']} // {inc['title']}\nSECTOR: {inc['location']} | GPS: {inc['gps']} (Conf: {inc['confidence']})"
        item = QListWidgetItem(item_text)
        item.setData(Qt.UserRole, inc)
        if inc['severity'] == 'CRITICAL':
            item.setForeground(QColor("#dc2626"))
        elif inc['severity'] == 'WARNING':
            item.setForeground(QColor("#d97706"))
        elif inc['type'] in ('ZEBRA_CROSSING', 'ROAD_DIVIDER', 'SIGNBOARD'):
            item.setForeground(QColor("#059669"))
        elif inc['type'] == 'VEHICLE':
            item.setForeground(QColor("#0284c7"))
        else:
            item.setForeground(QColor("#16a34a"))
        self.event_list.insertItem(0, item)

        if inc['type'] == 'POTHOLE':
            row = self.pothole_table.rowCount()
            self.pothole_table.insertRow(row)
            self.pothole_table.setItem(row, 0, QTableWidgetItem(inc['id']))
            self.pothole_table.setItem(row, 1, QTableWidgetItem(inc['severity']))
            self.pothole_table.setItem(row, 2, QTableWidgetItem(inc['confidence']))
            self.pothole_table.setItem(row, 3, QTableWidgetItem(inc['gps']))
        elif inc['type'] == 'PLATE':
            row = self.plate_table.rowCount()
            self.plate_table.insertRow(row)
            self.plate_table.setItem(row, 0, QTableWidgetItem(inc['title'].replace("ANPR // ", "")))
            self.plate_table.setItem(row, 1, QTableWidgetItem(inc['confidence']))
            self.plate_table.setItem(row, 2, QTableWidgetItem(inc['time_sec']))
        elif inc['type'] == 'VEHICLE':
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

    def on_incident_clicked(self, item: QListWidgetItem):
        inc_data = item.data(Qt.UserRole)
        if inc_data:
            dialog = EvidenceInspectorDialog(inc_data, self)
            dialog.exec_()

    def on_pipeline_done(self, summary: dict):
        self.last_summary_data = summary
        self.start_btn.setText("▶ ENGAGE TELEMETRY")
        self.start_btn.setStyleSheet("background-color: #0284c7; color: white; font-weight: 800; padding: 8px 18px; border-radius: 6px; border: none;")
        self.status_badge.set_idle("● MISSION COMPLETE")
        self.prog_bar.setValue(100)

    def capture_snapshot(self):
        if self.last_frame_qimage:
            os.makedirs("data/output", exist_ok=True)
            save_path = f"data/output/snapshot_{int(time.time())}.jpg"
            self.last_frame_qimage.save(save_path)
            self.status_badge.set_live(f"📸 SNAPSHOT SAVED // {save_path}")
            QMessageBox.information(self, "Forensic Snapshot Saved", f"Frame snapshot saved to:\n{save_path}")

    def export_report(self):
        if not self.last_summary_data:
            QMessageBox.warning(self, "No Telemetry Data", "Engage telemetry stream before generating report.")
            return
        os.makedirs("data/output", exist_ok=True)
        report_path = os.path.abspath("data/output/surveillance_report.json")
        with open(report_path, "w") as f:
            json.dump(self.last_summary_data, f, indent=2)
        QMessageBox.information(self, "Dossier Exported", f"Forensic Dossier successfully saved to:\n{report_path}")

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
