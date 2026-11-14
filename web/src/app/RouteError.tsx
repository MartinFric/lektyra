import { isRouteErrorResponse, Link, useRouteError } from 'react-router';
import { AppError, toAppError } from '@/platform/api';
import { Card, EmptyState, ErrorPanel, LogoMark } from '@/platform/ui';
import styles from './AppShell.module.css';

/** A render error anywhere under the router lands here, as an AppError, with a way back. */
export function RouteError() {
  const raw = useRouteError();
  const error = isRouteErrorResponse(raw)
    ? new AppError(raw.status === 404 ? 'not_found' : 'internal', raw.statusText || 'This page failed.')
    : toAppError(raw);
  return (
    <main className={styles.fallback}>
      <LogoMark size={40} />
      <ErrorPanel error={error} />
      <Link to="/videos">Back to videos</Link>
    </main>
  );
}

export function NotFoundPage() {
  return (
    <Card>
      <EmptyState icon="search" title="Nothing here" action={<Link to="/videos">Back to videos</Link>}>
        This address is not a page of lektyra.
      </EmptyState>
    </Card>
  );
}
