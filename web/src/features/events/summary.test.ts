import { describe, expect, it } from 'vitest';
import { speakersDone } from './summary';

describe('speakersDone', () => {
  it('counts mixed speakers as settled', () => {
    expect(speakersDone({ speakers: 6, named: 5, mixed: 1 })).toEqual({ text: '5 named + 1 mixed of 6', tone: 'ok' });
    expect(speakersDone({ speakers: 5, named: 3, mixed: 1 })).toEqual({ text: '3 named + 1 mixed of 5', tone: 'signal' });
  });

  it('reads as before without mixed speakers', () => {
    expect(speakersDone({ speakers: 3, named: 3, mixed: 0 })).toEqual({ text: '3/3 speakers named', tone: 'ok' });
    expect(speakersDone({ speakers: 2, named: 0, mixed: 0 }).tone).toBe('neutral');
  });
});
