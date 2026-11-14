import type { Claim } from './api';

/** What the claims panel shows. Worth first: two claims a minute is too many to read, the worth-checking ones are not. */
export interface ClaimFilter {
  readonly minWorth: number;
  /** Speaker labels to keep (S1…); empty keeps everyone. */
  readonly speakers: readonly string[];
  /** Claim kinds to keep; empty keeps every kind. */
  readonly kinds: readonly string[];
  readonly sort: 'time' | 'worth';
}

export const DEFAULT_FILTER: ClaimFilter = { minWorth: 0.7, speakers: [], kinds: [], sort: 'time' };

export const WORTH_STEPS: readonly { readonly value: number; readonly label: string }[] = [
  { value: 0, label: 'All claims' },
  { value: 0.5, label: 'Worth ≥ 50 %' },
  { value: 0.7, label: 'Worth checking (≥ 70 %)' },
  { value: 0.85, label: 'Most worth (≥ 85 %)' },
];

/** Open claims that pass the filter, by time or by worth (ties by time). */
export function filterClaims(claims: readonly Claim[], f: ClaimFilter): Claim[] {
  const kept = claims.filter(
    (c) =>
      c.status === 'open' &&
      c.worth >= f.minWorth &&
      (f.speakers.length === 0 || f.speakers.includes(c.speaker)) &&
      (f.kinds.length === 0 || f.kinds.includes(c.kind)),
  );
  return kept.sort((a, b) => (f.sort === 'worth' ? b.worth - a.worth : 0) || a.at_ms - b.at_ms);
}

/** How many open claims at or above the worth threshold each speaker (or kind) has, most first. */
export function countBy(claims: readonly Claim[], minWorth: number, key: 'speaker' | 'kind'): [string, number][] {
  const counts = new Map<string, number>();
  for (const c of claims) {
    if (c.status === 'open' && c.worth >= minWorth) counts.set(c[key], (counts.get(c[key]) ?? 0) + 1);
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}

/** Claims said in [startMs, endMs): the ones a transcript paragraph holds. */
export function claimsIn(claims: readonly Claim[], startMs: number, endMs: number): Claim[] {
  return claims.filter((c) => c.at_ms >= startMs && c.at_ms < endMs);
}

/** The claim being heard: the last one said at or before `now`, if it was said in the last two minutes. */
export function currentClaim(claims: readonly Claim[], now: number): Claim | null {
  let best: Claim | null = null;
  for (const c of claims) if (c.at_ms <= now && (best === null || c.at_ms >= best.at_ms)) best = c;
  return best !== null && now - best.at_ms <= 120_000 ? best : null;
}

/** Toggle a value in a list (a filter chip). */
export function toggle(list: readonly string[], value: string): string[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}
