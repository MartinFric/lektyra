import { useState } from 'react';
import { dateTime } from '@/platform/format';
import { Button, Field, Stars, TextArea } from '@/platform/ui';
import { type Rating, type RatingInput, useRate } from './api';
import styles from './TranscriptPage.module.css';

interface RatingPanelProps {
  readonly eventId: string;
  readonly variant: string;
  readonly rating: Rating | undefined;
}

/** Martin's verdict on one transcript. Keyed by the saved rating, so a save starts it fresh from the server. */
export function RatingPanel({ eventId, variant, rating }: RatingPanelProps) {
  const initial: RatingInput = {
    accuracy: rating?.accuracy ?? null,
    names_numbers: rating?.names_numbers ?? null,
    note: rating?.note ?? '',
  };
  const [input, setInput] = useState(initial);
  const rate = useRate(eventId, variant);
  const changed =
    input.accuracy !== initial.accuracy || input.names_numbers !== initial.names_numbers || input.note !== initial.note;

  return (
    <form
      className={styles.rating}
      onSubmit={(e) => {
        e.preventDefault();
        rate.mutate(input);
      }}
    >
      <Stars
        label="Words right"
        value={input.accuracy}
        onChange={(accuracy) => { setInput((c) => ({ ...c, accuracy })); }}
      />
      <Stars
        label="Names and numbers right"
        value={input.names_numbers}
        onChange={(names_numbers) => { setInput((c) => ({ ...c, names_numbers })); }}
      />
      <Field label="Note">
        {({ id }) => (
          <TextArea
            id={id}
            rows={2}
            maxLength={2000}
            value={input.note}
            placeholder="What it got wrong most"
            onChange={(e) => { setInput((c) => ({ ...c, note: e.target.value })); }}
          />
        )}
      </Field>
      <div className={styles.ratingFoot}>
        <span className={styles.muted}>{rating ? `Saved ${dateTime(rating.rated_at)}` : 'Not rated yet'}</span>
        <Button type="submit" size="sm" variant="primary" icon="check" disabled={!changed} loading={rate.isPending}>
          Save rating
        </Button>
      </div>
    </form>
  );
}
