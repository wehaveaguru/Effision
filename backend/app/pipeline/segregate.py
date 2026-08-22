"""
Step 2 (segregate half) — classify/structure ParsedDocument.raw_text into
schema-defined fields (SegregatedField), each carrying its own confidence.

Real path: Groq, JSON mode, one batched call per document (minimizes tokens
vs. one call per field).

Offline path (no GROQ_API_KEY): a small regex/heuristic extractor tuned to
the Camber Supply Co. sample doc. This exists ONLY so `--dry-run` can prove
out the pipeline shape (parse -> segregate -> would-be-write) without
credentials. It is intentionally narrow and should not be mistaken for the
real segregation logic.
"""

from __future__ import annotations
from groq import Groq
from dotenv import load_dotenv,find_dotenv

import json
import os
import re

load_dotenv(find_dotenv())


# pyrefly: ignore [missing-import]
from app.models.schemas import ParsedDocument, SegregatedField, SegregationResult

_SEGREGATION_SYSTEM_PROMPT = """You are a product-data extraction engine.
Given raw text from a supplier spec sheet, extract structured fields.
Return ONLY valid JSON matching this shape, nothing else:
{
  "product_label": "<short product name>",
  "fields": [
    {"field_name": "<attribute name>", "field_value": <value>,
     "node_type_hint": "Attribute|Category|Supplier",
     "confidence": <0.0-1.0>}
  ]
}
Confidence should reflect how explicitly the source text states the value —
1.0 for an exact labeled spec, lower for anything inferred or ambiguous."""


def segregate_document(doc: ParsedDocument) -> SegregationResult:
    api_key = os.environ.get("GROQ_API_KEY")
    if api_key:
        return _segregate_via_groq(doc, api_key)
    return _segregate_offline_heuristic(doc)


def _segregate_via_groq(doc: ParsedDocument, api_key: str) -> SegregationResult:
      # imported lazily — optional dep

    client = Groq(api_key=api_key)
    completion = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _SEGREGATION_SYSTEM_PROMPT},
            {"role": "user", "content": doc.raw_text},
        ],
        temperature=0.1,
    )
    payload = json.loads(completion.choices[0].message.content)
    fields = [SegregatedField(**f) for f in payload["fields"]]
    return SegregationResult(
        file_name=doc.file_name, product_label=payload["product_label"], fields=fields
    )


_LABEL_PATTERNS = {
    "diameter_mm": r"diameter[:\s]+([\d.]+)\s*mm",
    "length_mm": r"length[:\s]+([\d.]+)\s*mm",
    "thread_pitch_mm": r"thread pitch[:\s]+([\d.]+)\s*mm",
    "material": r"material[:\s]+([A-Za-z0-9 \-]+?)(?:\n|$)",
    "tensile_strength_mpa": r"tensile strength[:\s]+([\d.]+)\s*mpa",
    "category": r"category[:\s]+([A-Za-z0-9 \-]+?)(?:\n|$)",
    "supplier": r"supplier[:\s]+([A-Za-z0-9 \-.,&]+?)(?:\n|$)",
}

_NODE_TYPE_HINTS = {
    "category": "Category",
    "supplier": "Supplier",
}


def _segregate_offline_heuristic(doc: ParsedDocument) -> SegregationResult:
    text = doc.raw_text
    lower = text.lower()

    title_match = re.search(r"^product name[:\s]+(.+)$", text, re.IGNORECASE | re.MULTILINE)
    product_label = title_match.group(1).strip() if title_match else doc.file_name

    fields: list[SegregatedField] = []
    for field_name, pattern in _LABEL_PATTERNS.items():
        m = re.search(pattern, lower, re.IGNORECASE)
        if not m:
            continue
        value = m.group(1).strip()
        # numeric coercion where it makes sense
        if re.match(r"^-?[\d.]+$", value):
            value = float(value) if "." in value else int(value)
        fields.append(
            SegregatedField(
                field_name=field_name,
                field_value=value,
                node_type_hint=_NODE_TYPE_HINTS.get(field_name, "Attribute"),
                # explicit labeled match in raw text -> high confidence,
                # but never 1.0 for the offline path (it's a heuristic, not a model)
                confidence=0.82,
            )
        )

    return SegregationResult(file_name=doc.file_name, product_label=product_label, fields=fields)