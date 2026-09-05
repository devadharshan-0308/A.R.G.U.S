"""
Step 3: OCR & Safety Rule Engine
─────────────────────────────────
Consumes the raw YOLO traffic event and applies three rules:

Rule A – School Zone Safety
    IF pedestrians > 0 in frame  →  HIGH PRIORITY pedestrian safety alert
    ELSE                          →  Standard traffic monitoring

Rule B – License Plate OCR (now incident-triggered, see Rule C)
    For a vehicle bounding box that looks like it could carry a visible
    plate (car, bus, truck), crop the bottom-third of the bbox (where plates
    sit), run EasyOCR, clean the text, and return structured plate records.

Rule C – Rash Driving / Hit-and-Run Detection
    Tracks each vehicle's bbox center across frames (using ByteTrack's
    track_id). Flags "rash driving" when a vehicle shows both a sudden
    speed spike AND erratic lateral movement relative to its own recent
    history. Flags "hit_and_run" when a vehicle's bbox overlaps a
    pedestrian's bbox and that vehicle does not decelerate afterward.
    Only vehicles flagged by Rule C get their plate OCR'd — this replaces
    the old "OCR everything, every frame" behaviour.

Output schema (RuleEngineResult dict):
{
    "frame_id":           int,
    "timestamp_sec":      float,
    "school_zone_active": bool,       # True when pedestrians detected
    "alert_level":        str,        # "HIGH_PRIORITY" | "STANDARD"
    "alert_message":      str,
    "pedestrian_count":   int,
    "violations":         [           # Rule C output (may be empty)
        {
            "track_id":      int,
            "vehicle_bbox":  [x1,y1,x2,y2],
            "vehicle_label": str,
            "violation_type": str,    # "RASH_DRIVING" | "HIT_AND_RUN"
            "speed_score":   float,
            "description":   str
        }, ...
    ],
    "plates":             [           # list of extracted plates (may be empty)
        {
            "vehicle_bbox":  [x1,y1,x2,y2],
            "vehicle_label": str,
            "plate_text":    str,     # e.g. "KA-01-MJ-4021"
            "raw_ocr":       str,     # before cleanup
            "confidence":    float,   # mean EasyOCR confidence
            "triggered_by":  str      # "RASH_DRIVING" | "HIT_AND_RUN"
        }, ...
    ]
}
"""

import re
import logging
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

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



# ── Rule C: Vehicle Motion History (for rash driving / hit-and-run) ─────────


def _bbox_center(bbox: List[float]) -> Tuple[float, float]:
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)



def _bbox_width(bbox: List[float]) -> float:
    x1, _, x2, _ = bbox
    return max(1.0, x2 - x1)   # avoid div-by-zero



def _bboxes_overlap(a: List[float], b: List[float]) -> bool:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    return not (ax2 < bx1 or bx2 < ax1 or ay2 < by1 or by2 < ay1)



