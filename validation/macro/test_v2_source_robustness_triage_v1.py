#!/usr/bin/env python3
"""Adversarial, completely offline tests for the Macro V2 research triage."""
import copy
import math
import unittest

from validation.macro.v2_g8_24_axis_training_history_gap_audit_v1 import SCHEMA as GAP
from validation.macro.v2_domestic_candidate_explicit_formula_v1 import (
    G8, SCHEMA as CANDIDATE, activity_class, continuous_weight_interval,
    independent_axis_revision_envelope,
)
from validation.macro.v2_source_robustness_triage_v1 import (
    SCHEMA, boundary_distance, build,
)

PILLARS=("growth","labour","inflation")


def fixtures():
    slots={}
    for c in G8:
        for p in PILLARS:
            k=c+"."+p
            missing=(["2025-10"] if k=="USD.inflation" else
                     ["2024-09","2024-10"] if k=="CHF.labour" else [])
            caveat=["ORIGINAL_SOURCE_DEFINITION_REVIEW_REQUIRED"] if k=="EUR.inflation" else []
            slots[k]={
                "slot":k,"currency":c,"pillar":p,
                "published_observation_frequency":"Q" if p=="growth" else "M",
                "reference_period_last_first_web":"2026-09",
                "prior_first_release_periods_required":12 if p=="growth" else 24,
                "missing_required_prior_periods":missing,
                "prior_initial_web_sequence_complete_mathematically":not missing,
                "current_PIT_research_comparability_caveats":caveat,
                "research_only_quality_label":"INCOMPLETE_PRIOR_FIRST_RELEASES" if missing else
                    "DEFINITION_OR_SEMANTIC_RISK" if caveat else
                    "NUMERIC_WEB_WINDOW_AVAILABLE_NOT_PIT_CERTIFIED",
                "model_PIT_training_approved":False,
                "FX_signal_approved":False,
                "complete_source_day_original_bytes_and_revision_chain_certified":False,
            }
    gap={
        "schema":GAP,"as_of_utc":"2026-10-26T23:59:59+00:00",
        "safe_to_publish_new_D":False,"safe_to_recalculate_28_pairs":False,
        "summary":{
            "genuinely_historic_PIT_training_slots_certified":0,
            "prior_first_web_contiguous_12Q_or_24M_slots":22,
            "missing_required_prior_periods_total":3,
        },"slots":slots,
    }
    rows={}
    current={}
    for c in G8:
        g,l=(0.1,1.1) if c=="CHF" else (1.1,1.1)
        interval=continuous_weight_interval(g,l)
        stress={str(int(v*100)):independent_axis_revision_envelope(g,l,v)
                for v in (.10,.25,.50)}
        rows[c]={
            "growth_within_history_z":g,
            "unemployment_tightness_within_history_z":l,
            "domestic_activity_class":activity_class(.5*(g+l)),
            "activity_class_stable_across_25_50_75pct_growth":
                interval["classification_unchanged_at_every_weight_in_interval"],
            "continuous_weight_sensitivity_RESEARCH_ONLY":interval,
            "hypothetical_axis_revision_stress_RESEARCH_ONLY":stress,
            "source_quality_flags":[],
        }
        current[c]={"axes":{p:{"z_available_for_RESEARCH_ONLY":True}
                             for p in PILLARS},
                    "complete_three_axis_research_candidate":True}
    candidate={
        "schema":CANDIDATE,"economic_as_of":"2026-10-27",
        "safe_to_publish_D":False,"safe_to_update_pair_theses":False,
        "writes_live_data":False,
        "summary":{"FX_scores_produced":0,"axes":24,"currencies":8},
        "countries":rows,
    }
    readiness={
        "schema":"GMFQ_MACRO_V2_G8_CURRENT_SOURCE_READINESS_V1",
        "as_of":"2026-10-31","eligible_to_publish_D":False,
        "eligible_to_recompute_28_pairs":False,
        "historical_PIT_or_OOS_validated":False,
        "no_missing_z_substituted":True,"currencies_blocked":0,
        "countries":current,
    }
    return gap,candidate,readiness


