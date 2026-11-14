import { type ReactNode, useId } from 'react';
import { IconButton } from './Button';
import styles from './Dialog.module.css';

interface DialogProps {
  readonly title: string;
  readonly onClose: () => void;
  readonly children: ReactNode;
  readonly footer?: ReactNode;
  readonly tone?: 'default' | 'danger';
}

/**
 * A modal on the native <dialog>: focus trap, Escape and the backdrop come from the browser. Render it only while
 * it is open; the ref callback opens it as it mounts (no effect needed).
 */
export function Dialog({ title, onClose, children, footer, tone = 'default' }: DialogProps) {
  const titleId = useId();
  return (
    <dialog
      className={`${styles.dialog} ${tone === 'danger' ? styles.danger : ''}`}
      ref={(el) => {
        if (el && !el.open) el.showModal();
      }}
      onClose={onClose}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      aria-labelledby={titleId}
    >
      <div className={styles.panel}>
        <header className={styles.header}>
          <h2 id={titleId} className={styles.title}>
            {title}
          </h2>
          <IconButton icon="x" label="Close" size="sm" onClick={onClose} />
        </header>
        <div className={styles.body}>{children}</div>
        {footer ? <footer className={styles.footer}>{footer}</footer> : null}
      </div>
    </dialog>
  );
}
