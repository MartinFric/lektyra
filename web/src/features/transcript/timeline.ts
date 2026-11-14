/** Lookups on time-ordered stretches, by binary search: called on every audio tick. Pure. */

interface Stretch {
  readonly start_ms: number;
  readonly end_ms: number;
}

/** Index of the last stretch that starts at or before `ms`, or -1 before the first. */
export function lastStartedAt(items: readonly Stretch[], ms: number): number {
  let lo = 0;
  let hi = items.length - 1;
  let found = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    const item = items[mid];
    if (item && item.start_ms <= ms) {
      found = mid;
      lo = mid + 1;
    } else {
      hi = mid - 1;
    }
  }
  return found;
}

/** The stretch playing at `ms`: the last started one if it has not ended yet. */
export function activeAt<T extends Stretch>(items: readonly T[], ms: number): T | undefined {
  const item = items[lastStartedAt(items, ms)];
  return item && ms < item.end_ms ? item : undefined;
}
