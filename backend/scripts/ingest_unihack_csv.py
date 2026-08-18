"""
scripts/ingest_unihack_csv.py
==============================
End-to-end pipeline for the Unihack procurement dataset:

  1. Read  ``Unihack_ Sample.csv``   -> pandas DataFrame (already structured)
  2. Enrich rows                     -> Groq (EnrichedProduct profiles)
  3. Embed each profile              -> SentenceTransformer (384-dim vector)
  4. Store in Supabase               -> documents table (content + metadata + embedding)

Prerequisites
-------------
* Run ``app/db/schema.sql`` once in your Supabase SQL editor to create the
  ``documents`` table and the ``pgvector`` extension.
* SUPABASE_URL and SUPABASE_KEY must be set in backend/.env
  (use the **service_role** key so that inserts are permitted).
* GROQ_API_KEY must be set in backend/.env

Usage (run from the backend/ directory)
----------------------------------------
    python scripts/ingest_unihack_csv.py
    python scripts/ingest_unihack_csv.py --csv path/to/file.csv
    python scripts/ingest_unihack_csv.py --limit 20          # first 20 rows only
    python scripts/ingest_unihack_csv.py --dry-run           # no Supabase write
"""

from __future__ import annotations

import argparse
import json
import sys

# Ensure UTF-8 output on Windows consoles that default to cp1252
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Allow running from backend/ as:  python scripts/ingest_unihack_csv.py
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import find_dotenv, load_dotenv
load_dotenv(find_dotenv())

import pandas as pd
from groq import Groq
from sentence_transformers import SentenceTransformer

from app.db.supabase_client import get_client
from app.models.schemas import EnrichedProduct


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_CSV = str(Path(__file__).parent.parent / "Unihack_ Sample.csv")
GROQ_MODEL = "openai/gpt-oss-120b"
EMBED_MODEL = "all-MiniLM-L6-v2"
BATCH_SIZE_ENRICH = 2       # rows per Groq call (keep small to avoid token truncation)
BATCH_SIZE_INSERT = 10      # rows per Supabase insert
INTER_BATCH_SLEEP = 5.0     # seconds between Groq batches (TPM guard)

# ---------------------------------------------------------------------------
# Groq enrichment prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are an expert industrial product information specialist.
Transform the raw procurement rows below into rich, searchable product profiles.

Output strictly valid JSON with the top-level key "products" containing an array:
{
  "products": [
    {
      "title": "Clear, searchable product title including part number and key specs",
      "brand": "Best available brand name (prefer non-placeholder values)",
      "category_hierarchy": ["Category", "Subcategory", "Product Type"],
      "summary": "1-2 sentence value proposition for this industrial part.",
      "enriched_description": "Comprehensive description covering use cases, compatibility, and benefits.",
      "key_features": ["Feature 1", "Feature 2", "Feature 3"],
      "technical_specifications": {"key": "value"},
      "attributes": {
        "part_number": "...",
        "manufacturer": "...",
        "material": "...",
        "application": "..."
      },
      "search_keywords": ["keyword1", "keyword2", "keyword3"]
    }
  ]
}

Rules:
- Process EVERY product in the input list.
- For brand: use E1_Brand if it is not "-- Unbranded --", else try Unilog_Brand,
  then DIB_Brand, then extract from Part_Manuf or Part_Desc.
