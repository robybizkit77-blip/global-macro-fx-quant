from copy import deepcopy
from datetime import date, datetime
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from validation.forward import macro_challenger_common_yields_v1 as study
from validation.forward import macro_challenger_v1 as base
from validation.forward import test_macro_challenger_v1 as fixtures


def curve(start, end, levels):
    rates = fixtures.curve(levels[end], round((levels[end] - levels[start]) * 100, 2), start, end)
    rates["history2"] = {"dates": sorted(levels), "values": [levels[d] for d in sorted(levels)]}
    return rates


class CommonYieldsTests(unittest.TestCase):
    def test_uses_same_real_quotes_with_different_latest_dates(self):
        eur = curve("2026-11-11", "2026-11-18",
                    {"2026-11-11": 3.04, "2026-11-12": 3.05, "2026-11-18": 3.08})
        usd = curve("2026-11-12", "2026-11-19",
                    {"2026-11-12": 4.86, "2026-11-18": 4.80, "2026-11-19": 4.76})
        left, right = (study.approved_history(row, fixtures.DAY) for row in (eur, usd))
        self.assertEqual(study.matched_window(left, right),
                         (date(2026, 11, 12), date(2026, 11, 18), 9.0))
        self.assertEqual(study.matched_window(right, left)[-1], -9.0)

    def test_rejects_stale_or_disagreeing_weekly_anchor(self):
        sample = curve("2026-10-07", "2026-10-14", {"2026-10-07": 0.3, "2026-10-14": 0.4})
        self.assertEqual(study.approved_history(sample, fixtures.DAY), {})
        sample = curve("2026-11-12", "2026-11-19", {"2026-11-12": 4.9, "2026-11-19": 4.8})
        sample["history2"]["values"][0] = 4.85
        self.assertEqual(study.approved_history(sample, fixtures.DAY), {})

    def test_validation_is_local_to_the_certified_window(self):
        sample = curve("2026-11-12", "2026-11-19", {"2026-11-12": 4.9, "2026-11-19": 4.8})
        sample["history2"]["dates"].insert(0, "2026-8-7")
        sample["history2"]["values"].insert(0, 4.85)
        self.assertEqual(len(study.approved_history(sample, fixtures.DAY)), 2)
        sample["history2"]["dates"].append("2026-11-19")
        sample["history2"]["values"].append(4.8)
        self.assertEqual(study.approved_history(sample, fixtures.DAY), {})

    def test_start_prefers_seven_days_and_never_look_back_past_certified_range(self):
        end = date(2026, 11, 19)
        x = {date(2026, 11, 11): 1, date(2026, 11, 12): 2, date(2026, 11, 13): 3, end: 4}
        self.assertEqual(study.matched_window(x, x)[0], date(2026, 11, 12))
        self.assertIsNone(study.matched_window(x, {date(2026, 11, 11): 1, date(2026, 11, 13): 3}))
        self.assertIsNone(study.matched_window(x, {end: 4}))

    def test_variant_has_distinct_fingerprint_preserves_original_and_reuses_macro(self):
        inputs = fixtures.fixture()
        inputs["rates"] = {
            "EUR": curve("2026-11-11", "2026-11-18",
                         {"2026-11-11": 3.08, "2026-11-12": 3.09, "2026-11-18": 3.00}),
            "USD": curve("2026-11-12", "2026-11-19",
                         {"2026-11-12": 4.8, "2026-11-18": 4.8, "2026-11-19": 4.75}),
        }
        baseline = base.build(inputs, {}, fixtures.NOW, "a" * 40)
        unchanged = deepcopy(baseline)
        variant = study.build(baseline, inputs["rates"], fixtures.DAY)
        self.assertEqual(unchanged, baseline)
        self.assertNotEqual(variant["formula_sha256"], baseline["formula_sha256"])
        self.assertEqual(variant["base_formula_sha256"], baseline["formula_sha256"])
        fx = variant["pairs"]["EUR/USD"]
        self.assertEqual((fx["baseline_candidate"], fx["candidate"], fx["rates_contradicted"]), (1, 0, True))
        expected = sum(bool(row["candidate"] and row["baseline_candidate"]) for row in variant["pairs"].values())
        with TemporaryDirectory() as temp:
            root = Path(temp)
            prices = root / "prices.json"
            prices.write_text(json.dumps(fixtures.fx(date(2026, 12, 1))))
            archive = root / "archive"
            archive.mkdir()
            (archive / "2026-11-20.json").write_text(json.dumps(variant))
            with (patch.object(study, "ROOT", root), patch.object(study, "ARCHIVE", archive),
                  patch.object(base, "FX_PATH", prices),
                  patch.object(study.subprocess, "check_output", return_value="2026-11-20T11:00:00+00:00")):
                result = study.evaluate(datetime.fromisoformat("2026-12-01T22:00:00+01:00"))
        comparison = result["windows"][0]["comparison_to_original_rule_same_inputs"]
        self.assertEqual(comparison["comparable_pairs"], expected)


if __name__ == "__main__":
    unittest.main()
