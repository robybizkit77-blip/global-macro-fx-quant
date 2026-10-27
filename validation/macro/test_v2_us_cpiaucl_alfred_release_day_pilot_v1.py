"""Adversarial offline coverage for the USD CPIAUCSL ALFRED pilot."""
import csv
import io
import unittest
from validation.macro.v2_us_cpiaucl_alfred_release_day_pilot_v1 import (
    RELEASES, SCHEMA, inspect, url_for, earlier_month,
)


def fixture(month, base=300.0, current=310.0, extra=None):
    vintage = RELEASES[month][0].replace("-", "")
    b = io.StringIO(newline="")
    w = csv.writer(b)
    w.writerow(["observation_date", "CPIAUCSL_" + vintage])
    w.writerow([earlier_month(month, 12) + "-01", base])
    w.writerow([month + "-01", current])
    for p, v in extra or []:
        w.writerow([p + "-01", v])
    return b.getvalue().encode()


class TestReleaseDayPilot(unittest.TestCase):
    def test_independent_bls_release_day_mapping_and_sa_index_math(self):
        for month in RELEASES:
            with self.subTest(month=month):
                out = inspect(month, fixture(month))
                self.assertEqual(out["schema"], SCHEMA)
                self.assertEqual(out["CPIAUCSL_SA_index_current_at_release_day"], 310)
                self.assertAlmostEqual(out["index_based_SA_YOY_pct_as_of_release_day"], 100/30)
                self.assertIn("alfred.stlouisfed.org", url_for(month))
                self.assertEqual(out["BLS_published_release_day"], RELEASES[month][0])
                self.assertFalse(out["safe_to_publish_new_D"])
                self.assertFalse(out["safe_to_change_28_pairs"])
                self.assertFalse(out["safe_for_beta"])
                self.assertFalse(out["safe_for_forward"])
                self.assertFalse(out["writes_live_data"])
                self.assertFalse(out["research_first_release_training_24M_complete"])
                self.assertFalse(out["first_release_BLS_download_sha256_verified"])
                self.assertFalse(out["BLS_NSA_official_headline_YOY_identical"])

    def test_shut_down_october_2025_must_never_be_filled(self):
        with self.assertRaises(ValueError):
            inspect("2026-09", fixture("2026-09", extra=[("2025-10", 310)]))

    def test_spoofed_vintage_header_and_extra_columns(self):
        for bad in (b"DATE,CPIAUCSL_20261013\n", b"DATE,CPIAUCSL_20261014,EXTRA\n"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                inspect("2026-09", bad)

    def test_no_missing_base_missing_latest_or_future_period(self):
        for bad in (
            b"DATE,CPIAUCSL_20261014\n2026-09-01,310\n",
            b"DATE,CPIAUCSL_20261014\n2025-09-01,300\n",
            fixture("2026-09", extra=[("2026-10", 310)]),
            fixture("2026-09", extra=[("2026-09", 311)]),
            fixture("2026-09", extra=[("2026-02", "nan")]),
        ):
            with self.subTest(bad=bad[:65]), self.assertRaises(ValueError):
                inspect("2026-09", bad)

    def test_no_unapproved_month_release_date(self):
        with self.assertRaises(ValueError):
            url_for("2025-10")
        with self.assertRaises(ValueError):
            inspect("2025-10", fixture("2025-09"))


if __name__ == "__main__":
    unittest.main()
