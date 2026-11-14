import type { HTMLAttributes, ReactNode } from 'react';
import styles from './Card.module.css';

interface CardProps extends HTMLAttributes<HTMLElement> {
  readonly as?: 'section' | 'article' | 'div';
  readonly padded?: boolean;
}

export function Card({ as: Tag = 'section', padded = true, className, children, ...rest }: CardProps) {
  const classes = [styles.card, padded ? styles.padded : '', className].filter(Boolean).join(' ');
  return (
    <Tag {...rest} className={classes}>
      {children}
    </Tag>
  );
}

interface CardHeaderProps {
  readonly title: ReactNode;
  readonly subtitle?: ReactNode;
  readonly actions?: ReactNode;
}

export function CardHeader({ title, subtitle, actions }: CardHeaderProps) {
  return (
    <header className={styles.header}>
      <div className={styles.titles}>
        <h2 className={styles.title}>{title}</h2>
        {subtitle ? <p className={styles.subtitle}>{subtitle}</p> : null}
      </div>
      {actions ? <div className={styles.actions}>{actions}</div> : null}
    </header>
  );
}
