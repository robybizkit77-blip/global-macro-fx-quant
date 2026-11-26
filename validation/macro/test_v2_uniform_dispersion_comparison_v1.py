import statistics
import unittest
from validation.macro.v2_uniform_dispersion_comparison_v1 import compare, run

class UniformDispersionTests(unittest.TestCase):
    def test_zero_mad_nonconstant(self):
        prior = [6.3]*10 + [6.4]*14
        r = compare(prior, 6.5)
        self.assertIsNone(r["strict_mad_z"])
        self.assertAlmostEqual(r["sample_sd_z_unclipped"],
                               (6.5-statistics.mean(prior))/statistics.stdev(prior))
        self.assertGreater(r["sample_sd_z"], 0)
        self.assertEqual(r["midrank_percentile"], 1)

    def test_constant_is_not_imputed(self):
        r = compare([6.4]*24, 6.5)
        self.assertIsNone(r["sample_sd_z"])
        self.assertIsNone(r["strict_mad_z"])

    def test_prior_only_and_dynamics(self):
        prior = [1, 2, 3, 2]
        a, b = compare(prior, 4), compare(prior, 10)
        self.assertEqual(a["prior_sample_sd"], b["prior_sample_sd"])
        self.assertEqual(a["prior_mean"], b["prior_mean"])
        self.assertEqual(a["velocity"], 2)
        self.assertEqual(a["acceleration"], 3)
        self.assertEqual(a["turning_point"], "DOWN_TO_UP")

    def test_invalid_inputs(self):
        for prior in ([1], [1, float("nan")], [True, 2]):
            with self.assertRaises(ValueError):
                compare(prior, 2)

    def test_live_registry_comparison_read_only(self):
        r = run()
        self.assertEqual(len(r["rows"]), 16)
        self.assertFalse(r["safe_to_publish_D"])
        self.assertFalse(r["safe_to_update_pairs"])
        self.assertFalse(r["writes_live_data"])
        for key, row in r["rows"].items():
            if row["missing_prior_periods"]:
                self.assertIsNone(row["sample_sd_z"], key)
            elif row["sample_sd_z"] is not None:
                sign = -1 if key.endswith(".labour") else 1
                self.assertEqual(row["economic_polarity_sample_sd_z"],
                                 sign * row["sample_sd_z"])
                self.assertGreater(row["prior_sample_sd"], 0)

    def test_all_24_axes_no_promotion(self):
        r = run()
        self.assertEqual(len(r["growth_rows"]), 8)
        self.assertEqual(len(r["rows"]) + len(r["growth_rows"]), 24)
        axes = {**r["rows"], **r["growth_rows"]}
        self.assertEqual(r["all_24_axis_alternative_numeric_count"],
                         sum(v["sample_sd_z"] is not None for v in axes.values()))
        self.assertTrue(r["mixed_evidence_classes_not_synchronized_PIT_panel"])
        for row in r["growth_rows"].values():
            self.assertEqual(row["source_class"], "INITIAL_PUBLISHER_WEB_STATEMENTS_NOT_ARCHIVAL_PIT")
            if row["sample_sd_z"] is not None:
                self.assertEqual(row["prior_count"], 12)
            if row["latest_visible_revision"] is not None:
                self.assertTrue(row["latest_visible_revision"]["NOT_used_to_train_initial_web_z"])
