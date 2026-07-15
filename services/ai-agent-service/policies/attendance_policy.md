# Attendance Policy — Regularization & Anomaly Handling (v1.0)

## Section 1: Regularization Eligibility
Regularization requests are normally approved when the stated reason falls into
one of the following accepted categories:
- Device malfunction or outage at the time of the punch
- Approved work-from-home day where biometric capture was not possible
- Medical emergency, with or without documentation attached
- Forgotten badge/credential, corroborated by building entry logs where available
- Manager-approved travel or client-site work

## Section 2: Frequency Threshold
An employee submitting more than 3 regularization requests within a trailing
30-day window is flagged as a **repeat pattern** and routed to priority manager
review rather than being eligible for streamlined approval, regardless of the
individual reason's plausibility.

## Section 3: Buddy Punching Definition
Buddy punching is defined as one employee recording an attendance event on
behalf of another. Indicators include: multiple distinct employee check-ins
from the same device within an implausibly short window, and check-in
locations inconsistent with an employee's established pattern without a
corresponding regularization or manager note.

## Section 4: Escalation SLA
High-risk anomaly flags (rule score >= 0.75) must be reviewed by a manager or
HR admin within 4 business hours. If unresolved, the flag auto-escalates to
HR_ADMIN priority review.

## Section 5: AI Agent Authority Limits
The AI agent may draft recommendations and pre-screen requests, but may not
approve, reject, or otherwise finalize any regularization request or anomaly
flag. All such decisions require a human with appropriate role authority.
