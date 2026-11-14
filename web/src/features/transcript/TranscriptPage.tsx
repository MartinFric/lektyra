import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useNavigate } from 'react-router';
import { type EventDetail, eventQuery, isComplete, type Speaker, speakersQuery } from '@/features/events/api';
import { SpeakerNaming } from '@/features/events/SpeakerNaming';
import { byLabel, speakerName } from '@/features/events/speakerName';
import { apiUrl, seg } from '@/platform/api';
import { clock, count, engineName, talkTime } from '@/platform/format';
import { useRequiredParam } from '@/platform/routing';
import {
  Badge,
  Card,
  CardHeader,
  Checkbox,
  EmptyState,
  IconButton,
  PageHeader,
  QueryView,
  Skeleton,
  voiceColor,
} from '@/platform/ui';
import { type Flag, flagLabel, flagsQuery, type Paragraph, ratingsQuery, type Transcript, transcriptQuery, useDeleteFlag } from './api';
import { FlagDialog } from './FlagDialog';
import { Paragraphs } from './Paragraphs';
import { PlayerBar } from './PlayerBar';
import { RatingPanel } from './RatingPanel';
import { activeAt, lastStartedAt } from './timeline';
import styles from './TranscriptPage.module.css';
import { type Player, usePlayer } from './usePlayer';

export function TranscriptPage() {
  const eventId = useRequiredParam('eventId');
  const variant = useRequiredParam('variant');
  const event = useQuery(eventQuery(eventId));
  const transcript = useQuery(transcriptQuery(eventId, variant));
  return (
    <QueryView query={event} loading={<Skeleton lines={10} height={20} />}>
      {(e) => (
        <QueryView query={transcript} loading={<Skeleton lines={10} height={20} />}>
          {(t) => <TranscriptView key={variant} event={e} variant={variant} transcript={t} />}
        </QueryView>
      )}
    </QueryView>
  );
}

interface ViewProps {
  readonly event: EventDetail;
  readonly variant: string;
  readonly transcript: Transcript;
}

function TranscriptView({ event, variant, transcript }: ViewProps) {
  const navigate = useNavigate();
  const player = usePlayer(event.audio_ms);
  const speakers = useQuery(speakersQuery(event.id));
  const flags = useQuery(flagsQuery(event.id, variant));
  const [follow, setFollow] = useState(true);
  const [flagging, setFlagging] = useState<Paragraph | null>(null);
  const byName = byLabel(speakers.data ?? []);
  const active = lastStartedAt(transcript.paragraphs, player.now);
  const current = activeAt(transcript.turns, player.now);
  const info = event.variants.find((v) => v.id === variant);
  const choices = event.variants.filter(isComplete);

  return (
    <>
      <PageHeader
        back={{ to: `/videos/${encodeURIComponent(event.id)}`, label: event.title }}
        title={info ? engineName(info.engine, info.language) : variant}
        subtitle={
          <>
            <span>{transcript.words.toLocaleString('en-GB')} words</span>
            <span>{count(transcript.paragraphs.length, 'paragraph')}</span>
            {transcript.unknown_words > 0 ? (
              <span>{count(transcript.unknown_words, 'word')} without a speaker</span>
            ) : null}
          </>
        }
        actions={
          choices.length > 1 ? (
            <label className={styles.variantSelect}>
              <span className={styles.muted}>Transcript</span>
              <select
                value={variant}
                onChange={(e) => {
                  void navigate(`/videos/${encodeURIComponent(event.id)}/transcripts/${encodeURIComponent(e.target.value)}`);
                }}
              >
                {choices.map((v) => (
                  <option key={v.id} value={v.id}>
                    {engineName(v.engine, v.language)}
                  </option>
                ))}
              </select>
            </label>
          ) : null
        }
      />

      <div className={styles.sticky}>
        {event.has_audio ? (
          <PlayerBar player={player} turns={transcript.turns} src={apiUrl(`/events/${seg(event.id)}/audio`)} />
        ) : (
          <Card>
            <EmptyState icon="alert" title="No audio for this video">The transcript can be read; it cannot be played.</EmptyState>
          </Card>
        )}
      </div>

      <div className={styles.layout}>
        <Card padded={false} className={styles.reader}>
          <div className={styles.readerHead}>
            <h2 className={styles.readerTitle}>Transcript</h2>
            <Checkbox
              label="Follow playback"
              checked={follow}
              onChange={(e) => { setFollow(e.target.checked); }}
            />
          </div>
          {transcript.paragraphs.length === 0 ? (
            <EmptyState icon="doc" title="No words in this transcript" />
          ) : (
            <Paragraphs
              paragraphs={transcript.paragraphs}
              speakers={byName}
              flags={flags.data ?? []}
              active={active}
              follow={follow && player.playing}
              onSeek={(ms) => { player.seek(ms); }}
              onFlag={setFlagging}
            />
          )}
        </Card>

        <aside className={styles.side}>
          <Card className={styles.now}>
            <CardHeader title="Speaking now" subtitle={current ? `${clock(current.start_ms)} – ${clock(current.end_ms)}` : 'Play to see who speaks; name them right here.'} />
            <NowSpeaking eventId={event.id} label={current?.label} speakers={byName} />
          </Card>

          <Card>
            <CardHeader title="Speakers" subtitle="Colours match the timeline" />
            <QueryView query={speakers} loading={<Skeleton lines={3} height={28} />}>
              {(list) => <SpeakerLegend eventId={event.id} speakers={list} player={player} turns={transcript.turns} />}
            </QueryView>
          </Card>

          <Card>
            <CardHeader title="Rate this transcript" />
            <RatingBlock eventId={event.id} variant={variant} />
          </Card>

          <Card>
            <CardHeader title="Flags" subtitle="Mistakes you marked, for the engine comparison" />
            <QueryView query={flags} loading={<Skeleton lines={2} />}>
              {(list) => <FlagList eventId={event.id} variant={variant} flags={list} onSeek={(ms) => { player.seek(ms); }} />}
            </QueryView>
          </Card>
        </aside>
      </div>

      {flagging ? (
        <FlagDialog eventId={event.id} variant={variant} paragraph={flagging} onClose={() => { setFlagging(null); }} />
      ) : null}
    </>
  );
}

