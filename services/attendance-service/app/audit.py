"""
Append-only, hash-chained audit logging.

Every mutation writes an audit_log row whose record_hash is a SHA-256 of
(prev_hash + entity + actor + action + before/after state). Chaining makes
silent row tampering or deletion detectable: recomputing the chain and
comparing to stored hashes will reveal a break.
"""
import hashlib
import json
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app import models


def _serialize(obj) -> str:
    return json.dumps(obj, sort_keys=True, default=str)


def write_audit_entry(
    db: Session,
    entity_type: str,
    entity_id: uuid.UUID,
    actor_id: str,
    actor_role: str,
    action: str,
    before_state: Optional[dict],
    after_state: Optional[dict],
) -> models.AuditLog:
    last = (
        db.query(models.AuditLog)
        .order_by(models.AuditLog.created_at.desc())
        .first()
    )
    prev_hash = last.record_hash if last else "GENESIS"

    payload = prev_hash + entity_type + str(entity_id) + actor_id + action + _serialize(before_state) + _serialize(after_state)
    record_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    entry = models.AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor_id,
        actor_role=actor_role,
        action=action,
        before_state=before_state,
        after_state=after_state,
        prev_hash=prev_hash,
        record_hash=record_hash,
    )
    db.add(entry)
    db.flush()
    return entry
