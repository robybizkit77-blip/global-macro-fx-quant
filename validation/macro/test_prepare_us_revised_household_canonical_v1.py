"""US revised real PCE / DPI canonical promotion: two-series all-or-nothing."""
from __future__ import annotations
import copy
from datetime import datetime,timezone
import unittest

from validation.macro import prepare_us_revised_household_canonical_v1 as p
from validation.macro.test_reconcile_us_real_households_countrybook_v2 import (
    USHouseholdRevisedResearchTests, fake_canonical, NOW,
)

CURRENCIES=("USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD")


def setup():
    t=USHouseholdRevisedResearchTests(
        "test_full_revised_history_not_tail_only_spliced")
    note=t.reconciled()
    current={ccy:[] for ccy in CURRENCIES}
    current["USD"]=fake_canonical()["USD"]+[{
        "id":"US_OTHER","dates":["2026-09-01"],"values":[77],
        "last_date":"2026-09-01","last_value":77}]
    return note,current


class UsRevisedPromotionTests(unittest.TestCase):
    def test_full_vintage_both_series_and_unit_provenance(self):
        note,old=setup()
        before=copy.deepcopy(old)
        new,r=p.prepare(note,old,as_of=NOW)
        self.assertEqual(r["status"],
                         "REVISED_US_HOUSEHOLDS_READY_FOR_CANONICAL_APPLY")
        self.assertTrue(r["full_revised_history_not_spliced"])
        self.assertFalse(r["first_release_pit_eligible"])
        self.assertEqual(old,before)
        self.assertEqual(new["USD"][-1],old["USD"][-1])
        self.assertEqual(len(new["USD"]),len(old["USD"]))
        self.assertTrue(all(new[c]==old[c] for c in CURRENCIES if c!="USD"))
        self.assertEqual(sum(z["changed"] for z in r["series"]),2)
        for z in new["USD"][:2]:
            self.assertEqual(len(z["dates"]),84)
            self.assertEqual(z["last_date"],"2026-09-01")
            self.assertEqual(z["unit"],p.EXPECTED_UNIT)
            self.assertEqual(z["frequency"],"M")
            self.assertEqual(z["current_vintage_provenance"]
                             ["source_series_first_release_PIT_certified"],False)
            self.assertEqual(z["current_vintage_provenance"]
                             ["issuer"],"US_BEA")
            self.assertTrue(z["current_vintage_provenance"]
                            ["historical_levels_may_be_revised_again"])

    def test_idempotent_second_pass_no_new_commit_or_rewritten_metadata(self):
        note,old=setup()
        first,_=p.prepare(note,old,as_of=NOW)
        second,result=p.prepare(note,first,as_of=NOW)
        self.assertEqual(result["status"],
                         "NO_CHANGE_VERIFIED_REVISED_VINTAGE")
        self.assertFalse(result["requires_atomic_payload_manifest_update"])
        self.assertEqual(first,second)

    def test_one_failed_series_blocks_both(self):
        note,old=setup()
        broken=copy.deepcopy(note)
        broken["revised_series"]["DSPIC96"]["latest_level"]+=150
        with self.assertRaisesRegex(ValueError,"US_REVISED_PROMOTION_REJECTED"):
            p.prepare(broken,old,as_of=NOW)
        self.assertEqual(old["USD"][0]["last_date"],"2026-07-01")

    def test_inconsistent_older_revision_month_rejected(self):
        note,old=setup()
        broken=copy.deepcopy(note)
        broken["revised_series"]["PCEC96"]["complete_revised_history"][5]["value"]+=3
        with self.assertRaisesRegex(ValueError,"revised overlap"):
            p.prepare(broken,old,as_of=NOW)

    def test_changed_prior_month_fakes_bea_rate_rejected(self):
        note,old=setup()
        broken=copy.deepcopy(note)
        broken["revised_series"]["PCEC96"]["complete_revised_history"][-2]["value"]-=100
        with self.assertRaisesRegex(ValueError,"BEA latest monthly rate"):
            p.prepare(broken,old,as_of=NOW)

    def test_future_research_clock_rejected(self):
        note,old=setup()
        future=datetime(2026,11,8,20,tzinfo=timezone.utc)
        with self.assertRaisesRegex(ValueError,"observed in the future"):
            p.prepare(note,old,as_of=future)

    def test_no_cross_currency_or_other_us_series_mutation(self):
        note,old=setup()
        old["GBP"].append({"id":"KEEP","last_value":32})
        new,_=p.prepare(note,old,as_of=NOW)
        self.assertEqual(new["GBP"],old["GBP"])
        self.assertEqual(new["USD"][-1],old["USD"][-1])

    def test_wrong_unit_and_missing_series_or_period_rejected(self):
        note,old=setup()
        broken=copy.deepcopy(old)
        broken["USD"][1]["unit"]="Millions current dollars"
        with self.assertRaisesRegex(ValueError,"incompatible definition"):
            p.prepare(note,broken,as_of=NOW)
        broken=copy.deepcopy(old)
        broken["USD"][1]["id"]="OTHER"
        with self.assertRaisesRegex(ValueError,"identity"):
            p.prepare(note,broken,as_of=NOW)

    def test_historical_first_release_claim_cannot_be_enabled(self):
        note,old=setup()
        changed=copy.deepcopy(note)
        changed["series_pit_certified"]=True
        with self.assertRaisesRegex(ValueError,"research issuer gate"):
            p.prepare(changed,old,as_of=NOW)

    def test_no_period_regression_after_promotion(self):
        note,old=setup()
        updated,_=p.prepare(note,old,as_of=NOW)
        altered=copy.deepcopy(note)
        altered["latest_release_month"]="2026-07"
        with self.assertRaisesRegex(ValueError,"issuer month"):
            p.prepare(altered,updated,as_of=NOW)


if __name__=="__main__":
    unittest.main()
