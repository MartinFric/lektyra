import { useQuery } from '@tanstack/react-query';
import { speakersQuery } from '@/features/events/api';
import { byLabel, speakerName } from '@/features/events/speakerName';
import { transcriptQuery } from '@/features/transcript/api';
import { clock, count } from '@/platform/format';
import { Badge, Button, Card, CardHeader, Icon, Spinner } from '@/platform/ui';
import { isActive, type LiveState, scheduleQuery, type Upload, uploadsQuery } from './api';
import styles from './LivePage.module.css';
import { runWhen, sourceLabel, startsIn } from './sources';

const LAST_CHARS = 220;

/**
 * What lektyra is transcribing now: each running session with what it has heard and its latest words, one click
 * from watching it. When nothing runs: the next scheduled run and how soon it starts.
 */
export function NowPanel({ sessions, onWatch }: { readonly sessions: readonly LiveState[]; readonly onWatch: (id: string) => void }) {
  const runs = useQuery(scheduleQuery);
  const uploads = useQuery(uploadsQuery);
  const running = sessions.filter((s) => isActive(s.status));
  const next = (runs.data ?? [])
    .filter((r) => r.status === 'scheduled')
    .sort((a, b) => a.starts_at.getTime() - b.starts_at.getTime())[0];

  if (running.length > 0) {
    return (
      <Card className={styles.nowPanel} data-live>
        <CardHeader
          title={
            <span className={styles.nowTitle}>
              <span className={styles.pulse} aria-hidden="true" /> Transcribing now
            </span>
          }
          subtitle="Runs in lektyra's background service: closing this page stops nothing."
        />
        <ul className={styles.nowList}>
          {running.map((s) => (
            <NowRow key={s.id} state={s} uploads={uploads.data ?? []} onWatch={() => { onWatch(s.id); }} />
          ))}
        </ul>
      </Card>
    );
  }
  return (
    <Card className={styles.nowPanel}>
      <CardHeader title="Nothing is being transcribed right now" />
      {next ? (
        <p className={styles.next}>
          <Icon name="calendar" size={17} />
          <span>
            Next: <strong>{next.title}</strong> · {sourceLabel(next.source, uploads.data)} ·{' '}
            {runWhen(next.starts_at, next.ends_at)}
          </span>
          <Badge tone="signal">{startsIn(next.starts_at, new Date())}</Badge>
        </p>
      ) : (
        <p className={styles.muted}>Nothing scheduled either: Schedule… a show, or Start now….</p>
      )}
    </Card>
  );
}

interface RowProps {
  readonly state: LiveState;
  readonly uploads: readonly Upload[];
  readonly onWatch: () => void;
}

function NowRow({ state, uploads, onWatch }: RowProps) {
  const eventId = state.event_id;
  const variant = state.variant;
  const words = useQuery({
    ...transcriptQuery(eventId ?? '-', variant ?? '-'),
    enabled: eventId !== null && variant !== null,
    staleTime: 0,
    refetchInterval: 5000,
  });
  const speakers = useQuery({ ...speakersQuery(eventId ?? '-'), enabled: eventId !== null, refetchInterval: 5000 });
  const last = words.data?.paragraphs.at(-1);
  const who = last ? speakerName(last.label, byLabel(speakers.data ?? [])).text : null;
  const voices = state.speakers.filter((s) => s.listed).length;

  return (
    <li className={styles.nowRow}>
      <div className={styles.nowRowText}>
        <strong>{state.title ?? sourceLabel(state.source, uploads)}</strong>
        <span className={styles.muted}>
          {sourceLabel(state.source, uploads)} · heard <span className="tabular">{clock(state.position_ms)}</span> ·{' '}
          {count(voices, 'voice')} ·{' '}
          {state.transcribe ? `${String(state.transcribed)}/${String(state.pieces)} pieces in words` : 'voices only'}
          {state.status === 'loading' ? (
            <>
              {' '}
              · <Spinner size={11} /> starting
            </>
          ) : null}
        </span>
        {last ? (
          <p className={styles.lastWords}>
            <strong>{who}:</strong> {last.text.length > LAST_CHARS ? `…${last.text.slice(-LAST_CHARS)}` : last.text}
          </p>
        ) : state.transcribe ? (
          <p className={styles.muted}>The first words arrive after about 30–40 seconds.</p>
        ) : null}
      </div>
      <Button variant="primary" icon="play" onClick={onWatch}>
        Watch
      </Button>
    </li>
  );
}
