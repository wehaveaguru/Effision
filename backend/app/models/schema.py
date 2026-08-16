from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

NodeType = Literal["Product", "Attribute", "Category", "Supplier", "Source"]
EdgeStatus = Literal["proposed", "approved", "rejected"]


class Node(BaseModel):
    id: str
    node_type: NodeType
    label: str
    properties: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class Edge(BaseModel):
    id: str
    source_node_id: str
    target_node_id: str
    relation: str
    value: dict[str, Any] | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    source_document_id: str
    status: EdgeStatus = "proposed"
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime | None = None


class SourceDocument(BaseModel):
    id: str
    file_name: str
    file_type: str
    raw_text: str | None = None
    parsed_at: datetime | None = None


class ParsedDocument(BaseModel):
    """Output of app/pipeline/parse.py"""

    file_name: str
    file_type: str
    raw_text: str
    tables: list[dict[str, Any]] = Field(default_factory=list)


class SegregatedField(BaseModel):
    """One structured field pulled out of a ParsedDocument by segregate.py,
    before it becomes a graph edge — this is the pre-persistence shape."""

    field_name: str          # e.g. "diameter_mm", "category", "supplier"
    field_value: Any
    node_type_hint: NodeType
    confidence: float = Field(ge=0.0, le=1.0)


class SegregationResult(BaseModel):
    file_name: str
    product_label: str
    fields: list[SegregatedField]


class GraphResponse(BaseModel):
    nodes: list[Node]
    edges: list[Edge]


class ReviewDecision(BaseModel):
    decision: Literal["approved", "rejected"]
    reviewed_by: str = "anonymous"


class ReviewQueueItem(BaseModel):
    edge: Edge
    source_node: Node
    target_node: Node
    source_document: SourceDocument


# ---------------------------------------------------------------------------
# Ingestor models
# ---------------------------------------------------------------------------

class RawProduct(BaseModel):
    """Schema used by LlamaCloud Extract to pull rows from tabular files
    (CSV, XLSX). Field names mirror what LlamaCloud returns for e-commerce
    product sheets."""

    product_name: str = Field(description="The product name")
    brand_name: str = Field(description="What brand the product is related to")
    product_price: float = Field(description="Amount of money received in procurement")
    product_image: str = Field(description="Link to product image")
    product_star_rating: float = Field(description="Ratings of a product")
    number_of_ratings: int = Field(description="Number of ratings")


class EnrichedProduct(BaseModel):
    """Groq-enriched product profile produced by DocumentIngestor."""

    title: str
    brand: str
    category_hierarchy: list[str] = Field(default_factory=list)
    summary: str
    enriched_description: str
    key_features: list[str] = Field(default_factory=list)
    technical_specifications: dict[str, Any] = Field(default_factory=dict)
    attributes: dict[str, Any] = Field(default_factory=dict)
    search_keywords: list[str] = Field(default_factory=list)