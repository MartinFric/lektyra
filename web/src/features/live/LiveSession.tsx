import { useQuery } from '@tanstack/react-query';
import { type RefObject, useRef, useState } from 'react';
import { type Speaker, speakersQuery } from '@/features/events/api';
import { SpeakerNaming } from '@/features/events/SpeakerNaming';
import { ClaimsPanel } from '@/features/claims/ClaimsPanel';
import { useClaims } from '@/features/claims/useClaims';
import { FaceOf } from '@/features/persons/PersonFace';
import { byLabel, speakerName } from '@/features/events/speakerName';
import { flagsQuery, type Paragraph, transcriptQuery } from '@/features/transcript/api';
import { FlagDialog } from '@/features/transcript/FlagDialog';
import { Paragraphs } from '@/features/transcript/Paragraphs';
import { clock, count, talkTime } from '@/platform/format';
import { Badge, Button, Card, CardHeader, EmptyState, Icon, Spinner, voiceColor } from '@/platform/ui';
import { type LiveSpeaker, type LiveState, type LiveTurn, mediaUrl, useStopLive } from './api';
import styles from './LivePage.module.css';

const TIMELINE_MS = 5 * 60_000;

/** A running session. Everything here is the server's state, polled; the only local state is the player's time. */
export function LiveSession({ state }: { readonly state: LiveState }) {
  const stop = useStopLive();
  const eventId = state.event_id;
  const speakers = useQuery({ ...speakersQuery(eventId ?? '-'), enabled: eventId !== null, refetchInterval: 3000 });
  const byName = byLabel(speakers.data ?? []);
  const video = useRef<HTMLVideoElement>(null);
  const [watching, setWatching] = useState<number | null>(null);
  const seek = (ms: number) => {
    if (video.current) video.current.currentTime = ms / 1000;
  };

  return (
    <div className={styles.session}>
      <Card className={styles.statusBar}>
        <StatusBadge state={state} />
        <div className={styles.statusText}>
          <strong className={styles.statusTitle}>{state.title ?? state.source}</strong>
          <span className={styles.muted}>{state.message}</span>
        </div>
        <dl className={styles.facts}>
          <div>
            <dt>heard</dt>
            <dd className="tabular">
              {clock(state.position_ms)}
              {state.duration_s ? <span className={styles.muted}> / {clock(state.duration_s * 1000)}</span> : null}
            </dd>
          </div>
          <div>
            <dt>pieces</dt>
            <dd className="tabular">
              {state.transcribe ? `${String(state.transcribed)}/${String(state.pieces)}` : state.pieces}
            </dd>
          </div>
          {state.transcribe ? (
            <div>
              <dt>claims</dt>
              <dd className="tabular" title={state.claims_error ?? `read up to minute ${String(state.claims_minutes)}`}>
                {state.claims}
                {state.claims_error ? <span className={styles.claimsError}> !</span> : null}
              </dd>
            </div>
          ) : null}
          <div>
            <dt>cost</dt>
            <dd className="tabular">${state.cost_usd.toFixed(3)}</dd>
          </div>
        </dl>
        <Button
          variant="danger"
          icon="x"
          disabled={state.status === 'stopping'}
          loading={stop.isPending}
          onClick={() => { stop.mutate(state.id); }}
        >
          Stop
        </Button>
      </Card>

      <div className={styles.liveGrid}>
        <div className={styles.left}>
          {state.media ? (
            <VideoPanel state={state} video={video} watching={watching} onTime={setWatching} />
          ) : (
            <Card>
              <EmptyState icon="voices" title="lektyra is listening to the stream">
                Watch it on TV or in Orange TV; lektyra shows who speaks and what was said here.
              </EmptyState>
            </Card>
          )}
          <Timeline turns={state.turns} position={state.position_ms} speakers={byName} />
        </div>
        <div className={styles.right}>
          <NowCard state={state} eventId={eventId} speakers={byName} />
          <HeardCard state={state} eventId={eventId} speakers={byName} />
        </div>
      </div>

      {eventId ? (
        <div className={styles.words}>
          <LiveTranscript state={state} eventId={eventId} speakers={byName} onSeek={state.media ? seek : null} />
          {state.transcribe ? <LiveClaims eventId={eventId} speakers={byName} onSeek={state.media ? seek : null} /> : null}
        </div>
      ) : null}
    </div>
  );
}

function StatusBadge({ state }: { readonly state: LiveState }) {
  if (state.status === 'loading') {
    return (
      <Badge>
        <Spinner size={11} /> starting
      </Badge>
    );
  }
  if (state.status === 'stopping') return <Badge tone="warn">stopping</Badge>;
  return (
    <Badge tone="error">
      <span className={styles.pulse} aria-hidden="true" /> live
    </Badge>
  );
}

