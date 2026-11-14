#!/usr/bin/env python3
"""EvalRank stylised-clip board: image-to-video models animating a stylised character that speaks.

Every candidate fal endpoint animates 4 stylised stock stills (felt puppet, gouache, clay, paper
cut-out) x 2 spoken lines (one calm, one exclaimed): 8 clips, 5 s, vertical, audio on. The input
is shaped from the endpoint's own fal input schema exactly as a product would send it (image
key, 9:16, 1080p when offered, audio on, duration rounded UP to an allowed length).

A clip PASSES only when every check passes:

* delivered: fal returned a video (a refusal, e.g. a moderation 422, fails the clip);
* format: portrait frame, an audio track, at least ``MIN_SECONDS`` long (``ffprobe``);
* line: ``fal-ai/whisper`` transcribes the spoken line within ``MAX_WER`` word error;
* no text: a three-vendor vision panel, shown the still and one frame per second, finds no
  captions, subtitles, speech bubbles or letters that are not in the still (majority);
* identity: the same panel finds the character's design, outfit, hair, colours and art style
  unchanged (majority "same"; pose, expression and camera may change).

The board metric is the pass rate over the 8 clips: a unit interval, higher is better. A clip
that could not be judged (transport failure, fewer than two judge verdicts) is an error, not a
fail; a row with more than ``MAX_ERRORS`` errors is published with ``excluded: true``, never
ranked, and retried next run.

The entity name is the LMArena arena name (``candidates.json``, a reviewed map), so a row joins
the LMArena video families in EvalRank; the fal endpoint is row metadata.

Usage (stdlib + ffmpeg/ffprobe; needs FAL_API_KEY and OPENROUTER_API_KEY)::

    python3 harness.py run --results results.json              # score every unscored candidate
    python3 harness.py run --results results.json --models alibaba/wan-3.0/image-to-video
    python3 harness.py candidates                              # the map, with fal status
    python3 harness.py calibrate --sample labelled.jsonl       # checks vs human-labelled clips
"""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import hashlib
import http.client
import json
import math
import os
import re
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

HARNESS_VERSION = "1"
HERE = Path(__file__).resolve().parent
ITEMS = HERE / "items.json"
CANDIDATES = HERE / "candidates.json"
FAL_QUEUE = "https://queue.fal.run"
FAL_API = "https://api.fal.ai/v1"
FAL_OPENAPI = "https://fal.ai/api/openapi/queue/openapi.json"
FAL_STORAGE = "https://rest.alpha.fal.ai/storage/upload/initiate?storage_type=fal-cdn-v3"
OPENROUTER = "https://openrouter.ai/api/v1"
TRANSCRIBER = "fal-ai/whisper"
JUDGES = ("anthropic/claude-sonnet-5.5", "google/gemini-3.8-flash", "openai/gpt-6.1-terra-pro")
JUDGE_EFFORT = "low"
MIN_JUDGES = 2
MAX_WER = 0.2
MIN_SECONDS = 4.5
MAX_ERRORS = 1
CLIP_TIMEOUT_SECONDS = 900
REQUEST_TIMEOUT_SECONDS = 180
RETRIES = 4
POLL_SECONDS = 5

