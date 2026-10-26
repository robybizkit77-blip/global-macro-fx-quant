"""Impact gate regression checks for site CHF proxy and pair rate consumers."""
from __future__ import annotations

import copy
import json
import unittest

from validation.rates import audit_eur_2y_10y_site_consumer_impact_v1 as m


class ECBRatesSiteImpactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live=json.loads(m.LIVE.read_text())
        cls.home=m.HOME.read_text()
        cls.legacy=m.LEGACY_CHART.read_text()
        cls.dash=m.LEGACY_DASH.read_text()
        cls.adapter=m.DATA_ADAPTER.read_text()

    def build(self):
        cand=copy.deepcopy(self.live)
        cand["EUR"]["history2"]["values"][0] += .1
        cand["EUR"]["history10"]["values"][0] += .2
        cand["EUR"]["history2_quality"]="ECB_ORIGINAL_NOT_PIT"
        return cand

    def assess(self,cand=None,**overrides):
        return m.assess(self.live,cand or self.build(),
            overrides.get("home",self.home),
            overrides.get("legacy",self.legacy),
            overrides.get("dash",self.dash),
            overrides.get("adapter",self.adapter))

    def test_correctly_classifies_actual_impact_and_not_published(self):
        x=self.assess()
        self.assertEqual(x["status"],"CONTROLLED_RELEASE_REQUIRED_NO_AUTO_PROMOTION")
        self.assertEqual(x["impacts"]["2Y"]["changed_stored_historical_days"],1)
        self.assertEqual(x["impacts"]["10Y"]["changed_stored_historical_days"],1)
        self.assertTrue(x["unchanged_latest_official_EUR_2Y_10Y"])
        self.assertFalse(x["safe_to_publish_now"])
        self.assertFalse(x["source_origin_defect_resolved"])
        self.assertFalse(x["quantified_derived_CHF_beta_estimate_reaction"])
        self.assertTrue(any("CHF" in v["consumer"] for v in x["consumer_classes"]))
        self.assertTrue(any("EUR crosses" in v["consumer"] for v in x["consumer_classes"]))

    def test_changes_in_other_currencies_forbidden(self):
        c=self.build()
        c["USD"]["2Y"]+=.01
        with self.assertRaisesRegex(ValueError,"other-G8"):
            self.assess(c)

    def test_current_eur_official_rate_cannot_change(self):
        c=self.build()
        c["EUR"]["2Y"]+=.01
        with self.assertRaisesRegex(ValueError,"current official"):
            self.assess(c)

    def test_5y_or_30y_non_equivalent_tenors_must_be_untouched(self):
        c=self.build()
        c["EUR"]["tenors"][1]["value"]+=.1
        with self.assertRaisesRegex(ValueError,"current official"):
            self.assess(c)

    def test_unknown_rate_metadata_or_model_fields_cannot_change(self):
        c=self.build()
        c["EUR"]["unexpected_score"]="fake"
        with self.assertRaisesRegex(ValueError,"scope invalid"):
            self.assess(c)

    def test_consumer_code_shape_change_stops_publisher_review(self):
        with self.assertRaisesRegex(ValueError,"consumer shape"):
            self.assess(home=self.home.replace("function estimate(","function _oldEstimate("))

    def test_no_curve_history_change_does_not_create_a_repair_receipt(self):
        with self.assertRaisesRegex(ValueError,"scope invalid"):
            self.assess(copy.deepcopy(self.live))


if __name__=="__main__":
    unittest.main()
