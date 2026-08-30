import os
import logging
import cv2
import torch
import numpy as np
from typing import Dict, List, Any, Optional, Union

# pyrefly: ignore [missing-import]
from ultralytics import YOLO

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Severity Classification by Bounding Box Area
# ─────────────────────────────────────────────
# Thresholds are expressed as fraction of total frame area.
# Tune these values if needed for your camera / road distance.
SEVERITY_AREA_THRESHOLDS = {
    "severe pothole":  0.015,   # bbox > 1.5% of frame area  → Severe
    "mild pothole":    0.005,   # bbox 0.5%–1.5% of frame    → Mild
    "shallow pothole": 0.0,     # bbox < 0.5% of frame       → Shallow
}

# Color mapping for severity visualization (BGR)
SEVERITY_COLORS = {
    "severe pothole":  (0,   0,   255),   # Red
    "mild pothole":    (0,   165, 255),   # Orange
    "shallow pothole": (0,   255, 255),   # Yellow
}

DEFAULT_HF_REPO   = "peterhdd/pothole-detection-yolov8"
DEFAULT_HF_FILE   = "best.pt"
DEFAULT_LOCAL_MODEL = os.path.join("models", "pothole.pt")


def _download_pothole_model(local_path: str) -> bool:
    """
    Downloads the pre-trained pothole YOLOv8 model from HuggingFace
    using huggingface_hub — works correctly on Windows (no hf:// path issues).
    Saves the file permanently to local_path.

    Returns True on success, False on failure.
    """
    try:
        from huggingface_hub import hf_hub_download
        logger.info(f"Downloading pothole model from HuggingFace ({DEFAULT_HF_REPO}/{DEFAULT_HF_FILE})...")
        cached_path = hf_hub_download(
            repo_id=DEFAULT_HF_REPO,
            filename=DEFAULT_HF_FILE
        )
        # Copy from HuggingFace cache to our models/ folder for easy local access
        import shutil
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        shutil.copy2(cached_path, local_path)
        logger.info(f"Pothole model saved to '{local_path}' — runs offline from now on.")
        return True
    except Exception as e:
        logger.error(f"Failed to download pothole model from HuggingFace: {e}")
        return False


def classify_severity(x1: float, y1: float, x2: float, y2: float,
                      frame_w: int, frame_h: int) -> str:
    """
    Classifies pothole severity based on its bounding box area
    relative to the total frame area.

    Returns:
        "severe pothole" | "mild pothole" | "shallow pothole"
    """
    bbox_area = (x2 - x1) * (y2 - y1)
    frame_area = frame_w * frame_h
    ratio = bbox_area / frame_area if frame_area > 0 else 0.0

    if ratio >= SEVERITY_AREA_THRESHOLDS["severe pothole"]:
        return "severe pothole"
    elif ratio >= SEVERITY_AREA_THRESHOLDS["mild pothole"]:
        return "mild pothole"
    else:
        return "shallow pothole"