# The product's motion prompt tail: style lock and no burned-in text.
SAFE_TAIL = (
    " Keep the character, set and lighting exactly as in the image. No music, no captions, no"
    " on-screen text."
)
JUDGE_PROMPT = (
    "You check one AI-generated video clip. The first image is the reference still the clip was"
    " animated from; the next images are frames from the clip, one per second, in order.\n"
    "Answer two questions.\n"
    "1. on_screen_text: true if ANY frame shows text that is not in the reference still:"
    " captions, subtitles, speech bubbles, titles, letters or words overlaid on or drawn into"
    " the picture. Text already in the still (for example on a screen) and unchanged does not"
    " count.\n"
    "2. identity: 'changed' if, in any frame, the character's clothing or accessories are added,"
    " removed or swapped, the hair changes (colour, length, shape), the art style or medium"
    " changes (for example paint becomes clean vector, felt becomes plastic), the character"
    " becomes a realistic human, or it becomes a different character. Otherwise 'same'. Facial"
    " features that animate as part of an expression do NOT count: a mouth opening, teeth, a"
    " tongue, eyebrows or eyelids appearing for an expression, blinking, hands or arms entering"
    " the frame for a gesture, and any change of pose, camera, crop or lighting.\n"
    "Reply with the JSON object only."
)
JUDGE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "clip_check",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "on_screen_text": {"type": "boolean"},
                "identity": {"type": "string", "enum": ["same", "changed"]},
                "notes": {"type": "string"},
            },
            "required": ["on_screen_text", "identity", "notes"],
            "additionalProperties": False,
        },
    },
}
CHECKS = ("delivered", "format", "line", "no_text", "identity")
_IMAGE_KEYS = ("image_url", "start_image_url")
_AUDIO_KEYS = ("generate_audio", "audio", "enable_audio", "with_audio")
_RESOLUTIONS = ("1080p", "720p", "580p", "540p", "480p", "360p")
_VERTICAL = ("9:16", "auto", "adaptive")
PROMPT_SHA256 = hashlib.sha256(json.dumps([SAFE_TAIL, JUDGE_PROMPT, JUDGE_FORMAT]).encode()).hexdigest()


class Refused(Exception):
    """fal refused or failed the request; ``args[0]`` is a short code."""


def _fetch(url: str, *, headers: dict[str, str] | None = None, data: bytes | None = None, method: str | None = None) -> bytes:
    request = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:  # noqa: S310 - fixed https hosts
        return response.read()


def _retry(call):
    for attempt in range(RETRIES):
        try:
            return call()
        except urllib.error.HTTPError as exc:
            if exc.code not in {408, 429, 500, 502, 503, 504} or attempt + 1 == RETRIES:
                raise
        except (OSError, http.client.HTTPException):
            if attempt + 1 == RETRIES:
                raise
        time.sleep(2 ** (attempt + 1))
    raise AssertionError("unreachable")


def items() -> dict:
    return json.loads(ITEMS.read_text(encoding="utf-8"))


def candidates() -> list[dict]:
    return json.loads(CANDIDATES.read_text(encoding="utf-8"))["candidates"]


def item_set_sha256(spec: dict) -> str:
    stills = [(s["id"], s["sha256"]) for s in spec["stills"]]
    lines = [(line["id"], line["direction"], line["line"]) for line in spec["lines"]]
    return hashlib.sha256(json.dumps([stills, lines, spec["seconds"]]).encode()).hexdigest()


def prompt_for(line: dict) -> str:
    return f'{line["direction"]} They say: "{line["line"]}"{SAFE_TAIL}'


def fal_inputs(props: dict, seconds: float, image_url: str) -> dict:
    """The request body a product sends this endpoint, shaped from its own input schema.

    Raises ``Refused`` when the endpoint cannot take a still or cannot make a vertical clip.
    """
    image_key = next((key for key in _IMAGE_KEYS if key in props), None)
    if image_key is None:
        raise Refused("no_image_input")
    out: dict = {image_key: image_url}
    aspect = props.get("aspect_ratio")
    if isinstance(aspect, dict) and (enum := aspect.get("enum")):
        choice = next((value for value in _VERTICAL if value in enum), None)
        if choice is None:
            raise Refused("no_vertical")
        out["aspect_ratio"] = choice
    resolution = props.get("resolution")
    if isinstance(resolution, dict) and (enum := resolution.get("enum")):
        out["resolution"] = next((value for value in _RESOLUTIONS if value in enum), enum[0])
    duration = props.get("duration")
    if isinstance(duration, dict):
        options = duration.get("enum") or next(
            (branch.get("enum") for branch in duration.get("anyOf", []) if branch.get("enum")), None
        )
        if options:
            allowed = [value for value in options if str(value).replace(".", "", 1).isdigit()]
            if not allowed:
                raise ValueError(f"no numeric duration among {options}")
            longer = [value for value in allowed if float(value) >= seconds]
            out["duration"] = min(longer, key=float) if longer else max(allowed, key=float)
        elif duration.get("type") == "number":
            out["duration"] = seconds
        elif duration.get("type") == "string":
            out["duration"] = str(math.ceil(seconds))
        else:
            out["duration"] = math.ceil(seconds)
    for key in _AUDIO_KEYS:
        if isinstance(props.get(key), dict) and props[key].get("type") == "boolean":
            out[key] = True
    return out


