import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { Link, useNavigate } from 'react-router';
import { personsQuery } from '@/features/persons/api';
import { similarity, talkTime } from '@/platform/format';
import { Badge, Card, CardHeader, EmptyState, PageHeader, personColor, QueryView, Skeleton } from '@/platform/ui';
import { type VoicePoint, voicesQuery } from './api';
import styles from './VoicesPage.module.css';

const SIZE = 640;
const PAD = 40;

export function VoicesPage() {
  const voices = useQuery(voicesQuery);
  const persons = useQuery(personsQuery);
  return (
    <>
      <PageHeader
        title="Voice map"
        subtitle="Every speaker of every video as one dot. Close dots sound alike. The page is a flat picture of 192 numbers, so read the similarity in the tooltip, not the distance."
      />
      <QueryView query={voices} loading={<Card><Skeleton lines={10} height={24} /></Card>}>
        {(points) =>
          points.length === 0 ? (
            <Card>
              <EmptyState icon="voices" title="No voices yet">
                Diarize a video (<code>uv run lektyra diarize …</code>) and rescan folders.
              </EmptyState>
            </Card>
          ) : (
            <VoiceMap points={points} personOrder={(persons.data ?? []).map((p) => p.id)} />
          )
        }
      </QueryView>
    </>
  );
}

interface MapProps {
  readonly points: readonly VoicePoint[];
  readonly personOrder: readonly number[];
}

