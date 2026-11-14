import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router';
import { eventsQuery } from '@/features/events/api';
import { clock, dateTime } from '@/platform/format';
import { Badge, Button, Card, CardHeader, Icon, QueryView, Skeleton, type Tone } from '@/platform/ui';
import { type Run, type RunStatus, scheduleQuery, uploadsQuery, useCancelRun } from './api';
import styles from './LivePage.module.css';
import { runWhen, sourceLabel } from './sources';

const STATUS: Record<RunStatus, { readonly label: string; readonly tone: Tone }> = {
  scheduled: { label: 'scheduled', tone: 'signal' },
  running: { label: 'live', tone: 'error' },
  done: { label: 'done', tone: 'ok' },
  failed: { label: 'failed', tone: 'error' },
  missed: { label: 'missed', tone: 'warn' },
  cancelled: { label: 'cancelled', tone: 'neutral' },
};

/** Runs to come first (soonest first), then what ran (latest first). */
function ordered(runs: readonly Run[]): Run[] {
  const coming = runs.filter((r) => r.status === 'scheduled' || r.status === 'running');
  const past = runs.filter((r) => !coming.includes(r)).reverse();
  return [...coming, ...past.slice(0, 12)];
}

/** Scheduled live runs: what comes, what runs, what ran and which video it became. */
export function ScheduleCard({ onSchedule }: { readonly onSchedule: () => void }) {
  const runs = useQuery(scheduleQuery);
  const uploads = useQuery(uploadsQuery);
  const cancel = useCancelRun();
  return (
    <Card>
      <CardHeader
        title="Scheduled"
        subtitle="lektyra starts and stops these itself while `lektyra ui` runs on this PC."
        actions={
          <Button size="sm" icon="calendar" onClick={onSchedule}>
            Schedule…
          </Button>
        }
      />
      <QueryView query={runs} loading={<Skeleton lines={3} height={40} />}>
        {(list) =>
          list.length === 0 ? (
            <p className={styles.muted}>Nothing scheduled. TA3 at 11:00, STVR at 11:55: schedule them once, lektyra does the rest.</p>
          ) : (
            <ul className={styles.runs}>
              {ordered(list).map((r) => (
                <li key={r.id} className={styles.run} data-status={r.status}>
                  <Badge tone={STATUS[r.status].tone}>
                    {r.status === 'running' ? <span className={styles.pulse} aria-hidden="true" /> : null}
                    {STATUS[r.status].label}
                  </Badge>
                  <span className={styles.runText}>
                    <strong>{r.title}</strong>
                    <span className={styles.muted}>
                      {runWhen(r.starts_at, r.ends_at)} · {sourceLabel(r.source, uploads.data)}
                      {r.transcribe ? '' : ' · voices only'}
                    </span>
                    {r.message && r.status !== 'scheduled' ? <span className={styles.runMessage}>{r.message}</span> : null}
                  </span>
                  {r.status === 'running' && r.session_id ? (
                    <Link to={`/live?session=${encodeURIComponent(r.session_id)}`} className={styles.open}>
                      Watch <Icon name="chevron" size={15} />
                    </Link>
                  ) : null}
                  {r.status === 'scheduled' || r.status === 'running' ? (
                    <Button
                      size="sm"
                      variant={r.status === 'running' ? 'danger' : 'ghost'}
                      icon="x"
                      disabled={cancel.isPending}
                      onClick={() => { cancel.mutate(r.id); }}
                    >
                      {r.status === 'running' ? 'Stop' : 'Cancel'}
                    </Button>
                  ) : r.event_id ? (
                    <Link to={`/videos/${encodeURIComponent(r.event_id)}`} className={styles.open}>
                      Video <Icon name="chevron" size={15} />
                    </Link>
                  ) : null}
                </li>
              ))}
            </ul>
          )
        }
      </QueryView>
    </Card>
  );
}

/** The latest videos lektyra made (live sessions and archives), newest first. */
export function RecentVideos() {
  const events = useQuery(eventsQuery);
  return (
    <Card>
      <CardHeader
        title="Transcribed videos"
        subtitle="The latest first. Every finished session lands here."
        actions={
          <Link to="/videos" className={styles.open}>
            All videos <Icon name="chevron" size={15} />
          </Link>
        }
      />
      <QueryView query={events} loading={<Skeleton lines={4} height={40} />}>
        {(list) => (
          <ul className={styles.runs}>
            {[...list]
              .sort((a, b) => b.started_at.getTime() - a.started_at.getTime())
              .slice(0, 8)
              .map((e) => (
                <li key={e.id} className={styles.run}>
                  <Icon name={e.is_live ? 'broadcast' : 'video'} size={17} />
                  <span className={styles.runText}>
                    <Link to={`/videos/${encodeURIComponent(e.id)}`} className={styles.videoLink}>
                      {e.title}
                    </Link>
                    <span className={styles.muted}>
                      {dateTime(e.started_at)} · {clock(e.audio_ms)} · {e.named}/{e.speakers} voices named
                      {e.transcripts > 0 ? '' : ' · no transcript yet'}
                    </span>
                  </span>
                </li>
              ))}
          </ul>
        )}
      </QueryView>
    </Card>
  );
}
