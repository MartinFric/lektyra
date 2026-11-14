import { describe, expect, it } from 'vitest';
import { clock, engineName, talkTime } from './index';

describe('format', () => {
  it('prints clock times', () => {
    expect(clock(83_000)).toBe('1:23');
    expect(clock(3_723_000)).toBe('1:02:03');
    expect(clock(-5)).toBe('0:00');
  });

  it('prints talk time', () => {
    expect(talkTime(32)).toBe('32 s');
    expect(talkTime(1686.6)).toBe('28 min');
  });

  it('names an engine', () => {
    expect(engineName('elevenlabs/scribe-v2', 'sk')).toBe('elevenlabs · scribe-v2 · sk');
    expect(engineName('whisper', null)).toBe('whisper');
  });
});
