import type { Upload } from './api';

/** The live channels lektyra opens itself (ADR-013): their own players, no login. */
export const CHANNELS = [
  { source: 'ta3:live', name: 'TA3', hint: 'news channel: V politike on Sundays at 11:00' },
  { source: 'stvr:1', name: 'STVR Jednotka', hint: 'O 5 minút 12 on Sundays at 11:55' },
  { source: 'stvr:2', name: 'STVR Dvojka', hint: 'the second public channel' },
] as const;

const LINK_HOSTS = ['youtube.com', 'youtu.be', 'facebook.com', 'fb.watch'];

function host(address: string): string | null {
  try {
    const url = new URL(address);
    return url.protocol === 'https:' ? url.hostname.replace(/^(www|m|web)\./, '') : null;
  } catch {
    return null;
  }
}

/** Why a link cannot be listened to; null when it can. Public YouTube and Facebook videos and lives only. */
export function linkProblem(address: string): string | null {
  const name = host(address.trim());
  if (name === null) return 'Paste a full https:// address of a YouTube or Facebook video or live.';
  if (!LINK_HOSTS.some((h) => name === h || name.endsWith(`.${h}`))) return 'Only YouTube and Facebook addresses.';
  return null;
}

/** How a source reads in lists: "TA3", "YouTube", "PC sound", or the uploaded file's name. */
export function sourceLabel(source: string, uploads: readonly Upload[] = []): string {
  const channel = CHANNELS.find((c) => c.source === source);
  if (channel) return channel.name;
  if (source.startsWith('pc:sound')) return 'PC sound';
  if (source.startsWith('upload:')) {
    const id = source.slice('upload:'.length);
    return uploads.find((u) => u.id === id)?.name ?? 'Uploaded video';
  }
  const name = host(source);
  if (name?.includes('youtu')) return 'YouTube';
  if (name?.includes('facebook') || name === 'fb.watch') return 'Facebook';
  return source;
}

/** Local date and time inputs (YYYY-MM-DD, HH:MM) to an instant. An end before the start is on the next day. */
export function runTimes(day: string, start: string, end: string): { starts: Date; ends: Date } | null {
  const starts = new Date(`${day}T${start}`);
  let ends = new Date(`${day}T${end}`);
  if (Number.isNaN(starts.getTime()) || Number.isNaN(ends.getTime())) return null;
  if (ends <= starts) ends = new Date(ends.getTime() + 24 * 3600_000);
  return { starts, ends };
}

/** Why a run cannot be scheduled for these times; null when it can. The server checks again. */
export function runProblem(times: { starts: Date; ends: Date } | null, now: Date): string | null {
  if (times === null) return 'Pick a day, a start and an end.';
  if (times.ends <= now) return 'This time is over already.';
  if (times.ends.getTime() - times.starts.getTime() > 6 * 3600_000) return 'A run is at most 6 hours long.';
  return null;
}

/** "2026-11-15" for a date input, in local time. */
export function dayInput(value: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${String(value.getFullYear())}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
}

/** "Ne 15. 11. 11:00–12:00": a run's time, short. */
export function runWhen(starts: Date, ends: Date): string {
  const day = starts.toLocaleDateString('sk-SK', { weekday: 'short', day: 'numeric', month: 'numeric' });
  const time = (d: Date) => d.toLocaleTimeString('sk-SK', { hour: '2-digit', minute: '2-digit' });
  return `${day} ${time(starts)}–${time(ends)}`;
}
