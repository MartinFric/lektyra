import { useQuery } from '@tanstack/react-query';
import type { Speaker } from '@/features/events/api';
import { speakerName } from '@/features/events/speakerName';
import { FaceOf } from '@/features/persons/PersonFace';
import { clock } from '@/platform/format';
import { Badge, Card, CardHeader, Icon, QueryView, Skeleton } from '@/platform/ui';
import { type Claim, claimsQuery, KIND_LABELS, SOURCE_LABELS } from './api';
import styles from './ClaimsPanel.module.css';

interface ClaimsPanelProps {
  readonly eventId: string;
  /** A live session: claims grow every minute, the newest on top. */
  readonly live?: boolean;
  readonly speakers: ReadonlyMap<string, Speaker>;
  /** Jump the player to a claim; null where nothing plays. */
  readonly onSeek: ((ms: number) => void) | null;
}

/** The claims the claims loop found in this video (K29): the lekton, as said, who, where to check. Not checked yet. */
export function ClaimsPanel({ eventId, live = false, speakers, onSeek }: ClaimsPanelProps) {
  const claims = useQuery(claimsQuery(eventId, live));
  return (
    <Card padded={false} className={styles.panel}>
      <div className={styles.head}>
        <CardHeader
          title={`Claims${claims.data ? ` · ${String(claims.data.claims.filter((c) => c.status === 'open').length)}` : ''}`}
          subtitle={
            claims.data?.model
              ? `${claims.data.model.split('/').at(-1) ?? claims.data.model} · ${
                  claims.data.stage === 'final' ? 'after the end pass' : `read up to minute ${String(claims.data.minutes)}`
                } · not checked yet`
              : 'What can be checked, minute by minute. Not checked yet.'
          }
        />
      </div>
      <QueryView query={claims} loading={<div className={styles.pad}><Skeleton lines={4} height={40} /></div>}>
        {(view) =>
          view.claims.length === 0 ? (
            <p className={styles.empty}>
              <Icon name="doc" size={16} />
              {live ? 'No claims yet: they come about a minute after the words.' : 'No claims for this video yet.'}
            </p>
          ) : (
            <ol className={styles.list}>
              {(live ? [...view.claims].reverse() : view.claims).map((c) => (
                <ClaimItem key={c.id} claim={c} speakers={speakers} onSeek={onSeek} />
              ))}
            </ol>
          )
        }
      </QueryView>
    </Card>
  );
}

interface ItemProps {
  readonly claim: Claim;
  readonly speakers: ReadonlyMap<string, Speaker>;
  readonly onSeek: ((ms: number) => void) | null;
}

function ClaimItem({ claim, speakers, onSeek }: ItemProps) {
  const who = speakerName(claim.speaker, speakers);
  const speaker = speakers.get(claim.speaker);
  const faces =
    who.kind === 'mixed'
      ? (speaker?.overlap.map((o) => o.person_id) ?? [])
      : speaker !== undefined && speaker.person_id !== null
        ? [speaker.person_id]
        : [];
  return (
    <li className={styles.item} data-withdrawn={claim.status === 'withdrawn' || undefined}>
      <div className={styles.meta}>
        {onSeek ? (
          <button type="button" className={styles.time} onClick={() => { onSeek(claim.at_ms); }} title="Play from here">
            {clock(claim.at_ms)}
          </button>
        ) : (
          <span className={styles.time}>{clock(claim.at_ms)}</span>
        )}
        {faces.map((id) => (
          <FaceOf key={id} personId={id} size="xs" />
        ))}
        <span className={styles.who}>{who.text}</span>
        <span className={styles.spacer} />
        <span className={styles.worth} title="How worth checking: checkable × weight × new">
          {Math.round(claim.worth * 100)} %
        </span>
      </div>
      <p className={styles.lekton}>{claim.lekton}</p>
      {claim.quote ? <p className={styles.quote}>„{claim.quote}“</p> : null}
      <div className={styles.tags}>
        <Badge tone="claim">{KIND_LABELS[claim.kind] ?? claim.kind}</Badge>
        {claim.sources.map((s) => (
          <Badge key={s} tone="signal" title="Where it can be checked">
            {SOURCE_LABELS[s] ?? s}
          </Badge>
        ))}
        {claim.numbers.slice(0, 3).map((n) => (
          <span key={n} className={styles.number}>
            {n}
          </span>
        ))}
        {claim.links.length > 0 ? (
          <span className={styles.links} title={claim.links.map(([rel, other]) => `${rel} ${other}`).join(', ')}>
            {claim.links.map(([rel, other]) => `${rel} ${other}`).join(' · ')}
          </span>
        ) : null}
        {claim.status === 'withdrawn' ? <Badge>withdrawn</Badge> : null}
      </div>
    </li>
  );
}
