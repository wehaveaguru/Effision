"""
`make seed` — seeds via get_client(), so it works identically against the
local SQLite shim or a real Supabase instance (whichever get_client()
resolves to). Mirrors data/seed/seed_data.sql for the local dev path.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.supabase_client import get_client  # noqa: E402


def seed() -> None:
    client = get_client()

    doc = client.table("source_documents").insert(
        {
            "file_name": "camber_bolt_specsheet.txt",
            "file_type": "txt",
            "raw_text": Path("data/sample_docs/camber_bolt_specsheet.txt").read_text(),
        }
    ).execute().data[0]

    product = client.table("nodes").insert(
        {"node_type": "Product", "label": "Camber Hex Head Bolt M8x40 Grade 8.8", "properties": {}}
    ).execute().data[0]

    diameter_attr = client.table("nodes").insert(
        {"node_type": "Attribute", "label": "8.0", "properties": {"field_name": "diameter_mm"}}
    ).execute().data[0]

    supplier = client.table("nodes").insert(
        {"node_type": "Supplier", "label": "Camber Supply Co.", "properties": {}}
    ).execute().data[0]

    client.table("edges").insert(
        {
            "source_node_id": product["id"],
            "target_node_id": diameter_attr["id"],
            "relation": "has_attribute",
            "value": {"diameter_mm": 8.0},
            "confidence": 0.95,
            "source_document_id": doc["id"],
            "status": "proposed",
        }
    ).execute()

    client.table("edges").insert(
        {
            "source_node_id": product["id"],
            "target_node_id": supplier["id"],
            "relation": "supplied_by",
            "value": {"supplier": "Camber Supply Co."},
            "confidence": 0.9,
            "source_document_id": doc["id"],
            "status": "proposed",
        }
    ).execute()

    print(f"Seeded 1 source document, 3 nodes, 2 proposed edges (product id: {product['id']})")


if __name__ == "__main__":
    seed()