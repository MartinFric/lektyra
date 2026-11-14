import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useSearchParams } from 'react-router';
import { count } from '@/platform/format';
import { Badge, Button, Card, EmptyState, Icon, PageHeader, QueryView, Skeleton, TextInput } from '@/platform/ui';
import { ReelButton } from '@/features/voices/Reel';
import { useReel } from '@/features/voices/reelContext';
import { isRecurring, KIND_LABELS, type Person, personsQuery, RECURRING_AFTER } from './api';
import { PersonFace } from './PersonFace';
import { PersonForm } from './PersonForm';
import styles from './PersonsPage.module.css';

/** Persons: the list and one editor. What is being edited lives in the URL (?person=<id> or ?person=new). */
export function PersonsPage() {
  const persons = useQuery(personsQuery);
  const [params, setParams] = useSearchParams();
  const [filter, setFilter] = useState('');
  const editing = params.get('person');

  const reel = useReel();
  /** Select a person (or none, or a new one). What plays always belongs to the selected row: picking another row
   * stops a reel of someone else, so a voice is never named while another one is heard. */
  const open = (value: string | null) => {
    if (reel.active?.startsWith('person:') && reel.active !== `person:${value ?? ''}`) reel.stop();
    setParams(value === null ? {} : { person: value }, { replace: true });
  };

  return (
    <>
      <PageHeader
        title="Persons"
        subtitle="Who can be named. A name is all that is needed; the voice comes from naming a speaker."
        actions={
          <Button variant="primary" icon="plus" onClick={() => { open('new'); }}>
            New person
          </Button>
        }
      />
      <div className={styles.layout}>
        <Card padded={false} className={styles.listCard}>
          <div className={styles.search}>
            <Icon name="search" size={16} />
            <TextInput
              type="search"
              placeholder="Filter by name, party, function"
              value={filter}
              onChange={(e) => { setFilter(e.target.value); }}
              aria-label="Filter persons"
              className={styles.searchInput}
            />
          </div>
          <QueryView query={persons} loading={<div className={styles.pad}><Skeleton lines={6} height={40} /></div>}>
            {(list) => <PersonList persons={list} filter={filter} selected={editing} onSelect={(id) => { open(String(id)); }} />}
          </QueryView>
        </Card>
        <Card className={styles.editor}>
          {editing === null ? (
            <EmptyState icon="user" title="Pick a person or add one">
              Names you add here appear in every speaker&apos;s picker. Naming a speaker teaches lektyra the voice.
            </EmptyState>
          ) : (
            <QueryView query={persons}>
              {(list) => {
                const person = editing === 'new' ? null : (list.find((p) => String(p.id) === editing) ?? null);
                if (editing !== 'new' && person === null) {
                  return <EmptyState icon="search" title="This person is not in the list">They may have been forgotten.</EmptyState>;
                }
                return (
                  <PersonForm
                    key={person?.id ?? 'new'}
                    person={person}
                    onSaved={(saved) => { open(String(saved.id)); }}
                    onClose={() => { open(null); }}
                    onMerged={(into) => { open(String(into.id)); }}
                    onOpen={(p) => { open(String(p.id)); }}
                  />
                );
              }}
            </QueryView>
          )}
        </Card>
      </div>
    </>
  );
}

interface PersonListProps {
  readonly persons: readonly Person[];
  readonly filter: string;
  readonly selected: string | null;
  readonly onSelect: (id: number) => void;
}

function PersonList({ persons, filter, selected, onSelect }: PersonListProps) {
  const needle = filter.trim().toLowerCase();
  const shown = needle
    ? persons.filter((p) => [p.name, p.party ?? '', p.function ?? ''].some((s) => s.toLowerCase().includes(needle)))
    : persons;
  if (persons.length === 0) {
    return <EmptyState icon="users" title="No persons yet">Add the people you expect to hear: guests, moderators.</EmptyState>;
  }
  if (shown.length === 0) {
    return <EmptyState icon="search" title="No match">Nobody matches “{filter}”.</EmptyState>;
  }
  const people = shown.filter((p) => !p.anonymous);
  const voices = shown.filter((p) => p.anonymous).sort((a, b) => Number(isRecurring(b)) - Number(isRecurring(a)));
  const rows = (list: readonly Person[]) =>
    list.map((p) => (
      <li key={p.id} className={styles.item}>
        <button
          type="button"
          className={styles.row}
          aria-current={selected === String(p.id) || undefined}
          onClick={() => { onSelect(p.id); }}
        >
          <PersonFace person={p} className={styles.face} />
          <span className={styles.who}>
            <span className={styles.name}>{p.name}</span>
            <span className={styles.meta}>
              {p.anonymous
                ? p.kind === 'other'
                  ? 'not named yet'
                  : KIND_LABELS[p.kind]
                : [KIND_LABELS[p.kind], p.function, p.party].filter(Boolean).join(' · ')}
            </span>
          </span>
          <span className={styles.badges}>
            {isRecurring(p) ? (
              <Badge tone="claim" title={`Heard in more than ${String(RECURRING_AFTER)} videos: worth naming`}>
                recurring
              </Badge>
            ) : null}
            {p.samples > 0 ? (
              <Badge tone="signal" title="Voice samples">
                {count(p.samples, 'sample')}
              </Badge>
            ) : (
              <Badge title="Name a speaker as this person to teach the voice">no voice yet</Badge>
            )}
            {p.events > 0 ? <Badge>{count(p.events, 'video')}</Badge> : null}
          </span>
        </button>
        {p.events > 0 ? (
          <ReelButton
            source={{ kind: 'person', personId: p.id }}
            showWhere={false}
            onPlay={() => { onSelect(p.id); }}
          />
        ) : null}
      </li>
    ));
  return (
    <div className={styles.sections}>
      {people.length > 0 ? (
        <section>
          <h3 className={styles.section}>People · {people.length}</h3>
          <ul className={styles.list}>{rows(people)}</ul>
        </section>
      ) : null}
      {voices.length > 0 ? (
        <section>
          <h3 className={styles.section}>
            Unnamed voices · {voices.length}
            <span className={styles.sectionHint}>numbered as they were first heard; name one to name it everywhere</span>
          </h3>
          <ul className={styles.list}>{rows(voices)}</ul>
        </section>
      ) : null}
    </div>
  );
}
