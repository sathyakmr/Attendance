-- ==========================================================================
-- Phase 4: Automated Reporting + WhatsApp Notification Delivery
-- NOTE: only applies to a fresh Postgres volume — `docker compose down -v`
-- before `up` if you have an existing volume from an earlier phase.
-- ==========================================================================

CREATE TYPE notification_channel AS ENUM ('WHATSAPP', 'FALLBACK_LOG');
CREATE TYPE notification_status AS ENUM ('PENDING', 'SENT', 'DELIVERED', 'READ', 'FAILED');
CREATE TYPE report_period AS ENUM ('DAILY', 'WEEKLY', 'MONTHLY', 'ADHOC');

CREATE TABLE notifications (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notification_id     VARCHAR(64) UNIQUE NOT NULL,   -- our own idempotency key, generated per send attempt series
    channel             notification_channel NOT NULL DEFAULT 'WHATSAPP',
    recipient           VARCHAR(64) NOT NULL,
    report_period       report_period NOT NULL,
    period_start        TIMESTAMPTZ NOT NULL,
    period_end          TIMESTAMPTZ NOT NULL,
    payload_summary     TEXT NOT NULL,
    whatsapp_message_id VARCHAR(128),                  -- Meta's wamid, used to match webhook delivery callbacks
    status              notification_status NOT NULL DEFAULT 'PENDING',
    attempt_count       INTEGER NOT NULL DEFAULT 0,
    last_attempt_at     TIMESTAMPTZ,
    last_error          TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_at             TIMESTAMPTZ,
    delivered_at        TIMESTAMPTZ,
    read_at             TIMESTAMPTZ
);

CREATE INDEX idx_notifications_whatsapp_msg ON notifications (whatsapp_message_id);
CREATE INDEX idx_notifications_status ON notifications (status);
CREATE INDEX idx_notifications_period ON notifications (report_period, period_start);
