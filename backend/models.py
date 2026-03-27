"""SQLAlchemy ORM models for Auction Vision."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import mapped_column, relationship

from backend.database import Base


class Source(Base):
    """Auction source configuration."""

    __tablename__ = "sources"

    id = mapped_column(Integer, primary_key=True)
    name = mapped_column(String(100), unique=True, nullable=False, index=True)
    base_url = mapped_column(String(500), nullable=False)
    enabled = mapped_column(Integer, default=1)  # SQLite bool
    fetch_strategy = mapped_column(String(50), default="listing_page")
    parser_name = mapped_column(String(100), nullable=False)
    rate_limit_policy = mapped_column(String(500), nullable=True)
    buyer_premium_policy = mapped_column(String(500), nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    lots = relationship("Lot", back_populates="source", cascade="all, delete-orphan")

    __table_args__ = (Index("idx_source_enabled", "enabled"),)


class Lot(Base):
    """Auction lot metadata."""

    __tablename__ = "lots"

    id = mapped_column(Integer, primary_key=True)
    source_id = mapped_column(Integer, ForeignKey("sources.id"), nullable=False)
    external_lot_id = mapped_column(String(200), nullable=False)
    lot_url = mapped_column(String(500), nullable=False)
    canonical_title = mapped_column(String(500), nullable=True)
    status = mapped_column(String(50), default="active")  # active, sold, ended, removed
    first_seen_at = mapped_column(DateTime, default=datetime.utcnow)
    last_seen_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_fetched_at = mapped_column(DateTime, nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    source = relationship("Source", back_populates="lots")
    fetches = relationship("LotFetch", back_populates="lot", cascade="all, delete-orphan")
    images = relationship("LotImage", back_populates="lot", cascade="all, delete-orphan")
    parsed_fields = relationship("ParsedLotFields", back_populates="lot", cascade="all, delete-orphan")
    normalized_fields = relationship("NormalizedLotFields", back_populates="lot", cascade="all, delete-orphan")
    enrichment_runs = relationship("EnrichmentRun", back_populates="lot", cascade="all, delete-orphan")
    scores = relationship("LotScores", back_populates="lot", cascade="all, delete-orphan")
    user_actions = relationship("UserAction", back_populates="lot", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_lot_source_id", "source_id"),
        Index("idx_lot_external_id", "external_lot_id"),
        Index("idx_lot_status", "status"),
        Index("idx_lot_last_seen", "last_seen_at"),
    )


class LotFetch(Base):
    """Record of fetching a lot page."""

    __tablename__ = "lot_fetches"

    id = mapped_column(Integer, primary_key=True)
    lot_id = mapped_column(Integer, ForeignKey("lots.id"), nullable=False)
    fetched_at = mapped_column(DateTime, default=datetime.utcnow)
    fetch_type = mapped_column(String(50), default="full")  # full, snapshot, refresh
    http_status = mapped_column(Integer, nullable=True)
    content_hash = mapped_column(String(64), nullable=True)  # SHA256
    raw_html_path = mapped_column(String(500), nullable=True)
    raw_text_path = mapped_column(String(500), nullable=True)
    screenshot_path = mapped_column(String(500), nullable=True)
    parser_version = mapped_column(String(50), nullable=True)
    success = mapped_column(Integer, default=0)  # SQLite bool
    error_message = mapped_column(Text, nullable=True)

    # Relationships
    lot = relationship("Lot", back_populates="fetches")
    parsed_fields = relationship("ParsedLotFields", back_populates="lot_fetch")

    __table_args__ = (
        Index("idx_lot_fetch_lot_id", "lot_id"),
        Index("idx_lot_fetch_success", "success"),
        Index("idx_lot_fetch_fetched_at", "fetched_at"),
    )


class LotImage(Base):
    """Images associated with a lot."""

    __tablename__ = "lot_images"

    id = mapped_column(Integer, primary_key=True)
    lot_id = mapped_column(Integer, ForeignKey("lots.id"), nullable=False)
    image_url = mapped_column(String(500), nullable=False)
    local_path = mapped_column(String(500), nullable=True)
    sort_order = mapped_column(Integer, default=0)
    fetched_at = mapped_column(DateTime, nullable=True)

    # Relationships
    lot = relationship("Lot", back_populates="images")

    __table_args__ = (Index("idx_lot_image_lot_id", "lot_id"),)


class ParsedLotFields(Base):
    """Parsed fields extracted from lot page."""

    __tablename__ = "parsed_lot_fields"

    id = mapped_column(Integer, primary_key=True)
    lot_id = mapped_column(Integer, ForeignKey("lots.id"), nullable=False)
    lot_fetch_id = mapped_column(Integer, ForeignKey("lot_fetches.id"), nullable=False)
    parser_version = mapped_column(String(50), nullable=False)
    title = mapped_column(String(500), nullable=True)
    subtitle = mapped_column(String(500), nullable=True)
    description = mapped_column(Text, nullable=True)
    category_raw = mapped_column(String(200), nullable=True)
    condition_text = mapped_column(String(200), nullable=True)
    dimensions_text = mapped_column(String(200), nullable=True)
    current_bid = mapped_column(Float, nullable=True)
    estimate_low = mapped_column(Float, nullable=True)
    estimate_high = mapped_column(Float, nullable=True)
    currency = mapped_column(String(10), nullable=True)  # e.g., SEK, EUR
    auction_end_time = mapped_column(DateTime, nullable=True)
    time_left_text = mapped_column(String(100), nullable=True)
    provenance_text = mapped_column(Text, nullable=True)
    seller_location = mapped_column(String(200), nullable=True)
    auction_house_name = mapped_column(String(200), nullable=True)
    raw_designer_mentions = mapped_column(JSON, nullable=True)
    raw_material_mentions = mapped_column(JSON, nullable=True)
    parse_confidence = mapped_column(Float, default=0.5)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    lot = relationship("Lot", back_populates="parsed_fields")
    lot_fetch = relationship("LotFetch", back_populates="parsed_fields")

    __table_args__ = (Index("idx_parsed_lot_id", "lot_id"),)


class NormalizedLotFields(Base):
    """Normalized and enriched lot fields."""

    __tablename__ = "normalized_lot_fields"

    id = mapped_column(Integer, primary_key=True)
    lot_id = mapped_column(Integer, ForeignKey("lots.id"), nullable=False)
    parsed_lot_fields_id = mapped_column(Integer, ForeignKey("parsed_lot_fields.id"), nullable=True)
    normalizer_version = mapped_column(String(50), nullable=False)
    designer_entity_id = mapped_column(Integer, ForeignKey("entities.id"), nullable=True)
    producer_entity_id = mapped_column(Integer, ForeignKey("entities.id"), nullable=True)
    object_type_id = mapped_column(String(100), nullable=True)
    era_label = mapped_column(String(100), nullable=True)
    materials = mapped_column(JSON, nullable=True)
    normalized_category = mapped_column(String(200), nullable=True)
    normalization_confidence = mapped_column(Float, default=0.5)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    lot = relationship("Lot", back_populates="normalized_fields")

    __table_args__ = (
        Index("idx_normalized_lot_id", "lot_id"),
        Index("idx_normalized_designer_id", "designer_entity_id"),
    )


class Entity(Base):
    """Designer, producer, or other named entity."""

    __tablename__ = "entities"

    id = mapped_column(Integer, primary_key=True)
    entity_type = mapped_column(String(50), nullable=False)  # designer, producer, brand, etc
    canonical_name = mapped_column(String(200), nullable=False, index=True)
    aliases = mapped_column(JSON, nullable=True)  # list of alternate names
    country = mapped_column(String(100), nullable=True)
    active_years = mapped_column(String(100), nullable=True)  # e.g., "1920-1980"
    notes = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_entity_type", "entity_type"),
        Index("idx_entity_canonical", "canonical_name"),
    )


class Comparable(Base):
    """Comparable sales or reference data."""

    __tablename__ = "comparables"

    id = mapped_column(Integer, primary_key=True)
    entity_id = mapped_column(Integer, ForeignKey("entities.id"), nullable=True)
    source_name = mapped_column(String(100), nullable=False)
    external_ref = mapped_column(String(200), nullable=True)
    title = mapped_column(String(500), nullable=False)
    object_type = mapped_column(String(200), nullable=True)
    material_tags = mapped_column(JSON, nullable=True)
    sold_price = mapped_column(Float, nullable=True)
    currency = mapped_column(String(10), nullable=True)
    sold_at = mapped_column(DateTime, nullable=True)
    country = mapped_column(String(100), nullable=True)
    confidence = mapped_column(Float, default=0.5)
    raw_payload = mapped_column(JSON, nullable=True)

    __table_args__ = (Index("idx_comparable_source", "source_name"),)


class EnrichmentRun(Base):
    """Record of running an enrichment agent on a lot."""

    __tablename__ = "enrichment_runs"

    id = mapped_column(Integer, primary_key=True)
    lot_id = mapped_column(Integer, ForeignKey("lots.id"), nullable=False)
    agent_name = mapped_column(String(100), nullable=False)
    agent_version = mapped_column(String(50), nullable=False)
    model_name = mapped_column(String(100), nullable=True)  # e.g., claude-3-5-sonnet
    prompt_version = mapped_column(String(50), nullable=True)
    input_hash = mapped_column(String(64), nullable=True)
    started_at = mapped_column(DateTime, default=datetime.utcnow)
    completed_at = mapped_column(DateTime, nullable=True)
    success = mapped_column(Integer, default=0)  # SQLite bool
    error_message = mapped_column(Text, nullable=True)

    # Relationships
    lot = relationship("Lot", back_populates="enrichment_runs")
    outputs = relationship("EnrichmentOutput", back_populates="enrichment_run", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_enrichment_lot_id", "lot_id"),
        Index("idx_enrichment_agent", "agent_name"),
    )


class EnrichmentOutput(Base):
    """Output data from an enrichment run."""

    __tablename__ = "enrichment_outputs"

    id = mapped_column(Integer, primary_key=True)
    enrichment_run_id = mapped_column(Integer, ForeignKey("enrichment_runs.id"), nullable=False)
    lot_id = mapped_column(Integer, ForeignKey("lots.id"), nullable=False)
    output_json = mapped_column(JSON, nullable=False)
    score_primary = mapped_column(Float, nullable=True)
    confidence = mapped_column(Float, nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    enrichment_run = relationship("EnrichmentRun", back_populates="outputs")

    __table_args__ = (Index("idx_enrichment_output_lot_id", "lot_id"),)


class LotScores(Base):
    """Computed scores for a lot."""

    __tablename__ = "lot_scores"

    id = mapped_column(Integer, primary_key=True)
    lot_id = mapped_column(Integer, ForeignKey("lots.id"), nullable=False, unique=True)
    scoring_version = mapped_column(String(50), nullable=False)
    arbitrage_score = mapped_column(Float, nullable=True)
    norway_gap_score = mapped_column(Float, nullable=True)
    taste_score = mapped_column(Float, nullable=True)
    wildcard_score = mapped_column(Float, nullable=True)
    urgency_score = mapped_column(Float, nullable=True)
    overall_watch_score = mapped_column(Float, nullable=True)
    explanation_json = mapped_column(JSON, nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    lot = relationship("Lot", back_populates="scores")

    __table_args__ = (
        Index("idx_scores_arbitrage", "arbitrage_score"),
        Index("idx_scores_norway_gap", "norway_gap_score"),
        Index("idx_scores_taste", "taste_score"),
        Index("idx_scores_wildcard", "wildcard_score"),
        Index("idx_scores_overall_watch", "overall_watch_score"),
    )


class UserAction(Base):
    """User action on a lot (star, skip, watch, etc)."""

    __tablename__ = "user_actions"

    id = mapped_column(Integer, primary_key=True)
    lot_id = mapped_column(Integer, ForeignKey("lots.id"), nullable=False)
    action_type = mapped_column(String(50), nullable=False)  # star, skip, watch, archive, note, bought, false_positive
    note = mapped_column(Text, nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    lot = relationship("Lot", back_populates="user_actions")

    __table_args__ = (
        Index("idx_user_action_lot_id", "lot_id"),
        Index("idx_user_action_type", "action_type"),
    )
