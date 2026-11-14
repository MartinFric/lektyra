import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router';
import { Badge, Card, Icon, PageHeader, QueryView, Skeleton } from '@/platform/ui';
import { isActive, liveQuery, type LiveState } from './api';
import { LiveSession } from './LiveSession';
import styles from './LivePage.module.css';
import { StartPanel } from './StartPanel';

/** Live: start a session on a stream or a downloaded video, then hear it, see who speaks and name them (ADR-013). */
export function LivePage() {
  const live = useQuery(liveQuery);
  return (
    <>
      <PageHeader
        title="Live"
        subtitle="lektyra listens in real time: who speaks now, their voice number or name, and the words as each piece is ready."
      />
      <QueryView query={live} loading={<Skeleton lines={6} height={24} />}>
        {(state) =>
          state && isActive(state.status) ? (
            <LiveSession state={state} />
          ) : (
            <div className={styles.idle}>
              {state ? <LastSession state={state} /> : null}
              <StartPanel />
            </div>
          )
        }
      </QueryView>
    </>
  );
}

function LastSession({ state }: { readonly state: LiveState }) {
  const failed = state.status === 'failed';
  return (
    <Card className={failed ? styles.failed : styles.finished}>
      <div className={styles.lastRow}>
        <Icon name={failed ? 'alert' : 'check'} size={20} />
        <div className={styles.lastText}>
          <strong>{state.title ?? state.source}</strong>
          <span className={styles.muted}>{state.message}</span>
        </div>
        <Badge tone={failed ? 'error' : 'ok'}>{failed ? 'failed' : 'finished'}</Badge>
        {state.event_id ? (
          <Link to={`/videos/${encodeURIComponent(state.event_id)}`} className={styles.open}>
            Open the video <Icon name="chevron" size={15} />
          </Link>
        ) : null}
      </div>
    </Card>
  );
}
