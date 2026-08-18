import sys
from pathlib import Path
import os


# Ensure backend directory is in python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.pipeline.ingestor import DocumentIngestor

# Use absolute/resolved path to amazon_product.csv in backend/
csv_file = backend_dir / "amazon_product.csv"

# Ingest and enrich
result = DocumentIngestor().ingest(csv_file)

print(f"Extracted {len(result.rows)} raw product rows.")
print(f"Enriched {len(result.enriched)} products.\n")

for product in result.enriched:
    print(f"Title:   {product.title}")
    print(f"Brand:   {product.brand}")
    print(f"Summary: {product.summary}")
    print(f"Specs:   {product.technical_specifications}")
    print("-" * 50)