def resolve_props(doc: dict) -> dict:
    """The request schema's properties, each with ``$ref``/``allOf`` resolved one level.

    The request schema is the ``*Input`` schema that takes a ``prompt``; a nested ``*Input``
    (a LoRA, a reference image) never matches.
    """
    schemas = doc.get("components", {}).get("schemas", {})
    props = next(
        (v.get("properties", {}) for k, v in schemas.items() if k.endswith("Input") and "prompt" in v.get("properties", {})),
        {},
    )

    def _one(prop: dict) -> dict:
        ref = prop.get("$ref") or next((p.get("$ref") for p in prop.get("allOf", []) if "$ref" in p), None)
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            return {**schemas.get(ref.rsplit("/", 1)[1], {}), **{k: v for k, v in prop.items() if k not in {"$ref", "allOf"}}}
        return prop

    return {name: _one(prop) if isinstance(prop, dict) else prop for name, prop in props.items()}


def model_inputs(endpoint: str) -> dict:
    return resolve_props(json.loads(_retry(lambda: _fetch(f"{FAL_OPENAPI}?endpoint_id={urllib.parse.quote(endpoint, safe='/')}"))))


def _fal_headers(key: str) -> dict[str, str]:
    return {"Authorization": f"Key {key}", "Content-Type": "application/json"}


def upload(key: str, data: bytes, content_type: str, name: str) -> str:
    """Put bytes on fal's CDN; the file URL fal endpoints read."""
    body = json.dumps({"content_type": content_type, "file_name": name}).encode()
    target = json.loads(_retry(lambda: _fetch(FAL_STORAGE, headers=_fal_headers(key), data=body)))
    _retry(lambda: _fetch(target["upload_url"], headers={"Content-Type": content_type}, data=data, method="PUT"))
    return target["file_url"]


def _detail(exc: urllib.error.HTTPError) -> dict:
    try:
        detail = json.loads(exc.read() or b"{}").get("detail")
    except (json.JSONDecodeError, OSError, AttributeError):
        return {}
    return detail[0] if isinstance(detail, list) and detail and isinstance(detail[0], dict) else {}


def model_refusal(exc: urllib.error.HTTPError) -> str | None:
    """The refusal code when the MODEL declined a valid request, else None.

    Only two 422s are the model's: a content-policy refusal, and fal's "could not generate" for
    a well-formed prompt. A bad key, an empty balance, a schema mismatch in our own request or
    any other 4xx is ours, so it is an error (retried next run), never a published fail.
    """
    if exc.code != 422:
        return None
    detail = _detail(exc)
    kind = detail.get("type")
    if kind == "content_policy_violation":
        return f"http_422:{kind}"
    if kind == "invalid_request" and "could not generate" in str(detail.get("msg", "")).lower():
        return f"http_422:{kind}"
    return None


