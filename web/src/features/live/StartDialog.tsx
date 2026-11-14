import { useState } from 'react';
import { Button, Checkbox, Dialog, Field, TextInput } from '@/platform/ui';
import { type LiveState, useStartLive } from './api';
import { notifyMissing, useSourceChoice } from './sourceChoice';
import { SourcePicker } from './SourcePicker';

interface StartDialogProps {
  readonly onClose: () => void;
  readonly onStarted: (state: LiveState) => void;
}

/** Start a session now (Markíza through PC sound, a link, an upload). Several may run at once. */
export function StartDialog({ onClose, onStarted }: StartDialogProps) {
  const start = useStartLive();
  const choice = useSourceChoice();
  const [title, setTitle] = useState('');
  const [transcribe, setTranscribe] = useState(true);
  const submit = () => {
    if (notifyMissing(choice)) return;
    start.mutate({ source: choice.source, title: title.trim(), transcribe }, { onSuccess: onStarted });
  };

  return (
    <Dialog
      title="Start now"
      size="lg"
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" icon="play" loading={start.isPending} onClick={submit}>
            Start listening
          </Button>
        </>
      }
    >
      <SourcePicker state={choice} group="start-source" />
      <Field label="Title" hint="The show and date, e.g. Na telo 15. 11.; it names the video">
        {({ id, describedBy }) => (
          <TextInput id={id} aria-describedby={describedBy} value={title} maxLength={120} onChange={(e) => { setTitle(e.target.value); }} />
        )}
      </Field>
      <Checkbox
        label="Transcribe as it goes"
        hint="About $0.22 an hour. Without it you still see and name the voices. Starting loads the voice model (a few seconds)."
        checked={transcribe}
        onChange={(e) => { setTranscribe(e.target.checked); }}
      />
    </Dialog>
  );
}
