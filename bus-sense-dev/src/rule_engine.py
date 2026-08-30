"""
Step 3: OCR & Safety Rule Engine
─────────────────────────────────
Consumes the raw YOLO traffic event and applies two rules:

Rule A – School Zone Safety
    IF pedestrians > 0 in frame  →  HIGH PRIORITY pedestrian safety alert
    ELSE                          →  Standard traffic monitoring

Rule B – License Plate OCR
    For every vehicle bounding box that looks like it could carry a visible
    plate (car, bus, truck), crop the bottom-third of the bbox (where plates
    sit), run EasyOCR, clean the text, and return structured plate records.

Output schema (RuleEngineResult dict):
{
    "frame_id":           int,
    "timestamp_sec":      float,
    "school_zone_active": bool,       # True when pedestrians detected
    "alert_level":        str,        # "HIGH_PRIORITY" | "STANDARD"
    "alert_message":      str,
    "pedestrian_count":   int,
    "plates":             [           # list of extracted plates (may be empty)
        {
            "vehicle_bbox":  [x1,y1,x2,y2],
            "vehicle_label": str,
            "plate_text":    str,     # e.g. "KA-01-MJ-4021"
            "raw_ocr":       str,     # before cleanup
            "confidence":    float    # mean EasyOCR confidence
        }, ...
    ]
}
"""

import re
import logging
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ── OCR reader is expensive to init; create once and reuse ──────────────────
_ocr_reader = None


def _get_reader():
    """Lazy-load EasyOCR reader (GPU if available, CPU fallback)."""
    global _ocr_reader
    if _ocr_reader is None:
        try:
            # pyrefly: ignore [missing-import]
            import easyocr
            # pyrefly: ignore [missing-import]
            import torch
            gpu = torch.cuda.is_available()
            logger.info(f"Loading EasyOCR reader (gpu={gpu})...")
            _ocr_reader = easyocr.Reader(["en"], gpu=gpu, verbose=False)
            logger.info("EasyOCR reader ready.")
        except ImportError:
            logger.warning(
                "easyocr not installed — plate OCR disabled. "
                "Run: pip install easyocr"
            )
    return _ocr_reader


# ── Plate text normalisation ─────────────────────────────────────────────────

# Indian plate pattern: XX-00-XX-0000
_PLATE_RE = re.compile(
    r"[A-Z]{2}[\s\-]?\d{1,2}[\s\-]?[A-Z]{1,3}[\s\-]?\d{1,4}", re.IGNORECASE
)


def _clean_plate(raw: str) -> str:
    """
    Normalises raw OCR text into a standard Indian plate format.
    Strips noise, maps common OCR confusions, inserts hyphens.
    """
    text = re.sub(r"[^A-Z0-9\s\-]", "", raw.upper()).strip()
    text = re.sub(r"\s+", " ", text)

    m = _PLATE_RE.search(text)
    if m:
        return re.sub(r"[\s\-]+", "-", m.group()).upper()

    # Fallback: return cleaned compact text if long enough to be useful
    compact = re.sub(r"[\s\-]", "", text)
    return compact if len(compact) >= 4 else ""


# ── Vehicle classes that typically carry readable plates ────────────────────
_PLATE_VEHICLE_LABELS = {"car", "bus", "truck", "motorcycle"}


def _crop_plate_region(image: np.ndarray, bbox: List[float]) -> np.ndarray:
    """
    Crops the bottom-third of a vehicle bounding box — where number plates sit.
    Expands horizontally by 10% each side to handle slight misalignment.
    """
    h, w = image.shape[:2]
    x1, y1, x2, y2 = [int(v) for v in bbox]

    box_h = y2 - y1
    plate_y1 = y1 + int(box_h * 0.65)   # bottom 35% of bbox
    plate_y2 = y2

    expand_x = int((x2 - x1) * 0.10)
    plate_x1 = max(0, x1 - expand_x)
    plate_x2 = min(w, x2 + expand_x)
    plate_y1 = max(0, plate_y1)
    plate_y2 = min(h, plate_y2)

    return image[plate_y1:plate_y2, plate_x1:plate_x2]


def _preprocess_plate_crop(crop: np.ndarray) -> np.ndarray:
    """
    2x upscale → grayscale → CLAHE contrast boost.
    Significantly improves EasyOCR accuracy on small/shadowed plates.
    """
    if crop.size == 0:
        return crop

    crop = cv2.resize(
        crop,
        (crop.shape[1] * 2, crop.shape[0] * 2),
        interpolation=cv2.INTER_CUBIC
    )
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
    gray = clahe.apply(gray)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


# ── Main Rule Engine ─────────────────────────────────────────────────────────