def fal_run(key: str, endpoint: str, payload: dict, *, timeout: float = CLIP_TIMEOUT_SECONDS) -> dict:
    """Submit to fal's queue, poll, and return the result JSON. ``Refused`` on a refusal."""
    headers = _fal_headers(key)
    try:
        submitted = json.loads(_submit(f"{FAL_QUEUE}/{endpoint}", headers, json.dumps(payload).encode()))
        deadline = None  # starts when fal starts the job: time queued behind other jobs is not the model's
        while True:
            status = json.loads(_retry(lambda: _fetch(submitted["status_url"], headers=headers)))
            state = status.get("status")
            if state == "COMPLETED":
                break
            if state not in {"IN_QUEUE", "IN_PROGRESS"}:
                raise RuntimeError(f"fal status {state}")  # an error: retried next run
            if state == "IN_PROGRESS" and deadline is None:
                deadline = time.monotonic() + timeout
            if deadline is not None and time.monotonic() > deadline:
                raise TimeoutError(f"{endpoint} ran past {timeout} s")
            time.sleep(POLL_SECONDS)
        return json.loads(_retry(lambda: _fetch(submitted["response_url"], headers=headers)))
    except urllib.error.HTTPError as exc:
        code = model_refusal(exc)
        if code is not None:
            raise Refused(code) from exc
        raise


def _submit(url: str, headers: dict[str, str], body: bytes) -> bytes:
    """One queue submit. Retried only on 429/503, which fal sends before accepting a job: a
    retry after a read timeout could queue (and pay for) the same job twice."""
    for attempt in range(RETRIES):
        try:
            return _fetch(url, headers=headers, data=body)
        except urllib.error.HTTPError as exc:
            if exc.code not in {429, 503} or attempt + 1 == RETRIES:
                raise
        time.sleep(2 ** (attempt + 1))
    raise AssertionError("unreachable")


def video_url(result: dict) -> str:
    video = result.get("video")
    url = video.get("url") if isinstance(video, dict) else None
    if not isinstance(url, str):
        raise Refused("no_video")
    return url


def probe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height:format=duration", "-of", "json", str(path)],
        capture_output=True, check=True, text=True,
    )
    info = json.loads(out.stdout)
    video = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), {})
    return {
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "audio": any(s.get("codec_type") == "audio" for s in info.get("streams", [])),
        "seconds": float((info.get("format") or {}).get("duration") or 0),
    }


def format_ok(info: dict) -> bool:
    return info["height"] > info["width"] > 0 and info["audio"] and info["seconds"] >= MIN_SECONDS


_WORD = re.compile(r"[a-z0-9']+")


def words(text: str) -> list[str]:
    return _WORD.findall(text.lower().replace("’", "'"))


def wer(expected: str, heard: str) -> float:
    """Word error rate of ``heard`` against ``expected`` (substitutions, insertions, deletions)."""
    ref, hyp = words(expected), words(heard)
    if not ref:
        return 0.0 if not hyp else 1.0
    row = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        prev, row[0] = row[0], i
        for j, h in enumerate(hyp, 1):
            prev, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, prev + (r != h))
    return row[-1] / len(ref)


def transcribe(key: str, url: str) -> str:
    result = fal_run(key, TRANSCRIBER, {"audio_url": url, "task": "transcribe", "language": "en"}, timeout=300)
    return str(result.get("text") or "")


def frames(path: Path, workdir: Path) -> list[bytes]:
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(path), "-vf", "fps=1,scale=360:-2", str(workdir / "f%02d.jpg")],
        check=True,
    )
    return [p.read_bytes() for p in sorted(workdir.glob("f*.jpg"))]


def still_preview(path: Path, workdir: Path) -> bytes:
    out = workdir / "still.jpg"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(path), "-vf", "scale=360:-2", str(out)], check=True)
    return out.read_bytes()


def _data_url(jpeg: bytes) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()


