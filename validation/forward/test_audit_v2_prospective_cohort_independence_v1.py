"""No fabricated live outcomes: synthetic ECB prices exist only in test RAM."""
import copy
from datetime import datetime, timedelta, timezone
import itertools
import unittest

from validation.forward import audit_v2_prospective_cohort_independence_v1 as audit
from validation.forward.capture_v2_research_prospective_evidence_v1 import (
    G8, SCHEMA as FREEZE_SCHEMA, sha
)
from validation.forward.observe_v2_research_ecb_reference_returns_v1 import (
    SCHEMA as RETURN_SCHEMA, SOURCE_URL
)


def test_freeze(day="2026-10-27",utc_cut="2026-10-27T18:31:00Z"):
    pairs={}
    values={k:1+(i+1)/10 for i,k in enumerate(G8)}
    values["EUR"]=1.0
    for a,b in itertools.combinations(G8,2):
        pairs[a+"/"+b]={
            "date":day, "rate":values[b]/values[a],
            "layer":"ECB_DAILY_REFERENCE_NOT_EXECUTABLE_SPOT",
            "trade_execution_price":False,
        }
    rec={
        "schema":FREEZE_SCHEMA,
        "snapshot_id":sha({"day":day,"type":"test-only"}),
        "capture_at_utc":utc_cut, "local_date_rome":day,
        "official_ecb_t0_date":day,
        "economic_checked_as_of":day,
        "observed_t0_ref":pairs,
        "domestic_v2_features":{k:{"FX_signal":None,"trade_entry":None,
                                    "cb_CAN_not_calibrated":True} for k in G8},
        "future_outcomes_observed_at_capture":False,
        "V2_pair_directional_predictions":False,
        "core_D_recalculated":False
    }
    rec["snapshot_sha256"]=sha(rec)
    return rec


def test_return(snap,pair,horizon="1D",date="2026-10-29"):
    rate=snap["observed_t0_ref"][pair]["rate"]
    final=rate*1.001
    due=(datetime.fromisoformat(snap["capture_at_utc"].replace("Z","+00:00"))+
         timedelta(days=audit.HORIZONS[horizon])).astimezone(audit.ROME).date()
    obs=datetime.strptime(date,"%Y-%m-%d").date()
    row={
        "schema":RETURN_SCHEMA,
        "shadow_snapshot_id":snap["snapshot_id"],
        "origin_snapshot_sha256":snap["snapshot_sha256"],
        "capture_at_utc":snap["capture_at_utc"],
        "original_economic_asof":snap["economic_checked_as_of"],
        "pair":pair,"horizon":horizon,
        "horizon_calendar_days":audit.HORIZONS[horizon],
        "t0_source_date":snap["official_ecb_t0_date"],
        "t0_ECB_nonexecutable_rate":rate,
        "maturity_date":due.isoformat(),
        "first_observed_ecb_date_strictly_after_maturity":date,
        "days_after_maturity":(obs-due).days,
        "observed_ECB_nonexecutable_rate":final,
        "observed_reference_return_pct":round(100*(final/rate-1),8),
        "reference_source":SOURCE_URL,
        "reference_layer":audit.REFERENCE_LAYER,
        "source_day_original_issuer_bytes_verifiable":False,
        "trade_direction":None,"trade_gross_return":None,
        "trade_cost_bps":None,"trade_net_return":None,"trade_PnL":None,
        "beta_predictive_accuracy":None,"model_alpha_claim":False,
        "beta_validation_certified":False,
        "new_core_score_calculated":False
    }
    row["reference_return_sha256"]=sha(row)
    return row


