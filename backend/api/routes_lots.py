"""Lots API routes."""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Lot, LotFetch, LotScores, UserAction, ParsedLotFields
from backend.schemas import (
    EnrichmentOutputDetail,
    FetchHistoryItem,
    LotCard,
    LotDetail,
    ParsedFieldsDetail,
    UserActionCreate,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _build_lot_card(lot: Lot, db: Session) -> LotCard:
    """Build a LotCard from a Lot model."""
    # Get latest parsed fields
    parsed = db.query(ParsedLotFields).filter(
        ParsedLotFields.lot_id == lot.id
    ).order_by(ParsedLotFields.created_at.desc()).first()

    # Get scores
    scores_record = db.query(LotScores).filter(LotScores.lot_id == lot.id).first()

    # Get user actions
    user_actions_records = db.query(UserAction).filter(
        UserAction.lot_id == lot.id
    ).all()

    # Get first image
    image_url = None
    if lot.images:
        image_url = lot.images[0].image_url

    # Build card
    return LotCard(
        id=lot.id,
        title=parsed.title if parsed else lot.canonical_title or "Unknown",
        source=lot.source.name if lot.source else "unknown",
        image_url=image_url,
        current_bid=parsed.current_bid if parsed else None,
        estimate_low=parsed.estimate_low if parsed else None,
        estimate_high=parsed.estimate_high if parsed else None,
        currency=parsed.currency if parsed else None,
        auction_end_time=parsed.auction_end_time if parsed else None,
        time_remaining=parsed.time_left_text if parsed else None,
        scores={
            "arbitrage": scores_record.arbitrage_score if scores_record else None,
            "taste": scores_record.taste_score if scores_record else None,
            "wildcard": scores_record.wildcard_score if scores_record else None,
            "urgency": scores_record.urgency_score if scores_record else None,
        },
        user_actions=[a.action_type for a in user_actions_records],
    )


def _build_lot_detail(lot: Lot, db: Session) -> LotDetail:
    """Build a LotDetail from a Lot model."""
    card = _build_lot_card(lot, db)
    detail = LotDetail(**card.model_dump())
    detail.lot_url = lot.lot_url

    # Get parsed fields
    parsed = db.query(ParsedLotFields).filter(
        ParsedLotFields.lot_id == lot.id
    ).order_by(ParsedLotFields.created_at.desc()).first()

    if parsed:
        detail.parsed_fields = ParsedFieldsDetail(
            parser_version=parsed.parser_version,
            title=parsed.title,
            subtitle=parsed.subtitle,
            description=parsed.description,
            category_raw=parsed.category_raw,
            condition_text=parsed.condition_text,
            dimensions_text=parsed.dimensions_text,
            current_bid=parsed.current_bid,
            estimate_low=parsed.estimate_low,
            estimate_high=parsed.estimate_high,
            currency=parsed.currency,
            auction_end_time=parsed.auction_end_time,
            time_left_text=parsed.time_left_text,
            provenance_text=parsed.provenance_text,
            seller_location=parsed.seller_location,
            auction_house_name=parsed.auction_house_name,
            raw_designer_mentions=parsed.raw_designer_mentions,
            raw_material_mentions=parsed.raw_material_mentions,
            parse_confidence=parsed.parse_confidence,
        )

    # Get enrichments
    detail.enrichments = [
        EnrichmentOutputDetail(
            agent_name=run.agent_name,
            agent_version=run.agent_version,
            completed_at=run.completed_at,
            output_json=output.output_json,
            confidence=output.confidence,
        )
        for run in lot.enrichment_runs
        for output in run.outputs
    ]

    # Get fetch history
    detail.fetch_history = [
        FetchHistoryItem(
            fetched_at=fetch.fetched_at,
            fetch_type=fetch.fetch_type,
            http_status=fetch.http_status,
            success=bool(fetch.success),
            error_message=fetch.error_message,
        )
        for fetch in sorted(lot.fetches, key=lambda f: f.fetched_at, reverse=True)
    ]

    # Get images
    detail.images = [
        {"url": img.image_url, "local_path": img.local_path, "sort_order": img.sort_order}
        for img in sorted(lot.images, key=lambda i: i.sort_order)
    ]

    return detail


@router.get("", response_model=dict)
async def list_lots(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    source: Optional[str] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
) -> dict:
    """List lots with pagination and filters."""
    query = db.query(Lot)

    if source:
        query = query.join(Lot.source).filter(Lot.source.name == source)

    if status:
        query = query.filter(Lot.status == status)

    if category:
        query = query.join(ParsedLotFields).filter(
            ParsedLotFields.category_raw == category
        )

    total = query.count()
    lots = query.order_by(Lot.updated_at.desc()).offset(skip).limit(limit).all()

    cards = [_build_lot_card(lot, db) for lot in lots]
    return {"lots": cards, "total": total, "skip": skip, "limit": limit}


@router.get("/{lot_id}", response_model=LotDetail)
async def get_lot(lot_id: int, db: Session = Depends(get_db)) -> LotDetail:
    """Get detailed information about a specific lot."""
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")

    return _build_lot_detail(lot, db)


@router.get("/{lot_id}/history", response_model=dict)
async def get_lot_history(lot_id: int, db: Session = Depends(get_db)) -> dict:
    """Get fetch history for a lot."""
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")

    history = [
        FetchHistoryItem(
            fetched_at=fetch.fetched_at,
            fetch_type=fetch.fetch_type,
            http_status=fetch.http_status,
            success=bool(fetch.success),
            error_message=fetch.error_message,
        )
        for fetch in sorted(lot.fetches, key=lambda f: f.fetched_at, reverse=True)
    ]

    return {"lot_id": lot_id, "fetch_history": history}


@router.get("/{lot_id}/scores", response_model=dict)
async def get_lot_scores(lot_id: int, db: Session = Depends(get_db)) -> dict:
    """Get scores for a lot."""
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")

    scores = db.query(LotScores).filter(LotScores.lot_id == lot_id).first()
    if not scores:
        return {
            "lot_id": lot_id,
            "arbitrage_score": None,
            "taste_score": None,
            "wildcard_score": None,
            "urgency_score": None,
            "overall_watch_score": None,
        }

    return {
        "lot_id": lot_id,
        "arbitrage_score": scores.arbitrage_score,
        "taste_score": scores.taste_score,
        "wildcard_score": scores.wildcard_score,
        "urgency_score": scores.urgency_score,
        "overall_watch_score": scores.overall_watch_score,
        "explanation": scores.explanation_json,
    }


@router.get("/{lot_id}/enrichments", response_model=dict)
async def get_lot_enrichments(lot_id: int, db: Session = Depends(get_db)) -> dict:
    """Get enrichment data for a lot."""
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")

    enrichments = [
        {
            "agent_name": run.agent_name,
            "agent_version": run.agent_version,
            "completed_at": run.completed_at,
            "success": bool(run.success),
            "outputs": [output.output_json for output in run.outputs],
        }
        for run in lot.enrichment_runs
    ]

    return {"lot_id": lot_id, "enrichments": enrichments}


@router.post("/{lot_id}/action", response_model=dict)
async def create_user_action(
    lot_id: int,
    action: UserActionCreate,
    db: Session = Depends(get_db),
) -> dict:
    """Create a user action on a lot."""
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")

    user_action = UserAction(
        lot_id=lot_id,
        action_type=action.action_type,
        note=action.note,
    )
    db.add(user_action)
    db.commit()
    db.refresh(user_action)

    return {
        "id": user_action.id,
        "lot_id": lot_id,
        "action_type": user_action.action_type,
        "note": user_action.note,
        "created_at": user_action.created_at,
    }
