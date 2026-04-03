"""Configuration management for Auction Vision."""

import logging
import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


class Settings:
    """Application settings loaded from .env and environment variables."""

    def __init__(self):
        """Initialize settings from environment."""
        # Load .env file
        load_dotenv(".env")

        # Database
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///data/auction.db")

        # Data storage
        self.data_dir = os.getenv("DATA_DIR", "data")

        # Logging
        self.log_level = os.getenv("LOG_LEVEL", "INFO")

        # API
        self.api_port = int(os.getenv("API_PORT", "8000"))
        self.api_host = os.getenv("API_HOST", "0.0.0.0")

        # Auction sources
        self.auctionet_base_url = os.getenv("AUCTIONET_BASE_URL", "https://auctionet.com")
        self.auctionet_rate_limit_requests = int(os.getenv("AUCTIONET_RATE_LIMIT_REQUESTS", "10"))
        self.auctionet_rate_limit_period = int(os.getenv("AUCTIONET_RATE_LIMIT_PERIOD", "60"))

        # Job scheduling
        self.broad_crawl_interval_minutes = int(os.getenv("BROAD_CRAWL_INTERVAL_MINUTES", "60"))
        self.watchlist_refresh_interval_minutes = int(os.getenv("WATCHLIST_REFRESH_INTERVAL_MINUTES", "15"))
        self.ending_soon_refresh_interval_minutes = int(os.getenv("ENDING_SOON_REFRESH_INTERVAL_MINUTES", "5"))
        self.ending_soon_threshold_hours = int(os.getenv("ENDING_SOON_THRESHOLD_HOURS", "2"))
        self.enrichment_queue_interval_minutes = int(os.getenv("ENRICHMENT_QUEUE_INTERVAL_MINUTES", "10"))

        # Enrichment
        self.claude_api_key = os.getenv("CLAUDE_API_KEY", "")
        self.claude_model = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")

        # Feature flags
        self.enable_image_download = os.getenv("ENABLE_IMAGE_DOWNLOAD", "true").lower() == "true"
        self.enable_enrichment = os.getenv("ENABLE_ENRICHMENT", "true").lower() == "true"
        self.enable_scheduler = os.getenv("ENABLE_SCHEDULER", "true").lower() == "true"
        self.enable_visual_triage = os.getenv("ENABLE_VISUAL_TRIAGE", "false").lower() == "true"

    @property
    def snapshots_dir(self) -> Path:
        """Get snapshots directory path."""
        return Path(self.data_dir) / "snapshots"

    @property
    def images_dir(self) -> Path:
        """Get images directory path."""
        return Path(self.data_dir) / "images"

    def ensure_dirs(self) -> None:
        """Create necessary directories if they don't exist."""
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(parents=True, exist_ok=True)
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)


def load_yaml_config(filename: str, config_dir: str = "config") -> dict[str, Any]:
    """Load YAML configuration file from config directory.

    Args:
        filename: Name of the YAML file (e.g., "scoring.yaml")
        config_dir: Path to config directory

    Returns:
        Parsed YAML as dictionary
    """
    config_path = Path(config_dir) / filename
    if not config_path.exists():
        return {}

    with open(config_path, "r") as f:
        return yaml.safe_load(f) or {}


def setup_logging(log_level: str = "INFO") -> None:
    """Configure logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


# Global settings instance
settings = Settings()
