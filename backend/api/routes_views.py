"""Curated views API routes."""

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.api.routes_lots import _build_lot_card
from backend.database import get_db
from backend.models import Lot, LotScores, UserAction, ParsedLotFields, WantedListing
from backend.schemas import LotCard, ViewResponse, WantedListingCard, WantedViewResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/all-lots", response_model=ViewResponse)
async def view_all_lots(
    limit: int = Query(2000, ge=1, le=5000),
    db: Session = Depends(get_db),
) -> ViewResponse:
    """Get all active lots for calendar and aggregate views."""
    query = (
        db.query(Lot)
        .join(ParsedLotFields, Lot.id == ParsedLotFields.lot_id)
        .filter(Lot.status == "active")
        .order_by(Lot.id.desc())
        .limit(limit)
    )

    lots = query.all()
    cards = [_build_lot_card(lot, db) for lot in lots]

    return ViewResponse(
        lots=cards,
        total=len(cards),
        view_name="all-lots",
        filters={},
    )


@router.get("/best-buys", response_model=ViewResponse)
async def view_best_buys(
    limit: int = Query(50, ge=1, le=1000),
    min_score: float = Query(0.5, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
) -> ViewResponse:
    """Get lots sorted by arbitrage score (best buys)."""
    query = (
        db.query(Lot)
        .join(LotScores, Lot.id == LotScores.lot_id)
        .filter(Lot.status == "active")
        .filter(LotScores.arbitrage_score >= min_score)
        .order_by(LotScores.arbitrage_score.desc())
        .limit(limit)
    )

    lots = query.all()
    cards = [_build_lot_card(lot, db) for lot in lots]

    return ViewResponse(
        lots=cards,
        total=len(cards),
        view_name="best-buys",
        filters={"min_score": min_score},
    )


@router.get("/resale-arbitrage", response_model=ViewResponse)
async def view_resale_arbitrage(
    limit: int = Query(50, ge=1, le=1000),
    min_score: float = Query(0.5, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
) -> ViewResponse:
    """Get lots sorted by resale arbitrage score."""
    query = (
        db.query(Lot)
        .join(LotScores, Lot.id == LotScores.lot_id)
        .filter(Lot.status == "active")
        .filter(LotScores.resale_arb_score >= min_score)
        .order_by(LotScores.resale_arb_score.desc())
        .limit(limit)
    )

    lots = query.all()
    cards = [_build_lot_card(lot, db) for lot in lots]

    return ViewResponse(
        lots=cards,
        total=len(cards),
        view_name="resale-arbitrage",
        filters={"min_score": min_score},
    )


@router.get("/taste", response_model=ViewResponse)
async def view_taste(
    limit: int = Query(50, ge=1, le=1000),
    min_score: float = Query(0.5, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
) -> ViewResponse:
    """Get lots sorted by taste score."""
    query = (
        db.query(Lot)
        .join(LotScores, Lot.id == LotScores.lot_id)
        .filter(Lot.status == "active")
        .filter(LotScores.taste_score >= min_score)
        .order_by(LotScores.taste_score.desc())
        .limit(limit)
    )

    lots = query.all()
    cards = [_build_lot_card(lot, db) for lot in lots]

    return ViewResponse(
        lots=cards,
        total=len(cards),
        view_name="taste",
        filters={"min_score": min_score},
    )


@router.get("/wildcards", response_model=ViewResponse)
async def view_wildcards(
    limit: int = Query(50, ge=1, le=1000),
    min_score: float = Query(0.5, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
) -> ViewResponse:
    """Get lots sorted by wildcard score."""
    query = (
        db.query(Lot)
        .join(LotScores, Lot.id == LotScores.lot_id)
        .filter(Lot.status == "active")
        .filter(LotScores.wildcard_score >= min_score)
        .order_by(LotScores.wildcard_score.desc())
        .limit(limit)
    )

    lots = query.all()
    cards = [_build_lot_card(lot, db) for lot in lots]

    return ViewResponse(
        lots=cards,
        total=len(cards),
        view_name="wildcards",
        filters={"min_score": min_score},
    )


@router.get("/ending-soon", response_model=ViewResponse)
async def view_ending_soon(
    hours: int = Query(2, ge=1, le=24),
    limit: int = Query(50, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> ViewResponse:
    """Get lots ending within specified hours, sorted by end time."""
    now = datetime.utcnow()
    cutoff = now + timedelta(hours=hours)

    query = (
        db.query(Lot)
        .join(ParsedLotFields, Lot.id == ParsedLotFields.lot_id)
        .filter(Lot.status == "active")
        .filter(ParsedLotFields.auction_end_time > now)
        .filter(ParsedLotFields.auction_end_time <= cutoff)
        .order_by(ParsedLotFields.auction_end_time.asc())
        .limit(limit)
    )

    lots = query.all()
    cards = [_build_lot_card(lot, db) for lot in lots]

    return ViewResponse(
        lots=cards,
        total=len(cards),
        view_name="ending-soon",
        filters={"hours": hours},
    )


@router.get("/watchlist", response_model=ViewResponse)
async def view_watchlist(
    limit: int = Query(50, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> ViewResponse:
    """Get lots marked as watched."""
    query = (
        db.query(Lot)
        .join(UserAction, Lot.id == UserAction.lot_id)
        .filter(Lot.status == "active")
        .filter(UserAction.action_type == "watch")
        .order_by(Lot.updated_at.desc())
        .limit(limit)
        .distinct()
    )

    lots = query.all()
    cards = [_build_lot_card(lot, db) for lot in lots]

    return ViewResponse(
        lots=cards,
        total=len(cards),
        view_name="watchlist",
        filters={},
    )


@router.get("/wanted", response_model=WantedViewResponse)
async def view_wanted(
    limit: int = Query(100, ge=1, le=1000),
    category: Optional[str] = None,
    db: Session = Depends(get_db),
) -> WantedViewResponse:
    """Get high-value Finn wanted listings (demand signals)."""
    query = (
        db.query(WantedListing)
        .filter(WantedListing.status == "active")
        .filter(WantedListing.is_high_value == 1)
    )

    if category:
        query = query.filter(WantedListing.category == category)

    query = query.order_by(WantedListing.last_seen_at.desc()).limit(limit)

    listings = query.all()
    cards = [
        WantedListingCard(
            id=w.id,
            finn_id=w.finn_id,
            url=w.url,
            title=w.title,
            offered_price=w.offered_price,
            currency=w.currency or "NOK",
            brand=w.brand,
            designer=w.designer,
            category=w.category,
            buyer_location=w.buyer_location,
            image_urls=w.image_urls,
            published_text=w.published_text,
            match_reason=w.match_reason,
        )
        for w in listings
    ]

    return WantedViewResponse(listings=cards, total=len(cards))
