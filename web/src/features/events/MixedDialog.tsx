import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { findPersons } from '@/features/persons/findPersons';
import { personsQuery } from '@/features/persons/api';
import { PersonFace } from '@/features/persons/PersonFace';
import { Button, Dialog, Icon, Spinner, TextInput } from '@/platform/ui';
import { type Speaker, useMarkMixed } from './api';
import styles from './MixedDialog.module.css';

interface MixedDialogProps {
  readonly eventId: string;
  readonly speaker: Speaker;
  readonly onClose: () => void;
}

/**
 * Mark a speaker as mixed: two or more known people talking at once (crosstalk, ADR-017). A label only: nobody's
 * voice learns from it, and samples it gave a name are taken back. Render it only while it is open.
 */
export function MixedDialog({ eventId, speaker, onClose }: MixedDialogProps) {
  const persons = useQuery(personsQuery);
  const mark = useMarkMixed(eventId);
  const [text, setText] = useState('');
  const [chosen, setChosen] = useState<readonly number[]>(() =>
    speaker.overlap.length > 0
      ? speaker.overlap.map((o) => o.person_id)
      : speaker.person_id !== null && speaker.person_anonymous === false
        ? [speaker.person_id]
        : [],
  );
  const named = (persons.data ?? []).filter((p) => !p.anonymous);
  const found = findPersons(named, text);
  const picked = named.filter((p) => chosen.includes(p.id));
  const toggle = (id: number) => {
    setChosen((c) => (c.includes(id) ? c.filter((x) => x !== id) : [...c, id]));
  };
  const namedNow = speaker.status === 'confirmed' && speaker.person_name !== null;

  return (
    <Dialog
      title={`${speaker.label} is mixed: who talks at once?`}
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="primary"
            icon="users"
            disabled={chosen.length < 2}
            loading={mark.isPending}
            onClick={() => {
              mark.mutate({ label: speaker.label, personIds: chosen }, { onSuccess: onClose });
            }}
          >
            Mark as mixed
          </Button>
        </>
      }
    >
      <p className={styles.lead}>
        Pick two or more people. A label only: their voices do not learn from it
        {namedNow ? (
          <>
            , and the samples {speaker.label} gave <strong>{speaker.person_name}</strong> are taken back
          </>
        ) : null}
        .
      </p>
      <div className={styles.search}>
        <Icon name="search" size={16} />
        <TextInput
          autoFocus
          aria-label="Search persons by name"
          placeholder="Search persons by name"
          className={styles.input}
          value={text}
          onChange={(e) => { setText(e.target.value); }}
        />
      </div>
      {persons.isPending ? (
        <p className={styles.status}>
          <Spinner size={14} /> Loading persons…
        </p>
      ) : (
        <ul className={styles.options} aria-label="Named persons">
          {found.map((p) => (
            <li key={p.id}>
              <label className={styles.option} data-on={chosen.includes(p.id) || undefined}>
                <input type="checkbox" checked={chosen.includes(p.id)} onChange={() => { toggle(p.id); }} />
                <PersonFace person={p} size="sm" />
                <span className={styles.name}>{p.name}</span>
                {p.party ? <span className={styles.meta}>{p.party}</span> : null}
              </label>
            </li>
          ))}
          {found.length === 0 ? <li className={styles.status}>Nobody called “{text.trim()}”.</li> : null}
        </ul>
      )}
      <p className={styles.result} role="status">
        {picked.length >= 2
          ? `${speaker.label}: ${picked.map((p) => p.name).join(' + ')}`
          : `${String(picked.length)} picked: pick at least two.`}
      </p>
    </Dialog>
  );
}
