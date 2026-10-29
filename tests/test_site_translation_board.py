"""The site-translation board harness: deterministic checks, judge panel, scoring, candidates, items."""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "boards" / "site-translation"
_SPEC = importlib.util.spec_from_file_location("site_translation_harness", BOARD / "harness.py")
harness = importlib.util.module_from_spec(_SPEC)
sys.modules["site_translation_harness"] = harness
_SPEC.loader.exec_module(harness)

NOW = 1_800_000_000
KEEP = ["SPRING15", "@northsideflowers"]


def _model(**overrides):
    model = {
        "id": "vendor/model",
        "created": NOW - 86400,
        "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
        "pricing": {"prompt": "0.0000001", "completion": "0.0000004"},
        "supported_parameters": ["structured_outputs", "response_format", "reasoning"],
        "reasoning": {"mandatory": False, "supported_efforts": ["high", "none"]},
    }
    model.update(overrides)
    return model


class CheckTests(unittest.TestCase):
    def test_localized_values_pass(self):
        self.assertEqual([], harness.check("Sourdough £4.50 from 8am", "Sauerteigbrot 4,50 £ ab 8 Uhr", "de", keep=KEEP))
        self.assertEqual([], harness.check("Only $1,499 today", "今日だけ$1,499", "ja", keep=KEEP))
        self.assertEqual([], harness.check("Call 0161 496 0732", "اتصل على ٠١٦١ ٤٩٦ ٠٧٣٢", "ar", keep=KEEP))

    def test_changed_values_clocks_and_protected_terms_fail(self):
        self.assertIn("money", harness.check("Only £4.50", "Nur 5,40 £", "de", keep=KEEP))
        self.assertIn("number", harness.check("Since 1987", "Desde 1978", "es", keep=KEEP))
        self.assertIn("clock", harness.check("Open 8am", "สั่งก่อน 8am", "th", keep=KEEP))
        self.assertIn("keep", harness.check("Use SPRING15 now", "Utilisez PRINTEMPS15", "fr", keep=KEEP))
        self.assertIn("placeholder", harness.check("Hi {name}", "Hola {nombre}", "es", keep=KEEP))
        self.assertIn("script", harness.check("Open daily", "Открыто ежедневно", "ar", keep=KEEP))
        self.assertIn("identical", harness.check("Free delivery on all orders", "Free delivery on all orders", "fr", keep=KEEP))

    def test_cjk_and_hebrew_particles_never_break_an_email_or_url(self):
        self.assertEqual([], harness.check("Email hello@shop.co.uk", "hello@shop.co.uk로 이메일 주세요", "ko", keep=KEEP))
        self.assertEqual([], harness.check("Email hello@shop.co.uk", "שלחו ל-hello@shop.co.uk", "he", keep=KEEP))
        self.assertEqual([], harness.check("Book at www.shop.com/book", "予約はwww.shop.com/bookから", "ja", keep=KEEP))

    def test_japanese_iteration_marks_and_halfwidth_kana_are_japanese_script(self):
        self.assertEqual([], harness.check("We bake every morning.", "毎朝、様々なパンを焼いています。", "ja", keep=KEEP))
        self.assertEqual([], harness.check("Coffee", "ｺｰﾋｰ", "ja", keep=KEEP))

    def test_english_left_in_a_non_latin_script_fails_but_names_pass(self):
        self.assertEqual([], harness.check("Dale fixed it in the UK", "Dale 在 UK 修好了", "zh", keep=KEEP))
        self.assertIn("english", harness.check("the room was spotless", "the room 很干净", "zh", keep=KEEP))
        self.assertEqual([], harness.check("Follow @northsideflowers", "Подпишитесь на @northsideflowers", "ru", keep=KEEP))


class PanelTests(unittest.TestCase):
    def test_the_panel_is_the_median_and_needs_two_judges(self):
        self.assertEqual(0.75, harness.panel([{"s1": 1.0}, {"s1": 0.75}, {"s1": 0.0}], "s1"))
        self.assertEqual(0.625, harness.panel([{"s1": 1.0}, {"s1": 0.25}, {}], "s1"))
        self.assertIsNone(harness.panel([{"s1": 1.0}, {}, {}], "s1"))


class ScoreTests(unittest.TestCase):
    def _segments(self):
        return [harness.Segment("own", "a", "Open from 8am"), harness.Segment("wmt24pp", "1", "Holding prices")]

    def test_a_failed_check_scores_zero_and_judges_set_the_rest(self):
        got = {"s1": ["Geöffnet ab 8am"], "s2": ["Preise halten"]}
        rows = harness.score_language(self._segments(), "de", got, [{"s2": 1.0}, {"s2": 0.75}, {"s2": 0.75}], KEEP)
        self.assertEqual([0.0, 0.75], [row["score"] for row in rows])
        self.assertEqual(["clock"], rows[0]["codes"])

    def test_a_missing_or_duplicated_id_scores_zero_and_a_failed_call_is_an_error(self):
        rows = harness.score_language(self._segments(), "de", {"s2": ["a", "b"]}, [], KEEP)
        self.assertEqual([["id"], ["id"]], [row["codes"] for row in rows])
        rows = harness.score_language(self._segments(), "de", None, [], KEEP)
        self.assertEqual(["call", "call"], [row["error"] for row in rows])

    def test_errors_over_the_ceiling_exclude_the_row(self):
        ok = [{"source": "own", "segment_id": "a", "score": 1.0}] * 19
        row = harness.summarize({"de": ok + [{"source": "own", "segment_id": "b", "error": "call"}]})
        self.assertFalse(row["excluded"])  # exactly 5%
        self.assertEqual(1.0, row["score"])
        row = harness.summarize({"de": ok[:9] + [{"source": "own", "segment_id": "b", "error": "unjudged"}]})
        self.assertTrue(row["excluded"])


