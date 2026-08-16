import os
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
from backend.app.db.supabase_client import supabase

# Initialize the embedding model (runs locally on CPU/GPU)
# all-MiniLM-L6-v2 generates 384-dimensional dense vectors
embed_model = SentenceTransformer("all-MiniLM-L6-v2")


def get_embedding(text: str) -> List[float]:
    """Generate a 384-dimension vector embedding using sentence-transformers."""
    embedding = embed_model.encode(text)
    return embedding.tolist()


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
    embeddings = embed_model.encode(contents).tolist()

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
    match_count: int = 5
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


# --- Demonstration / Testing ---
if __name__ == "__main__":
    print("Testing Vector Database Operations...\n")

    # 1. Insert sample documents
    sample_docs = [
        {
            "content": "Supabase provides PostgreSQL with pgvector support for AI applications.",
            "metadata": {"category": "database", "source": "docs"},
        },
        {
            "content": "SentenceTransformers allows running embedding models offline on CPU.",
            "metadata": {"category": "nlp", "source": "docs"},
        },
        {
            "content": "FastAPI is a Python web framework for building APIs.",
            "metadata": {"category": "backend", "source": "web"},
        },
    ]

    print("Inserting batch documents...")
    inserted = insert_documents_batch(sample_docs)
    print(f"Inserted {len(inserted)} records successfully.\n")

    # 2. Perform a semantic similarity search
    search_query = "How to run vector embeddings locally without cloud APIs?"
    print(f"Searching for: '{search_query}'")

    results = search_documents(search_query, match_threshold=0.2, match_count=2)
    print("\nSearch Results:")
    for idx, match in enumerate(results, 1):
        print(f"{idx}. [Similarity: {match['similarity']:.4f}]")
        print(f"   Content: {match['content']}")
        print(f"   Metadata: {match['metadata']}\n")