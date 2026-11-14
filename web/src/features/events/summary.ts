import type { Tone } from '@/platform/ui';
import type { EventSummary } from './api';

/**
 * How far a video's speakers are settled: named, or mixed (several known people at once, ADR-017). Green when
 * every speaker is one or the other.
 */
export function speakersDone(e: Pick<EventSummary, 'speakers' | 'named' | 'mixed'>): { text: string; tone: Tone } {
  const done = e.named + e.mixed;
  const tone: Tone = e.speakers > 0 && done === e.speakers ? 'ok' : done > 0 ? 'signal' : 'neutral';
  if (e.mixed === 0) return { text: `${String(e.named)}/${String(e.speakers)} speakers named`, tone };
  return { text: `${String(e.named)} named + ${String(e.mixed)} mixed of ${String(e.speakers)}`, tone };
}
