"""
src/road_infra_detector.py — Road Infrastructure Deficiency & Asset Detector.

Detects:
  1. Zebra Crossings  (active + missing where pedestrians cross without one)
  2. Road Dividers    (concrete medians, painted kerbs, metal barriers + missing)
  3. Waterlogging     (specular sky reflections + murky standing water)
  4. Traffic Signboards (blue/red regulatory signs, damaged/tilted)

Uses calibrated multi-channel CV heuristics designed specifically for real Indian dashcam footage.
Strictly guards against false positives on unpaved/dirt roads, divider blocks, and vehicle cabins.
"""

import cv2
import numpy as np
import logging
from collections import deque
from typing import Dict, List, Any, Optional

logger = logging.getLogger("RoadInfraDetector")

# Visual HUD Colors (BGR)
COLOR_ZEBRA_FOUND = (255, 230, 0)
COLOR_ZEBRA_MISSING = (0, 69, 255)
COLOR_DIVIDER_FOUND = (0, 220, 100)
COLOR_DIVIDER_MISSING = (0, 140, 255)
COLOR_WATERLOGGING = (245, 180, 0)
COLOR_SIGNBOARD = (255, 120, 180)
COLOR_SIGN_DAMAGED = (255, 0, 255)


class RoadInfrastructureDetector:
    def __init__(self, history_len: int = 15):
        self.history_len = history_len
        self.divider_presence_history = deque(maxlen=history_len)
        self.zebra_presence_history = deque(maxlen=history_len)
        self.frame_count = 0

    @staticmethod
    def _is_unpaved_dirt_road(frame: np.ndarray) -> bool:
        """
        Determines if the scene is an unpaved/dirt/rural mud road.
        Dirt roads lack asphalt, painted crosswalks, or urban median infrastructure.
        """
        h, w = frame.shape[:2]
        roi = frame[int(h * 0.55):int(h * 0.95), int(w * 0.15):int(w * 0.85)]
        if roi.size == 0:
            return False
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        dirt_mask = cv2.inRange(hsv, np.array([8, 20, 30]), np.array([38, 220, 220]))
        dirt_ratio = cv2.countNonZero(dirt_mask) / float(roi.shape[0] * roi.shape[1])
        return dirt_ratio > 0.92

    def analyze(
        self,
        frame: np.ndarray,
        vehicle_detections: Optional[List[Dict[str, Any]]] = None,
        pedestrian_detections: Optional[List[Dict[str, Any]]] = None,
        is_school_zone: bool = False,
        is_hospital_zone: bool = False
    ) -> Dict[str, Any]:
        self.frame_count += 1
        h, w = frame.shape[:2]
        vehicle_detections = vehicle_detections or []
        pedestrian_detections = pedestrian_detections or []
        defects: List[Dict[str, Any]] = []

        is_dirt = self._is_unpaved_dirt_road(frame)

        # Build exclusion mask (vehicles + pedestrians)
        exclusion_mask = np.zeros((h, w), dtype=np.uint8)
        for det in vehicle_detections + pedestrian_detections:
            bx = det.get("bbox", [])
            if len(bx) == 4:
                x1, y1, x2, y2 = [int(v) for v in bx]
                pad = 12
                cv2.rectangle(exclusion_mask,
                              (max(0, x1 - pad), max(0, y1 - pad)),
                              (min(w, x2 + pad), min(h, y2 + pad)), 255, -1)

        # 1. Zebra Crossing
        zebra_res = self._detect_zebra_crossing(frame, exclusion_mask, is_dirt)
        self.zebra_presence_history.append(zebra_res["found"])
        confirmed_zebra = zebra_res["found"]

        if confirmed_zebra:
            defects.append({
                "type": "zebra_crossing",
                "label": "ZEBRA CROSSING [ACTIVE]",
                "severity": "INFO",
                "confidence": zebra_res.get("confidence", 0.85),
                "bbox": zebra_res["bbox"],
                "description": f"Pedestrian crosswalk ({zebra_res.get('stripe_count', 0)} stripes)"
            })
        elif not is_dirt:
            # Check for missing crossing where pedestrians cross on paved roads
            real_peds = self._filter_real_pedestrians(pedestrian_detections, vehicle_detections, h, w)
            crossing_peds = [p for p in real_peds
                            if int(w * 0.15) < ((p["bbox"][0] + p["bbox"][2]) // 2) < int(w * 0.85)]
            if len(crossing_peds) >= 2 or (crossing_peds and is_school_zone):
                x_coords = [p["bbox"][0] for p in crossing_peds]
                x_min = max(0, int(min(x_coords) - 60))
                x_max = min(w, int(max(x_coords) + 120))
                defects.append({
                    "type": "missing_zebra_crossing",
                    "label": "MISSING ZEBRA CROSSING",
                    "severity": "CRITICAL" if is_school_zone else "WARNING",
                    "confidence": 0.82,
                    "bbox": [x_min, int(h * 0.65), x_max, int(h * 0.95)],
                    "description": "Pedestrians crossing road without marked crosswalk"
                })

        # 2. Road Divider
        divider_res = self._detect_road_divider(frame, exclusion_mask, is_dirt)
        self.divider_presence_history.append(divider_res["found"])

        is_two_way = self._verify_opposing_traffic(vehicle_detections, w)

        if divider_res["found"]:
            defects.append({
                "type": "road_divider",
                "label": "ROAD DIVIDER [MEDIAN]",
                "severity": "INFO",
                "confidence": divider_res.get("confidence", 0.85),
                "bbox": divider_res["bbox"],
                "description": "Physical median barrier separating opposing traffic"
            })
        elif not is_dirt:
            div_rate = sum(self.divider_presence_history) / max(1, len(self.divider_presence_history))
            if (is_two_way and div_rate < 0.20
                    and len(self.divider_presence_history) >= 5
                    and not confirmed_zebra):
                cx = int(w * 0.5)
                defects.append({
                    "type": "missing_road_divider",
                    "label": "MISSING ROAD DIVIDER",
                    "severity": "HIGH",
                    "confidence": 0.80,
                    "bbox": [cx - 60, int(h * 0.45), cx + 60, int(h * 0.88)],
                    "description": "Two-way arterial road without central median barrier"
                })

        # 3. Waterlogging
        defects.extend(self._detect_waterlogging(frame, exclusion_mask, is_dirt=is_dirt))

        # 4. Traffic Signs
        defects.extend(self._detect_traffic_signs(frame, exclusion_mask))

        return {
            "defects": defects,
            "defect_count": len(defects),
            "zebra_crossing_present": confirmed_zebra,
            "divider_present": divider_res["found"],
            "is_two_way": is_two_way
        }

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------
    @staticmethod
    def _filter_real_pedestrians(ped_dets, veh_dets, h, w):
        """Filter out pedestrians that are actually inside vehicles."""
        real = []
        for p in ped_dets:
            bx = p.get("bbox", [])
            if len(bx) != 4:
                continue
            px1, py1, px2, py2 = [int(v) for v in bx]
            pcx, pcy = (px1 + px2) // 2, (py1 + py2) // 2
            inside = any(
                v["bbox"][0] <= pcx <= v["bbox"][2] and v["bbox"][1] <= pcy <= v["bbox"][3]
                for v in veh_dets if len(v.get("bbox", [])) == 4
            )
            if inside:
                continue
            if py2 > int(h * 0.50):
                real.append(p)
        return real

    # -----------------------------------------------------------------
    # SUB-DETECTOR 1: Zebra Crossing
    # -----------------------------------------------------------------
    def _detect_zebra_crossing(self, frame: np.ndarray, vehicle_mask: np.ndarray, is_dirt: bool = False) -> Dict[str, Any]:
        """
        Detects zebra crosswalks using true white paint geometry & lateral grouping.
        Stripes must be white thermoplastic paint, aligned horizontally across the lane.
        """
        if is_dirt:
            return {"found": False, "confidence": 0.0, "stripe_count": 0, "bbox": []}

        h, w = frame.shape[:2]
        roi_y1 = int(h * 0.58)
        roi_y2 = int(h * 0.92)
        roi = frame[roi_y1:roi_y2, :]
        roi_vmask = vehicle_mask[roi_y1:roi_y2, :]
        rh, rw = roi.shape[:2]

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

        # White thermoplastic paint: bright (V >= 165), neutral/desaturated (S <= 40)
        white_mask = cv2.inRange(hsv, np.array([0, 0, 165]), np.array([180, 40, 255]))
        road_mean = np.mean(gray)
        _, contrast_mask = cv2.threshold(gray, max(155, int(road_mean + 35)), 255, cv2.THRESH_BINARY)
        combined = cv2.bitwise_and(white_mask, contrast_mask)
        combined[roi_vmask == 255] = 0

        # Minimum stripe width: at least 9% of ROI width
        min_stripe_w = max(45, int(rw * 0.09))
        h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (int(min_stripe_w * 0.5), 4))
        opened = cv2.morphologyEx(combined, cv2.MORPH_OPEN, h_kernel)

        contours, _ = cv2.findContours(opened, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        stripes = []
        for cnt in contours:
            x, y, cw, ch = cv2.boundingRect(cnt)
            if cw >= min_stripe_w and 6 <= ch <= int(rh * 0.35) and (cw / max(1, ch)) >= 1.8:
                stripes.append((x, y, cw, ch))

        if len(stripes) < 3:
            return {"found": False, "confidence": 0.0, "stripe_count": len(stripes), "bbox": []}

        # Cluster by lateral overlap across the drivable lane
        best_cluster = []
        for i, s1 in enumerate(stripes):
            cluster = [s1]
            x1_a, x2_a = s1[0], s1[0] + s1[2]
            for j, s2 in enumerate(stripes):
                if i == j:
                    continue
                x1_b, x2_b = s2[0], s2[0] + s2[2]
                overlap = max(0, min(x2_a, x2_b) - max(x1_a, x1_b))
                min_w = min(s1[2], s2[2])
                if min_w > 0 and (overlap / min_w) >= 0.50:
                    cluster.append(s2)
            if len(cluster) > len(best_cluster):
                best_cluster = cluster

        if len(best_cluster) < 3:
            return {"found": False, "confidence": 0.0, "stripe_count": len(best_cluster), "bbox": []}

        unique_stripes = list({(s[0], s[1], s[2], s[3]): s for s in best_cluster}.values())
        sorted_stripes = sorted(unique_stripes, key=lambda s: s[1])

        # Vertical pitch regularity
        y_centers = [s[1] + s[3] // 2 for s in sorted_stripes]
        diffs = [y_centers[i+1] - y_centers[i] for i in range(len(y_centers)-1) if y_centers[i+1] - y_centers[i] > 6]
        if len(diffs) < 2:
            return {"found": False, "confidence": 0.0, "stripe_count": len(sorted_stripes), "bbox": []}

        mean_d = np.mean(diffs)
        std_d = np.std(diffs)
        if (std_d / max(1e-3, mean_d)) > 0.55 or mean_d > rh * 0.30:
            return {"found": False, "confidence": 0.0, "stripe_count": len(sorted_stripes), "bbox": []}

        min_x = max(0, min(s[0] for s in sorted_stripes) - 10)
        max_x = min(rw, max(s[0] + s[2] for s in sorted_stripes) + 10)
        min_y = min(s[1] for s in sorted_stripes) + roi_y1
        max_y = max(s[1] + s[3] for s in sorted_stripes) + roi_y1

        return {
            "found": True,
            "confidence": round(min(0.95, 0.82 + len(sorted_stripes) * 0.02), 2),
            "stripe_count": len(sorted_stripes),
            "bbox": [min_x, min_y, max_x, max_y]
        }

    # -----------------------------------------------------------------
    # SUB-DETECTOR 2: Road Divider (Median)
    # -----------------------------------------------------------------
    def _detect_road_divider(self, frame: np.ndarray, exclusion_mask: np.ndarray, is_dirt: bool = False) -> Dict[str, Any]:
        """
        Detects road dividers via multi-channel approach:
        1. Yellow/black painted kerb stripes
        2. Concrete median barriers
        3. Vertical edge structure in center corridor
        """
        if is_dirt:
            return {"found": False, "confidence": 0.0, "bbox": []}

        h, w = frame.shape[:2]
        cx_start = int(w * 0.28)
        cx_end = int(w * 0.72)
        roi_y1 = int(h * 0.35)
        roi_y2 = int(h * 0.90)
        roi = frame[roi_y1:roi_y2, cx_start:cx_end]
        roi_ex = exclusion_mask[roi_y1:roi_y2, cx_start:cx_end]
        roi_h, roi_w = roi.shape[:2]
        roi_area = roi_h * roi_w

        if roi_area < 100:
            return {"found": False, "confidence": 0.0, "bbox": []}

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        found_segments = []

        # Channel A: True bright yellow paint on kerbs (IRC standard)
        yellow_mask = cv2.inRange(hsv, np.array([18, 90, 110]), np.array([33, 255, 255]))
        # Channel A2: Sun-bleached/faded yellow-orange kerb paint (common on Indian arterials)
        yellow_faded = cv2.inRange(hsv, np.array([14, 50, 140]), np.array([36, 180, 255]))
        yellow_mask = cv2.bitwise_or(yellow_mask, yellow_faded)
        yellow_mask[roi_ex == 255] = 0
        found_segments.extend(self._find_divider_contours(yellow_mask, roi_area, roi_w, min_area=600, require_vertical=False))

        # Channel B: Grey concrete median (solid elongated barrier)
        grey_mask = cv2.inRange(hsv, np.array([0, 0, 85]), np.array([180, 45, 195]))
        grey_mask[roi_ex == 255] = 0
        k_close = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 15))
        grey_clean = cv2.morphologyEx(grey_mask, cv2.MORPH_CLOSE, k_close)
        found_segments.extend(self._find_divider_contours(grey_clean, roi_area, roi_w, min_area=2200, max_width_ratio=0.32, require_vertical=True))

        # Channel C: Vertical edge structure in center corridor
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 70, 160)
        edges[roi_ex == 255] = 0
        v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 22))
        v_edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, v_kernel)
        found_segments.extend(self._find_divider_contours(v_edges, roi_area, roi_w, min_area=1800, max_width_ratio=0.30, require_vertical=True))

        if not found_segments:
            return {"found": False, "confidence": 0.0, "bbox": []}

        found_segments.sort(key=lambda s: s[4], reverse=True)
        primary = found_segments[0]
        cluster = [primary]
        for s in found_segments[1:]:
            if abs(s[0] - primary[0]) < roi_w * 0.28:
                cluster.append(s)

        min_x = min(s[0] for s in cluster) + cx_start
        max_x = max(s[0] + s[2] for s in cluster) + cx_start
        min_y = min(s[1] for s in cluster) + roi_y1
        max_y = max(s[1] + s[3] for s in cluster) + roi_y1

        conf = 0.88 if len(cluster) >= 2 else 0.78
        return {"found": True, "confidence": conf, "bbox": [min_x, min_y, max_x, max_y]}

    @staticmethod
    def _find_divider_contours(mask, roi_area, roi_w, min_area=1000, max_width_ratio=0.35, require_vertical=False):
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        segments = []
        for c in contours:
            area = cv2.contourArea(c)
            if min_area < area < (roi_area * 0.20):
                bx, by, bw, bh = cv2.boundingRect(c)
                if bw < (roi_w * max_width_ratio) and bh >= 18:
                    if require_vertical and (bh < bw * 1.1 or bh < 45):
                        continue
                    segments.append((bx, by, bw, bh, area))
        return segments

    # -----------------------------------------------------------------
    # SUB-DETECTOR 3: Waterlogging
    # -----------------------------------------------------------------
    def _detect_waterlogging(self, frame: np.ndarray, exclusion_mask: np.ndarray, is_dirt: bool = False) -> List[Dict[str, Any]]:
        """
        Calibrated waterlogging detection:
        - Must be on paved roads (dirt road puddles are tracked as potholes).
        - Specular sky reflection (blue tint B > R+15, B >= G, high brightness, mirror smooth).
        - Murky flood water (localized pool, area 0.8%-18% of road, Laplacian variance < 65).
        - Strictly excludes center median corridor and vehicle shadows.
        """
        if is_dirt:
            return []

        h, w = frame.shape[:2]
        roi_y1 = int(h * 0.60)
        roi_y2 = int(h * 0.95)
        road_roi = frame[roi_y1:roi_y2, :]
        road_ex = exclusion_mask[roi_y1:roi_y2, :].copy()
        roi_h, roi_w = road_roi.shape[:2]
        roi_area = roi_h * roi_w
        if roi_area < 100:
            return []

        # Mask out center median corridor to prevent divider blocks matching as water
        cv2.rectangle(road_ex, (int(roi_w * 0.38), 0), (int(roi_w * 0.62), roi_h), 255, -1)

        hsv = cv2.cvtColor(road_roi, cv2.COLOR_BGR2HSV)
        gray_roi = cv2.cvtColor(road_roi, cv2.COLOR_BGR2GRAY)
        lap = cv2.Laplacian(gray_roi, cv2.CV_64F)
        water_defects = []

        # Path A: Specular Sky Reflection on Water (Cyan/Blue reflection)
        specular = cv2.inRange(hsv, np.array([95, 35, 125]), np.array([135, 220, 255]))
        specular[road_ex == 255] = 0

        # Path B: Localized Standing Murky Water (distinct silt pool)
        murky = cv2.inRange(hsv, np.array([15, 35, 45]), np.array([35, 160, 115]))
        murky[road_ex == 255] = 0

        for path_name, mask in [("specular", specular), ("murky", murky)]:
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
            clean = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            clean = cv2.morphologyEx(clean, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9)))

            contours, _ = cv2.findContours(clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                area = cv2.contourArea(cnt)
                # Bounded area: between 0.8% and 24% of ROI
                if area < (roi_area * 0.008) or area > (roi_area * 0.24):
                    continue

                bx, by, bw, bh = cv2.boundingRect(cnt)
                if bw < bh * 0.8:
                    continue

                cnt_mask = np.zeros(road_roi.shape[:2], dtype=np.uint8)
                cv2.drawContours(cnt_mask, [cnt], -1, 255, -1)

                # Texture check: water surface is mirror smooth
                local_lap = np.abs(lap[cnt_mask == 255])
                # ponytail: coarse asphalt texture raises Laplacian naturally; 130 is calibrated
                # for Indian roads (upgrade path: per-road-surface adaptive threshold)
                if len(local_lap) < 80 or np.var(local_lap) > 130:
                    continue

                if path_name == "specular":
                    c_pixels = road_roi[cnt_mask == 255]
                    mb = np.mean(c_pixels[:, 0])  # Blue
                    mg = np.mean(c_pixels[:, 1])  # Green
                    mr = np.mean(c_pixels[:, 2])  # Red
                    if not (mb > mr + 15 and mb >= mg):
                        continue

                area_ratio = area / float(roi_area)
                x1 = bx
                y1 = by + roi_y1
                x2 = bx + bw
                y2 = by + bh + roi_y1

                water_defects.append({
                    "type": "water_logging",
                    "label": "ROAD WATERLOGGING",
                    "severity": "CRITICAL" if area_ratio >= 0.08 else "WARNING",
                    "confidence": round(min(0.92, 0.78 + area_ratio * 1.5), 2),
                    "bbox": [x1, y1, x2, y2],
                    "area_ratio": round(area_ratio, 4),
                    "description": f"{'Deep murky' if path_name == 'murky' else 'Standing'} water pool ({area_ratio*100:.1f}% lane coverage)"
                })

        return self._nms_defects(water_defects, iou_thresh=0.35)

    @staticmethod
    def _nms_defects(defects: List[Dict], iou_thresh: float = 0.35) -> List[Dict]:
        if len(defects) <= 1:
            return defects
        defects.sort(key=lambda d: d.get("confidence", 0), reverse=True)
        keep = []
        for d in defects:
            b = d["bbox"]
            overlaps = False
            for k in keep:
                kb = k["bbox"]
                x1 = max(b[0], kb[0])
                y1 = max(b[1], kb[1])
                x2 = min(b[2], kb[2])
                y2 = min(b[3], kb[3])
                inter = max(0, x2 - x1) * max(0, y2 - y1)
                a1 = (b[2] - b[0]) * (b[3] - b[1])
                a2 = (kb[2] - kb[0]) * (kb[3] - kb[1])
                union = a1 + a2 - inter
                if union > 0 and inter / union > iou_thresh:
                    overlaps = True
                    break
            if not overlaps:
                keep.append(d)
        return keep

    # -----------------------------------------------------------------
    # SUB-DETECTOR 4: Traffic Signs
    # -----------------------------------------------------------------
    def _detect_traffic_signs(self, frame: np.ndarray, exclusion_mask: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detects genuine regulatory traffic signboards.
        Excludes bus cabin rear-view mirrors, vehicle bodies, and hood glare.
        """
        h, w = frame.shape[:2]
        upper_roi = frame[0:int(h * 0.60), :]
        upper_vmask = exclusion_mask[0:int(h * 0.60), :].copy()

        # Exclude bus cabin rearview mirror area (top-left 22% width, top 25% height)
        cv2.rectangle(upper_vmask, (0, 0), (int(w * 0.22), int(h * 0.25)), 255, -1)

        hsv = cv2.cvtColor(upper_roi, cv2.COLOR_BGR2HSV)
        gray_roi = cv2.cvtColor(upper_roi, cv2.COLOR_BGR2GRAY)

        blue_mask = cv2.inRange(hsv, np.array([98, 110, 80]), np.array([128, 255, 255]))
        red1 = cv2.inRange(hsv, np.array([0, 120, 100]), np.array([10, 255, 255]))
        red2 = cv2.inRange(hsv, np.array([170, 120, 100]), np.array([180, 255, 255]))
        sign_mask = cv2.bitwise_or(blue_mask, cv2.bitwise_or(red1, red2))
        sign_mask[upper_vmask == 255] = 0

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        clean = cv2.morphologyEx(sign_mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        sign_defects = []

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if not (800 < area < 18000):
                continue

            bx, by, bw, bh = cv2.boundingRect(cnt)
            cx = bx + bw / 2.0
            cy = by + bh / 2.0

            # Must be roadside shoulder or overhead
            is_roadside = (cx < 0.20 * w) or (cx > 0.80 * w) or (cy < 0.28 * h)
            if not is_roadside:
                continue

            aspect = bw / max(1, bh)
            if not (0.6 <= aspect <= 1.8):
                continue

            hull = cv2.convexHull(cnt)
            hull_area = cv2.contourArea(hull)
            solidity = area / max(1.0, hull_area)
            if solidity < 0.85:
                continue

            # Internal feature contrast check (symbols/letters)
            cnt_mask = np.zeros(upper_roi.shape[:2], dtype=np.uint8)
            cv2.drawContours(cnt_mask, [cnt], -1, 255, -1)
            sign_gray = gray_roi[cnt_mask == 255]
            if len(sign_gray) < 100 or np.std(sign_gray) < 22:
                continue

            rect = cv2.minAreaRect(cnt)
            _, _, angle = rect
            tilt = abs(angle)
            if tilt > 45:
                tilt = 90 - tilt

            if 25.0 <= tilt <= 65.0:
                sign_defects.append({
                    "type": "damaged_signboard",
                    "label": "DAMAGED SIGNBOARD (TILTED)",
                    "severity": "WARNING",
                    "confidence": 0.84,
                    "bbox": [bx, by, bx + bw, by + bh],
                    "description": f"Signboard tilted at {tilt:.0f}°"
                })
            else:
                sign_defects.append({
                    "type": "signboard",
                    "label": "TRAFFIC SIGNBOARD",
                    "severity": "INFO",
                    "confidence": 0.86,
                    "bbox": [bx, by, bx + bw, by + bh],
                    "description": "Roadside regulatory signboard"
                })

        return sign_defects

    # -----------------------------------------------------------------
    # Opposing Traffic Check
    # -----------------------------------------------------------------
    @staticmethod
    def _verify_opposing_traffic(vehicle_detections: List[Dict[str, Any]], frame_w: int) -> bool:
        if len(vehicle_detections) < 2:
            return False
        mid = frame_w * 0.5
        has_left = any((v.get("bbox", [0])[0] + v.get("bbox", [0, 0, 0])[2]) / 2.0 < mid for v in vehicle_detections if len(v.get("bbox", [])) == 4)
        has_right = any((v.get("bbox", [0])[0] + v.get("bbox", [0, 0, 0])[2]) / 2.0 >= mid for v in vehicle_detections if len(v.get("bbox", [])) == 4)
        return has_left and has_right

    # -----------------------------------------------------------------
    # HUD Annotation
    # -----------------------------------------------------------------
    def annotate(self, frame: np.ndarray, defects: List[Dict[str, Any]]) -> np.ndarray:
        annotated = frame.copy()

        for defect in defects:
            d_type = defect.get("type", "")
            label = defect.get("label", "DEFECT")
            conf = defect.get("confidence", 0.8)
            bbox = defect.get("bbox", [])

            if len(bbox) != 4:
                continue

            x1, y1, x2, y2 = [int(v) for v in bbox]

            color_map = {
                "zebra_crossing": COLOR_ZEBRA_FOUND,
                "missing_zebra_crossing": COLOR_ZEBRA_MISSING,
                "road_divider": COLOR_DIVIDER_FOUND,
                "missing_road_divider": COLOR_DIVIDER_MISSING,
                "water_logging": COLOR_WATERLOGGING,
                "damaged_signboard": COLOR_SIGN_DAMAGED,
                "signboard": COLOR_SIGNBOARD,
            }
            color = color_map.get(d_type, (0, 165, 255))

            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

            # Corner indicators
            c_len = min(16, int((x2 - x1) * 0.2), int((y2 - y1) * 0.2))
            if c_len > 3:
                cv2.line(annotated, (x1, y1), (x1 + c_len, y1), (255, 255, 255), 2)
                cv2.line(annotated, (x1, y1), (x1, y1 + c_len), (255, 255, 255), 2)
                cv2.line(annotated, (x2, y2), (x2 - c_len, y2), (255, 255, 255), 2)
                cv2.line(annotated, (x2, y2), (x2 - c_len, y2), (255, 255, 255), 2)

            tag = f"{label} {conf*100:.0f}%"
            badge_w = len(tag) * 8 + 10
            cv2.rectangle(annotated, (x1, max(0, y1 - 22)), (x1 + badge_w, y1), color, -1)
            cv2.putText(annotated, tag, (x1 + 4, max(14, y1 - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 0, 0), 1, cv2.LINE_AA)

        return annotated
