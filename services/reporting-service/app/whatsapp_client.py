"""
WhatsApp Business Cloud API client.

Mirrors the pattern from ai-agent-service/app/llm_client.py: if credentials
aren't configured, every call degrades to a deterministic mock instead of
raising — so the full report -> send -> retry -> delivery-status pipeline is
testable with zero external dependencies. In mock mode, sends always
"succeed" immediately with a synthesized wamid; this is intentional (there's
no meaningful failure to simulate without a real API to fail against), and
is clearly reported via the `mode` field on every result so it's never
mistaken for a real delivery in logs or responses.

Real mode calls https://graph.facebook.com — outside this sandbox's network
allowlist, so it is implemented correctly per the Meta Cloud API but could
not be exercised end-to-end here; test it against your own WhatsApp Business
account credentials.
"""
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger("reporting.whatsapp_client")


@dataclass
class SendResult:
    success: bool
    external_message_id: Optional[str] = None
    error: Optional[str] = None
    mode: str = "MOCK"  # "MOCK" | "LIVE"


def _send_once(text: str) -> SendResult:
    if not settings.whatsapp_access_token:
        mock_id = f"mock-wamid-{uuid.uuid4()}"
        logger.info("MOCK WhatsApp send (no access token configured). Would send: %s", text[:120])
        return SendResult(success=True, external_message_id=mock_id, mode="MOCK")

    url = f"https://graph.facebook.com/{settings.whatsapp_api_version}/{settings.whatsapp_phone_number_id}/messages"
    try:
        resp = httpx.post(
            url,
            headers={
                "Authorization": f"Bearer {settings.whatsapp_access_token}",
                "Content-Type": "application/json",
            },
            json={
                "messaging_product": "whatsapp",
                "to": settings.whatsapp_to_number,
                "type": "template",
                "template": {
                    "name": settings.whatsapp_template_name,
                    "language": {"code": "en_US"},
                    "components": [
                        {
                            "type": "body",
                            "parameters": [{"type": "text", "text": text}],
                        }
                    ],
                },
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()
        wamid = data.get("messages", [{}])[0].get("id")
        if not wamid:
            return SendResult(success=False, error="No message id in WhatsApp response", mode="LIVE")
        return SendResult(success=True, external_message_id=wamid, mode="LIVE")
    except httpx.HTTPStatusError as exc:
        return SendResult(success=False, error=f"HTTP {exc.response.status_code}: {exc.response.text[:300]}", mode="LIVE")
    except Exception as exc:  # noqa: BLE001
        return SendResult(success=False, error=str(exc), mode="LIVE")


def send_with_retry(text: str) -> tuple[SendResult, int]:
    """
    Attempts to send, retrying with exponential backoff up to
    settings.max_send_attempts times. Returns (final_result, attempts_made).
    In MOCK mode this always succeeds on the first attempt — there is
    nothing meaningful to retry against without a real API.
    """
    last_result = None
    for attempt in range(1, settings.max_send_attempts + 1):
        result = _send_once(text)
        last_result = result
        if result.success:
            return result, attempt
        if attempt < settings.max_send_attempts:
            backoff = settings.retry_backoff_base_seconds * (2 ** (attempt - 1))
            logger.warning("WhatsApp send attempt %d failed (%s); retrying in %.1fs", attempt, result.error, backoff)
            time.sleep(backoff)
    return last_result, settings.max_send_attempts
