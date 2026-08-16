"""
app/pipeline/pdf_parser.py  (DEPRECATED)
=========================================
This file has been superseded by ``app/pipeline/ingestor.py``.

The CSV extraction + Groq enrichment logic that used to live here as a
top-level script is now encapsulated in:

    DocumentIngestor._LlamaExtractStrategy   (extraction)
    DocumentIngestor._LlamaExtractStrategy._enrich()  (enrichment)

Migration
---------
Old (script-style, ran at import time)::

    # pdf_parser.py — everything at module level
    client = LlamaCloud(...)
    job = client.extract.create(...)
    ...
    for batch in llm_batches:
        groq_client.chat.completions.create(...)

New (on-demand, reusable)::

    from app.pipeline.ingestor import DocumentIngestor

    result = DocumentIngestor().ingest("amazon_product.csv")
    # result.rows     — raw extracted rows
    # result.enriched — list[EnrichedProduct] (Groq-enriched profiles)
    print(result.enriched[0].title)

This file is kept to avoid breaking any external imports.
All symbols are re-exported from ingestor / schema for convenience.
"""

from app.models.schemas import EnrichedProduct, RawProduct  # noqa: F401
from app.pipeline.ingestor import DocumentIngestor, IngestResult  # noqa: F401

__all__ = ["DocumentIngestor", "IngestResult", "RawProduct", "EnrichedProduct"]