class VehicleTrackHistory:
    """
    Remembers each tracked vehicle's recent bbox-center positions so Rule C
    can compute frame-to-frame speed and lateral swerve without needing a
    real speedometer or GPS speed feed.
    """

    def __init__(self, history_len: int = 12):
        self.history_len = history_len
        # track_id -> deque of (timestamp_sec, cx, cy, bbox_width)
        self._history: Dict[int, deque] = {}
        # track_id -> timestamp_sec when it was last seen touching a pedestrian
        self._pedestrian_contact: Dict[int, float] = {}

    def update(self, track_id: int, timestamp_sec: float, bbox: List[float]) -> None:
        cx, cy = _bbox_center(bbox)
        w = _bbox_width(bbox)
        if track_id not in self._history:
            self._history[track_id] = deque(maxlen=self.history_len)
        self._history[track_id].append((timestamp_sec, cx, cy, w))

    def mark_pedestrian_contact(self, track_id: int, timestamp_sec: float) -> None:
        self._pedestrian_contact[track_id] = timestamp_sec

    def had_recent_pedestrian_contact(self, track_id: int, timestamp_sec: float, window_sec: float = 2.0) -> bool:
        last = self._pedestrian_contact.get(track_id)
        return last is not None and (timestamp_sec - last) <= window_sec

    def compute_motion(self, track_id: int) -> Optional[Dict[str, float]]:
        """
        Returns normalised speed + lateral-swerve scores for a track,
        or None if there isn't enough history yet.
        """
        hist = self._history.get(track_id)
        if hist is None or len(hist) < 6:
            return None   # Need at least 6 frames to establish stable baseline and filter tracker snap-in

        # Speed: displacement between the last two frames, normalised by
        # vehicle bbox width (so a vehicle far away isn't unfairly flagged
        # just because it "moves fewer pixels" than a close-up vehicle).
        t_prev, x_prev, y_prev, w_prev = hist[-2]
        t_curr, x_curr, y_curr, w_curr = hist[-1]
        dt = max(1e-3, t_curr - t_prev)
        dist = ((x_curr - x_prev) ** 2 + (y_curr - y_prev) ** 2) ** 0.5
        current_speed = (dist / w_curr) / dt

        # Baseline: this vehicle's own average speed over its history
        # (excluding the very latest frame), so we detect a *spike*
        # relative to itself, not an arbitrary global threshold.
        speeds = []
        pts = list(hist)
        for i in range(1, len(pts) - 1):
            tp, xp, yp, wp = pts[i - 1]
            tc, xc, yc, wc = pts[i]
            d = max(1e-3, tc - tp)
            dd = ((xc - xp) ** 2 + (yc - yp) ** 2) ** 0.5
            speeds.append((dd / wc) / d)
        raw_baseline = (sum(speeds) / len(speeds)) if speeds else current_speed
        # Floor baseline at 0.50 width/sec: prevents dividing by near-zero when a vehicle accelerates from a stop
        effective_baseline = max(0.50, raw_baseline)

        # Lateral swerve: sum of direction reversals in the x-position
        # over the tracked window. Sub-pixel or small 1-2px jitter from
        # bounding box fluctuations must NOT count as swerving.
        xs = [p[1] for p in pts]
        deadband = max(5.0, w_curr * 0.05)  # must move at least 5px or 5% of vehicle width
        sig_diffs = []
        last_x = xs[0]
        for x in xs[1:]:
            dx = x - last_x
            if abs(dx) >= deadband:
                sig_diffs.append(dx)
                last_x = x

        reversals = 0
        for i in range(1, len(sig_diffs)):
            if sig_diffs[i] * sig_diffs[i - 1] < 0:
                reversals += 1

        return {
            "current_speed":     current_speed,
            "baseline_speed":    raw_baseline,
            "speed_spike_ratio": current_speed / effective_baseline,
            "lateral_reversals": reversals,
            "dist_px":           dist,
        }



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
        speed_spike_threshold: float = 2.0,  # current speed must be this many x the vehicle's own baseline
        lateral_reversal_threshold: int = 2, # min direction-reversals in tracked window to count as "swerving"
        violation_cooldown_sec: float = 3.0, # suppress repeat violation alerts for same track_id
    ):
        self.ocr_enabled = ocr_enabled
        self.min_ocr_confidence = min_ocr_confidence
        self.min_vehicle_bbox_area = min_vehicle_bbox_area
        self.plate_cooldown_sec = plate_cooldown_sec
        self.speed_spike_threshold = speed_spike_threshold
        self.lateral_reversal_threshold = lateral_reversal_threshold
        self.violation_cooldown_sec = violation_cooldown_sec

        # {plate_text: last_emitted_timestamp_sec}
        self._plate_cooldown: Dict[str, float] = {}
        # {track_id: last_violation_emitted_timestamp_sec}
        self._violation_cooldown: Dict[int, float] = {}

        self._motion_history = VehicleTrackHistory(history_len=15)

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
        triggered_map: Optional[Dict[int, str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        OCRs plates only for vehicles present in `triggered_map`
        (track_id -> violation_type). If triggered_map is None, falls back
        to the old "scan everything" behaviour — useful for offline testing.
        """
        reader = _get_reader()
        if reader is None:
            return []

        results = []
        for vehicle in vehicles:
            label = vehicle.get("label", "")
            if label not in _PLATE_VEHICLE_LABELS:
                continue

            track_id = vehicle.get("track_id")
            if triggered_map is not None and track_id not in triggered_map:
                continue   # only OCR vehicles flagged by Rule C

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
                "triggered_by":  (triggered_map or {}).get(track_id, "MANUAL_SCAN"),
            })

        return results


    # ── Rule C: Rash Driving / Hit-and-Run ───────────────────────────────────

    def _evaluate_violations(
        self,
        vehicles: List[Dict[str, Any]],
        pedestrians: List[Dict[str, Any]],
        timestamp_sec: float,
    ) -> List[Dict[str, Any]]:
        violations: List[Dict[str, Any]] = []

        # First, record pedestrian-contact for any vehicle whose bbox
        # overlaps a pedestrian's bbox this frame (used for hit-and-run).
        ped_bboxes = [p.get("bbox", []) for p in pedestrians if len(p.get("bbox", [])) == 4]
        for vehicle in vehicles:
            bbox = vehicle.get("bbox", [])
            track_id = vehicle.get("track_id")
            if track_id is None or len(bbox) != 4:
                continue
            if any(_bboxes_overlap(bbox, pb) for pb in ped_bboxes):
                self._motion_history.mark_pedestrian_contact(track_id, timestamp_sec)

        # Then, update motion history and evaluate each vehicle.
        for vehicle in vehicles:
            bbox = vehicle.get("bbox", [])
            track_id = vehicle.get("track_id")
            label = vehicle.get("label", "vehicle")
            if track_id is None or len(bbox) != 4:
                continue

            self._motion_history.update(track_id, timestamp_sec, bbox)
            motion = self._motion_history.compute_motion(track_id)
            if motion is None:
                continue   # not enough history yet for this track

            # Cooldown: don't re-flag the same vehicle every single frame
            last_flag = self._violation_cooldown.get(track_id, -999.0)
            if (timestamp_sec - last_flag) < self.violation_cooldown_sec:
                continue

            is_speed_spike = (motion["speed_spike_ratio"] >= self.speed_spike_threshold) and (motion.get("dist_px", 0.0) >= 8.0)
            is_swerving = (motion["lateral_reversals"] >= self.lateral_reversal_threshold)
            is_solo_speeding = (motion["speed_spike_ratio"] >= 3.0) and (motion["current_speed"] >= 1.5) and (motion.get("dist_px", 0.0) >= 15.0)
            had_contact = self._motion_history.had_recent_pedestrian_contact(track_id, timestamp_sec)

            violation_type = None
            description = ""

            # ponytail: pixel-space speed is noisy; require real physical movement before alleging violations
            #   Gate A: Hit-and-run = pedestrian contact followed by rapid vehicle egress
            #   Gate B: True rash swerving = speed surge (≥2.0x) + actual zig-zag weaving across lanes (≥2 reversals)
            #   Gate C: Hazardous speeding burst = extreme speed spike (≥3.0x) + high absolute speed (≥1.5 w/s and dist ≥15px)
            if had_contact and (motion["speed_spike_ratio"] >= 1.4 or motion.get("dist_px", 0.0) >= 8.0):
                violation_type = "HIT_AND_RUN"
                description = (
                    f"Vehicle (track #{track_id}) accelerated away after contact with pedestrian — hit-and-run suspected."
                )
            elif (is_speed_spike and is_swerving) or is_solo_speeding:
                violation_type = "RASH_DRIVING"
                if is_speed_spike and is_swerving:
                    description = (
                        f"Vehicle (track #{track_id}) exhibits erratic lane weaving "
                        f"({motion['lateral_reversals']} lateral reversals) with sudden speed surge "
                        f"({motion['speed_spike_ratio']:.1f}x baseline) — rash driving."
                    )
                else:
                    description = (
                        f"Vehicle (track #{track_id}) exhibits dangerous acceleration burst "
                        f"({motion['speed_spike_ratio']:.1f}x baseline, {motion['current_speed']:.1f} w/s) — hazardous speeding."
                    )

            if violation_type:
                self._violation_cooldown[track_id] = timestamp_sec
                logger.warning(f"[Rule Engine] Frame violation → {violation_type} | {description}")
                violations.append({
                    "track_id":       track_id,
                    "vehicle_bbox":   [int(v) for v in bbox],
                    "vehicle_label":  label,
                    "violation_type": violation_type,
                    "speed_score":    round(motion["speed_spike_ratio"], 2),
                    "description":    description,
                })

        return violations


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

        # Rule C — rash driving / hit-and-run detection (needs track_id from ByteTrack)
        violations: List[Dict[str, Any]] = []
        if vehicles:
            violations = self._evaluate_violations(vehicles, pedestrians, timestamp_sec)

        # Rule B — plate OCR: now only triggered for vehicles Rule C just flagged,
        # instead of scanning every vehicle every frame.
        plates: List[Dict[str, Any]] = []
        if self.ocr_enabled and image is not None and vehicles and violations:
            triggered_map = {v["track_id"]: v["violation_type"] for v in violations}
            plates = self._extract_plates(image, vehicles, timestamp_sec, triggered_map=triggered_map)

        return {
            "frame_id":           frame_id,
            "timestamp_sec":      timestamp_sec,
            "pedestrian_count":   pedestrian_count,
            "location":           location_context or {},
            **zone_result,
            "violations":         violations,
            "plates":             plates,
        }