#!/usr/bin/env python3
"""Collect research results from agent outputs, save to data/research/, and update DB."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

TASKS_DIR = Path("/private/tmp/claude-501/-Users-williamrode-Dropbox-01-Work-Current-Icevision-site-auctionVision/08f72fa5-a629-4f7e-9997-a00b92fb9bb5/tasks")
OUTPUT_DIR = Path("data/research")


def extract_assistant_text(raw: str) -> str:
    texts = []
    for line in raw.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if obj.get("type") == "assistant":
                msg = obj.get("message", {})
                content = msg.get("content", "")
                if isinstance(content, str):
                    texts.append(content)
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            texts.append(block.get("text", ""))
        except json.JSONDecodeError:
            continue
    return "\n".join(texts)


def extract_json_from_text(text: str) -> dict | None:
    # Try markdown code fence
    match = re.search(r"```json?\s*\n(.*?)\n```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # Try raw JSON
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    return None


def collect():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_files = sorted(TASKS_DIR.glob("*.output"))

    # Load existing enrichment lot IDs to know which are research vs enrichment
    enrichment_ids = set()
    for f in Path("data/enrichments").glob("*.json"):
        if not f.name.startswith("_"):
            enrichment_ids.add(f.stem)

    collected = 0
    failed = 0
    all_research = []

    for f in output_files:
        raw = f.read_text()
        if not raw.strip():
            continue

        text = extract_assistant_text(raw)
        if not text:
            continue

        data = extract_json_from_text(text)
        if not data:
            continue

        # Identify as research (has comparables or grounded_estimate) vs enrichment
        is_research = "comparables" in data or "grounded_estimate" in data or "search_terms_used" in data
        if not is_research:
            continue

        lot_id = data.get("lot_id")
        if not lot_id:
            # Try to extract from the prompt in the file
            for line in raw.strip().splitlines()[:5]:
                try:
                    obj = json.loads(line)
                    if obj.get("type") == "user":
                        msg_content = obj.get("message", {}).get("content", "")
                        m = re.search(r'lot_id["\s:]+(\d+)', msg_content)
                        if m:
                            lot_id = m.group(1)
                            data["lot_id"] = lot_id
                            break
                except:
                    continue

        if not lot_id:
            failed += 1
            continue

        out_path = OUTPUT_DIR / f"{lot_id}.json"
        out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        all_research.append(data)
        collected += 1

    # Save combined
    combined = OUTPUT_DIR / "_all_research.json"
    combined.write_text(json.dumps(all_research, indent=2, ensure_ascii=False))

    print(f"Collected: {collected} research results")
    print(f"Failed: {failed}")
    print(f"Combined: {combined}")

    # Stats
    if all_research:
        with_comps = sum(1 for r in all_research if r.get("comparables"))
        with_estimate = sum(1 for r in all_research if r.get("grounded_estimate", {}).get("low"))
        avg_comps = sum(len(r.get("comparables", [])) for r in all_research) / len(all_research)
        print(f"\nWith comparables: {with_comps}")
        print(f"With grounded estimate: {with_estimate}")
        print(f"Avg comparables per lot: {avg_comps:.1f}")


def update_db():
    """Update database with grounded estimates from research."""
    from backend.database import SessionLocal
    from backend.models import Lot, LotScores
    from sqlalchemy.orm.attributes import flag_modified

    db = SessionLocal()
    updated = 0

    for f in OUTPUT_DIR.glob("*.json"):
        if f.name.startswith("_"):
            continue

        ext_id = f.stem
        data = json.loads(f.read_text())

        lot = db.query(Lot).filter(Lot.external_lot_id == ext_id).first()
        if not lot:
            continue

        grounded = data.get("grounded_estimate", {})
        low = grounded.get("low")
        high = grounded.get("high")
        basis = grounded.get("basis", "")

        if not low:
            continue

        scores = db.query(LotScores).filter(LotScores.lot_id == lot.id).first()
        if scores and scores.explanation_json:
            expl = dict(scores.explanation_json)
            expl["ai_value_low"] = low
            expl["ai_value_high"] = high
            expl["ai_value_basis"] = basis
            expl["research_confidence"] = data.get("research_confidence")
            expl["comparables_count"] = len(data.get("comparables", []))

            # Also store dealer and auction ranges
            dealer = data.get("dealer_price_range", {})
            auction = data.get("auction_price_range", {})
            retail = data.get("retail_new_price", {})
            norway = data.get("norway_retail_price", {})

            if dealer.get("low"):
                expl["dealer_price_low"] = dealer["low"]
                expl["dealer_price_high"] = dealer.get("high")
            if auction.get("low"):
                expl["auction_price_low"] = auction["low"]
                expl["auction_price_high"] = auction.get("high")
            if isinstance(retail, dict) and retail.get("price"):
                expl["retail_new_price"] = retail["price"]
                expl["retail_new_currency"] = retail.get("currency", "EUR")
            if isinstance(norway, dict) and norway.get("price"):
                expl["norway_retail_price"] = norway["price"]
                expl["norway_retail_currency"] = norway.get("currency", "NOK")

            scores.explanation_json = expl
            flag_modified(scores, "explanation_json")
            updated += 1

    db.commit()
    db.close()
    print(f"\nUpdated {updated} lots with grounded research estimates")


if __name__ == "__main__":
    collect()
    update_db()
