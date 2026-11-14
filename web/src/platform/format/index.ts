/** 3 723 000 ms → "1:02:03"; 83 000 → "1:23". */
export function clock(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const ss = String(s).padStart(2, '0');
  return h > 0 ? `${h}:${String(m).padStart(2, '0')}:${ss}` : `${m}:${ss}`;
}

/** 1686.6 s → "28 min"; 32 s → "32 s". */
export function talkTime(seconds: number): string {
  return seconds >= 90 ? `${Math.round(seconds / 60)} min` : `${Math.round(seconds)} s`;
}

export function percent(share: number): string {
  return `${Math.round(share * 100)} %`;
}

export function similarity(value: number): string {
  return value.toFixed(2);
}

const dateFormat = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
const dateTimeFormat = new Intl.DateTimeFormat('en-GB', {
  day: 'numeric',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
});

export function date(value: Date): string {
  return dateFormat.format(value);
}

export function dateTime(value: Date): string {
  return dateTimeFormat.format(value);
}

/** "elevenlabs/scribe-v2" + "sk" → "elevenlabs · scribe-v2 · sk". */
export function engineName(engine: string, language: string | null): string {
  const slash = engine.indexOf('/');
  const parts = slash >= 0 ? [engine.slice(0, slash), engine.slice(slash + 1)] : [engine];
  return [...parts, language ?? ''].filter(Boolean).join(' · ');
}

/** 1 → "1 video", 3 → "3 videos". */
export function count(n: number, one: string, many = `${one}s`): string {
  return `${String(n)} ${n === 1 ? one : many}`;
}
