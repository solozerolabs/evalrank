#!/usr/bin/env python3
"""EvalRank talking-avatar board: a still + a spoken line becomes a lip-synced talking clip.

Every candidate fal endpoint lip-syncs 4 stylised stock stills (felt puppet, gouache, clay, paper
cut-out; the stylised-clip board's own stills) to 2 fixed recorded lines (one calm, one
exclaimed): 8 clips. The input is shaped from the endpoint's own fal input schema exactly as a
product sends it (``avatar_inputs``).

A clip PASSES only when every check passes:

* delivered: fal returned a video (a content-policy refusal fails the clip);
* format: portrait frame, an audio track, at least as long as the line (``ffprobe``);
* line: ``fal-ai/whisper`` hears the recorded line within ``MAX_WER`` word error (the model kept
  our audio rather than dropping or replacing it);
* no text, identity: the stylised-clip panel's questions (``JUDGE_PROMPT``);
* lips: the same panel, shown frames at ``FPS`` each labelled speaking or silent from the line's
  measured speech spans, finds the mouth moving while the line is spoken and not while silent.

The panel also rates the speaking performance 1-5 (``quality``). The board metric is
``avatar_score``: the mean over judged clips of ``quality / 5`` for a passing clip and 0 for a
failing one. A unit interval, higher is better; ``pass_rate`` is published beside it so a
consumer can require one refusal at most.

Candidates are discovered every run with no hand list: every active fal image-to-video endpoint
whose input schema takes one still and one audio file.

Usage (stdlib + ffmpeg/ffprobe; needs FAL_API_KEY and OPENROUTER_API_KEY)::

    python3 harness.py run --results results.json              # score every unscored candidate
    python3 harness.py run --results results.json --models veed/fabric-1.0
    python3 harness.py candidates                              # the discovered endpoints
    python3 harness.py calibrate --sample labelled.jsonl       # checks vs human-labelled clips
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import importlib.util
import json
import os
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
from datetime import UTC, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
# ponytail: the fal queue, upload, probe, whisper and panel plumbing is the stylised-clip
# board's, loaded by path; its harness version is part of this board's identity below.
_SPEC = importlib.util.spec_from_file_location("_stylised_clip_harness", HERE.parent / "stylised-clip" / "harness.py")
clip = importlib.util.module_from_spec(_SPEC)
sys.modules.setdefault("_stylised_clip_harness", clip)
_SPEC.loader.exec_module(clip)
Refused = clip.Refused

HARNESS_VERSION = f"1+clip{clip.HARNESS_VERSION}"
ITEMS = HERE / "items.json"
STILLS = HERE.parent / "stylised-clip"
JUDGES = clip.JUDGES
JUDGE_EFFORT = clip.JUDGE_EFFORT
TRANSCRIBER = clip.TRANSCRIBER
MAX_WER = clip.MAX_WER
MAX_ERRORS = 1
MAX_ATTEMPTS = 3
PASS_BAR = 0.875  # 7 of 8: one flaky refusal never evicts a working avatar model
REPRICE_DAYS = 28
FPS = 4  # frames per second the panel sees: enough to see a mouth open and close
SHORTER_OK = 0.25  # seconds a clip may run shorter than the line (encoder padding)
IMAGE_KEYS = ("image_url", "start_image_url")
AUDIO_KEYS = ("audio_url", "target_audio_url")
CAPTION_KEYS = ("caption", "captions", "enable_captions", "add_captions")
DIRECTION = "The character speaks to camera, small natural gestures."

LIPS_PROMPT = (
    "\n3. lips: the frames are labelled with their time and whether the recorded line is being"
    " spoken then (speaking) or not (silent). 'synced' if the mouth visibly opens, closes or"
    " changes shape across the speaking frames (a mouth resting open in a silent frame is fine);"
    " 'frozen' if the mouth barely changes while speaking, or only the jaw of a static drawing"
    " slides; 'off' if the mouth moves clearly more in the silent frames than in the speaking"
    " ones.\n"
    "4. quality: rate the speaking performance 1-5. 5: mouth shapes, face and head motion read"
    " as this character really saying the line; 3: plausible but stiff or slightly uncanny;"
    " 1: frozen, warped or unwatchable.\n"
)
JUDGE_PROMPT = clip.JUDGE_PROMPT.replace("Answer two questions.", "Answer four questions.").replace(
    "\nReply with the JSON object only.", LIPS_PROMPT + "Reply with the JSON object only."
).replace("frames from the clip, one per second, in order.", "frames from the clip, in order, each preceded by its label.")
JUDGE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "avatar_check",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "on_screen_text": {"type": "boolean"},
                "identity": {"type": "string", "enum": ["same", "changed"]},
                "lips": {"type": "string", "enum": ["synced", "frozen", "off"]},
                "quality": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
                "notes": {"type": "string"},
            },
            "required": ["on_screen_text", "identity", "lips", "quality", "notes"],
            "additionalProperties": False,
        },
    },
}
CHECKS = ("delivered", "format", "line", "no_text", "identity", "lips")
PROMPT_SHA256 = hashlib.sha256(json.dumps([DIRECTION, clip.SAFE_TAIL, JUDGE_PROMPT, JUDGE_FORMAT, FPS]).encode()).hexdigest()


def items() -> dict:
    return json.loads(ITEMS.read_text(encoding="utf-8"))


def item_set_sha256(spec: dict) -> str:
    stills = [(s["id"], s["sha256"]) for s in spec["stills"]]
    lines = [(line["id"], line["line"], line["sha256"], line["speech"]) for line in spec["lines"]]
    return hashlib.sha256(json.dumps([stills, lines]).encode()).hexdigest()


# --- candidates -------------------------------------------------------------------------------


def request_props(doc: dict) -> dict:
    """The request schema's properties: the ``*Input`` that takes a still and an audio file,
    each ``$ref``/``allOf`` resolved one level (the stylised-clip resolver, shown only it)."""
    schemas = doc.get("components", {}).get("schemas", {})
    for name, schema in schemas.items():
        props = schema.get("properties", {})
        if name.endswith("Input") and any(k in props for k in IMAGE_KEYS) and any(k in props for k in AUDIO_KEYS):
            others = {k: v for k, v in schemas.items() if not k.endswith("Input")}
            marked = {**schema, "properties": {"prompt": {}, **props}}
            out = clip.resolve_props({"components": {"schemas": {**others, name: marked}}})
            return out if "prompt" in props else {k: v for k, v in out.items() if k != "prompt"}
    return {}


def takes_still_and_audio(props: dict) -> bool:
    """One still and one audio file, each a single URL (a list of references is another task)."""
    def single(keys: tuple[str, ...]) -> bool:
        return any(k in props and (props[k].get("type") in (None, "string")) for k in keys)
    return single(IMAGE_KEYS) and single(AUDIO_KEYS)


def model_inputs(endpoint: str) -> dict:
    url = f"{clip.FAL_OPENAPI}?endpoint_id={urllib.parse.quote(endpoint, safe='/')}"
    return request_props(json.loads(clip._retry(lambda: clip._fetch(url))))


def candidates() -> list[dict]:
    """Every active fal image-to-video endpoint that takes a still and an audio file."""
    endpoints = clip.fal_endpoints()
    with concurrent.futures.ThreadPoolExecutor(16) as pool:
        props = list(pool.map(lambda row: _props_or_none(row["endpoint"]), endpoints))
    return sorted(
        ({"endpoint": row["endpoint"], "name": row.get("name") or row["endpoint"]} for row, p in zip(endpoints, props, strict=True) if p and takes_still_and_audio(p)),
        key=lambda row: row["endpoint"],
    )


def _props_or_none(endpoint: str) -> dict | None:
    try:
        return model_inputs(endpoint)
    except (urllib.error.HTTPError, OSError, json.JSONDecodeError):
        return None


# --- one clip ---------------------------------------------------------------------------------


def avatar_inputs(props: dict, seconds: float, image_url: str, audio_url: str) -> dict:
    """The request body a product sends this endpoint, shaped from its own input schema.

    The still and the audio under the keys the schema names; the motion direction when it takes
    a prompt; 9:16 (or auto/adaptive) when it asks for a frame; the highest resolution up to
    1080p; a duration rounded UP to cover the line; captions off. Raises ``Refused`` when the
    endpoint cannot take both inputs or cannot make a vertical clip.
    """
    image_key = next((k for k in IMAGE_KEYS if k in props), None)
    audio_key = next((k for k in AUDIO_KEYS if k in props), None)
    if image_key is None or audio_key is None:
        raise Refused("no_still_and_audio_input")
    out: dict = {image_key: image_url, audio_key: audio_url}
    if "prompt" in props:
        out["prompt"] = DIRECTION + clip.SAFE_TAIL
    shaped = clip.fal_inputs({"image_url": {}, **{k: props[k] for k in ("aspect_ratio", "duration") if k in props}}, seconds, image_url)
    out.update({k: v for k, v in shaped.items() if k != "image_url"})
    if isinstance(res := props.get("resolution"), dict) and (enum := res.get("enum")):
        out["resolution"] = resolution(enum)
    for key in CAPTION_KEYS:
        if isinstance(props.get(key), dict) and props[key].get("type") == "boolean":
            out[key] = False
    return out


def resolution(enum: list) -> object:
    """The highest ``<n>p`` up to 1080p, any case ("768P"); else the schema's first option."""
    lines = {v: int(str(v)[:-1]) for v in enum if str(v)[:-1].isdigit() and str(v)[-1] in "pP"}
    fits = [v for v, n in lines.items() if n <= 1080]
    return max(fits, key=lines.__getitem__) if fits else enum[0]


