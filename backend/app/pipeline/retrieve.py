"""
Step 3 — Retrieve. Hybrid search over source_documents:
  * vector similarity (pgvector, via the match_source_documents RPC)
  * BM25-style full text (Postgres FTS, via search_source_documents_fts RPC)
merged with Reciprocal Rank Fusion (RRF), so neither channel dominates just
because its raw scores happen to be on a bigger scale.
"""

from __future__ import annotations

from app.db.supabase_client import get_client

RRF_K = 60  # standard RRF damping constant


def hybrid_search(query_text: str, query_embedding: list[float] | None = None, match_count: int = 10):
    client = get_client()

    fts_res = client.rpc(
        "search_source_documents_fts",
        {"query_text": query_text, "match_count": match_count * 2},
    ).execute()
    fts_ranked = [row["id"] for row in fts_res.data]

    vec_ranked: list[str] = []
    if query_embedding is not None:
        vec_res = client.rpc(
            "match_source_documents",
            {"query_embedding": query_embedding, "match_count": match_count * 2},
        ).execute()
        vec_ranked = [row["id"] for row in vec_res.data]
    else:
        # No embedding available (e.g. offline dry run) — fall back to the
        # same lexical ranking for both channels rather than skipping RRF.
        vec_ranked = fts_ranked

    scores = reciprocal_rank_fusion([fts_ranked, vec_ranked])
    all_rows = {row["id"]: row for row in fts_res.data}
    ranked_ids = sorted(scores, key=scores.get, reverse=True)[:match_count]
    return [
        {**all_rows.get(doc_id, {"id": doc_id}), "rrf_score": scores[doc_id]}
        for doc_id in ranked_ids
    ]


def reciprocal_rank_fusion(ranked_lists: list[list[str]], k: int = RRF_K) -> dict[str, float]:
    """Standard RRF: score(d) = sum over lists of 1 / (k + rank_in_list(d))."""
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, doc_id in enumerate(ranked):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    return scores