class MacroTriageTests(unittest.TestCase):
    def test_exact_boundary_geometry_with_continuous_weights(self):
        self.assertAlmostEqual(boundary_distance(1,1),0.5)
        self.assertAlmostEqual(boundary_distance(0,0),0.5)
        self.assertAlmostEqual(boundary_distance(-1,-1),0.5)
        self.assertEqual(boundary_distance(0.1,1.1),0.0)
        self.assertAlmostEqual(boundary_distance(.6,.6),.1)
        self.assertEqual(boundary_distance(.5,.5),0)
        # At 0.10, the firm label is exactly on its class boundary.
        self.assertTrue(independent_axis_revision_envelope(.6,.6,.10)[
            "class_invariant_to_all_weights_and_independent_axis_shifts"])
        # This is a distance to a boundary, not an estimated probability.
        for bad in (True,float("nan"),float("inf"),3.1):
            with self.assertRaises(ValueError):
                boundary_distance(bad,0)

    def test_dated_source_queue_and_candidate_are_not_mixed(self):
        a,b,c=fixtures()
        result=build(a,b,c)
        self.assertEqual(result["schema"],SCHEMA)
        self.assertEqual(result["summary"]["mathematically_contiguous_windows"],22)
        self.assertEqual(result["summary"]["missing_window_axes"],
                         ["CHF.labour","USD.inflation"])
        self.assertEqual(result["source_work_queue"][0]["key"],"CHF.labour")
        self.assertEqual(result["source_work_queue"][1]["key"],"USD.inflation")
        self.assertEqual(result["summary"]["candidate_countries_weight_ambiguous"],1)
        self.assertEqual(result["countries"]["CHF"][
            "exact_boundary_distance_z_hypothetical_not_empirical"],0.0)
        self.assertEqual(result["historical_source_evidence_asof"],
                         "2026-10-26T23:59:59+00:00")
        self.assertEqual(result["current_input_readiness_asof"],"2026-10-31")
        self.assertTrue(result["snapshots_are_not_synchronous_and_cannot_be_joined_into_backtest"])
        self.assertEqual(result["summary"]["fully_certified_historical_PIT_axes"],0)
        self.assertFalse(result["safe_to_publish_new_D"])
        self.assertFalse(result["safe_to_recalculate_28_pairs"])
        self.assertFalse(result["safe_to_use_for_beta_or_forward"])
        self.assertFalse(result["writes_live_data"])

    def test_missing_current_z_is_reported_but_not_replaced(self):
        gap,candidate,ready=fixtures()
        ready["countries"]["EUR"]["axes"]["labour"]["z_available_for_RESEARCH_ONLY"]=False
        ready["countries"]["EUR"]["complete_three_axis_research_candidate"]=False
        ready["currencies_blocked"]=1
        result=build(gap,candidate,ready)
        self.assertEqual(result["countries"]["EUR"]["current_blocked_research_axes"],["labour"])
        self.assertEqual(result["summary"]["current_research_input_blocked_countries"],1)
        self.assertFalse(result["safe_to_publish_new_D"])

    def test_rejects_pit_fraud_or_incoherent_24_sources(self):
        for path,value in [
            (("gap","safe_to_publish_new_D"),True),
            (("gap","slots","CHF.labour","model_PIT_training_approved"),True),
            (("gap","slots","USD.inflation","prior_initial_web_sequence_complete_mathematically"),True),
            (("gap","summary","genuinely_historic_PIT_training_slots_certified"),1),
            (("candidate","safe_to_update_pair_theses"),True),
            (("candidate","countries","USD","growth_within_history_z"),float("nan")),
            (("ready","eligible_to_recompute_28_pairs"),True),
            (("ready","countries","NZD","complete_three_axis_research_candidate"),False),
        ]:
            with self.subTest(path=path):
                a,b,c=fixtures()
                obj={"gap":a,"candidate":b,"ready":c}[path[0]]
                for k in path[1:-1]:
                    obj=obj[k]
                obj[path[-1]]=value
                with self.assertRaises((ValueError,TypeError)):
                    build(a,b,c)


if __name__=="__main__":
    unittest.main()
