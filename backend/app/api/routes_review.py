from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.db.supabase_client import get_client
from app.models.schemas import Edge, ReviewDecision, ReviewQueueItem

router = APIRouter(tags=["review"])


@router.get("/edges/queue", response_model=list[ReviewQueueItem])
def get_review_queue(limit: int = 50):
    """Convenience endpoint for the dashboard: proposed edges, each joined
    with its source/target nodes and source document, so the React queue UI
    can render a full review card in one call instead of N+1 fetches."""
    client = get_client()
    edges = (
        client.table("edges")
        .select("*")
        .eq("status", "proposed")
        .order("confidence")  # lowest-confidence first — needs review most
        .limit(limit)
        .execute()
        .data
    )

    items = []
    for edge in edges:
        source_node = client.table("nodes").select("*").eq("id", edge["source_node_id"]).execute().data[0]
        target_node = client.table("nodes").select("*").eq("id", edge["target_node_id"]).execute().data[0]
        source_doc = (
            client.table("source_documents")
            .select("*")
            .eq("id", edge["source_document_id"])
            .execute()
            .data[0]
        )
        items.append(
            ReviewQueueItem(
                edge=edge, source_node=source_node, target_node=target_node, source_document=source_doc
            )
        )
    return items


@router.post("/edges/{edge_id}/review", response_model=Edge)
def review_edge(edge_id: str, decision: ReviewDecision):
    """The single code path in the whole system that can move an edge out
    of status='proposed'. The pipeline (app/pipeline/*) has no access to
    this and no way to call it."""
    client = get_client()
    existing = client.table("edges").select("*").eq("id", edge_id).execute().data
    if not existing:
        raise HTTPException(status_code=404, detail=f"No edge with id {edge_id}")

    updated = (
        client.table("edges")
        .update(
            {
                "status": decision.decision,
                "reviewed_by": decision.reviewed_by,
                "reviewed_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        .eq("id", edge_id)
        .execute()
        .data[0]
    )
    return updated