interface NowSpeakingProps {
  readonly eventId: string;
  readonly label: string | undefined;
  readonly speakers: ReadonlyMap<string, Speaker>;
}

function NowSpeaking({ eventId, label, speakers }: NowSpeakingProps) {
  if (!label) return <p className={styles.muted}>Nobody — a pause, or the player is stopped.</p>;
  const speaker = speakers.get(label);
  const name = speakerName(label, speakers);
  return (
    <div className={styles.nowBody} style={{ '--voice': voiceColor(label) }}>
      <div className={styles.nowWho}>
        <span className={styles.nowDot} aria-hidden="true" />
        <span className={styles.nowLabel}>{label}</span>
        {name.kind === 'unclear' ? <Badge>unclear stretch</Badge> : null}
      </div>
      {speaker ? <SpeakerNaming eventId={eventId} speaker={speaker} compact /> : null}
    </div>
  );
}

interface LegendProps {
  readonly eventId: string;
  readonly speakers: readonly Speaker[];
  readonly player: Player;
  readonly turns: Transcript['turns'];
}

function SpeakerLegend({ eventId, speakers, player, turns }: LegendProps) {
  return (
    <ul className={styles.legend}>
      {speakers.map((s) => {
        const next = turns.find((t) => t.label === s.label && t.start_ms > player.now) ?? turns.find((t) => t.label === s.label);
        return (
          <li key={s.label} className={styles.legendItem} style={{ '--voice': voiceColor(s.label) }}>
            <div className={styles.legendHead}>
              <span className={styles.nowDot} aria-hidden="true" />
              <span className={styles.nowLabel}>{s.label}</span>
              <span className={styles.muted}>{talkTime(s.talk_s)}</span>
              {next ? (
                <IconButton
                  icon="play"
                  size="sm"
                  label={`Play ${s.label} from ${clock(next.start_ms)}`}
                  onClick={() => { player.seek(next.start_ms); }}
                />
              ) : null}
            </div>
            <SpeakerNaming eventId={eventId} speaker={s} compact />
          </li>
        );
      })}
    </ul>
  );
}

function RatingBlock({ eventId, variant }: { readonly eventId: string; readonly variant: string }) {
  const ratings = useQuery(ratingsQuery(eventId));
  return (
    <QueryView query={ratings} loading={<Skeleton lines={3} />}>
      {(list) => {
        const rating = list.find((r) => r.variant === variant);
        return <RatingPanel key={rating?.rated_at.toISOString() ?? 'none'} eventId={eventId} variant={variant} rating={rating} />;
      }}
    </QueryView>
  );
}

interface FlagListProps {
  readonly eventId: string;
  readonly variant: string;
  readonly flags: readonly Flag[];
  readonly onSeek: (ms: number) => void;
}

function FlagList({ eventId, variant, flags, onSeek }: FlagListProps) {
  const remove = useDeleteFlag(eventId, variant);
  if (flags.length === 0) {
    return <p className={styles.muted}>None yet. Hover a paragraph and press its flag to mark a mistake.</p>;
  }
  return (
    <ul className={styles.flagList}>
      {flags.map((f) => (
        <li key={f.id} className={styles.flagItem}>
          <button type="button" className={styles.flagTime} onClick={() => { onSeek(f.at_ms); }}>
            {clock(f.at_ms)}
          </button>
          <span className={styles.flagText}>
            <strong>{flagLabel(f.kind)}</strong>
            {f.note ? <span className={styles.muted}> — {f.note}</span> : null}
          </span>
          <IconButton
            icon="trash"
            size="sm"
            label="Remove flag"
            disabled={remove.isPending}
            onClick={() => { remove.mutate(f.id); }}
          />
        </li>
      ))}
    </ul>
  );
}
