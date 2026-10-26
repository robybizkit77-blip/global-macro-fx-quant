"""ECB 2Y source parity tests, never infer equal instruments from labels."""
from __future__ import annotations
import copy
from datetime import date
import json
import unittest
from validation.beta import audit_ecb_eur2y_official_mirror_parity_v1 as m
from validation.beta import weekly_fx_2y_shadow_oos_v1 as b


class EUR2YParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rates=json.loads(b.RATE_PATH.read_text(encoding="utf-8"))
        cls.orig,_=b.rate_history("EUR",cls.rates,date(2026,10,22))

    def raw(self,*, alter=None,skip=()):
        alter=alter or {}
        out=["KEY,TIME_PERIOD,OBS_VALUE"]
        for d,v in sorted(self.orig.items()):
            if d.isoformat() not in skip:
                val=alter.get(d.isoformat(),v)
                out.append(f"YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y,{d.isoformat()},{val:.10f}")
        return ("\n".join(out)+"\n").encode()

    def test_no_change_if_publisher_values_identical(self):
        original=json.dumps(self.rates,sort_keys=True)
        x=m.audit_eur_original(self.rates,self.raw())
        self.assertEqual(x["status"],"SOURCE_DEFINITION_MATCHES_CURRENT_PUBLISHER")
        self.assertEqual(x["mismatching_same_day_yield_rows"],0)
        self.assertEqual(x["overlap_rows"],271)
        self.assertEqual(x["official_current_latest_2y_pct"],self.orig[date(2026,10,22)])
        self.assertEqual(json.dumps(self.rates,sort_keys=True),original)

    def test_two_official_2y_differences_create_source_quarantine(self):
        x=m.audit_eur_original(self.rates,self.raw(alter={
            "2026-09-21":3.1476088412,
            "2026-09-22":3.135563132,
        }))
        self.assertEqual(x["status"],
            "RATE_EUR2Y_CURRENT_MIRROR_DIFFERS_FROM_OFFICIAL_SERIES")
        self.assertEqual(x["mismatching_same_day_yield_rows"],2)
        self.assertEqual(len(x["september_21_22_exact_differences"]),2)
        self.assertGreater(x["max_absolute_difference_bp"],10)
        self.assertFalse(x["source_grade_comparable"])
        self.assertFalse(x["beta_promoted"])
        self.assertFalse(x["production_history_modified"])

    def test_reject_short_unverified_historic_source(self):
        days=[x.isoformat() for x in sorted(self.orig)[:100]]
        days.append("2026-10-22")  # preserve current end; test short overlap, not missing as-of
        with self.assertRaisesRegex(ValueError,"insufficient source overlap"):
            m.audit_eur_original(self.rates,self.raw(skip=set(x.isoformat()
                for x in self.orig if x.isoformat() not in days)))

    def test_invalid_source_key_rejected(self):
        raw=self.raw().replace(b"SR_2Y",b"SR_10Y")
        with self.assertRaisesRegex(ValueError,"wrong ECB AAA 2Y series"):
            m.audit_eur_original(self.rates,raw)

    def test_missing_last_official_source_day_rejected(self):
        with self.assertRaisesRegex(ValueError,"missing expected 2026-10-22"):
            m.audit_eur_original(self.rates,self.raw(skip={"2026-10-22"}))


if __name__=="__main__":
    unittest.main()
