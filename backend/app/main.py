"""FastAPI Application entrypoint for TraceMind."""
from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .api.routes import router, trigger_simulation, SimulateRequest


app = FastAPI(
    title="TraceMind AIOps Platform",
    description="AI-Powered Incident Detection and Root Cause Analysis Platform",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

# Mount frontend static directory if exists
FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIST)), name="static")

    @app.get("/")
    def serve_frontend():
        index_file = FRONTEND_DIST / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return {"message": "TraceMind Backend API Online"}


@app.on_event("startup")
def startup_seed_demo():
    """Seed initial demonstration incident on startup."""
    try:
        trigger_simulation(SimulateRequest(scenario="payment_db_exhaustion", duration_seconds=60))
        print("[✓] TraceMind Startup: Seeded initial Payment DB Exhaustion failure incident.")
    except Exception as e:
        print(f"[!] Warning seeding initial incident: {e}")
