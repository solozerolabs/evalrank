# Talking-avatar board

An open EvalRank board that ranks **audio-driven talking-avatar models**: a still of a stylised
character plus a recorded spoken line becomes a lip-synced vertical clip, the kind a small
business drops into a social reel. It is the only family of the `talking-avatar` cell
(`catalog/manifest.json`, family `evalrank-talking-avatar`).

No public leaderboard ranks these models (checked 2026-11-14): OpenArt Arena's lip-sync board
ranks five prompt-driven video models that make their own speech, with no audio-driven avatar
model and no feed; Artificial Analysis and LMArena have no lip-sync board; one-off blind tests
are not leaderboards. So EvalRank runs this board itself and publishes every row.

What breaks this use (found on the first run, 2026-11-14): burned-in pseudo-text captions, a
mouth that barely moves, a character redrawn in another style, and a refusal of a stylised still.

## Method

- **Clips** (8 per model): the stylised-clip board's 4 stills (felt puppet, gouache, clay,
  paper cut-out; sha256-pinned in `items.json`) x 2 recorded lines (`audio/`, one calm with two
  pauses, one exclaimed; sha256-pinned, with their measured speech spans).
- **Candidates:** discovered every run, with no hand list: every active fal image-to-video
  endpoint whose input schema takes one still and one audio file (`image_url` or
  `start_image_url`, and `audio_url` or `target_audio_url`, each a single URL).
  `python3 harness.py candidates` prints them.
- **Input:** shaped from the endpoint's own fal input schema the way a product sends it
  (`avatar_inputs`): the still and the line under the keys the schema names; the motion
  direction plus a fixed style-lock tail when it takes a prompt; `9:16` (or `auto`/`adaptive`)
  when it asks for a frame; the highest `<n>p` resolution up to 1080p; a duration rounded UP to
  cover the line; captions off.
- **Checks:** a clip passes only if all pass.
  - **delivered:** fal returned a video. A content-policy refusal or fal's "could not
    generate" fails the clip and its code is published; any other failure is an error.
  - **format:** a portrait frame, an audio track, and at least the line's length (`ffprobe`).
  - **line:** `fal-ai/whisper` hears the recorded line within 20% word error (the model kept
    our audio rather than dropping or replacing it).
  - **no text, identity:** the stylised-clip board's three-vendor panel questions over the
    still and the frames (majority).
  - **lips:** the same panel sees 4 frames per second, each labelled with its time and whether
    the line is being spoken then (from the line's measured speech spans), and judges whether
    the mouth moves with the speech (majority "synced").
- **Board metric:** `avatar_score`, the mean over judged clips of the panel's median
  performance rating / 5 for a passing clip and 0 for a failing one. It is a unit interval and
  higher is better; `pass_rate` (passed / judged clips) is published beside it, so a consumer
  can require at most one failure in 8.
- **Errors:** a clip that could not be judged is an error, not a fail. A row with more than one
  error is published with `excluded: true`, never ranked, and retried next run (3 runs in all).
- **Price:** each row's `billing` says what fal billed `key_id` (the board's own key, which
  runs nothing else) on the endpoint between `started_at` and `finished_at`, over
  `video_seconds` of delivered clips. Listed unit prices are not per second of output.
- **Identity:** `results.json` records the item-set digest, the prompt sha256 (direction, tail,
  judge prompt, schema, frame rate), the transcriber, word-error ceiling and panel. A change to
  any of them, or to `HARNESS_VERSION` (which includes the stylised-clip harness version whose
  fal, whisper and panel plumbing this board loads), starts a new board.

## Check validation

CALIBRATION

## Refresh

`.github/workflows/talking-avatar-board.yml` runs weekly. With no arena to rank a new endpoint
first, a scheduled run scores only endpoints fal added since the last run (and retries an
excluded row), at most 2, refuses rather than rescoring every model when the prompt, items or
panel changed, and re-measures one passer's price (best first, when its bill is missing or over
28 days old; well under $1). A quiet week costs $0; a manual run has no cap. It needs the
repository secrets `FAL_API_KEY` (the board's own key) and `OPENROUTER_API_KEY`; a scheduled
run without them fails, so a stale board is never silent.

```sh
FAL_API_KEY=... OPENROUTER_API_KEY=... python3 harness.py run --results results.json
```

## Rights

The scores, lines and stills are EvalRank's own data, published under this repository's
Apache-2.0 license. Clips are not published.