def frame_labels(seconds: float, speech: list[list[float]]) -> list[str]:
    """``t=0.25s speaking`` / ``silent`` for each frame ffmpeg takes at ``FPS``."""
    out = []
    for i in range(max(1, round(seconds * FPS))):
        t = (i + 0.5) / FPS
        out.append(f"t={t:.2f}s {'speaking' if any(a <= t <= b for a, b in speech) else 'silent'}")
    return out


def frames(path: Path, workdir: Path) -> list[bytes]:
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(path), "-vf", f"fps={FPS},scale=320:-2", str(workdir / "f%03d.jpg")],
        check=True,
    )
    return [p.read_bytes() for p in sorted(workdir.glob("f*.jpg"))]


def judge(api_key: str, model: str, still: bytes, shots: list[bytes], labels: list[str]) -> dict | None:
    """One judge's verdict on one clip, or None when it could not answer."""
    content: list[dict] = [{"type": "text", "text": JUDGE_PROMPT}, {"type": "text", "text": "reference still"}, {"type": "image_url", "image_url": {"url": clip._data_url(still)}}]
    for label, image in zip(labels, shots, strict=False):
        content += [{"type": "text", "text": label}, {"type": "image_url", "image_url": {"url": clip._data_url(image)}}]
    body = json.dumps({
        "model": model,
        "max_tokens": 4000,
        "messages": [{"role": "user", "content": content}],
        "response_format": JUDGE_FORMAT,
        "provider": {"require_parameters": True},
        "reasoning": {"effort": JUDGE_EFFORT, "exclude": True},
    }).encode()
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        reply = json.loads(clip._retry(lambda: clip._fetch(f"{clip.OPENROUTER}/chat/completions", headers=headers, data=body)))
        verdict = json.loads(((reply.get("choices") or [{}])[0].get("message") or {}).get("content") or "")
    except (urllib.error.HTTPError, OSError, json.JSONDecodeError, AttributeError, TypeError, ValueError):
        return None
    if (
        not isinstance(verdict, dict)
        or not isinstance(verdict.get("on_screen_text"), bool)
        or verdict.get("identity") not in {"same", "changed"}
        or verdict.get("lips") not in {"synced", "frozen", "off"}
        or verdict.get("quality") not in {1, 2, 3, 4, 5}
    ):
        return None
    return verdict


