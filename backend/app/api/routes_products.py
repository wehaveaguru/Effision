from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from pydantic import BaseModel, Field
from groq import Groq

from app.db.supabase_client import get_client
from app.db.vector_service import get_embedding, get_embeddings_batch
from app.models.schemas import EnrichedProduct

router = APIRouter(prefix="/api/products", tags=["products"])

GROQ_MODEL = "openai/gpt-oss-120b"

_ENRICH_PROMPT = """\
You are an expert industrial product information specialist and Product Information Management (PIM) system.
Given the minimal product information provided, transform it into a rich, comprehensive, and structured product profile.

Input:
Product Name / Description: {part_name}
Part Number / SKU: {part_num}
Brand: {brand}
Manufacturer: {manufacturer}
Additional Notes / Specs: {notes_or_specs}

Output strictly valid JSON with this exact schema (no markdown, no preamble):
{{
  "title": "Clean, standardized, searchable title including brand, part number, and primary spec",
  "brand": "Best resolved brand name",
  "category_hierarchy": ["Primary Category", "Subcategory", "Product Type"],
  "summary": "1-2 sentence compelling value proposition highlighting the core capability.",
  "enriched_description": "Comprehensive description detailing industrial applications, compatibility, materials, and benefits.",
  "key_features": [
    "Feature benefit statement 1",
    "Feature benefit statement 2",
    "Feature benefit statement 3"
  ],
  "technical_specifications": {{
    "Part Number": "{part_num}",
    "Brand": "...",
    "Material": "...",
    "Application": "..."
  }},
  "attributes": {{
    "part_number": "{part_num}",
    "manufacturer": "{manufacturer}",
    "brand": "...",
    "material": "...",
    "application": "..."
  }},
  "search_keywords": ["keyword1", "keyword2", "keyword3", "keyword4"]
}}
"""


class ProductSearchQuery(BaseModel):
    query: str
    match_threshold: float = Field(default=0.2, ge=0.0, le=1.0)
    match_count: int = Field(default=12, ge=1, le=50)


class ProductAutoAddRequest(BaseModel):
    part_name: str = Field(description="Product title, part name, or description")
    part_num: Optional[str] = Field(default="", description="Manufacturer part number or SKU")
    brand: Optional[str] = Field(default="", description="Brand name (optional, AI will infer if blank)")
    manufacturer: Optional[str] = Field(default="", description="Manufacturer name (optional)")
    notes_or_specs: Optional[str] = Field(default="", description="Raw specs, dimensions, material, or notes")


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


