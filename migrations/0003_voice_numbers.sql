-- 0003: every distinct voice gets a number that keeps counting across videos (ADR-012). A voice nobody has named
-- is a person row with anonymous = true and the name "Voice <number>"; naming it renames it (or merges it into a
-- person who already exists), so the name reaches every video the voice was heard in.

INSERT INTO schema_version (version) VALUES (3);

CREATE SEQUENCE IF NOT EXISTS voice_number_seq;
ALTER TABLE person ADD COLUMN IF NOT EXISTS number integer;
UPDATE person SET number = numbered.n
FROM (SELECT id, nextval('voice_number_seq') AS n FROM (SELECT id FROM person ORDER BY id) ordered) numbered
WHERE person.id = numbered.id AND person.number IS NULL;
ALTER TABLE person ALTER COLUMN number SET DEFAULT nextval('voice_number_seq');
ALTER TABLE person ALTER COLUMN number SET NOT NULL;
ALTER TABLE person ADD CONSTRAINT person_number_unique UNIQUE (number);
ALTER TABLE person ADD COLUMN IF NOT EXISTS anonymous boolean NOT NULL DEFAULT false;

-- A person is more than a name: what they are on air, a key that never changes, and a link to what is known about
-- them elsewhere (a Wikidata id or a URL), so knowledge kept outside lektyra can be joined to the voice.
ALTER TABLE person ADD COLUMN IF NOT EXISTS kind text NOT NULL DEFAULT 'other'
  CHECK (kind IN ('politician', 'host', 'journalist', 'expert', 'official', 'other'));
ALTER TABLE person ADD COLUMN IF NOT EXISTS key uuid NOT NULL DEFAULT gen_random_uuid();
ALTER TABLE person ADD CONSTRAINT person_key_unique UNIQUE (key);
ALTER TABLE person ADD COLUMN IF NOT EXISTS external_ref text;

-- A speaker whose person was forgotten (or that is an ad's voice) must not grow a new profile: forgetting sticks.
ALTER TABLE event_speaker ADD COLUMN IF NOT EXISTS no_profile boolean NOT NULL DEFAULT false;

-- 'new': this speaker is where an unnamed voice was first heard; its samples define that voice.
ALTER TABLE event_speaker DROP CONSTRAINT IF EXISTS event_speaker_status_check;
ALTER TABLE event_speaker ADD CONSTRAINT event_speaker_status_check
  CHECK (status IN ('auto', 'suggested', 'unknown', 'confirmed', 'new'));

ALTER TABLE audit_log DROP CONSTRAINT IF EXISTS audit_log_action_check;
ALTER TABLE audit_log ADD CONSTRAINT audit_log_action_check
  CHECK (action IN ('name', 'unname', 'reject', 'forget', 'rebuild', 'person', 'rate', 'flag', 'voice', 'merge'));
