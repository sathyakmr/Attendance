-- ==========================================================================
-- Phase 3: AI Agent — Anomaly Detection + Human-in-the-Loop Queue
-- NOTE: only applies to a fresh Postgres volume (docker-entrypoint-initdb.d
-- scripts run once). Run `docker compose down -v` before `up` if you have
-- an existing volume from Phase 1/2.
-- ==========================================================================

CREATE TYPE anomaly_flag_type AS ENUM (
    'GEO_JUMP',                -- impossible travel speed between consecutive events
    'SAME_DEVICE_MULTI_EMPLOYEE',  -- possible buddy punching
    'FREQUENCY_ANOMALY',       -- unusual punch frequency vs personal baseline
    'SHIFT_WINDOW'             -- carried over from deterministic validation flag
);

CREATE TYPE anomaly_flag_status AS ENUM (
    'OPEN',
    'CLEARED',
    'CONFIRMED'
);

CREATE TYPE review_priority AS ENUM ('LOW', 'NORMAL', 'HIGH');
CREATE TYPE review_status AS ENUM ('OPEN', 'RESOLVED');

CREATE TABLE anomaly_flags (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    attendance_event_id UUID NOT NULL REFERENCES attendance_events(id),
    employee_id         UUID NOT NULL REFERENCES employees(id),
    flag_type           anomaly_flag_type NOT NULL,
    rule_score          REAL NOT NULL,          -- deterministic rule-engine score, always present
    llm_narrative       TEXT,                   -- optional LLM-generated explanation (never the sole basis for a decision)
    llm_confidence      REAL,                   -- optional, calibrated separately from rule_score
    status              anomaly_flag_status NOT NULL DEFAULT 'OPEN',
    details             JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at         TIMESTAMPTZ
);

CREATE INDEX idx_anomaly_employee ON anomaly_flags (employee_id, status);
CREATE INDEX idx_anomaly_event ON anomaly_flags (attendance_event_id);

CREATE TABLE human_review_queue (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_type    VARCHAR(32) NOT NULL,   -- 'ANOMALY_FLAG' | 'REGULARIZATION'
    subject_id      UUID NOT NULL,
    employee_id     UUID REFERENCES employees(id),
    priority        review_priority NOT NULL DEFAULT 'NORMAL',
    reason          TEXT NOT NULL,
    status          review_status NOT NULL DEFAULT 'OPEN',
    resolution      VARCHAR(32),            -- 'CONFIRMED' | 'DISMISSED' (set on resolve)
    resolution_notes TEXT,
    resolved_by     UUID,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at     TIMESTAMPTZ
);

CREATE INDEX idx_review_queue_status ON human_review_queue (status, priority);
