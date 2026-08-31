"""
Local YOLOv8 License Plate Detector & OCR Module
────────────────────────────────────────────────
- 100% Local Inference on NVIDIA GPU (RTX 3050).
- Automatically downloads the pre-trained License Plate YOLO model to models/license_plate.pt on first run.
- Pinpoints the EXACT license plate bounding box [x1, y1, x2, y2].
- Applies CLAHE contrast enhancement on the tight plate crop.
- Runs EasyOCR locally on the enhanced crop to extract license plate text.
- Formats & normalizes Indian / international plate numbers.
"""

import os
import re
import cv2
import torch
import shutil
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from typing import Dict, List, Any, Optional, Union

# pyrefly: ignore [missing-import]
from ultralytics import YOLO

logger = logging.getLogger(__name__)

DEFAULT_HF_REPO = "Koushim/yolov8-license-plate-detection"
DEFAULT_HF_FILE = "best.pt"
DEFAULT_LOCAL_MODEL = os.path.join("models", "license_plate.pt")

# Indian plate regex: XX-00-XX-0000 or general alphanumeric
_PLATE_RE = re.compile(
    r"[A-Z]{2}[\s\-]?\d{1,2}[\s\-]?[A-Z]{1,3}[\s\-]?\d{1,4}", re.IGNORECASE
)


def _download_plate_model(local_path: str) -> bool:
    """
    Downloads the pre-trained license plate YOLOv8 model from HuggingFace
    and saves permanently to models/license_plate.pt for offline GPU usage.
    """
    try:
        from huggingface_hub import hf_hub_download
        logger.info(f"Downloading license plate YOLO model from HuggingFace ({DEFAULT_HF_REPO})...")
        cached_path = hf_hub_download(
            repo_id=DEFAULT_HF_REPO,
            filename=DEFAULT_HF_FILE
        )
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        shutil.copy2(cached_path, local_path)
        logger.info(f"License plate model saved to '{local_path}' — runs 100% offline from now on.")
        return True
    except Exception as e:
        logger.error(f"Failed to download license plate model: {e}")
        return False


def _clean_plate_text(raw: str) -> str:
    """
    Cleans and standardizes extracted OCR plate text.
    """
    text = re.sub(r"[^A-Z0-9\s\-]", "", raw.upper()).strip()
    text = re.sub(r"\s+", " ", text)

    m = _PLATE_RE.search(text)
    if m:
        return re.sub(r"[\s\-]+", "-", m.group()).upper()

    compact = re.sub(r"[\s\-]", "", text)
    return compact if len(compact) >= 4 else ""


def _preprocess_plate_crop(crop: np.ndarray) -> np.ndarray:
    """
    Enhances the tight plate crop for OCR:
    3x upscale -> grayscale -> CLAHE contrast boost -> mild unsharp mask.
    """
    if crop.size == 0:
        return crop

    # 3x upscale for small plate regions
    h, w = crop.shape[:2]
    target_h = max(64, h * 3)
    target_w = int(w * (target_h / h))
    crop = cv2.resize(crop, (target_w, target_h), interpolation=cv2.INTER_CUBIC)

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(6, 6))
    enhanced = clahe.apply(gray)

    # Mild sharpening kernel to clarify blurred letter edges
    kernel = np.array([[0, -0.5, 0], [-0.5, 3.0, -0.5], [0, -0.5, 0]], dtype=np.float32)
    sharpened = cv2.filter2D(enhanced, -1, kernel)

    return cv2.cvtColor(sharpened, cv2.COLOR_GRAY2BGR)


