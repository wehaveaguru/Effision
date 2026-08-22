import os
from typing import List, Dict, Any, Optional
from app.db.supabase_client import get_client

supabase = get_client()

_embed_model = None

def _get_model():
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer
        _embed_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embed_model


def get_embedding(text: str) -> List[float]:
    """Generate a dense 384-dimension vector embedding via SentenceTransformer (all-MiniLM-L6-v2)."""
    model = _get_model()
    embedding = model.encode(text)
    return embedding.tolist()


def get_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Batch embed multiple texts into 384-dimension vectors."""
    model = _get_model()
    embeddings = model.encode(texts)
    return embeddings.tolist()



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