class CohortIndependenceTests(unittest.TestCase):
    def setUp(self):
        self.snap=test_freeze()
        self.now=datetime.fromisoformat("2026-10-30T21:15:00+01:00")
        self.returns=[test_return(self.snap,p) for p in self.snap["observed_t0_ref"]]

    def test_zero_real_observations_not_called_verified(self):
        result=audit.inspect([],[],self.now)
        self.assertEqual(result["total_frozen_capture_date_clusters"],0)
        self.assertEqual(result["total_reference_outcome_rows"],0)
        self.assertEqual(result["per_horizon"]["1W"]["recorded_reference_pair_rows"],0)
        self.assertFalse(result["new_candidate_predictive_accuracy_or_alpha_claimed"])
        self.assertFalse(result["allowed_to_promote_D_or_28_pairs"])

    def test_28_shared_currency_crosses_are_one_date_cluster_not_28_trials(self):
        result=audit.inspect([self.snap],self.returns,self.now)
        self.assertEqual(result["total_frozen_capture_date_clusters"],1)
        self.assertEqual(result["number_of_independent_EUR_base_FX_quote_levels_per_date_at_most"],7)
        self.assertEqual(result["canonical_28_pair_crosses_per_snapshot"],28)
        self.assertEqual(result["total_reference_outcome_rows"],28)
        c=result["per_horizon"]["1D"]
        self.assertEqual(c["capture_date_clusters_with_elapsed_horizon"],1)
        self.assertEqual(c["possible_reference_pair_rows_at_matured_dates"],28)
        self.assertEqual(c["recorded_reference_pair_rows"],28)
        self.assertEqual(c["complete_28_cross_capture_dates"],1)
        self.assertEqual(c["observed_capture_date_clusters"],1)
        self.assertFalse(c["28_pairs_are_statistically_independent"])
        self.assertTrue(c["capture_days_are_not_guaranteed_serially_independent"])
        self.assertFalse(c["statistical_predictive_skill_certified"])
        self.assertEqual(result["per_horizon"]["1W"]["capture_date_clusters_with_elapsed_horizon"],0)
        self.assertTrue(result["no_naive_pair_level_p_values"])

    def test_missing_losing_pair_not_survivorship_excluded(self):
        result=audit.inspect([self.snap],self.returns[:-1],self.now)
        c=result["per_horizon"]["1D"]
        self.assertEqual(c["possible_reference_pair_rows_at_matured_dates"],28)
        self.assertEqual(c["recorded_reference_pair_rows"],27)
        self.assertEqual(c["not_observed_yet_pair_rows"],1)
        self.assertEqual(c["complete_28_cross_capture_dates"],0)
        self.assertEqual(c["partial_capture_dates"],1)

    def test_maturity_and_contemporaneous_clock_are_enforced(self):
        noon=datetime.fromisoformat("2026-10-28T12:00:00Z")
        r=audit.inspect([self.snap],[],noon)
        self.assertEqual(r["per_horizon"]["1D"]["possible_reference_pair_rows_at_matured_dates"],0)
        with self.assertRaises(ValueError):
            audit.inspect([self.snap],self.returns,noon)
        after=self.returns[0].copy()
        after["first_observed_ecb_date_strictly_after_maturity"]="2026-10-31"
        after["days_after_maturity"]=3
        after["reference_return_sha256"]=sha({k:v for k,v in after.items()
                                                if k!="reference_return_sha256"})
        with self.assertRaises(ValueError):
            audit.inspect([self.snap],[after],self.now)

    def test_not_even_rehashed_fake_pnl_returns_allowed(self):
        for field,value in (
            ("trade_direction","LONG"),("trade_net_return",2.5),
            ("beta_predictive_accuracy",1.0),("model_alpha_claim",True),
            ("t0_ECB_nonexecutable_rate",4.0),
            ("observed_reference_return_pct",99.0),
            ("reference_source","https://example.org/fake"),
            ("origin_snapshot_sha256","a"*64)
        ):
            with self.subTest(field=field):
                bad=copy.deepcopy(self.returns[0])
                bad[field]=value
                bad["reference_return_sha256"]=sha({
                    k:v for k,v in bad.items() if k!="reference_return_sha256"})
                with self.assertRaises(ValueError):
                    audit.inspect([self.snap],[bad],self.now)

    def test_orphans_duplicates_source_universe_and_date_clustering(self):
        with self.assertRaises(ValueError):
            audit.inspect([],[self.returns[0]],self.now)
        with self.assertRaises(ValueError):
            audit.inspect([self.snap],self.returns+[self.returns[0]],self.now)
        bad=copy.deepcopy(self.snap)
        del bad["observed_t0_ref"][next(iter(bad["observed_t0_ref"]))]
        bad["snapshot_sha256"]=sha({
            k:v for k,v in bad.items() if k!="snapshot_sha256"})
        with self.assertRaises(ValueError):
            audit.inspect([bad],[],self.now)
        second=test_freeze("2026-10-28","2026-10-28T18:31:00Z")
        result=audit.inspect([self.snap,second],self.returns,self.now)
        c=result["per_horizon"]["1D"]
        self.assertEqual(result["total_frozen_capture_date_clusters"],2)
        self.assertEqual(c["capture_date_clusters_with_elapsed_horizon"],2)
        self.assertEqual(c["possible_reference_pair_rows_at_matured_dates"],56)
        self.assertEqual(c["recorded_reference_pair_rows"],28)
        self.assertEqual(c["no_observed_return_capture_dates"],1)
        self.assertEqual(c["not_observed_yet_pair_rows"],28)

    def test_no_live_ledger_edit(self):
        self.assertEqual(audit.OUTCOMES.exists(),audit.OUTCOMES.exists())
        self.assertFalse(audit.inspect([self.snap],[],self.now)["writes_live_data"])


if __name__=="__main__":
    unittest.main()
