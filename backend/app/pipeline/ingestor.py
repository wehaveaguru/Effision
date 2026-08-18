"""
app/pipeline/ingestor.py
========================
Unified document ingestor — replaces the split logic that used to live in
``parse.py`` (text/PDF ingestion) and ``pdf_parser.py`` (CSV extraction +
Groq enrichment).

Usage
-----
    from app.pipeline.ingestor import DocumentIngestor

    result = DocumentIngestor().ingest("path/to/file.pdf")
    # result.raw_text   — markdown text (document types)
    # result.rows       — raw structured rows (tabular types)
    # result.enriched   — Groq-enriched product profiles (tabular types)
    # result.as_parsed_document() — backwards-compat ParsedDocument

Strategy routing (auto-selected by file extension)
---------------------------------------------------
    .txt / .md   -> OfflineStrategy      (no API keys required)
    .pdf / .docx -> LlamaParseStrategy   (LLAMA_CLOUD_API_KEY)
    .csv / .xlsx -> LlamaExtractStrategy (LLAMA_CLOUD_API_KEY + GROQ_API_KEY)
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import find_dotenv, load_dotenv

from app.models.schemas import EnrichedProduct, ParsedDocument, RawProduct



# ---------------------------------------------------------------------------
# Env loading — walk up from the module location to find .env
# ---------------------------------------------------------------------------
_env_path = find_dotenv()
if not _env_path:
    for _candidate in [
        Path(__file__).parent.parent / ".env",
        Path(__file__).parent.parent.parent / ".env",
        Path.cwd() / ".env",
        Path.cwd() / "app" / ".env",
    ]:
        if _candidate.is_file():
            _env_path = str(_candidate)
            break
load_dotenv(_env_path)

# ---------------------------------------------------------------------------
# Supported extension sets
# ---------------------------------------------------------------------------
OFFLINE_EXTENSIONS: frozenset[str] = frozenset({".txt", ".md"})
LLAMAPARSE_EXTENSIONS: frozenset[str] = frozenset({".pdf", ".docx"})
EXTRACT_EXTENSIONS: frozenset[str] = frozenset({".csv", ".xlsx"})
ALL_EXTENSIONS: frozenset[str] = (
    OFFLINE_EXTENSIONS | LLAMAPARSE_EXTENSIONS | EXTRACT_EXTENSIONS
)

# ---------------------------------------------------------------------------
# Groq enrichment prompt (shared by any tabular ingest path)
# ---------------------------------------------------------------------------
_ENRICHMENT_SYSTEM_PROMPT = """\
You are an expert e-commerce copywriter and Product Information Management (PIM) specialist.
Your task is to transform the provided array of raw products into rich, engaging, and
comprehensive product profiles.

Output strictly valid JSON with the top-level key "products" containing an array of
enriched objects:
{
  "products": [
    {
      "title": "Optimized, SEO-friendly product title (Brand + Product Line + Key Specs)",
      "brand": "Brand name",
      "category_hierarchy": ["Category", "Subcategory", "Product Type"],
      "summary": "A punchy 1-2 sentence hook highlighting the core value proposition.",
      "enriched_description": "A comprehensive, persuasive description detailing use cases and benefits.",
      "key_features": [
        "Feature benefit statement 1",
        "Feature benefit statement 2",
        "Feature benefit statement 3"
      ],
      "technical_specifications": {"key": "value"},
      "attributes": {
        "color": "...",
        "material": "...",
        "dimensions": "...",
        "target_audience": "..."
      },
      "search_keywords": ["keyword1", "keyword2", "keyword3"]
    }
  ]
}

