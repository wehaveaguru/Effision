"""
Step 3 (write half) — takes a SegregationResult and writes it to the graph
as nodes + PROPOSED edges.

Hard rule, structurally enforced here and nowhere overridden elsewhere in
the pipeline: every edge this module inserts has status='proposed'. There
is no parameter, flag, or code path in this file that can write 'approved'.
The only place status can change is app/api/routes_review.py.
"""

from __future__ import annotations

from app.db.supabase_client import get_client
from app.models.schemas import ParsedDocument, SegregationResult


def write_source_document(doc: ParsedDocument) -> str:
    """Insert the parsed source doc; returns its new id."""
    client = get_client()
    res = client.table("source_documents").insert(
        {
            "file_name": doc.file_name,
            "file_type": doc.file_type,
            "raw_text": doc.raw_text,
        }
    ).execute()
    return res.data[0]["id"]


def write_segregation_result(result: SegregationResult, source_document_id: str) -> dict:
    """Writes the Product node plus one Attribute/Category/Supplier node and
    one PROPOSED edge per segregated field. Returns a summary dict of what
    was written, for logging / dry-run diffing."""
    client = get_client()

    product_node = client.table("nodes").insert(
        {"node_type": "Product", "label": result.product_label, "properties": {}}
    ).execute().data[0]

    written_edges = []
    for field in result.fields:
        field_node = client.table("nodes").insert(
            {
                "node_type": field.node_type_hint,
                "label": str(field.field_value),
                "properties": {"field_name": field.field_name},
            }
        ).execute().data[0]

        relation = _relation_for(field.node_type_hint)
        edge = client.table("edges").insert(
            {
                "source_node_id": product_node["id"],
                "target_node_id": field_node["id"],
                "relation": relation,
                "value": {field.field_name: field.field_value},
                "confidence": field.confidence,
                "source_document_id": source_document_id,
                "status": "proposed",  # <-- the only value this pipeline ever writes
            }
        ).execute().data[0]
        written_edges.append(edge)

    return {"product_node": product_node, "edges": written_edges}


def _relation_for(node_type_hint: str) -> str:
    return {
        "Attribute": "has_attribute",
        "Category": "belongs_to_category",
        "Supplier": "supplied_by",
    }.get(node_type_hint, "related_to")