import { type RefObject, type SyntheticEvent, useRef, useState } from 'react';
import { notifyError } from '@/platform/query/queryClient';
import { AppError } from '@/platform/api';

export interface Player {
  readonly now: number; // ms
  readonly duration: number; // ms
  readonly playing: boolean;
  readonly rate: number;
  readonly broken: string | null;
  readonly seek: (ms: number, play?: boolean) => void;
  readonly toggle: () => void;
  readonly skip: (deltaMs: number) => void;
  readonly setRate: (rate: number) => void;
  readonly audioProps: {
    readonly ref: RefObject<HTMLAudioElement | null>;
    readonly preload: 'metadata';
    readonly onTimeUpdate: (e: SyntheticEvent<HTMLAudioElement>) => void;
    readonly onLoadedMetadata: (e: SyntheticEvent<HTMLAudioElement>) => void;
    readonly onPlay: () => void;
    readonly onPause: () => void;
    readonly onError: (e: SyntheticEvent<HTMLAudioElement>) => void;
  };
}

const MEDIA_ERRORS: Record<number, string> = {
  1: 'Loading the audio was stopped.',
  2: 'The audio could not be downloaded from the server.',
  3: 'The browser could not decode the audio.',
  4: 'The audio file is missing or its format is not supported.',
};

/**
 * One <audio> element and its state, driven only by the element's own events (no effect, no timer). The caller
 * spreads `audioProps` on the element; everything else is plain state and handlers.
 */
export function usePlayer(knownDurationMs: number): Player {
  const ref = useRef<HTMLAudioElement>(null);
  const [now, setNow] = useState(0);
  const [duration, setDuration] = useState(knownDurationMs);
  const [playing, setPlaying] = useState(false);
  const [rate, setRateState] = useState(1);
  const [broken, setBroken] = useState<string | null>(null);

  const play = (audio: HTMLAudioElement) => {
    audio.play().catch((error: unknown) => {
      if (error instanceof DOMException && error.name === 'AbortError') return;
      notifyError(new AppError('internal', 'The browser refused to play the audio. Click play again.'));
    });
  };

  const seek = (ms: number, andPlay = true) => {
    const audio = ref.current;
    if (!audio) return;
    const clamped = Math.max(0, Math.min(ms, duration || ms));
    audio.currentTime = clamped / 1000;
    setNow(clamped);
    if (andPlay) play(audio);
  };

  return {
    now,
    duration,
    playing,
    rate,
    broken,
    seek,
    toggle: () => {
      const audio = ref.current;
      if (!audio) return;
      if (audio.paused) play(audio);
      else audio.pause();
    },
    skip: (deltaMs) => {
      seek(now + deltaMs, !(ref.current?.paused ?? true));
    },
    setRate: (value) => {
      if (ref.current) ref.current.playbackRate = value;
      setRateState(value);
    },
    audioProps: {
      ref,
      preload: 'metadata',
      onTimeUpdate: (e) => {
        setNow(e.currentTarget.currentTime * 1000);
      },
      onLoadedMetadata: (e) => {
        const seconds = e.currentTarget.duration;
        if (Number.isFinite(seconds) && seconds > 0) setDuration(seconds * 1000);
        e.currentTarget.playbackRate = rate;
      },
      onPlay: () => {
        setPlaying(true);
      },
      onPause: () => {
        setPlaying(false);
      },
      onError: (e) => {
        const code = e.currentTarget.error?.code ?? 0;
        const message = MEDIA_ERRORS[code] ?? 'The audio could not be played.';
        setBroken(message);
        notifyError(new AppError('internal', message));
      },
    },
  };
}
