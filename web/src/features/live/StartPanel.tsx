import { useState } from 'react';
import { Button, Card, CardHeader, Checkbox, Field, TextInput } from '@/platform/ui';
import { type LiveState, useStartLive } from './api';
import styles from './LivePage.module.css';
import { notifyMissing, useSourceChoice } from './sourceChoice';
import { SourcePicker } from './SourcePicker';

/** Start a session now. Several may run at once (a scheduled one keeps running while this starts). */
export function StartPanel({ onStarted }: { readonly onStarted: (state: LiveState) => void }) {
  const start = useStartLive();
  const choice = useSourceChoice();
  const [title, setTitle] = useState('');
  const [transcribe, setTranscribe] = useState(true);

  return (
    <Card>
      <CardHeader
        title="Start now"
        subtitle="A live channel, a YouTube or Facebook address, this PC's sound, or an uploaded video played as live."
      />
      <form
        className={styles.startForm}
        onSubmit={(e) => {
          e.preventDefault();
          if (notifyMissing(choice)) return;
          start.mutate({ source: choice.source, title: title.trim(), transcribe }, { onSuccess: onStarted });
        }}
      >
        <SourcePicker state={choice} group="start-source" />
        <Field label="Title" hint="Optional: the show and date, e.g. V politike 15. 11.">
          {({ id, describedBy }) => (
            <TextInput id={id} aria-describedby={describedBy} value={title} maxLength={120} onChange={(e) => { setTitle(e.target.value); }} />
          )}
        </Field>
        <Checkbox
          label="Transcribe as it goes"
          hint="ElevenLabs through OpenRouter, about $0.22 an hour. Without it you still see and name the voices."
          checked={transcribe}
          onChange={(e) => { setTranscribe(e.target.checked); }}
        />
        <div className={styles.startFoot}>
          <span className={styles.muted}>Starting loads the voice model first (a few seconds).</span>
          <Button type="submit" variant="primary" icon="play" loading={start.isPending}>
            Start listening
          </Button>
        </div>
      </form>
    </Card>
  );
}
