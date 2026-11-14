import type { Speaker } from './api';

export interface SpeakerName {
  readonly text: string;
  /**
   * named: Martin said who it is · auto: matched to a named person, not confirmed · voice: a numbered voice nobody
   * has named yet · maybe: a weak match · label: no voice yet (S2) · unclear: a stretch nobody could be given ·
   * mixed: several known people at once (crosstalk), "Fico + Kráľ".
   */
  readonly kind: 'named' | 'auto' | 'voice' | 'maybe' | 'label' | 'unclear' | 'mixed';
}

/** What a transcript shows for a label: a confirmed name, a marked guess, a voice number, or the bare label. */
export function speakerName(label: string, speakers: ReadonlyMap<string, Speaker>): SpeakerName {
  if (label === '?') return { text: 'unclear', kind: 'unclear' };
  const s = speakers.get(label);
  if (s?.status === 'overlap' && s.overlap.length > 0) {
    return { text: s.overlap.map((o) => o.name).join(' + '), kind: 'mixed' };
  }
  if (!s?.person_name) return { text: label, kind: 'label' };
  if (s.person_anonymous) return { text: s.person_name, kind: 'voice' };
  // 'new' with a name: the voice was first heard here and named since (in the person form)
  if (s.status === 'confirmed' || s.status === 'new') return { text: s.person_name, kind: 'named' };
  if (s.status === 'auto') return { text: s.person_name, kind: 'auto' };
  if (s.status === 'suggested') return { text: `${label} · ${s.person_name}?`, kind: 'maybe' };
  return { text: label, kind: 'label' };
}

export function byLabel(speakers: readonly Speaker[]): ReadonlyMap<string, Speaker> {
  return new Map(speakers.map((s) => [s.label, s]));
}
