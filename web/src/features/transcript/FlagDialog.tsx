import { useState } from 'react';
import { clock } from '@/platform/format';
import { Button, Dialog, Field, TextArea } from '@/platform/ui';
import { FLAG_KINDS, type FlagKind, type Paragraph, useAddFlag } from './api';
import styles from './TranscriptPage.module.css';

interface FlagDialogProps {
  readonly eventId: string;
  readonly variant: string;
  readonly paragraph: Paragraph;
  readonly onClose: () => void;
}

export function FlagDialog({ eventId, variant, paragraph, onClose }: FlagDialogProps) {
  const [kind, setKind] = useState<FlagKind>('words');
  const [note, setNote] = useState('');
  const add = useAddFlag(eventId, variant);
  return (
    <Dialog
      title={`Flag at ${clock(paragraph.start_ms)}`}
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="primary"
            icon="flag"
            loading={add.isPending}
            onClick={() => {
              add.mutate({ at_ms: paragraph.start_ms, kind, note: note.trim() }, { onSuccess: onClose });
            }}
          >
            Add flag
          </Button>
        </>
      }
    >
      <blockquote className={styles.quote}>{paragraph.text}</blockquote>
      <fieldset className={styles.kinds}>
        <legend className={styles.kindsLegend}>What is wrong</legend>
        {FLAG_KINDS.map((k) => (
          <label key={k.kind} className={styles.kind} data-on={kind === k.kind}>
            <input
              type="radio"
              name="flag-kind"
              value={k.kind}
              checked={kind === k.kind}
              onChange={() => { setKind(k.kind); }}
              className="visually-hidden"
            />
            {k.label}
          </label>
        ))}
      </fieldset>
      <Field label="Note" hint="What should it say? (optional)">
        {({ id, describedBy }) => (
          <TextArea
            id={id}
            aria-describedby={describedBy}
            rows={2}
            maxLength={500}
            value={note}
            onChange={(e) => { setNote(e.target.value); }}
          />
        )}
      </Field>
    </Dialog>
  );
}
