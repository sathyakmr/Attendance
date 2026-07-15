-- ==========================================================================
-- Phase 2: RBAC / Identity + Regularization Workflow
-- NOTE: docker-entrypoint-initdb.d scripts only run when the Postgres data
-- volume is freshly created. If you already ran Phase 1, you must reset
-- the local volume for this to apply: `docker compose down -v`
-- ==========================================================================

-- Attendance events created via an approved regularization (not a live punch)
ALTER TYPE event_source ADD VALUE IF NOT EXISTS 'REGULARIZATION';

CREATE TYPE user_role AS ENUM (
    'EMPLOYEE',
    'MANAGER',
    'HR_ADMIN',
    'PAYROLL',
    'SYSTEM_AGENT',
    'SUPER_ADMIN'
);

CREATE TYPE regularization_status AS ENUM (
    'PENDING',
    'AI_PRESCREENED',
    'APPROVED',
    'REJECTED',
    'ESCALATED'
);

-- One login identity per person. employee_id is nullable so HR/admin
-- accounts can exist without a corresponding attendance-tracked employee row.
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username        VARCHAR(64) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    role            user_role NOT NULL,
    employee_id     UUID UNIQUE REFERENCES employees(id),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE regularization_requests (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id         UUID NOT NULL REFERENCES employees(id),
    target_date         DATE NOT NULL,
    requested_event_type event_type NOT NULL,
    requested_time      TIME NOT NULL,
    reason              TEXT NOT NULL,
    original_event_id   UUID REFERENCES attendance_events(id),
    new_event_id        UUID REFERENCES attendance_events(id),
    status              regularization_status NOT NULL DEFAULT 'PENDING',
    ai_recommendation   TEXT,
    ai_confidence       REAL,
    decided_by          UUID REFERENCES users(id),
    decision_notes      TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    decided_at          TIMESTAMPTZ
);

CREATE INDEX idx_regularization_employee ON regularization_requests (employee_id, status);
CREATE INDEX idx_regularization_status ON regularization_requests (status);

-- ---- Wire up a manager relationship + seed RBAC users for local dev ----
-- Vikram (EMP002) manages Asha (EMP001) and Meera (EMP003)
UPDATE employees SET manager_id = (SELECT id FROM employees WHERE employee_code = 'EMP002')
WHERE employee_code IN ('EMP001', 'EMP003');

-- All seed users share password: "password123"
-- (bcrypt hash generated offline — see README for how to regenerate)
INSERT INTO users (username, password_hash, role, employee_id) VALUES
    ('asha.rao',    '$2b$12$0LCE6rHyCPbXGEu6QgyEC.WdaPYH8J./6rFfTJl96bkq5YUH3KB6C', 'EMPLOYEE', (SELECT id FROM employees WHERE employee_code = 'EMP001')),
    ('vikram.shah', '$2b$12$0LCE6rHyCPbXGEu6QgyEC.WdaPYH8J./6rFfTJl96bkq5YUH3KB6C', 'MANAGER',  (SELECT id FROM employees WHERE employee_code = 'EMP002')),
    ('meera.iyer',  '$2b$12$0LCE6rHyCPbXGEu6QgyEC.WdaPYH8J./6rFfTJl96bkq5YUH3KB6C', 'EMPLOYEE', (SELECT id FROM employees WHERE employee_code = 'EMP003')),
    ('hr.admin',    '$2b$12$0LCE6rHyCPbXGEu6QgyEC.WdaPYH8J./6rFfTJl96bkq5YUH3KB6C', 'HR_ADMIN', NULL);
