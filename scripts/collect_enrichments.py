#!/usr/bin/env python3
"""Collect enrichment JSON results from agent output files and save to data/enrichments/."""
import json
import re
import sys
from pathlib import Path

TASKS_DIR = Path("/private/tmp/claude-501/-Users-williamrode-Dropbox-01-Work-Current-Icevision-site-auctionVision/08f72fa5-a629-4f7e-9997-a00b92fb9bb5/tasks")
OUTPUT_DIR = Path("data/enrichments")


def extract_json_from_output(text: str) -> dict | None:
    """Extract JSON object from agent output text."""
    # Try to find JSON block in markdown code fence
    match = re.search(r"```json?\s*\n(.*?)\n```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find raw JSON object
    # Find the first { and last }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    return None


def extract_assistant_text(raw: str) -> str:
    """Extract assistant message text from JSONL conversation format."""
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


def collect():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_files = sorted(TASKS_DIR.glob("*.output"))
    print(f"Found {len(output_files)} output files")

    collected = 0
    failed = 0
    all_enrichments = []

    for f in output_files:
        raw = f.read_text()
        if not raw.strip():
            continue

        # Extract assistant text from JSONL conversation format
        text = extract_assistant_text(raw)
        if not text:
            text = raw  # fallback to raw content

        data = extract_json_from_output(text)
        if data and ("lot_id" in data or "title" in data):
            lot_id = data["lot_id"]
            out_path = OUTPUT_DIR / f"{lot_id}.json"
            out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
            all_enrichments.append(data)
            collected += 1
        else:
            failed += 1
            # Save raw for debugging
            debug_path = OUTPUT_DIR / f"_failed_{f.stem}.txt"
            debug_path.write_text(text[:2000])

    # Save combined file
    combined_path = OUTPUT_DIR / "_all_enrichments.json"
    combined_path.write_text(json.dumps(all_enrichments, indent=2, ensure_ascii=False))

    print(f"Collected: {collected}")
    print(f"Failed: {failed}")
    print(f"Combined: {combined_path}")

    # Print summary stats
    if all_enrichments:
        confirmed = sum(1 for e in all_enrichments if e.get("designer", {}).get("attribution_type") == "confirmed")
        probably = sum(1 for e in all_enrichments if e.get("designer", {}).get("attribution_type") in ("probably", "attributed_to"))
        unknown = sum(1 for e in all_enrichments if e.get("designer", {}).get("attribution_type") in ("unknown", "style_of", None))
        print(f"\nAttribution breakdown:")
        print(f"  Confirmed designer: {confirmed}")
        print(f"  Probable/attributed: {probably}")
        print(f"  Unknown/style_of: {unknown}")


if __name__ == "__main__":
    collect()
