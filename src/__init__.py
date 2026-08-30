# Smart Traffic Ingestion & Detection Layer
__version__ = "1.0.0"

# Expose key classes
def get_video_frame_generator():
    from .ingestion import video_frame_generator
    return video_frame_generator

def get_yolo_detector():
    from .yolo_detector import TrafficYOLODetector
    return TrafficYOLODetector

def get_pothole_detector():
    from .pothole_detector import PotholeDetector
    return PotholeDetector

def get_spatial_deduplicator():
    from .spatial_dedup import SpatialPotholeDeduplicator
    return SpatialPotholeDeduplicator

def get_rule_engine():
    from .rule_engine import SafetyRuleEngine
    return SafetyRuleEngine

def get_license_plate_detector():
    from .plate_detector import LicensePlateDetector
    return LicensePlateDetector

def get_maps_enricher():
    from .maps_enricher import MapsEnricher
    return MapsEnricher
