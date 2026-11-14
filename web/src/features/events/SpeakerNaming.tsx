import { type ReactNode, useState } from 'react';
import { FaceOf } from '@/features/persons/PersonFace';
import { PersonPicker } from '@/features/persons/PersonPicker';
import { similarity } from '@/platform/format';
import { Badge, Button, Icon, IconButton, Spinner } from '@/platform/ui';
import { type Speaker, useClearMixed, useNameSpeaker, useRejectCandidate, useUnnameSpeaker } from './api';
import { MixedDialog } from './MixedDialog';
import styles from './SpeakerNaming.module.css';

interface SpeakerNamingProps {
  readonly eventId: string;
  readonly speaker: Speaker;
  readonly compact?: boolean;
  /** Off where the card already shows the name large (the live screen): only the state and the actions. */
  readonly showName?: boolean;
}

interface Who {
  readonly id: number;
  readonly name: string;
}

/**
 * Who a speaker is, and the actions to settle it. One component for the speakers list, the player and the live
 * screen, so naming works the same everywhere.
 *
 * Every voice has a number that continues across videos (ADR-012). Naming a numbered voice names it in every video
 * it was heard in. A match to a named person is only a suggestion until Martin confirms it (ADR-004: a wrong name
 * is worse than unknown).
 */
export function SpeakerNaming({ eventId, speaker, compact = false, showName = true }: SpeakerNamingProps) {
  const name = useNameSpeaker(eventId);
  const unname = useUnnameSpeaker(eventId);
  const reject = useRejectCandidate(eventId);
  const clear = useClearMixed(eventId);
  const [mixing, setMixing] = useState(false);
  const busy = name.isPending || unname.isPending || reject.isPending || clear.isPending;
  const hints = speaker.candidates.map((c) => ({ personId: c.person_id, score: c.score }));
  const pick = (p: Who) => {
    name.mutate({ label: speaker.label, personId: p.id, personName: p.name });
  };
  const refuse = (p: Who) => {
    reject.mutate({ label: speaker.label, personId: p.id, personName: p.name });
  };
  const current: Who | null =
    speaker.person_id !== null && speaker.person_name !== null ? { id: speaker.person_id, name: speaker.person_name } : null;
  const row = (who: ReactNode, actions: ReactNode) => (
    <div className={styles.row} data-compact={compact || undefined}>
      <span className={styles.who}>{who}</span>
      <span className={styles.actions}>{actions}</span>
      {mixing ? <MixedDialog eventId={eventId} speaker={speaker} onClose={() => { setMixing(false); }} /> : null}
    </div>
  );
  /** Several known people talking at once (crosstalk): a label, never a voice (ADR-017). */
  const mixed = (
    <IconButton icon="users" size="sm" label={`Mixed: ${speaker.label} is several people at once…`} disabled={busy} onClick={() => { setMixing(true); }} />
  );

  /** Pick who it is. A tag names a speaker nobody named; a pencil changes a name. Icons only, named in the tooltip. */
  const picker = (kind: 'name' | 'change' | 'other') => (
    <PersonPicker
      label={kind === 'change' ? `Change who ${speaker.label} is` : kind === 'other' ? `Someone else: who is ${speaker.label}?` : `Name ${speaker.label}: who is it?`}
      onPick={pick}
      hints={hints}
      exclude={[...speaker.rejected, ...(speaker.person_anonymous && speaker.person_id !== null ? [speaker.person_id] : [])]}
      currentId={speaker.status === 'confirmed' ? speaker.person_id : null}
      align="end"
      iconOnly
    >
      <Icon name={kind === 'change' ? 'edit' : 'tag'} size={15} />
    </PersonPicker>
  );

  if (name.status === 'pending') {
    return (
      <div className={styles.row} data-compact={compact || undefined} role="status">
        <span className={styles.who}>
          <Spinner size={14} />
          <span className={styles.maybe}>
            Naming <strong className={styles.name}>{name.variables.personName}</strong>: learning the voice and
            matching the other videos…
          </span>
        </span>
      </div>
    );
  }

  // Mixed: several known people at once. Their faces and names; change who, or undo.
  if (speaker.status === 'overlap') {
    const names = speaker.overlap.map((o) => o.name).join(' + ');
    return row(
      <>
        {speaker.overlap.map((o) => (
          <FaceOf key={o.person_id} personId={o.person_id} size="xs" />
        ))}
        {showName ? <strong className={styles.name}>{names}</strong> : null}
        <Badge title="Several people talking at once: a label, no voice profile">mixed</Badge>
      </>,
      <>
        <IconButton icon="edit" size="sm" label={`Change who is mixed in ${speaker.label}`} disabled={busy} onClick={() => { setMixing(true); }} />
        <IconButton icon="x" size="sm" label={`${speaker.label} is not mixed`} disabled={busy} onClick={() => { clear.mutate(speaker.label); }} />
      </>,
    );
  }

  // A numbered voice nobody has named: give it a name (it reaches every video), or say it is someone else.
  if (current && speaker.person_anonymous) {
    const closest = speaker.candidates.find((c) => c.person_id !== current.id && c.score >= 0.55);
    const heardBefore = speaker.status === 'auto';
    return row(
      <>
        {showName ? (
          <>
            <FaceOf personId={current.id} size="xs" />
            <strong className={styles.voiceName}>{current.name}</strong>
          </>
        ) : null}
        {heardBefore ? (
          <Badge tone="signal" title="Matched to this voice from another video">
            heard before · {similarity(speaker.score ?? 0)}
          </Badge>
        ) : speaker.status === 'confirmed' ? (
          <Badge tone="ok">
            <Icon name="check" size={12} /> confirmed
          </Badge>
        ) : (
          <Badge title="First heard in this video">new voice</Badge>
        )}
        {closest && !compact ? (
          <span className={styles.closest} title="Similar to this person's samples, but not enough to be sure">
            maybe {closest.name} {similarity(closest.score)}
          </span>
        ) : null}
      </>,
      <>
        {closest ? (
          <Button size="sm" variant="secondary" icon="check" disabled={busy} onClick={() => { pick({ id: closest.person_id, name: closest.name }); }}>
            It is {shortName(closest.name)}
          </Button>
        ) : null}
        {heardBefore ? (
          <Button size="sm" variant="ghost" icon="x" disabled={busy} loading={reject.isPending} onClick={() => { refuse(current); }}>
            Other voice
          </Button>
        ) : null}
        {mixed}
        {picker('name')}
      </>,
    );
  }

  // 'new' with a name: the voice was first heard here and named since; it is as good as named.
  if ((speaker.status === 'confirmed' || speaker.status === 'new') && current) {
    return row(
      <>
        {showName ? (
          <>
            <FaceOf personId={current.id} size="sm" />
            <strong className={styles.name}>{current.name}</strong>
          </>
        ) : null}
        {compact ? (
          <span className={styles.check} title="Named by you">
            <Icon name="check" size={14} label="named" />
          </span>
        ) : (
          <Badge tone="ok">
            <Icon name="check" size={12} /> named
          </Badge>
        )}
      </>,
      <>
        {mixed}
        {picker('change')}
        <IconButton icon="x" size="sm" label={`Remove the name from ${speaker.label}`} disabled={busy} onClick={() => { unname.mutate(speaker.label); }} />
      </>,
    );
  }

  if ((speaker.status === 'auto' || speaker.status === 'suggested') && current) {
    const auto = speaker.status === 'auto';
    return row(
      <>
        <span className={styles.maybe}>{auto ? 'Sounds like' : 'Maybe'}</span>
        {showName ? (
          <>
            <FaceOf personId={current.id} size="xs" />
            <strong className={styles.name}>{current.name}</strong>
          </>
        ) : null}
        <Badge tone={auto ? 'signal' : 'claim'} title="Mean similarity of the closest samples (≥ 0.70 sure, ≥ 0.55 maybe)">
          {similarity(speaker.score ?? 0)}
        </Badge>
      </>,
      <>
        <Button size="sm" variant="primary" icon="check" disabled={busy} loading={name.isPending} onClick={() => { pick(current); }}>
          Confirm
        </Button>
        <Button size="sm" variant="ghost" icon="x" disabled={busy} loading={reject.isPending} onClick={() => { refuse(current); }}>
          Not {shortName(current.name)}
        </Button>
        {mixed}
        {picker('other')}
      </>,
    );
  }

  return row(
    <>
      <span className={styles.unknown}>{speaker.no_profile ? 'Forgotten voice' : 'Unknown voice'}</span>
      {!compact ? (
        <span className={styles.closest}>
          {speaker.no_profile ? 'no profile is kept' : 'too little clear speech for a voice profile'}
        </span>
      ) : null}
    </>,
    <>
      {mixed}
      {picker('name')}
    </>,
  );
}

/** "Robert Fico" → "Fico" (how a guest is referred to on air, short enough for a button); "Voice 5" stays whole. */
function shortName(name: string): string {
  if (/^Voice \d+$/.test(name)) return name;
  return name.trim().split(/\s+/).at(-1) ?? name;
}
