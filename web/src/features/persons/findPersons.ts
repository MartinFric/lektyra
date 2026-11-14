import type { Person } from './api';

/** Lower case without diacritics: "Šumichrast" is found by typing "sumi". */
export function plain(text: string): string {
  return text.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase();
}

type Findable = Pick<Person, 'name' | 'function' | 'party'>;

/**
 * Persons whose name, function or party hold every word typed, in any order and without diacritics. Names that start
 * with what was typed come first, then the rest by name.
 */
export function findPersons<P extends Findable>(persons: readonly P[], text: string): P[] {
  const words = plain(text).split(/\s+/).filter(Boolean);
  const first = words[0] ?? '';
  const hay = (p: P) => plain([p.name, p.function ?? '', p.party ?? ''].join(' '));
  const startsWith = (p: P) => plain(p.name).split(/\s+/).some((w) => w.startsWith(first));
  return persons
    .filter((p) => words.every((w) => hay(p).includes(w)))
    .sort((a, b) => Number(startsWith(b)) - Number(startsWith(a)) || a.name.localeCompare(b.name, 'sk'));
}
