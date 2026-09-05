"""
Municipal Public Works Department (PWD) Civil Maintenance Work-Order Generator
─────────────────────────────────────────────────────────────────────────────
Generates official, ready-to-dispatch municipal road repair schedules from
deduplicated computer vision detections. Grounded in Indian Road Congress (IRC)
civil engineering specifications and municipal SLA guidelines.
"""

import csv
import os
import time
from typing import Any, Dict, List, Tuple


PWD_SPEC_CATALOG = {
    "severe pothole": {
        "category": "Road Surface Distress",
        "defect_name": "Severe Pothole (Depth Hazard)",
        "priority": "P1 - CRITICAL",
        "sla": "24 Hours (Immediate)",
        "irc_code": "IRC:82-2015",
        "repair_action": "Cold-milling (50mm depth), tack coat application, and hot-mix asphalt (VG-30) mechanical compaction",
        "material_qty": "2.5 m² (125 kg Bituminous Concrete)",
        "est_cost_inr": 3800
    },
    "mild pothole": {
        "category": "Road Surface Distress",
        "defect_name": "Mild Pothole (Surface Depression)",
        "priority": "P2 - HIGH",
        "sla": "48 Hours",
        "irc_code": "IRC:82-2015",
        "repair_action": "Debris clearance, emulsified tack coat, cold-mix asphalt patch, and vibratory plate compaction",
        "material_qty": "1.2 m² (50 kg Cold Mix Asphalt)",
        "est_cost_inr": 1650
    },
    "shallow pothole": {
        "category": "Road Surface Distress",
        "defect_name": "Shallow Pothole (Surface Raveling)",
        "priority": "P3 - MEDIUM",
        "sla": "7 Days",
        "irc_code": "IRC:SP:81-2008",
        "repair_action": "Bituminous micro-surfacing polymer slurry seal application",
        "material_qty": "0.8 m² Slurry Seal",
        "est_cost_inr": 750
    },
    "missing_road_divider": {
        "category": "Traffic Safety Infrastructure",
        "defect_name": "Missing Central Median Separation",
        "priority": "P1 - CRITICAL",
        "sla": "24 Hours (Immediate Barrier Install)",
        "irc_code": "IRC:119-2015",
        "repair_action": "Install cast-in-place concrete New Jersey median barrier (M30 grade) with retroreflective yellow/black delineators",
        "material_qty": "30 running meters (Precast Concrete Barrier)",
        "est_cost_inr": 48000
    },
    "missing_zebra_crossing": {
        "category": "Pedestrian Safety Infrastructure",
        "defect_name": "Missing Pedestrian Crosswalk (High-Density Zone)",
        "priority": "P1 - CRITICAL",
        "sla": "48 Hours",
        "irc_code": "IRC:35-2015",
        "repair_action": "Apply 2.5mm thermoplastic hot-melt road marking with retroreflective drop-on glass beads (500mm x 3000mm stripes)",
        "material_qty": "8 stripes (24 m² Thermoplastic Compound)",
        "est_cost_inr": 14500
    },
    "water_logging": {
        "category": "Stormwater & Drainage Maintenance",
        "defect_name": "Road Surface Waterlogging / Inadequate Drainage",
        "priority": "P2 - HIGH",
        "sla": "48 Hours (Hydroplaning Risk)",
        "irc_code": "IRC:SP:42-2014",
        "repair_action": "Desilt roadside stormwater catch-basins; re-grade road camber cross-slope (2.5%) towards lateral drainage channel",
        "material_qty": "25 meters roadside drainage clearing",
        "est_cost_inr": 9200
    },
    "damaged_signboard": {
        "category": "Traffic Signage & Delineation",
        "defect_name": "Damaged / Structurally Tilted Traffic Signboard",
        "priority": "P3 - MEDIUM",
        "sla": "5 Days",
        "irc_code": "IRC:67-2012",
        "repair_action": "Re-plumb vertical galvanized steel mounting post, torque foundation anchor bolts (45 Nm), verify retroreflectivity (Type XI)",
        "material_qty": "1 signboard post repair & bracket re-torque",
        "est_cost_inr": 2200
    }
}


