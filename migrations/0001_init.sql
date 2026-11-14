-- 0001: the spike's schema (spike-plan §4; ADR-003 costs, ADR-004 profiles, ADR-005 forget).
-- Embedding columns have no fixed dimension: each row names its embedding_model, and a model is compared only with
-- itself. Indexes per model come once the model is chosen.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE schema_version (
  version     integer PRIMARY KEY,
  applied_at  timestamptz NOT NULL DEFAULT now()
);
INSERT INTO schema_version (version) VALUES (1);

CREATE TABLE event (
  id          text PRIMARY KEY,                -- the folder name under data/events/
  source_url  text NOT NULL,
  source_id   text,                            -- the site's own id (TA3 video id)
  title       text NOT NULL,
  is_live     boolean NOT NULL,
  aired_at    timestamptz,
  started_at  timestamptz NOT NULL,
  audio_ms    integer NOT NULL DEFAULT 0
);

CREATE TABLE piece (
  event_id      text NOT NULL REFERENCES event (id) ON DELETE CASCADE,
  index         integer NOT NULL,
  start_ms      integer NOT NULL,              -- includes the overlap
  own_start_ms  integer NOT NULL,
  end_ms        integer NOT NULL,
  cut_kind      text NOT NULL CHECK (cut_kind IN ('pause', 'dip', 'forced', 'end')),
  quiet_ms      integer NOT NULL,
  PRIMARY KEY (event_id, index)
);

CREATE TABLE transcript_run (
  id            bigserial PRIMARY KEY,
  event_id      text NOT NULL REFERENCES event (id) ON DELETE CASCADE,
  engine        text NOT NULL,                 -- e.g. openrouter, soniox
  model         text NOT NULL,                 -- e.g. openai/whisper-large-v3
  params        jsonb NOT NULL DEFAULT '{}',
  zdr           boolean,                       -- zero data retention asked and granted
  price_per_h   numeric,                       -- list price at run time, USD per audio hour
  cost_usd      numeric NOT NULL DEFAULT 0,
  wall_ms       integer NOT NULL DEFAULT 0,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE utterance (
  run_id         bigint NOT NULL REFERENCES transcript_run (id) ON DELETE CASCADE,
  start_ms       integer NOT NULL,             -- stream time
  end_ms         integer NOT NULL,
  speaker_label  text,                         -- S1…N once aligned to diarization
  text           text NOT NULL,
  words          jsonb                         -- [{text, start_ms, end_ms}] when the engine gives them
);
CREATE INDEX utterance_run_time ON utterance (run_id, start_ms);

CREATE TABLE diarization_run (
  id          bigserial PRIMARY KEY,
  event_id    text NOT NULL REFERENCES event (id) ON DELETE CASCADE,
  engine      text NOT NULL,
  params      jsonb NOT NULL DEFAULT '{}',
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE turn (
  diarization_run_id  bigint NOT NULL REFERENCES diarization_run (id) ON DELETE CASCADE,
  start_ms            integer NOT NULL,
  end_ms              integer NOT NULL,
  label               text NOT NULL
);

CREATE TABLE person (
  id             bigserial PRIMARY KEY,
  name           text NOT NULL,
  function       text,
  party          text,
  public_figure  boolean NOT NULL DEFAULT false,
  created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE event_speaker (
  id                  bigserial PRIMARY KEY,
  event_id            text NOT NULL REFERENCES event (id) ON DELETE CASCADE,
  diarization_run_id  bigint REFERENCES diarization_run (id) ON DELETE CASCADE,
  label               text NOT NULL,           -- S1…N
  embedding           vector,
  embedding_model     text,
  person_id           bigint REFERENCES person (id) ON DELETE SET NULL,
  score               real,
  status              text NOT NULL DEFAULT 'unknown'
                      CHECK (status IN ('auto', 'suggested', 'unknown', 'confirmed')),
  UNIQUE (event_id, diarization_run_id, label)
);

CREATE TABLE voice_sample (
  id                bigserial PRIMARY KEY,
  person_id         bigint NOT NULL REFERENCES person (id) ON DELETE CASCADE,
  event_id          text NOT NULL REFERENCES event (id) ON DELETE CASCADE,
  event_speaker_id  bigint REFERENCES event_speaker (id) ON DELETE SET NULL,
  start_ms          integer NOT NULL,
  end_ms            integer NOT NULL,
  embedding         vector NOT NULL,
  embedding_model   text NOT NULL,
  provenance        text NOT NULL CHECK (provenance IN ('auto', 'human_confirmed', 'human_corrected')),
  quality           real NOT NULL,
  weight            real NOT NULL,
  channel           text,                      -- studio, hall, phone, … (metadata, not a key: ADR-004)
  confirmed_by      text,
  created_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX voice_sample_person_model ON voice_sample (person_id, embedding_model);

CREATE TABLE voice_rejection (
  event_speaker_id  bigint NOT NULL REFERENCES event_speaker (id) ON DELETE CASCADE,
  person_id         bigint NOT NULL REFERENCES person (id) ON DELETE CASCADE,
  created_by        text NOT NULL,
  created_at        timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (event_speaker_id, person_id)
);

-- Who named, rejected or forgot whom. No biometric content here (ADR-005).
CREATE TABLE audit_log (
  id       bigserial PRIMARY KEY,
  at       timestamptz NOT NULL DEFAULT now(),
  actor    text NOT NULL,
  action   text NOT NULL CHECK (action IN ('name', 'reject', 'forget', 'rebuild')),
  subject  text NOT NULL,
  detail   jsonb NOT NULL DEFAULT '{}'
);
