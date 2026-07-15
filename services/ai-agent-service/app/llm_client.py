"""
Thin wrapper around the Anthropic Messages API.

Design intent: every public function here returns None instead of raising
whenever the LLM path can't complete cleanly (no API key configured, network
failure, timeout, or a response that fails JSON parsing/grounding checks).
Callers (rules.py, main.py) always have a deterministic result ready before
calling into this module, and simply keep that deterministic result if this
returns None. This is what makes the agent's "deterministic fallback"
requirement (design doc Section 6/9.3) actually true rather than aspirational.

No conversation history or long-term memory is sent here — each call is
single-shot and stateless, scoped tightly to the one task it's asked to do,
which keeps prompt-injection blast radius small (see guardrails/sanitize.py
for the layer that runs before any text reaches this module).
"""
import json
import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger("ai-agent.llm_client")

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"


def _call(system_prompt: str, user_content: str, max_tokens: int = 500) -> Optional[str]:
    if not settings.anthropic_api_key:
        logger.info("No ANTHROPIC_API_KEY configured — skipping LLM call, deterministic path will be used.")
        return None

    try:
        resp = httpx.post(
            ANTHROPIC_API_URL,
            headers={
                "x-api-key": settings.anthropic_api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": settings.anthropic_model,
                "max_tokens": max_tokens,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_content}],
            },
            timeout=settings.llm_timeout_seconds,
        )
        resp.raise_for_status()
        data = resp.json()
        text_blocks = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
        return "\n".join(text_blocks).strip() or None
    except Exception as exc:  # noqa: BLE001 — any failure here must degrade gracefully, not propagate
        logger.warning("LLM call failed, falling back to deterministic path: %s", exc)
        return None


def explain_anomaly(redacted_context: dict) -> Optional[dict]:
    """
    Given already-redacted, already-computed anomaly facts, ask the LLM only
    to phrase a short explanation — it is never asked to compute the score
    or invent facts not present in redacted_context.
    Returns {"narrative": str, "recommended_action": str} or None.
    """
    system_prompt = (
        "You are an attendance-anomaly explainer. You will be given a JSON "
        "object of facts that were already computed by a deterministic rule "
        "engine. Your only job is to phrase a short (2-3 sentence), plain "
        "English explanation of these facts for a manager. Do not invent any "
        "fact not present in the input. Do not recommend approving or "
        "rejecting anything yourself — only describe what was observed. "
        "Respond ONLY with JSON: {\"narrative\": \"...\", \"recommended_action\": "
        "\"REVIEW\"} with recommended_action always exactly \"REVIEW\" (a human "
        "always makes the actual decision)."
    )
    raw = _call(system_prompt, json.dumps(redacted_context), max_tokens=300)
    if not raw:
        return None
    try:
        cleaned = raw.strip().removeprefix("```json").removesuffix("```").strip()
        parsed = json.loads(cleaned)
        if "narrative" not in parsed:
            return None
        return parsed
    except (json.JSONDecodeError, AttributeError):
        logger.warning("LLM anomaly explanation was not valid JSON, discarding.")
        return None


def prescreen_regularization(redacted_context: dict, policy_text: str) -> Optional[dict]:
    """
    Given redacted request facts and the policy document text, ask the LLM to
    draft a recommendation citing the policy. This is a DRAFT only —
    regularization-service still requires a human decision regardless of
    what's returned here.
    Returns {"recommendation": str, "confidence": float, "risk_level": str} or None.
    """
    system_prompt = (
        "You are an HR regularization pre-screening assistant. You will "
        "receive: (1) the text of the attendance policy, and (2) redacted "
        "facts about a specific regularization request. Draft a brief "
        "recommendation citing the relevant policy section. You must not "
        "state any fact not present in the provided request data. This is "
        "only a draft for a human manager — never state that the request is "
        "approved or rejected, only what you recommend and why. "
        "Respond ONLY with JSON: {\"recommendation\": \"...\", \"confidence\": "
        "0.0-1.0, \"risk_level\": \"LOW\"|\"MEDIUM\"|\"HIGH\"}."
    )
    user_content = json.dumps({"policy": policy_text, "request": redacted_context})
    raw = _call(system_prompt, user_content, max_tokens=400)
    if not raw:
        return None
    try:
        cleaned = raw.strip().removeprefix("```json").removesuffix("```").strip()
        parsed = json.loads(cleaned)
        if not all(k in parsed for k in ("recommendation", "confidence", "risk_level")):
            return None
        return parsed
    except (json.JSONDecodeError, AttributeError):
        logger.warning("LLM regularization prescreen was not valid JSON, discarding.")
        return None


def parse_query_intent(question: str) -> Optional[dict]:
    """
    Translate a natural-language question into a constrained, structured
    intent — never into raw SQL. The caller (main.py) builds a parametrized
    query from this structured intent only; the LLM never gets to produce
    executable query text.
    Returns a dict like {"metric": "LATE_COUNT", "department": null,
    "employee_code": null, "date_from": "2026-06-01", "date_to": "2026-06-30",
    "threshold": 3} or None.
    """
    system_prompt = (
        "You translate a manager's natural-language question about "
        "attendance into a structured JSON intent. You never write SQL or "
        "any executable query. Valid metric values are exactly: "
        "LATE_COUNT, ABSENT_COUNT, FLAGGED_COUNT, ANOMALY_COUNT. "
        "Respond ONLY with JSON: {\"metric\": \"...\", \"department\": "
        "string|null, \"employee_code\": string|null, \"date_from\": "
        "\"YYYY-MM-DD\"|null, \"date_to\": \"YYYY-MM-DD\"|null, \"threshold\": "
        "int|null}. If you cannot confidently map the question to one of "
        "the four metrics, respond with {\"metric\": null}."
    )
    raw = _call(system_prompt, question, max_tokens=200)
    if not raw:
        return None
    try:
        cleaned = raw.strip().removeprefix("```json").removesuffix("```").strip()
        parsed = json.loads(cleaned)
        if parsed.get("metric") not in ("LATE_COUNT", "ABSENT_COUNT", "FLAGGED_COUNT", "ANOMALY_COUNT"):
            return None
        return parsed
    except (json.JSONDecodeError, AttributeError):
        return None


def summarize_report(stats: dict) -> Optional[str]:
    """
    Given already-computed, already-correct report statistics (see
    reporting-service/app/aggregation.py), ask the LLM to phrase a short
    (2-3 sentence) plain-language summary for a WhatsApp message. The LLM is
    never asked to compute any number — only to phrase numbers it's given.
    Returns a narrative string, or None (caller falls back to a deterministic
    templated summary — see deterministic.py::deterministic_report_narrative).
    """
    system_prompt = (
        "You write a short (2-3 sentence), plain-English summary of an "
        "attendance report for a business owner reading it on WhatsApp. "
        "You will be given a JSON object of statistics that were already "
        "computed correctly. Restate only these numbers — do not invent, "
        "estimate, or round in a way that changes their meaning, and do not "
        "add any fact not present in the input. Keep it concise and plain, "
        "no markdown headers. Respond with the summary text only, no JSON, "
        "no preamble."
    )
    raw = _call(system_prompt, json.dumps(stats), max_tokens=200)
    return raw or None
