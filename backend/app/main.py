import os
from pathlib import Path
from dotenv import find_dotenv, load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.api import routes_graph, routes_review, routes_products

load_dotenv(find_dotenv())

app = FastAPI(
    title="Effision Product Brain PIM API",
    description="Propose-only product enrichment & semantic vector PIM: every edge carries provenance "
    "and confidence, and nothing is final until a human approves it.",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_graph.router)
app.include_router(routes_review.router)
app.include_router(routes_products.router)

@app.get("/health")
def health():
    return {"status": "ok", "service": "Effision PIM"}

# Mount frontend static files
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

    @app.get("/")
    def serve_frontend():
        return FileResponse(frontend_dir / "index.html")