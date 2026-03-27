"""Curated views API routes."""

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.api.routes_lots import _build_lot_card
from backend.database import get_db
from backend.models import Lot, LotScores, UserAction, ParsedLotFields
from backend.schemas import LotCard, ViewResponse

logger = logging.getLogger(__name__)

router = APIRouter()


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


@router.get("/norway-arbitrage", response_model=ViewResponse)
async def view_norway_arbitrage(
    limit: int = Query(50, ge=1, le=1000),
    min_score: float = Query(0.5, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
) -> ViewResponse:
    """Get lots sorted by Norway gap score."""
    query = (
        db.query(Lot)
        .join(LotScores, Lot.id == LotScores.lot_id)
        .filter(Lot.status == "active")
        .filter(LotScores.norway_gap_score >= min_score)
        .order_by(LotScores.norway_gap_score.desc())
        .limit(limit)
    )

    lots = query.all()
    cards = [_build_lot_card(lot, db) for lot in lots]

    return ViewResponse(
        lots=cards,
        total=len(cards),
        view_name="norway-arbitrage",
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
