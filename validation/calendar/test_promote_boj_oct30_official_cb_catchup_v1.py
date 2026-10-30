"""Policy-date catch-up: fail closed and never rewrite live TONA pricing."""
from copy import deepcopy
import unittest
from validation.calendar.promote_boj_oct30_official_cb_catchup_v1 import (
    patch,LAST_ISSUER_DECISION,NEXT_ISSUER_MEETING)

G8=("USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD")
def source():
    return {c:({"bank":"BoJ","last_date":"2026-09-18","next_meeting":"2026-10-30",
                "rate":1.25,"rate_text":"1.25%","action":"RIALZO +25 pb",
                "impulse":"TIGHTENING",
                "market_pricing":{"as_of":"2026-10-29","h3m":1.468,"quality":"CURRENT"}}
               if c=="JPY" else {"bank":c,"last_date":"2026-10-29",
               "next_meeting":"2026-12-01","rate":1.0}) for c in G8}

class BojCatchupTests(unittest.TestCase):
    def test_only_jpy_policy_fields_change(self):
        old=source();out,status=patch(old)
        self.assertEqual(status,"OFFICIAL_BOJ_2026_10_30_CATCHUP_READY")
        self.assertEqual(out["JPY"]["last_date"],LAST_ISSUER_DECISION)
        self.assertEqual(out["JPY"]["next_meeting"],NEXT_ISSUER_MEETING)
        self.assertEqual(out["JPY"]["rate"],old["JPY"]["rate"])
        self.assertEqual(out["JPY"]["market_pricing"],old["JPY"]["market_pricing"])
        self.assertTrue(all(out[c]==old[c] for c in G8 if c!="JPY"))
        self.assertEqual(old["JPY"]["last_date"],"2026-09-18")

    def test_idempotent_and_never_overwrite_newer_certified(self):
        today,_=patch(source())
        self.assertEqual(patch(today),(today,"ALREADY_CERTIFIED_NO_CHANGE"))
        later=deepcopy(today);later["JPY"]["last_date"]="2026-12-18"
        self.assertEqual(patch(later),(later,"SKIP_NEWER_CERTIFIED_JPY_DECISION"))

    def test_rejects_unknown_prior_and_conflicting_same_day(self):
        for field,value in (("last_date","2026-10-29"),("rate",1.50),
                            ("rate_text","1.50%"),("next_meeting","2026-12-18"),
                            ("action","INVARIATO"),("impulse","HOLD")):
            with self.subTest(field=field):
                s=source();s["JPY"][field]=value
                with self.assertRaisesRegex(ValueError,"BOJ_CATCHUP_FAIL_CLOSED"):
                    patch(s)
        today,_=patch(source())
        today["JPY"]["context"]="unverified"
        with self.assertRaisesRegex(ValueError,"conflicting facts"):
            patch(today)

    def test_requires_exact_g8(self):
        s=source();s.pop("CHF")
        with self.assertRaisesRegex(ValueError,"unexpected G8"):
            patch(s)

if __name__=="__main__": unittest.main()