def generate_pwd_work_orders(incidents: List[Dict[str, Any]], output_dir: str = "data/output") -> Tuple[str, Dict[str, Any]]:
    """
    Transforms detected incidents into a structured Public Works Department (PWD)
    CSV Work Order schedule. Returns the absolute file path and summary analytics.
    """
    os.makedirs(output_dir, exist_ok=True)
    ts_slug = time.strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.abspath(os.path.join(output_dir, f"PWD_WORK_ORDER_{ts_slug}.csv"))

    rows: List[Dict[str, Any]] = []
    order_idx = 1
    total_budget_inr = 0
    priority_counts = {"P1 - CRITICAL": 0, "P2 - HIGH": 0, "P3 - MEDIUM": 0}

    # Deduplicate incidents by physical ID / type
    seen_ids = set()

    for inc in incidents:
        inc_type = str(inc.get("type", "")).lower()
        title = str(inc.get("title", "")).lower()
        severity = str(inc.get("severity", "")).lower()
        inc_id = inc.get("id", f"INC-{order_idx}")

        if inc_id in seen_ids:
            continue

        # Match with PWD civil engineering spec
        matched_spec = None
        if "pothole" in inc_type or "pothole" in title:
            combined = f"{severity} {title} {inc.get('class', '')} {inc.get('description', '')}".lower()
            if any(k in combined for k in ("severe", "critical", "p1")):
                matched_spec = PWD_SPEC_CATALOG["severe pothole"]
            elif any(k in combined for k in ("mild", "high", "warning", "p2")):
                matched_spec = PWD_SPEC_CATALOG["mild pothole"]
            else:
                matched_spec = PWD_SPEC_CATALOG["shallow pothole"]
        elif "missing_road_divider" in inc_type or "missing road divider" in title:
            matched_spec = PWD_SPEC_CATALOG["missing_road_divider"]
        elif "missing_zebra" in inc_type or "missing zebra" in title:
            matched_spec = PWD_SPEC_CATALOG["missing_zebra_crossing"]
        elif "water" in inc_type or "water" in title:
            matched_spec = PWD_SPEC_CATALOG["water_logging"]
        elif "damaged_sign" in inc_type or "damaged sign" in title or "tilted" in title:
            matched_spec = PWD_SPEC_CATALOG["damaged_signboard"]

        if matched_spec is None:
            continue

        seen_ids.add(inc_id)

        # GPS extraction
        gps = inc.get("gps", "")
        lat, lon = "", ""
        if gps and "," in gps:
            parts = gps.split(",")
            lat, lon = parts[0].strip(), parts[1].strip()
        else:
            lat = str(inc.get("lat", "13.0827"))
            lon = str(inc.get("lon", "80.2707"))

        wo_number = f"PWD-CHN-{time.strftime('%Y')}-{order_idx:04d}"
        prio = matched_spec["priority"]
        cost = matched_spec["est_cost_inr"]

        total_budget_inr += cost
        priority_counts[prio] = priority_counts.get(prio, 0) + 1

        rows.append({
            "Work Order No": wo_number,
            "Date Logged": inc.get("timestamp", time.strftime("%H:%M:%S")),
            "Defect Category": matched_spec["category"],
            "Defect Description": matched_spec["defect_name"],
            "Severity Rating": inc.get("severity", "STANDARD").upper(),
            "PWD Priority & SLA": f"{prio} // SLA: {matched_spec['sla']}",
            "Corridor / Sector": inc.get("location", "Urban Corridor"),
            "GPS Latitude": lat,
            "GPS Longitude": lon,
            "IRC Standard Specification": matched_spec["irc_code"],
            "Recommended Engineering Repair": matched_spec["repair_action"],
            "Estimated Material Quantity": matched_spec["material_qty"],
            "Estimated Cost (INR)": f"₹{cost:,}",
            "Detection Confidence": inc.get("confidence", "88%"),
            "Inspection Status": "PENDING FIELD CREW DISPATCH"
        })
        order_idx += 1

    # Write to standard CSV with headers
    fieldnames = [
        "Work Order No",
        "Date Logged",
        "Defect Category",
        "Defect Description",
        "Severity Rating",
        "PWD Priority & SLA",
        "Corridor / Sector",
        "GPS Latitude",
        "GPS Longitude",
        "IRC Standard Specification",
        "Recommended Engineering Repair",
        "Estimated Material Quantity",
        "Estimated Cost (INR)",
        "Detection Confidence",
        "Inspection Status"
    ]

    with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "file_path": csv_path,
        "total_orders": len(rows),
        "total_budget_inr": total_budget_inr,
        "priority_counts": priority_counts
    }
    return csv_path, summary