def panel(verdicts: list[dict | None]) -> dict | None:
    """Majority over the judges that answered, median quality; None below two answers."""
    got = [v for v in verdicts if v is not None]
    if len(got) < clip.MIN_JUDGES:
        return None
    majority = lambda test: sum(map(test, got)) * 2 > len(got)  # noqa: E731
    return {
        "no_text": not majority(lambda v: v["on_screen_text"]),
        "identity": majority(lambda v: v["identity"] == "same"),
        "lips": majority(lambda v: v["lips"] == "synced"),
        "quality": statistics.median(v["quality"] for v in got),
    }


def format_ok(info: dict, line_seconds: float) -> bool:
    return info["height"] > info["width"] > 0 and info["audio"] and info["seconds"] >= line_seconds - SHORTER_OK


def check_clip(path: Path, still_path: Path, line: dict, url: str, *, fal_key: str, api_key: str) -> dict:
    """Every check but ``delivered`` for one clip on disk."""
    info = clip.probe(path)
    heard = clip.transcribe(fal_key, url) if info["audio"] else ""
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        shots, still = frames(path, work), clip.still_preview(still_path, work)
    labels = frame_labels(len(shots) / FPS, line["speech"])
    verdicts = [judge(api_key, model, still, shots, labels) for model in JUDGES]
    agreed = panel(verdicts)
    error_rate = clip.wer(line["line"], heard)
    return {
        "format": format_ok(info, line["seconds"]),
        "line": error_rate <= MAX_WER,
        **({k: None for k in ("no_text", "identity", "lips", "quality")} if agreed is None else agreed),
        "transcript": heard,
        "wer": round(error_rate, 3),
        "judges_answered": sum(v is not None for v in verdicts),
        "verdicts": verdicts,
        "probe": info,
    }


