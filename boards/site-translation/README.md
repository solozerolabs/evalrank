# Site-translation board

An open EvalRank board that ranks general chat LLMs as **translators of short small-business
website copy**: opening hours, prices, phone numbers, reviews and offers, into 15 languages,
with reasoning off and a strict JSON reply. It feeds the `multilingual` cell's
model-configuration group (`catalog/manifest.json`, family `evalrank-site-translation`).

No public board (surveyed 2026-10-29) measures this. WMT runs once a year, Artificial
Analysis's multilingual index is paid, and LMArena's non-English arena has no Arabic, Hebrew,
Hindi or Thai category. So EvalRank runs this board itself, from public and own data with a
public harness, and publishes every row.

## Method

- **Segments** (40, digest-pinned):
  - 30 of EvalRank's own strings (`items.json`, Apache-2.0). They carry what site copy carries:
    12-hour clocks, prices in £, $ and €, phone numbers, a URL, an email, a `{placeholder}`, a
    discount code and an Instagram handle (protected terms), and review idioms.
  - 10 English sources from [WMT24++](https://huggingface.co/datasets/google/wmt24pp)
    (Apache-2.0), pinned by file sha256 and segment id. Only the English source is used. The
    judges are reference-free, so no reference is needed, and WMT24++ text is never
    republished here.
- **Languages** (15): es, fr, de, pt-BR, pl, fi, tr, ru, ar, he, hi, th, ja, ko, zh-Hans.
- **Call:** one call per language carries all 40 segments, the way a site translator batches a
  page. Each call has:
  - a strict `json_schema` reply with `provider.require_parameters`;
  - reasoning off (`effort: none`);
  - temperature 0 where the model takes it.
- **Score per segment:** a deterministic check times the panel verdict.
  - The check covers:
    - money amounts, long numbers, English am/pm clocks and currency symbols;
    - the URL, the email, the placeholder and the protected terms;
    - the target script, an untranslated copy, and English words left in a non-Latin script.

    A failure, or a missing or duplicated id, scores 0.
  - The panel is the median verdict of three LLM judges from three vendors:
    `anthropic/claude-sonnet-5.5`, `google/gemini-3.8-flash` and `openai/gpt-6.1-terra-pro`, at
    low reasoning effort. The verdicts score no_error 1, minor 0.75, major 0.25 and critical 0.
    Every judge has mandatory reasoning, so no judge is ever a candidate and no model grades
    itself.
- **Board metric:** the mean over all 600 segments. It is a unit interval and higher is better.
  Each row also publishes per-language scores, per-source (own and WMT24++) scores, and its
  check-failure codes.
- **Errors:** a failed call (transport, refusal, unparseable reply) or a segment fewer than two
  judges graded is an error. A row with more than 5% errors is published with `excluded: true`
  and never ranked.
- **Candidates:** every OpenRouter text model that:
  - takes a strict `json_schema` (`structured_outputs`);
  - can answer with reasoning off (`reasoning.mandatory` is false, and `none` is a supported
    effort when efforts are listed);
  - is priced at or under $2/M input and $10/M output tokens;
  - was released in the last 365 days;
  - is not a `:free`, `:batch` or `~` alias.

  `python3 harness.py candidates` prints the current list.
- **Identity:** `results.json` records the item-set digest (segment texts, languages and protected
  terms), the prompt sha256 (both prompts and the grading rules), the dataset sha256s and the
  judge panel. A
  change to any of them, or to `HARNESS_VERSION`, starts a new board instead of mixing scores.

## Judge validation

`python3 harness.py calibrate --sample <jsonl>` grades a human-labelled sample of rows
`{code, en, text, catch}` and reports how well each judge, the panel and the full scorer agree
with the labels.

On 2026-10-29 the sample was 68 site-translation lines in the same 15 languages: 28 lines a
native reader marked as major errors (changed values, English clocks, idioms that flip a
count, English left in) and 40 clean lines. The results:

- The panel median scored balanced accuracy 0.97: it caught 27 of the 28 errors and flagged 1
  of the 40 clean lines.
- Single judges scored 0.94 to 0.98.

The panel agrees with the human sample, so no learned metric (MetricX-24-QE) is added. Rerun
the calibration whenever the panel or the judge prompt changes.

## Refresh

`.github/workflows/site-translation-board.yml` runs weekly. It scores candidates not yet on
the board, retries excluded rows (a 404 costs nothing), and commits `results.json`. It needs the repository secret `OPENROUTER_API_KEY`;
a scheduled run without it fails, so a stale board is never silent. A full board costs about
$0.17 per model.

Run it locally:

```sh
OPENROUTER_API_KEY=... python3 harness.py run --results results.json
```

## Rights

The scores are EvalRank's own data, published under this repository's Apache-2.0 license.
Datasets: EvalRank's own site-copy strings (Apache-2.0) and WMT24++ by Deutsch et al., Google
(Apache-2.0). Republish rows with the same attribution.
