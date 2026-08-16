from dotenv import find_dotenv, load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes_graph, routes_review

load_dotenv(find_dotenv())


app = FastAPI(
    title="Product Brain API",
    description="Propose-only product enrichment: every edge carries provenance "
    "and confidence, and nothing is final until a human approves it.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten before production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_graph.router)
app.include_router(routes_review.router)


@app.get("/health")
def health():
    return {"status": "ok"}