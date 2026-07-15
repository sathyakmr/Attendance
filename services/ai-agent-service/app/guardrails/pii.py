"""
PII redaction guardrail.

Employee codes and precise GPS coordinates are replaced with stable,
non-reversible-by-the-LLM placeholder tokens before any text reaches the LLM
call. The mapping is held only in trusted backend memory for the duration of
the request and used to rehydrate the LLM's response afterward — the LLM
itself never sees or produces real identifiers.

This is a minimal MVP redactor (regex-based, employee-code and lat/lng
patterns) — a production system would extend this to names, national IDs,
and biometric template references per the design doc's data-classification
work in Phase 0.
"""
import re
from typing import Tuple

EMPLOYEE_CODE_PATTERN = re.compile(r"\bEMP\d{3,}\b")
LATLNG_PATTERN = re.compile(r"-?\d{1,3}\.\d{4,}")


def redact(text: str) -> Tuple[str, dict]:
    """Returns (redacted_text, rehydration_map)."""
    mapping = {}
    counter = {"emp": 0, "geo": 0}

    def _replace_emp(match):
        counter["emp"] += 1
        token = f"[EMPLOYEE_{counter['emp']}]"
        mapping[token] = match.group(0)
        return token

    def _replace_geo(match):
        counter["geo"] += 1
        token = f"[COORD_{counter['geo']}]"
        mapping[token] = match.group(0)
        return token

    redacted = EMPLOYEE_CODE_PATTERN.sub(_replace_emp, text)
    redacted = LATLNG_PATTERN.sub(_replace_geo, redacted)
    return redacted, mapping


def rehydrate(text: str, mapping: dict) -> str:
    for token, original in mapping.items():
        text = text.replace(token, original)
    return text