- Return ONLY the JSON object. No markdown fences or preamble.\
"""


# ---------------------------------------------------------------------------
# Helper: read CSV → list of raw row dicts
# ---------------------------------------------------------------------------

def _load_csv(csv_path: Path, limit: int | None) -> list[dict]:
    """Read the CSV with pandas and normalise column names."""
    df = pd.read_csv(csv_path, dtype=str).fillna("")
    if limit:
        df = df.head(limit)

    # Rename columns to match our internal schema
    df = df.rename(columns={
        "Mfg_Part_Num": "mfg_part_num",
        "Part_Desc":    "part_desc",
        "E1_Brand":     "e1_brand",
        "Unilog_Brand": "unilog_brand",
        "DIB_Brand":    "dib_brand",
        "Part_Manuf":   "part_manuf",
    })
    return df.to_dict(orient="records")


# ---------------------------------------------------------------------------
# Helper: Groq enrichment (one batch at a time, with retry)
# ---------------------------------------------------------------------------

def _call_groq(batch: list[dict], groq_client: Groq) -> str:
    """Call Groq and return the raw response text. Retries on rate-limit."""
    max_retries = 5
    for attempt in range(max_retries):
        try:
            response = groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"Enrich these procurement rows:\n{json.dumps(batch)}",
                    },
                ],
                # NOTE: do NOT use response_format json_object — it causes
                # json_validate_failed on longer outputs. Parse manually instead.
                temperature=0.2,
                max_tokens=4096,
            )
            return response.choices[0].message.content
        except Exception as exc:
            err_str = str(exc).lower()
            if "rate_limit" in err_str or "429" in err_str:
                wait = 2 ** (attempt + 2)   # 4 → 8 → 16 → 32 → 64 s
                print(f"  [enrich] Rate limit — retrying in {wait}s "
                      f"(attempt {attempt + 1}/{max_retries})...")
                time.sleep(wait)
                if attempt == max_retries - 1:
                    raise
            else:
                raise
    raise RuntimeError("Groq call failed after all retries")


def _parse_products(text: str) -> list[EnrichedProduct]:
    """Extract EnrichedProduct list from a Groq response string.

    Strategy:
    1. Try json.loads on the whole string.
    2. If that fails, find the first {...} block with regex.
    3. Validate each item into EnrichedProduct with graceful degradation.
    """
    import re

    payload = None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        # Attempt to extract JSON object from surrounding text / markdown
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                payload = json.loads(match.group())
            except json.JSONDecodeError:
                pass

    if payload is None:
        print("  [enrich] WARNING: could not parse JSON from response, skipping batch.")
        return []

    enriched: list[EnrichedProduct] = []
    for item in payload.get("products", []):
        try:
            enriched.append(EnrichedProduct(**item))
        except Exception:
            enriched.append(
                EnrichedProduct(
                    title=item.get("title", "Unknown Part"),
                    brand=item.get("brand", "Unknown"),
                    summary=item.get("summary", ""),
                    enriched_description=item.get("enriched_description", ""),
                )
            )
    return enriched


def _enrich_batch(
    batch: list[dict],
    groq_client: Groq,
    batch_idx: int,
    total_batches: int,
) -> list[EnrichedProduct]:
    """Enrich one batch. On failure, retry each item individually."""
    print(f"  [enrich] Batch {batch_idx + 1}/{total_batches} ({len(batch)} rows)...")
    try:
        text = _call_groq(batch, groq_client)
        results = _parse_products(text)
        if results:
            return results
        raise ValueError("Empty parse result")
    except Exception as exc:
        if len(batch) == 1:
            # Can't split further — skip and warn
            print(f"  [enrich] WARNING: single-item batch failed ({exc}), skipping.")
            return []
        # Split the batch and retry halves individually
        print(f"  [enrich] Batch failed ({type(exc).__name__}), retrying item-by-item...")
        results: list[EnrichedProduct] = []
        for i, item in enumerate(batch):
            try:
                text = _call_groq([item], groq_client)
                results.extend(_parse_products(text))
                time.sleep(2)  # small pause between individual retries
            except Exception as item_exc:
                print(f"  [enrich] WARNING: item {i} failed ({item_exc}), skipping.")
        return results



# ---------------------------------------------------------------------------
# Helper: flatten EnrichedProduct → plain text for embedding
# ---------------------------------------------------------------------------

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


def _product_to_metadata(p: EnrichedProduct) -> dict:
    return {
        "title": p.title,
        "brand": p.brand,
        "category_hierarchy": p.category_hierarchy,
        "key_features": p.key_features,
        "technical_specifications": p.technical_specifications,
        "attributes": p.attributes,
        "search_keywords": p.search_keywords,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--csv",
        default=DEFAULT_CSV,
        help=f"Path to the CSV file (default: Unihack_ Sample.csv)",
    )
    ap.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Ingest only the first N rows (useful for testing)",
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

    # -------------------------------------------------------------------
    # Step 1: Load CSV
    # -------------------------------------------------------------------
    print(f"\n[1/3] Loading {csv_path.name} ...")
    rows = _load_csv(csv_path, args.limit)
    print(f"      -> {len(rows)} rows loaded")

    if not rows:
        print("[warn] No rows to process.")
        return

    # -------------------------------------------------------------------
    # Step 2: Groq enrichment
    # -------------------------------------------------------------------
    import os
    groq_key = os.environ.get("GROQ_API_KEY")
    if not groq_key:
        print("[error] GROQ_API_KEY is not set in .env")
        sys.exit(1)

    print(f"\n[2/3] Enriching rows via Groq ({GROQ_MODEL}) ...")
    groq_client = Groq(api_key=groq_key)

    batches = [
        rows[i : i + BATCH_SIZE_ENRICH]
        for i in range(0, len(rows), BATCH_SIZE_ENRICH)
    ]
    enriched: list[EnrichedProduct] = []
    for idx, batch in enumerate(batches):
        enriched.extend(_enrich_batch(batch, groq_client, idx, len(batches)))
        if idx < len(batches) - 1:
            time.sleep(INTER_BATCH_SLEEP)

    print(f"      -> {len(enriched)} products enriched")

    # -------------------------------------------------------------------
    # Step 3: Embed
    # -------------------------------------------------------------------
    print(f"\n[3/3a] Generating embeddings ({EMBED_MODEL}) ...")
    embed_model = SentenceTransformer(EMBED_MODEL)
    texts = [_product_to_text(p) for p in enriched]
    embeddings = embed_model.encode(texts, show_progress_bar=True).tolist()
    print(f"       -> {len(embeddings)} embeddings (dim={len(embeddings[0])})")

    if args.dry_run:
        print("\n--dry-run: skipping Supabase write.")
        print("Sample text (first product):\n", texts[0][:300])
        print("Sample embedding (first 5 dims):", embeddings[0][:5])
        return

    # -------------------------------------------------------------------
    # Step 4: Insert into Supabase
    # -------------------------------------------------------------------
    print("\n[3/3b] Inserting into Supabase documents table ...")
    client = get_client()
    backend_name = type(client).__name__
    print(f"       Using backend: {backend_name}")

    if backend_name == "LocalPostgresShim":
        print("\n[warn] SUPABASE_URL / SUPABASE_KEY not set — writing to local SQLite shim.")
        print("       Set both env vars in backend/.env to write to real Supabase.")

    records = [
        {
            "content": text,
            "metadata": _product_to_metadata(product),
            "embedding": embedding,
        }
        for text, product, embedding in zip(texts, enriched, embeddings)
    ]

    total_inserted = 0
    for i in range(0, len(records), BATCH_SIZE_INSERT):
        batch = records[i : i + BATCH_SIZE_INSERT]
        resp = client.table("documents").insert(batch).execute()
        total_inserted += len(resp.data)
        print(f"       Inserted {total_inserted}/{len(records)} records...")

    print(f"\nDone! {total_inserted} products stored in Supabase ({backend_name}).")

    # -------------------------------------------------------------------
    # Quick semantic search sanity-check
    # -------------------------------------------------------------------
    print("\n--- Quick semantic search sanity-check ---")
    test_query = "sanding belt abrasive"
    q_vec = embed_model.encode(test_query).tolist()
    try:
        hits = client.rpc(
            "match_documents",
            {"query_embedding": q_vec, "match_threshold": 0.2, "match_count": 3},
        ).execute()
        print(f"Query: '{test_query}'")
        for h in hits.data:
            meta = h.get("metadata", {})
            title = meta.get("title") if isinstance(meta, dict) else ""
            print(f"  [{h.get('similarity', 0):.3f}] {title or h.get('content', '')[:80]}")
    except Exception as exc:
        print(f"[warn] Semantic search test skipped: {exc}")


if __name__ == "__main__":
    main()