def verdict(checks: dict) -> tuple[bool, bool]:
    """``(passed, error)``: a format or line failure fails the clip whatever the panel says."""
    if not (checks["format"] and checks["line"]):
        return False, False
    if checks["no_text"] is None:
        return False, True
    return bool(checks["no_text"] and checks["identity"] and checks["lips"]), False


def score_clip(endpoint: str, props: dict, still: dict, line: dict, urls: dict, *, fal_key: str, api_key: str, keep: Path | None) -> dict:
    out = {"still_id": still["id"], "line_id": line["id"]}
    started = time.monotonic()
    try:
        payload = avatar_inputs(props, line["seconds"], urls[still["id"]], urls[line["id"]])
        out["video_seconds"] = float(payload.get("duration") or line["seconds"])
        url = clip.video_url(clip.fal_run(fal_key, endpoint, payload))
    except Refused as exc:
        return {**out, "delivered": False, "passed": False, "code": str(exc), "error": False}
    except Exception as exc:  # noqa: BLE001 - transport trouble is an error, retried next run
        return {**out, "passed": False, "error": True, "code": type(exc).__name__}
    out["seconds_to_video"] = round(time.monotonic() - started, 1)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "clip.mp4"
            path.write_bytes(clip._retry(lambda: clip._fetch(url)))
            if keep is not None:
                (keep / f"{endpoint.replace('/', '__')}__{still['id']}__{line['id']}.mp4").write_bytes(path.read_bytes())
            checks = check_clip(path, STILLS / still["file"], line, url, fal_key=fal_key, api_key=api_key)
    except Exception as exc:  # noqa: BLE001
        return {**out, "delivered": True, "passed": False, "error": True, "code": type(exc).__name__}
    passed, error = verdict(checks)
    out["video_seconds"] = (checks.get("probe") or {}).get("seconds") or out["video_seconds"]
    return {**out, "delivered": True, **checks, "passed": passed, "error": error}


# --- a row ------------------------------------------------------------------------------------