def judge(api_key: str, model: str, still: bytes, shots: list[bytes]) -> dict | None:
    """One judge's verdict on one clip, or None when it could not answer."""
    content = [{"type": "text", "text": JUDGE_PROMPT}] + [
        {"type": "image_url", "image_url": {"url": _data_url(image)}} for image in [still, *shots]
    ]
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
        reply = json.loads(_retry(lambda: _fetch(f"{OPENROUTER}/chat/completions", headers=headers, data=body)))
        verdict = json.loads(((reply.get("choices") or [{}])[0].get("message") or {}).get("content") or "")
    except (urllib.error.HTTPError, OSError, http.client.HTTPException, json.JSONDecodeError, AttributeError, TypeError):
        return None
    if not isinstance(verdict.get("on_screen_text"), bool) or verdict.get("identity") not in {"same", "changed"}:
        return None
    return verdict


def panel(verdicts: list[dict | None]) -> dict | None:
    """Majority over the judges that answered; None below ``MIN_JUDGES``."""
    got = [v for v in verdicts if v is not None]
    if len(got) < MIN_JUDGES:
        return None
    text = sum(v["on_screen_text"] for v in got) * 2 > len(got)
    same = sum(v["identity"] == "same" for v in got) * 2 > len(got)
    return {"no_text": not text, "identity": same}


def check_clip(path: Path, still_path: Path, line: str, url: str, *, fal_key: str, api_key: str) -> dict:
    """Every check but ``delivered`` for one clip on disk. ``error`` when it could not be judged."""
    info = probe(path)
    heard = transcribe(fal_key, url) if info["audio"] else ""
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        shots, still = frames(path, work), still_preview(still_path, work)
    verdicts = [judge(api_key, model, still, shots) for model in JUDGES]
    agreed = panel(verdicts)
    error_rate = wer(line, heard)
    return {
        "format": format_ok(info),
        "line": error_rate <= MAX_WER,
        "no_text": None if agreed is None else agreed["no_text"],
        "identity": None if agreed is None else agreed["identity"],
        "transcript": heard,
        "wer": round(error_rate, 3),
        "judges_answered": sum(v is not None for v in verdicts),
        "verdicts": verdicts,
        "probe": info,
    }


def score_clip(endpoint: str, props: dict, still: dict, line: dict, still_url: str, seconds: float, *, fal_key: str, api_key: str) -> dict:
    clip = {"still_id": still["id"], "line_id": line["id"]}
    started = time.monotonic()
    try:
        payload = {"prompt": prompt_for(line), **fal_inputs(props, seconds, still_url)}
        url = video_url(fal_run(fal_key, endpoint, payload))
    except Refused as exc:
        return {**clip, "delivered": False, "passed": False, "code": str(exc), "error": False}
    except Exception as exc:  # noqa: BLE001 - transport trouble is an error, retried next run
        return {**clip, "passed": False, "error": True, "code": type(exc).__name__}
    clip["seconds_to_video"] = round(time.monotonic() - started, 1)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "clip.mp4"
            path.write_bytes(_retry(lambda: _fetch(url)))
            checks = check_clip(path, HERE / still["file"], line["line"], url, fal_key=fal_key, api_key=api_key)
    except Exception as exc:  # noqa: BLE001
        return {**clip, "delivered": True, "passed": False, "error": True, "code": type(exc).__name__}
    # A format or line failure fails the clip whatever the panel says; only a clip that could
    # still pass is an error when the panel could not decide.
    decided_fail = not (checks["format"] and checks["line"])
    undecided = checks["no_text"] is None and not decided_fail
    passed = not decided_fail and not undecided and bool(checks["no_text"] and checks["identity"])
    return {**clip, "delivered": True, **checks, "passed": passed, "error": undecided}


def summarize(endpoint: str, arena_name: str, clips: list[dict], price: dict | None) -> dict:
    judged = [c for c in clips if not c["error"]]
    errors = len(clips) - len(judged)
    passed = sum(c["passed"] for c in judged)
    seconds = [c["seconds_to_video"] for c in clips if "seconds_to_video" in c]
    return {
        "model": arena_name,
        "endpoint": endpoint,
        "score": round(passed / len(judged), 4) if judged else 0.0,
        "clips": len(clips),
        "passed": passed,
        "errors": errors,
        "excluded": errors > MAX_ERRORS,
        "check_passes": {
            name: sum(c.get(name) is True for c in judged) for name in CHECKS
        },
        "refusals": sorted({c["code"] for c in judged if not c.get("delivered", True)}),
        "seconds_to_video_p50": round(statistics.median(seconds), 1) if seconds else None,
        "list_price": price,
        "scored_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "clip_results": [
            {k: c.get(k) for k in ("still_id", "line_id", "passed", "error", "code", *CHECKS, "wer", "transcript")}
            for c in clips
        ],
    }


