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

/** Slovak short forms and the names they stand for, both ways: "Mišo" is Michal, "Braňo" is Branislav. */
const SHORT: Readonly<Record<string, string>> = {
  miso: 'michal', brano: 'branislav', jano: 'jan', jozo: 'jozef', palo: 'pavol', peto: 'peter', mato: 'matus',
  robo: 'robert', tomo: 'tomas', riso: 'richard', fero: 'frantisek', duro: 'juraj', duri: 'juraj', tono: 'anton',
  miro: 'miroslav', stevo: 'stefan', majo: 'marian', laco: 'ladislav', vlado: 'vladimir', igor: 'igor',
  zuzka: 'zuzana', katka: 'katarina', majka: 'maria', janka: 'jana', evka: 'eva', danka: 'dana', lucka: 'lucia',
};

function canon(word: string): string {
  return SHORT[word] ?? word;
}

/** How alike two words are, 0..1 (1 − edit distance / longer length). */
function alike(a: string, b: string): number {
  if (a === b) return 1;
  const row = Array.from({ length: b.length + 1 }, (_, j) => j);
  for (let i = 1; i <= a.length; i++) {
    let diagonal = row[0] ?? 0;
    row[0] = i;
    for (let j = 1; j <= b.length; j++) {
      const above = row[j] ?? 0;
      row[j] = Math.min(above + 1, (row[j - 1] ?? 0) + 1, diagonal + (a[i - 1] === b[j - 1] ? 0 : 1));
      diagonal = above;
    }
  }
  return 1 - (row[b.length] ?? 0) / Math.max(a.length, b.length);
}

function wordScore(typed: string, word: string): number {
  const t = canon(typed);
  const w = canon(word);
  if (t === w) return 1;
  if (t.length >= 3 && (w.startsWith(t) || t.startsWith(w))) return 0.9;
  const near = alike(t, w);
  return near >= 0.7 ? near : 0;
}

/**
 * Persons whose name sounds like what was typed ("Did you mean Michal Šimečka?"): any word order, no diacritics,
 * short forms (Mišo, Braňo), a typo or an unfinished word. Best first, at most `limit`.
 */
export function similarPersons<P extends Pick<Person, 'name'>>(persons: readonly P[], text: string, limit = 5): P[] {
  const typed = plain(text).split(/\s+/).filter((w) => w.length >= 2);
  if (typed.length === 0) return [];
  const scored = persons.map((p) => {
    const words = plain(p.name).split(/\s+/).filter(Boolean);
    const total = typed.reduce((sum, t) => sum + Math.max(0, ...words.map((w) => wordScore(t, w))), 0);
    return { p, score: total / typed.length };
  });
  return scored
    .filter((s) => s.score >= 0.6)
    .sort((a, b) => b.score - a.score || a.p.name.localeCompare(b.p.name, 'sk'))
    .slice(0, limit)
    .map((s) => s.p);
}
