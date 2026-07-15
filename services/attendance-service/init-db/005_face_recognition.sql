-- ==========================================================================
-- Phase 6: Face-Recognition Check-In (client-side matching)
-- NOTE: only applies to a fresh Postgres volume. `docker compose down -v`
-- before `up` if you have an existing volume from an earlier phase.
--
-- SECURITY NOTE: face_descriptor is a 128-dimensional float vector (a face
-- "fingerprint," not a photo) produced by face-api.js's recognition model.
-- Because the person chose CLIENT-SIDE matching, these descriptors must be
-- readable by the browser to do 1:N matching locally — see
-- GET /api/v1/employees/face-descriptors in attendance-service, which is
-- deliberately a SEPARATE, narrowly-scoped endpoint from the general
-- employee directory, so normal directory/roster calls never include
-- biometric data. This endpoint being unauthenticated is the concrete
-- expression of the "client-side is weaker security" tradeoff that was
-- explicitly chosen over a server-side biometric-service — see the
-- Phase 6 section of the README for the full discussion.
-- ==========================================================================

ALTER TABLE employees ADD COLUMN face_descriptor JSONB;
ALTER TABLE employees ADD COLUMN face_enrolled_at TIMESTAMPTZ;
