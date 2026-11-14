import { useQuery } from '@tanstack/react-query';
import { useId, useState } from 'react';
import { toast } from 'sonner';
import { count } from '@/platform/format';
import { Button, Dialog, Icon, Spinner, TextInput } from '@/platform/ui';
import { KIND_LABELS, type Person, personsQuery, useMergeVoice } from './api';
import { findPersons } from './findPersons';
import { PersonFace } from './PersonFace';
import styles from './MergeDialog.module.css';

interface MergeDialogProps {
  /** An unnamed voice. */
  readonly voice: Person;
  readonly onClose: () => void;
  readonly onMerged: (into: Person) => void;
}

/**
 * "Voice 4 is Robert Fico": pick the named person an unnamed voice belongs to, by searching names (without
 * diacritics), and merge. The whole voice moves to them in every video it was heard in (ADR-012). Render it only
 * while it is open.
 */
export function MergeDialog({ voice, onClose, onMerged }: MergeDialogProps) {
  const persons = useQuery(personsQuery);
  const merge = useMergeVoice();
  const [text, setText] = useState('');
  const [active, setActive] = useState(0);
  const [chosen, setChosen] = useState<Person | null>(null);
  const listId = useId();
  const named = (persons.data ?? []).filter((p) => !p.anonymous);
  const found = findPersons(named, text);
  const highlighted = found[Math.min(active, found.length - 1)] ?? null;
  const optionId = (p: Person) => `${listId}-${String(p.id)}`;

  const submit = () => {
    if (chosen === null) return;
    merge.mutate(
      { voiceId: voice.id, intoId: chosen.id },
      {
        onSuccess: (into) => {
          toast.success(`${voice.name} is ${into.name} now`, {
            description: `Named in ${count(into.events, 'video')}, keeps #${String(into.number)}.`,
          });
          onMerged(into);
        },
      },
    );
  };

  return (
    <Dialog
      title={`Merge ${voice.name} with…`}
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" icon="merge" disabled={chosen === null} loading={merge.isPending} onClick={submit}>
            {chosen ? `Merge into ${chosen.name}` : 'Merge'}
          </Button>
        </>
      }
    >
      <p className={styles.lead}>
        Who is <strong>{voice.name}</strong>? Pick the person: the voice, its {count(voice.samples, 'sample')} and
        its {count(voice.events, 'video')} move to them.
      </p>

      <div className={styles.search}>
        <Icon name="search" size={16} />
        <TextInput
          role="combobox"
          aria-expanded="true"
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={highlighted ? optionId(highlighted) : undefined}
          aria-label="Search persons by name"
          placeholder="Search persons by name"
          autoFocus
          autoComplete="off"
          className={styles.input}
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            setActive(0);
          }}
          onKeyDown={(e) => {
            if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
              e.preventDefault();
              const step = e.key === 'ArrowDown' ? 1 : -1;
              setActive((a) => Math.max(0, Math.min(found.length - 1, a + step)));
            } else if (e.key === 'Enter' && highlighted) {
              e.preventDefault();
              setChosen(highlighted);
            }
          }}
        />
      </div>

      {persons.isPending ? (
        <div className={styles.status}>
          <Spinner size={14} /> Loading persons…
        </div>
      ) : named.length === 0 ? (
        <div className={styles.status}>Nobody is named yet. Add the person first, then merge.</div>
      ) : (
        <ul id={listId} role="listbox" aria-label="Named persons" className={styles.options}>
          {found.map((p) => (
            <li
              key={p.id}
              id={optionId(p)}
              role="option"
              aria-selected={chosen?.id === p.id}
              data-active={p.id === highlighted?.id || undefined}
              ref={p.id === highlighted?.id ? (el) => el?.scrollIntoView({ block: 'nearest' }) : undefined}
            >
              <button
                type="button"
                tabIndex={-1}
                className={styles.option}
                onClick={() => { setChosen(p); }}
                onMouseEnter={() => { setActive(found.indexOf(p)); }}
              >
                <PersonFace person={p} size="sm" />
                <span className={styles.text}>
                  <span className={styles.name}>{p.name}</span>
                  <span className={styles.meta}>
                    {[KIND_LABELS[p.kind], p.function, p.party].filter(Boolean).join(' · ')}
                  </span>
                </span>
                <span className={styles.number}>#{p.number}</span>
                {chosen?.id === p.id ? <Icon name="check" size={16} label="chosen" /> : null}
              </button>
            </li>
          ))}
          {found.length === 0 ? <li className={styles.status}>Nobody called “{text.trim()}”.</li> : null}
        </ul>
      )}

      {chosen ? (
        <p className={styles.result} role="status">
          <PersonFace person={chosen} size="xs" className={styles.resultFace} /> <strong>{chosen.name}</strong> is named
          wherever {voice.name} was
          heard and keeps #{Math.min(voice.number, chosen.number)}. Speakers only matched to {voice.name} come along
          as guesses: confirm them in their videos.
        </p>
      ) : null}
    </Dialog>
  );
}
