# ADR-007: One ingest path: a stored video is a stream that runs faster

*Status: accepted · 2026-11-14 · Martin ("just url to livestream or stored video")*

## Context

The input is a URL: a live stream (HLS/DASH, a TV site, YouTube live), a page with a stored video, a direct media
URL, or a local file. Two code paths (live and batch) would drift apart, and the live one would be tested less.

## Decision

- Every source becomes the same thing: **16 kHz mono 16-bit PCM read from ffmpeg's stdout**, in order, frame by
  frame.
- `yt-dlp` resolves pages to media URLs and says whether a source is live. ffmpeg decodes anything it can open
  (HLS, DASH, RTMP, files).
- A stored video is read as fast as ffmpeg can decode it. `--realtime` (ffmpeg `-re`) replays it at live speed, to
  rehearse the live path.
- The chunker, cutting, transcription and the claims loop see only the stream. They cannot tell live from
  recorded. So **replay = live**, and every recorded video is a test of the live path.
- The full audio is also written to `data/events/<event>/audio.flac` as it streams, for evaluation and re-cutting.

## Consequences

Sources that need a login, DRM or a browser session cannot be opened by ffmpeg/yt-dlp. Those get a separate
`MediaSource` adapter later (e.g. capture from a browser), still producing the same PCM stream.

## Enforced by

`ports.MediaSource` has one method returning PCM frames; review; the replay test in `tests/`.
