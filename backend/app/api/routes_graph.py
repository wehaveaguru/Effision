from fastapi import APIRouter, Query

from app.db.supabase_client import get_client
from app.models.schemas import GraphResponse

router = APIRouter(tags=["graph"])


@router.get("/graph", response_model=GraphResponse)
def get_graph(status: str = Query("approved", description="Edge status to include")):
    """Fetch nodes + edges for the graph visualization.

    Defaults to approved-only, matching the product rule that nothing is
    "real" in the dashboard's graph view until a human has reviewed it.
    Pass status=proposed to preview pending edges instead.
    """
    client = get_client()
    edges_res = client.table("edges").select("*").eq("status", status).execute()
    edges = edges_res.data

    node_ids = {e["source_node_id"] for e in edges} | {e["target_node_id"] for e in edges}
    nodes = []
    for node_id in node_ids:
        n = client.table("nodes").select("*").eq("id", node_id).execute().data
        if n:
            nodes.append(n[0])

    return GraphResponse(nodes=nodes, edges=edges)