"""No-writing preflight tests of actual source shapes and adversarial tampering."""
import copy
from datetime import date, datetime, timezone
import json
import unittest

from validation.forward import audit_quality_aware_preflight_v1 as audit
from validation.forward.capture_v2_quality_aware_prospective_v1 import ROOT, SOURCE_PATHS
from validation.forward.v2_quality_market_context_v1 import build as market_build
from validation.macro.v2_g8_observed_feature_bridge_v1 import run as observed_run
from validation.macro.v2_us_shutdown_2025_calendar_gap_v1 import audit as us_audit
from validation.macro.v2_zero_mad_ordinal_quality_v1 import (
    build as ordinal_build, SOURCE as SERIES, REGISTRY,
)


class QualityAwarePreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.now = datetime(2026, 10, 31, 12, 30, tzinfo=timezone.utc)
        cls.day = "2026-10-31"
        load = lambda key: json.loads((ROOT / SOURCE_PATHS[key]).read_text())
        cls.fx = load("ecb")
        cls.pairs = load("pair_setup")
        cls.observed = observed_run(as_of=cls.day)
        series=json.loads(SERIES.read_text())
        registry=json.loads(REGISTRY.read_text())
        cls.us_shutdown=us_audit(series,registry,cls.observed,checked_as_of=cls.day)
        cls.ordinal = ordinal_build(
            cls.observed,
            json.loads(SERIES.read_text()),
            json.loads(REGISTRY.read_text()),
            today=date.fromisoformat(cls.day),
        )
        cls.market = market_build(
            cls.day,load("rates"),load("ois"),load("banks"),
            load("nzd_proxy"),cls.pairs
        )

    def inspect(self, **kwargs):
        data = {key:copy.deepcopy(getattr(self,key)) for key
                in ("now","fx","pairs","observed","ordinal","market","us_shutdown")}
        data.update(kwargs)
        return audit.inspect(**data)

    def test_all_24_sources_with_zero_MAD_and_no_fake_weekend_freeze(self):
        out=self.inspect()
        self.assertEqual(out["economic_research_dimensions"],24)
        self.assertEqual(out["market_context_pairs"],28)
        self.assertEqual(out["source_quality_graded_market_currencies"],8)
        self.assertEqual(out["status"],"NOT_BEFORE_REGISTERED_FIRST_REAL_CAPTURE")
        self.assertFalse(out["official_same_day_ECB_T0_observed"])
        self.assertFalse(out["future_snapshot_captured_now"])
        self.assertFalse(out["forecast_FX_accuracy_claimed"])
        self.assertFalse(out["safe_to_capture_without_real_time_admission"])
        self.assertFalse(out["historical_PIT_validated"])
        self.assertEqual(out["ordinal_context_only_slots"],["EUR.labour"])
        self.assertIn("EUR.labour",out["current_strict_z_missing_slots"])
        self.assertTrue(out["current_USD_inflation_missing_Oct2025_source_PIT_not_repaired"])
        self.assertTrue(out["current_USD_labour_missing_Oct2025_CPS_PIT_not_repaired"])
        self.assertEqual(out["US_oct2025_unpublished_source_calendar_gap"]["strict_24_calendar_missing_slots"],
                         ["USD.inflation","USD.labour"])
        self.assertTrue(out["current_CHF_labour_first_SNB_precision_PIT_not_repaired"])

    def test_rejects_source_promotion_or_fake_data(self):
        for source,path,value in (
            ("observed",("safe_to_publish_new_D",),True),
            ("observed",("inflation_labour","EUR.labour","research_robust_z"),0),
            ("ordinal",("strict_numeric_z_imputation_count",),1),
            ("ordinal",("zero_mad_components","EUR.labour","numeric_replacement_z"),2),
            ("market",("summary","FX_scores"),1),
            ("us_shutdown",("slots","USD.labour","oct_2025_observation_exists"),True),
            ("us_shutdown",("slots","USD.inflation","prior_24_missing_periods"),[]),
            ("market",("summary","28_pairs"),27),
            ("pairs",("pair_count",),27),
            ("fx",("last_as_of",),"2026-10-30" if self.fx["last_as_of"]!="2026-10-30" else "2026-10-29"),
        ):
            with self.subTest(source=source,path=path):
                node=copy.deepcopy(getattr(self,source))
                parent=node
                for k in path[:-1]:
                    parent=parent[k]
                parent[path[-1]]=value
                with self.assertRaises((ValueError,TypeError)):
                    self.inspect(**{source:node})

    def test_actual_read_only_function_does_not_create_snapshot(self):
        result=audit.run(now=self.now)
        self.assertEqual(result["schema"],audit.SCHEMA)
        self.assertFalse(result["future_snapshot_captured_now"])
        self.assertFalse(result["current_D_or_28_pair_score_changed"])


if __name__ == "__main__":
    unittest.main()
