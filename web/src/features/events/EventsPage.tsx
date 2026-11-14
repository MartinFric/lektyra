import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router';
import { clock, count, date } from '@/platform/format';
import { Badge, Card, EmptyState, Icon, PageHeader, QueryView, Skeleton } from '@/platform/ui';
import { type EventSummary, eventsQuery } from './api';
import styles from './EventsPage.module.css';

export function EventsPage() {
  const events = useQuery(eventsQuery);
  return (
    <>
      <PageHeader title="Videos" subtitle="Everything ingested into data/events, newest first." />
      <QueryView
        query={events}
        loading={
          <div className={styles.grid}>
            {[0, 1, 2].map((i) => (
              <Card key={i}>
                <Skeleton lines={3} />
              </Card>
            ))}
          </div>
        }
      >
        {(list) =>
          list.length === 0 ? (
            <Card>
              <EmptyState icon="video" title="No videos yet">
                Ingest one with <code>uv run lektyra ingest &lt;url&gt;</code>, then press Rescan folders.
              </EmptyState>
            </Card>
          ) : (
            <div className={styles.grid}>
              {list.map((e) => (
                <EventCard key={e.id} event={e} />
              ))}
            </div>
          )
        }
      </QueryView>
    </>
  );
}

function EventCard({ event }: { readonly event: EventSummary }) {
  const allNamed = event.speakers > 0 && event.named === event.speakers;
  return (
    <Link to={`/videos/${encodeURIComponent(event.id)}`} className={styles.cardLink}>
      <Card as="article" className={styles.card}>
        <div className={styles.top}>
          <span className={styles.icon} aria-hidden="true">
            <Icon name={event.is_live ? 'voices' : 'video'} size={18} />
          </span>
          {event.is_live ? <Badge tone="error">live</Badge> : null}
          <span className={styles.duration}>{clock(event.audio_ms)}</span>
        </div>
        <h2 className={styles.title}>{event.title}</h2>
        <p className={styles.meta}>Ingested {date(event.started_at)}</p>
        <div className={styles.badges}>
          <Badge tone={allNamed ? 'ok' : event.named > 0 ? 'signal' : 'neutral'}>
            {event.named}/{event.speakers} speakers named
          </Badge>
          <Badge tone={event.transcripts > 0 ? 'signal' : 'warn'}>
            {count(event.transcripts, 'transcript')}
          </Badge>
        </div>
      </Card>
    </Link>
  );
}
