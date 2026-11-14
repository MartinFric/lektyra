import { useQuery } from '@tanstack/react-query';
import { toast } from 'sonner';
import { count } from '@/platform/format';
import { Button } from '@/platform/ui';
import { KIND_LABELS, type Person, personsQuery, useMergeVoice } from './api';
import { similarPersons } from './findPersons';
import { PersonFace } from './PersonFace';
import styles from './PersonForm.module.css';

interface DidYouMeanProps {
  /** The unnamed voice being named, or null for a new person. */
  readonly voice: Person | null;
  readonly typed: string;
  readonly onMerged: (into: Person) => void;
  readonly onOpen: (person: Person) => void;
}

/**
 * While a name is typed: persons already in the list that sound like it ("simecka miso" → Michal Šimečka). For an
 * unnamed voice, one click says the voice is that person (it merges, ADR-012); for a new person, open the one that
 * exists instead of making a twin.
 */
export function DidYouMean({ voice, typed, onMerged, onOpen }: DidYouMeanProps) {
  const persons = useQuery(personsQuery);
  const merge = useMergeVoice();
  const named = (persons.data ?? []).filter((p) => !p.anonymous && p.id !== voice?.id);
  const near = typed.trim().length >= 2 && typed.trim() !== voice?.name ? similarPersons(named, typed) : [];
  if (near.length === 0) return null;

  return (
    <div className={styles.didYouMean} role="status">
      <span className={styles.didYouMeanTitle}>Did you mean…</span>
      <ul className={styles.didYouMeanList}>
        {near.map((p) => (
          <li key={p.id} className={styles.didYouMeanRow}>
            <PersonFace person={p} size="sm" />
            <span className={styles.didYouMeanText}>
              <strong>{p.name}</strong>
              <span className={styles.didYouMeanMeta}>
                {[KIND_LABELS[p.kind], p.party, p.samples > 0 ? count(p.samples, 'sample') : 'no voice yet']
                  .filter(Boolean)
                  .join(' · ')}
              </span>
            </span>
            {voice ? (
              <Button
                size="sm"
                variant="primary"
                icon="merge"
                loading={merge.isPending && merge.variables.intoId === p.id}
                disabled={merge.isPending}
                onClick={() => {
                  merge.mutate(
                    { voiceId: voice.id, intoId: p.id },
                    {
                      onSuccess: (into) => {
                        toast.success(`${voice.name} is ${into.name} now`, {
                          description: `Named in ${count(into.events, 'video')}, keeps #${String(into.number)}.`,
                        });
                        onMerged(into);
                      },
                    },
                  );
                }}
              >
                {voice.name} is {p.name.split(' ').at(-1) ?? p.name}
              </Button>
            ) : (
              <Button size="sm" onClick={() => { onOpen(p); }}>
                Open
              </Button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
