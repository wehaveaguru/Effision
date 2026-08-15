"""
Step 2 (parse half) — turn a raw source file into a ParsedDocument.

.pdf / .docx route through LlamaCloud (needs LLAMA_CLOUD_API_KEY).
.txt / .md are read directly — this is what lets the pipeline run
end-to-end offline against data/sample_docs/, with zero API keys, so the
pipeline *shape* can be verified before wiring real credentials.
"""

from __future__ import annotations

import os
from pathlib import Path

from app.models.schemas import ParsedDocument

OFFLINE_EXTENSIONS = {".txt", ".md"}
CLOUD_EXTENSIONS = {".pdf", ".docx"}


def parse_document(file_path: str | Path) -> ParsedDocument:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"No such source document: {path}")

    ext = path.suffix.lower()
    if ext in OFFLINE_EXTENSIONS:
        return _parse_offline(path)
    if ext in CLOUD_EXTENSIONS:
        return _parse_via_llamacloud(path)
    raise ValueError(f"Unsupported source document type: {ext}")


def _parse_offline(path: Path) -> ParsedDocument:
    text = path.read_text(encoding="utf-8")
    return ParsedDocument(
        file_name=path.name,
        file_type=path.suffix.lstrip("."),
        raw_text=text,
        tables=[],
    )


def _parse_via_llamacloud(path: Path) -> ParsedDocument:
    api_key = os.environ.get("LLAMA_CLOUD_API_KEY")
    if not api_key:
        raise RuntimeError(
            "LLAMA_CLOUD_API_KEY is not set. Parsing "
            f"{path.name} requires LlamaCloud since it isn't .txt/.md. "
            "Set the key in .env or convert the doc to .txt for offline testing."
        )

    from llama_cloud_services import LlamaParse  # imported lazily — optional dep

    parser = LlamaParse(api_key=api_key, result_type="markdown")
    result = parser.parse(str(path))
    raw_text = "\n\n".join(page.md for page in result.pages)
    tables = []
    for page in result.pages:
        tables.extend(getattr(page, "tables", []) or [])

    return ParsedDocument(
        file_name=path.name,
        file_type=path.suffix.lstrip("."),
        raw_text=raw_text,
        tables=tables,
    )