-- 0004: a face next to a name (ADR-015). One picture per named person. lektyra re-encodes every picture itself
-- (WebP, at most 512 px, no metadata); the file lives in lektyra's own MinIO, this row says which object it is,
-- where it came from and under which licence. Forgetting a person deletes the row (ON DELETE CASCADE) and then the
-- object (every object no row points at is swept, ADR-005).

INSERT INTO schema_version (version) VALUES (4);

CREATE TABLE IF NOT EXISTS person_photo (
  person_id   bigint PRIMARY KEY REFERENCES person (id) ON DELETE CASCADE,
  object_key  text NOT NULL UNIQUE,   -- persons/<person key>/<version>.webp in the pictures bucket
  content_type text NOT NULL CHECK (content_type = 'image/webp'),
  width       integer NOT NULL CHECK (width BETWEEN 1 AND 512),
  height      integer NOT NULL CHECK (height BETWEEN 1 AND 512),
  version     text NOT NULL,          -- part of the picture's hash: its URL changes when the picture does
  source_url  text,                   -- where it came from (a Wikimedia Commons file page, an official page); null = a file Martin uploaded
  license     text,                   -- as the source states it (e.g. "CC BY-SA 4.0"); null = unknown, local use only
  author      text,
  added_by    text NOT NULL,
  added_at    timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE audit_log DROP CONSTRAINT IF EXISTS audit_log_action_check;
ALTER TABLE audit_log ADD CONSTRAINT audit_log_action_check
  CHECK (action IN ('name', 'unname', 'reject', 'forget', 'rebuild', 'person', 'rate', 'flag', 'voice', 'merge',
                    'photo'));
