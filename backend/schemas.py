"""Pydantic schemas for API requests/responses."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# === Lot Card (summary view) ===
class LotCard(BaseModel):
    """Summary view of a lot."""

    id: int
    title: str
    source: str
    lot_url: Optional[str] = None
    image_url: Optional[str] = None
    current_bid: Optional[float] = None
    current_bid_updated_at: Optional[datetime] = None
    bid_count: Optional[int] = None
    estimate_low: Optional[float] = None
    estimate_high: Optional[float] = None
    currency: Optional[str] = None
    auction_end_time: Optional[datetime] = None
    time_remaining: Optional[str] = None
    labels: list[str] = Field(default_factory=list)
    scores: dict[str, Optional[float]] = Field(default_factory=dict)
    ai_value_low: Optional[float] = None
    ai_value_high: Optional[float] = None
    ai_value_basis: Optional[str] = None
    landed_cost_eur: Optional[float] = None
    expected_resale_eur: Optional[float] = None
    predicted_hammer_eur: Optional[float] = None
    max_bid_eur: Optional[float] = None
    hammer_prediction_method: Optional[str] = None
    estimate_confidence: Optional[str] = None
    estimate_basis: Optional[list[dict]] = None
    enrichment_version: Optional[str] = None
    best_market: Optional[str] = None
    best_market_reasoning: Optional[str] = None
    buyer_profile: Optional[dict] = None
    listing: Optional[dict] = None
    inspection_checklist: Optional[list[str]] = None
    conviction: Optional[str] = None
    comparables_count: Optional[int] = None
    retail_new_price: Optional[float] = None
    seller_location: Optional[str] = None
    demand_summary: Optional[str] = None
    demand_detail: Optional[dict] = None
    rationale: Optional[str] = None
    risk_flags: list[str] = Field(default_factory=list)
    user_actions: list[str] = Field(default_factory=list)

    class Config:
        from_attributes = True


# === Lot Detail ===
class ParsedFieldsDetail(BaseModel):
    """Parsed fields from lot page."""

    parser_version: str
    title: Optional[str] = None
    subtitle: Optional[str] = None
    description: Optional[str] = None
    category_raw: Optional[str] = None
    condition_text: Optional[str] = None
    dimensions_text: Optional[str] = None
    current_bid: Optional[float] = None
    estimate_low: Optional[float] = None
    estimate_high: Optional[float] = None
    currency: Optional[str] = None
    auction_end_time: Optional[datetime] = None
    time_left_text: Optional[str] = None
    provenance_text: Optional[str] = None
    seller_location: Optional[str] = None
    auction_house_name: Optional[str] = None
    raw_designer_mentions: Optional[list[str]] = None
    raw_material_mentions: Optional[list[str]] = None
    parse_confidence: float = 0.5

    class Config:
        from_attributes = True


class NormalizedFieldsDetail(BaseModel):
    """Normalized lot fields."""

    normalizer_version: str
    designer_entity_id: Optional[int] = None
    designer_name: Optional[str] = None
    producer_entity_id: Optional[int] = None
    producer_name: Optional[str] = None
    object_type_id: Optional[str] = None
    era_label: Optional[str] = None
    materials: Optional[list[str]] = None
    normalized_category: Optional[str] = None
    normalization_confidence: float = 0.5

    class Config:
        from_attributes = True


class EnrichmentOutputDetail(BaseModel):
    """Enrichment output from an agent."""

    agent_name: str
    agent_version: str
    completed_at: Optional[datetime] = None
    output_json: dict[str, Any]
    confidence: Optional[float] = None

    class Config:
        from_attributes = True


class FetchHistoryItem(BaseModel):
    """Single fetch history item."""

    fetched_at: datetime
    fetch_type: str
    http_status: Optional[int] = None
    success: bool
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class LotDetail(LotCard):
    """Detailed view of a lot."""

    lot_url: str
    parsed_fields: Optional[ParsedFieldsDetail] = None
    normalized_fields: Optional[NormalizedFieldsDetail] = None
    enrichments: list[EnrichmentOutputDetail] = Field(default_factory=list)
    fetch_history: list[FetchHistoryItem] = Field(default_factory=list)
    images: list[dict[str, Any]] = Field(default_factory=list)
    notes: Optional[str] = None

    class Config:
        from_attributes = True


# === View Response ===
class ViewResponse(BaseModel):
    """Response for a view endpoint."""

    lots: list[LotCard]
    total: int
    view_name: str
    filters: dict[str, Any] = Field(default_factory=dict)

    class Config:
        from_attributes = True


# === User Actions ===
class UserActionCreate(BaseModel):
    """Create a user action on a lot."""

    action_type: str  # star, skip, watch, archive, note, bought, false_positive
    note: Optional[str] = None


# === Enrichment Output Schemas ===
class AttributionOutput(BaseModel):
    """Designer attribution enrichment output."""

    designer_candidate: Optional[str] = None
    designer_confidence: Optional[float] = None
    producer_candidate: Optional[str] = None
    object_type: Optional[str] = None
    era: Optional[str] = None
    materials: list[str] = Field(default_factory=list)
    attribution_flags: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)

    class Config:
        from_attributes = True


class HammerPredictionDetail(BaseModel):
    """Hammer price prediction from historical Auctionet data (buy-side)."""

    predicted: Optional[float] = None
    low: Optional[float] = None
    high: Optional[float] = None
    confidence: Optional[float] = None
    method: Optional[str] = None  # historical_match, ratio_adjusted, estimate_fallback
    num_historical_matches: Optional[int] = None
    estimate_to_hammer_ratio: Optional[float] = None

    class Config:
        from_attributes = True


class ArbitrageOutput(BaseModel):
    """Arbitrage scoring enrichment output."""

    fair_value_range: Optional[dict[str, float]] = None
    expected_resale_value: Optional[float] = None
    landed_cost_estimate: Optional[float] = None
    estimated_margin_range: Optional[dict[str, float]] = None
    arbitrage_score: Optional[float] = None
    confidence: Optional[float] = None
    reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    hammer_prediction: Optional[HammerPredictionDetail] = None
    max_bid_eur: Optional[float] = None

    class Config:
        from_attributes = True


class TasteOutput(BaseModel):
    """Taste matching enrichment output."""

    taste_score: Optional[float] = None
    mode: Optional[str] = None  # core, adjacent, exploratory
    similar_to: list[str] = Field(default_factory=list)
    adjacent_entities: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)

    class Config:
        from_attributes = True


class WildcardOutput(BaseModel):
    """Wildcard scoring enrichment output."""

    wildcard_score: Optional[float] = None
    sculptural_score: Optional[float] = None
    luxury_material_score: Optional[float] = None
    distinctiveness_score: Optional[float] = None
    reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)

    class Config:
        from_attributes = True


# === Wanted Listings ===
class WantedListingCard(BaseModel):
    """Summary of a Finn wanted listing."""

    id: int
    finn_id: str
    url: str
    title: str
    offered_price: Optional[float] = None
    currency: str = "NOK"
    brand: Optional[str] = None
    designer: Optional[str] = None
    category: Optional[str] = None
    buyer_location: Optional[str] = None
    image_urls: Optional[list[str]] = None
    published_text: Optional[str] = None
    match_reason: Optional[str] = None

    class Config:
        from_attributes = True


class WantedViewResponse(BaseModel):
    """Response for wanted listings view."""

    listings: list[WantedListingCard]
    total: int

    class Config:
        from_attributes = True


# === Job Responses ===
class JobTriggerResponse(BaseModel):
    """Response when triggering a job."""

    job_id: str
    status: str  # queued, running, completed, failed
    message: str

    class Config:
        from_attributes = True


# === Pagination ===
class PaginationParams(BaseModel):
    """Pagination parameters."""

    skip: int = 0
    limit: int = 50

    class Config:
        from_attributes = True
