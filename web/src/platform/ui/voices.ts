/** Speakers wear fixed colours in label order (S1 first), the same in the list, the timeline and the transcript. */
const VOICES = 8;

export function voiceColor(label: string): string {
  const m = /^S(\d+)$/.exec(label);
  if (!m?.[1]) return 'var(--voice-unknown)';
  const n = Number(m[1]);
  return n >= 1 && n <= VOICES ? `var(--voice-${String(n)})` : 'var(--voice-unknown)';
}

/** A person's colour on the voice map: by their place in the sorted list, never cycled past eight. */
export function personColor(index: number): string {
  return index >= 0 && index < VOICES ? `var(--voice-${String(index + 1)})` : 'var(--voice-unknown)';
}