interface VideoPanelProps {
  readonly state: LiveState;
  readonly video: RefObject<HTMLVideoElement | null>;
  readonly watching: number | null;
  readonly onTime: (ms: number) => void;
}

/** The downloaded video, playing where lektyra is. The player starts at lektyra's position; Sync puts it back. */
function VideoPanel({ state, video, watching, onTime }: VideoPanelProps) {
  if (state.status === 'loading') {
    return (
      <Card className={styles.videoWaiting}>
        <Spinner size={18} /> The video starts when lektyra starts listening.
      </Card>
    );
  }
  const drift = watching === null ? null : Math.round((watching - state.position_ms) / 1000);
  return (
    <Card padded={false} className={styles.videoCard}>
      <video
        ref={video}
        className={styles.video}
        src={mediaUrl(state.id)}
        controls
        autoPlay
        playsInline
        onLoadedMetadata={(e) => {
          e.currentTarget.currentTime = state.position_ms / 1000;
        }}
        onTimeUpdate={(e) => { onTime(e.currentTarget.currentTime * 1000); }}
      />
      <div className={styles.syncRow}>
        <span>
          lektyra hears <strong className="tabular">{clock(state.position_ms)}</strong>
        </span>
        <span>
          you watch <strong className="tabular">{watching === null ? '–' : clock(watching)}</strong>
          {drift !== null && Math.abs(drift) >= 3 ? (
            <Badge tone="warn">
              {drift > 0 ? '+' : ''}
              {drift} s
            </Badge>
          ) : null}
        </span>
        <Button
          size="sm"
          variant="ghost"
          icon="refresh"
          onClick={() => {
            if (video.current) video.current.currentTime = state.position_ms / 1000;
          }}
        >
          Sync to lektyra
        </Button>
      </div>
    </Card>
  );
}

interface CardProps {
  readonly state: LiveState;
  readonly eventId: string | null;
  readonly speakers: ReadonlyMap<string, Speaker>;
}

/** Who is speaking now: their name or voice number, and the naming actions right there. */
function NowCard({ state, eventId, speakers }: CardProps) {
  const label = state.current;
  const live = label ? state.speakers.find((s) => s.label === label) : undefined;
  const speaker = label ? speakers.get(label) : undefined;
  return (
    <Card className={styles.now}>
      <CardHeader title="Speaking now" />
      {!label ? (
        <p className={styles.muted}>Nobody right now: a pause, music, an ad, or a voice too short to tell.</p>
      ) : (
        <div className={styles.nowBody} style={{ '--voice': voiceColor(label) }}>
          <div className={styles.nowWho}>
            <span className={styles.nowDot} aria-hidden="true" />
            {speaker && speaker.person_id !== null ? <FaceOf personId={speaker.person_id} size="md" /> : null}
            <span className={styles.nowName}>{speaker ? speakerName(label, speakers).text : 'New voice'}</span>
            <span className={styles.mono}>{label}</span>
          </div>
          {speaker && eventId ? (
            <SpeakerNaming eventId={eventId} speaker={speaker} showName={false} />
          ) : (
            <p className={styles.muted}>
              {live?.listed
                ? `Listening… ${String(live.windows)} s of speech: giving it its voice number.`
                : `Listening… ${live ? `${String(live.windows)} s of speech so far; ` : ''}a voice gets its number after about 8 seconds.`}
            </p>
          )}
        </div>
      )}
    </Card>
  );
}

/** Everyone heard so far, most recent first. */
function HeardCard({ state, eventId, speakers }: CardProps) {
  const heard = [...state.speakers].filter((s) => s.listed).sort((a, b) => b.last_ms - a.last_ms);
  return (
    <Card>
      <CardHeader title="Heard so far" subtitle={count(heard.length, 'voice')} />
      {heard.length === 0 ? (
        <p className={styles.muted}>Nobody yet.</p>
      ) : (
        <ul className={styles.heard}>
          {heard.map((s) => (
            <HeardRow key={s.label} live={s} position={state.position_ms} eventId={eventId} speakers={speakers} />
          ))}
        </ul>
      )}
    </Card>
  );
}

interface HeardRowProps {
  readonly live: LiveSpeaker;
  readonly position: number;
  readonly eventId: string | null;
  readonly speakers: ReadonlyMap<string, Speaker>;
}