def _enrich_with_groq(req: ProductAutoAddRequest) -> EnrichedProduct:
    """Call Groq to auto-enrich raw user input into an EnrichedProduct."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return _fallback_enrich(req)

    client = Groq(api_key=api_key)
    prompt = _ENRICH_PROMPT.format(
        part_name=req.part_name,
        part_num=req.part_num or "N/A",
        brand=req.brand or "Unknown",
        manufacturer=req.manufacturer or "Unknown",
        notes_or_specs=req.notes_or_specs or "None provided",
    )

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": "You are a product data specialist. Return strictly valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=2048,
        )
        content = response.choices[0].message.content.strip()
        
        # Parse JSON from content
        payload = None
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                payload = json.loads(match.group())

        if payload:
            return EnrichedProduct(
                title=payload.get("title", req.part_name),
                brand=payload.get("brand", req.brand or "Industrial"),
                category_hierarchy=payload.get("category_hierarchy", ["Industrial", "Hardware"]),
                summary=payload.get("summary", f"{req.part_name} industrial specification."),
                enriched_description=payload.get("enriched_description", req.notes_or_specs or req.part_name),
                key_features=payload.get("key_features", ["High-durability specification", "Industrial grade standard"]),
                technical_specifications=payload.get("technical_specifications", {"Part Number": req.part_num or "N/A"}),
                attributes=payload.get("attributes", {"part_number": req.part_num or "N/A", "brand": req.brand or "Industrial"}),
                search_keywords=payload.get("search_keywords", [req.part_name, req.brand or "hardware"]),
            )
    except Exception as exc:
        print(f"[routes_products] Groq enrichment error: {exc}. Using fallback.")

    return _fallback_enrich(req)


def _fallback_enrich(req: ProductAutoAddRequest) -> EnrichedProduct:
    """Heuristic fallback when Groq is unavailable."""
    title = f"{req.brand + ' ' if req.brand else ''}{req.part_name}{(' (' + req.part_num + ')') if req.part_num else ''}"
    brand = req.brand or "Industrial"
    summary = f"High-performance {req.part_name} engineered for industrial procurement and manufacturing reliability."
    description = (
        f"{title} is built to industrial quality standards. "
        f"{req.notes_or_specs if req.notes_or_specs else 'Engineered for optimal durability, reliability, and precision.'}"
    )
    
    specs = {
        "Part Number": req.part_num or "N/A",
        "Brand": brand,
        "Manufacturer": req.manufacturer or brand,
    }
    if req.notes_or_specs:
        specs["Notes"] = req.notes_or_specs

    return EnrichedProduct(
        title=title,
        brand=brand,
        category_hierarchy=["Industrial", "Procurement", "Hardware"],
        summary=summary,
        enriched_description=description,
        key_features=[
            f"Precision {req.part_name}",
            f"Manufacturer: {req.manufacturer or brand}",
            "Industrial grade tolerance & reliability",
        ],
        technical_specifications=specs,
        attributes={
            "part_number": req.part_num or "N/A",
            "brand": brand,
            "manufacturer": req.manufacturer or brand,
        },
        search_keywords=[k.strip() for k in f"{req.part_name} {brand} {req.part_num}".split() if len(k.strip()) > 1],
    )


def _product_to_text(p: EnrichedProduct) -> str:
    parts = [
        p.title,
        f"Brand: {p.brand}" if p.brand else "",
        p.summary,
        p.enriched_description,
        "Features: " + "; ".join(p.key_features) if p.key_features else "",
        "Keywords: " + ", ".join(p.search_keywords) if p.search_keywords else "",
    ]
    return "\n".join(filter(None, parts))


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
    nodes_resp = client.table("nodes").select("id").execute()
    
    docs = docs_resp.data
    edges = edges_resp.data
    nodes = nodes_resp.data
    
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
        if edges else 0.96
    )
    
    return {
        "total_products": len(docs),
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "total_brands": len(brands),
        "total_categories": len(categories),
        "brands_list": sorted(list(brands)),
        "proposed_edges": proposed_count,
        "approved_edges": approved_count,
        "avg_confidence": round(avg_conf, 2),
    }


@router.get("/analysis")
def get_catalog_analysis():
    """Deep catalogue analytics: brand distribution, category breakdown,
    top keywords, data completeness scores, and data quality overview.
    """
    from collections import Counter

    client = get_client()
    docs_resp = client.table("documents").select("id, content, metadata").execute()
    docs = docs_resp.data or []

    # ── Brand distribution ──────────────────────────────────────────────────
    brand_counter: Counter = Counter()
    category_counter: Counter = Counter()
    keyword_counter: Counter = Counter()

    completeness_scores: list[float] = []
    quality_buckets = {"complete": 0, "partial": 0, "sparse": 0}
    source_counter: Counter = Counter()

    COMPLETENESS_FIELDS = [
        "title", "brand", "summary", "enriched_description",
        "key_features", "technical_specifications", "search_keywords",
        "category_hierarchy",
    ]

    for doc in docs:
        meta = doc.get("metadata") or {}
        if not isinstance(meta, dict):
            meta = {}

        # Brand
        brand = meta.get("brand") or ""
        if brand:
            brand_counter[brand] += 1

        # Categories (de-dup per product — only count top-level category)
        cats = meta.get("category_hierarchy") or []
        if cats and isinstance(cats, list):
            category_counter[cats[0]] += 1

        # Keywords
        kws = meta.get("search_keywords") or []
        if isinstance(kws, list):
            for kw in kws:
                if kw and isinstance(kw, str) and len(kw) > 2:
                    keyword_counter[kw.lower().strip()] += 1

        # Completeness score
        filled = 0
        for field in COMPLETENESS_FIELDS:
            val = meta.get(field)
            if val and (not isinstance(val, (list, dict)) or len(val) > 0):
                filled += 1
        score = filled / len(COMPLETENESS_FIELDS)
        completeness_scores.append(score)

        if score >= 0.85:
            quality_buckets["complete"] += 1
        elif score >= 0.5:
            quality_buckets["partial"] += 1
        else:
            quality_buckets["sparse"] += 1

        # Source file provenance
        src = meta.get("source_file") or meta.get("file_name") or "Manual Entry"
        source_counter[src] += 1

    total = len(docs) or 1
    avg_completeness = (
        round(sum(completeness_scores) / len(completeness_scores) * 100, 1)
        if completeness_scores else 0.0
    )

    return {
        "total_products": len(docs),
        "avg_completeness_pct": avg_completeness,
        "brand_distribution": [
            {"brand": b, "count": c}
            for b, c in brand_counter.most_common(15)
        ],
        "category_breakdown": [
            {"category": cat, "count": cnt}
            for cat, cnt in category_counter.most_common(12)
        ],
        "top_keywords": [
            {"keyword": kw, "count": cnt}
            for kw, cnt in keyword_counter.most_common(30)
        ],
        "quality_distribution": {
            "complete": quality_buckets["complete"],
            "complete_pct": round(quality_buckets["complete"] / total * 100, 1),
            "partial": quality_buckets["partial"],
            "partial_pct": round(quality_buckets["partial"] / total * 100, 1),
            "sparse": quality_buckets["sparse"],
            "sparse_pct": round(quality_buckets["sparse"] / total * 100, 1),
        },
        "source_files": [
            {"file": f, "count": c}
            for f, c in source_counter.most_common(10)
        ],
        "field_fill_rates": _compute_field_fill_rates(docs),
    }


def _compute_field_fill_rates(docs: list) -> list[dict]:
    """Per-field fill rate as percentage across all documents."""
    fields = [
        ("title", "Title"),
        ("brand", "Brand"),
        ("summary", "Summary"),
        ("enriched_description", "Description"),
        ("key_features", "Key Features"),
        ("technical_specifications", "Tech Specs"),
        ("search_keywords", "Keywords"),
        ("category_hierarchy", "Categories"),
    ]
    total = len(docs) or 1
    result = []
    for field_key, label in fields:
        filled = sum(
            1 for doc in docs
            if isinstance(doc.get("metadata"), dict)
            and doc["metadata"].get(field_key)
            and (
                not isinstance(doc["metadata"][field_key], (list, dict))
                or len(doc["metadata"][field_key]) > 0
            )
        )
        result.append({
            "field": label,
            "fill_rate": round(filled / total * 100, 1),
            "filled": filled,
            "total": total,
        })
    return result



@router.post("/search")
def search_products(req: ProductSearchQuery):
    """Semantic vector search against Supabase using all-MiniLM-L6-v2."""
    if not req.query.strip():
        return {"query": req.query, "count": 0, "results": []}

    client = get_client()
    try:
        q_vec = get_embedding(req.query)
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


@router.post("/auto-add")
def auto_add_product(req: ProductAutoAddRequest):
    """Automatically enrich minimal product data, generate vector embedding,
    store in Supabase Vector DB (documents), and populate Knowledge Graph nodes & edges.
    """
    if not req.part_name.strip():
        raise HTTPException(status_code=400, detail="Product name / description is required.")

    client = get_client()

    # 1. AI Enrichment
    enriched = _enrich_with_groq(req)

    # 2. Vector Embedding & Supabase Document Insertion
    content = _product_to_text(enriched)
    embedding = get_embedding(content)

    metadata = {
        "title": enriched.title,
        "brand": enriched.brand,
        "category_hierarchy": enriched.category_hierarchy,
        "summary": enriched.summary,
        "enriched_description": enriched.enriched_description,
        "key_features": enriched.key_features,
        "technical_specifications": enriched.technical_specifications,
        "attributes": enriched.attributes,
        "search_keywords": enriched.search_keywords,
        "is_user_added": True,
    }

    doc_resp = client.table("documents").insert({
        "content": content,
        "metadata": metadata,
        "embedding": embedding,
    }).execute()

    created_doc = doc_resp.data[0] if doc_resp.data else {}
    doc_id = created_doc.get("id")

    # 3. Create Source Document for Provenance
    source_doc = client.table("source_documents").insert({
        "file_name": f"Manual_Entry_{req.part_num or req.part_name[:20].replace(' ', '_')}",
        "file_type": "manual_entry",
        "raw_text": content,
    }).execute().data[0]
    source_doc_id = source_doc["id"]

    # 4. Knowledge Graph Creation: Product Node
    product_node = client.table("nodes").insert({
        "node_type": "Product",
        "label": enriched.title,
        "properties": {
            "part_number": req.part_num or "N/A",
            "brand": enriched.brand,
            "document_id": doc_id,
        },
    }).execute().data[0]
    product_node_id = product_node["id"]

    created_nodes = [product_node]
    created_edges = []

    # 4a. Brand Node & Edge
    if enriched.brand and enriched.brand != "Unknown":
        brand_node = client.table("nodes").insert({
            "node_type": "Supplier",
            "label": enriched.brand,
            "properties": {"type": "Brand"},
        }).execute().data[0]
        created_nodes.append(brand_node)

        edge = client.table("edges").insert({
            "source_node_id": product_node_id,
            "target_node_id": brand_node["id"],
            "relation": "has_brand",
            "value": {"brand": enriched.brand},
            "confidence": 1.0,
            "source_document_id": source_doc_id,
            "status": "proposed",
        }).execute().data[0]
        created_edges.append(edge)

    # 4b. Category Nodes & Edges
    for cat in enriched.category_hierarchy:
        cat_node = client.table("nodes").insert({
            "node_type": "Category",
            "label": cat,
            "properties": {},
        }).execute().data[0]
        created_nodes.append(cat_node)

        edge = client.table("edges").insert({
            "source_node_id": product_node_id,
            "target_node_id": cat_node["id"],
            "relation": "belongs_to_category",
            "value": {"category": cat},
            "confidence": 0.95,
            "source_document_id": source_doc_id,
            "status": "proposed",
        }).execute().data[0]
        created_edges.append(edge)

    # 4c. Attribute Nodes & Edges (from Technical Specs)
    for k, v in list(enriched.technical_specifications.items())[:6]:
        if not v or v == "N/A":
            continue
        attr_node = client.table("nodes").insert({
            "node_type": "Attribute",
            "label": f"{k}: {v}",
            "properties": {"field_name": k, "field_value": str(v)},
        }).execute().data[0]
        created_nodes.append(attr_node)

        edge = client.table("edges").insert({
            "source_node_id": product_node_id,
            "target_node_id": attr_node["id"],
            "relation": "has_specification",
            "value": {k: str(v)},
            "confidence": 0.92,
            "source_document_id": source_doc_id,
            "status": "proposed",
        }).execute().data[0]
        created_edges.append(edge)

    # 4d. Manufacturer Node & Edge (if different from brand)
    if req.manufacturer and req.manufacturer != enriched.brand:
        manuf_node = client.table("nodes").insert({
            "node_type": "Supplier",
            "label": req.manufacturer,
            "properties": {"type": "Manufacturer"},
        }).execute().data[0]
        created_nodes.append(manuf_node)

        edge = client.table("edges").insert({
            "source_node_id": product_node_id,
            "target_node_id": manuf_node["id"],
            "relation": "manufactured_by",
            "value": {"manufacturer": req.manufacturer},
            "confidence": 0.95,
            "source_document_id": source_doc_id,
            "status": "proposed",
        }).execute().data[0]
        created_edges.append(edge)

    return {
        "status": "success",
        "document_id": doc_id,
        "product": enriched.model_dump(),
        "graph_updates": {
            "product_node_id": product_node_id,
            "nodes_created": len(created_nodes),
            "edges_created": len(created_edges),
        },
    }


@router.post("/insert")
def insert_product(req: ProductInsertRequest):
    """Direct manual insert with pre-enriched data (Backwards-compatible)."""
    client = get_client()

    parts = [
        req.title,
        f"Brand: {req.brand}" if req.brand else "",
        req.summary,
        req.enriched_description,
        "Features: " + "; ".join(req.key_features) if req.key_features else "",
        "Keywords: " + ", ".join(req.search_keywords) if req.search_keywords else "",
    ]
    content = "\n".join(filter(None, parts))
    embedding = get_embedding(content)

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


@router.post("/bulk-upload")
async def bulk_upload_products(file: UploadFile = File(...)):
    """Ingest products from an uploaded CSV or PDF file.

    CSV files are processed via LlamaCloud Extract + Groq enrichment.
    PDF files are parsed via LlamaParse and stored as document knowledge.

    Returns a summary of how many products were ingested plus any errors.
    """
    from app.pipeline.ingestor import DocumentIngestor, EXTRACT_EXTENSIONS, LLAMAPARSE_EXTENSIONS
    from app.db.vector_service import get_embedding

    filename = file.filename or "upload"
    ext = Path(filename).suffix.lower()

    allowed = EXTRACT_EXTENSIONS | LLAMAPARSE_EXTENSIONS
    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {sorted(allowed)}",
        )

    # Save upload to a temp file so the ingestor can work with a real path
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        result = DocumentIngestor().ingest(tmp_path)
    except RuntimeError as exc:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(exc))
    finally:
        tmp_path.unlink(missing_ok=True)

    client = get_client()
    ingested_ids: list[int] = []
    errors: list[str] = []

    # ---- CSV / XLSX path: enriched products list ---------------------------
    if result.enriched:
        for enriched in result.enriched:
            try:
                content = _product_to_text(enriched)
                embedding = get_embedding(content)
                metadata = {
                    "title": enriched.title,
                    "brand": enriched.brand,
                    "category_hierarchy": enriched.category_hierarchy,
                    "summary": enriched.summary,
                    "enriched_description": enriched.enriched_description,
                    "key_features": enriched.key_features,
                    "technical_specifications": enriched.technical_specifications,
                    "attributes": enriched.attributes,
                    "search_keywords": enriched.search_keywords,
                    "source_file": filename,
                    "is_bulk_import": True,
                }
                doc_resp = client.table("documents").insert({
                    "content": content,
                    "metadata": metadata,
                    "embedding": embedding,
                }).execute()
                if doc_resp.data:
                    ingested_ids.append(doc_resp.data[0]["id"])
            except Exception as exc:
                errors.append(f"{enriched.title}: {exc}")

    # ---- PDF / DOCX path: raw text document --------------------------------
    elif result.raw_text:
        try:
            # Treat entire document as a single knowledge chunk
            embedding = get_embedding(result.raw_text[:8000])  # truncate for embedding
            metadata = {
                "title": filename,
                "source_file": filename,
                "file_type": result.file_type,
                "is_bulk_import": True,
            }
            doc_resp = client.table("documents").insert({
                "content": result.raw_text,
                "metadata": metadata,
                "embedding": embedding,
            }).execute()
            if doc_resp.data:
                ingested_ids.append(doc_resp.data[0]["id"])
        except Exception as exc:
            errors.append(str(exc))

    return {
        "status": "success",
        "file": filename,
        "file_type": result.file_type,
        "products_ingested": len(ingested_ids),
        "document_ids": ingested_ids,
        "errors": errors,
    }
