"""
src/hazard_detector.py — Unified Road Hazard Intelligence Engine.
Detects, classifies, and assesses road infrastructure hazards:
  1. Potholes (Severe / Mild / Shallow area classification)
  2. Barricades & Construction Barriers
  3. Water Logging & Street Flooding
Accelerated with native PyTorch FP16 on NVIDIA Tensor Cores.
"""

import os
import logging
from typing import Dict, Any, List, Optional
import cv2
import numpy as np
import torch
from ultralytics import YOLO

logger = logging.getLogger("RoadHazardDetector")

DEFAULT_POTHOLE_MODEL = os.path.join("models", "pothole.pt")
DEFAULT_UNIFIED_MODEL = os.path.join("models", "road_hazard.pt")


class RoadHazardDetector:
    """
    Unified Road Hazard AI Engine.
    Inspects model class taxonomy dynamically to identify potholes, barricades, and water logging.
    """

    HAZARD_COLORS = {
        "severe pothole": (0, 0, 255),       # Crimson Red
        "mild pothole": (0, 140, 255),        # Deep Amber/Orange
        "shallow pothole": (0, 215, 255),     # Yellow
        "pothole": (0, 0, 255),
        "barricade": (11, 158, 245),          # Bright Amber
        "barrier": (11, 158, 245),
        "water_logging": (255, 200, 0),       # Cyan / Aqua
        "flooding": (255, 200, 0),
        "hazard": (0, 165, 255)
    }

    def __init__(
        self,
        model_path: Optional[str] = None,
        conf_threshold: float = 0.30,
        secondary_model_path: Optional[str] = None
    ):
        self.conf_threshold = conf_threshold
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.half = (self.device == "cuda")
        device_name = torch.cuda.get_device_name(0) if self.device == "cuda" else "CPU"

        logger.info(f"Initializing RoadHazardDetector on device: '{self.device}' ({device_name}) [FP16={self.half}]")

        # Resolve primary model path
        if model_path and os.path.exists(model_path):
            chosen_path = model_path
        elif os.path.exists(DEFAULT_UNIFIED_MODEL):
            chosen_path = DEFAULT_UNIFIED_MODEL
        elif os.path.exists(DEFAULT_POTHOLE_MODEL):
            chosen_path = DEFAULT_POTHOLE_MODEL
        else:
            chosen_path = "models/pothole.pt"

        self.primary_model = YOLO(chosen_path)
        if self.device == "cuda":
            self.primary_model.to(self.device)
            self.primary_model.half()

        # Inspect class names
        self.class_names = self.primary_model.names
        logger.info(f"Road Hazard Model loaded from '{chosen_path}'. Taxonomy: {self.class_names}")

        # Optional secondary hazard model (e.g. specialized barricade or flood detector)
        self.secondary_model = None
        sec_path = secondary_model_path or os.path.join("models", "barricade.pt")
        if os.path.exists(sec_path):
            try:
                self.secondary_model = YOLO(sec_path)
                if self.device == "cuda":
                    self.secondary_model.to(self.device)
                    self.secondary_model.half()
                logger.info(f"Secondary Hazard Model loaded from '{sec_path}'.")
            except Exception as e:
                logger.warning(f"Could not load secondary hazard model: {e}")

    def _classify_hazard(self, raw_label: str, bbox: List[float], img_area: int) -> Dict[str, Any]:
        """Categorizes raw YOLO class into standardized hazard taxonomy and calculates severity."""
        label_lower = raw_label.lower().replace("-", "_").replace(" ", "_")
        x1, y1, x2, y2 = bbox
        box_area = max(0, x2 - x1) * max(0, y2 - y1)
        area_ratio = box_area / max(1, img_area)

        # Check for Water Logging
        if any(k in label_lower for k in ["water", "flood", "puddle", "logging"]):
            return {
                "hazard_type": "water_logging",
                "hazard_class": "water_logging",
                "severity": "CRITICAL" if area_ratio >= 0.03 else "WARNING",
                "area_ratio": area_ratio
            }

        # Check for Barricade / Barrier
        if any(k in label_lower for k in ["barricade", "barrier", "cone", "construction", "obstacle"]):
            return {
                "hazard_type": "barricade",
                "hazard_class": "barricade",
                "severity": "WARNING",
                "area_ratio": area_ratio
            }

        # Default to Pothole
        # Calibrated for transit dashcam / bus roof camera perspective:
        bw = max(0, x2 - x1)
        bh = max(0, y2 - y1)
        if area_ratio >= 0.008 or (bw >= 130 and bh >= 55):
            severity_class = "severe pothole"
            severity_level = "CRITICAL"
        elif area_ratio >= 0.0025 or (bw >= 65 and bh >= 30):
            severity_class = "mild pothole"
            severity_level = "WARNING"
        else:
            severity_class = "shallow pothole"
            severity_level = "INFO"

        return {
            "hazard_type": "pothole",
            "hazard_class": severity_class,
            "severity": severity_level,
            "area_ratio": area_ratio
        }

    def detect(self, frame_packet: Dict[str, Any], annotate: bool = True) -> Dict[str, Any]:
        """
        Runs hardware-accelerated hazard detection on frame_packet.
        Returns unified detections for Potholes, Barricades, and Water Logging.
        """
        image = frame_packet["image"]
        frame_id = frame_packet.get("frame_id", 0)
        ts = frame_packet.get("timestamp_sec", 0.0)
        h, w = image.shape[:2]
        img_area = h * w
        annotated_frame = image.copy() if annotate else None

        hazards = []
        counts = {
            "total": 0,
            "potholes": 0,
            "severe pothole": 0,
            "mild pothole": 0,
            "shallow pothole": 0,
            "barricades": 0,
            "water_logging": 0
        }

        # Run Primary Hazard Model
        try:
            results = self.primary_model.predict(
                source=image,
                conf=self.conf_threshold,
                device=self.device,
                imgsz=640,
                verbose=False
            )[0]

            if results.boxes is not None and len(results.boxes) > 0:
                boxes = results.boxes.xyxy.cpu().numpy()
                confs = results.boxes.conf.cpu().numpy()
                cls_ids = results.boxes.cls.cpu().numpy().astype(int)

                for bbox, conf, cls_id in zip(boxes, confs, cls_ids):
                    raw_label = self.class_names.get(cls_id, "pothole")
                    hazard_info = self._classify_hazard(raw_label, bbox.tolist(), img_area)

                    h_type = hazard_info["hazard_type"]
                    h_class = hazard_info["hazard_class"]

                    counts["total"] += 1
                    if h_type == "pothole":
                        counts["potholes"] += 1
                        if h_class in counts:
                            counts[h_class] += 1
                    elif h_type == "barricade":
                        counts["barricades"] += 1
                    elif h_type == "water_logging":
                        counts["water_logging"] += 1

                    item = {
                        "type": h_type,
                        "class": h_class,
                        "severity": hazard_info["severity"],
                        "confidence": float(conf),
                        "bbox": [float(v) for v in bbox],
                        "area_ratio": float(hazard_info["area_ratio"])
                    }
                    hazards.append(item)

        except Exception as e:
            logger.error(f"Primary hazard inference error: {e}")

        # Run Secondary Model if available
        if self.secondary_model is not None:
            try:
                sec_res = self.secondary_model.predict(
                    source=image,
                    conf=self.conf_threshold,
                    device=self.device,
                    imgsz=640,
                    verbose=False
                )[0]
                if sec_res.boxes is not None and len(sec_res.boxes) > 0:
                    s_boxes = sec_res.boxes.xyxy.cpu().numpy()
                    s_confs = sec_res.boxes.conf.cpu().numpy()
                    s_cls = sec_res.boxes.cls.cpu().numpy().astype(int)
                    for bbox, conf, cls_id in zip(s_boxes, s_confs, s_cls):
                        raw_label = self.secondary_model.names.get(cls_id, "barricade")
                        hazard_info = self._classify_hazard(raw_label, bbox.tolist(), img_area)
                        h_type = hazard_info["hazard_type"]
                        h_class = hazard_info["hazard_class"]

                        counts["total"] += 1
                        if h_type == "barricade":
                            counts["barricades"] += 1
                        elif h_type == "water_logging":
                            counts["water_logging"] += 1

                        hazards.append({
                            "type": h_type,
                            "class": h_class,
                            "severity": hazard_info["severity"],
                            "confidence": float(conf),
                            "bbox": [float(v) for v in bbox],
                            "area_ratio": float(hazard_info["area_ratio"])
                        })
            except Exception as e:
                logger.debug(f"Secondary hazard inference error: {e}")

        # Optional Annotation
        if annotate and annotated_frame is not None:
            for hz in hazards:
                h_class = hz["class"]
                conf = hz["confidence"]
                x1, y1, x2, y2 = [int(v) for v in hz["bbox"]]
                color = self.HAZARD_COLORS.get(h_class, (0, 165, 255))

                cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)
                tag = f"{h_class.upper()} {conf*100:.0f}%"
                cv2.putText(
                    annotated_frame,
                    tag,
                    (x1, max(18, y1 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45,
                    color,
                    2
                )

        return {
            "frame_id": frame_id,
            "timestamp_sec": ts,
            "hazards": hazards,
            "detections": hazards,  # backward compatibility alias
            "counts": counts,
            "annotated_frame": annotated_frame
        }
