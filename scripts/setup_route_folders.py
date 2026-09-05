import os
import json
import shutil

def setup_route_folders():
    routes_file = os.path.join("data", "corridor_routes.json")
    with open(routes_file, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    base_dir = os.path.join("data", "input", "routes")
    os.makedirs(base_dir, exist_ok=True)

    demo_pool = [
        "pothole.mp4",
        "demo_traffic.mp4",
        "dividers_.mp4",
        "example2.mp4",
        "crowd.mp4"
    ]

    for idx in range(1, 11):
        bus_id = f"bus{idx}"
        info = catalog.get(bus_id, {})
        folder = os.path.join(base_dir, bus_id)
        os.makedirs(folder, exist_ok=True)

        readme_path = os.path.join(folder, "ROUTE_INFO.txt")
        with open(readme_path, "w", encoding="utf-8") as rf:
            rf.write(f"CORRIDOR ID: {bus_id}\n")
            rf.write(f"ROUTE: {info.get('route_label', '')}\n")
            rf.write(f"CORRIDOR NAME: {info.get('corridor_name', '')}\n")
            rf.write(f"STREET NAME: {info.get('street_name', '')}\n")
            rf.write(f"WAYPOINTS: {len(info.get('coordinates', []))}\n")
            rf.write("\nINSTRUCTIONS: Drop your route video files (.mp4, .avi, .mov, .mkv) in this directory.\n")
            rf.write("The application will automatically detect and load videos placed here.\n")

        # Check existing videos in folder
        existing = [f for f in os.listdir(folder) if f.lower().endswith(('.mp4', '.avi', '.mov', '.mkv'))]
        if not existing:
            # Seed a default demo video so each corridor has a working stream out of the box
            demo_name = demo_pool[(idx - 1) % len(demo_pool)]
            src_v = os.path.join("data", "input", demo_name)
            if os.path.exists(src_v):
                dst_v = os.path.join(folder, f"{bus_id}_{demo_name}")
                shutil.copyfile(src_v, dst_v)
                print(f"Seeded: {dst_v}")

    print("All 10 route folders initialized successfully!")

if __name__ == "__main__":
    setup_route_folders()
