import copy
import json
import math
import unittest
from datetime import date

from validation.macro.v2_g8_growth_rolling_pit_normalization_v1 import (
    descriptor, same_math_cohort, group_contract,
    rolling_research_normalization, SNAPSHOT_METHOD,
)
from validation.macro.v2_g8_growth_transform_proposal_gate_v1 import FILE
from validation.macro.v2_shadow_features_v1 import period_index


class FrozenAsOfRollingGrowthNormalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proposals={p["currency"]:p for p in
             json.loads(FILE.read_text(encoding="utf-8"))["feature_proposals"]}

    def stamp(self,cc,ref,value,*,time=None):
        p=descriptor(self.proposals[cc])
        if p["frequency"]=="M":
            y,m=map(int,ref.split("-"))
            y2,m2=(y+1,1) if m==12 else (y,m+1)
            default=f"{y2:04d}-{m2:02d}-01T00:00:00Z"
        else:
            y,q=int(ref[:4]),int(ref[-1])
            # A synthetic release in the second month following each quarter.
            y2,m2=(y+1,2) if q==4 else (y,q*3+2)
            default=f"{y2:04d}-{m2:02d}-01T00:00:00Z"
        return {
            "currency":cc,
            "source_series_id":p["source_series_id"],
            "frequency":p["frequency"],
            "economic_family":p["economic_family"],
            "horizon":p["horizon"],
            "feature_method":p["transform"],
            "snapshot_method":SNAPSHOT_METHOD,
            "reference_period":ref,
            "frozen_at_utc":time or default,
            "feature_percent":value,
            "recomputed_using_later_vintages":False,
            "source_original_day_archive_verified":False,
            "certified_for_macro_scoring":False,
        }

    def month(self,index):
        return f"{index//12:04d}-{index%12+1:02d}"

    def quarter(self,index):
        return f"{index//4:04d}Q{index%4+1}"

    def cases(self,cc,current_period,values):
        p=descriptor(self.proposals[cc])
        idx=period_index(current_period,p["frequency"])
        encode=self.month if p["frequency"]=="M" else self.quarter
        required=p["historical_train_count"]
        history=[self.stamp(cc,encode(idx-required+i),v)
                 for i,v in enumerate(values)]
        current=self.stamp(cc,current_period,13.0)
        cutoff="2026-12-31T23:59:59Z"
        return current,history,cutoff

    def test_five_industry_countries_distinct_from_cad_gdp_aud_nzd(self):
        cohorts=group_contract()
        self.assertEqual(cohorts["mathematically_distinct_cohort_count"],4)
        self.assertEqual(cohorts["observed_growth_series_reviewed"],8)
        self.assertFalse(cohorts["cross_currency_growth_rank_approved"])
        self.assertFalse(cohorts["within_cohort_country_calibration_approved"])
        self.assertTrue(cohorts["nzd_yoy_requires_independent_qoq_source_or_same_vintage_level_bridge"])
        self.assertTrue(cohorts["quarter_end_rolling_3m3m_is_not_automatic_gdp_qoq_equivalence"])
        self.assertTrue(same_math_cohort(self.proposals["USD"],self.proposals["EUR"]))
        self.assertTrue(same_math_cohort(self.proposals["EUR"],self.proposals["JPY"]))
        self.assertFalse(same_math_cohort(self.proposals["USD"],self.proposals["CAD"]))
        self.assertFalse(same_math_cohort(self.proposals["CHF"],self.proposals["AUD"]))
        self.assertFalse(same_math_cohort(self.proposals["CAD"],self.proposals["NZD"]))
        self.assertFalse(same_math_cohort(self.proposals["AUD"],self.proposals["NZD"]))

    def test_monthly_25_prior_frozen_periods_then_new_current_is_research_math(self):
        cur,history,cutoff=self.cases("USD","2026-09",list(range(-12,13)))
        self.assertEqual(len(history),25)
        result=rolling_research_normalization(self.proposals["USD"],cur,history,as_of=cutoff)
        self.assertEqual(result["historical_train_count_required"],25)
        self.assertEqual(result["historical_relevant_prior_features_visible"],25)
        self.assertEqual(result["status"],"RESEARCH_ROLLING_Z_MATH_ONLY_UNVERIFIED_VINTAGES")
        self.assertEqual(result["research_rolling_mean_pct"],0.0)
        self.assertAlmostEqual(result["research_rolling_std_pct"],math.sqrt(52),places=12)
        self.assertAlmostEqual(result["research_rolling_z"],13/math.sqrt(52),places=12)
        self.assertEqual(result["historical_train_reference_periods"][0],"2024-08")
        self.assertEqual(result["historical_train_reference_periods"][-1],"2026-08")
        self.assertFalse(result["source_feature_snapshots_independently_authenticated"])
        self.assertFalse(result["usable_for_macro_score"])
        self.assertFalse(result["usable_for_backtest"])
        self.assertFalse(result["safe_to_update_pair_theses"])

    def test_25_training_snapshots_not_including_current_nor_any_future_period(self):
        cur,history,cutoff=self.cases("USD","2026-09",list(range(25)))
        r=rolling_research_normalization(self.proposals["USD"],cur,history[:-1],as_of=cutoff)
        self.assertEqual(r["status"],"INSUFFICIENT_CONSECUTIVE_FROZEN_PRIOR_FEATURES")
        self.assertIsNone(r["research_rolling_z"])
        extra=self.stamp("USD","2026-10",150)
        with self.assertRaises(ValueError):
            rolling_research_normalization(self.proposals["USD"],cur,history+[extra],as_of=cutoff)
        # Even when supplied, an observation made available after the current
        # feature is excluded rather than retroactively re-fitting the past.
        revised=copy.deepcopy(history)
        revised[-1]["frozen_at_utc"]="2026-11-01T00:00:00Z"
        with self.assertRaises(ValueError):
            rolling_research_normalization(self.proposals["USD"],cur,revised,as_of=cutoff)

    def test_full_same_quarter_yoy_does_not_normalize_with_aud_qoq(self):
        cur,hist,cutoff=self.cases("NZD","2026Q3",list(range(13)))
        r=rolling_research_normalization(self.proposals["NZD"],cur,hist,as_of=cutoff)
        self.assertEqual(r["historical_train_count_required"],13)
        self.assertEqual(r["status"],"RESEARCH_ROLLING_Z_MATH_ONLY_UNVERIFIED_VINTAGES")
        self.assertAlmostEqual(r["research_rolling_mean_pct"],6)
        self.assertAlmostEqual(r["research_rolling_std_pct"],math.sqrt(14))
        self.assertEqual(r["horizon"],"SAME_QUARTER_PREVIOUS_YEAR")
        mismatch=copy.deepcopy(hist);mismatch[0]["horizon"]="QUARTER_ON_QUARTER"
        with self.assertRaises(ValueError):
            rolling_research_normalization(self.proposals["NZD"],cur,mismatch,as_of=cutoff)
        with self.assertRaises(ValueError):
            rolling_research_normalization(self.proposals["AUD"],cur,hist,as_of=cutoff)

    def test_zero_variance_and_nonconsecutive_quarters_do_not_produce_fake_z(self):
        cur,hist,cutoff=self.cases("AUD","2026Q3",[2.0]*13)
        r=rolling_research_normalization(self.proposals["AUD"],cur,hist,as_of=cutoff)
        self.assertEqual(r["status"],"ZERO_OR_NEAR_ZERO_FROZEN_HISTORY_VARIANCE")
        self.assertIsNone(r["research_rolling_z"])
        other=copy.deepcopy(hist)
        other[5]["reference_period"]="2019Q2"
        other[5]["frozen_at_utc"]="2019-08-01T00:00:00Z"
        r=rolling_research_normalization(self.proposals["AUD"],cur,other,as_of=cutoff)
        self.assertEqual(r["status"],"INSUFFICIENT_CONSECUTIVE_FROZEN_PRIOR_FEATURES")
        self.assertIsNone(r["research_rolling_z"])

    def test_no_lookahead_and_bad_revision_or_scoring_flags_fail_closed(self):
        cur,hist,cutoff=self.cases("USD","2026-09",list(range(25)))
        invalid=[
            ("history_future",24,"frozen_at_utc","2027-01-01T00:00:00Z"),
            ("history_naive",0,"frozen_at_utc","2024-09-01T10:00:00"),
            ("history_recompute",12,"recomputed_using_later_vintages",True),
            ("history_claim_proven",7,"source_original_day_archive_verified",True),
            ("history_score",10,"certified_for_macro_scoring",True),
            ("history_other_fx",4,"currency","GBP"),
            ("history_bad_horizon",2,"horizon","QUARTER_ON_QUARTER"),
            ("history_nonfinite",6,"feature_percent",float("nan")),
            ("history_true",6,"feature_percent",True),
            ("history_method",6,"snapshot_method","TODAY_REVISED_REPLAY"),
        ]
        for name,index,key,value in invalid:
            arr=copy.deepcopy(hist)
            arr[index][key]=value
            with self.subTest(name=name):
                with self.assertRaises((ValueError,TypeError)):
                    rolling_research_normalization(self.proposals["USD"],cur,arr,as_of=cutoff)
        with self.assertRaises(ValueError):
            rolling_research_normalization(self.proposals["USD"],cur,hist,
                                          as_of="2026-09-30T23:59:59Z")
        obj=copy.deepcopy(cur);obj["feature_method"]="REPORTED_YOY_RATE"
        with self.assertRaises(ValueError):
            rolling_research_normalization(self.proposals["USD"],obj,hist,as_of=cutoff)

    def test_breach_on_duplicate_reference_and_inverted_freeze_order(self):
        cur,hist,cutoff=self.cases("USD","2026-09",list(range(25)))
        duplicate=copy.deepcopy(hist)
        duplicate[1]["reference_period"]=duplicate[0]["reference_period"]
        with self.assertRaises(ValueError):
            rolling_research_normalization(self.proposals["USD"],cur,duplicate,as_of=cutoff)
        later=copy.deepcopy(hist)
        later[5]["frozen_at_utc"]=hist[7]["frozen_at_utc"]
        with self.assertRaises(ValueError):
            rolling_research_normalization(self.proposals["USD"],cur,later,as_of=cutoff)

    def test_never_mutate_input_or_call_live_data_and_research_only_reproducible(self):
        cur,hist,cutoff=self.cases("EUR","2026-09",list(range(-12,13)))
        snap=copy.deepcopy(cur);vintages=copy.deepcopy(hist)
        a=rolling_research_normalization(self.proposals["EUR"],cur,hist,as_of=cutoff)
        b=rolling_research_normalization(self.proposals["EUR"],cur,hist,as_of=cutoff)
        self.assertEqual(a,b)
        self.assertEqual(cur,snap)
        self.assertEqual(hist,vintages)
        for k in ("source_feature_snapshots_independently_authenticated",
                  "original_publication_bytes_certified","full_historical_revisions_certified",
                  "cross_country_economic_comparability_certified",
                  "usable_for_macro_score","usable_for_backtest",
                  "safe_to_publish_new_D","safe_to_update_pair_theses",
                  "writes_live_data"):
            self.assertFalse(a[k])


if __name__=="__main__":
    unittest.main()
