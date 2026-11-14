import { useQuery } from '@tanstack/react-query';
import { type ReactNode, useState } from 'react';
import { similarity } from '@/platform/format';
import { Icon, Popover, Spinner, TextInput } from '@/platform/ui';
import { type Person, personsQuery, useCreatePersonByName } from './api';
import { PersonFace } from './PersonFace';
import styles from './PersonPicker.module.css';

export interface PickerHint {
  readonly personId: number;
  readonly score: number;
}

interface PersonPickerProps {
  /** The trigger's content (the trigger is a button the picker renders). */
  readonly children: ReactNode;
  readonly label: string;
  readonly onPick: (person: { readonly id: number; readonly name: string }) => void;
  /** Voice similarity per person, shown next to names and used to sort the closest first. */
  readonly hints?: readonly PickerHint[];
  readonly exclude?: readonly number[];
  readonly currentId?: number | null;
  readonly triggerClassName?: string;
  readonly align?: 'start' | 'end';
}

/** Choose a person, or add one by typing a new name. The closest voices come first when hints are given. */
export function PersonPicker({
  children,
  label,
  onPick,
  hints = [],
  exclude = [],
  currentId = null,
  triggerClassName,
  align = 'start',
}: PersonPickerProps) {
  return (
    <Popover
      label={label}
      align={align}
      width={320}
      trigger={(props) => (
        <button type="button" {...props} className={triggerClassName ?? styles.trigger}>
          {children}
        </button>
      )}
    >
      {(close) => (
        <PickerPanel
          hints={hints}
          exclude={exclude}
          currentId={currentId}
          onPick={(p) => {
            close();
            onPick(p);
          }}
        />
      )}
    </Popover>
  );
}

interface PanelProps {
  readonly hints: readonly PickerHint[];
  readonly exclude: readonly number[];
  readonly currentId: number | null;
  readonly onPick: (person: { readonly id: number; readonly name: string }) => void;
}

function PickerPanel({ hints, exclude, currentId, onPick }: PanelProps) {
  const persons = useQuery(personsQuery);
  const create = useCreatePersonByName();
  const [text, setText] = useState('');
  const needle = text.trim().toLowerCase();
  const scoreOf = (p: Person) => hints.find((h) => h.personId === p.id)?.score;
  const list = (persons.data ?? [])
    .filter((p) => !exclude.includes(p.id))
    .filter((p) => !needle || p.name.toLowerCase().includes(needle) || (p.party ?? '').toLowerCase().includes(needle))
    .sort(
      (a, b) =>
        Number(a.anonymous) - Number(b.anonymous) ||
        (scoreOf(b) ?? -1) - (scoreOf(a) ?? -1) ||
        a.name.localeCompare(b.name),
    );
  const exact = (persons.data ?? []).some((p) => p.name.toLowerCase() === needle);

  return (
    <div className={styles.panel}>
      <div className={styles.search}>
        <Icon name="search" size={15} />
        <TextInput
          autoFocus
          value={text}
          onChange={(e) => { setText(e.target.value); }}
          placeholder="Find or add a person"
          aria-label="Find or add a person"
          className={styles.input}
        />
      </div>
      {persons.isPending ? (
        <div className={styles.status}>
          <Spinner size={14} /> Loading persons…
        </div>
      ) : persons.isError ? (
        <div className={styles.status} role="alert">
          {persons.error.message}
        </div>
      ) : list.length === 0 && needle ? null : (
        <ul className={styles.list} role="listbox" aria-label="Persons">
          {list.map((p) => {
            const score = scoreOf(p);
            return (
              <li key={p.id} role="option" aria-selected={p.id === currentId}>
                <button type="button" className={styles.option} onClick={() => { onPick({ id: p.id, name: p.name }); }}>
                  <PersonFace person={p} size="xs" />
                  <span className={styles.optionName}>
                    {p.name}
                    {p.anonymous ? <span className={styles.party}>unnamed voice</span> : null}
                    {p.party ? <span className={styles.party}>{p.party}</span> : null}
                  </span>
                  {score !== undefined ? (
                    <span className={styles.score} title="Voice similarity to this person's samples">
                      {similarity(score)}
                    </span>
                  ) : null}
                  {p.id === currentId ? <Icon name="check" size={15} label="current" /> : null}
                </button>
              </li>
            );
          })}
          {list.length === 0 && !needle ? <li className={styles.status}>No persons yet: type a name to add one.</li> : null}
        </ul>
      )}
      {needle && !exact ? (
        <button
          type="button"
          className={styles.add}
          disabled={create.isPending}
          onClick={() => {
            create.mutate(text.trim(), { onSuccess: (p) => { onPick({ id: p.id, name: p.name }); } });
          }}
        >
          {create.isPending ? <Spinner size={14} /> : <Icon name="plus" size={15} />}
          Add “{text.trim()}” as a new person
        </button>
      ) : null}
    </div>
  );
}
