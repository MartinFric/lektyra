import { useCallback } from 'react';
import { type SpeakerName, speakerName } from '@/features/events/speakerName';
import { FaceOf } from '@/features/persons/PersonFace';
import type { Speaker } from '@/features/events/api';
import { clock } from '@/platform/format';
import { Icon, IconButton, voiceColor } from '@/platform/ui';
import { type Flag, flagLabel, type Paragraph } from './api';
import styles from './Paragraphs.module.css';

interface ParagraphsProps {
  readonly paragraphs: readonly Paragraph[];
  readonly speakers: ReadonlyMap<string, Speaker>;
  readonly flags: readonly Flag[];
  readonly active: number;
  readonly follow: boolean;
  readonly onSeek: (ms: number) => void;
  readonly onFlag: (paragraph: Paragraph) => void;
  /** How many shown claims a paragraph holds (K29); a chip on it picks them in the claims panel. */
  readonly claimsIn?: (paragraph: Paragraph) => number;
  readonly onClaims?: (paragraph: Paragraph) => void;
}

/** The transcript as people read it: who, when, what. The paragraph being heard is marked and, with `follow`,
 * kept in view by a ref callback that runs only when the active paragraph changes (no effect). */
export function Paragraphs({ paragraphs, speakers, flags, active, follow, onSeek, onFlag, claimsIn, onClaims }: ParagraphsProps) {
  const keepInView = useCallback(
    (el: HTMLElement | null) => {
      if (el && follow && el.dataset.index === String(active)) el.scrollIntoView({ block: 'center', behavior: 'smooth' });
    },
    [active, follow],
  );

  return (
    <ol className={styles.list}>
      {paragraphs.map((p, i) => {
        const name = speakerName(p.label, speakers);
        const previous = paragraphs[i - 1];
        const sameSpeaker = previous?.label === p.label;
        const flagged = flags.filter((f) => f.at_ms === p.start_ms);
        return (
          <li
            key={`${String(p.start_ms)}-${p.label}`}
            data-index={i}
            ref={i === active ? keepInView : undefined}
            className={`${styles.item} ${i === active ? styles.active : ''} ${sameSpeaker ? styles.continued : ''}`}
            style={{ '--voice': voiceColor(p.label) }}
          >
            <div className={styles.gutter}>
              <button type="button" className={styles.time} onClick={() => { onSeek(p.start_ms); }} title="Play from here">
                {clock(p.start_ms)}
              </button>
            </div>
            <div className={styles.body}>
              {sameSpeaker ? null : <SpeakerTag name={name} speaker={speakers.get(p.label)} />}
              <p className={styles.text}>{p.text}</p>
              {claimsIn && claimsIn(p) > 0 ? (
                <button type="button" className={styles.claimChip} onClick={() => { onClaims?.(p); }} title="Show them in the claims panel">
                  {claimsIn(p) === 1 ? '1 claim' : `${String(claimsIn(p))} claims`}
                </button>
              ) : null}
              {flagged.length > 0 ? (
                <div className={styles.flags}>
                  {flagged.map((f) => (
                    <span key={f.id} className={styles.flag} title={f.note || undefined}>
                      <Icon name="flag" size={12} /> {flagLabel(f.kind)}
                      {f.note ? `: ${f.note}` : ''}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
            <IconButton icon="flag" size="sm" label="Flag a mistake here" className={styles.flagButton} onClick={() => { onFlag(p); }} />
          </li>
        );
      })}
    </ol>
  );
}

function SpeakerTag({ name, speaker }: { readonly name: SpeakerName; readonly speaker: Speaker | undefined }) {
  const ids =
    name.kind === 'mixed'
      ? (speaker?.overlap.map((o) => o.person_id) ?? [])
      : speaker !== undefined && speaker.person_id !== null && (name.kind === 'named' || name.kind === 'auto' || name.kind === 'voice')
        ? [speaker.person_id]
        : [];
  return (
    <span className={`${styles.speaker} ${styles[name.kind] ?? ''}`}>
      <span className={styles.dot} aria-hidden="true" />
      {ids.map((id) => (
        <FaceOf key={id} personId={id} size="xs" />
      ))}
      {name.text}
      {name.kind === 'auto' ? <span className={styles.guess}>auto</span> : null}
    </span>
  );
}
