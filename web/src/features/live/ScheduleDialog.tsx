import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { toast } from 'sonner';
import { Button, Checkbox, Dialog, ErrorPanel, Field, TextInput } from '@/platform/ui';
import { uploadsQuery, useAddRun } from './api';
import styles from './LivePage.module.css';
import { notifyMissing, useSourceChoice } from './sourceChoice';
import { SourcePicker } from './SourcePicker';
import { dayInput, runProblem, runTimes, runWhen, sourceLabel } from './sources';

/** The first sensible day for a run: today until 11:00, then tomorrow (Sunday's shows start at 11). */
function firstDay(now: Date): string {
  return dayInput(now.getHours() < 11 ? now : new Date(now.getTime() + 24 * 3600_000));
}

/** Schedule a live run: a source, a day, from–to. lektyra starts and stops it itself while `lektyra ui` runs. */
export function ScheduleDialog({ onClose }: { readonly onClose: () => void }) {
  const choice = useSourceChoice();
  const uploads = useQuery(uploadsQuery);
  const add = useAddRun();
  const [day, setDay] = useState(() => firstDay(new Date()));
  const [start, setStart] = useState('11:00');
  const [end, setEnd] = useState('12:00');
  const [title, setTitle] = useState('');
  const [transcribe, setTranscribe] = useState(true);
  const times = runTimes(day, start, end);
  const problem = runProblem(times, new Date());
  const fallbackTitle = `${sourceLabel(choice.source || 'ta3:live', uploads.data)} ${day}`;

  const submit = () => {
    if (notifyMissing(choice) || times === null || problem) return;
    add.mutate(
      {
        source: choice.source,
        title: title.trim() || fallbackTitle,
        starts_at: times.starts.toISOString(),
        ends_at: times.ends.toISOString(),
        transcribe,
      },
      {
        onSuccess: (run) => {
          toast.success(`Scheduled: ${run.title}`, { description: runWhen(run.starts_at, run.ends_at) });
          onClose();
        },
      },
    );
  };

  return (
    <Dialog
      title="Schedule a live run"
      size="lg"
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" icon="calendar" loading={add.isPending} disabled={problem !== null} onClick={submit}>
            Schedule
          </Button>
        </>
      }
    >
      <SourcePicker state={choice} group="schedule-source" />
      <div className={styles.when}>
        <Field label="Day">
          {({ id }) => <TextInput id={id} type="date" value={day} onChange={(e) => { setDay(e.target.value); }} />}
        </Field>
        <Field label="From">
          {({ id }) => <TextInput id={id} type="time" value={start} onChange={(e) => { setStart(e.target.value); }} />}
        </Field>
        <Field label="To" hint="an earlier time is the next day">
          {({ id, describedBy }) => (
            <TextInput id={id} aria-describedby={describedBy} type="time" value={end} onChange={(e) => { setEnd(e.target.value); }} />
          )}
        </Field>
      </div>
      {problem ? (
        <p className={styles.problem} role="alert">
          {problem}
        </p>
      ) : times ? (
        <p className={styles.muted}>{runWhen(times.starts, times.ends)}: start a minute or two early, shows rarely start on the dot.</p>
      ) : null}
      <Field label="Title" hint="The show and date; it names the video">
        {({ id, describedBy }) => (
          <TextInput
            id={id}
            aria-describedby={describedBy}
            value={title}
            maxLength={120}
            placeholder={fallbackTitle}
            onChange={(e) => { setTitle(e.target.value); }}
          />
        )}
      </Field>
      <Checkbox
        label="Transcribe as it goes"
        hint="About $0.22 an hour. Without it you still see and name the voices."
        checked={transcribe}
        onChange={(e) => { setTranscribe(e.target.checked); }}
      />
      {add.error ? <ErrorPanel error={add.error} /> : null}
    </Dialog>
  );
}
