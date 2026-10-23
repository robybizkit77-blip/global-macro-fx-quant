#!/usr/bin/env python3
"""Adversarial Macro V2 PIT normalization tests; no trading claims."""
from __future__ import annotations

import copy
import json
import math
import statistics
import unittest
from datetime import datetime, timezone
from pathlib import Path

from validation.macro.v2_shadow_features_v1 import SCHEMA, ROOT
from validation.macro.v2_shadow_intensity_v1 import build_shadow_intensity


def fixture(pillar="labour", frequency="M"):
    if frequency == "M":
        pairs = [((2024+(i//12),i%12+1), i) for i in range(30)]
        variable = {"labour":"unemployment_rate",
                    "inflation":"headline_cpi_yoy",
                    "growth":"industrial_production_yoy"}[pillar]
        unit = "percent" if pillar=="labour" else "yoy_pct"
        rows = []
        for (year,month), i in pairs:
            release_y,release_m = year+(month==12),(month%12)+1
            value=round(4.0+0.037*i+0.17*(i%5-2),4)
            rows.append({
                "observation_period": f"{year:04d}-{month:02d}",
                "released_at": datetime(release_y,release_m,3,12,
                                          tzinfo=timezone.utc).isoformat(),
                "value":value,"kind":"FIRST","evidence_ref":f"SYN_M_{i:02d}",
            })
        as_of = "2026-07-15T12:00:00Z"
    else:
        variable="real_gdp_qoq"
        unit="qoq_pct"
        rows=[]
        for i in range(16):
            year,quarter=2022+i//4,i%4+1
            release_month=quarter*3+1
            release_year=year
            if release_month>12:release_month,release_year=1,year+1
            rows.append({
                "observation_period":f"{year}Q{quarter}",
                "released_at":datetime(release_year,release_month,10,12,
                                       tzinfo=timezone.utc).isoformat(),
                "value":round(0.2+0.035*i+0.14*(i%4-1.5),4),
                "kind":"FIRST","evidence_ref":f"SYN_Q_{i:02d}",
            })
        as_of="2026-01-20T12:00:00Z"
    return {
        "schema":SCHEMA,"as_of":as_of,
        "currency":"USD","pillar":pillar,"series_id":"SYNTHETIC_"+variable,
        "variable_type":variable,"frequency":frequency,"unit":unit,
        "max_lag_periods":2,
        "source":{"authority":"TEST_ONLY","source_id":"SYNTHETIC",
                  "transport":"SYNTHETIC_FIXTURE"},
        "vintages":rows,
    }


class ShadowIntensityTests(unittest.TestCase):
    def test_unemployment_means_tightness_not_fx_strength(self):
        m=fixture()
        out=build_shadow_intensity(m)
        self.assertEqual(out["training_first_releases"],24)
        self.assertEqual(out["training_end_period"],"2026-05")
        self.assertEqual(out["latest_period"],"2026-06")
        self.assertEqual(out["economic_dimension"],"LABOUR_TIGHTNESS")
        self.assertEqual(out["economic_polarity"],-1)
        self.assertAlmostEqual(out["dimension_intensity"],-out["robust_z_clipped"])
        self.assertTrue(0<=out["history_rank_percent"]<=100)
        self.assertIsNone(out["currency_strength_score"])
        self.assertIsNone(out["economic_cycle"])
        self.assertFalse(out["ready_for_macro_scoring"])
        self.assertFalse(out["usable_for_backtest"])
        self.assertFalse(out["safe_to_publish_new_D"])
        self.assertFalse(out["safe_to_update_pair_theses"])
        self.assertFalse(out["source_evidence_is_independently_certified"])
        self.assertFalse(out["writes_live_data"])

    def test_current_value_out_of_own_training_window(self):
        m=fixture()
        a=build_shadow_intensity(m)
        m["vintages"][-1]["value"]+=10
        b=build_shadow_intensity(m)
        self.assertEqual(a["training_median"],b["training_median"])
        self.assertEqual(a["training_mad"],b["training_mad"])
        self.assertNotEqual(a["robust_z_unclipped"],b["robust_z_unclipped"])
        self.assertEqual(b["robust_z_clipped"],3.0)

    def test_first_release_history_vs_revisions_never_uses_future(self):
        m=fixture()
        a=build_shadow_intensity(m)
        m["vintages"].append({
            "observation_period":"2026-05",
            "released_at":"2026-07-18T13:30:00+00:00",
            "value":99.0,"kind":"REVISION","evidence_ref":"SYN_REV_FUTURE",
        })
        b=build_shadow_intensity(m)
        self.assertEqual(a["method_fingerprint_sha256"],b["method_fingerprint_sha256"])
        self.assertEqual(a["dimension_intensity"],b["dimension_intensity"])
        m["vintages"][-1]["released_at"]="2026-07-10T13:30:00+00:00"
        c=build_shadow_intensity(m)
        self.assertEqual(a["method_fingerprint_sha256"],c["method_fingerprint_sha256"])
        self.assertNotEqual(a["raw_feature_receipt_fingerprint_sha256"],
                            c["raw_feature_receipt_fingerprint_sha256"])
        self.assertEqual(c["latest_first_release_value"],a["latest_first_release_value"])

    def test_future_period_after_cutoff_does_not_enter_window(self):
        m=fixture()
        a=build_shadow_intensity(m)
        m["vintages"].append({
            "observation_period":"2026-07",
            "released_at":"2026-08-03T12:00:00Z",
            "kind":"FIRST","value":29.5,"evidence_ref":"SYN_NEXT",
        })
        self.assertEqual(a["method_fingerprint_sha256"],
                         build_shadow_intensity(m)["method_fingerprint_sha256"])

    def test_asof_cutoff_rolling_history_changes_without_leakage(self):
        m=fixture()
        latest=build_shadow_intensity(m)
        m["as_of"]="2026-06-15T12:00:00Z"
        prior=build_shadow_intensity(m)
        self.assertEqual(prior["latest_period"],"2026-05")
        self.assertNotEqual(prior["method_fingerprint_sha256"],
                            latest["method_fingerprint_sha256"])

    def test_quarterly_is_explicit_and_has_different_training_window(self):
        m=fixture("growth","Q")
        a=build_shadow_intensity(m)
        self.assertEqual(a["training_first_releases"],12)
        self.assertEqual(a["latest_period"],"2025Q4")
        self.assertEqual(a["economic_dimension"],"REAL_ACTIVITY")
        self.assertEqual(a["economic_polarity"],1)
        self.assertIsNone(a["currency_strength_score"])

    def test_inflation_pressure_is_not_hawkish_or_positive_fx(self):
        m=fixture("inflation","M")
        x=build_shadow_intensity(m)
        self.assertEqual(x["economic_dimension"],"PRICE_PRESSURE")
        self.assertTrue(x["inflation_pressure_is_not_fx_strength"])
        self.assertIsNone(x["currency_strength_score"])

    def test_real_bls_five_release_pilot_has_insufficient_training(self):
        p=ROOT/"validation/macro/fixtures/v2_bls_us_unrate_first_release_2023_12_2024_04.json"
        m=json.loads(p.read_text(encoding="utf-8"))
        m["unit"]="percent"
        m["variable_type"]="unemployment_rate"
        with self.assertRaisesRegex(ValueError,"insufficient independently dated"):
            build_shadow_intensity(m)

    def test_fail_closed_bad_pillar_units_lags_transport_clocks(self):
        for change,reason in (
            (lambda x:x.update(unit="yoy_pct"),"pillar/frequency/units"),
            (lambda x:x.update(pillar="inflation"),"pillar/frequency/units"),
            (lambda x:x.update(variable_type="fx_buy_score"),"unsupported"),
            (lambda x:x.update(as_of="2026-07-15T12:00:00"),"offset-aware"),
            (lambda x:x["source"].update(transport="SECONDARY_MIRROR"),"secondary transport"),
            (lambda x:x.update(as_of="2026-12-15T12:00:00Z"),"staleness"),
        ):
            m=fixture()
            change(m)
            with self.subTest(change=repr(change)):
                with self.assertRaisesRegex(ValueError,reason):
                    build_shadow_intensity(m)

    def test_missing_historical_period_stops_even_with_last_four_contiguous(self):
        m=fixture()
        m["vintages"]=[x for x in m["vintages"] if x["observation_period"]!="2025-05"]
        with self.assertRaisesRegex(ValueError,"rolling training window"):
            build_shadow_intensity(m)

    def test_flat_distribution_rejected_not_padded(self):
        m=fixture()
        for x in m["vintages"]:x["value"]=4.0
        with self.assertRaisesRegex(ValueError,"zero or near-zero"):
            build_shadow_intensity(m)

    def test_input_unchanged_and_reproducible(self):
        m=fixture()
        original=copy.deepcopy(m)
        a=build_shadow_intensity(m)
        b=build_shadow_intensity(m)
        self.assertEqual(a,b)
        self.assertEqual(m,original)


if __name__=="__main__":
    unittest.main()
