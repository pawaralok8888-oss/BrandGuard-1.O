-- Notifications: record why each delivery was skipped or failed, and allow the 'skipped' status.
-- Idempotent: safe to run on a database that already has these changes.
ALTER TABLE notification_log ADD COLUMN IF NOT EXISTS error TEXT NOT NULL DEFAULT '';
ALTER TABLE notification_log DROP CONSTRAINT IF EXISTS notification_log_status_check;
ALTER TABLE notification_log ADD CONSTRAINT notification_log_status_check
  CHECK (status IN ('queued','sent','failed','read','skipped'));
