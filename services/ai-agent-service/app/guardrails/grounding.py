"""
Grounding and confidence-gating guardrail.

`rule_score` is always deterministic and always present — it's computed by
plain arithmetic over tool-retrieved data (see rules.py), never by the LLM,
so it can't hallucinate. The LLM's own `llm_confidence` (when the LLM path
runs at all) is treated as advisory narrative, never as the number that
decides routing — this is the "confidence score is calibrated, not
self-reported by the LLM" requirement from the design doc.

route() returns one of:
  - "AUTO"     : low risk, no human touch needed
  - "REVIEW"   : queued for human review at NORMAL priority
  - "ESCALATE" : queued for human review at HIGH priority (policy SLA applies)
"""
from dataclasses import dataclass

from app.config import POLICY


@dataclass
class RoutingDecision:
    route: str
    priority: str  # LOW | NORMAL | HIGH, meaningful only when route != AUTO


def route_anomaly(rule_score: float) -> RoutingDecision:
    thresholds = POLICY["anomaly_thresholds"]
    if rule_score < thresholds["clear_below"]:
        return RoutingDecision(route="AUTO", priority="LOW")
    if rule_score < thresholds["review_below"]:
        return RoutingDecision(route="REVIEW", priority="NORMAL")
    return RoutingDecision(route="ESCALATE", priority="HIGH")


def strip_ungrounded_claims(llm_text: str, allowed_facts: list[str]) -> str:
    """
    Minimal grounding guard for the deterministic-first design: since the LLM
    prompt (see llm_client.py) is constructed to only ever discuss facts we
    already computed and pass in as `allowed_facts`, this function is a
    last-resort safety net that flags (rather than silently trusts) an
    LLM response containing no reference to any provided fact — signaling
    the caller to fall back to the deterministic narrative instead.
    """
    if not llm_text:
        return ""
    if not allowed_facts:
        return llm_text
    if any(str(fact).lower() in llm_text.lower() for fact in allowed_facts):
        return llm_text
    # No overlap with anything we actually retrieved — treat as ungrounded.
    return ""
