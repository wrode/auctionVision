"""Visual triage: download one image and ask Claude if the lot looks interesting."""

import base64
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

TRIAGE_PROMPT = (
    "You are a furniture auction triage filter for a resale buyer. "
    "Look at this auction lot image. Is it visually distinctive, unusual, "
    "sculptural, made of high-quality materials, or potentially high-value "
    "— even without a named designer? "
    "Answer YES or NO on the first line, followed by one short reason."
)


def download_primary_image(image_urls: list[str]) -> tuple[Optional[bytes], Optional[str]]:
    """Download the first available image.

    Returns:
        (image_bytes, media_type) or (None, None) on failure.
    """
    if not image_urls:
        return None, None

    url = image_urls[0]
    # Prefer large version
    if "medium_" in url:
        url = url.replace("medium_", "large_")
    elif "thumb_" in url:
        url = url.replace("thumb_", "large_")

    try:
        resp = httpx.get(url, timeout=10.0, follow_redirects=True)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "image/jpeg")
        media_type = content_type.split(";")[0].strip()
        return resp.content, media_type
    except Exception as e:
        logger.debug(f"Image download failed for {url}: {e}")
        return None, None


def visual_triage(
    image_bytes: bytes,
    media_type: str,
    api_key: str,
    model: str = "claude-haiku-4-5-20251001",
    max_tokens: int = 100,
) -> tuple[str, str]:
    """Send image to Claude vision for a quick yes/no triage.

    Returns:
        ("YES", reason) or ("NO", reason)
    """
    import anthropic

    try:
        client = anthropic.Anthropic(api_key=api_key)
        b64_data = base64.standard_b64encode(image_bytes).decode("utf-8")

        message = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": TRIAGE_PROMPT,
                    },
                ],
            }],
        )

        response_text = message.content[0].text.strip()
        first_line = response_text.split("\n")[0].strip()

        if first_line.upper().startswith("YES"):
            return "YES", response_text
        else:
            return "NO", response_text

    except Exception as e:
        logger.warning(f"Visual triage API error: {e}")
        return "NO", f"error: {e}"


def run_image_triage(
    image_urls: list[str],
    api_key: str,
    model: str = "claude-haiku-4-5-20251001",
    max_tokens: int = 100,
) -> tuple[str, str]:
    """Download primary image and run visual triage. Convenience wrapper.

    Returns:
        ("YES", reason) or ("NO", reason)
    """
    image_bytes, media_type = download_primary_image(image_urls)
    if not image_bytes:
        return "NO", "no images available"

    return visual_triage(image_bytes, media_type, api_key, model, max_tokens)
