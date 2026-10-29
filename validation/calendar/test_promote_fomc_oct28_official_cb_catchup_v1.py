"""Deterministic issuer-date catch-up tests; no historical rewrite."""
from copy import deepcopy
import unittest

from validation.calendar.promote_fomc_oct28_official_cb_catchup_v1 import (
    patch, LAST_ISSUER_DECISION, NEXT_ISSUER_MEETING
)

G8=("USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD")

def source():
    return {
        c: ({"bank":"Fed","last_date":"2026-09-16",
             "next_meeting":"2026-10-28","rate":3.875,
             "rate_text":"3.75-4.00%","action":"RIALZO +25 pb",
             "impulse":"TIGHTENING","market_pricing":{
                "as_of":"2026-09 (latest surfaced)","h3m":4.0,"quality":"STALE"
             }}
            if c=="USD" else {"bank":c,"last_date":"2026-09-01",
                              "next_meeting":"2026-11-01","rate":1.0})
        for c in G8
    }

class FomcSourcePatchTests(unittest.TestCase):
    def test_updates_only_issuer_supported_facts_and_keeps_stale_futures(self):
        old=source()
        result,status=patch(old)
        self.assertEqual(status,"OFFICIAL_FOMC_2026_10_28_CATCHUP_READY")
        self.assertEqual(result["USD"]["last_date"],LAST_ISSUER_DECISION)
        self.assertEqual(result["USD"]["next_meeting"],NEXT_ISSUER_MEETING)
        self.assertEqual(result["USD"]["rate"],old["USD"]["rate"])
        self.assertEqual(result["USD"]["rate_text"],old["USD"]["rate_text"])
        self.assertEqual(result["USD"]["market_pricing"],old["USD"]["market_pricing"])
        self.assertEqual(result["USD"]["impulse"],"HOLD_HAWKISH_RISK")
        self.assertNotEqual(result["USD"]["action"],old["USD"]["action"])
        self.assertTrue(all(result[c]==old[c] for c in G8 if c!="USD"))
        self.assertEqual(old["USD"]["last_date"],"2026-09-16")

    def test_idempotent_and_does_not_regress_future_certified_date(self):
        next_version,_=patch(source())
        after,status=patch(next_version)
        self.assertEqual(status,"ALREADY_CERTIFIED_NO_CHANGE")
        self.assertEqual(after,next_version)
        later=deepcopy(next_version)
        later["USD"]["last_date"]="2026-12-09"
        after,status=patch(later)
        self.assertEqual(status,"SKIP_NEWER_CERTIFIED_USD_DECISION")
        self.assertEqual(after,later)

    def test_rejects_unknown_prior_snapshot_or_rate_mutation(self):
        for field,value in (
            ("last_date","2026-10-27"),("rate",3.75),
            ("rate_text","4.0-4.25%"),("next_meeting","2026-12-09"),
            ("impulse","HOLD_HAWKISH_RISK"),("action","INVARIATO"),
        ):
            with self.subTest(field=field):
                data=source()
                data["USD"][field]=value
                with self.assertRaisesRegex(ValueError,"FOMC_CATCHUP_FAIL_CLOSED"):
                    patch(data)

    def test_same_date_conflicting_context_fails_closed(self):
        valid,_=patch(source())
        valid["USD"]["context"]="Invented meeting outcome"
        with self.assertRaisesRegex(ValueError,"decision date already"):
            patch(valid)

    def test_requires_exact_currency_universe(self):
        bad=source()
        bad.pop("NZD")
        with self.assertRaisesRegex(ValueError,"unexpected G8"):
            patch(bad)

if __name__=="__main__":
    unittest.main()
