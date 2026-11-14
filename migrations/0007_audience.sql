-- 0007: a voice can be the audience (Martin: a question from the floor, a voice from the public). Like a host, what
-- the audience says is not a claim (K60); it is a kind, so an unnamed voice can carry it too.

INSERT INTO schema_version (version) VALUES (7);

ALTER TABLE person DROP CONSTRAINT IF EXISTS person_kind_check;
ALTER TABLE person ADD CONSTRAINT person_kind_check
  CHECK (kind IN ('politician', 'host', 'journalist', 'expert', 'official', 'audience', 'other'));
