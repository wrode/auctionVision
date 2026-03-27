"""Job triggering API routes."""

import logging
import uuid

from fastapi import APIRouter, HTTPException

from backend.schemas import JobTriggerResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/fetch/source/{source_name}", response_model=JobTriggerResponse)
async def trigger_broad_crawl(source_name: str) -> JobTriggerResponse:
    """Trigger a broad crawl of an auction source."""
    job_id = str(uuid.uuid4())
    logger.info(f"Triggered broad crawl for {source_name} with job_id {job_id}")

    return JobTriggerResponse(
        job_id=job_id,
        status="queued",
        message=f"Broad crawl job queued for source {source_name}",
    )


@router.post("/fetch/lot/{lot_id}", response_model=JobTriggerResponse)
async def trigger_lot_fetch(lot_id: int) -> JobTriggerResponse:
    """Trigger fetching a single lot."""
    job_id = str(uuid.uuid4())
    logger.info(f"Triggered lot fetch for lot_id {lot_id} with job_id {job_id}")

    return JobTriggerResponse(
        job_id=job_id,
        status="queued",
        message=f"Lot fetch job queued for lot {lot_id}",
    )


@router.post("/parse/{lot_fetch_id}", response_model=JobTriggerResponse)
async def trigger_parse(lot_fetch_id: int) -> JobTriggerResponse:
    """Trigger parsing a lot fetch."""
    job_id = str(uuid.uuid4())
    logger.info(f"Triggered parse for lot_fetch_id {lot_fetch_id} with job_id {job_id}")

    return JobTriggerResponse(
        job_id=job_id,
        status="queued",
        message=f"Parse job queued for lot_fetch {lot_fetch_id}",
    )


@router.post("/enrich/{lot_id}", response_model=JobTriggerResponse)
async def trigger_enrichment(lot_id: int) -> JobTriggerResponse:
    """Trigger enrichment of a lot."""
    job_id = str(uuid.uuid4())
    logger.info(f"Triggered enrichment for lot_id {lot_id} with job_id {job_id}")

    return JobTriggerResponse(
        job_id=job_id,
        status="queued",
        message=f"Enrichment job queued for lot {lot_id}",
    )


@router.post("/rescore/{lot_id}", response_model=JobTriggerResponse)
async def trigger_rescore(lot_id: int) -> JobTriggerResponse:
    """Trigger rescoring a lot."""
    job_id = str(uuid.uuid4())
    logger.info(f"Triggered rescore for lot_id {lot_id} with job_id {job_id}")

    return JobTriggerResponse(
        job_id=job_id,
        status="queued",
        message=f"Rescore job queued for lot {lot_id}",
    )
