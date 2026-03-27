"""FastAPI application setup and configuration."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes_jobs import router as jobs_router
from backend.api.routes_lots import router as lots_router
from backend.api.routes_views import router as views_router
from backend.config import settings, setup_logging
from backend.database import init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    # Startup
    logger.info("Initializing database...")
    settings.ensure_dirs()
    init_db()
    logger.info("Application startup complete")
    yield
    # Shutdown
    logger.info("Application shutting down")


# Create FastAPI app
app = FastAPI(
    title="Auction Vision API",
    description="Local auction sourcing engine",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure logging
setup_logging(settings.log_level)

# CORS middleware (allow all origins for local dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routers
app.include_router(lots_router, prefix="/api/lots", tags=["lots"])
app.include_router(views_router, prefix="/api/views", tags=["views"])
app.include_router(jobs_router, prefix="/api/jobs", tags=["jobs"])


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Auction Vision API", "version": "0.1.0"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )
