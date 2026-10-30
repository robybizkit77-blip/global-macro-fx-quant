"""Adversarial tests for future-only, non-numeric zero-MAD handling."""
from __future__ import annotations

import copy
from datetime import date, datetime
import json
from zoneinfo import ZoneInfo
import unittest

from validation.macro import v2_zero_mad_ordinal_quality_v1 as q
from validation.macro.v2_g8_observed_feature_bridge_v1 import (
    run as observed_run, ROOT
)


def base():
    # Sep-2024 ... Aug-2026 (24 prior), Sep-2026 (observed current).
    start=2024*12+8
    dates=[f"{(start+i)//12:04d}-{(start+i)%12+1:02d}" for i in range(25)]
    row={"id":"EA_UNEMP_history_value", "dates":dates,
         "values":[6.3]*11+[6.4]*13+[6.5]}
    reg={"series_id":"EA_UNEMP","transformation":"level",
         "frequency":"M","historical_replay_evidence":{
             "macro_series_id":"EA_UNEMP_history_value"}}
    feat={"canonical_series_id":"EA_UNEMP",
          "transformation":"level","frequency":"M",
          "status":"NO_Z_ZERO_ROBUST_DISPERSION",
          "research_robust_z":None,
          "observation_period":"2026-09",
          "eligible_for_macro_score":False,
          "eligible_for_historical_backtest":False}
    return row,reg,feat


class OrdinalZeroMadTests(unittest.TestCase):
    def test_zero_mad_above_prior_max_has_no_numeric_fallback(self):
        row,reg,feat=base()
        out=q.source_quality(row,reg,feat)
        self.assertEqual(out["prior_median"],6.4)
        self.assertEqual(out["strict_prior_MAD"],0)
        self.assertEqual(out["number_of_prior_economic_periods"],24)
        self.assertEqual(out["ordinal_relation"],"ABOVE_ALL_PRIOR")
        self.assertEqual(out["less_than_current_prior_count"],24)
        self.assertEqual(out["equal_to_current_prior_count"],0)
        self.assertEqual(out["midrank_percentile_of_prior"],1.0)
        self.assertAlmostEqual(out["current_minus_prior_median_original_units"],0.1)
        self.assertIsNone(out["numeric_replacement_z"])
        self.assertFalse(out["eligible_for_forward_features"])
        self.assertFalse(out["eligible_for_domestic_activity_weighting"])

    def test_all_equal_prior_and_tied_current_not_fake_momentum(self):
        row,reg,feat=base()
        row["values"]=[6.4]*25
        out=q.source_quality(row,reg,feat)
        self.assertEqual(out["ordinal_relation"],"WITHIN_OR_TIED_PRIOR_RANGE")
        self.assertEqual(out["midrank_percentile_of_prior"],0.5)
        self.assertEqual(out["current_minus_prior_median_original_units"],0)
        self.assertIsNone(out["numeric_replacement_z"])

    def test_lower_than_all_and_duplicate_alias_same_value(self):
        row,reg,feat=base()
        row["values"][-1]=6.2
        row["dates"].append("2026-08-01")
        row["values"].append(6.4)
        out=q.source_quality(row,reg,feat)
        self.assertEqual(out["ordinal_relation"],"BELOW_ALL_PRIOR")
        self.assertEqual(out["midrank_percentile_of_prior"],0)
        self.assertEqual(out["date_precision_aliases_collapsed"],1)

    def test_malformed_source_and_schema_fail_closed(self):
        row,reg,feat=base()
        f=copy.deepcopy(feat)
        f["research_robust_z"]=0
        with self.assertRaisesRegex(ValueError,"model score"):
            q.source_quality(row,reg,f)
        f=copy.deepcopy(feat)
        f["observation_period"]="2026-08"
        with self.assertRaisesRegex(ValueError,"latest economic period"):
            q.source_quality(row,reg,f)
        f=copy.deepcopy(feat)
        f["canonical_series_id"]="FAKE"
        with self.assertRaisesRegex(ValueError,"registry mismatch"):
            q.source_quality(row,reg,f)
        r=copy.deepcopy(row)
        r["dates"].pop(10)
        r["values"].pop(10)
        with self.assertRaisesRegex(ValueError,"incomplete prior"):
            q.source_quality(r,reg,feat)
        r=copy.deepcopy(row)
        r["values"][2]=float("nan")
        with self.assertRaises(ValueError):
            q.source_quality(r,reg,feat)

    def test_non_zero_mad_is_not_replaced(self):
        row,reg,feat=base()
        feat["status"]="DESCRIPTIVE_REVISED_HISTORY_ROBUST_Z_NOT_PIT"
        feat["research_robust_z"]=1.8
        self.assertIsNone(q.source_quality(row,reg,feat))

    def test_readonly_real_observation_never_changes_legacy_or_frozen(self):
        today=datetime.now(ZoneInfo("Europe/Rome")).date()
        protect=[ROOT/"live_data/sections/D.json",
                 ROOT/"live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json",
                 ROOT/"validation/forward/candidate_shadow_snapshots/V2_MACRO_EVIDENCE_SNAPSHOTS_V1.jsonl",
                 ROOT/"validation/forward/decision_snapshots/CORE_DECISION_SNAPSHOTS_V1.jsonl"]
        before={str(p):p.read_bytes() for p in protect}
        obs=observed_run(as_of=today.isoformat())
        series=json.loads(q.SOURCE.read_text())
        reg=json.loads(q.REGISTRY.read_text())
        report=q.build(obs,series,reg,today=today)
        after={str(p):p.read_bytes() for p in protect}
        self.assertEqual(before,after)
        self.assertEqual(report["policy_id"],q.POLICY_ID)
        self.assertEqual(report["strict_numeric_z_imputation_count"],0)
        self.assertTrue(report["existing_macro_v2_strict_z_unchanged"])
        self.assertFalse(report["can_feed_preregistered_H1"])
        self.assertFalse(report["can_write_forward_v2_journal"])
        self.assertFalse(report["allowed_to_create_trading_signal"])
        self.assertTrue(all(x["numeric_replacement_z"] is None
                            for x in report["zero_mad_components"].values()))
        self.assertEqual(set(report["zero_mad_components"]),
                         {k for k,v in obs["inflation_labour"].items()
                          if v["status"]=="NO_Z_ZERO_ROBUST_DISPERSION"})

    def test_future_only_capture_gate_is_not_yet_enabled(self):
        self.assertEqual(q.NOT_BEFORE_ROME,date(2026,11,2))
        report=q.run()
        self.assertFalse(report["can_write_forward_v2_journal"])
        self.assertEqual(report["registration_day_rome"],"2026-10-30")


if __name__=="__main__":
    unittest.main()
