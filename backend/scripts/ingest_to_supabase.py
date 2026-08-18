"""
scripts/ingest_to_supabase.py
==============================
End-to-end pipeline:
  1. Parse amazon_product.csv  -> LlamaCloud Extract (structured rows)
  2. Enrich rows               -> Groq (EnrichedProduct profiles)
  3. Embed each profile        -> SentenceTransformer (384-dim vector)
  4. Store in Supabase         -> documents table (content + metadata + embedding)

Usage (from the backend/ directory):
    python scripts/ingest_to_supabase.py
    python scripts/ingest_to_supabase.py --csv path/to/file.csv
    python scripts/ingest_to_supabase.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import find_dotenv, load_dotenv
load_dotenv(find_dotenv())

from sentence_transformers import SentenceTransformer
from app.db.supabase_client import get_client
from app.models.schemas import EnrichedProduct
from app.pipeline.ingestor import DocumentIngestor


def _product_to_text(p: EnrichedProduct) -> str:
    """Flatten an EnrichedProduct into a single string for embedding."""
    parts = [
        p.title,
        f"Brand: {p.brand}" if p.brand else "",
        p.summary,
        p.enriched_description,
        "Features: " + "; ".join(p.key_features) if p.key_features else "",
        "Keywords: " + ", ".join(p.search_keywords) if p.search_keywords else "",
    ]
    return "\n".join(filter(None, parts))


def _product_to_metadata(p: EnrichedProduct) -> dict:
    """Build a JSON-serialisable metadata dict for the documents row."""
    return {
        "title": p.title,
        "brand": p.brand,
        "category_hierarchy": p.category_hierarchy,
        "key_features": p.key_features,
        "technical_specifications": p.technical_specifications,
        "attributes": p.attributes,
        "search_keywords": p.search_keywords,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--csv",
        default=str(Path(__file__).parent.parent / "amazon_product.csv"),
        help="Path to the CSV file to ingest (default: backend/amazon_product.csv)",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse + enrich + embed, but do NOT write to Supabase",
    )
    args = ap.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"[error] CSV not found: {csv_path}")
        sys.exit(1)

    # Step 1 & 2: Parse + Enrich
    print(f"\n[1/3] Parsing & enriching {csv_path.name} ...")
    result = DocumentIngestor().ingest(csv_path)
    print(f"      -> {len(result.rows)} raw rows extracted")
    print(f"      -> {len(result.enriched)} products enriched")

    if not result.enriched:
        print("[warn] No enriched products - nothing to store.")
        return

    # Step 3: Embed
    print("\n[2/3] Generating embeddings (all-MiniLM-L6-v2) ...")
    embed_model = SentenceTransformer("all-MiniLM-L6-v2")
    texts = [_product_to_text(p) for p in result.enriched]
    embeddings = embed_model.encode(texts, show_progress_bar=True).tolist()
    print(f"      -> {len(embeddings)} embeddings generated (dim={len(embeddings[0])})")

    if args.dry_run:
        print("\n--dry-run: skipping Supabase write.")
        print("Sample embedding (first 5 dims):", embeddings[0][:5])
        return

    # Step 4: Store in Supabase
    print("\n[3/3] Inserting into Supabase documents table ...")
    client = get_client()
    print(f"      Using backend: {type(client).__name__}")

    records = [
        {
            "content": text,
            "metadata": _product_to_metadata(product),
            "embedding": embedding,
        }
        for text, product, embedding in zip(texts, result.enriched, embeddings)
    ]

    batch_size = 10
    total_inserted = 0
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        resp = client.table("documents").insert(batch).execute()
        total_inserted += len(resp.data)
        print(f"      Inserted {total_inserted}/{len(records)} records...")

    print(f"\nDone! {total_inserted} products stored in Supabase.")

    # Quick semantic search sanity check
    print("\n--- Quick semantic search test ---")
    test_query = "wireless headphones with noise cancellation"
    q_vec = embed_model.encode(test_query).tolist()
    hits = client.rpc(
        "match_documents",
        {"query_embedding": q_vec, "match_threshold": 0.2, "match_count": 3},
    ).execute()
    print(f"Query: '{test_query}'")
    for h in hits.data:
        meta = h.get("metadata", {})
        print(f"  [{h.get('similarity', 0):.3f}] {meta.get('title', h.get('content', '')[:60])}")


if __name__ == "__main__":
    main()
