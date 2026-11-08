"""FastAPI Application entrypoint for TraceMind."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, PlainTextResponse

from .api.routes import router, trigger_simulation, SimulateRequest


app = FastAPI(
    title="TraceMind AIOps Platform",
    description="Next-Gen AI-Powered Incident Detection and Causal Root Cause Analysis Platform",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# Compression Middleware for high-performance sub-millisecond asset delivery
app.add_middleware(GZipMiddleware, minimum_size=500)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Security & SEO Performance Headers Middleware
@app.middleware("http")
async def add_security_and_performance_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.path.startswith("/static"):
        response.headers["Cache-Control"] = "public, max-age=86400, stale-while-revalidate=3600"
    return response


# Include API routes
app.include_router(router)

# Root SEO Endpoints
@app.get("/robots.txt", response_class=PlainTextResponse)
def serve_robots():
    """SEO Robots.txt directive for search engine crawlers."""
    return """User-agent: *
Allow: /
Allow: /static/
Disallow: /api/v1/chaos/

Sitemap: https://tracemind.ai/sitemap.xml
"""


@app.get("/sitemap.xml")
def serve_sitemap():
    """Dynamic XML Sitemap for Google, Bing, and search indexing."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://tracemind.ai/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>hourly</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>https://tracemind.ai/api/docs</loc>
    <lastmod>{today}</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.8</priority>
  </url>
  <url>
    <loc>https://tracemind.ai/api/redoc</loc>
    <lastmod>{today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.7</priority>
  </url>
</urlset>"""
    return Response(content=xml_content, media_type="application/xml")


@app.get("/manifest.json")
def serve_manifest():
    """Web App Manifest for Progressive Web App and SEO Lighthouse audit."""
    return {
        "name": "TraceMind AIOps Platform",
        "short_name": "TraceMind",
        "description": "AI-Powered Incident Detection and Causal Root Cause Analysis Platform",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#07090e",
        "theme_color": "#00f0ff",
        "orientation": "any",
        "icons": [
            {
                "src": "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><circle cx='50' cy='50' r='45' fill='%236366f1'/><text x='50' y='65' font-size='45' font-weight='bold' text-anchor='middle' fill='white'>Ψ</text></svg>",
                "sizes": "192x192 512x512",
                "type": "image/svg+xml",
                "purpose": "any maskable",
            }
        ],
        "categories": ["utilities", "productivity", "developer tools"],
    }


# Mount frontend static directory if exists
FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIST)), name="static")

    @app.api_route("/", methods=["GET", "HEAD"])
    def serve_frontend():
        index_file = FRONTEND_DIST / "index.html"
        if index_file.exists():
            return FileResponse(
                str(index_file),
                headers={"Cache-Control": "public, max-age=300, stale-while-revalidate=60"},
            )
        return {"message": "TraceMind Backend API Online"}


@app.on_event("startup")
def startup_seed_demo():
    """Seed initial demonstration incident on startup."""
    try:
        trigger_simulation(SimulateRequest(scenario="payment_db_exhaustion", duration_seconds=60))
        print("[✓] TraceMind Startup: Seeded initial Payment DB Exhaustion failure incident.")
    except Exception as e:
        print(f"[!] Warning seeding initial incident: {e}")
