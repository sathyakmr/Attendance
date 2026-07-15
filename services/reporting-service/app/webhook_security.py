"""
Verifies the X-Hub-Signature-256 header Meta attaches to every webhook
delivery, per the Cloud API docs. If whatsapp_app_secret isn't configured
(local/dev without real WhatsApp credentials), verification is skipped and
a warning is logged — this mirrors the rest of the system's
deterministic/mock fallback pattern, but is called out explicitly since
skipping signature verification is a real security tradeoff, not a neutral
default, and should never happen in a production deployment.
"""
import hashlib
import hmac
import logging

from app.config import settings

logger = logging.getLogger("reporting.webhook_security")


def verify_signature(raw_body: bytes, signature_header: str) -> bool:
    if not settings.whatsapp_app_secret:
        logger.warning(
            "WHATSAPP_APP_SECRET not configured — skipping webhook signature "
            "verification. This is only acceptable in local/dev; configure "
            "the app secret before exposing this webhook publicly."
        )
        return True

    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected_signature = signature_header.removeprefix("sha256=")
    computed = hmac.new(
        settings.whatsapp_app_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(computed, expected_signature)
