import { useQueryClient } from '@tanstack/react-query';
import { type ReactNode, useRef, useState } from 'react';
import { toast } from 'sonner';
import { AppError, apiUrl, seg } from '@/platform/api';
import { clock } from '@/platform/format';
import { notifyError } from '@/platform/query/queryClient';
import { Icon, Spinner } from '@/platform/ui';
import { type Clip, personClipsQuery, speakerClipsQuery } from './api';
import { ReelContext, useReel } from './reelContext';
import styles from './Reel.module.css';

const END_SLACK_MS = 250; // a media fragment stops a few ms short of its end

interface Playing {
  readonly key: string;
  readonly clips: readonly Clip[];
  readonly index: number;
}

/**
 * One reel at a time for the whole app: a hidden <audio> that plays clips one after another. Each clip is the
 * video's audio with a media fragment (`#t=start,end`), so the browser seeks and stops by itself; the next clip
 * starts when the current one reaches its end. Driven by event handlers only.
 */
export function ReelProvider({ children }: { readonly children: ReactNode }) {
  const [playing, setPlaying] = useState<Playing | null>(null);
  const [loading, setLoading] = useState<string | null>(null);
  const request = useRef(0); // the latest click wins when clips arrive late

  const stop = () => {
    request.current += 1;
    setLoading(null);
    setPlaying(null);
  };

  const play = (key: string, load: () => Promise<readonly Clip[]>) => {
    const mine = ++request.current;
    setPlaying(null);
    setLoading(key);
    load().then(
      (clips) => {
        if (mine !== request.current) return;
        setLoading(null);
        if (clips.length === 0) {
          toast.info('No clear passage of this voice yet', { description: 'It needs turns of at least a few seconds.' });
          return;
        }
        setPlaying({ key, clips, index: 0 });
      },
      (error: unknown) => {
        if (mine !== request.current) return;
        setLoading(null);
        notifyError(error);
      },
    );
  };

  /** Leave clip `from`. The browser reports a clip's end more than once (timeupdate, then the fragment's pause);
   * only the first report for the clip that is playing moves on, so no clip is skipped. */
  const leave = (from: number) => {
    setPlaying((p) => {
      if (p?.index !== from) return p;
      return p.index + 1 < p.clips.length ? { ...p, index: p.index + 1 } : null;
    });
  };

  const clip = playing?.clips[playing.index] ?? null;
  const at = playing?.index ?? 0;
  const value = {
    active: loading ?? playing?.key ?? null,
    loading: loading !== null,
    clip,
    index: playing?.index ?? 0,
    count: playing?.clips.length ?? 0,
    play,
    stop,
  };

  return (
    <ReelContext.Provider value={value}>
      {children}
      {clip ? (
        <audio
          key={`${clip.event_id}/${clip.label}/${String(clip.start_ms)}`}
          src={`${apiUrl(`/events/${seg(clip.event_id)}/audio`)}#t=${String(clip.start_ms / 1000)},${String(clip.end_ms / 1000)}`}
          autoPlay
          hidden
          onTimeUpdate={(e) => {
            if (e.currentTarget.currentTime * 1000 >= clip.end_ms - END_SLACK_MS) leave(at);
          }}
          onPause={(e) => {
            // the fragment's end pauses the element a few ms before `end_ms`; nothing else can pause it (hidden)
            if (e.currentTarget.currentTime * 1000 >= clip.end_ms - END_SLACK_MS) leave(at);
          }}
          onEnded={() => { leave(at); }}
          onError={() => {
            notifyError(new AppError('internal', 'This clip could not be played.'));
            leave(at);
          }}
        />
      ) : null}
    </ReelContext.Provider>
  );
}

type Source =
  | { readonly kind: 'person'; readonly personId: number }
  | { readonly kind: 'speaker'; readonly eventId: string; readonly label: string };

/** ▶ Hear this voice: plays its clearest passages; shows which clip of which video is playing. */
export function ReelButton({ source, showWhere = true }: { readonly source: Source; readonly showWhere?: boolean }) {
  const reel = useReel();
  const client = useQueryClient();
  const key = source.kind === 'person' ? `person:${String(source.personId)}` : `speaker:${source.eventId}/${source.label}`;
  const active = reel.active === key;
  const clip = active ? reel.clip : null;
  const label = active ? 'Stop' : 'Hear this voice';

  return (
    <span className={styles.reel}>
      <button
        type="button"
        className={`${styles.button} ${active ? styles.on : ''}`}
        aria-label={label}
        title={label}
        onClick={(e) => {
          e.stopPropagation();
          if (active) {
            reel.stop();
            return;
          }
          reel.play(key, () =>
            source.kind === 'person'
              ? client.query(personClipsQuery(source.personId))
              : client.query(speakerClipsQuery(source.eventId, source.label)),
          );
        }}
      >
        {active && reel.loading ? <Spinner size={13} /> : <Icon name={active ? 'pause' : 'play'} size={14} />}
      </button>
      {clip ? (
        <span className={styles.where} aria-live="polite">
          {reel.index + 1}/{reel.count}
          {showWhere ? (
            <span className={styles.title} title={clip.event_title}>
              {' '}
              · {clip.event_title}
            </span>
          ) : null}{' '}
          · {clip.label} {clock(clip.start_ms)}
        </span>
      ) : null}
    </span>
  );
}
