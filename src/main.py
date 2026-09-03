import os
import sys
import cv2
import json
import time
import queue
import logging
import threading
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# Ensure project root is in sys.path when running this script directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ingestion import video_frame_generator
from src.yolo_detector import TrafficYOLODetector
from src.hazard_detector import RoadHazardDetector as PotholeDetector
from src.pothole_detector import SEVERITY_COLORS
from src.spatial_dedup import SpatialPotholeDeduplicator
from src.rule_engine import SafetyRuleEngine
from src.plate_detector import LicensePlateDetector
from src.maps_enricher import MapsEnricher
from src.road_infra_detector import RoadInfrastructureDetector
import base64
import requests

def format_label(name, count):
    if name.lower() == "bus":
        return f"Buses: {count}" if count > 1 else f"Bus: {count}"
    return f"{name.title()}s: {count}" if count > 1 else f"{name.title()}: {count}"

class AsyncVideoWriter:
    """
    Threaded non-blocking video writer to prevent disk encoding from stalling GPU inference.
    """
    def __init__(self, output_path, fourcc, fps, frame_size):
        self.writer = cv2.VideoWriter(output_path, fourcc, fps, frame_size)
        self.queue = queue.Queue(maxsize=128)
        self.stopped = False
        self.thread = threading.Thread(target=self._write_loop, daemon=True)
        self.thread.start()

    def _write_loop(self):
        while not self.stopped or not self.queue.empty():
            try:
                frame = self.queue.get(timeout=0.1)
                self.writer.write(frame)
                self.queue.task_done()
            except queue.Empty:
                continue

    def write(self, frame):
        if not self.stopped:
            self.queue.put(frame)

    def release(self):
        self.stopped = True
        if self.thread.is_alive():
            self.thread.join(timeout=5.0)
        self.writer.release()

