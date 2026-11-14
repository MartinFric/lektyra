import { describe, expect, it } from 'vitest';
import type { Speaker } from './api';
import { byLabel, speakerName } from './speakerName';

function speaker(over: Partial<Speaker>): Speaker {
  return {
    label: 'S1', talk_s: 10, share: 0.5, person_id: null, person_name: null, person_number: null,
    person_anonymous: null, status: 'unknown', score: null, candidates: [], rejected: [], no_profile: false, overlap: [],
    ...over,
  };
}

describe('speakerName', () => {
  it('shows a mixed speaker as everyone in it', () => {
    const s = speaker({
      status: 'overlap',
      overlap: [
        { person_id: 1, name: 'Robert Fico' },
        { person_id: 21, name: 'Braňo Kráľ' },
      ],
    });
    expect(speakerName('S1', byLabel([s]))).toEqual({ text: 'Robert Fico + Braňo Kráľ', kind: 'mixed' });
  });

  it('shows a named speaker, a voice founded here and named since, and a bare label', () => {
    const named = speaker({ label: 'S2', status: 'confirmed', person_id: 1, person_name: 'Robert Fico', person_anonymous: false });
    const founded = speaker({ label: 'S3', status: 'new', person_id: 7, person_name: 'Zuzana Števulová', person_anonymous: false });
    const map = byLabel([named, founded, speaker({ label: 'S4' })]);
    expect(speakerName('S2', map).kind).toBe('named');
    expect(speakerName('S3', map)).toEqual({ text: 'Zuzana Števulová', kind: 'named' });
    expect(speakerName('S4', map)).toEqual({ text: 'S4', kind: 'label' });
  });
});
