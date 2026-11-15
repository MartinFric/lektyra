import type { ReactNode } from 'react';
import type { UseQueryResult } from '@tanstack/react-query';
import type { AppError, ErrorCode } from '@/platform/api';

import { Button } from './Button';
import { Icon, type IconName } from './Icon';
import styles from './States.module.css';

/** Asking again cannot change these answers. */
const NO_RETRY: ReadonlySet<ErrorCode> = new Set(['not_found', 'invalid', 'contract']);

export function Skeleton({ lines = 3, height = 14 }: { readonly lines?: number; readonly height?: number }) {
  return (
    <div className={styles.skeleton} aria-busy="true" aria-label="Loading">
      {Array.from({ length: lines }, (_, i) => (
        <span key={i} className={styles.bar} style={{ height, width: `${String(92 - ((i * 17) % 40))}%` }} />
      ))}
    </div>
  );
}

interface EmptyStateProps {
  readonly icon?: IconName;
  readonly title: string;
  readonly children?: ReactNode;
  readonly action?: ReactNode;
}

export function EmptyState({ icon = 'doc', title, children, action }: EmptyStateProps) {
  return (
    <div className={styles.empty}>
      <span className={styles.emptyIcon}>
        <Icon name={icon} size={22} />
      </span>
      <h3 className={styles.emptyTitle}>{title}</h3>
      {children ? <p className={styles.emptyText}>{children}</p> : null}
      {action}
    </div>
  );
}

interface ErrorPanelProps {
  readonly error: AppError;
  readonly onRetry?: () => void;
  readonly retrying?: boolean;
}

export function ErrorPanel({ error, onRetry, retrying = false }: ErrorPanelProps) {
  return (
    <div className={styles.error} role="alert">
      <span className={styles.errorIcon}>
        <Icon name="alert" size={20} />
      </span>
      <div className={styles.errorBody}>
        <h3 className={styles.errorTitle}>{error.title}</h3>
        <p>{error.message}</p>
      </div>
      {onRetry ? (
        <Button size="sm" icon="refresh" onClick={onRetry} loading={retrying}>
          Try again
        </Button>
      ) : null}
    </div>
  );
}

interface QueryViewProps<T> {
  readonly query: UseQueryResult<T>;
  readonly children: (data: T) => ReactNode;
  readonly loading?: ReactNode;
}

/**
 * One way to show a query: a skeleton while it loads, an error panel with a retry, then the data. Once there is data,
 * a failed refresh keeps showing it (the query client toasts the failure): one failed poll of a live session must
 * not swap the whole screen for an error and restart its video (review 2026-11-15, point 2).
 */
export function QueryView<T>({ query, children, loading }: QueryViewProps<T>) {
  const data = query.data;
  if (data !== undefined) return <>{children(data)}</>;
  if (query.isPending) return <>{loading ?? <Skeleton />}</>;
  if (query.isError) {
    return (
      <ErrorPanel
        error={query.error}
        onRetry={NO_RETRY.has(query.error.code) ? undefined : () => void query.refetch()}
        retrying={query.isFetching}
      />
    );
  }
  return <>{loading ?? <Skeleton />}</>;
}
