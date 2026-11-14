import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { Badge, Button, Card, Icon, PageHeader, QueryView, Skeleton } from '@/platform/ui';
import { isActive, liveSessionsQuery, type LiveState, uploadsQuery } from './api';
import { RecentVideos, ScheduleCard } from './Lists';
import { LiveSession } from './LiveSession';
import styles from './LivePage.module.css';
import { NowPanel } from './NowPanel';
import { ScheduleDialog } from './ScheduleDialog';
import { sourceLabel } from './sources';
import { StartDialog } from './StartDialog';

/**
 * Live (ADR-013, ADR-016): an overview (what is being transcribed now, the schedule, the latest videos) and each
 * session as a tab. Which one is shown lives in the URL (?session=<id>); none is the overview. Sessions run in the
 * background service: this page only shows them.
 */
export function LivePage() {
  const sessions = useQuery(liveSessionsQuery);
  const [params, setParams] = useSearchParams();
  const [dialog, setDialog] = useState<'start' | 'schedule' | null>(null);
  const wanted = params.get('session');
  const select = (id: string | null) => { setParams(id === null ? {} : { session: id }, { replace: true }); };

  return (
    <>
      <PageHeader
        title="Live"
        subtitle="What lektyra transcribes now, what it will transcribe, and what it made. Click a session to watch it."
        actions={
          <>
            <Button icon="play" onClick={() => { setDialog('start'); }}>
              Start now…
            </Button>
            <Button variant="primary" icon="calendar" onClick={() => { setDialog('schedule'); }}>
              Schedule…
            </Button>
          </>
        }
      />
      <QueryView query={sessions} loading={<Skeleton lines={6} height={24} />}>
        {(list) => {
          const selected = wanted === null ? null : (list.find((s) => s.id === wanted) ?? null);
          return (
            <div className={styles.page}>
              {list.length > 0 ? <SessionTabs sessions={list} selected={selected?.id ?? null} onSelect={select} /> : null}
              {selected === null ? (
                <>
                  <NowPanel sessions={list} onWatch={select} />
                  <div className={styles.lists}>
                    <ScheduleCard />
                    <RecentVideos />
                  </div>
                </>
              ) : isActive(selected.status) ? (
                <LiveSession key={selected.id} state={selected} />
              ) : (
                <div className={styles.idle}>
                  <LastSession state={selected} />
                </div>
              )}
            </div>
          );
        }}
      </QueryView>
      {dialog === 'start' ? (
        <StartDialog
          onClose={() => { setDialog(null); }}
          onStarted={(s) => {
            setDialog(null);
            select(s.id);
          }}
        />
      ) : null}
      {dialog === 'schedule' ? <ScheduleDialog onClose={() => { setDialog(null); }} /> : null}
    </>
  );
}

interface TabsProps {
  readonly sessions: readonly LiveState[];
  readonly selected: string | null;
  readonly onSelect: (id: string | null) => void;
}

/** The overview, then one tab per session of the service (running first). */
function SessionTabs({ sessions, selected, onSelect }: TabsProps) {
  const uploads = useQuery(uploadsQuery);
  return (
    <div className={styles.tabs} role="tablist" aria-label="Live sessions">
      <button type="button" role="tab" aria-selected={selected === null} className={styles.tab} onClick={() => { onSelect(null); }}>
        <Icon name="broadcast" size={15} />
        <span className={styles.tabText}>
          <strong>Overview</strong>
          <span>now, scheduled, videos</span>
        </span>
      </button>
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
