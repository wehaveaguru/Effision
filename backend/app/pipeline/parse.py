"""
app/pipeline/parse.py  (backwards-compat shim)
===============================================
All document-parsing logic has been consolidated into
``app/pipeline/ingestor.py``.

This module is kept so existing imports and pipeline scripts continue to
work without modification.  New code should use DocumentIngestor directly:

    from app.pipeline.ingestor import DocumentIngestor
    result = DocumentIngestor().ingest("path/to/file.pdf")
"""

from __future__ import annotations

from pathlib import Path

# Re-export constants and types that callers may have imported from here.
from app.models.schemas import ParsedDocument  # noqa: F401
from app.pipeline.ingestor import (  # noqa: F401
    ALL_EXTENSIONS,
    EXTRACT_EXTENSIONS,
    LLAMAPARSE_EXTENSIONS,
    OFFLINE_EXTENSIONS,
    DocumentIngestor,
    IngestResult,
    parse_document,
)

# Keep the old extension sets at module level for any code that accessed them.
CLOUD_EXTENSIONS = LLAMAPARSE_EXTENSIONS  # old alias


def parse_document(file_path: str | Path) -> ParsedDocument:  # type: ignore[misc]
    """Backwards-compat wrapper around DocumentIngestor.

    Equivalent to ``DocumentIngestor().ingest(file_path).as_parsed_document()``.
    """
    return DocumentIngestor().ingest(file_path).as_parsed_document()