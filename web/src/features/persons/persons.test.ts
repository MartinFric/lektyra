import { describe, expect, it } from 'vitest';
import { findPersons, plain, similarPersons } from './findPersons';
import { photoCredit, photoProblem } from './photos';

const people = [
  { name: 'Jozef Šumichrast', function: 'predseda SPPK', party: null },
  { name: 'Emil Macho', function: 'podpredseda SPPK', party: null },
  { name: 'Robert Fico', function: 'premiér', party: 'Smer' },
  { name: 'Richard Takáč', function: 'minister pôdohospodárstva', party: 'Smer' },
];

describe('findPersons', () => {
  it('finds names without diacritics', () => {
    expect(plain('Šumichrast Takáč')).toBe('sumichrast takac');
    expect(findPersons(people, 'sumi').map((p) => p.name)).toEqual(['Jozef Šumichrast']);
    expect(findPersons(people, 'takac').map((p) => p.name)).toEqual(['Richard Takáč']);
  });

  it('needs every word, in any order, in the name, function or party', () => {
    expect(findPersons(people, 'smer fico').map((p) => p.name)).toEqual(['Robert Fico']);
    expect(findPersons(people, 'sppk').map((p) => p.name)).toEqual(['Emil Macho', 'Jozef Šumichrast']);
  });

  it('puts names that start with the text first', () => {
    // every one holds an "r"; only Richard and Robert start a name with it
    expect(findPersons(people, 'r').map((p) => p.name)).toEqual([
      'Richard Takáč',
      'Robert Fico',
      'Emil Macho',
      'Jozef Šumichrast',
    ]);
  });

  it('lists everyone, by name, when nothing is typed', () => {
    expect(findPersons(people, '  ').map((p) => p.name)).toEqual([
      'Emil Macho',
      'Jozef Šumichrast',
      'Richard Takáč',
      'Robert Fico',
    ]);
  });
});

describe('photos', () => {
  it('refuses what is not a picture or too large, before sending it', () => {
    expect(photoProblem({ type: 'image/png', size: 1000 })).toBeNull();
    expect(photoProblem({ type: 'application/pdf', size: 1000 })).toMatch(/JPEG, PNG/);
    expect(photoProblem({ type: 'image/jpeg', size: 16_000_000 })).toMatch(/15 MB/);
  });

  it('credits Wikimedia Commons with licence and author', () => {
    expect(
      photoCredit({
        version: 'v',
        source_url: 'https://commons.wikimedia.org/wiki/File:X.jpg',
        license: 'CC BY-SA 4.0',
        author: 'Jana',
      }),
    ).toEqual({
      source: 'Wikimedia Commons',
      href: 'https://commons.wikimedia.org/wiki/File:X.jpg',
      terms: 'CC BY-SA 4.0 · by Jana',
    });
  });

  it('says when the licence is unknown, and what an upload is', () => {
    expect(photoCredit({ version: 'v', source_url: 'https://www.nrsr.sk/x.jpg', license: null, author: null })).toEqual({
      source: 'nrsr.sk',
      href: 'https://www.nrsr.sk/x.jpg',
      terms: 'licence unknown, local use only',
    });
    expect(photoCredit({ version: 'v', source_url: null, license: null, author: null }).source).toBe('Uploaded by you');
  });
});

describe('similarPersons', () => {
  const list = [
    { name: 'Michal Šimečka' },
    { name: 'Matúš Šutaj Eštok' },
    { name: 'Braňo Kráľ' },
    { name: 'Robert Fico' },
    { name: 'Tomáš Drucker' },
    { name: 'Marek Gudiak' },
  ];
  const names = (text: string) => similarPersons(list, text).map((p) => p.name);

  it('finds a person in any word order, without diacritics, by short form', () => {
    expect(names('simecka miso')[0]).toBe('Michal Šimečka');
    expect(names('Michal Simecka')[0]).toBe('Michal Šimečka');
    expect(names('branislav kral')[0]).toBe('Braňo Kráľ');
    expect(names('sutaj estok')[0]).toBe('Matúš Šutaj Eštok');
  });

  it('forgives a typo and an unfinished word', () => {
    expect(names('simeckaa')[0]).toBe('Michal Šimečka');
    expect(names('druck')[0]).toBe('Tomáš Drucker');
    expect(names('gudyak')[0]).toBe('Marek Gudiak');
  });

  it('stays quiet when nobody is near', () => {
    expect(names('Jozef Novák')).toEqual([]);
    expect(names('a')).toEqual([]);
  });
});
