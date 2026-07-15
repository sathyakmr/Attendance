"""
Input sanitization guardrail.

Applied to any user-controlled free text (regularization `reason`, NL query
`question`) before it is either (a) sent to the LLM or (b) used to influence
the agent's control flow. Two independent checks:

1. Length limit — cheap denial-of-service / cost-abuse guard.
2. Injection pattern scan — heuristic detection of attempts to override
   system instructions, redefine the agent's role, or exfiltrate the system
   prompt. This is deliberately conservative (pattern-based, not ML-based)
   so it's auditable and has no dependency on the LLM itself being available.

Per the design doc: untrusted content is always treated as *data*, never as
*instructions* — this scanner is a defense-in-depth layer on top of that
structural separation (the LLM call, when made, wraps user text in a
clearly-labeled data block; see llm_client.py), not a substitute for it.
"""
import re
from dataclasses import dataclass

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+|any\s+|previous\s+|prior\s+|the\s+)*instructions",
    r"disregard\s+(all\s+|any\s+|previous\s+|prior\s+|the\s+)*instructions",
    r"you are now",
    r"system prompt",
    r"act as (a |an )?(?!employee|manager)",  # "act as employee" is benign in context; "act as root/admin/etc" is not
    r"new instructions?:",
    r"override (your |the )?(rules|policy|guardrails)",
    r"reveal (your |the )?(prompt|instructions|system)",
    r"</?(system|assistant|user)>",  # attempts to forge role tags
    r"\bDAN\b",  # common jailbreak alias
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


@dataclass
class SanitizeResult:
    allowed: bool
    reason: str = ""


def scan_for_injection(text: str) -> SanitizeResult:
    for pattern in _COMPILED:
        if pattern.search(text):
            return SanitizeResult(allowed=False, reason=f"Matched injection pattern: {pattern.pattern}")
    return SanitizeResult(allowed=True)


def check_length(text: str, max_length: int) -> SanitizeResult:
    if len(text) > max_length:
        return SanitizeResult(allowed=False, reason=f"Input exceeds max length {max_length}")
    return SanitizeResult(allowed=True)


def sanitize(text: str, max_length: int) -> SanitizeResult:
    length_check = check_length(text, max_length)
    if not length_check.allowed:
        return length_check
    return scan_for_injection(text)