Guidelines:
- Process every product present in the input list.
- Return ONLY the JSON object. No markdown fences or preamble.\
"""
load_dotenv(find_dotenv())

# ---------------------------------------------------------------------------
# IngestResult — unified output type
# ---------------------------------------------------------------------------

@dataclass
class IngestResult:
    """Unified output of DocumentIngestor.ingest().

    Attributes
    ----------
    file_name : original filename (stem + suffix)
    file_type : extension without leading dot, e.g. "pdf", "csv"
    raw_text  : extracted markdown/plain text (document paths; None for CSV/XLSX)
    tables    : table dicts extracted from pages (PDF/DOCX)
    rows      : raw structured rows from LlamaCloud Extract (CSV/XLSX)
    enriched  : Groq-enriched product profiles (CSV/XLSX); empty list otherwise
    """

    file_name: str
    file_type: str
    raw_text: str | None = None
    tables: list[dict[str, Any]] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)
    enriched: list[EnrichedProduct] = field(default_factory=list)

    def as_parsed_document(self) -> ParsedDocument:
        """Backwards-compatible conversion to ParsedDocument.

        For tabular files (CSV/XLSX) the enriched profiles are serialised as
        JSON and stored in ``raw_text`` so downstream pipeline steps that only
        know about ParsedDocument still receive something meaningful.
        """
        if self.raw_text is not None:
            return ParsedDocument(
                file_name=self.file_name,
                file_type=self.file_type,
                raw_text=self.raw_text,
                tables=self.tables,
            )
        # tabular path — serialise enriched profiles as compact JSON text
        body = json.dumps([e.model_dump() for e in self.enriched], indent=2)
        return ParsedDocument(
            file_name=self.file_name,
            file_type=self.file_type,
            raw_text=body,
            tables=self.rows,
        )


# ---------------------------------------------------------------------------
# Private strategy implementations
# ---------------------------------------------------------------------------

class _OfflineStrategy:
    """Read .txt / .md files directly — no API keys required."""

    def ingest(self, path: Path) -> IngestResult:
        text = path.read_text(encoding="utf-8")
        return IngestResult(
            file_name=path.name,
            file_type=path.suffix.lstrip("."),
            raw_text=text,
        )


class _LlamaParseStrategy:
    """Parse .pdf / .docx via LlamaCloud LlamaParse -> markdown text."""

    def ingest(self, path: Path) -> IngestResult:
        api_key = os.environ.get("LLAMA_CLOUD_API_KEY")
        if not api_key:
            raise RuntimeError(
                "LLAMA_CLOUD_API_KEY is not set. "
                f"Parsing {path.name} requires LlamaCloud. "
                "Set the key in .env or convert the doc to .txt for offline testing."
            )
        try:
            from llama_cloud_services import LlamaParse
        except ImportError:
            from llama_parse import LlamaParse

        parser = LlamaParse(api_key=api_key, result_type="markdown")
        result = parser.parse(str(path))

        raw_text = "\n\n".join(page.md for page in result.pages)
        tables: list[dict[str, Any]] = []
        for page in result.pages:
            tables.extend(getattr(page, "tables", []) or [])

        return IngestResult(
            file_name=path.name,
            file_type=path.suffix.lstrip("."),
            raw_text=raw_text,
            tables=tables,
        )


class _LlamaExtractStrategy:
    """Extract structured rows from .csv / .xlsx via LlamaCloud Extract,
    then enrich each batch with Groq.

    Two-stage pipeline
    ------------------
    1. Upload file -> LlamaCloud Extract job (schema: RawProduct)
    2. Poll until COMPLETED, collect raw rows
    3. Batch rows -> Groq (llama-3.3-70b-versatile) -> EnrichedProduct list
    """

    BATCH_SIZE: int = 3               # smaller batches → fewer tokens per call
    POLL_INTERVAL_S: int = 2
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    INTER_BATCH_SLEEP_S: float = 8.0  # pause between batches to stay under TPM

    def ingest(self, path: Path) -> IngestResult:
        llama_key = os.environ.get("LLAMA_CLOUD_API_KEY")
        groq_key = os.environ.get("GROQ_API_KEY")

        if not llama_key:
            raise RuntimeError(
                "LLAMA_CLOUD_API_KEY is not set. "
                f"Extracting {path.name} requires LlamaCloud Extract."
            )
        if not groq_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. "
                "Groq enrichment requires GROQ_API_KEY."
            )

        from groq import Groq  # optional dep, imported lazily
        try:
            from llama_cloud.client import LlamaCloud
        except ImportError:
            from llama_cloud import LlamaCloud

        try:
            llama_client = LlamaCloud(token=llama_key)
        except TypeError:
            llama_client = LlamaCloud(api_key=llama_key)

        groq_client = Groq(api_key=groq_key)

        rows = self._extract(path, llama_client)
        enriched = self._enrich(rows, groq_client)

        return IngestResult(
            file_name=path.name,
            file_type=path.suffix.lstrip("."),
            rows=rows,
            enriched=enriched,
        )

    # -- private helpers ---------------------------------------------------

    def _extract(self, path: Path, client: Any) -> list[dict[str, Any]]:
        """Upload file to LlamaCloud Extract and poll until job is done."""
        if hasattr(client, "llama_extract"):
            from llama_cloud.types import ExtractConfig, ExtractTarget

            with open(path, "rb") as fh:
                uploaded = client.files.upload_file(upload_file=fh)

            job = client.llama_extract.extract_stateless(
                file_id=uploaded.id,
                data_schema=RawProduct.model_json_schema(),
                config=ExtractConfig(
                    extraction_target=ExtractTarget.PER_TABLE_ROW,
                    tier="agentic",
                ),
            )

            terminal = {"COMPLETED", "FAILED", "CANCELLED", "SUCCESS"}
            while str(getattr(job.status, "value", job.status)).upper() not in terminal:
                time.sleep(self.POLL_INTERVAL_S)
                job = client.llama_extract.get_job(job.id)

            status_str = str(getattr(job.status, "value", job.status)).upper()
            if status_str not in {"COMPLETED", "SUCCESS"}:
                raise RuntimeError(
                    f"LlamaCloud Extract job failed with status: {status_str}"
                )

            res = client.llama_extract.get_job_result(job.id)
            if hasattr(res, "data") and isinstance(res.data, list):
                return res.data
            return getattr(job, "extract_result", []) or []

        # Legacy llama_cloud client API fallback
        with open(path, "rb") as fh:
            uploaded = client.files.create(file=fh, purpose="extract")

        job = client.extract.create(
            file_input=uploaded.id,
            configuration={
                "data_schema": RawProduct.model_json_schema(),
                "extraction_target": "per_table_row",
                "tier": "agentic",
            },
        )

        terminal = {"COMPLETED", "FAILED", "CANCELLED"}
        while job.status not in terminal:
            time.sleep(self.POLL_INTERVAL_S)
            job = client.extract.get(job.id)

        if job.status != "COMPLETED":
            raise RuntimeError(
                f"LlamaCloud Extract job failed with status: {job.status}"
            )

        return job.extract_result or []

    def _enrich(
        self,
        rows: list[dict[str, Any]],
        groq_client: Any,
    ) -> list[EnrichedProduct]:
        """Batch rows and enrich via Groq. Returns validated EnrichedProduct list."""
        batches = [
            rows[i : i + self.BATCH_SIZE]
            for i in range(0, len(rows), self.BATCH_SIZE)
        ]
        enriched: list[EnrichedProduct] = []

        for idx, batch in enumerate(batches):
            print(f"[ingestor] Enriching batch {idx + 1}/{len(batches)}...")

            # Retry with exponential backoff on rate-limit errors.
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    response = groq_client.chat.completions.create(
                        model=self.GROQ_MODEL,
                        messages=[
                            {"role": "system", "content": _ENRICHMENT_SYSTEM_PROMPT},
                            {
                                "role": "user",
                                "content": f"Enrich these products:\n{json.dumps(batch)}",
                            },
                        ],
                        response_format={"type": "json_object"},
                        temperature=0.2,
                    )
                    break  # success — exit retry loop
                except Exception as exc:
                    err_str = str(exc).lower()
                    if "rate_limit" in err_str or "429" in err_str:
                        wait = 2 ** (attempt + 2)  # 4s, 8s, 16s, 32s, 64s
                        print(
                            f"[ingestor] Rate limit hit on batch {idx + 1}, "
                            f"retrying in {wait}s (attempt {attempt + 1}/{max_retries})..."
                        )
                        time.sleep(wait)
                        if attempt == max_retries - 1:
                            raise
                    else:
                        raise

            payload = json.loads(response.choices[0].message.content)
            for item in payload.get("products", []):
                try:
                    enriched.append(EnrichedProduct(**item))
                except Exception:
                    # Partial enrichment is better than a hard crash.
                    enriched.append(
                        EnrichedProduct(
                            title=item.get("title", "Unknown"),
                            brand=item.get("brand", "Unknown"),
                            summary=item.get("summary", ""),
                            enriched_description=item.get("enriched_description", ""),
                        )
                    )

            # Brief pause between batches to respect Groq's free-tier TPM cap.
            if idx < len(batches) - 1:
                time.sleep(self.INTER_BATCH_SLEEP_S)

        return enriched


# ---------------------------------------------------------------------------
# Strategy registry — maps extension -> strategy class
# ---------------------------------------------------------------------------

_STRATEGY_MAP: dict[str, type] = {
    **{ext: _OfflineStrategy for ext in OFFLINE_EXTENSIONS},
    **{ext: _LlamaParseStrategy for ext in LLAMAPARSE_EXTENSIONS},
    **{ext: _LlamaExtractStrategy for ext in EXTRACT_EXTENSIONS},
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class DocumentIngestor:
    """Single entry point for all document ingestion paths.

    Examples
    --------
    Offline (no keys needed)::

        result = DocumentIngestor().ingest("data/sample.txt")
        doc = result.as_parsed_document()

    PDF / DOCX via LlamaParse::

        result = DocumentIngestor().ingest("spec_sheet.pdf")
        print(result.raw_text)

    CSV / XLSX via LlamaCloud Extract + Groq enrichment::

        result = DocumentIngestor().ingest("amazon_products.csv")
        for product in result.enriched:
            print(product.title, product.summary)
    """

    def ingest(self, file_path: str | Path) -> IngestResult:
        """Auto-detect file type and run the appropriate ingest strategy.

        Parameters
        ----------
        file_path : path to the source file

        Returns
        -------
        IngestResult with fields populated according to file type

        Raises
        ------
        FileNotFoundError : source file does not exist
        ValueError        : unsupported file extension
        RuntimeError      : missing API key or upstream job failure
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"No such source document: {path}")

        ext = path.suffix.lower()
        strategy_cls = _STRATEGY_MAP.get(ext)
        if strategy_cls is None:
            raise ValueError(
                f"Unsupported file type: {ext!r}. "
                f"Supported extensions: {sorted(ALL_EXTENSIONS)}"
            )

        return strategy_cls().ingest(path)


# ---------------------------------------------------------------------------
# Backwards-compat helper — drop-in for the old parse.parse_document
# ---------------------------------------------------------------------------

def parse_document(file_path: str | Path) -> ParsedDocument:
    """Thin shim for existing callers of parse.parse_document().

    New code should use ``DocumentIngestor().ingest()`` directly.
    """
    return DocumentIngestor().ingest(file_path).as_parsed_document()
