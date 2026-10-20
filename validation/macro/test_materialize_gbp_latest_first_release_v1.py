"""Regression for strict two ONS first-publication period checks."""
import copy
import json
import unittest
from pathlib import Path
from validation.macro.materialize_gbp_latest_first_release_v1 import (
    verify_materialization, ROOT, CONTRACT,
)

def make_rows():
    return [
        {
            "reference_month": p,
            "rolling_period":label,
            "source_rolling_period":label,
            "headline_unemployment_rate_pct":value,
            "release_date":date,
            "source_route":"ONS_EMPLOYMENT_IN_UK_COMPANION_BULLETIN",
            "source_url":"https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/employmentandemployeetypes/bulletins/employmentintheuk/"+slug,
            "page_sha256": sha*64,
            "pit_status":"STRICT_FIRST_RELEASE",
        }
        for p,label,value,date,slug,sha in [
            ("2026-07","May 2026 to July 2026",4.9,"2026-09-15","september2026","a"),
            ("2026-08","June 2026 to August 2026",4.7,"2026-10-20","october2026","b"),
        ]
    ]


class UKONSFirstReleaseUnit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract=json.loads((ROOT/CONTRACT).read_text())

    def check(self,modify=None):
        rows=make_rows()
        if modify:
            modify(rows)
        return verify_materialization(rows, self.contract)

    def test_two_bulletins_can_prove_period_and_value_without_score(self):
        r=self.check()
        self.assertEqual(r["status"],"TWO_FIRST_RELEASE_PAGES_VERIFIED")
        self.assertEqual(r["official_pages_independently_hashed"],2)
        self.assertFalse(r["all_history_vintage_certified"])
        self.assertFalse(r["macro_score_rebase_authorized"])

    def test_shifted_ons_july_center_date_rejected(self):
        with self.assertRaisesRegex(ValueError,"unexpected end-of-rolling-period"):
            self.check(lambda x:x[1].update(reference_month="2026-07"))

    def test_substituted_may_july_47_rate_rejected(self):
        with self.assertRaisesRegex(ValueError,"value/date mismatch"):
            self.check(lambda x:x[0].update(headline_unemployment_rate_pct=4.7))

    def test_future_release_date_not_equivalent_to_first_release(self):
        with self.assertRaisesRegex(ValueError,"value/date mismatch"):
            self.check(lambda x:x[1].update(release_date="2026-11-18"))

    def test_same_source_document_cannot_cover_two_months(self):
        with self.assertRaisesRegex(ValueError,"source page reused"):
            self.check(lambda x:x[1].update(page_sha256="a"*64))

    def test_untrusted_url_rejected(self):
        with self.assertRaisesRegex(ValueError,"release must be hosted"):
            self.check(lambda x:x[0].update(source_url="https://ons.gov.uk.evil.test/ons"))

    def test_current_mutated_MGSX_api_not_an_archived_source(self):
        with self.assertRaisesRegex(ValueError,"unsupported retrieval"):
            self.check(lambda x:x[0].update(source_route="ONS_LIVE_CURRENT_REVISION"))

    def test_wrong_rolling_window_rejected(self):
        with self.assertRaisesRegex(ValueError,"source rolling-window identity drift"):
            self.check(lambda x:x[1].update(rolling_period="July 2026 to September 2026"))


if __name__=="__main__":
    unittest.main()
