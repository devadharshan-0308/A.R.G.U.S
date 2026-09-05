import math
import logging
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)

# Severity hierarchy for prioritizing highest severity when merging
SEVERITY_RANKS = {
    "severe pothole": 3,
    "mild pothole": 2,
    "shallow pothole": 1,
    "pothole": 1
}

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculates the great-circle distance between two points on the Earth
    specified in decimal degrees (latitude/longitude) using the Haversine formula.

    Returns:
        Distance in meters.
    """
    R = 6371000.0  # Earth's radius in meters

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    
    # Avoid float precision issues yielding a > 1
    a = min(1.0, max(0.0, a))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return R * c


class PotholeIncident:
    """
    Represents a unique physical road hazard (pothole, barricade, water logging) identified on a map coordinate.
    """
    def __init__(self, pothole_id: int, lat: float, lon: float, severity: str,
                 confidence: float, timestamp_sec: float, frame_id: int, bbox: Optional[List[float]] = None,
                 hazard_type: str = "pothole"):
        self.pothole_id = pothole_id
        self.hazard_type = hazard_type
        self.latitude = lat
        self.longitude = lon
        self.severity = severity.strip().lower()
        self.highest_confidence = confidence
        self.detection_count = 1
        self.first_seen_sec = timestamp_sec
        self.last_seen_sec = timestamp_sec
        self.first_frame_id = frame_id
        self.last_frame_id = frame_id
        self.last_bbox = bbox or []

    def merge_detection(self, lat: float, lon: float, severity: str,
                        confidence: float, timestamp_sec: float, frame_id: int,
                        bbox: Optional[List[float]] = None):
        """
        Merges a subsequent frame detection of the same physical hazard.
        Updates coordinates with a running weighted average, elevates severity if higher,
        and records timestamps.
        """
        self.detection_count += 1
        self.last_seen_sec = timestamp_sec
        self.last_frame_id = frame_id
        if bbox:
            self.last_bbox = bbox

        # Update coordinate weighted average for pinpoint map accuracy
        n = self.detection_count
        self.latitude = round(((self.latitude * (n - 1)) + lat) / n, 7)
        self.longitude = round(((self.longitude * (n - 1)) + lon) / n, 7)

        # Update highest confidence
        if confidence > self.highest_confidence:
            self.highest_confidence = round(confidence, 3)

        # Promote severity if current detection is more severe
        curr_severity = severity.strip().lower()
        if SEVERITY_RANKS.get(curr_severity, 0) > SEVERITY_RANKS.get(self.severity, 0):
            self.severity = curr_severity

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pothole_id": self.pothole_id,
            "hazard_type": self.hazard_type,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "severity": self.severity,
            "highest_confidence": round(self.highest_confidence, 3),
            "detection_count": self.detection_count,
            "first_seen_sec": self.first_seen_sec,
            "last_seen_sec": self.last_seen_sec,
            "first_frame_id": self.first_frame_id,
            "last_frame_id": self.last_frame_id,
            "last_bbox": self.last_bbox
        }


class SpatialPotholeDeduplicator:
    """
    Deduplicates rapid-fire frame detections of road hazards (potholes, barricades, water logging)
    using Haversine distance threshold.
    Groups detections within the threshold distance (default: 2.5 meters) into a single map incident.
    """
    def __init__(self, distance_threshold_meters: float = 2.5):
        self.distance_threshold = distance_threshold_meters
        self.incidents: List[PotholeIncident] = []
        self._next_id = 1

    def add_or_merge(self, lat: float, lon: float, severity: str,
                     confidence: float, timestamp_sec: float, frame_id: int,
                     bbox: Optional[List[float]] = None,
                     hazard_type: str = "pothole") -> Tuple[PotholeIncident, bool]:
        """
        Check if detection matches an existing hazard of the same type within distance_threshold_meters.
        Returns:
            (incident, is_new): Incident object and boolean indicating whether a new hazard was registered.
        """
        closest_incident: Optional[PotholeIncident] = None
        min_dist = float('inf')

        for inc in self.incidents:
            if getattr(inc, "hazard_type", "pothole") != hazard_type:
                continue
            dist = haversine_distance(lat, lon, inc.latitude, inc.longitude)
            if dist < min_dist:
                min_dist = dist
                closest_incident = inc

        if closest_incident is not None and min_dist <= self.distance_threshold:
            # Merge into existing hazard incident
            closest_incident.merge_detection(
                lat=lat,
                lon=lon,
                severity=severity,
                confidence=confidence,
                timestamp_sec=timestamp_sec,
                frame_id=frame_id,
                bbox=bbox
            )
            return closest_incident, False
        else:
            # Register new unique physical hazard
            new_inc = PotholeIncident(
                pothole_id=self._next_id,
                lat=lat,
                lon=lon,
                severity=severity,
                confidence=confidence,
                timestamp_sec=timestamp_sec,
                frame_id=frame_id,
                bbox=bbox,
                hazard_type=hazard_type
            )
            self._next_id += 1
            self.incidents.append(new_inc)
            logger.info(
                f"[Spatial Dedup] New unique {hazard_type} #{new_inc.pothole_id} ({new_inc.severity}) "
                f"registered at ({lat:.6f}, {lon:.6f}) on frame {frame_id}"
            )
            return new_inc, True

    def get_unique_potholes(self) -> List[Dict[str, Any]]:
        return [inc.to_dict() for inc in self.incidents]

    def get_summary(self) -> Dict[str, Any]:
        """
        Returns a breakdown summary of detected unique potholes.
        """
        breakdown = {"severe pothole": 0, "mild pothole": 0, "shallow pothole": 0, "other": 0}
        for inc in self.incidents:
            sev = inc.severity
            if sev in breakdown:
                breakdown[sev] += 1
            else:
                breakdown["other"] += 1

        return {
            "total_unique_potholes": len(self.incidents),
            "breakdown": breakdown,
            "distance_threshold_meters": self.distance_threshold
        }


SpatialHazardDeduplicator = SpatialPotholeDeduplicator
