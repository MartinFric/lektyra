import { type ReactNode, useId } from 'react';
import styles from './Popover.module.css';

interface PopoverProps {
  /** The trigger; it gets the attributes that open the panel. */
  readonly trigger: (props: { popoverTarget: string; 'aria-haspopup': 'dialog' }) => ReactNode;
  /** The panel's content; `close` hides it (after a choice). */
  readonly children: (close: () => void) => ReactNode;
  readonly label: string;
  readonly align?: 'start' | 'end';
  readonly width?: number;
}

/**
 * A panel anchored to its trigger, on the native Popover API: light dismiss, Escape and focus return come from the
 * browser, and the trigger is the panel's implicit anchor, so CSS `position-area` keeps it next to the trigger.
 * No effect, no document listeners.
 */
export function Popover({ trigger, children, label, align = 'start', width = 300 }: PopoverProps) {
  const id = useId();
  const close = () => {
    document.getElementById(id)?.hidePopover();
  };
  return (
    <span className={styles.anchor}>
      {trigger({ popoverTarget: id, 'aria-haspopup': 'dialog' })}
      <div
        id={id}
        popover="auto"
        role="dialog"
        aria-label={label}
        className={`${styles.panel} ${align === 'end' ? styles.end : ''}`}
        style={{ width }}
      >
        {children(close)}
      </div>
    </span>
  );
}