def list_price(fal_key: str, endpoint: str) -> dict | None:
    try:
        body = json.loads(_retry(lambda: _fetch(
            f"{FAL_API}/models/pricing?endpoint_id={urllib.parse.quote(endpoint, safe='/')}", headers=_fal_headers(fal_key)
        )))
    except (urllib.error.HTTPError, OSError, json.JSONDecodeError):
        return None
    row = next(iter(body.get("prices") or []), None)
    return {k: row.get(k) for k in ("unit_price", "unit", "currency")} if row else None


def score_model(candidate: dict, still_urls: dict[str, str], *, fal_key: str, api_key: str, concurrency: int) -> dict:
    spec = items()
    props = model_inputs(candidate["endpoint"])
    jobs = [(still, line) for still in spec["stills"] for line in spec["lines"]]
    with concurrent.futures.ThreadPoolExecutor(max(1, concurrency)) as pool:
        clips = list(pool.map(
            lambda job: score_clip(candidate["endpoint"], props, job[0], job[1], still_urls[job[0]["id"]], spec["seconds"], fal_key=fal_key, api_key=api_key),
            jobs,
        ))
    return summarize(candidate["endpoint"], candidate["arena_name"], clips, list_price(fal_key, candidate["endpoint"]))


def empty_results() -> dict:
    spec = items()
    return {
        "object": "evalrank_stylised_clip_board",
        "schema_version": "1",
        "harness_version": HARNESS_VERSION,
        "metric": "clip_pass_rate",
        "metric_direction": "higher",
        "prompt_sha256": PROMPT_SHA256,
        "item_set_sha256": item_set_sha256(spec),
        "transcriber": TRANSCRIBER,
        "max_wer": MAX_WER,
        "judges": list(JUDGES),
        "judge_effort": JUDGE_EFFORT,
        "datasets": [{
            "dataset_id": "evalrank-stylised-clip",
            "url": "boards/stylised-clip/items.json",
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
    same = all(current.get(key) == fresh[key] for key in IDENTITY)
    return current if same else fresh  # a changed prompt, item set, harness or panel starts a new board


def merge(results: dict, rows: list[dict]) -> dict:
    by_endpoint = {row["endpoint"]: row for row in results["models"]}
    by_endpoint.update({row["endpoint"]: row for row in rows})
    results["models"] = [by_endpoint[key] for key in sorted(by_endpoint)]
    results["updated_at"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return results


def calibrate(sample: list[dict], *, fal_key: str, api_key: str) -> dict:
    """Run the post-generation checks on labelled local clips and report agreement per check.

    Rows: ``{"video": path, "still": id, "line": id, "line_text": optional override, "labels":
    {check: bool}}``.
    A row without a URL is uploaded first (whisper reads a URL).
    """
    spec = items()
    stills = {s["id"]: s for s in spec["stills"]}
    lines = {line["id"]: line for line in spec["lines"]}
    def _check(row: dict) -> tuple[dict, dict]:
        path = Path(row["video"])
        url = row.get("url") or upload(fal_key, path.read_bytes(), "video/mp4", path.name)
        line = row.get("line_text") or lines[row["line"]]["line"]
        return row, check_clip(path, HERE / stills[row["still"]]["file"], line, url, fal_key=fal_key, api_key=api_key)

    tally: dict[str, dict[str, int]] = {}
    rows = []
    with concurrent.futures.ThreadPoolExecutor(8) as pool:
        for row, got in pool.map(_check, sample):
            for name, want in row["labels"].items():
                t = tally.setdefault(name, {"agree": 0, "disagree": 0, "undecided": 0})
                t["undecided" if got.get(name) is None else ("agree" if got[name] == want else "disagree")] += 1
            rows.append({"video": Path(row["video"]).name, "labels": row["labels"], "got": {k: got.get(k) for k in row["labels"]}, "transcript": got["transcript"], "verdicts": got["verdicts"]})
    return {"per_check": tally, "rows": rows}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--results", type=Path, required=True)
    run.add_argument("--models", default="", help="comma-separated fal endpoints; default: every unscored candidate")
    run.add_argument("--rescore", action="store_true")
    run.add_argument("--max-models", type=int, default=0)
    run.add_argument("--concurrency", type=int, default=8, help="clips in flight per model")
    run.add_argument("--workers", type=int, default=2, help="models scored in parallel")
    cal = sub.add_parser("calibrate")
    cal.add_argument("--sample", type=Path, required=True)
    sub.add_parser("candidates")
    args = parser.parse_args(argv)

    if args.command == "candidates":
        live = {}
        for category in ("image-to-video",):
            body = json.loads(_retry(lambda: _fetch(f"{FAL_API}/models?category={category}&limit=500")))
            live.update({m["endpoint_id"]: (m.get("metadata") or {}).get("status") for m in body.get("models", [])})
        for row in candidates():
            print(f"{row['endpoint']}\t{row['arena_name']}\t{live.get(row['endpoint'], 'not_listed')}")
        return 0

    fal_key = os.environ.get("FAL_API_KEY", "")
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not fal_key or not api_key:
        print("error: FAL_API_KEY and OPENROUTER_API_KEY must both be set", file=sys.stderr)
        return 2
    if args.command == "calibrate":
        sample = [json.loads(line) for line in args.sample.read_text(encoding="utf-8").splitlines() if line.strip()]
        print(json.dumps(calibrate(sample, fal_key=fal_key, api_key=api_key), indent=2))
        return 0

    for still in items()["stills"]:
        if hashlib.sha256((HERE / still["file"]).read_bytes()).hexdigest() != still["sha256"]:
            print(f"error: {still['file']} does not match its pinned sha256", file=sys.stderr)
            return 2
    results = load_results(args.results)
    scored = {row["endpoint"] for row in results["models"] if not row["excluded"]}
    wanted = {name for name in args.models.split(",") if name}
    todo = [c for c in candidates() if (c["endpoint"] in wanted if wanted else True)]
    if not args.rescore:
        todo = [c for c in todo if c["endpoint"] not in scored]
    if args.max_models:
        todo = todo[: args.max_models]
    if not todo:
        print("no candidates to score", file=sys.stderr)
        return 0
    still_urls = {
        s["id"]: upload(fal_key, (HERE / s["file"]).read_bytes(), s["content_type"], Path(s["file"]).name)
        for s in items()["stills"]
    }
    lock = threading.Lock()

    def _one(candidate: dict) -> None:
        try:
            row = score_model(candidate, still_urls, fal_key=fal_key, api_key=api_key, concurrency=args.concurrency)
        except Exception as exc:  # noqa: BLE001 - one model's failure never stops the run
            print(f"{candidate['endpoint']}: failed ({type(exc).__name__}: {exc}); not recorded", file=sys.stderr)
            return
        with lock:
            merge(results, [row])
            tmp = args.results.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            tmp.replace(args.results)
            print(
                f"{row['endpoint']}: score={row['score']} passed={row['passed']}/{row['clips']}"
                f" errors={row['errors']} checks={row['check_passes']} refusals={row['refusals']}",
                file=sys.stderr,
            )

    with concurrent.futures.ThreadPoolExecutor(max(1, args.workers)) as workers:
        list(workers.map(_one, todo))
    print(f"{len(results['models'])} models on the board", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
