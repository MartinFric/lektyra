import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { Button, Card, CardHeader, Checkbox, EmptyState, Field, Icon, QueryView, Skeleton, TextInput } from '@/platform/ui';
import { type LiveSource, liveSourcesQuery, useStartLive } from './api';
import styles from './LivePage.module.css';

type Choice = { readonly kind: 'file'; readonly name: string } | { readonly kind: 'stream' };

/** Pick what to listen to: a video downloaded with `lektyra fetch` (played here, next to lektyra) or a stream. */
export function StartPanel() {
  const sources = useQuery(liveSourcesQuery);
  const start = useStartLive();
  const [choice, setChoice] = useState<Choice | null>(null);
  const [stream, setStream] = useState('ta3:live');
  const [title, setTitle] = useState('');
  const [transcribe, setTranscribe] = useState(true);
  const source = choice === null ? '' : choice.kind === 'file' ? choice.name : stream.trim();

  return (
    <Card>
      <CardHeader
        title="Start a session"
        subtitle="A downloaded video plays here while lektyra hears it at the same speed, as if it were live."
      />
      <form
        className={styles.startForm}
        onSubmit={(e) => {
          e.preventDefault();
          if (source) start.mutate({ source, title: title.trim(), transcribe });
        }}
      >
        <fieldset className={styles.sources}>
          <legend className={styles.legend}>Source</legend>
          <QueryView query={sources} loading={<Skeleton lines={2} height={44} />}>
            {(list) =>
              list.length === 0 ? (
                <EmptyState icon="video" title="No downloaded videos">
                  Get one with <code>uv run lektyra fetch &lt;TA3, YouTube or Facebook address&gt;</code>; it lands in
                  data/videos.
                </EmptyState>
              ) : (
                <div className={styles.sourceList}>
                  {list.map((s) => (
                    <SourceOption
                      key={s.name}
                      source={s}
                      selected={choice?.kind === 'file' && choice.name === s.name}
                      onSelect={() => { setChoice({ kind: 'file', name: s.name }); }}
                    />
                  ))}
                </div>
              )
            }
          </QueryView>
          <label className={styles.option} data-on={choice?.kind === 'stream'}>
            <input
              type="radio"
              name="source"
              checked={choice?.kind === 'stream'}
              onChange={() => { setChoice({ kind: 'stream' }); }}
              className="visually-hidden"
            />
            <Icon name="voices" size={18} />
            <span className={styles.optionText}>
              <strong>A live stream</strong>
              <span className={styles.muted}>ta3:live, ta3:nrsr, or a YouTube / Facebook live address. Watch it on TV.</span>
            </span>
          </label>
          {choice?.kind === 'stream' ? (
            <TextInput
              aria-label="Stream address"
              value={stream}
              onChange={(e) => { setStream(e.target.value); }}
              placeholder="ta3:live or https://…"
            />
          ) : null}
        </fieldset>
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
          <Button type="submit" variant="primary" icon="play" disabled={!source} loading={start.isPending}>
            Start listening
          </Button>
        </div>
      </form>
    </Card>
  );
}

interface SourceOptionProps {
  readonly source: LiveSource;
  readonly selected: boolean;
  readonly onSelect: () => void;
}

function SourceOption({ source, selected, onSelect }: SourceOptionProps) {
  return (
    <label className={styles.option} data-on={selected}>
      <input type="radio" name="source" checked={selected} onChange={onSelect} className="visually-hidden" />
      <Icon name={source.kind === 'video' ? 'video' : 'voices'} size={18} />
      <span className={styles.optionText}>
        <strong>{source.name}</strong>
        <span className={styles.muted}>
          {source.kind} · {Math.round(source.size / 1e6)} MB
        </span>
      </span>
    </label>
  );
}
