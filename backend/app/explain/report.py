"""
Step 6 — Explainability report. Renders approved edges + their reasoning
trail (source doc, confidence, who approved it and when) as a PDF, so a
catalog manager can hand auditors something other than "trust the dashboard".
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from app.db.supabase_client import get_client

TEMPLATE_DIR = Path(__file__).parent / "templates"


def build_report_context() -> dict:
    client = get_client()
    edges = client.table("edges").select("*").eq("status", "approved").execute().data

    rows = []
    for edge in edges:
        source_node = client.table("nodes").select("*").eq("id", edge["source_node_id"]).execute().data[0]
        target_node = client.table("nodes").select("*").eq("id", edge["target_node_id"]).execute().data[0]
        source_doc = (
            client.table("source_documents")
            .select("*")
            .eq("id", edge["source_document_id"])
            .execute()
            .data[0]
        )
        rows.append(
            {
                "product": source_node["label"],
                "relation": edge["relation"],
                "value": edge.get("value"),
                "confidence": edge["confidence"],
                "target_label": target_node["label"],
                "source_file": source_doc["file_name"],
                "reviewed_by": edge.get("reviewed_by"),
                "reviewed_at": edge.get("reviewed_at"),
            }
        )

    return {"generated_at": datetime.utcnow().isoformat(timespec="seconds"), "rows": rows}


def render_report(output_path: str | Path = "product_brain_report.pdf") -> Path:
    context = build_report_context()
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template("report.html.j2")
    html_str = template.render(**context)

    from weasyprint import HTML  # imported lazily — optional/heavy dep

    output_path = Path(output_path)
    HTML(string=html_str).write_pdf(str(output_path))
    return output_path