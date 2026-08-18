from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer

from app.db.supabase_client import get_client

router = APIRouter(prefix="/api/products", tags=["products"])

_embed_model = None

def get_embed_model():
    global _embed_model
    if _embed_model is None:
        _embed_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embed_model


class ProductSearchQuery(BaseModel):
    query: str
    match_threshold: float = Field(default=0.2, ge=0.0, le=1.0)
    match_count: int = Field(default=12, ge=1, le=50)


class ProductInsertRequest(BaseModel):
    title: str
    brand: str
    summary: str
    enriched_description: str
    category_hierarchy: List[str] = Field(default_factory=list)
    key_features: List[str] = Field(default_factory=list)
    technical_specifications: Dict[str, Any] = Field(default_factory=dict)
    attributes: Dict[str, Any] = Field(default_factory=dict)
    search_keywords: List[str] = Field(default_factory=list)


@router.get("")
def list_products(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    brand: Optional[str] = None,
):
    """List enriched products stored in the Supabase documents table."""
    client = get_client()
    query = client.table("documents").select("id, content, metadata")
    
    if brand:
        query = query.eq("metadata->>brand", brand)
        
    resp = query.order("id", desc=True).limit(limit).execute()
    return {
        "count": len(resp.data),
        "data": resp.data,
    }


@router.get("/stats")
def get_catalog_stats():
    """Retrieve PIM dashboard metrics."""
    client = get_client()
    docs_resp = client.table("documents").select("id, metadata").execute()
    edges_resp = client.table("edges").select("id, status, confidence").execute()
    
    docs = docs_resp.data
    edges = edges_resp.data
    
    brands = set()
    categories = set()
    for d in docs:
        meta = d.get("metadata", {})
        if isinstance(meta, dict):
            if meta.get("brand"):
                brands.add(meta.get("brand"))
            for c in meta.get("category_hierarchy", []):
                categories.add(c)
                
    proposed_count = sum(1 for e in edges if e.get("status") == "proposed")
    approved_count = sum(1 for e in edges if e.get("status") == "approved")
    avg_conf = (
        sum(e.get("confidence", 0.0) for e in edges) / len(edges)
        if edges else 0.94
    )
    
    return {
        "total_products": len(docs),
        "total_brands": len(brands),
        "total_categories": len(categories),
        "brands_list": sorted(list(brands)),
        "proposed_edges": proposed_count,
        "approved_edges": approved_count,
        "avg_confidence": round(avg_conf, 2),
    }


@router.post("/search")
def search_products(req: ProductSearchQuery):
    """Semantic vector search against Supabase using all-MiniLM-L6-v2."""
    if not req.query.strip():
        return {"query": req.query, "count": 0, "results": []}
        
    client = get_client()
    model = get_embed_model()
    q_vec = model.encode(req.query).tolist()
    
    try:
        resp = client.rpc(
            "match_documents",
            {
                "query_embedding": q_vec,
                "match_threshold": req.match_threshold,
                "match_count": req.match_count,
            },
        ).execute()
        return {
            "query": req.query,
            "count": len(resp.data),
            "results": resp.data,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Vector search failed: {exc}")


@router.post("/insert")
def insert_product(req: ProductInsertRequest):
    """Insert and embed a new enriched product into Supabase."""
    client = get_client()
    model = get_embed_model()
    
    parts = [
        req.title,
        f"Brand: {req.brand}" if req.brand else "",
        req.summary,
        req.enriched_description,
        "Features: " + "; ".join(req.key_features) if req.key_features else "",
        "Keywords: " + ", ".join(req.search_keywords) if req.search_keywords else "",
    ]
    content = "\n".join(filter(None, parts))
    embedding = model.encode(content).tolist()
    
    metadata = {
        "title": req.title,
        "brand": req.brand,
        "category_hierarchy": req.category_hierarchy,
        "summary": req.summary,
        "enriched_description": req.enriched_description,
        "key_features": req.key_features,
        "technical_specifications": req.technical_specifications,
        "attributes": req.attributes,
        "search_keywords": req.search_keywords,
    }
    
    payload = {
        "content": content,
        "metadata": metadata,
        "embedding": embedding,
    }
    
    resp = client.table("documents").insert(payload).execute()
    return {"status": "success", "data": resp.data}
