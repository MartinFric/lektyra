import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router';
import { ratingsQuery } from '@/features/transcript/api';
import { ReelButton } from '@/features/voices/Reel';
import { clock, engineName, talkTime } from '@/platform/format';
import { useRequiredParam } from '@/platform/routing';
import { Badge, Card, CardHeader, EmptyState, Icon, PageHeader, QueryView, Skeleton, voiceColor } from '@/platform/ui';
import { type EventDetail, eventQuery, isComplete, type Speaker, speakersQuery } from './api';
import styles from './EventPage.module.css';
import { SpeakerNaming } from './SpeakerNaming';

export function EventPage() {
  const eventId = useRequiredParam('eventId');
  const event = useQuery(eventQuery(eventId));
  return (
    <QueryView query={event} loading={<Skeleton lines={8} height={22} />}>
      {(e) => <EventView event={e} />}
    </QueryView>
  );
}

function EventView({ event }: { readonly event: EventDetail }) {
  const speakers = useQuery(speakersQuery(event.id));
  const best = event.variants.find(isComplete);
  return (
    <>
      <PageHeader
        back={{ to: '/videos', label: 'Videos' }}
        title={event.title}
        subtitle={
          <>
            <span className="tabular">{clock(event.audio_ms)}</span>
            {event.complete === false ? <Badge tone="warn">incomplete audio</Badge> : null}
            {event.is_live ? <Badge tone="error">live</Badge> : null}
            {event.source_url.startsWith('http') ? (
              <a href={event.source_url} target="_blank" rel="noreferrer" className={styles.source}>
                source <Icon name="external" size={13} />
              </a>
            ) : (
              <span>{event.source_url}</span>
            )}
          </>
        }
        actions={
          best ? (
            <Link to={`transcripts/${encodeURIComponent(best.id)}`} className={styles.primaryLink}>
              <Icon name="play" size={15} /> Listen and read
            </Link>
          ) : null
        }
      />
      <div className={styles.layout}>
        <Card>
          <CardHeader
            title="Speakers"
            subtitle="Voices found in this video, most talk first. Naming one teaches lektyra that voice for every other video."
          />
          <QueryView query={speakers} loading={<Skeleton lines={4} height={34} />}>
            {(list) =>
              list.length === 0 ? (
                <EmptyState icon="voices" title="No speakers yet">
                  Run <code>uv run lektyra diarize {shortId(event.id)}</code>, then Look for new videos.
                </EmptyState>
              ) : (
                <SpeakerList eventId={event.id} speakers={list} />
              )
            }
          </QueryView>
        </Card>
        <div className={styles.side}>
          <TranscriptsCard event={event} />
          <DocumentsCard event={event} />
        </div>
      </div>
    </>
  );
}

function SpeakerList({ eventId, speakers }: { readonly eventId: string; readonly speakers: readonly Speaker[] }) {
  return (
    <ul className={styles.speakers}>
      {speakers.map((s) => (
        <li key={s.label} className={styles.speaker}>
          <div className={styles.speakerHead}>
            <span className={styles.voice} style={{ background: voiceColor(s.label) }} aria-hidden="true" />
            <strong className={styles.label}>{s.label}</strong>
            <ReelButton source={{ kind: 'speaker', eventId, label: s.label }} showWhere={false} />
            <span className={styles.talk}>
              {talkTime(s.talk_s)} · {Math.round(s.share * 100)} %
            </span>
            <span className={styles.shareTrack} aria-hidden="true">
              <span className={styles.shareBar} style={{ width: `${String(Math.max(2, s.share * 100))}%`, background: voiceColor(s.label) }} />
            </span>
          </div>
          <SpeakerNaming eventId={eventId} speaker={s} />
        </li>
      ))}
    </ul>
  );
}

function TranscriptsCard({ event }: { readonly event: EventDetail }) {
  const ratings = useQuery(ratingsQuery(event.id));
  const complete = event.variants.filter(isComplete);
  const partial = event.variants.length - complete.length;
  return (
    <Card>
      <CardHeader title="Transcripts" subtitle={partial > 0 ? `${String(partial)} partial (screening windows) not listed` : undefined} />
      {complete.length === 0 ? (
        <EmptyState icon="doc" title="No full transcript yet">
          Run <code>uv run lektyra transcribe {shortId(event.id)} --language sk --models elevenlabs/scribe-v2</code>.
        </EmptyState>
      ) : (
        <ul className={styles.variants}>
          {complete.map((v) => {
            const rating = ratings.data?.find((r) => r.variant === v.id);
            return (
              <li key={v.id}>
                <Link to={`transcripts/${encodeURIComponent(v.id)}`} className={styles.variant}>
                  <span className={styles.variantName}>{engineName(v.engine, v.language)}</span>
                  {rating?.accuracy ? (
                    <Badge tone="claim" title="Your accuracy rating">
                      <Icon name="star" size={12} filled /> {rating.accuracy}
                    </Badge>
                  ) : (
                    <Badge>not rated</Badge>
                  )}
                  <Icon name="chevron" size={16} />
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}

function DocumentsCard({ event }: { readonly event: EventDetail }) {
  if (event.documents.length === 0) return null;
  return (
    <Card>
      <CardHeader title="Documents" subtitle="Reports lektyra wrote next to the audio" />
      <ul className={styles.variants}>
        {event.documents.map((d) => (
          <li key={d.name}>
            <Link to={`documents/${encodeURIComponent(d.name)}`} className={styles.variant}>
              <Icon name="doc" size={16} />
              <span className={styles.variantName}>{d.name}</span>
              <Icon name="chevron" size={16} />
            </Link>
          </li>
        ))}
      </ul>
    </Card>
  );
}

/** The part of a folder name after the time stamp: enough for the CLI's selector. */
function shortId(id: string): string {
  return id.replace(/^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}_/, '');
}
