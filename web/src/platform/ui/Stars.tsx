import { useId } from 'react';
import { Icon } from './Icon';
import styles from './Stars.module.css';

interface StarsProps {
  readonly label: string;
  readonly value: number | null;
  readonly onChange: (value: number | null) => void;
  readonly disabled?: boolean;
}

const WORDS = ['', 'unusable', 'poor', 'usable', 'good', 'excellent'] as const;

/** A 1–5 score as a radio group: arrow keys work, and clicking the chosen star again clears it. */
export function Stars({ label, value, onChange, disabled = false }: StarsProps) {
  const name = useId();
  return (
    <fieldset className={styles.stars} disabled={disabled}>
      <legend className={styles.legend}>{label}</legend>
      <div className={styles.row}>
        {[1, 2, 3, 4, 5].map((n) => (
          <label key={n} className={styles.star} data-on={value !== null && n <= value} title={WORDS[n]}>
            <input
              type="radio"
              name={name}
              value={n}
              checked={value === n}
              onChange={() => { onChange(n); }}
              onClick={() => {
                if (value === n) onChange(null);
              }}
              className="visually-hidden"
            />
            <Icon name="star" size={20} filled={value !== null && n <= value} />
            <span className="visually-hidden">{`${String(n)} – ${WORDS[n] ?? ''}`}</span>
          </label>
        ))}
        <span className={styles.word}>{value === null ? 'not rated' : WORDS[value]}</span>
      </div>
    </fieldset>
  );
}
