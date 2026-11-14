import { describe, expect, it } from 'vitest';
import type { Claim } from './api';
import { claimsIn, countBy, currentClaim, DEFAULT_FILTER, filterClaims, toggle } from './filter';

function claim(id: string, at_ms: number, worth: number, speaker = 'S1', kind = 'number', status = 'open'): Claim {
  return {
    id, speaker, at_ms, quote: '', lekton: id, kind, entities: [], numbers: [], sources: [], worth, status, links: [],
  };
}

const claims = [
  claim('a', 10_000, 0.9, 'S1', 'money'),
  claim('b', 70_000, 0.6, 'S2', 'number'),
  claim('c', 130_000, 0.75, 'S2', 'law'),
  claim('d', 200_000, 0.95, 'S1', 'number', 'withdrawn'),
];

describe('filterClaims', () => {
  it('keeps the worth-checking open claims by default, in time order', () => {
    expect(filterClaims(claims, DEFAULT_FILTER).map((c) => c.id)).toEqual(['a', 'c']);
  });

  it('filters by speaker and kind, sorts by worth', () => {
    expect(filterClaims(claims, { ...DEFAULT_FILTER, minWorth: 0, speakers: ['S2'] }).map((c) => c.id)).toEqual(['b', 'c']);
    expect(filterClaims(claims, { ...DEFAULT_FILTER, minWorth: 0, kinds: ['money', 'law'] }).map((c) => c.id)).toEqual(['a', 'c']);
    expect(filterClaims(claims, { ...DEFAULT_FILTER, minWorth: 0, sort: 'worth' }).map((c) => c.id)).toEqual(['a', 'c', 'b']);
  });
});

describe('counts and places', () => {
  it('counts open claims above the threshold per speaker and kind', () => {
    expect(countBy(claims, 0, 'speaker')).toEqual([['S2', 2], ['S1', 1]]);
    expect(countBy(claims, 0.7, 'kind')).toEqual([['law', 1], ['money', 1]]);
  });

  it('finds the claims of a paragraph and the one being heard', () => {
    expect(claimsIn(claims, 60_000, 140_000).map((c) => c.id)).toEqual(['b', 'c']);
    expect(currentClaim(claims, 135_000)?.id).toBe('c');
    expect(currentClaim(claims, 5_000)).toBeNull();
    expect(currentClaim([claim('x', 0, 1)], 200_000)).toBeNull(); // said too long ago
  });

  it('toggles a chip', () => {
    expect(toggle(['S1'], 'S2')).toEqual(['S1', 'S2']);
    expect(toggle(['S1', 'S2'], 'S1')).toEqual(['S2']);
  });
});
