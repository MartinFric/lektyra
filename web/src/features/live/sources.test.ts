import { describe, expect, it } from 'vitest';
import { linkProblem, runProblem, runTimes, sourceLabel, startsIn } from './sources';

describe('linkProblem', () => {
  it('takes public YouTube and Facebook addresses', () => {
    expect(linkProblem('https://www.youtube.com/watch?v=abc')).toBeNull();
    expect(linkProblem('https://youtu.be/abc')).toBeNull();
    expect(linkProblem(' https://www.facebook.com/somebody/videos/123 ')).toBeNull();
    expect(linkProblem('https://m.facebook.com/watch/live/?v=1')).toBeNull();
    expect(linkProblem('https://fb.watch/xyz/')).toBeNull();
  });

  it('refuses anything else', () => {
    expect(linkProblem('youtube.com/watch?v=abc')).toMatch(/https/);
    expect(linkProblem('http://www.youtube.com/watch?v=abc')).toMatch(/https/);
    expect(linkProblem('https://notyoutube.com/x')).toMatch(/Only YouTube and Facebook/);
  });
});

describe('sourceLabel', () => {
  const uploads = [{ id: 'u1', name: 'Hlina vs Takáč.mp4', size: 1, kind: 'video' as const, added_at: new Date() }];

  it('names channels, links, PC sound and uploads', () => {
    expect(sourceLabel('ta3:live')).toBe('TA3');
    expect(sourceLabel('stvr:1')).toBe('STVR Jednotka');
    expect(sourceLabel('pc:sound:Speakers')).toBe('PC sound');
    expect(sourceLabel('https://www.youtube.com/watch?v=a')).toBe('YouTube');
    expect(sourceLabel('https://fb.watch/a')).toBe('Facebook');
    expect(sourceLabel('upload:u1', uploads)).toBe('Hlina vs Takáč.mp4');
    expect(sourceLabel('upload:gone', uploads)).toBe('Uploaded video');
  });
});

describe('run times', () => {
  const now = new Date('2026-11-14T22:00:00');

  it('reads local inputs; an end before the start is the next day', () => {
    const t = runTimes('2026-11-15', '23:30', '00:30');
    expect(t?.starts.getHours()).toBe(23);
    expect(t?.ends.getDate()).toBe(16);
    expect(runTimes('', '11:00', '12:00')).toBeNull();
  });

  it('says what is wrong before asking the server', () => {
    expect(runProblem(runTimes('2026-11-15', '11:00', '12:00'), now)).toBeNull();
    expect(runProblem(runTimes('2026-11-14', '20:00', '21:00'), now)).toMatch(/over/);
    expect(runProblem(runTimes('2026-11-15', '08:00', '15:00'), now)).toMatch(/6 hours/);
    expect(runProblem(null, now)).toMatch(/Pick/);
  });
});

describe('startsIn', () => {
  const now = new Date('2026-11-14T23:27:00');

  it('says how soon, in words', () => {
    expect(startsIn(new Date('2026-11-15T10:58:00'), now)).toBe('in 11 h 31 min');
    expect(startsIn(new Date('2026-11-14T23:31:30'), now)).toBe('in 5 min');
    expect(startsIn(new Date('2026-11-14T23:00:00'), now)).toBe('now');
    expect(startsIn(new Date('2026-11-20T11:00:00'), now)).toBe('in 5 days'); // 5 days 11 h
  });
});