function VoiceMap({ points, personOrder }: MapProps) {
  const navigate = useNavigate();
  const [hover, setHover] = useState<VoicePoint | null>(null);
  const maxTalk = Math.max(...points.map((p) => p.talk_s), 1);
  const titles = new Map(points.map((p) => [p.event_id, p.event_title]));
  const colourOf = (p: VoicePoint) => (p.person_id === null ? 'var(--voice-unknown)' : personColor(personOrder.indexOf(p.person_id)));
  const xy = (p: VoicePoint) => ({
    cx: PAD + ((p.x + 1) / 2) * (SIZE - 2 * PAD),
    cy: PAD + ((1 - p.y) / 2) * (SIZE - 2 * PAD),
  });
  const named = new Map<number, string>();
  for (const p of points) if (p.person_id !== null && p.person_name) named.set(p.person_id, p.person_name);
  const legend = [...named.entries()].sort((a, b) => personOrder.indexOf(a[0]) - personOrder.indexOf(b[0]));
  const ordered = [...points].sort((a, b) => b.talk_s - a.talk_s);

  return (
    <div className={styles.layout}>
      <Card className={styles.mapCard}>
        <div className={styles.legend} aria-label="Legend">
          {legend.map(([id, name]) => (
            <span key={id} className={styles.key}>
              <span className={styles.swatch} style={{ background: personColor(personOrder.indexOf(id)) }} />
              {name}
            </span>
          ))}
          <span className={styles.key}>
            <span className={styles.swatch} style={{ background: 'var(--voice-unknown)' }} />
            not named
          </span>
          <span className={styles.key}>
            <span className={`${styles.swatch} ${styles.ring}`} />
            matched, not confirmed
          </span>
        </div>
        <div className={styles.plot}>
          <svg viewBox={`0 0 ${String(SIZE)} ${String(SIZE)}`} className={styles.svg} role="img" aria-label="Voice map">
            <line x1={SIZE / 2} y1={PAD / 2} x2={SIZE / 2} y2={SIZE - PAD / 2} className={styles.axis} />
            <line x1={PAD / 2} y1={SIZE / 2} x2={SIZE - PAD / 2} y2={SIZE / 2} className={styles.axis} />
            {ordered.map((p) => {
              const { cx, cy } = xy(p);
              const r = 6 + 10 * Math.sqrt(p.talk_s / maxTalk);
              const confirmed = p.status === 'confirmed';
              const guessed = p.status === 'auto' || p.status === 'suggested';
              return (
                <g
                  key={`${p.event_id}/${p.label}`}
                  className={styles.point}
                  onMouseEnter={() => { setHover(p); }}
                  onMouseLeave={() => { setHover(null); }}
                  onFocus={() => { setHover(p); }}
                  onBlur={() => { setHover(null); }}
                  onClick={() => { void navigate(`/videos/${encodeURIComponent(p.event_id)}`); }}
                  tabIndex={0}
                  role="link"
                  aria-label={`${p.label} in ${p.event_title}${p.person_name ? `, ${p.person_name}` : ''}`}
                >
                  <circle cx={cx} cy={cy} r={r + 8} fill="transparent" />
                  <circle
                    cx={cx}
                    cy={cy}
                    r={r}
                    fill={confirmed || p.person_id === null ? colourOf(p) : 'var(--surface)'}
                    fillOpacity={confirmed ? 0.9 : p.person_id === null ? 0.55 : 1}
                    stroke={guessed ? colourOf(p) : 'var(--surface)'}
                    strokeWidth={guessed ? 3 : 2}
                    strokeDasharray={p.status === 'suggested' ? '4 3' : undefined}
                  />
                </g>
              );
            })}
          </svg>
          {hover ? <Tooltip point={hover} at={xy(hover)} titles={titles} /> : null}
        </div>
      </Card>
      <Card>
        <CardHeader title="All voices" subtitle="Largest talk time first; the closest other voice beside each" />
        <table className={styles.table}>
          <colgroup>
            <col className={styles.colWhere} />
            <col className={styles.colWho} />
            <col />
          </colgroup>
          <thead>
            <tr>
              <th>Speaker</th>
              <th>Who</th>
              <th>Closest</th>
            </tr>
          </thead>
          <tbody>
            {ordered.map((p) => {
              const near = p.nearest[0];
              return (
                <tr key={`${p.event_id}/${p.label}`}>
                  <td>
                    <Link to={`/videos/${encodeURIComponent(p.event_id)}`} className={styles.where} title={p.event_title}>
                      <span className={styles.mono}>{p.label}</span> {p.event_title}
                    </Link>
                    <span className={styles.muted}>{talkTime(p.talk_s)}</span>
                  </td>
                  <td>{p.person_name ? <StatusName point={p} /> : <span className={styles.muted}>—</span>}</td>
                  <td>
                    {near ? (
                      <span className={styles.near} title={titles.get(near.event_id)}>
                        <span className={styles.nearName}>
                          <span className={styles.mono}>{near.label}</span> {titles.get(near.event_id) ?? ''}
                        </span>
                        <Badge tone={near.similarity >= 0.7 ? 'signal' : near.similarity >= 0.55 ? 'claim' : 'neutral'}>
                          {similarity(near.similarity)}
                        </Badge>
                      </span>
                    ) : null}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

function StatusName({ point }: { readonly point: VoicePoint }) {
  if (point.status === 'confirmed') return <strong>{point.person_name}</strong>;
  return (
    <span>
      {point.person_name} <Badge tone={point.status === 'auto' ? 'signal' : 'claim'}>{point.status === 'auto' ? 'auto' : 'maybe'}</Badge>
    </span>
  );
}

interface TooltipProps {
  readonly point: VoicePoint;
  readonly at: { readonly cx: number; readonly cy: number };
  readonly titles: ReadonlyMap<string, string>;
}

function Tooltip({ point, at, titles }: TooltipProps) {
  const left = `${String(Math.min(82, Math.max(18, (at.cx / SIZE) * 100)))}%`;
  const top = `${String((at.cy / SIZE) * 100)}%`;
  const below = at.cy < SIZE * 0.4;
  return (
    <div className={`${styles.tooltip} ${below ? styles.below : ''}`} style={{ left, top }} role="status">
      <div className={styles.tipHead}>
        <span className={styles.mono}>{point.label}</span>
        {point.person_name ? <StatusName point={point} /> : <span className={styles.muted}>not named</span>}
      </div>
      <div className={styles.muted}>
        {point.event_title} · {talkTime(point.talk_s)}
      </div>
      <div className={styles.tipNear}>
        {point.nearest.map((n) => (
          <div key={`${n.event_id}/${n.label}`} className={styles.tipRow}>
            <span>
              <span className={styles.mono}>{n.label}</span> {shortTitle(titles.get(n.event_id) ?? '')}
            </span>
            <strong className="tabular">{similarity(n.similarity)}</strong>
          </div>
        ))}
      </div>
    </div>
  );
}

function shortTitle(title: string): string {
  return title.length > 34 ? `${title.slice(0, 33)}…` : title;
}
