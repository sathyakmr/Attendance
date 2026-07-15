-- ==========================================================================
-- Attendance Management System — Core Ledger Schema
-- Append-only attendance_events table is the source of truth.
-- Nothing is ever UPDATE'd in place except status transitions and the
-- superseded_by pointer (used for corrections) — raw history is preserved.
-- ==========================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";  -- for gen_random_uuid()

CREATE TYPE event_type AS ENUM ('CHECK_IN', 'CHECK_OUT');
CREATE TYPE event_source AS ENUM ('BIOMETRIC', 'MOBILE', 'WEB');
CREATE TYPE event_status AS ENUM (
    'PENDING_VALIDATION',
    'VALIDATED',
    'FLAGGED',
    'REJECTED',
    'SUPERSEDED'
);

CREATE TABLE employees (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_code   VARCHAR(32) UNIQUE NOT NULL,
    full_name       VARCHAR(255) NOT NULL,
    department      VARCHAR(128),
    manager_id      UUID REFERENCES employees(id),
    shift_start     TIME NOT NULL DEFAULT '09:00:00',
    shift_end       TIME NOT NULL DEFAULT '18:00:00',
    grace_minutes   INTEGER NOT NULL DEFAULT 10,
    geofence_lat    DOUBLE PRECISION,
    geofence_lng    DOUBLE PRECISION,
    geofence_radius_m INTEGER DEFAULT 200,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE devices (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_code     VARCHAR(64) UNIQUE NOT NULL,
    location_name   VARCHAR(255),
    latitude        DOUBLE PRECISION,
    longitude       DOUBLE PRECISION,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    registered_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE attendance_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id     UUID NOT NULL REFERENCES employees(id),
    device_id       UUID REFERENCES devices(id),
    event_type      event_type NOT NULL,
    source          event_source NOT NULL,
    event_ts        TIMESTAMPTZ NOT NULL,
    received_ts     TIMESTAMPTZ NOT NULL DEFAULT now(),
    latitude        DOUBLE PRECISION,
    longitude       DOUBLE PRECISION,
    status          event_status NOT NULL DEFAULT 'PENDING_VALIDATION',
    validation_notes TEXT,
    superseded_by   UUID REFERENCES attendance_events(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Fast lookups for "employee's events in a time range" (regularization, reporting)
CREATE INDEX idx_attendance_employee_ts ON attendance_events (employee_id, event_ts DESC);

-- Fast lookup for debounce check (most recent event per employee)
CREATE INDEX idx_attendance_employee_status ON attendance_events (employee_id, status);

CREATE INDEX idx_attendance_device ON attendance_events (device_id);

-- Append-only audit log (immutable; hash-chained for tamper evidence)
CREATE TABLE audit_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type     VARCHAR(64) NOT NULL,
    entity_id       UUID NOT NULL,
    actor_id        VARCHAR(128) NOT NULL,
    actor_role      VARCHAR(64) NOT NULL,
    action          VARCHAR(64) NOT NULL,
    before_state    JSONB,
    after_state     JSONB,
    prev_hash       VARCHAR(64),
    record_hash     VARCHAR(64) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_entity ON audit_log (entity_type, entity_id);

-- ---- Seed data for local dev / quick testing ----
INSERT INTO employees (employee_code, full_name, department, shift_start, shift_end, geofence_lat, geofence_lng, geofence_radius_m)
VALUES
    ('EMP001', 'Asha Rao', 'Engineering', '09:00:00', '18:00:00', 12.9716, 77.5946, 300),
    ('EMP002', 'Vikram Shah', 'Engineering', '09:00:00', '18:00:00', 12.9716, 77.5946, 300),
    ('EMP003', 'Meera Iyer', 'HR', '09:30:00', '18:30:00', 12.9716, 77.5946, 300);

INSERT INTO devices (device_code, location_name, latitude, longitude)
VALUES
    ('DEV-BLR-01', 'Bengaluru Office - Main Entrance', 12.9716, 77.5946);
