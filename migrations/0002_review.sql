-- 0002: the local review UI (ADR-009): persons get a note, speakers are unique per event even without a
-- diarization run in the database, and Martin's transcript ratings and flags have a home.

INSERT INTO schema_version (version) VALUES (2);

ALTER TABLE person ADD COLUMN IF NOT EXISTS note text;
ALTER TABLE person ADD CONSTRAINT person_name_unique UNIQUE (name);

-- event_speaker: one row per (event, label) when the diarization lives in files (diarization_run_id NULL).
ALTER TABLE event_speaker DROP CONSTRAINT IF EXISTS event_speaker_event_id_diarization_run_id_label_key;
ALTER TABLE event_speaker ADD CONSTRAINT event_speaker_unique UNIQUE NULLS NOT DISTINCT (event_id, diarization_run_id, label);
ALTER TABLE event_speaker ADD COLUMN IF NOT EXISTS talk_s real;
ALTER TABLE event_speaker ADD COLUMN IF NOT EXISTS share real;

-- One rating per transcript variant (event + engine@language), changed in place.
CREATE TABLE transcript_rating (
  event_id        text NOT NULL REFERENCES event (id) ON DELETE CASCADE,
  variant         text NOT NULL,                 -- e.g. elevenlabs__scribe-v2@sk
  accuracy        smallint CHECK (accuracy BETWEEN 1 AND 5),
  names_numbers   smallint CHECK (names_numbers BETWEEN 1 AND 5),
  note            text NOT NULL DEFAULT '',
  rated_by        text NOT NULL,
  rated_at        timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (event_id, variant)
);

-- A flag on one paragraph of one transcript.
CREATE TABLE transcript_flag (
  id         bigserial PRIMARY KEY,
  event_id   text NOT NULL REFERENCES event (id) ON DELETE CASCADE,
  variant    text NOT NULL,
  at_ms      integer NOT NULL,
  kind       text NOT NULL CHECK (kind IN ('words', 'speaker', 'name_number', 'other')),
  note       text NOT NULL DEFAULT '',
  created_by text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX transcript_flag_event ON transcript_flag (event_id, variant, at_ms);

ALTER TABLE audit_log DROP CONSTRAINT IF EXISTS audit_log_action_check;
ALTER TABLE audit_log ADD CONSTRAINT audit_log_action_check
  CHECK (action IN ('name', 'unname', 'reject', 'forget', 'rebuild', 'person', 'rate', 'flag'));
