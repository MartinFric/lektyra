-- 0006: a speaker can be several known persons talking at once (ADR-017). A label only: it never gives samples to
-- anyone's voice, never founds a voice and is never matched.

INSERT INTO schema_version (version) VALUES (6);

ALTER TABLE event_speaker DROP CONSTRAINT IF EXISTS event_speaker_status_check;
ALTER TABLE event_speaker ADD CONSTRAINT event_speaker_status_check
  CHECK (status IN ('auto', 'suggested', 'unknown', 'confirmed', 'new', 'overlap'));

CREATE TABLE IF NOT EXISTS speaker_overlap (
  event_speaker_id bigint NOT NULL REFERENCES event_speaker (id) ON DELETE CASCADE,
  person_id        bigint NOT NULL REFERENCES person (id) ON DELETE CASCADE,
  created_by       text NOT NULL,
  created_at       timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (event_speaker_id, person_id)
);

ALTER TABLE audit_log DROP CONSTRAINT IF EXISTS audit_log_action_check;
ALTER TABLE audit_log ADD CONSTRAINT audit_log_action_check
  CHECK (action IN ('name', 'unname', 'reject', 'forget', 'rebuild', 'person', 'rate', 'flag', 'voice', 'merge',
                    'photo', 'schedule', 'upload', 'overlap'));