def summarize(candidate: dict, clips: list[dict], price: dict | None) -> dict:
    judged = [c for c in clips if not c["error"]]
    errors = len(clips) - len(judged)
    passed = sum(c["passed"] for c in judged)
    seconds = [c["seconds_to_video"] for c in clips if "seconds_to_video" in c]
    score = sum(c["quality"] / 5 for c in judged if c["passed"]) / len(judged) if judged else 0.0
    return {
        "model": candidate["name"],
        "endpoint": candidate["endpoint"],
        "score": round(score, 4),
        "pass_rate": round(passed / len(judged), 4) if judged else 0.0,
        "clips": len(clips),
        "passed": passed,
        "errors": errors,
        "excluded": errors > MAX_ERRORS,
        "check_passes": {name: sum(c.get(name) is True for c in judged) for name in CHECKS},
        "quality_median": statistics.median(c["quality"] for c in judged if c.get("quality")) if any(c.get("quality") for c in judged) else None,
        "refusals": sorted({c["code"] for c in judged if not c.get("delivered", True)}),
        "seconds_to_video_p50": round(statistics.median(seconds), 1) if seconds else None,
        "list_price": price,
        "scored_at": _now(),
        "clip_results": [
            {k: c.get(k) for k in ("still_id", "line_id", "passed", "error", "code", *CHECKS, "quality", "wer", "transcript")}
            for c in clips
        ],
    }


def upload_items(fal_key: str) -> dict[str, str]:
    spec = items()
    urls = {s["id"]: clip.upload(fal_key, (STILLS / s["file"]).read_bytes(), s["content_type"], Path(s["file"]).name) for s in spec["stills"]}
    urls |= {line["id"]: clip.upload(fal_key, (HERE / line["file"]).read_bytes(), "audio/mpeg", Path(line["file"]).name) for line in spec["lines"]}
    return urls


def score_model(candidate: dict, urls: dict, *, fal_key: str, api_key: str, concurrency: int, keep: Path | None) -> dict:
    spec = items()
    props = model_inputs(candidate["endpoint"])
    jobs = [(still, line) for still in spec["stills"] for line in spec["lines"]]
    started = _now()
    with concurrent.futures.ThreadPoolExecutor(max(1, concurrency)) as pool:
        clips = list(pool.map(lambda job: score_clip(candidate["endpoint"], props, job[0], job[1], urls, fal_key=fal_key, api_key=api_key, keep=keep), jobs))
    row = summarize(candidate, clips, clip.list_price(fal_key, candidate["endpoint"]))
    return {**row, "billing": clip.billing(fal_key, started, clips)}


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def empty_results() -> dict:
    spec = items()
    return {
        "object": "evalrank_talking_avatar_board",
        "schema_version": "1",
        "harness_version": HARNESS_VERSION,
        "metric": "avatar_score",
        "metric_direction": "higher",
        "prompt_sha256": PROMPT_SHA256,
        "item_set_sha256": item_set_sha256(spec),
        "transcriber": TRANSCRIBER,
        "max_wer": MAX_WER,
        "judges": list(JUDGES),
        "judge_effort": JUDGE_EFFORT,
        "datasets": [{
            "dataset_id": "evalrank-talking-avatar",
            "url": "boards/talking-avatar/items.json",
            "sha256": hashlib.sha256(ITEMS.read_bytes()).hexdigest(),
            "license": spec["license"],
            "attribution": spec["attribution"],
            "items": len(spec["stills"]) * len(spec["lines"]),
        }],
        "updated_at": None,
        "models": [],
    }


IDENTITY = ("prompt_sha256", "item_set_sha256", "harness_version", "judges", "judge_effort", "transcriber", "max_wer")


def load_results(path: Path) -> dict:
    fresh = empty_results()
    if not path.exists():
        return fresh
    current = json.loads(path.read_text(encoding="utf-8"))
    return current if all(current.get(key) == fresh[key] for key in IDENTITY) else fresh


def passers(results: dict, found: list[dict]) -> list[dict]:
    """Rows a pick could come from, best score first (undiscovered rows drop out)."""
    live = {c["endpoint"] for c in found}
    rows = [r for r in results["models"] if not r["excluded"] and r["pass_rate"] >= PASS_BAR and r["endpoint"] in live]
    return sorted(rows, key=lambda r: (-r["score"], r["endpoint"]))


def pick(results: dict, found: list[dict], wanted: set[str], *, rescore: bool) -> list[dict]:
    """Candidates to score: unscored ones, plus excluded ones under ``MAX_ATTEMPTS``.

    With no arena to rank them first, a new endpoint can only be judged by scoring it, so a
    weekly run scores only endpoints it has never scored (capped by ``--max-models``).
    """
    todo = [c for c in found if (c["endpoint"] in wanted if wanted else True)]
    if rescore or wanted:
        return todo
    rows = {row["endpoint"]: row for row in results["models"]}
    return [
        c for c in todo
        if c["endpoint"] not in rows or (rows[c["endpoint"]]["excluded"] and rows[c["endpoint"]].get("attempts", 1) < MAX_ATTEMPTS)
    ]