class AsyncBackendPusher:
    """
    Non-blocking background thread that pushes enriched events to the FastAPI backend.
    If the backend is not running, it silently drops requests without stalling video FPS.
    """
    def __init__(self, endpoint_url="http://localhost:8000/api/events"):
        self.endpoint_url = endpoint_url
        self.queue = queue.Queue(maxsize=256)
        self.stopped = False
        self.thread = threading.Thread(target=self._push_loop, daemon=True)
        self.thread.start()

    def _push_loop(self):
        session = requests.Session()
        while not self.stopped or not self.queue.empty():
            try:
                payload = self.queue.get(timeout=0.1)
                try:
                    session.post(self.endpoint_url, json=payload, timeout=0.5)
                except Exception:
                    pass  # Backend not running or timeout — ignore
                self.queue.task_done()
            except queue.Empty:
                continue

    def push(self, event_type, frame_id, ts, lat, lon, street_name, formatted_addr, is_school, is_hosp, payload, image_crop=None):
        if self.stopped:
            return
        img_b64 = None
        if image_crop is not None and image_crop.size > 0:
            try:
                _, buf = cv2.imencode(".jpg", image_crop, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                img_b64 = base64.b64encode(buf).decode("utf-8")
            except Exception:
                pass

        item = {
            "event_type": event_type,
            "frame_id": frame_id,
            "timestamp_sec": ts,
            "latitude": lat,
            "longitude": lon,
            "street_name": street_name,
            "formatted_address": formatted_addr,
            "is_school_zone": is_school,
            "is_hospital_zone": is_hosp,
            "payload": payload,
            "image_base64": img_b64
        }
        try:
            self.queue.put_nowait(item)
        except queue.Full:
            pass  # Avoid memory buildup if backend is slow

    def stop(self):
        self.stopped = True

def parse_args():
    parser = argparse.ArgumentParser(description="Smart Traffic & Pothole Ingestion Detection Pipeline")
    parser.add_argument("--input", default=os.path.join("data", "input", "demo_traffic.mp4"),
                        help="Path to input video file (default: data/input/demo_traffic.mp4)")
    parser.add_argument("--output", default=os.path.join("data", "output", "output_detected.mp4"),
                        help="Path to save annotated output video (default: data/output/output_detected.mp4)")
    parser.add_argument("--json-output", default=os.path.join("data", "output", "detections.json"),
                        help="Path to save detection JSON log (default: data/output/detections.json)")
    def _best_model(base: str) -> str:
        """Return .engine (if tensorrt available) > .onnx > .pt, whichever exists first."""
        has_trt = False
        try:
            # pyrefly: ignore [missing-import]
            import tensorrt
            has_trt = True
        except ImportError:
            pass

        extensions = (".engine", ".onnx", ".pt") if has_trt else (".onnx", ".pt")
        for ext in extensions:
            p = os.path.join("models", base + ext)
            if os.path.exists(p):
                return p
        return os.path.join("models", base + ".pt")  # fallback (will auto-download)

    parser.add_argument("--model", default=_best_model("yolo11s"),
                        help="Path to YOLO model file (.engine/.onnx/.pt) (default: best available)")
    parser.add_argument("--skip", type=int, default=3,
                        help="Frame skip rate - process 1 every N frames (default: 3)")
    parser.add_argument("--conf", type=float, default=0.25,
                        help="YOLO detection confidence threshold (default: 0.25)")
    parser.add_argument("--res-width", type=int, default=480,
                        help="Output video width resolution (default: 480p)")
    parser.add_argument("--no-preview", action="store_true",
                        help="Disable live OpenCV preview window for faster headless processing")

    # Pothole detection & Spatial Deduplication options
    parser.add_argument("--enable-potholes", action="store_true",
                        help="Enable local GPU pothole detection & severity classification")
    parser.add_argument("--pothole-model", default=_best_model("pothole"),
                        help="Path to local pothole YOLO model (.engine/.onnx/.pt, best available)")
    parser.add_argument("--pothole-conf", type=float, default=0.35,
                        help="Pothole detection confidence threshold (default: 0.35)")
    parser.add_argument("--pothole-dist-thresh", type=float, default=2.5,
                        help="Spatial deduplication distance threshold in meters (default: 2.5m)")
    parser.add_argument("--pothole-every", type=int, default=3,
                        help="Run pothole detection every N frames (default: 3). Reuses last result in between.")

    # Rule Engine & License Plate options
    parser.add_argument("--no-plates", action="store_true",
                        help="Disable local YOLO license plate detector model")
    parser.add_argument("--plate-model", default=_best_model("license_plate"),
                        help="Path to local license plate YOLO model (.engine/.onnx/.pt, best available)")
    parser.add_argument("--plate-conf", type=float, default=0.20,
                        help="License plate detection confidence threshold (default: 0.20)")
    parser.add_argument("--no-ocr", action="store_true",
                        help="Disable EasyOCR text extraction on detected plates")

    # Maps & Backend options
    parser.add_argument("--no-maps", action="store_true",
                        help="Disable Google Maps / OpenStreetMap location enrichment")
    parser.add_argument("--backend-url", default="http://localhost:8000/api/events",
                        help="FastAPI backend events endpoint (default: http://localhost:8000/api/events)")

    return parser.parse_args()

def main(args=None):
    if args is None:
        args = parse_args()

    # 1. Ensure output directories exist
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    os.makedirs(os.path.dirname(args.json_output), exist_ok=True)

    # 2. Initialize Models
    logger.info("--- STEP 1: INITIALIZING AI MODELS ---")
    traffic_detector = TrafficYOLODetector(
        model_name=args.model,
        conf_threshold=args.conf
    )

    pothole_detector = None
    spatial_deduplicator = None

    if args.enable_potholes:
        logger.info("Pothole Detection & Classification: ENABLED (Local GPU)")
        pothole_detector = PotholeDetector(
            model_path=args.pothole_model,
            conf_threshold=args.pothole_conf
        )
        spatial_deduplicator = SpatialPotholeDeduplicator(
            distance_threshold_meters=args.pothole_dist_thresh
        )
    else:
        logger.info("Pothole Detection: DISABLED (use --enable-potholes to activate)")

    # Step 3: Rule Engine & Local License Plate Detector
    ocr_on = not args.no_ocr
    rule_engine = SafetyRuleEngine(ocr_enabled=False)  # Plate detector handles dedicated OCR
    logger.info("Rule Engine: ACTIVE")

    plate_detector = None
    if not args.no_plates:
        logger.info("License Plate Detector: ENABLED (Local GPU YOLO + EasyOCR)")
        plate_detector = LicensePlateDetector(
            model_path=args.plate_model,
            conf_threshold=args.plate_conf,
            ocr_enabled=ocr_on
        )
    else:
        logger.info("License Plate Detector: DISABLED (use --no-plates to toggle)")

    # Step 4: Maps Enricher & Backend Live Streamer
    maps_enricher = None
    if not args.no_maps:
        maps_enricher = MapsEnricher()
    backend_pusher = AsyncBackendPusher(endpoint_url=args.backend_url)
    infra_detector = RoadInfrastructureDetector()

    out_writer = None
    all_detection_logs = []
    start_time = time.time()
    total_processed = 0

    logger.info("--- STEP 2: RUNNING INGESTION PIPELINE ---")

    _last_pothole_event = None
    _pushed_plates_cooldown = {}
    _last_violation_push_ts = -999.0

    try:
        for packet in video_frame_generator(args.input, frame_skip=args.skip):
            total_processed += 1
            loc_info = None

            # 1. Run YOLO Traffic Detection
            traffic_event = traffic_detector.detect(packet)
            annotated_frame = traffic_event["annotated_frame"]
            counts = traffic_event["counts"]
            ts = traffic_event["timestamp_sec"]
            frame_id = traffic_event["frame_id"]
            h, w = annotated_frame.shape[:2]

            pothole_event = None
            potholes_detected = []
            pothole_counts = {"total": 0, "severe pothole": 0, "mild pothole": 0, "shallow pothole": 0}

            # 2. Run Pothole Detection (interleaved — only on every N-th frame, reuse cache in between)
            if pothole_detector is not None:
                if frame_id % args.pothole_every == 0:
                    pothole_event = pothole_detector.detect(packet, annotate=False)
                    _last_pothole_event = pothole_event  # cache for reuse
                elif _last_pothole_event is not None:
                    pothole_event = _last_pothole_event  # free reuse — zero GPU cost

                if pothole_event is not None:
                    potholes_detected = pothole_event.get("detections", [])
                    pothole_counts["total"] = len(potholes_detected)
                    pothole_counts.update(pothole_event.get("breakdown", {}))

                    # GPS coordinate handling:
                    if "latitude" in packet and "longitude" in packet:
                        gps_lat = packet["latitude"]
                        gps_lon = packet["longitude"]
                    else:
                        METERS_PER_FRAME = 0.5
                        LAT_DEG_PER_METER = 1.0 / 111320.0
                        base_lat = 12.971598
                        base_lon = 77.594566
                        gps_lat = base_lat + (packet["raw_frame_id"] * METERS_PER_FRAME * LAT_DEG_PER_METER)
                        gps_lon = base_lon

                    # Maps Geocoding & POI Enrichment (50m cache)
                    loc_info = maps_enricher.enrich_location(gps_lat, gps_lon) if maps_enricher else {}
                    street_name = loc_info.get("street_name", "Main Road")
                    is_school = loc_info.get("is_school_zone", False)
                    is_hosp = loc_info.get("is_hospital_zone", False)

                    for p_det in potholes_detected:
                        p_class = p_det["class"]
                        p_conf = p_det["confidence"]
                        p_bbox = p_det["bbox"]

                        # Spatial Deduplication (Haversine 2.5m)
                        incident, is_new = spatial_deduplicator.add_or_merge(
                            lat=gps_lat,
                            lon=gps_lon,
                            severity=p_class,
                            confidence=p_conf,
                            timestamp_sec=ts,
                            frame_id=frame_id,
                            bbox=p_bbox
                        )
                        p_det["pothole_id"] = incident.pothole_id
                        p_det["is_new_incident"] = is_new

                        # Draw Pothole Bounding Box & Label on Frame
                        x1, y1, x2, y2 = [int(v) for v in p_bbox]
                        color = SEVERITY_COLORS.get(p_class, (0, 0, 255))
                        cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)
                        label_text = f"#{incident.pothole_id} {p_class.title()}: {p_conf * 100:.0f}%"
                        cv2.putText(annotated_frame, label_text, (x1, max(15, y1 - 6)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 2)

                        # If newly discovered incident, crop evidence and push to Backend
                        if is_new:
                            crop = annotated_frame[max(0, y1):min(h, y2), max(0, x1):min(w, x2)]
                            backend_pusher.push(
                                event_type="pothole",
                                frame_id=frame_id,
                                ts=ts,
                                lat=gps_lat,
                                lon=gps_lon,
                                street_name=street_name,
                                formatted_addr=loc_info.get("formatted_address"),
                                is_school=is_school,
                                is_hosp=is_hosp,
                                payload={"severity": p_class, "confidence": p_conf, "pothole_id": incident.pothole_id},
                                image_crop=crop
                            )

            # Location context for frames without potholes
            if loc_info is None:
                if "latitude" in packet and "longitude" in packet:
                    gps_lat, gps_lon = packet["latitude"], packet["longitude"]
                else:
                    gps_lat = 12.971598 + (packet["raw_frame_id"] * 0.5 / 111320.0)
                    gps_lon = 77.594566
                loc_info = maps_enricher.enrich_location(gps_lat, gps_lon) if maps_enricher else {}
                street_name = loc_info.get("street_name", "Main Road")
                is_school = loc_info.get("is_school_zone", False)
                is_hosp = loc_info.get("is_hospital_zone", False)

            # Step 2b: Run Local License Plate Detector & OCR
            detected_plates = []
            if plate_detector is not None:
                plate_event = plate_detector.detect(annotated_frame, annotate=True)
                detected_plates = plate_event.get("plates", [])
                for pl in detected_plates:
                    plate_txt = pl.get("plate_text", "")
                    plate_conf = pl.get("confidence", 0.0)
                    pb = pl.get("bbox", [])
                    p_crop = None
                    if len(pb) == 4:
                        px1, py1, px2, py2 = [int(v) for v in pb]
                        p_crop = annotated_frame[max(0, py1):min(h, py2), max(0, px1):min(w, px2)]
                    
                    # Deduplicate plate pushes: max once per 2.0s per plate text/location
                    plate_cache_key = plate_txt if plate_txt else f"bbox_{int(gps_lat*1000)}_{int(gps_lon*1000)}"
                    last_plate_time = _pushed_plates_cooldown.get(plate_cache_key, -999.0)
                    if (ts - last_plate_time) >= 2.0 and p_crop is not None and p_crop.size > 0:
                        _pushed_plates_cooldown[plate_cache_key] = ts
                        backend_pusher.push(
                            event_type="plate",
                            frame_id=frame_id,
                            ts=ts,
                            lat=gps_lat,
                            lon=gps_lon,
                            street_name=street_name,
                            formatted_addr=loc_info.get("formatted_address"),
                            is_school=is_school,
                            is_hosp=is_hosp,
                            payload={"plate_text": plate_txt, "confidence": plate_conf},
                            image_crop=p_crop
                        )

            # Step 3: Rule Engine evaluation with Geospatial Context
            rule_result = rule_engine.evaluate(traffic_event, image=packet["image"], location_context=loc_info)
            if detected_plates:
                rule_result["plates"] = detected_plates

            # Stream safety violations to backend with cooldown (at most once every 2.5s)
            alert_lvl = rule_result.get("alert_level")
            if alert_lvl in ("HIGH_PRIORITY", "CRITICAL_SCHOOL_ZONE", "HOSPITAL_ZONE_ALERT"):
                if (ts - _last_violation_push_ts) >= 2.5:
                    _last_violation_push_ts = ts
                    # Crop pedestrian region if available
                    v_crop = None
                    peds = traffic_event.get("detections", {}).get("pedestrians", [])
                    if peds and len(peds[0].get("bbox", [])) == 4:
                        vx1, vy1, vx2, vy2 = [int(v) for v in peds[0]["bbox"]]
                        v_crop = annotated_frame[max(0, vy1):min(h, vy2), max(0, vx1):min(w, vx2)]
                    else:
                        # Fallback: center crop of frame
                        v_crop = annotated_frame[int(h*0.2):int(h*0.8), int(w*0.2):int(w*0.8)]

                    backend_pusher.push(
                        event_type="violation",
                        frame_id=frame_id,
                        ts=ts,
                        lat=gps_lat,
                        lon=gps_lon,
                        street_name=street_name,
                        formatted_addr=loc_info.get("formatted_address"),
                        is_school=is_school,
                        is_hosp=is_hosp,
                        payload={
                            "violation_type": alert_lvl,
                            "severity": "CRITICAL" if is_school else "HIGH",
                            "description": rule_result.get("alert_message", ""),
                            "plate_text": detected_plates[0].get("plate_text", "") if detected_plates else ""
                        },
                        image_crop=v_crop
                    )

            # Step 3.5: Road Infrastructure Deficiencies (Dividers, Zebra Crossings, Waterlogging, Signboards)
            infra_res = infra_detector.analyze(
                packet["image"],
                vehicle_detections=traffic_event.get("detections", {}).get("vehicles", []),
                pedestrian_detections=traffic_event.get("detections", {}).get("pedestrians", []),
                is_school_zone=is_school,
                is_hospital_zone=is_hosp
            )
            infra_defects = infra_res.get("defects", [])
            annotated_frame = infra_detector.annotate(annotated_frame, infra_defects)

            # Draw HIGH_PRIORITY banner on annotated frame
            if rule_result["alert_level"] == "HIGH_PRIORITY":
                cv2.rectangle(annotated_frame, (10, 55), (w - 10, 90), (0, 0, 200), -1)
                cv2.putText(annotated_frame, rule_result["alert_message"],
                            (20, 78), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (255, 255, 255), 2)

            # Save detection telemetry
            log_entry = {
                "frame_id": frame_id,
                "timestamp_sec": ts,
                "traffic_counts": counts,
                "pedestrians": traffic_event["detections"]["pedestrians"],
                "vehicles": traffic_event["detections"]["vehicles"],
                "rule_engine": rule_result,
                "infra_defects": infra_defects,
            }

            if pothole_detector is not None:
                log_entry["pothole_counts"] = pothole_counts
                log_entry["potholes"] = potholes_detected

            if detected_plates:
                log_entry["license_plates"] = detected_plates

            all_detection_logs.append(log_entry)

            # Detailed vehicle breakdown string
            bd = counts.get("breakdown", {})
            bd_parts = [format_label(k, v) for k, v in bd.items() if v > 0]
            total_vehs = counts.get("total_vehicles", counts.get("vehicles", 0))
            peds_count = counts.get("pedestrians", 0)
            bd_str = " | ".join(bd_parts) if bd_parts else f"Vehicles: {total_vehs}"

            # Dashboard text overlay
            pothole_hud = ""
            if pothole_detector is not None:
                p_total = pothole_counts["total"]
                pothole_hud = f" | Potholes: {p_total}"
                if p_total > 0:
                    sev_parts = [f"{v} {k.replace(' pothole', '').title()}" for k, v in pothole_counts.items() if k != "total" and v > 0]
                    if sev_parts:
                        pothole_hud += f" ({', '.join(sev_parts)})"

            plate_hud = ""
            if detected_plates:
                plate_labels = [p.get("plate_text") or f"Plate:{p['confidence']*100:.0f}%" for p in detected_plates]
                plate_hud = f" | Plates: {len(detected_plates)} [{', '.join(plate_labels)}]"

            status_text = f"Frame {frame_id:03d} ({ts:4.1f}s) | Pedestrians: {peds_count} | {bd_str}{pothole_hud}{plate_hud}"
            cv2.rectangle(annotated_frame, (10, 10), (w - 10, 50), (20, 20, 20), -1)
            cv2.putText(annotated_frame, status_text, (20, 38), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.50, (0, 255, 255), 2)

            # Downscale output to target resolution
            target_w = args.res_width
            target_h = int(h * (target_w / w))
            output_frame = cv2.resize(annotated_frame, (target_w, target_h), interpolation=cv2.INTER_AREA)

            # Initialize Async Threaded VideoWriter
            if out_writer is None:
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                out_writer = AsyncVideoWriter(args.output, fourcc, 30.0, (target_w, target_h))

            # Push traffic metrics to backend
            backend_pusher.push(
                event_type="metric",
                frame_id=frame_id,
                ts=ts,
                lat=gps_lat,
                lon=gps_lon,
                street_name=street_name,
                formatted_addr=loc_info.get("formatted_address") if loc_info else None,
                is_school=is_school,
                is_hosp=is_hosp,
                payload={
                    "total_vehicles": total_vehs,
                    "pedestrians": peds_count,
                    "cars": bd.get("car", 0),
                    "motorcycles": bd.get("motorcycle", 0),
                    "buses": bd.get("bus", 0),
                    "trucks": bd.get("truck", 0)
                }
            )

            # Log to console if anything detected
            if peds_count > 0 or total_vehs > 0 or (pothole_counts.get("total", 0) > 0) or detected_plates:
                logger.info(f"[Frame {frame_id:04d} | {ts:05.2f}s] Pedestrians: {peds_count} | {bd_str}{pothole_hud}{plate_hud}")

            out_writer.write(output_frame)

            # Live preview
            if not args.no_preview:
                try:
                    cv2.imshow("Smart Traffic & Pothole Pipeline (Press 'q' to stop)", output_frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        logger.info("Interrupted by user.")
                        break
                except Exception:
                    pass  # Headless environment without display

    except FileNotFoundError as e:
        logger.error(str(e))
        logger.error(f"Tip: Place your demo video inside 'data/input/' folder or pass --input <path_to_video>")

    finally:
        if out_writer is not None:
            out_writer.release()
        if not args.no_preview:
            try:
                cv2.destroyAllWindows()
            except Exception:
                pass

        # Save minified detection JSON log
        if all_detection_logs:
            output_data = {
                "frames": all_detection_logs,
                "total_frames_processed": total_processed
            }
            if spatial_deduplicator is not None:
                output_data["unique_potholes"] = spatial_deduplicator.get_unique_potholes()
                output_data["spatial_dedup_summary"] = spatial_deduplicator.get_summary()

            with open(args.json_output, "w") as f:
                json.dump(output_data, f, indent=2)

        # Export Official Municipal PWD Civil Maintenance Work-Orders
        pwd_summary_info = None
        if spatial_deduplicator is not None and spatial_deduplicator.get_unique_potholes():
            try:
                from src.pwd_workorder import generate_pwd_work_orders
                pothole_incidents = [
                    {
                        "type": "POTHOLE",
                        "id": f"POT-{p['id']}",
                        "title": f"{p['severity'].title()}",
                        "severity": "CRITICAL" if "severe" in p['severity'] else ("WARNING" if "mild" in p['severity'] else "INFO"),
                        "gps": f"{p['lat']:.5f}, {p['lon']:.5f}",
                        "lat": p['lat'],
                        "lon": p['lon'],
                        "confidence": f"{p['confidence']*100:.0f}%",
                        "location": "Surveyed Transit Corridor"
                    }
                    for p in spatial_deduplicator.get_unique_potholes()
                ]
                csv_file, pwd_sum = generate_pwd_work_orders(pothole_incidents)
                pwd_summary_info = (csv_file, pwd_sum)
            except Exception as e:
                logger.warning(f"Could not generate PWD work-orders: {e}")

    elapsed = time.time() - start_time
    fps = total_processed / elapsed if elapsed > 0 else 0
    logger.info("")
    logger.info("=" * 50)
    logger.info("           PIPELINE EXECUTION COMPLETE")
    logger.info("=" * 50)
    logger.info(f"Frames Processed : {total_processed}")
    logger.info(f"Time Taken       : {elapsed:.2f} seconds ({fps:.1f} FPS)")
    logger.info(f"Output Video     : {args.output}")
    logger.info(f"Output JSON Log  : {args.json_output}")
    if spatial_deduplicator is not None:
        summary = spatial_deduplicator.get_summary()
        logger.info(f"Unique Potholes  : {summary['total_unique_potholes']} (Threshold: {args.pothole_dist_thresh}m)")
    if pwd_summary_info:
        csv_file, pwd_sum = pwd_summary_info
        logger.info(f"PWD Work-Orders  : {csv_file} ({pwd_sum['total_orders']} orders, Est: INR {pwd_sum['total_budget_inr']:,})")
    logger.info("=" * 50)

if __name__ == "__main__":
    main()