class LicensePlateDetector:
    """
    Local GPU License Plate Detector with Asynchronous Multi-threaded OCR.
    """

    def __init__(
        self,
        model_path: str = DEFAULT_LOCAL_MODEL,
        conf_threshold: float = 0.20,
        ocr_enabled: bool = True
    ):
        self.conf_threshold = conf_threshold
        self.ocr_enabled = ocr_enabled
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        device_name = torch.cuda.get_device_name(0) if self.device == "cuda" else "CPU"
        logger.info(f"Initializing LicensePlateDetector on device: '{self.device}' ({device_name})")

        os.makedirs("models", exist_ok=True)

        if not os.path.exists(model_path):
            success = _download_plate_model(model_path)
            if not success:
                logger.error("License plate model could not be loaded. Plate detection disabled.")
                self.model = None
                return
        else:
            logger.info(f"Loading local license plate model from: '{model_path}'")

        try:
            self.model = YOLO(model_path)
        except Exception as e:
            logger.error(f"Failed to load license plate model '{model_path}': {e}")
            self.model = None

        self.reader = None
        self.ocr_pool = None
        self._cache_lock = threading.Lock()
        self._plate_cache: Dict[str, Dict[str, Any]] = {}
        self._in_flight_keys = set()

        if ocr_enabled:
            try:
                import easyocr
                self.reader = easyocr.Reader(["en"], gpu=(self.device == "cuda"), verbose=False)
                # Thread pool for asynchronous non-blocking OCR inference
                self.ocr_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="AsyncOCRWorker")
                logger.info("EasyOCR initialized with Multi-Threaded Async Workers.")
            except Exception as e:
                logger.warning(f"EasyOCR initialization failed ({e}). Plate text extraction disabled.")

    def _async_ocr_worker(self, cache_key: str, enhanced_crop: np.ndarray):
        """
        Background worker that processes EasyOCR without stalling the video feed.
        """
        try:
            ocr_res = self.reader.readtext(enhanced_crop, detail=1)
            if ocr_res:
                texts = [t[1] for t in ocr_res if t[2] >= 0.25]
                confs = [t[2] for t in ocr_res if t[2] >= 0.25]
                if texts:
                    raw_ocr = " ".join(texts)
                    ocr_conf = float(np.mean(confs))
                    cleaned = _clean_plate_text(raw_ocr)

                    with self._cache_lock:
                        self._plate_cache[cache_key] = {
                            "plate_text": cleaned if cleaned else raw_ocr,
                            "raw_ocr": raw_ocr,
                            "ocr_confidence": round(ocr_conf, 3)
                        }
        except Exception as e:
            logger.debug(f"Async OCR error: {e}")
        finally:
            with self._cache_lock:
                self._in_flight_keys.discard(cache_key)

    def _get_spatial_key(self, bbox: List[int]) -> str:
        """
        Groups bounding boxes within ~40px spatial vicinity to reuse recognized plate results.
        """
        cx = (bbox[0] + bbox[2]) // 80
        cy = (bbox[1] + bbox[3]) // 80
        return f"{cx}_{cy}"

    def detect(
        self,
        frame_or_packet: Union[Dict[str, Any], np.ndarray],
        annotate: bool = True
    ) -> Dict[str, Any]:
        """
        Detects license plates and extracts text using async parallel processing.
        """
        if isinstance(frame_or_packet, dict):
            image = frame_or_packet.get("image")
            frame_id = frame_or_packet.get("frame_id", 0)
            timestamp_sec = frame_or_packet.get("timestamp_sec", 0.0)
        else:
            image = frame_or_packet
            frame_id = 0
            timestamp_sec = 0.0

        if image is None or self.model is None:
            return {"frame_id": frame_id, "timestamp_sec": timestamp_sec, "plates": []}

        annotated_frame = image.copy() if annotate else image
        h, w = image.shape[:2]

        results = self.model.predict(
            source=image,
            conf=self.conf_threshold,
            device=self.device,
            imgsz=640,
            verbose=False
        )[0]

        detected_plates = []

        for box in results.boxes:
            conf = float(box.conf[0].item())
            xyxy = box.xyxy[0].tolist()
            x1, y1, x2, y2 = [int(v) for v in xyxy]

            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)

            if (x2 - x1) <= 5 or (y2 - y1) <= 5:
                continue

            cache_key = self._get_spatial_key([x1, y1, x2, y2])
            cached_result = None

            with self._cache_lock:
                cached_result = self._plate_cache.get(cache_key)

            plate_text = cached_result.get("plate_text", "") if cached_result else ""
            raw_ocr = cached_result.get("raw_ocr", "") if cached_result else ""
            ocr_conf = cached_result.get("ocr_confidence", 0.0) if cached_result else 0.0

            # If not in cache and not already in flight, dispatch async OCR task
            if not cached_result and self.ocr_enabled and self.reader is not None and self.ocr_pool is not None:
                plate_crop = image[y1:y2, x1:x2]
                if plate_crop.size > 0:
                    with self._cache_lock:
                        if cache_key not in self._in_flight_keys:
                            self._in_flight_keys.add(cache_key)
                            enhanced_crop = _preprocess_plate_crop(plate_crop)
                            self.ocr_pool.submit(self._async_ocr_worker, cache_key, enhanced_crop)

            plate_info = {
                "bbox": [x1, y1, x2, y2],
                "confidence": round(conf, 3),
                "plate_text": plate_text,
                "raw_ocr": raw_ocr,
                "ocr_confidence": round(ocr_conf, 3)
            }
            detected_plates.append(plate_info)

            if annotate:
                # Draw plate bounding box (Cyan / Yellow)
                cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
                disp_label = plate_text if plate_text else f"Plate: {conf*100:.0f}%"
                cv2.putText(
                    annotated_frame,
                    disp_label,
                    (x1, max(15, y1 - 5)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 255),
                    2
                )

        return {
            "frame_id": frame_id,
            "timestamp_sec": timestamp_sec,
            "plates": detected_plates,
            "annotated_frame": annotated_frame
        }

