import { useQuery } from '@tanstack/react-query';
import { NavLink, Outlet } from 'react-router';
import { useSync } from '@/features/events/api';
import { isActive, liveSessionsQuery } from '@/features/live/api';
import { Button, Icon, type IconName, LogoMark } from '@/platform/ui';
import styles from './AppShell.module.css';

const NAV: readonly { readonly to: string; readonly label: string; readonly icon: IconName }[] = [
  { to: '/live', label: 'Live', icon: 'broadcast' },
  { to: '/videos', label: 'Videos', icon: 'video' },
  { to: '/persons', label: 'Persons', icon: 'users' },
  { to: '/voices', label: 'Voice map', icon: 'voices' },
];

export function AppShell() {
  const sync = useSync();
  const sessions = useQuery(liveSessionsQuery);
  const live = (sessions.data ?? []).filter((s) => isActive(s.status)).length;
  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>
        <NavLink to="/videos" className={styles.brand} aria-label="lektyra home">
          <LogoMark size={34} />
          <span className={styles.wordmark}>lektyra</span>
        </NavLink>
        <nav className={styles.nav} aria-label="Main">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => `${styles.link} ${isActive ? styles.active : ''}`}
            >
              <Icon name={item.icon} size={18} />
              {item.label}
              {item.to === '/live' && live > 0 ? (
                <span className={styles.live} title={`${String(live)} live session(s) running`}>
                  <span className={styles.pulse} aria-hidden="true" />
                  {live}
                </span>
              ) : null}
            </NavLink>
          ))}
        </nav>
        <div className={styles.foot}>
          <Button
            size="sm"
            variant="ghost"
            icon="refresh"
            loading={sync.isPending}
            onClick={() => { sync.mutate(); }}
            title="Videos made in a terminal (lektyra ingest, diarize, transcribe) appear without restarting lektyra ui"
          >
            Look for new videos
          </Button>
          <p className={styles.local}>
            <span className={styles.dot} aria-hidden="true" />
            Local · data stays on this PC
          </p>
        </div>
      </aside>
      <main className={styles.main}>
        <div className={styles.content}>
          <Outlet />
        </div>
      </main>
    </div>
  );
}
