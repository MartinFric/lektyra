import { useRef } from 'react';
import type { Speaker } from '@/features/events/api';
import { speakerName } from '@/features/events/speakerName';
import { FaceOf } from '@/features/persons/PersonFace';
import { clock } from '@/platform/format';
import { Badge, Card, CardHeader, Icon, QueryView, Select, Skeleton } from '@/platform/ui';
import { type Claim, KIND_LABELS, SOURCE_LABELS } from './api';
import styles from './ClaimsPanel.module.css';
import { countBy, toggle, WORTH_STEPS } from './filter';
import type { ClaimsState } from './useClaims';

interface ClaimsPanelProps {
  readonly claims: ClaimsState;
  /** A live session: claims grow every minute, the newest on top. */
  readonly live?: boolean;
  readonly speakers: ReadonlyMap<string, Speaker>;
  /** Jump the player to a claim; null where nothing plays. */
  readonly onSeek: ((ms: number) => void) | null;
  /** The claim to mark and keep in view: the one being heard, or the one picked in the transcript. */
  readonly highlight?: string | null;
}

/** "Robert Fico" → "Fico"; a voice number or a mixed speaker stays whole. */
function short(text: string): string {
  return /^Voice \d+$/.test(text) || text.includes(' + ') ? text : (text.trim().split(/\s+/).at(-1) ?? text);
}

/**
 * The claims the claims loop found (K29), about two a minute: filtered by worth (the worth-checking ones by
 * default), speaker and kind, sorted by time or worth. Not checked yet: no verdicts here.
 */
export function ClaimsPanel({ claims, live = false, speakers, onSeek, highlight = null }: ClaimsPanelProps) {
  const { query, filter, setFilter, all, shown } = claims;
  const open = all.filter((c) => c.status === 'open').length;
  const bySpeaker = countBy(all, filter.minWorth, 'speaker');
  const byKind = countBy(all, filter.minWorth, 'kind');
  const list = live && filter.sort === 'time' ? [...shown].reverse() : shown;
  // Scroll the list to the current claim only when it changes, not on every render (playback re-renders about four
  // times a second, and a scroll then would fight the reader's own: review 2026-11-15, point 3).
  const scrolledTo = useRef<string | null>(null);
  const keepInView = (el: HTMLLIElement | null, id: string) => {
    const box = el?.parentElement;
    if (!el || !box || scrolledTo.current === id) return;
    scrolledTo.current = id;
    box.scrollTop = Math.max(0, el.offsetTop - 8);
  };

  return (
    <Card padded={false} className={styles.panel}>
      <div className={styles.head}>
        <CardHeader
          title={`Claims · ${String(shown.length)}${shown.length === open ? '' : ` of ${String(open)}`}`}
          subtitle={
            query.data?.model
              ? `${query.data.model.split('/').at(-1) ?? query.data.model} · ${
                  query.data.stage === 'final' ? 'after the end pass' : `read up to minute ${String(query.data.minutes)}`
                }${query.data.hidden_host > 0 ? ` · ${String(query.data.hidden_host)} by hosts or audience left out` : ''} · not checked yet`
              : 'What can be checked, minute by minute. Not checked yet.'
          }
        />
        {open > 0 ? (
          <div className={styles.filters}>
            <div className={styles.filterRow}>
              <Select
                aria-label="How worth checking"
                className={styles.worth}
                value={String(filter.minWorth)}
                onChange={(e) => { setFilter({ ...filter, minWorth: Number(e.target.value) }); }}
              >
                {WORTH_STEPS.map((s) => (
                  <option key={s.value} value={String(s.value)}>
                    {s.label}
                  </option>
                ))}
              </Select>
              <span className={styles.sort} role="group" aria-label="Order">
                {(['time', 'worth'] as const).map((s) => (
                  <button
                    key={s}
                    type="button"
                    aria-pressed={filter.sort === s}
                    className={styles.sortButton}
                    onClick={() => { setFilter({ ...filter, sort: s }); }}
                  >
                    {s === 'time' ? (live ? 'newest' : 'time') : 'worth'}
                  </button>
                ))}
              </span>
            </div>
            <div className={styles.chips} role="group" aria-label="Who">
              {bySpeaker.map(([label, n]) => {
                const s = speakers.get(label);
                const name = speakerName(label, speakers).text;
                return (
                  <button
                    key={label}
                    type="button"
                    className={styles.chip}
                    aria-pressed={filter.speakers.includes(label)}
                    title={name}
                    onClick={() => { setFilter({ ...filter, speakers: toggle(filter.speakers, label) }); }}
                  >
                    {s && s.person_id !== null ? <FaceOf personId={s.person_id} size="xs" /> : null}
                    {short(name)} <span className={styles.count}>{n}</span>
                  </button>
                );
              })}
            </div>
            <div className={styles.chips} role="group" aria-label="Kind">
              {byKind.map(([kind, n]) => (
                <button
                  key={kind}
                  type="button"
                  className={styles.chip}
                  data-kind
                  aria-pressed={filter.kinds.includes(kind)}
                  onClick={() => { setFilter({ ...filter, kinds: toggle(filter.kinds, kind) }); }}
                >
                  {KIND_LABELS[kind] ?? kind} <span className={styles.count}>{n}</span>
                </button>
              ))}
            </div>
          </div>
        ) : null}
      </div>
      <QueryView query={query} loading={<div className={styles.pad}><Skeleton lines={4} height={40} /></div>}>
        {() =>
          list.length === 0 ? (
            <p className={styles.empty}>
              <Icon name="doc" size={16} />
              {open > 0
                ? 'No claim matches: lower the worth or clear a filter.'
                : live
                  ? 'No claims yet: they come about a minute after the words.'
                  : 'No claims for this video yet.'}
            </p>
          ) : (
            <ol className={styles.list}>
              {list.map((c) => (
                <ClaimItem
                  key={c.id}
                  claim={c}
                  speakers={speakers}
                  onSeek={onSeek}
                  current={c.id === highlight}
                  keepInView={keepInView}
                />
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
  readonly current: boolean;
  readonly keepInView: (el: HTMLLIElement | null, id: string) => void;
}

function ClaimItem({ claim, speakers, onSeek, current, keepInView }: ItemProps) {
  const who = speakerName(claim.speaker, speakers);
  const speaker = speakers.get(claim.speaker);
  const faces =
    who.kind === 'mixed'
      ? (speaker?.overlap.map((o) => o.person_id) ?? [])
      : speaker !== undefined && speaker.person_id !== null
        ? [speaker.person_id]
        : [];
  return (
    <li
      className={styles.item}
      data-current={current || undefined}
      ref={current ? (el) => { keepInView(el, claim.id); } : undefined}
    >
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
        <span className={styles.worthValue} data-high={claim.worth >= 0.85 || undefined} title="How worth checking: checkable × weight × new">
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
      </div>
    </li>
  );
}