class UnavailableTests(unittest.TestCase):
    def test_an_unavailable_model_is_a_recorded_excluded_row_not_a_crash(self):
        def unavailable(_key, _body):
            raise harness.Unavailable

        original = harness.complete
        harness.complete = unavailable
        try:
            segments = [harness.Segment("own", "a", "Open daily")]
            row = harness.score_model(_model(), segments, KEEP, [_model(id="j/1")], "key", concurrency=2)
        finally:
            harness.complete = original
        self.assertEqual("unavailable", row["mode"])
        self.assertTrue(row["excluded"])
        self.assertEqual(len(harness.LANGUAGES), row["errors"])


class JudgeTests(unittest.TestCase):
    def test_a_judge_reply_off_schema_is_no_verdicts_not_a_crash(self):
        original = harness.complete
        try:
            for reply in ([1, 2], "no", 3, {"verdicts": "x"}, {"verdicts": [{"id": [1], "verdict": "minor"}]}):
                harness.complete = lambda _key, _body, reply=reply: reply
                with self.subTest(reply=reply):
                    self.assertEqual({}, harness.judge("key", _model(), "de", [("s1", "a", "b")]))
        finally:
            harness.complete = original


class CandidateTests(unittest.TestCase):
    def test_the_rule_admits_a_cheap_recent_strict_schema_model_that_can_skip_reasoning(self):
        self.assertTrue(harness.is_candidate(_model(), now=NOW))
        self.assertTrue(harness.is_candidate(_model(reasoning=None), now=NOW))

    def test_the_rule_rejects_mandatory_reasoning_aliases_and_out_of_policy_models(self):
        for model in (
            _model(reasoning={"mandatory": True}),
            _model(reasoning={"mandatory": False, "supported_efforts": ["high", "low"]}),
            _model(id="vendor/model:free"),
            _model(id="~vendor/model-latest"),
            _model(pricing={"prompt": "0.000003", "completion": "0.000004"}),
            _model(supported_parameters=["response_format"]),
            _model(created=NOW - 400 * 86400),
        ):
            with self.subTest(model=model):
                self.assertFalse(harness.is_candidate(model, now=NOW))

    def test_no_judge_is_ever_a_candidate(self):
        self.assertEqual(3, len({judge.split("/")[0] for judge in harness.JUDGES}))


class ItemTests(unittest.TestCase):
    def test_the_item_set_digest_tracks_text_languages_and_protected_terms(self):
        items = [harness.Segment("own", "a", "x")]
        digest = harness.item_set_sha256(items, ["de"], KEEP)
        self.assertNotEqual(digest, harness.item_set_sha256([harness.Segment("own", "a", "y")], ["de"], KEEP))
        self.assertNotEqual(digest, harness.item_set_sha256(items, ["fr"], KEEP))
        self.assertNotEqual(digest, harness.item_set_sha256(items, ["de"], ["SPRING15"]))

    def test_the_wmt_slice_is_the_pinned_segment_ids(self):
        rows = [{"segment_id": i, "is_bad_source": False, "source": f"text {i}"} for i in range(500)]
        picked = harness.wmt_segments("\n".join(json.dumps(row) for row in rows).encode())
        self.assertEqual([str(i) for i in harness.WMT24PP_SEGMENTS], [s.segment_id for s in picked])

    def test_own_items_are_forty_with_the_wmt_slice_in_fifteen_languages(self):
        own = harness.own_items()
        self.assertEqual(30, len(own["segments"]))
        self.assertEqual(10, len(harness.WMT24PP_SEGMENTS))
        self.assertEqual(15, len(harness.LANGUAGES))
        self.assertTrue({"ar", "he", "hi", "th"} <= set(harness.LANGUAGES))
        for segment in own["segments"]:
            with self.subTest(segment=segment["id"]):
                self.assertIn("identical", harness.check(segment["text"], segment["text"], "fr", keep=own["keep"]))


class ResultsTests(unittest.TestCase):
    def test_the_committed_board_matches_the_harness_identity(self):
        results = json.loads((BOARD / "results.json").read_text(encoding="utf-8"))
        self.assertEqual("evalrank_site_translation_board", results["object"])
        self.assertEqual(harness.PROMPT_SHA256, results["prompt_sha256"])
        self.assertEqual(harness.HARNESS_VERSION, results["harness_version"])
        self.assertEqual(list(harness.JUDGES), results["judges"])
        self.assertEqual(list(harness.LANGUAGES), results["languages"])
        self.assertEqual(harness.WMT24PP["sha256"], results["datasets"][1]["sha256"])
        self.assertEqual(sorted(row["model"] for row in results["models"]), [row["model"] for row in results["models"]])
        for row in results["models"]:
            with self.subTest(model=row["model"]):
                self.assertTrue(0 <= row["score"] <= 1)
                self.assertEqual(row["error_rate"] > harness.MAX_ERROR_RATE, row["excluded"])
        # WMT24++ text is never republished.
        self.assertNotIn("Greggs", (BOARD / "results.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
