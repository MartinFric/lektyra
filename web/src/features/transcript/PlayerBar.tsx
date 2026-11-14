import type { KeyboardEvent, MouseEvent } from 'react';
import { clock } from '@/platform/format';
import { Icon, IconButton, voiceColor } from '@/platform/ui';
import type { Turn } from './api';
import styles from './PlayerBar.module.css';
import type { Player } from './usePlayer';

const RATES = [1, 1.25, 1.5, 2] as const;

export interface ClaimMark {
  readonly id: string;
  readonly at_ms: number;
  readonly worth: number;
}

interface PlayerBarProps {
  readonly player: Player;
  readonly turns: readonly Turn[];
  readonly src: string;
  /** Claims shown in the claims panel, as ticks over the timeline: where they cluster, at a glance. */
  readonly marks?: readonly ClaimMark[];
}

/** Play, skip, speed, and a timeline coloured by who speaks: a click anywhere on it jumps there. */
export function PlayerBar({ player, turns, src, marks = [] }: PlayerBarProps) {
  const { now, duration, playing } = player;
  const total = Math.max(duration, 1);

  const seekFromPointer = (e: MouseEvent<HTMLDivElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    const share = Math.min(1, Math.max(0, (e.clientX - box.left) / box.width));
    player.seek(share * total, playing);
  };

  const seekFromKeys = (e: KeyboardEvent<HTMLDivElement>) => {
    const steps: Record<string, number> = { ArrowLeft: -5_000, ArrowRight: 5_000, PageDown: -60_000, PageUp: 60_000 };
    const delta = steps[e.key];
    if (delta !== undefined) {
      e.preventDefault();
      player.skip(delta);
    } else if (e.key === 'Home') {
      e.preventDefault();
      player.seek(0, playing);
    }
  };

  return (
    <div className={styles.bar}>
      <audio {...player.audioProps} src={src} />
      <div className={styles.controls}>
        <IconButton icon="rewind" label="Back 10 seconds" onClick={() => { player.skip(-10_000); }} />
        <button
          type="button"
          className={styles.play}
          onClick={player.toggle}
          aria-label={playing ? 'Pause' : 'Play'}
          disabled={player.broken !== null}
        >
          <Icon name={playing ? 'pause' : 'play'} size={20} />
        </button>
        <IconButton icon="forward" label="Forward 10 seconds" onClick={() => { player.skip(10_000); }} />
      </div>
      <span className={styles.time}>
        {clock(now)} <span className={styles.of}>/ {clock(duration)}</span>
      </span>
      <div
        className={styles.track}
        role="slider"
        tabIndex={0}
        aria-label="Position"
        aria-valuemin={0}
        aria-valuemax={Math.round(total / 1000)}
        aria-valuenow={Math.round(now / 1000)}
        aria-valuetext={clock(now)}
        onClick={seekFromPointer}
        onKeyDown={seekFromKeys}
      >
        {turns.map((t) => (
          <span
            key={`${String(t.start_ms)}-${t.label}`}
            className={styles.turn}
            style={{
              left: `${String((t.start_ms / total) * 100)}%`,
              width: `${String(Math.max(0.15, ((t.end_ms - t.start_ms) / total) * 100))}%`,
              background: voiceColor(t.label),
            }}
          />
        ))}
        {marks.map((m) => (
          <span
            key={m.id}
            className={styles.mark}
            style={{ left: `${String((m.at_ms / total) * 100)}%`, opacity: String(0.35 + m.worth * 0.65) }}
          />
        ))}
        <span className={styles.head} style={{ left: `${String(Math.min(100, (now / total) * 100))}%` }} />
      </div>
      <label className={styles.rate}>
        <span className="visually-hidden">Speed</span>
        <select value={player.rate} onChange={(e) => { player.setRate(Number(e.target.value)); }}>
          {RATES.map((r) => (
            <option key={r} value={r}>
              {r}×
            </option>
          ))}
        </select>
      </label>
      {player.broken ? (
        <span className={styles.broken} role="alert">
          {player.broken}
        </span>
      ) : null}
    </div>
  );
}
