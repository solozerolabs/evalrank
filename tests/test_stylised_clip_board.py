"""The stylised-clip board harness: input shaping, checks, panel, scoring, items and the board file."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "boards" / "stylised-clip"
_SPEC = importlib.util.spec_from_file_location("stylised_clip_harness", BOARD / "harness.py")
harness = importlib.util.module_from_spec(_SPEC)
sys.modules["stylised_clip_harness"] = harness
_SPEC.loader.exec_module(harness)

URL = "https://v3b.fal.media/files/still.png"


class FalInputTests(unittest.TestCase):
    def test_gemini_omni_takes_vertical_1080p_and_an_integer_duration(self):
        props = {
            "image_url": {"type": "string"},
            "aspect_ratio": {"enum": ["16:9", "9:16"]},
            "resolution": {"enum": ["360p", "720p", "1080p", "4k"]},
            "duration": {"type": "integer"},
        }
        self.assertEqual(
            {"image_url": URL, "aspect_ratio": "9:16", "resolution": "1080p", "duration": 5},
            harness.fal_inputs(props, 5, URL),
        )

    def test_an_enum_duration_rounds_up_so_a_clip_never_ends_early(self):
        props = {"image_url": {}, "duration": {"enum": ["5", "10", "15"]}, "generate_audio": {"type": "boolean"}}
        self.assertEqual({"image_url": URL, "duration": "10", "generate_audio": True}, harness.fal_inputs(props, 6, URL))
        self.assertEqual("5", harness.fal_inputs(props, 5, URL)["duration"])
        self.assertEqual("15", harness.fal_inputs(props, 20, URL)["duration"])

    def test_a_start_image_model_with_adaptive_aspect_and_an_audio_flag(self):
        props = {
            "start_image_url": {},
            "aspect_ratio": {"enum": ["adaptive", "16:9", "4:3"]},
            "resolution": {"enum": ["480p", "720p"]},
            "duration": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
            "audio": {"type": "boolean"},
        }
        self.assertEqual(
            {"start_image_url": URL, "aspect_ratio": "adaptive", "resolution": "720p", "duration": 5, "audio": True},
            harness.fal_inputs(props, 5, URL),
        )

    def test_no_still_input_or_no_vertical_frame_is_refused(self):
        with self.assertRaisesRegex(harness.Refused, "no_image_input"):
            harness.fal_inputs({"prompt": {}}, 5, URL)
        with self.assertRaisesRegex(harness.Refused, "no_vertical"):
            harness.fal_inputs({"image_url": {}, "aspect_ratio": {"enum": ["16:9", "1:1"]}}, 5, URL)


class CheckTests(unittest.TestCase):
    def test_word_error_rate_ignores_case_and_punctuation(self):
        self.assertEqual(0.0, harness.wer("Wait. It wrote the tests too?", " wait, it wrote the tests, too"))
        self.assertAlmostEqual(1 / 6, harness.wer("Wait. It wrote the tests too?", "Wait, it wrote the test too?"))
        self.assertEqual(1.0, harness.wer("Three customers", ""))
        self.assertLessEqual(harness.wer("Three customers signed up while I was asleep!", "Three customers signed up up while I was asleep"), harness.MAX_WER)

    def test_format_needs_portrait_audio_and_length(self):
        good = {"width": 1080, "height": 1920, "audio": True, "seconds": 5.0}
        self.assertTrue(harness.format_ok(good))
        self.assertFalse(harness.format_ok({**good, "audio": False}))
        self.assertFalse(harness.format_ok({**good, "width": 1920, "height": 1080}))
        self.assertFalse(harness.format_ok({**good, "seconds": 3.0}))

    def test_panel_is_a_majority_of_the_judges_that_answered(self):
        text = {"on_screen_text": True, "identity": "same", "notes": ""}
        clean = {"on_screen_text": False, "identity": "same", "notes": ""}
        changed = {"on_screen_text": False, "identity": "changed", "notes": ""}
        self.assertEqual({"no_text": False, "identity": True}, harness.panel([text, text, clean]))
        self.assertEqual({"no_text": True, "identity": False}, harness.panel([changed, changed, None]))
        self.assertIsNone(harness.panel([clean, None, None]))


def _clip(passed=True, *, delivered=True, error=False, code=None):
    clip = {"still_id": "felt", "line_id": "calm", "passed": passed, "error": error, "delivered": delivered}
    if delivered and not error:
        clip.update(format=True, line=True, no_text=passed, identity=True, wer=0.0, transcript="x", seconds_to_video=40.0)
    if code:
        clip["code"] = code
    return clip


class ScoringTests(unittest.TestCase):
    def test_a_refusal_is_a_failed_clip_not_an_error(self):
        clips = [_clip()] * 6 + [_clip(False, delivered=False, code="http_422:content_policy_violation")] * 2
        row = harness.summarize("vendor/model/image-to-video", "Model 1", clips, None)
        self.assertEqual(0.75, row["score"])
        self.assertEqual(["http_422:content_policy_violation"], row["refusals"])
        self.assertEqual(6, row["check_passes"]["delivered"])
        self.assertEqual(6, row["check_passes"]["line"])
        self.assertFalse(row["excluded"])

    def test_more_than_one_unjudged_clip_excludes_the_row(self):
        clips = [_clip()] * 6 + [_clip(False, error=True, code="URLError")] * 2
        row = harness.summarize("vendor/model/image-to-video", "Model 1", clips, None)
        self.assertTrue(row["excluded"])
        self.assertEqual(1.0, row["score"])

    def test_a_changed_prompt_or_item_set_starts_a_new_board(self):
        path = BOARD / "results.json"
        current = json.loads(path.read_text(encoding="utf-8"))
        fresh = harness.empty_results()
        for key in harness.IDENTITY:
            self.assertEqual(fresh[key], current[key], key)


class ItemTests(unittest.TestCase):
    def test_stills_match_their_pinned_digests(self):
        for still in harness.items()["stills"]:
            self.assertEqual(still["sha256"], hashlib.sha256((BOARD / still["file"]).read_bytes()).hexdigest())



DISCOVERY = json.loads((ROOT / "tests" / "fixtures" / "stylised_clip_discovery.json").read_text(encoding="utf-8"))
#: The hand-reviewed name map this matcher replaced (2026-11-14): every pair must still join.
REVIEWED = {
    "Gemini Omni 1.2 Flash": "google/gemini-omni-flash/v1.2/image-to-video",
    "MiniMax H3": "minimax/h3/image-to-video",
    "Dreamina Seedance 2.5 (720p)": "bytedance/seedance-2.5/us/image-to-video",
    "Gemini Omni 1.1 Flash": "google/gemini-omni-flash/v1.1/image-to-video",
    "Wan 3.0": "alibaba/wan-3.0/image-to-video",
    "Dreamina Seedance 2.0 (720p)": "bytedance/seedance-2.0/us/image-to-video",
    "gemini-omni-flash": "google/gemini-omni-flash/image-to-video",
    "Grok Imagine Video 1.5 (720p)": "xai/grok-imagine-video/v1.5/image-to-video",
    "FLUX 3 Video (20260811)": "blackforestlabs/flux-3/image-to-video",
    "HappyHorse 1.0": "alibaba/happy-horse/image-to-video",
    "Wan 2.7": "fal-ai/wan/v2.7/image-to-video",
    "Grok Imagine Video (720p)": "xai/grok-imagine-video/image-to-video",
    "Vidu Q3 Pro": "fal-ai/vidu/q3/image-to-video",
    "Kling 3.0 Pro": "fal-ai/kling-video/v3/pro/image-to-video",
    "Wan 2.6": "wan/v2.6/image-to-video",
    "PixVerse V5.6": "fal-ai/pixverse/v5.6/image-to-video",
    "Hailuo 2.3": "fal-ai/minimax/hailuo-2.3/pro/image-to-video",
}


class DiscoveryTests(unittest.TestCase):
    def _match(self, name):
        org = next(r["organization"] for r in DISCOVERY["arena"] if r["model_name"] == name)
        return harness.match_endpoint(name, org, DISCOVERY["fal"])

    def test_every_reviewed_pair_joins(self):
        for name, endpoint in REVIEWED.items():
            self.assertEqual(endpoint, self._match(name), name)

    def test_lookalikes_do_not_join(self):
        # Each was a wrong join in the prototype: one model would take another's arena rank.
        for name in ("SkyReels V4", "Veo 3", "Veo 3 (Audio)", "Veo 2", "Seedance 1.5 Pro", "Seedance 1.0 Lite", "HunyuanVideo 1.5", "P-Video"):
            self.assertIsNone(self._match(name), name)

    def test_join_is_best_ranked_first_and_one_name_per_endpoint(self):
        rows = harness.join(DISCOVERY["arena"], DISCOVERY["fal"])
        self.assertEqual([r["arena_rank"] for r in rows], sorted(r["arena_rank"] for r in rows))
        self.assertEqual(len(rows), len({r["endpoint"] for r in rows}))
        grok = [r["arena_name"] for r in rows if r["endpoint"] == "xai/grok-imagine-video/image-to-video"]
        self.assertEqual(["Grok Imagine Video (720p)"], grok)


class PriceTests(unittest.TestCase):
    CANDIDATES = [{"endpoint": e, "arena_name": e, "arena_rank": r} for r, e in enumerate(("top", "pick", "low", "fail"), 1)]

    def _results(self, billing=None):
        row = lambda e, score: {"endpoint": e, "excluded": False, "score": score, "billing": billing}
        return {"models": [row("pick", 0.875), row("low", 1.0), row("fail", 0.5)]}

    def test_a_scheduled_run_scores_only_models_above_the_best_passer(self):
        todo = harness.pick(self._results(), self.CANDIDATES, set(), rescore=False, above_best=True)
        self.assertEqual(["top"], [c["endpoint"] for c in todo])

    def test_billing_is_the_board_key_window_over_delivered_seconds(self):
        bill = harness.billing("fal_sk_board:secret", "2026-11-14T19:00:00Z", [
            {"delivered": True, "video_seconds": 5.04}, {"delivered": False, "video_seconds": 5}, {"delivered": True, "video_seconds": 4.96},
        ])
        self.assertEqual("fal_sk_board", bill["key_id"])
        self.assertEqual(10.0, bill["video_seconds"])
        self.assertLess(bill["started_at"], bill["finished_at"])

    def test_prices_are_due_when_missing_from_another_key_or_old(self):
        from datetime import UTC, datetime
        now = datetime(2026, 12, 30, tzinfo=UTC)
        fresh = {"key_id": "board", "finished_at": "2026-12-20T00:00:00Z"}
        self.assertEqual(["pick", "low"], [r["endpoint"] for r in harness.due_for_price(self._results(), self.CANDIDATES, "board", now=now)])
        self.assertEqual([], harness.due_for_price(self._results(fresh), self.CANDIDATES, "board", now=now))
        self.assertEqual(2, len(harness.due_for_price(self._results(fresh), self.CANDIDATES, "other", now=now)))
        self.assertEqual(2, len(harness.due_for_price(self._results({**fresh, "finished_at": "2026-11-01T00:00:00Z"}), self.CANDIDATES, "board", now=now)))


class PickTests(unittest.TestCase):
    CANDIDATES = [{"endpoint": e, "arena_name": e} for e in ("new", "good", "flaky", "stuck")]
    RESULTS = {"models": [
        {"endpoint": "good", "excluded": False},
        {"endpoint": "flaky", "excluded": True, "attempts": 2},
        {"endpoint": "stuck", "excluded": True, "attempts": 3},
    ]}

    def _pick(self, **kwargs):
        return [c["endpoint"] for c in harness.pick(self.RESULTS, self.CANDIDATES, set(), **kwargs)]

    def test_a_weekly_run_scores_only_new_and_retryable_models(self):
        self.assertEqual(["new", "flaky"], self._pick(rescore=False))

    def test_naming_a_model_or_rescore_spends_on_purpose(self):
        self.assertEqual(["stuck"], [c["endpoint"] for c in harness.pick(self.RESULTS, self.CANDIDATES, {"stuck"}, rescore=False)])
        self.assertEqual(4, len(self._pick(rescore=True)))

    def test_attempts_count_only_consecutive_exclusions(self):
        self.assertEqual(3, harness.attempts(self.RESULTS, {"endpoint": "flaky"}))
        self.assertEqual(1, harness.attempts(self.RESULTS, {"endpoint": "good"}))
        self.assertEqual(1, harness.attempts(self.RESULTS, {"endpoint": "new"}))


class BoardFileTests(unittest.TestCase):
    def test_every_row_is_consistent_with_its_clips(self):
        board = json.loads((BOARD / "results.json").read_text(encoding="utf-8"))
        self.assertEqual("evalrank_stylised_clip_board", board["object"])
        self.assertEqual("clip_pass_rate", board["metric"])
        for row in board["models"]:
            if row["endpoint"] in REVIEWED.values():
                self.assertIn(row["model"], REVIEWED)
            judged = [c for c in row["clip_results"] if not c["error"]]
            self.assertEqual(row["passed"], sum(c["passed"] for c in judged))
            self.assertEqual(row["score"], round(row["passed"] / len(judged), 4) if judged else 0.0)
            self.assertEqual(row["excluded"], row["errors"] > harness.MAX_ERRORS)
            self.assertTrue(0.0 <= row["score"] <= 1.0)


def _http_error(code, detail):
    import io
    import urllib.error

    body = json.dumps({"detail": detail}).encode()
    return urllib.error.HTTPError("https://queue.fal.run/x", code, "err", {}, io.BytesIO(body))


class FalRunTests(unittest.TestCase):
    def _run_with(self, error):
        original = harness._fetch

        def boom(url, **_kwargs):
            raise error

        harness._fetch = boom
        try:
            return harness.fal_run("key", "vendor/model", {"prompt": "x"})
        finally:
            harness._fetch = original

    def test_content_policy_and_could_not_generate_are_the_models_refusals(self):
        with self.assertRaisesRegex(harness.Refused, "content_policy_violation"):
            self._run_with(_http_error(422, [{"type": "content_policy_violation", "msg": "likeness"}]))
        with self.assertRaisesRegex(harness.Refused, "invalid_request"):
            self._run_with(_http_error(422, [{"type": "invalid_request", "msg": "Could not generate a video with the given inputs."}]))

    def test_our_own_failures_are_errors_never_a_published_fail(self):
        import urllib.error

        for error in (
            _http_error(403, "User is locked. Reason: Exhausted balance."),
            _http_error(401, "bad key"),
            _http_error(422, [{"type": "literal_error", "loc": ["body", "aspect_ratio"]}]),
        ):
            with self.assertRaises(urllib.error.HTTPError):
                self._run_with(error)

    def test_schema_refs_resolve_and_the_request_schema_takes_a_prompt(self):
        doc = {"components": {"schemas": {
            "LoraInput": {"properties": {"path": {}}},
            "VideoInput": {"properties": {
                "prompt": {}, "image_url": {},
                "aspect_ratio": {"allOf": [{"$ref": "#/components/schemas/Aspect"}], "default": "16:9"},
            }},
            "Aspect": {"enum": ["16:9", "9:16"]},
        }}}
        props = harness.resolve_props(doc)
        self.assertEqual(["16:9", "9:16"], props["aspect_ratio"]["enum"])
        self.assertEqual("9:16", harness.fal_inputs(props, 5, URL)["aspect_ratio"])


class ClipTests(unittest.TestCase):
    def test_a_line_failure_fails_the_clip_even_when_the_panel_cannot_decide(self):
        original_run, original_fetch, original_check = harness.fal_run, harness._fetch, harness.check_clip
        harness.fal_run = lambda *a, **k: {"video": {"url": "https://v3b.fal.media/c.mp4"}}
        harness._fetch = lambda *a, **k: b"mp4"
        base = {"format": True, "line": False, "no_text": None, "identity": None, "transcript": "", "wer": 1.0, "judges_answered": 0, "verdicts": [], "probe": {}}
        harness.check_clip = lambda *a, **k: dict(base)
        still = harness.items()["stills"][0]
        line = harness.items()["lines"][0]
        props = {"image_url": {}, "duration": {"type": "integer"}}
        try:
            clip = harness.score_clip("vendor/model", props, still, line, URL, 5, fal_key="k", api_key="k")
            self.assertFalse(clip["passed"])
            self.assertFalse(clip["error"])
            base["line"] = True
            clip = harness.score_clip("vendor/model", props, still, line, URL, 5, fal_key="k", api_key="k")
            self.assertTrue(clip["error"])
        finally:
            harness.fal_run, harness._fetch, harness.check_clip = original_run, original_fetch, original_check


if __name__ == "__main__":
    unittest.main()
