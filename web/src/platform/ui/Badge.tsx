import type { ReactNode } from 'react';
import styles from './Badge.module.css';

export type Tone = 'neutral' | 'signal' | 'claim' | 'ok' | 'warn' | 'error';

interface BadgeProps {
  readonly tone?: Tone;
  readonly children: ReactNode;
  readonly title?: string;
}

export function Badge({ tone = 'neutral', children, title }: BadgeProps) {
  return (
    <span className={`${styles.badge} ${styles[tone]}`} title={title}>
      {children}
    </span>
  );
}
