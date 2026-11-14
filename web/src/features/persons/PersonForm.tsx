import { useState } from 'react';
import { toast } from 'sonner';
import { ReelButton } from '@/features/voices/Reel';
import { count } from '@/platform/format';
import { Badge, Button, Checkbox, Dialog, ErrorPanel, Field, Icon, Select, TextArea, TextInput } from '@/platform/ui';
import {
  KIND_LABELS,
  PERSON_KINDS,
  type Person,
  type PersonInput,
  personKind,
  useForgetPerson,
  useSavePerson,
} from './api';
import styles from './PersonForm.module.css';

interface PersonFormProps {
  readonly person: Person | null;
  readonly onSaved: (person: Person) => void;
  readonly onClose: () => void;
}

function initialInput(person: Person | null): PersonInput {
  return {
    name: person?.name ?? '',
    kind: person?.kind ?? 'other',
    external_ref: person?.external_ref ?? '',
    function: person?.function ?? '',
    party: person?.party ?? '',
    public_figure: person?.public_figure ?? true,
    note: person?.note ?? '',
  };
}

/** Create or edit one person. Keyed by id by its parent, so switching persons starts from fresh state. */
export function PersonForm({ person, onSaved, onClose }: PersonFormProps) {
  const [input, setInput] = useState(() => initialInput(person));
  const [forgetting, setForgetting] = useState(false);
  const save = useSavePerson();
  const forget = useForgetPerson();
  const error = save.error;
  const nameError = error?.fieldMessage('name') ?? (error?.code === 'conflict' ? error.message : undefined);

  const set = <K extends keyof PersonInput>(key: K, value: PersonInput[K]) => {
    setInput((current) => ({ ...current, [key]: value }));
    if (save.isError) save.reset();
  };

  return (
    <form
      className={styles.form}
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate(
          { id: person?.id ?? null, input },
          {
            onSuccess: (saved) => {
              toast.success(person ? 'Saved' : `${saved.name} added`);
              onSaved(saved);
            },
          },
        );
      }}
    >
      <header className={styles.header}>
        <div className={styles.titleRow}>
          <h2 className={styles.title}>{person ? person.name : 'New person'}</h2>
          {person && person.events > 0 ? <ReelButton source={{ kind: 'person', personId: person.id }} /> : null}
        </div>
        {person?.anonymous ? (
          <p className={styles.hint}>
            A voice nobody has named yet. Give it a name and it is named in every video it was heard in.
          </p>
        ) : null}
        {person ? (
          <div className={styles.stats}>
            <Badge title="Voice number: counts up across all videos">#{person.number}</Badge>
            <Badge tone={person.samples > 0 ? 'signal' : 'neutral'}>{count(person.samples, 'voice sample')}</Badge>
            <Badge>named in {count(person.events, 'video')}</Badge>
          </div>
        ) : null}
      </header>

      {error && !nameError && error.details.length === 0 ? <ErrorPanel error={error} /> : null}

      <Field label="Name" required error={nameError}>
        {({ id, describedBy, invalid }) => (
          <TextInput
            id={id}
            aria-describedby={describedBy}
            aria-invalid={invalid}
            value={input.name}
            onChange={(e) => { set('name', e.target.value); }}
            placeholder="Full name as people say it"
            autoComplete="off"
            maxLength={120}
            required
          />
        )}
      </Field>
      <div className={styles.pair}>
        <Field label="Type" hint="What they are on air">
          {({ id, describedBy }) => (
            <Select
              id={id}
              aria-describedby={describedBy}
              value={input.kind}
              onChange={(e) => {
                const parsed = personKind.safeParse(e.target.value);
                if (parsed.success) set('kind', parsed.data);
              }}
            >
              {PERSON_KINDS.map((k) => (
                <option key={k} value={k}>
                  {KIND_LABELS[k]}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field
          label="Knowledge link"
          hint="Wikidata id (Q123) or a web address: where what is known about them lives"
          error={error?.fieldMessage('external_ref')}
        >
          {({ id, describedBy, invalid }) => (
            <TextInput
              id={id}
              aria-describedby={describedBy}
              aria-invalid={invalid}
              value={input.external_ref}
              onChange={(e) => { set('external_ref', e.target.value.trim()); }}
              placeholder="Q57792 or https://…"
              maxLength={120}
            />
          )}
        </Field>
      </div>
      <div className={styles.pair}>
        <Field label="Function" hint="e.g. minister, MP, moderator" error={error?.fieldMessage('function')}>
          {({ id, describedBy, invalid }) => (
            <TextInput
              id={id}
              aria-describedby={describedBy}
              aria-invalid={invalid}
              value={input.function}
              onChange={(e) => { set('function', e.target.value); }}
              maxLength={120}
            />
          )}
        </Field>
        <Field label="Party" hint="leave empty when none" error={error?.fieldMessage('party')}>
          {({ id, describedBy, invalid }) => (
            <TextInput
              id={id}
              aria-describedby={describedBy}
              aria-invalid={invalid}
              value={input.party}
              onChange={(e) => { set('party', e.target.value); }}
              maxLength={120}
            />
          )}
        </Field>
      </div>
      <Checkbox
        label="Public figure"
        hint="Speaks in public in that role. Voice profiles of anyone else need a reason (ADR-005)."
        checked={input.public_figure}
        onChange={(e) => { set('public_figure', e.target.checked); }}
      />
      <Field label="Note" hint="Only for you: where you know the voice from, look-alikes" error={error?.fieldMessage('note')}>
        {({ id, describedBy, invalid }) => (
          <TextArea
            id={id}
            aria-describedby={describedBy}
            aria-invalid={invalid}
            value={input.note}
            onChange={(e) => { set('note', e.target.value); }}
            maxLength={2000}
            rows={3}
          />
        )}
      </Field>

      {person ? <KeyLine person={person} link={input.external_ref} /> : null}

      <footer className={styles.footer}>
        {person ? (
          <Button variant="danger" icon="trash" onClick={() => { setForgetting(true); }}>
            Forget…
          </Button>
        ) : null}
        <span className={styles.spacer} />
        <Button variant="ghost" onClick={onClose}>
          Cancel
        </Button>
        <Button type="submit" variant="primary" icon="check" loading={save.isPending} disabled={!input.name.trim()}>
          {person ? 'Save' : 'Add person'}
        </Button>
      </footer>

      {forgetting && person ? (
        <Dialog
          title={`Forget ${person.name}?`}
          tone="danger"
          onClose={() => { setForgetting(false); }}
          footer={
            <>
              <Button variant="ghost" onClick={() => { setForgetting(false); }}>
                Keep
              </Button>
              <Button
                variant="danger"
                icon="trash"
                loading={forget.isPending}
                onClick={() => {
                  forget.mutate(person.id, {
                    onSuccess: () => {
                      setForgetting(false);
                      onClose();
                    },
                  });
                }}
              >
                Forget for good
              </Button>
            </>
          }
        >
          <p>
            This deletes the person, their <strong>{count(person.samples, 'voice sample')}</strong> and the names
            in <strong>{count(person.events, 'video')}</strong>. Those speakers become unknown again. It cannot be undone.
          </p>
        </Dialog>
      ) : null}
    </form>
  );
}

/** The key that never changes, for knowledge kept elsewhere; and where the knowledge link points. */
function KeyLine({ person, link }: { readonly person: Person; readonly link: string }) {
  const href = /^Q[1-9][0-9]*$/.test(link) ? `https://www.wikidata.org/wiki/${link}` : link.startsWith('http') ? link : null;
  return (
    <div className={styles.keyLine}>
      <span title="lektyra's key for this person: it never changes, so other systems can point at it">
        key <code className={styles.key}>{person.key}</code>
      </span>
      {href ? (
        <a href={href} target="_blank" rel="noreferrer" className={styles.open}>
          open link <Icon name="external" size={13} />
        </a>
      ) : null}
    </div>
  );
}
