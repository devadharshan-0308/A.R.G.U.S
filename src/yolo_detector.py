import os
import logging
# pyrefly: ignore [missing-import]
import torch
# pyrefly: ignore [missing-import]
from ultralytics import YOLO

logger = logging.getLogger(__name__)

class TrafficYOLODetector:
    """
    YOLOv8 Object Detection Layer:
    - Accurate classification of Pedestrians, Motorcycles/Bikes, Cars, Buses, and Trucks.
    - Runs on NVIDIA RTX GPU for real-time inference speed.
    - Preserves native aspect ratio to prevent misclassifying motorcycles as cars.
    """

    # Class ID mapping from standard COCO dataset
    PEDESTRIAN_CLASSES = {
        0: "pedestrian"
    }
    
    VEHICLE_CLASSES = {
        1: "bicycle",
        2: "car",
        3: "motorcycle",
        5: "bus",
        7: "truck"
    }

    def __init__(self, model_path="models/yolov8s.pt", conf_threshold=0.35):
        self.conf_threshold = conf_threshold
        
        # Check for CUDA availability
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        device_name = torch.cuda.get_device_name(0) if self.device == "cuda" else "CPU"
        logger.info(f"Initializing YOLOv8 on device: '{self.device}' ({device_name})")

        # Ensure model directory exists
        dir_name = os.path.dirname(model_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

        # Smart Model Loader: Prefer TensorRT engine, fall back to PyTorch .pt if missing
        if model_path.endswith(".engine") and not os.path.exists(model_path):
            pt_path = model_path.replace(".engine", ".pt")
            logger.warning(f"TensorRT engine '{model_path}' not found on disk. Falling back to PyTorch model: '{pt_path}'")
            model_path = pt_path

        try:
            self.model = YOLO(model_path)
        except Exception as e:
            pt_fallback = "models/yolov8s.pt"
            logger.warning(f"Failed to load '{model_path}' ({e}). Falling back to '{pt_fallback}'")
            self.model = YOLO(pt_fallback)
        
        # Target classes: person, bicycle, car, motorcycle, bus, truck
        self.target_class_ids = list(self.PEDESTRIAN_CLASSES.keys()) + list(self.VEHICLE_CLASSES.keys())

    def detect(self, frame_packet):
        """
        Takes a frame_packet from the Ingestion Layer,
        runs YOLO inference on GPU with aspect ratio preserved, and returns structured detection results.
        """
        image = frame_packet["image"]

        # Run inference (YOLO internally handles letterboxing/padding to maintain true proportions)
        results = self.model.predict(
            source=image,
            classes=self.target_class_ids,
            conf=self.conf_threshold,
            device=self.device,
            imgsz=640,
            verbose=False
        )[0]

        pedestrians = []
        vehicles = []
        breakdown = {
            "motorcycle": 0,
            "bicycle": 0,
            "car": 0,
            "bus": 0,
            "truck": 0
        }

        # Iterate over all detected bounding boxes
        for box in results.boxes:
            cls_id = int(box.cls[0].item())
            confidence = float(box.conf[0].item())
            xyxy = box.xyxy[0].tolist()

            detection_info = {
                "bbox": [round(coord, 1) for coord in xyxy],
                "confidence": round(confidence, 3),
                "class_id": cls_id
            }

            # Categorize into Pedestrians vs Vehicles
            if cls_id in self.PEDESTRIAN_CLASSES:
                label = self.PEDESTRIAN_CLASSES[cls_id]
                detection_info["label"] = label
                pedestrians.append(detection_info)
            elif cls_id in self.VEHICLE_CLASSES:
                label = self.VEHICLE_CLASSES[cls_id]
                detection_info["label"] = label
                vehicles.append(detection_info)
                if label in breakdown:
                    breakdown[label] += 1

        output_event = {
            "frame_id": frame_packet["frame_id"],
            "raw_frame_id": frame_packet["raw_frame_id"],
            "timestamp_sec": frame_packet["timestamp_sec"],
            "counts": {
                "pedestrians": len(pedestrians),
                "vehicles": len(vehicles),
                "breakdown": breakdown
            },
            "detections": {
                "pedestrians": pedestrians,
                "vehicles": vehicles
            },
            "annotated_frame": results.plot()
        }

        return output_event