class SafetyRuleEngine:
    """
    OCR & Safety Rule Engine (Step 3 of the Smart City pipeline).

    Usage:
        engine = SafetyRuleEngine()
        result = engine.evaluate(traffic_event, frame_image)
    """

    def __init__(
        self,
        ocr_enabled: bool = True,
        min_ocr_confidence: float = 0.30,
        min_vehicle_bbox_area: int = 1500,   # px² — skip tiny far-away boxes
        plate_cooldown_sec: float = 3.0,     # suppress same plate re-emit within N seconds
    ):
        self.ocr_enabled = ocr_enabled
        self.min_ocr_confidence = min_ocr_confidence
        self.min_vehicle_bbox_area = min_vehicle_bbox_area
        self.plate_cooldown_sec = plate_cooldown_sec

        # {plate_text: last_emitted_timestamp_sec}
        self._plate_cooldown: Dict[str, float] = {}

        if ocr_enabled:
            _get_reader()   # warm up at init so first frame isn't slow

    # ── Rule A: School Zone / Pedestrian Safety ──────────────────────────────

    @staticmethod
    def _evaluate_school_zone(pedestrian_count: int, location_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        is_geo_school = bool(location_context and location_context.get("is_school_zone"))
        is_geo_hosp = bool(location_context and location_context.get("is_hospital_zone"))
        street = (location_context.get("street_name") if location_context else None) or "Main Road"

        if pedestrian_count > 0:
            if is_geo_school:
                return {
                    "school_zone_active": True,
                    "alert_level": "CRITICAL_SCHOOL_ZONE",
                    "alert_message": (
                        f"CRITICAL: {pedestrian_count} pedestrian(s) in active SCHOOL ZONE ({street}). "
                        "Immediate 20 km/h speed limit enforcement and visual alert broadcast."
                    ),
                }
            elif is_geo_hosp:
                return {
                    "school_zone_active": True,
                    "alert_level": "HOSPITAL_ZONE_ALERT",
                    "alert_message": (
                        f"ALERT: {pedestrian_count} pedestrian(s) near HOSPITAL ZONE ({street}). "
                        "Enforce pedestrian right of way & no-honking zone."
                    ),
                }
            return {
                "school_zone_active": True,
                "alert_level": "HIGH_PRIORITY",
                "alert_message": (
                    f"ALERT: {pedestrian_count} pedestrian(s) detected on roadway ({street}). "
                    "Enforce speed limit. Activate warning signboard."
                ),
            }
        return {
            "school_zone_active": False,
            "alert_level": "STANDARD",
            "alert_message": f"Standard traffic flow monitoring on {street}.",
        }

    # ── Rule B: License Plate OCR ────────────────────────────────────────────

    def _extract_plates(
        self,
        image: np.ndarray,
        vehicles: List[Dict[str, Any]],
        timestamp_sec: float = 0.0,
    ) -> List[Dict[str, Any]]:
        reader = _get_reader()
        if reader is None:
            return []

        results = []
        for vehicle in vehicles:
            label = vehicle.get("label", "")
            if label not in _PLATE_VEHICLE_LABELS:
                continue

            bbox = vehicle.get("bbox", [])
            if len(bbox) != 4:
                continue

            x1, y1, x2, y2 = bbox
            if (x2 - x1) * (y2 - y1) < self.min_vehicle_bbox_area:
                continue   # too small / too far away — noisy crop

            crop = _crop_plate_region(image, bbox)
            if crop.size == 0:
                continue

            processed = _preprocess_plate_crop(crop)

            try:
                ocr_results = reader.readtext(processed, detail=1)
            except Exception as e:
                logger.debug(f"EasyOCR failed on crop: {e}")
                continue

            if not ocr_results:
                continue

            high_conf = [
                (text, conf)
                for (_, text, conf) in ocr_results
                if conf >= self.min_ocr_confidence
            ]
            if not high_conf:
                continue

            raw_text = " ".join(t for t, _ in high_conf)
            mean_conf = sum(c for _, c in high_conf) / len(high_conf)
            plate_text = _clean_plate(raw_text)

            if not plate_text:
                continue

            # Cooldown: suppress re-logging the same plate within N seconds
            # Every frame is processed, but we only emit a plate event once per 3s
            last_seen = self._plate_cooldown.get(plate_text, -999.0)
            if (timestamp_sec - last_seen) < self.plate_cooldown_sec:
                continue
            self._plate_cooldown[plate_text] = timestamp_sec

            logger.info(
                f"[Rule Engine] Plate → '{plate_text}' "
                f"(raw: '{raw_text}', conf: {mean_conf:.2f}) [{label}]"
            )
            results.append({
                "vehicle_bbox":  [int(v) for v in bbox],
                "vehicle_label": label,
                "plate_text":    plate_text,
                "raw_ocr":       raw_text,
                "confidence":    round(mean_conf, 3),
            })

        return results

    # ── Public API ───────────────────────────────────────────────────────────

    def evaluate(
        self,
        traffic_event: Dict[str, Any],
        image: Optional[np.ndarray] = None,
        location_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate all safety rules for a single frame with Maps geospatial context.

        Args:
            traffic_event:    Output dict from TrafficYOLODetector.detect()
            image:            Raw BGR frame (required for plate OCR; pass None to skip OCR)
            location_context: Optional enriched location dictionary from MapsEnricher.

        Returns:
            RuleEngineResult dict (see module docstring for full schema)
        """
        frame_id      = traffic_event.get("frame_id", 0)
        timestamp_sec = traffic_event.get("timestamp_sec", 0.0)
        detections    = traffic_event.get("detections", {})

        pedestrians     = detections.get("pedestrians", [])
        vehicles        = detections.get("vehicles", [])
        pedestrian_count = len(pedestrians)

        # Rule A — school zone / pedestrian safety enriched with Maps POI
        zone_result = self._evaluate_school_zone(pedestrian_count, location_context=location_context)

        if zone_result["alert_level"] in ("HIGH_PRIORITY", "CRITICAL_SCHOOL_ZONE", "HOSPITAL_ZONE_ALERT"):
            logger.warning(
                f"[Rule Engine] Frame {frame_id:04d} | {zone_result['alert_message']}"
            )

        # Rule B — plate OCR: runs every frame, but deduplicates by plate cooldown
        plates: List[Dict[str, Any]] = []
        if self.ocr_enabled and image is not None and vehicles:
            plates = self._extract_plates(image, vehicles, timestamp_sec)

        return {
            "frame_id":           frame_id,
            "timestamp_sec":      timestamp_sec,
            "pedestrian_count":   pedestrian_count,
            "location":           location_context or {},
            **zone_result,
            "plates":             plates,
        }

