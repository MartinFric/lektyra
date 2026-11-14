-- 0005: live runs on a schedule, and videos uploaded to be played as live (ADR-016).

INSERT INTO schema_version (version) VALUES (5);

-- A run starts a live session at starts_at and stops it at ends_at. It keeps its history: what ran, which video it
-- became, or why it did not run (missed: lektyra was not running; failed: the source could not be opened).
CREATE TABLE IF NOT EXISTS scheduled_run (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source      text NOT NULL,
  title       text NOT NULL,
  starts_at   timestamptz NOT NULL,
  ends_at     timestamptz NOT NULL,
  transcribe  boolean NOT NULL DEFAULT true,
  status      text NOT NULL DEFAULT 'scheduled'
              CHECK (status IN ('scheduled', 'running', 'done', 'failed', 'missed', 'cancelled')),
  session_id  text,
  event_id    text,
  message     text,
  created_by  text NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now(),
  CHECK (ends_at > starts_at)
);
CREATE INDEX IF NOT EXISTS scheduled_run_starts_at ON scheduled_run (starts_at);

-- A video Martin uploaded (or `lektyra fetch` downloaded) to play as if it were live. The file lives in lektyra's
-- MinIO under object_key; a working copy is cached under data/cache/uploads/ while it is used.
CREATE TABLE IF NOT EXISTS video_upload (
  id           uuid PRIMARY KEY,
  name         text NOT NULL,
  size         bigint NOT NULL CHECK (size > 0),
  content_type text NOT NULL,
  object_key   text NOT NULL UNIQUE,
  added_by     text NOT NULL,
  added_at     timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE audit_log DROP CONSTRAINT IF EXISTS audit_log_action_check;
ALTER TABLE audit_log ADD CONSTRAINT audit_log_action_check
  CHECK (action IN ('name', 'unname', 'reject', 'forget', 'rebuild', 'person', 'rate', 'flag', 'voice', 'merge',
                    'photo', 'schedule', 'upload'));