class PotholeDetector:
    """
    Local YOLOv8 Pothole Detection & Severity Classification Module.

    - Runs 100% on your local NVIDIA GPU — zero internet required after first run.
    - On first run, auto-downloads the pre-trained model from HuggingFace
      (same way yolov8s.pt is auto-downloaded by Ultralytics).
    - Classifies detected potholes into: Severe, Mild, and Shallow
      based on bounding box area relative to frame size.
    - Fully compatible with the ingestion layer frame packet schema.
    """

    def __init__(
        self,
        model_path: str = DEFAULT_LOCAL_MODEL,
        conf_threshold: float = 0.35
    ):
        self.conf_threshold = conf_threshold

        # GPU device selection — same as TrafficYOLODetector
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        device_name = torch.cuda.get_device_name(0) if self.device == "cuda" else "CPU"
        logger.info(f"Initializing PotholeDetector on device: '{self.device}' ({device_name})")

        os.makedirs("models", exist_ok=True)

        # Resolve model path:
        # 1. Use local .pt if it already exists in models/ (fast, offline)
        # 2. Otherwise, download once from HuggingFace and save locally
        if not os.path.exists(model_path):
            success = _download_pothole_model(model_path)
            if not success:
                logger.error("Pothole model could not be loaded. Detection is disabled.")
                self.model = None
                return
        else:
            logger.info(f"Loading local pothole model from: '{model_path}'")

        try:
            self.model = YOLO(model_path)
        except Exception as e:
            logger.error(f"Failed to load pothole model '{model_path}': {e}")
            self.model = None

    def detect(
        self,
        frame_or_packet: Union[Dict[str, Any], np.ndarray],
        annotate: bool = True
    ) -> Dict[str, Any]:
        """
        Detects and classifies potholes in a video frame using local GPU inference.

        Args:
            frame_or_packet: Ingestion layer frame packet dict OR raw BGR numpy array.
            annotate:        If True, draws bounding boxes + labels on the returned frame.

        Returns:
            Dictionary with pothole counts, severity breakdown, detections list,
            and annotated frame — compatible with the main pipeline schema.
        """
        # Unpack frame packet or raw image
        if isinstance(frame_or_packet, dict):
            image       = frame_or_packet.get("image")
            frame_id    = frame_or_packet.get("frame_id", 0)
            raw_frame_id = frame_or_packet.get("raw_frame_id", frame_id)
            timestamp_sec = frame_or_packet.get("timestamp_sec", 0.0)
        else:
            image        = frame_or_packet
            frame_id     = 0
            raw_frame_id = 0
            timestamp_sec = 0.0

        if image is None:
            raise ValueError("Input image to PotholeDetector is None.")

        annotated_frame = image.copy()
        img_h, img_w = image.shape[:2]

        detections = []
        breakdown  = {"severe pothole": 0, "mild pothole": 0, "shallow pothole": 0}

        if self.model is None:
            logger.warning("PotholeDetector model is not loaded. Skipping detection.")
            return self._empty_result(frame_id, raw_frame_id, timestamp_sec, annotated_frame)

        # ── Local GPU Inference (same as TrafficYOLODetector) ──────────────────
        results = self.model.predict(
            source=image,
            conf=self.conf_threshold,
            device=self.device,
            imgsz=640,
            verbose=False
        )[0]

        # ── Parse Predictions ──────────────────────────────────────────────────
        for box in results.boxes:
            conf = float(box.conf[0].item())
            xyxy = box.xyxy[0].tolist()
            x1, y1, x2, y2 = xyxy

            # Classify severity by bounding box size relative to frame
            severity = classify_severity(x1, y1, x2, y2, img_w, img_h)

            det_info = {
                "class":      severity,
                "confidence": round(conf, 3),
                "bbox":       [int(x1), int(y1), int(x2), int(y2)],
                "center":     [round((x1 + x2) / 2, 1), round((y1 + y2) / 2, 1)],
                "dimensions": [round(x2 - x1, 1), round(y2 - y1, 1)]
            }
            detections.append(det_info)
            breakdown[severity] += 1

            # ── Draw Annotations ───────────────────────────────────────────────
            if annotate:
                color = SEVERITY_COLORS.get(severity, (0, 0, 255))
                ix1, iy1, ix2, iy2 = int(x1), int(y1), int(x2), int(y2)

                # Bounding box
                cv2.rectangle(annotated_frame, (ix1, iy1), (ix2, iy2), color, 2)

                # Label banner
                label_text = f"{severity.title()}: {conf * 100:.0f}%"
                font = cv2.FONT_HERSHEY_SIMPLEX
                (tw, th), _ = cv2.getTextSize(label_text, font, 0.5, 1)
                banner_y = max(0, iy1 - th - 6)
                cv2.rectangle(annotated_frame, (ix1, banner_y), (ix1 + tw + 6, iy1), color, -1)
                cv2.putText(annotated_frame, label_text, (ix1 + 3, iy1 - 4),
                            font, 0.5, (0, 0, 0), 1)

        return {
            "frame_id":       frame_id,
            "raw_frame_id":   raw_frame_id,
            "timestamp_sec":  timestamp_sec,
            "pothole_count":  len(detections),
            "breakdown":      breakdown,
            "detections":     detections,
            "annotated_frame": annotated_frame
        }

    def _empty_result(self, frame_id, raw_frame_id, timestamp_sec, frame) -> Dict[str, Any]:
        return {
            "frame_id":       frame_id,
            "raw_frame_id":   raw_frame_id,
            "timestamp_sec":  timestamp_sec,
            "pothole_count":  0,
            "breakdown":      {"severe pothole": 0, "mild pothole": 0, "shallow pothole": 0},
            "detections":     [],
            "annotated_frame": frame
        }
