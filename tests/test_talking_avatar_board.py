"""The talking-avatar board harness: discovery, input shaping, frame labels, panel, scoring, items."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "boards" / "talking-avatar"
_SPEC = importlib.util.spec_from_file_location("talking_avatar_harness", BOARD / "harness.py")
harness = importlib.util.module_from_spec(_SPEC)
sys.modules["talking_avatar_harness"] = harness
_SPEC.loader.exec_module(harness)

IMG, AUD = "https://fal.media/still.png", "https://fal.media/line.mp3"


class DiscoveryTests(unittest.TestCase):
    def test_a_still_and_one_audio_file_make_a_candidate(self):
        self.assertTrue(harness.takes_still_and_audio({"image_url": {"type": "string"}, "audio_url": {}}))
        self.assertTrue(harness.takes_still_and_audio({"image_url": {}, "target_audio_url": {"type": "string"}}))

    def test_reference_lists_or_a_missing_input_are_not_candidates(self):
        self.assertFalse(harness.takes_still_and_audio({"image_url": {}, "audio_url": {"type": "array"}}))
        self.assertFalse(harness.takes_still_and_audio({"image_urls": {}, "audio_url": {}}))
        self.assertFalse(harness.takes_still_and_audio({"image_url": {}, "generate_audio": {"type": "boolean"}}))

    def test_the_request_schema_need_not_take_a_prompt(self):
        doc = {"components": {"schemas": {
            "LoraInput": {"properties": {"path": {}}},
            "FabricInput": {"properties": {"image_url": {}, "audio_url": {}, "resolution": {"$ref": "#/components/schemas/Res"}}},
            "Res": {"enum": ["720p", "480p"]},
        }}}
        props = harness.request_props(doc)
        self.assertEqual({"image_url", "audio_url", "resolution"}, set(props))
        self.assertEqual(["720p", "480p"], props["resolution"]["enum"])


class InputTests(unittest.TestCase):
    def test_a_prompted_avatar_gets_the_direction_vertical_frame_and_captions_off(self):
        props = {"image_url": {}, "audio_url": {}, "prompt": {}, "aspect_ratio": {"enum": ["16:9", "9:16"]}, "caption": {"type": "boolean"}}
        out = harness.avatar_inputs(props, 6.8, IMG, AUD)
        self.assertEqual("9:16", out["aspect_ratio"])
        self.assertIs(False, out["caption"])
        self.assertTrue(out["prompt"].startswith(harness.DIRECTION))

    def test_a_duration_covers_the_whole_line(self):
        out = harness.avatar_inputs({"image_url": {}, "audio_url": {}, "duration": {"enum": ["5", "10"]}}, 6.8, IMG, AUD)
        self.assertEqual("10", out["duration"])
        self.assertEqual(7, harness.avatar_inputs({"image_url": {}, "target_audio_url": {}, "duration": {"type": "integer"}}, 6.8, IMG, AUD)["duration"])

    def test_resolution_is_the_highest_line_count_up_to_1080_in_any_case(self):
        self.assertEqual("1080P", harness.resolution(["480P", "768P", "1080P", "2K"]))
        self.assertEqual("768P", harness.resolution(["480P", "768P", "2K", "4K"]))
        self.assertEqual("4k", harness.resolution(["4k"]))

    def test_no_audio_input_is_refused(self):
        with self.assertRaisesRegex(harness.Refused, "no_still_and_audio_input"):
            harness.avatar_inputs({"image_url": {}}, 5, IMG, AUD)


class CheckTests(unittest.TestCase):
    def test_frames_are_labelled_speaking_or_silent_from_the_lines_spans(self):
        labels = harness.frame_labels(1.0, [[0.0, 0.3], [0.7, 1.0]])
        self.assertEqual(["t=0.12s speaking", "t=0.38s silent", "t=0.62s silent", "t=0.88s speaking"], labels)

    def test_panel_is_a_majority_with_the_median_quality(self):
        v = lambda lips, q, text=False, ident="same": {"on_screen_text": text, "identity": ident, "lips": lips, "quality": q}  # noqa: E731
        self.assertEqual({"no_text": True, "identity": True, "lips": True, "quality": 4}, harness.panel([v("synced", 4), v("synced", 5), v("frozen", 2)]))
        self.assertFalse(harness.panel([v("frozen", 2), v("off", 1), v("synced", 4)])["lips"])
        self.assertIsNone(harness.panel([v("synced", 4), None, None]))

    def test_a_short_or_silent_or_landscape_clip_fails_format(self):
        ok = {"width": 720, "height": 1280, "audio": True, "seconds": 6.7}
        self.assertTrue(harness.format_ok(ok, 6.8))
        self.assertFalse(harness.format_ok({**ok, "seconds": 5.0}, 6.8))
        self.assertFalse(harness.format_ok({**ok, "audio": False}, 6.8))
        self.assertFalse(harness.format_ok({**ok, "width": 1280, "height": 720}, 6.8))

    def test_a_line_failure_fails_the_clip_even_when_the_panel_cannot_decide(self):
        self.assertEqual((False, False), harness.verdict({"format": True, "line": False, "no_text": None}))
        self.assertEqual((False, True), harness.verdict({"format": True, "line": True, "no_text": None}))
        self.assertEqual((True, False), harness.verdict({"format": True, "line": True, "no_text": True, "identity": True, "lips": True}))
        self.assertEqual((False, False), harness.verdict({"format": True, "line": True, "no_text": True, "identity": True, "lips": False}))


class RowTests(unittest.TestCase):
    def _clip(self, passed, quality=5, error=False):
        return {"still_id": "felt", "line_id": "calm", "passed": passed, "error": error, "delivered": True, "quality": quality, "seconds_to_video": 30.0}

    def test_the_score_weights_passing_clips_by_quality_and_failing_ones_at_zero(self):
        clips = [self._clip(True, 5)] * 6 + [self._clip(True, 3), self._clip(False, 4)]
        row = harness.summarize({"endpoint": "veed/fabric-1.0", "name": "Fabric 1.0"}, clips, None)
        self.assertEqual(0.875, row["pass_rate"])
        self.assertEqual(round((6 + 0.6) / 8, 4), row["score"])
        self.assertLessEqual(row["score"], row["pass_rate"])

    def test_more_than_one_unjudged_clip_excludes_the_row(self):
        clips = [self._clip(True)] * 6 + [self._clip(False, error=True)] * 2
        self.assertTrue(harness.summarize({"endpoint": "a/b", "name": "A"}, clips, None)["excluded"])

    def test_passers_rank_by_score_and_need_seven_of_eight(self):
        rows = [
            {"endpoint": "a/x", "score": 0.6, "pass_rate": 1.0, "excluded": False},
            {"endpoint": "b/x", "score": 0.8, "pass_rate": 0.875, "excluded": False},
            {"endpoint": "c/x", "score": 0.7, "pass_rate": 0.75, "excluded": False},
            {"endpoint": "d/x", "score": 0.9, "pass_rate": 1.0, "excluded": False},  # no longer on fal
        ]
        found = [{"endpoint": e} for e in ("a/x", "b/x", "c/x")]
        self.assertEqual(["b/x", "a/x"], [r["endpoint"] for r in harness.passers({"models": rows}, found)])

    def test_a_weekly_run_scores_only_new_and_retryable_endpoints(self):
        results = {"models": [{"endpoint": "a/x", "excluded": False}, {"endpoint": "b/x", "excluded": True, "attempts": 1}, {"endpoint": "c/x", "excluded": True, "attempts": 3}]}
        found = [{"endpoint": e} for e in ("a/x", "b/x", "c/x", "d/x")]
        self.assertEqual(["b/x", "d/x"], [c["endpoint"] for c in harness.pick(results, found, set(), rescore=False)])
        self.assertEqual(["a/x"], [c["endpoint"] for c in harness.pick(results, found, {"a/x"}, rescore=False)])

    def test_prices_are_due_when_missing_from_another_key_or_old(self):
        bill = lambda key, at: {"key_id": key, "started_at": at, "finished_at": at, "video_seconds": 40}  # noqa: E731
        row = lambda e, b: {"endpoint": e, "score": 0.8, "pass_rate": 1.0, "excluded": False, **({"billing": b} if b else {})}  # noqa: E731
        results = {"models": [row("a/x", None), row("b/x", bill("fal_sk_other", "2026-11-14T00:00:00Z")), row("c/x", bill("fal_sk_board", "2026-09-01T00:00:00Z")), row("d/x", bill("fal_sk_board", "2026-11-10T00:00:00Z"))]}
        found = [{"endpoint": e} for e in ("a/x", "b/x", "c/x", "d/x")]
        due = harness.due_for_price(results, found, "fal_sk_board", now=datetime(2026, 11, 14, tzinfo=UTC))
        self.assertEqual(["a/x", "b/x", "c/x"], sorted(r["endpoint"] for r in due))

    def test_a_changed_prompt_or_item_set_starts_a_new_board(self):
        fresh = harness.empty_results()
        self.assertEqual(fresh["prompt_sha256"], harness.PROMPT_SHA256)
        self.assertEqual("avatar_score", fresh["metric"])


class ItemTests(unittest.TestCase):
    def test_stills_and_lines_match_their_pinned_digests(self):
        self.assertIsNone(harness._verify_items())

    def test_speech_spans_sit_inside_each_line(self):
        for line in harness.items()["lines"]:
            spans = line["speech"]
            self.assertTrue(all(0 <= a < b <= line["seconds"] for a, b in spans), line["id"])
            self.assertEqual(spans, sorted(spans))

    def test_the_published_board_is_consistent_with_its_clips(self):
        path = BOARD / "results.json"
        if not path.exists():
            self.skipTest("no board yet")
        board = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(hashlib.sha256((BOARD / "items.json").read_bytes()).hexdigest(), board["datasets"][0]["sha256"])
        for row in board["models"]:
            judged = [c for c in row["clip_results"] if not c["error"]]
            self.assertEqual(row["passed"], sum(c["passed"] for c in judged), row["endpoint"])
            self.assertEqual(row["excluded"], row["errors"] > harness.MAX_ERRORS, row["endpoint"])
            if judged:
                self.assertAlmostEqual(row["pass_rate"], row["passed"] / len(judged), places=4)
                self.assertLessEqual(row["score"], row["pass_rate"])


if __name__ == "__main__":
    unittest.main()
