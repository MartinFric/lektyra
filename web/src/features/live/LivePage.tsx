import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { Badge, Button, Card, Icon, PageHeader, QueryView, Skeleton } from '@/platform/ui';
import { isActive, liveSessionsQuery, type LiveState, uploadsQuery } from './api';
import { RecentVideos, ScheduleCard } from './Lists';
import { LiveSession } from './LiveSession';
import styles from './LivePage.module.css';
import { ScheduleDialog } from './ScheduleDialog';
import { sourceLabel } from './sources';
import { StartPanel } from './StartPanel';

/**
 * Live (ADR-013, ADR-016): sessions running now (several at once, as tabs), starting one, the schedule, and the
 * videos lektyra made. Which session is shown lives in the URL (?session=<id>, or ?session=new to start one).
 */
export function LivePage() {
  const sessions = useQuery(liveSessionsQuery);
  const [params, setParams] = useSearchParams();
  const [scheduling, setScheduling] = useState(false);
  const wanted = params.get('session');
  const select = (id: string) => { setParams({ session: id }, { replace: true }); };

  return (
    <>
      <PageHeader
        title="Live"
        subtitle="lektyra listens in real time: who speaks now, their voice number or name, and the words as each piece is ready."
        actions={
          <Button variant="primary" icon="calendar" onClick={() => { setScheduling(true); }}>
            Schedule…
          </Button>
        }
      />
      <QueryView query={sessions} loading={<Skeleton lines={6} height={24} />}>
        {(list) => {
          const running = list.filter((s) => isActive(s.status));
          const selected =
            wanted === 'new' ? null : (list.find((s) => s.id === wanted) ?? (wanted === null ? (running[0] ?? null) : null));
          return (
            <div className={styles.page}>
              {list.length > 0 ? <SessionTabs sessions={list} selected={selected?.id ?? 'new'} onSelect={select} /> : null}
              {selected && isActive(selected.status) ? (
                <LiveSession key={selected.id} state={selected} />
              ) : (
                <div className={styles.idle}>
                  {selected ? <LastSession state={selected} /> : null}
                  <StartPanel onStarted={(s) => { select(s.id); }} />
                </div>
              )}
            </div>
          );
        }}
      </QueryView>
      <div className={styles.lists}>
        <ScheduleCard onSchedule={() => { setScheduling(true); }} />
        <RecentVideos />
      </div>
      {scheduling ? <ScheduleDialog onClose={() => { setScheduling(false); }} /> : null}
    </>
  );
}

interface TabsProps {
  readonly sessions: readonly LiveState[];
  readonly selected: string;
  readonly onSelect: (id: string) => void;
}

/** One tab per session of this server (running first), and one to start another. */
function SessionTabs({ sessions, selected, onSelect }: TabsProps) {
  const uploads = useQuery(uploadsQuery);
  return (
    <div className={styles.tabs} role="tablist" aria-label="Live sessions">
      {sessions.slice(0, 8).map((s) => {
        const on = isActive(s.status);
        return (
          <button
            key={s.id}
            type="button"
            role="tab"
            aria-selected={selected === s.id}
            className={styles.tab}
            data-ended={!on || undefined}
            onClick={() => { onSelect(s.id); }}
          >
            {on ? <span className={styles.pulse} aria-hidden="true" /> : <Icon name={s.status === 'failed' ? 'alert' : 'check'} size={14} />}
            <span className={styles.tabText}>
              <strong>{s.title ?? sourceLabel(s.source, uploads.data)}</strong>
              <span>{on ? sourceLabel(s.source, uploads.data) : s.status}</span>
            </span>
          </button>
        );
      })}
      <button type="button" role="tab" aria-selected={selected === 'new'} className={styles.tab} onClick={() => { onSelect('new'); }}>
        <Icon name="plus" size={15} />
        <span className={styles.tabText}>
          <strong>Start another</strong>
          <span>several run at once</span>
        </span>
      </button>
    </div>
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