function HeardRow({ live, position, eventId, speakers }: HeardRowProps) {
  const speaker = speakers.get(live.label);
  return (
    <li className={styles.heardRow} style={{ '--voice': voiceColor(live.label) }}>
      <div className={styles.heardHead}>
        <span className={styles.nowDot} aria-hidden="true" />
        {speaker && speaker.person_id !== null ? <FaceOf personId={speaker.person_id} size="xs" /> : null}
        <strong className={styles.heardName}>{speaker ? speakerName(live.label, speakers).text : live.label}</strong>
        <span className={styles.muted}>
          {talkTime(live.talk_s)} · {position - live.last_ms < 3000 ? 'now' : `${clock(position - live.last_ms)} ago`}
        </span>
      </div>
      {speaker && eventId ? <SpeakerNaming eventId={eventId} speaker={speaker} compact showName={false} /> : null}
    </li>
  );
}

interface TimelineProps {
  readonly turns: readonly LiveTurn[];
  readonly position: number;
  readonly speakers: ReadonlyMap<string, Speaker>;
}

/** The last five minutes, coloured by who spoke; now is the right edge. */
function Timeline({ turns, position, speakers }: TimelineProps) {
  const from = Math.max(0, position - TIMELINE_MS);
  const span = Math.max(position - from, 1);
  const shown = turns.filter((t) => t.end_ms > from && t.label !== '?');
  return (
    <Card className={styles.timelineCard}>
      <div className={styles.timelineHead}>
        <span className={styles.muted}>last {clock(span)}</span>
        <span className={styles.muted}>now</span>
      </div>
      <div className={styles.timeline} role="img" aria-label="Who spoke in the last five minutes">
        {shown.map((t) => (
          <span
            key={`${String(t.start_ms)}-${t.label}`}
            className={styles.turn}
            title={`${speakerName(t.label, speakers).text} ${clock(t.start_ms)}–${clock(t.end_ms)}`}
            style={{
              left: `${String((Math.max(t.start_ms, from) - from) / span * 100)}%`,
              width: `${String(Math.max(0.4, (Math.min(t.end_ms, position) - Math.max(t.start_ms, from)) / span * 100))}%`,
              background: voiceColor(t.label),
            }}
          />
        ))}
      </div>
    </Card>
  );
}

interface TranscriptProps {
  readonly state: LiveState;
  readonly eventId: string;
  readonly speakers: ReadonlyMap<string, Speaker>;
  readonly onSeek: ((ms: number) => void) | null;
}

/** The words, piece by piece. The list sticks to its newest line by CSS (column-reverse), not by script. */
function LiveTranscript({ state, eventId, speakers, onSeek }: TranscriptProps) {
  const variant = state.variant;
  const [flagging, setFlagging] = useState<Paragraph | null>(null);
  const transcript = useQuery({
    ...transcriptQuery(eventId, variant ?? '-'),
    enabled: variant !== null,
    staleTime: 0,
    refetchInterval: 5000,
  });
  const flags = useQuery({ ...flagsQuery(eventId, variant ?? '-'), enabled: variant !== null });
  const paragraphs = transcript.data?.paragraphs ?? [];
  return (
    <Card padded={false} className={styles.transcript}>
      <div className={styles.transcriptHead}>
        <h2 className={styles.transcriptTitle}>Transcript</h2>
        <span className={styles.muted}>
          {state.transcribe
            ? 'Words arrive piece by piece, about every 30–40 seconds.'
            : 'Transcription is off for this session.'}
          {state.stt_errors > 0 ? ` ${count(state.stt_errors, 'piece')} failed.` : ''}
        </span>
      </div>
      {paragraphs.length === 0 ? (
        <div className={styles.transcriptEmpty}>
          <Icon name="doc" size={18} /> {variant ? 'Loading the words…' : 'No words yet: the first piece is still being heard.'}
        </div>
      ) : (
        <div className={styles.transcriptScroll}>
          <Paragraphs
            paragraphs={paragraphs}
            speakers={speakers}
            flags={flags.data ?? []}
            active={paragraphs.length - 1}
            follow={false}
            onSeek={(ms) => onSeek?.(ms)}
            onFlag={setFlagging}
          />
        </div>
      )}
      {flagging && variant ? (
        <FlagDialog eventId={eventId} variant={variant} paragraph={flagging} onClose={() => { setFlagging(null); }} />
      ) : null}
    </Card>
  );
}

interface LiveClaimsProps {
  readonly eventId: string;
  readonly speakers: ReadonlyMap<string, Speaker>;
  readonly onSeek: ((ms: number) => void) | null;
}

/** The session's claims as they come, newest on top (K29). */
function LiveClaims({ eventId, speakers, onSeek }: LiveClaimsProps) {
  const claims = useClaims(eventId, true);
  return <ClaimsPanel claims={claims} live speakers={speakers} onSeek={onSeek} />;
}
