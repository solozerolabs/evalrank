# Stylised-clip board

An open EvalRank board that ranks **image-to-video models animating a stylised character that
speaks one line**: the short vertical clip a small business drops into a social reel. It feeds
the `video-generation` cell's model-configuration group (`catalog/manifest.json`, family
`evalrank-stylised-clip`), beside LMArena's text-to-video and image-to-video arenas.

The arenas rank general video quality from human votes. They do not catch what breaks this use
(found in bake-offs on 2026-11-14):

- burned-in captions, often misspelled, even when the prompt says "no captions";
- the character changing: an added scarf, new hair, a paper cut-out turned into a realistic
  person;
- a moderation refusal of a clearly stylised puppet as a "likeness of real people";
- a silent clip.

So EvalRank runs this board itself and publishes every row.

## Method

- **Clips** (8 per model): 4 stylised stills (felt puppet, gouache, clay, paper cut-out;
  `stills/`, EvalRank's own images, sha256-pinned in `items.json`) x 2 lines, one calm and one
  exclaimed. Each clip is 5 s, vertical, audio on.
- **Input:** shaped from the endpoint's own fal input schema the way a product sends it:
  - the still under `image_url` or `start_image_url`;
  - aspect `9:16` (or `auto`/`adaptive`, since the still is vertical);
  - the highest resolution offered up to 1080p;
  - a duration rounded UP to an allowed length;
  - every audio flag on.

  The prompt is the motion direction, `They say: "<line>"`, and a fixed tail that keeps the
  style and forbids captions.
- **Checks:** a clip passes only if all five pass.
  - **delivered:** fal returned a video. A content-policy refusal or fal's "could not generate"
    fails the clip, and the refusal code is published. Any other failure (a key, a balance, a
    timeout, a request our own shaping got wrong) is an error, never the model's fail.
  - **format:** a portrait frame, an audio track, and at least 4.5 s (`ffprobe`).
  - **line:** `fal-ai/whisper` transcribes the speech within 20% word error of the line.
  - **no text:** a three-vendor vision panel (`anthropic/claude-sonnet-5.5`,
    `google/gemini-3.8-flash`, `openai/gpt-6.1-terra-pro`, low effort) sees the still and one
    frame per second. Text that is not in the still fails the clip on a majority vote.
  - **identity:** the same panel judges whether clothing, accessories, hair, art style or
    realism changed (majority). An animated expression does not count: a mouth opening,
    eyebrows or teeth for an expression, or a gesture.
- **Board metric:** the pass rate over the 8 clips. It is a unit interval and higher is
  better. Each row also publishes per-check pass counts, refusal codes, time to video, fal's
  list price and every clip's result and transcript.
- **Errors:** a clip that could not be judged (transport failure, or fewer than two judges
  answered) is an error, not a fail. A row with more than one error is published with
  `excluded: true`, never ranked, and retried next run.
- **Candidates:** `candidates.json`, a reviewed map from LMArena arena names to the fal
  endpoint that serves each model. The board's entity name is the arena name, so a row joins
  the arena families as one model. `python3 harness.py candidates` prints the map with each
  endpoint's fal status.
- **Identity:** `results.json` records:
  - the item-set digest (stills, lines and length);
  - the prompt sha256 (prompt tail, judge prompt and schema);
  - the transcriber, the word-error ceiling and the panel.

  A change to any of them, or to `HARNESS_VERSION`, starts a new board.

## Check validation

`python3 harness.py calibrate --sample <jsonl>` runs the post-generation checks on labelled
local clips. On 2026-11-14 the sample was 33 clips from three bake-off rounds (Gemini Omni
Flash, Wan 2.2, 2.6 Flash, 2.7 and 3.0), labelled by eye from contact sheets:

| Check | Agreed |
| --- | --- |
| no text | 31 of 31 (7 clips with burned captions or a speech bubble) |
| line | 31 of 31 (2 silent clips) |
| identity | 20 of 21 |

The one identity miss is a gouache clip whose dark head outline grew into a large dark
shape: the panel read it as the same outline. A single model watching the whole video, before
this method, had missed burned captions. Rerun the calibration whenever the panel or a prompt
changes.

## Refresh

`.github/workflows/stylised-clip-board.yml` runs weekly. It scores candidates not yet on the
board, retries excluded rows, and commits `results.json`. It needs the repository secrets
`FAL_API_KEY` and `OPENROUTER_API_KEY`; a scheduled run without them fails, so a stale board is
never silent. A model costs its fal price for 40 s of video (about $2 to $8) plus a few cents
of judging.

Run it locally:

```sh
FAL_API_KEY=... OPENROUTER_API_KEY=... python3 harness.py run --results results.json
```

## Rights

The scores, stills and lines are EvalRank's own data, published under this repository's
Apache-2.0 license. Clips are not published.
