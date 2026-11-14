import { describe, expect, it } from 'vitest';
import { activeAt, lastStartedAt } from './timeline';

const turns = [
  { start_ms: 0, end_ms: 1_000, label: 'S1' },
  { start_ms: 1_500, end_ms: 4_000, label: 'S2' },
  { start_ms: 4_000, end_ms: 9_000, label: 'S1' },
];

describe('timeline', () => {
  it('finds the last stretch started', () => {
    expect(lastStartedAt(turns, -1)).toBe(-1);
    expect(lastStartedAt(turns, 0)).toBe(0);
    expect(lastStartedAt(turns, 1_200)).toBe(0);
    expect(lastStartedAt(turns, 4_000)).toBe(2);
    expect(lastStartedAt(turns, 99_000)).toBe(2);
    expect(lastStartedAt([], 5)).toBe(-1);
  });

  it('says who speaks now, and nobody in a pause', () => {
    expect(activeAt(turns, 500)?.label).toBe('S1');
    expect(activeAt(turns, 1_200)).toBeUndefined();
    expect(activeAt(turns, 2_000)?.label).toBe('S2');
    expect(activeAt(turns, 9_500)).toBeUndefined();
  });
});
