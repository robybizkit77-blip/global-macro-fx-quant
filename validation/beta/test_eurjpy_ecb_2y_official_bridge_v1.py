"""EURJPY ECB 2Y source-day recovery is exact-date, publisher verified, shadow only."""
from __future__ import annotations

import copy
from datetime import date
import json
import unittest

from validation.beta import eurjpy_ecb_2y_official_bridge_v1 as m
from validation.beta import weekly_fx_2y_shadow_oos_v1 as b


def official_fixture(eur, *, sep24=3.24, sep25=3.26, perturb_overlap=False):
    days=[("2026-09-21",eur[date(2026,9,21)]),
          ("2026-09-22",eur[date(2026,9,22)]+(0.01 if perturb_overlap else 0)),
          ("2026-09-23",3.25),
          ("2026-09-24",sep24),
          ("2026-09-25",sep25)]
    return ("KEY,TIME_PERIOD,OBS_VALUE\n"+
       "".join(f"{m.ECB_SERIES},{d},{v:.10f}\n" for d,v in days)).encode()


class EUR2YOriginalResearchBridge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rates=json.loads(b.RATE_PATH.read_text())
        cls.eur,reason=b.rate_history("EUR",cls.rates,date(2026,10,26))
        assert not reason

    def test_official_two_existing_days_and_three_new_are_staged_not_published(self):
        original=json.dumps(self.rates,sort_keys=True)
        candidate,proof=m.repair_eur_2y_history_in_memory(
            self.rates,official_fixture(self.eur))
        self.assertEqual(proof["overlap_confirmed_with_stored_eur2y_dates"],
                         ["2026-09-21","2026-09-22"])
        self.assertEqual(proof["restored_days"],
                         ["2026-09-23","2026-09-24","2026-09-25"])
        self.assertEqual(proof["new_research_2y_days"],
                         proof["original_repo_2y_days"]+3)
        self.assertTrue(proof["no_interpolation"])
        self.assertTrue(proof["no_week_date_shifting"])
        self.assertFalse(proof["live_data_modified"])
        self.assertFalse(proof["model_beta_promoted"])
        self.assertFalse(proof["official_historical_first_release_vintage_verified"])
        self.assertEqual(candidate["EUR"]["date"],self.rates["EUR"]["date"])
        self.assertEqual(json.dumps(self.rates,sort_keys=True),original)

    def test_legacy_source_value_mismatch_cannot_be_overwritten(self):
        with self.assertRaisesRegex(ValueError,"existing EUR2Y vs original ECB data disagree"):
            m.repair_eur_2y_history_in_memory(
                self.rates,official_fixture(self.eur,perturb_overlap=True))

    def test_wrong_yield_curve_key_is_rejected(self):
        f=official_fixture(self.eur).decode().replace(
            m.ECB_SERIES,"YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y")
        with self.assertRaisesRegex(ValueError,"wrong ECB AAA 2Y series"):
            m.repair_eur_2y_history_in_memory(self.rates,f.encode())

    def test_same_day_missing_sept24_25_is_not_a_fix(self):
        v=official_fixture(self.eur).decode()
        rows=v.splitlines()
        only="\n".join([l for l in rows if not l.startswith(("YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y,2026-09-24",
                                                              "YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y,2026-09-25"))])+"\n"
        with self.assertRaisesRegex(ValueError,"no same-day overlapping"):
            m.repair_eur_2y_history_in_memory(self.rates,only.encode())

    def test_duplicate_observations_are_rejected(self):
        orig=official_fixture(self.eur)
        extra=(f"{m.ECB_SERIES},2026-09-21,3.2598888904\n").encode()
        with self.assertRaisesRegex(ValueError,"duplicate ECB 2Y"):
            m.parse_ecb_sdmx_original_csv(orig+extra)

    def test_bad_api_header_and_date_outside_range_block(self):
        with self.assertRaisesRegex(ValueError,"header required"):
            m.parse_ecb_sdmx_original_csv(b"TIME_PERIOD,OBS_VALUE\n2026-09-24,3.2\n")
        wrong=official_fixture(self.eur).replace(b"2026-09-25",b"2026-09-28")
        with self.assertRaisesRegex(ValueError,"outside requested bounds"):
            m.parse_ecb_sdmx_original_csv(wrong)


if __name__=="__main__":
    unittest.main()
