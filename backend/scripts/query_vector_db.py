"""
scripts/query_vector_db.py
==========================
CLI tool to view, test search, and insert test data into Supabase Vector DB.

Usage:
    # 1. View all or latest stored rows
    python scripts/query_vector_db.py --list
    python scripts/query_vector_db.py --list --limit 20

    # 2. Test semantic vector search with custom test query
    python scripts/query_vector_db.py --query "sanding belt for wood"
    python scripts/query_vector_db.py --query "3M cubitron grinding disc" --top-k 3

    # 3. Insert custom test product / document
    python scripts/query_vector_db.py --insert-test "Bosch 18V Cordless Drill with brushless motor" --title "Bosch 18V Drill" --brand "Bosch"
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import find_dotenv, load_dotenv
load_dotenv(find_dotenv())

from app.db.supabase_client import get_client
from sentence_transformers import SentenceTransformer

EMBED_MODEL_NAME = "all-MiniLM-L6-v2"


def list_rows(limit: int = 20):
    client = get_client()
    resp = client.table("documents").select("id, content, metadata").limit(limit).order("id", desc=True).execute()
    rows = resp.data
    print(f"\n=======================================================")
    print(f" Supabase Vector Database: Found {len(rows)} rows (showing up to {limit})")
    print(f"=======================================================\n")
    
    if not rows:
        print("No documents found in Supabase 'documents' table.")
        return

    for idx, row in enumerate(rows, 1):
        meta = row.get("metadata", {})
        title = meta.get("title", "(No title)") if isinstance(meta, dict) else ""
        brand = meta.get("brand", "(No brand)") if isinstance(meta, dict) else ""
        content = row.get("content", "")
        # Short preview
        preview = content.replace("\n", " ")[:140]
        
        print(f"[{idx}] ID: {row.get('id')} | Brand: {brand}")
        print(f"    Title: {title}")
        print(f"    Content Preview: {preview}...")
        if isinstance(meta, dict) and meta.get("key_features"):
            print(f"    Key Features: {meta.get('key_features')[:3]}")
        print("-" * 55)


def search_vector_db(query: str, match_count: int = 5, match_threshold: float = 0.2):
    print(f"\n[1/2] Loading embedding model ({EMBED_MODEL_NAME})...")
    model = SentenceTransformer(EMBED_MODEL_NAME)
    
    print(f"[2/2] Generating vector embedding for query: '{query}'")
    query_vector = model.encode(query).tolist()
    
    client = get_client()
    resp = client.rpc(
        "match_documents",
        {
            "query_embedding": query_vector,
            "match_threshold": match_threshold,
            "match_count": match_count,
        }
    ).execute()
    
    results = resp.data
    print(f"\n=======================================================")
    print(f" Semantic Search Results for: \"{query}\" (Top {len(results)})")
    print(f"=======================================================\n")
    
    if not results:
        print("No matching documents found above threshold.")
        return
        
    for idx, match in enumerate(results, 1):
        sim = match.get("similarity", 0.0)
        meta = match.get("metadata", {})
        title = meta.get("title", "Unknown Title") if isinstance(meta, dict) else ""
        brand = meta.get("brand", "Unknown Brand") if isinstance(meta, dict) else ""
        content = match.get("content", "")
        preview = content.replace("\n", " ")[:180]
        
        print(f"{idx}. Score: {sim:.4f} ({sim*100:.1f}% match) | ID: {match.get('id')}")
        print(f"   Title: {title} | Brand: {brand}")
        print(f"   Excerpt: {preview}...")
        print()


def insert_test_data(content: str, title: str = "", brand: str = ""):
    print(f"\nGenerating vector embedding for test content...")
    model = SentenceTransformer(EMBED_MODEL_NAME)
    embedding = model.encode(content).tolist()
    
    metadata = {
        "title": title or content[:40],
        "brand": brand or "TestBrand",
        "is_test_data": True
    }
    
    payload = {
        "content": content,
        "metadata": metadata,
        "embedding": embedding
    }
    
    client = get_client()
    resp = client.table("documents").insert(payload).execute()
    print(f"\n[SUCCESS] Inserted test data into Supabase Vector DB:")
    print(f"  Inserted ID: {resp.data[0].get('id')}")
    print(f"  Title: {metadata['title']}")
    print(f"  Brand: {metadata['brand']}")
    print(f"  Embedding dimension: {len(embedding)}")


def main():
    parser = argparse.ArgumentParser(description="Query and test Supabase Vector DB.")
    parser.add_argument("--list", action="store_true", help="List stored rows in Supabase")
    parser.add_argument("--limit", type=int, default=20, help="Number of rows to list")
    parser.add_argument("--query", "-q", type=str, help="Semantic search test query string")
    parser.add_argument("--top-k", type=int, default=5, help="Number of search matches to return")
    parser.add_argument("--insert-test", type=str, help="Insert test data text into the vector DB")
    parser.add_argument("--title", type=str, default="", help="Optional title for test document")
    parser.add_argument("--brand", type=str, default="", help="Optional brand for test document")
    
    args = parser.parse_args()
    
    if args.query:
        search_vector_db(args.query, match_count=args.top_k)
    elif args.insert_test:
        insert_test_data(args.insert_test, title=args.title, brand=args.brand)
    else:
        list_rows(limit=args.limit)


if __name__ == "__main__":
    main()