def due_for_price(results: dict, found: list[dict], key_id: str, *, now: datetime) -> list[dict]:
    """Passers, best first, whose price is missing, from another key, or over ``REPRICE_DAYS`` old."""
    def stale(row: dict) -> bool:
        bill = row.get("billing")
        if not bill or bill["key_id"] != key_id:
            return True
        age = now - datetime.strptime(bill["finished_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        return age > timedelta(days=REPRICE_DAYS)
    return [row for row in passers(results, found) if stale(row)]


def reprice_row(row: dict, urls: dict, *, fal_key: str) -> dict:
    """One clip (the first still and line) on the board key: a fresh ``billing`` window."""
    spec = items()
    still, line = spec["stills"][0], spec["lines"][0]
    started = _now()
    payload = avatar_inputs(model_inputs(row["endpoint"]), line["seconds"], urls[still["id"]], urls[line["id"]])
    url = clip.video_url(clip.fal_run(fal_key, row["endpoint"], payload))
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "clip.mp4"
        path.write_bytes(clip._retry(lambda: clip._fetch(url)))
        seconds = clip.probe(path)["seconds"] or line["seconds"]
    return {**row, "billing": clip.billing(fal_key, started, [{"delivered": True, "video_seconds": seconds}])}


def attempts(results: dict, row: dict) -> int:
    prior = next((r for r in results["models"] if r["endpoint"] == row["endpoint"]), None)
    return prior.get("attempts", 1) + 1 if prior and prior["excluded"] else 1


def _save(results: dict, path: Path) -> None:
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def calibrate(sample: list[dict], *, fal_key: str, api_key: str) -> dict:
    """Run the post-generation checks on labelled local clips; agreement per check.

    Rows: ``{"video": path, "still": id, "line": id, "labels": {check: bool}}``.
    """
    spec = items()
    stills = {s["id"]: s for s in spec["stills"]}
    lines = {line["id"]: line for line in spec["lines"]}

    def _check(row: dict) -> tuple[dict, dict]:
        path = Path(row["video"])
        url = row.get("url") or clip.upload(fal_key, path.read_bytes(), "video/mp4", path.name)
        return row, check_clip(path, STILLS / stills[row["still"]]["file"], lines[row["line"]], url, fal_key=fal_key, api_key=api_key)

    tally: dict[str, dict[str, int]] = {}
    rows = []
    with concurrent.futures.ThreadPoolExecutor(8) as pool:
        for row, got in pool.map(_check, sample):
            for name, want in row["labels"].items():
                t = tally.setdefault(name, {"agree": 0, "disagree": 0, "undecided": 0})
                t["undecided" if got.get(name) is None else ("agree" if got[name] == want else "disagree")] += 1
            rows.append({"video": Path(row["video"]).name, "labels": row["labels"], "got": {k: got.get(k) for k in [*row["labels"], "quality"]}, "verdicts": got["verdicts"]})
    return {"per_check": tally, "rows": rows}


def _verify_items() -> str | None:
    spec = items()
    for still in spec["stills"]:
        if hashlib.sha256((STILLS / still["file"]).read_bytes()).hexdigest() != still["sha256"]:
            return still["file"]
    for line in spec["lines"]:
        if hashlib.sha256((HERE / line["file"]).read_bytes()).hexdigest() != line["sha256"]:
            return line["file"]
    return None


def main(argv: list[str] | None = None) -> int:  # noqa: C901, PLR0911, PLR0915 - one CLI
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--results", type=Path, required=True)
    run.add_argument("--models", default="", help="comma-separated fal endpoints; default: every unscored candidate")
    run.add_argument("--rescore", action="store_true")
    run.add_argument("--max-models", type=int, default=0, help="score at most this many models (the weekly cost cap)")
    run.add_argument("--keep-board", action="store_true", help="refuse instead of starting a new board when the prompt, items or panel changed")
    run.add_argument("--keep-clips", type=Path, default=None, help="save every clip here (for calibration)")
    run.add_argument("--concurrency", type=int, default=8, help="clips in flight per model")
    run.add_argument("--workers", type=int, default=2, help="models scored in parallel")
    cal = sub.add_parser("calibrate")
    cal.add_argument("--sample", type=Path, required=True)
    sub.add_parser("candidates")
    rep = sub.add_parser("reprice", help="re-measure passers' prices with one clip each")
    rep.add_argument("--results", type=Path, required=True)
    rep.add_argument("--max-models", type=int, default=1, help="0 = every passer that is due")
    args = parser.parse_args(argv)

    if args.command == "candidates":
        for row in candidates():
            print(f"{row['endpoint']}\t{row['name']}")
        return 0
    fal_key = os.environ.get("FAL_API_KEY", "")
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not fal_key or not api_key:
        print("error: FAL_API_KEY and OPENROUTER_API_KEY must both be set", file=sys.stderr)
        return 2
    if (bad := _verify_items()) is not None:
        print(f"error: {bad} does not match its pinned sha256", file=sys.stderr)
        return 2
    if args.command == "calibrate":
        sample = [json.loads(line) for line in args.sample.read_text(encoding="utf-8").splitlines() if line.strip()]
        print(json.dumps(calibrate(sample, fal_key=fal_key, api_key=api_key), indent=2))
        return 0

    results = load_results(args.results)
    found = candidates()
    if args.command == "reprice":
        due = due_for_price(results, found, fal_key.split(":", 1)[0], now=datetime.now(UTC))
        due = due[: args.max_models] if args.max_models else due
        if not due:
            print("no prices due", file=sys.stderr)
            return 0
        urls = upload_items(fal_key)
        for row in due:
            try:
                results = _merge(results, [reprice_row(row, urls, fal_key=fal_key)])
            except Exception as exc:  # noqa: BLE001 - one model's failure never stops the run
                print(f"{row['endpoint']}: reprice failed ({type(exc).__name__}: {exc})", file=sys.stderr)
                continue
            _save(results, args.results)
            print(f"{row['endpoint']}: repriced", file=sys.stderr)
        return 0
    if args.keep_board and args.results.exists() and not results["models"] and json.loads(args.results.read_text(encoding="utf-8"))["models"]:
        print("error: the board's prompt, items or panel changed; rescoring every model is a manual run", file=sys.stderr)
        return 3
    todo = pick(results, found, {name for name in args.models.split(",") if name}, rescore=args.rescore)
    todo = todo[: args.max_models] if args.max_models else todo
    if not todo:
        print("no candidates to score", file=sys.stderr)
        return 0
    if args.keep_clips is not None:
        args.keep_clips.mkdir(parents=True, exist_ok=True)
    urls = upload_items(fal_key)
    lock = threading.Lock()

    def _one(candidate: dict) -> None:
        nonlocal results
        try:
            row = score_model(candidate, urls, fal_key=fal_key, api_key=api_key, concurrency=args.concurrency, keep=args.keep_clips)
        except Exception as exc:  # noqa: BLE001 - one model's failure never stops the run
            print(f"{candidate['endpoint']}: failed ({type(exc).__name__}: {exc}); not recorded", file=sys.stderr)
            return
        with lock:
            row["attempts"] = attempts(results, row)
            results = _merge(results, [row])
            _save(results, args.results)
            print(
                f"{row['endpoint']}: score={row['score']} pass_rate={row['pass_rate']} errors={row['errors']}"
                f" checks={row['check_passes']} refusals={row['refusals']}",
                file=sys.stderr,
            )

    with concurrent.futures.ThreadPoolExecutor(max(1, args.workers)) as workers:
        list(workers.map(_one, todo))
    print(f"{len(results['models'])} models on the board", file=sys.stderr)
    return 0


def _merge(results: dict, rows: list[dict]) -> dict:
    return clip.merge(results, rows)


if __name__ == "__main__":
    raise SystemExit(main())
