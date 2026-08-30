"""
maps_mcp_server.py — Python Google Maps MCP Server (FastMCP).

Provides MCP tools:
  - reverse_geocode: Convert GPS coordinates (lat, lng) to street name, area, and city.
  - find_nearby_emergency_poi: Find closest hospital, school, police station, or depot.
  - get_route_directions: Calculate route travel time and distance between coordinates.
"""

import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

try:
    from fastmcp import FastMCP
    import googlemaps
    mcp = FastMCP("Smart City Traffic & Maps Engine")
except ImportError:
    mcp = None
    googlemaps = None

gmaps_client = None
if googlemaps and API_KEY and not API_KEY.startswith("YOUR_"):
    try:
        gmaps_client = googlemaps.Client(key=API_KEY)
    except Exception as e:
        logger.warning(f"Failed to initialize googlemaps client: {e}")

if mcp:
    @mcp.tool()
    def reverse_geocode(lat: float, lng: float) -> str:
        """Convert GPS coordinates to road name, area, and formatted address."""
        if not gmaps_client:
            return f"Simulated Location: MG Road Corridor (lat: {lat:.6f}, lng: {lng:.6f})"
        try:
            results = gmaps_client.reverse_geocode((lat, lng))
            if results:
                return results[0].get("formatted_address", "Unknown Road")
        except Exception as e:
            return f"Error geocoding: {str(e)}"
        return "Location not found"

    @mcp.tool()
    def find_nearby_emergency_poi(lat: float, lng: float, poi_type: str = "hospital", radius_meters: int = 1000) -> list:
        """Find closest hospital, school, police station, or bus depot."""
        if not gmaps_client:
            return [{
                "name": f"City {poi_type.title()} Point",
                "address": "Near MG Road, Bengaluru",
                "is_active": True
            }]
        try:
            places = gmaps_client.places_nearby(
                location=(lat, lng),
                radius=radius_meters,
                type=poi_type
            )
            results = []
            for p in places.get("results", [])[:3]:
                results.append({
                    "name": p.get("name"),
                    "address": p.get("vicinity"),
                    "rating": p.get("rating")
                })
            return results
        except Exception as e:
            return [{"error": str(e)}]

    @mcp.tool()
    def check_school_or_hospital_zone(lat: float, lng: float) -> dict:
        """Check if coordinates fall within 200m of a school or hospital."""
        if not gmaps_client:
            return {"is_school_zone": False, "is_hospital_zone": False, "nearby": []}
        try:
            places = gmaps_client.places_nearby(
                location=(lat, lng),
                radius=200,
                type="school|hospital|university"
            )
            results = places.get("results", [])
            is_school = any(any(t in p.get("types", []) for t in ["school", "university", "primary_school"]) for p in results)
            is_hosp = any(any(t in p.get("types", []) for t in ["hospital", "doctor"]) for p in results)
            names = [p.get("name") for p in results[:2]]
            return {
                "is_school_zone": is_school,
                "is_hospital_zone": is_hosp,
                "nearby": names
            }
        except Exception as e:
            return {"error": str(e), "is_school_zone": False, "is_hospital_zone": False}

if __name__ == "__main__":
    if mcp:
        print("Starting Maps MCP Server on stdio...")
        mcp.run()
    else:
        print("FastMCP or Googlemaps not installed. Run: pip install fastmcp googlemaps")
