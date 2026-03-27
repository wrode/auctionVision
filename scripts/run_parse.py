#!/usr/bin/env python3
"""Parse fetched HTML snapshots and extract structured lot data."""
import argparse
import sys
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class StubParser:
    """Stub parser for development."""

    def __init__(self, parser_name: str):
        self.parser_name = parser_name
        self.logger = logging.getLogger(__name__)

    def parse_lot_html(self, html_content: str, lot_url: str):
        """Stub: parse lot HTML."""
        self.logger.info(f"[STUB] Parsing lot with {self.parser_name} parser")
        self.logger.info(f"[STUB] Lot URL: {lot_url}")
        self.logger.info(f"[STUB] HTML length: {len(html_content)} chars")
        return {
            "title": "[STUB] Title not parsed",
            "description": "[STUB] Description not parsed",
            "estimated_price": None,
            "lot_number": None,
            "images": [],
            "condition": None,
        }


def get_parser(parser_name: str):
    """Get parser instance."""
    try:
        from backend.parsing.parser_factory import get_parser as real_get_parser
        return real_get_parser(parser_name)
    except (ImportError, ModuleNotFoundError):
        logger.warning(f"backend.parsing not available, using stub parser for {parser_name}")
        return StubParser(parser_name)


def load_snapshot(snapshot_path: Path) -> str:
    """Load HTML snapshot from file."""
    try:
        with open(snapshot_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"Snapshot not found: {snapshot_path}")
        raise
    except Exception as e:
        logger.error(f"Failed to load snapshot {snapshot_path}: {e}")
        raise


def save_parsed_data(lot_id: str, parsed_data: dict):
    """Save parsed data to database or file."""
    logger.info(f"[STUB] Would save parsed data for lot {lot_id}")
    logger.info(f"[STUB] Parsed fields: {list(parsed_data.keys())}")
    # In a real implementation, this would save to database or JSON file


async def parse_lot(lot_id: str, snapshot_path: str = None):
    """Parse a single lot."""
    if snapshot_path is None:
        snapshot_path = f"data/snapshots/{lot_id}.html"

    snapshot_file = Path(snapshot_path)
    logger.info(f"Parsing lot {lot_id} from {snapshot_file}")

    try:
        html_content = load_snapshot(snapshot_file)
    except Exception as e:
        logger.error(f"Cannot parse lot without snapshot: {e}")
        return

    # Stub: guess parser from lot ID or config
    parser = get_parser("auctionet")

    lot_url = f"https://auctionet.com/lot/{lot_id}"
    parsed_data = parser.parse_lot_html(html_content, lot_url)

    logger.info(f"Parsed lot {lot_id}: {len(parsed_data)} fields extracted")
    save_parsed_data(lot_id, parsed_data)


async def parse_all_lots():
    """Parse all lots in data/snapshots."""
    snapshots_dir = Path("data/snapshots")
    if not snapshots_dir.exists():
        logger.warning(f"Snapshots directory not found: {snapshots_dir}")
        return

    html_files = list(snapshots_dir.glob("*.html"))
    logger.info(f"Found {len(html_files)} snapshot files")

    for snapshot_file in html_files:
        lot_id = snapshot_file.stem
        try:
            await parse_lot(lot_id, str(snapshot_file))
        except Exception as e:
            logger.error(f"Failed to parse {lot_id}: {e}")

    logger.info("All parsing complete")


def main():
    parser = argparse.ArgumentParser(
        description="Parse fetched HTML snapshots and extract lot data"
    )
    subparsers = parser.add_subparsers(dest="command")

    lot_parser = subparsers.add_parser(
        "lot",
        help="Parse a single lot"
    )
    lot_parser.add_argument("lot_id", help="Lot ID to parse")
    lot_parser.add_argument(
        "--snapshot",
        help="Path to snapshot HTML file (default: data/snapshots/{lot_id}.html)"
    )

    all_parser = subparsers.add_parser(
        "all",
        help="Parse all snapshot files in data/snapshots/"
    )

    args = parser.parse_args()

    import asyncio

    if args.command == "lot":
        asyncio.run(parse_lot(args.lot_id, args.snapshot))
    elif args.command == "all":
        asyncio.run(parse_all_lots())
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
