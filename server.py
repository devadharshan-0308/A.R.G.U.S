"""
server.py — Run the FastAPI Smart City Ingestion Backend.

Usage:
    python server.py
    (Or: uvicorn src.backend.app:app --host 0.0.0.0 --port 8000 --reload)
"""

import uvicorn

if __name__ == "__main__":
    print("=" * 60)
    print("  Starting Smart City Ingestion & Alerts Backend Server")
    print("  API Docs available at: http://localhost:8000/docs")
    print("  Live WebSocket at:    ws://localhost:8000/ws/live")
    print("=" * 60)
    uvicorn.run("src.backend.app:app", host="0.0.0.0", port=8000, reload=True)
