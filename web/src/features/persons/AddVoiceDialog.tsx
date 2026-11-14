import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { toast } from 'sonner';
import { ReelButton } from '@/features/voices/Reel';
import { count } from '@/platform/format';
import { Button, Dialog, Icon, Spinner, TextInput } from '@/platform/ui';
import { isRecurring, KIND_LABELS, type Person, personsQuery, useMergeVoice } from './api';
import { PersonFace } from './PersonFace';
import styles from './MergeDialog.module.css';

interface AddVoiceDialogProps {
  /** A named person who has no voice yet, or should get another one. */
  readonly person: Person;
  readonly onClose: () => void;
}

/**
 * The other way round from Merge with…: on a person's page, pick which unnamed voice is them (hear it first with ▶).
 * The voice merges into the person in every video it was heard in (ADR-012). Render it only while it is open.
 */
export function AddVoiceDialog({ person, onClose }: AddVoiceDialogProps) {
  const persons = useQuery(personsQuery);
  const merge = useMergeVoice();
  const [text, setText] = useState('');
  const [chosen, setChosen] = useState<Person | null>(null);
  const needle = text.trim().toLowerCase();
  const voices = (persons.data ?? [])
    .filter((p) => p.anonymous && (!needle || p.name.toLowerCase().includes(needle) || String(p.number).includes(needle)))
    .sort((a, b) => Number(isRecurring(b)) - Number(isRecurring(a)) || b.number - a.number); // newest voices first

  return (
    <Dialog
      title={`Which voice is ${person.name}?`}
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="primary"
            icon="merge"
            disabled={chosen === null}
            loading={merge.isPending}
            onClick={() => {
              if (chosen === null) return;
              merge.mutate(
                { voiceId: chosen.id, intoId: person.id },
                {
                  onSuccess: (into) => {
                    toast.success(`${chosen.name} is ${into.name} now`, {
                      description: `Named in ${count(into.events, 'video')}.`,
                    });
                    onClose();
                  },
                },
              );
            }}
          >
            {chosen ? `${chosen.name} is ${person.name}` : 'Pick a voice'}
          </Button>
        </>
      }
    >
      <p className={styles.lead}>
        Hear a voice with ▶, then pick it: it becomes <strong>{person.name}</strong> in every video it was heard in.
      </p>
      <div className={styles.search}>
        <Icon name="search" size={16} />
        <TextInput
          autoFocus
          aria-label="Find a voice by number"
          placeholder="Voice number, e.g. 28"
          className={styles.input}
          value={text}
          onChange={(e) => { setText(e.target.value); }}
        />
      </div>
      {persons.isPending ? (
        <p className={styles.status}>
          <Spinner size={14} /> Loading voices…
        </p>
      ) : (
        <ul className={styles.options} aria-label="Unnamed voices">
          {voices.map((v) => (
            <li key={v.id} role="option" aria-selected={chosen?.id === v.id} className={styles.voiceRow}>
              <button type="button" className={styles.option} onClick={() => { setChosen(v); }}>
                <PersonFace person={v} size="sm" />
                <span className={styles.text}>
                  <span className={styles.name}>{v.name}</span>
                  <span className={styles.meta}>
                    {[
                      v.kind === 'other' ? null : KIND_LABELS[v.kind],
                      count(v.samples, 'sample'),
                      count(v.events, 'video'),
                      isRecurring(v) ? 'recurring' : null,
                    ]
                      .filter(Boolean)
                      .join(' · ')}
                  </span>
                </span>
                {chosen?.id === v.id ? <Icon name="check" size={16} label="chosen" /> : null}
              </button>
              {v.events > 0 ? <ReelButton source={{ kind: 'person', personId: v.id }} showWhere={false} /> : null}
            </li>
          ))}
          {voices.length === 0 ? <li className={styles.status}>No unnamed voice matches.</li> : null}
        </ul>
      )}
    </Dialog>
  );
}
