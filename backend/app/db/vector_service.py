import os
from typing import List, Dict, Any, Optional
from app.db.supabase_client import get_client

supabase = get_client()


def get_embedding(text: str) -> List[float]:
    """Generate a dense vector embedding via Groq's embedding API (nomic-embed-text-v1.5, 768-dim).
    Falls back to a zero-vector stub if GROQ_API_KEY is not set (dev/test only).
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        # Stub: return a 768-dim zero vector so the server starts without credentials
        return [0.0] * 768

    import httpx

    resp = httpx.post(
        "https://api.groq.com/openai/v1/embeddings",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": "nomic-embed-text-v1.5", "input": text},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["data"][0]["embedding"]


def get_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Batch embed multiple texts.  Groq accepts a list as 'input'."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return [[0.0] * 768 for _ in texts]

    import httpx

    resp = httpx.post(
        "https://api.groq.com/openai/v1/embeddings",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": "nomic-embed-text-v1.5", "input": texts},
        timeout=60,
    )
    resp.raise_for_status()
    data = sorted(resp.json()["data"], key=lambda x: x["index"])
    return [d["embedding"] for d in data]


def insert_document(content: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Store raw text, metadata, and the calculated embedding into Supabase."""
    vector = get_embedding(content)
    data = {
        "content": content,
        "metadata": metadata or {},
        "embedding": vector,
    }
    response = supabase.table("documents").insert(data).execute()
    return response.data


def insert_documents_batch(documents: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Batch insert multiple documents.
    Expected format: [{'content': '...', 'metadata': {...}}, ...]
    """
    contents = [doc["content"] for doc in documents]
    embeddings = get_embeddings_batch(contents)

    records = []
    for doc, emb in zip(documents, embeddings):
        records.append({
            "content": doc["content"],
            "metadata": doc.get("metadata", {}),
            "embedding": emb,
        })

    response = supabase.table("documents").insert(records).execute()
    return response.data


def search_documents(
    query: str,
    match_threshold: float = 0.3,
    match_count: int = 5,
) -> List[Dict[str, Any]]:
    """Query the Supabase vector index using semantic cosine similarity."""
    query_vector = get_embedding(query)

    response = supabase.rpc(
        "match_documents",
        {
            "query_embedding": query_vector,
            "match_threshold": match_threshold,
            "match_count": match_count,
        },
    ).execute()

    return response.data