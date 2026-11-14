"""Live voices, one window at a time (ADR-013). Synthetic vectors only (ADR-005)."""

import numpy as np

from lektyra.domain.diarization import UNCLEAR
from lektyra.domain.live_voices import OnlineSpeakers, WindowPlanner

DIM = 32


def _voice(rng: np.random.Generator) -> np.ndarray:
    return rng.normal(0, 1, DIM)


def _window(voice: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    return (voice + rng.normal(0, 0.35, DIM)).astype(np.float32)


def test_two_voices_taking_turns_become_two_speakers_that_keep_their_labels() -> None:
    rng = np.random.default_rng(11)
    a, b = _voice(rng), _voice(rng)
    tracker = OnlineSpeakers()
    for voice in (a, a, a, a, a, a, b, b, b, b, b, b, a, a, a, b, b, b):
        tracker.add(_window(voice, rng))
    assert tracker.count == 2
    labels = tracker.labels
    assert set(labels[:6]) == {0}
    assert set(labels[6:12]) == {1}
    assert set(labels[12:15]) == {0}  # A came back: the same speaker, not a new one
    assert set(labels[15:]) == {1}


def test_a_new_voice_is_founded_only_after_it_has_been_heard_for_a_while() -> None:
    rng = np.random.default_rng(12)
    a, c = _voice(rng), _voice(rng)
    tracker = OnlineSpeakers(found=5)
    for _ in range(5):
        tracker.add(_window(a, rng))
    first = [tracker.add(_window(c, rng)) for _ in range(4)]
    assert first == [UNCLEAR] * 4  # four windows are not enough to be sure
    assert tracker.add(_window(c, rng)) == 1
    assert tracker.labels[5:10] == [1] * 5  # the waiting windows are given to the new speaker too


def test_noise_that_sounds_like_nobody_stays_unclear() -> None:
    rng = np.random.default_rng(13)
    a = _voice(rng)
    tracker = OnlineSpeakers()
    for _ in range(5):
        tracker.add(_window(a, rng))
    noise = [tracker.add(rng.normal(0, 1, DIM).astype(np.float32)) for _ in range(12)]
    assert set(noise) == {UNCLEAR}
    assert tracker.count == 1


def test_windows_are_due_every_second_but_only_when_someone_speaks() -> None:
    planner = WindowPlanner()
    speech = np.full(31, 0.9, dtype=np.float32)  # ~1 s of 32 ms frames
    silence = np.full(31, 0.1, dtype=np.float32)
    due = planner.feed(speech) + planner.feed(speech) + planner.feed(speech)  # ~3 s of speech, fed in pieces
    assert due == [(0, 2000)]  # the second window ends at 3000 ms, after 2976 ms heard: not due yet
    due = planner.feed(silence) + planner.feed(silence) + planner.feed(silence)
    assert due == [(1000, 3000)]  # 3 s of silence after: only the window still mostly speech is kept
