"""Deterministic ECB issuer-date catch-up tests; no market-data rewrite."""
from copy import deepcopy
import unittest
from validation.calendar.promote_ecb_oct29_official_cb_catchup_v1 import patch, LAST_ISSUER_DECISION, NEXT_ISSUER_MEETING

G8=("USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD")
def source():
    return {c: ({"bank":"ECB","last_date":"2026-09-10","next_meeting":"2026-10-29",
                 "rate":2.5,"rate_text":"Deposit 2.50%","action":"RIALZO +25 pb",
                 "impulse":"TIGHTENING","market_pricing":{"as_of":"2026-09-26/29 surfaced","h3m":2.82,"quality":"SECONDARY"}}
                if c=="EUR" else {"bank":c,"last_date":"2026-09-01","next_meeting":"2026-11-01","rate":1.0})
            for c in G8}

class EcbSourcePatchTests(unittest.TestCase):
    def test_updates_only_official_eur_facts_and_preserves_pricing(self):
        old=source(); result,status=patch(old)
        self.assertEqual(status,"OFFICIAL_ECB_2026_10_29_CATCHUP_READY")
        self.assertEqual(result["EUR"]["last_date"],LAST_ISSUER_DECISION)
        self.assertEqual(result["EUR"]["next_meeting"],NEXT_ISSUER_MEETING)
        self.assertEqual(result["EUR"]["rate"],2.5)
        self.assertEqual(result["EUR"]["rate_text"],"Deposit 2.50%")
        self.assertEqual(result["EUR"]["market_pricing"],old["EUR"]["market_pricing"])
        self.assertEqual(result["EUR"]["action"],"INVARIATO")
        self.assertEqual(result["EUR"]["impulse"],"HOLD_DATA_DEPENDENT")
        self.assertTrue(all(result[c]==old[c] for c in G8 if c!="EUR"))
    def test_is_idempotent_and_never_regresses_newer_fact(self):
        valid,_=patch(source()); after,status=patch(valid)
        self.assertEqual(status,"ALREADY_CERTIFIED_NO_CHANGE"); self.assertEqual(after,valid)
        later=deepcopy(valid); later["EUR"]["last_date"]="2026-12-17"
        after,status=patch(later)
        self.assertEqual(status,"SKIP_NEWER_CERTIFIED_EUR_DECISION"); self.assertEqual(after,later)
    def test_rejects_wrong_predecessor_or_rate_mutation(self):
        for field,value in (("last_date","2026-10-28"),("rate",2.25),("rate_text","Deposit 2.25%"),
                            ("next_meeting","2026-12-17"),("action","INVARIATO"),("impulse","HOLD_DATA_DEPENDENT")):
            with self.subTest(field=field):
                x=source(); x["EUR"][field]=value
                with self.assertRaisesRegex(ValueError,"ECB_CATCHUP_FAIL_CLOSED"): patch(x)
    def test_same_date_conflict_fails_closed(self):
        x,_=patch(source()); x["EUR"]["context"]="invented"
        with self.assertRaisesRegex(ValueError,"decision date already"): patch(x)
if __name__=="__main__": unittest.main()
