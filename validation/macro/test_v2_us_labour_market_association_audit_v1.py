#!/usr/bin/env python3
"""2026 BLS -> 2Y daily -> first later ECB fixing, observational safeguards."""
import copy
import unittest
from datetime import date

from validation.macro.v2_us_labour_market_association_audit_v1 import (
    SOURCE_FX,SOURCE_RATES,SOURCE_OIS,SOURCE_QUOTES,ROOT,
    dated_series,inventory,read_json,read_lines,run,markdown,
)
from validation.macro.v2_bls_us_u3_2026_shadow_replay_v1 import evidence


def inputs():
    return dict(
        rates=read_json(ROOT,SOURCE_RATES),
        fx=read_json(ROOT,SOURCE_FX),
        ois=read_lines(ROOT,SOURCE_OIS),
        contracts=read_lines(ROOT,SOURCE_QUOTES),
        bls=evidence(),
        as_of=date(2026,10,23),
    )


class BLSReactionAuditTests(unittest.TestCase):
    def test_available_only_association_without_false_event_signal(self):
        r=run()
        self.assertEqual(r["schema"],
                         "GMFQ_MACRO_V2_BLS_DAILY_MARKET_ASSOCIATION_AUDIT_V1")
        self.assertEqual(r["status"],"DESCRIPTIVE_DAILY_ASSOCIATION_ONLY")
        c=r["coverage"]
        self.assertEqual(c["BLS_releases"],9)
        self.assertEqual(c["UST2Y_daily_pairs_with_event_observation"],9)
        self.assertEqual(c["UST2Y_clean_uninterrupted_normal_sessions"],6)
        self.assertEqual(c["UST2Y_problematic_or_multisession"],3)
        self.assertEqual(c["ECB_pre_and_first_later_fixings"],9)
        self.assertEqual(c["ECB_missing_event_day_fixings"],1)
        self.assertEqual(c["OIS_true_release_aligned_windows"],0)
        self.assertEqual(c["BLS_pre_release_consensus_synchronized"],0)
        self.assertEqual(c["intraday_millisecond_aligned_FX_or_rates"],0)
        self.assertEqual(len(r["events"]),9)
        self.assertEqual(r["sources"]["ois_usd_earliest_observed_date"],"2026-10-16")
        for row in r["events"]:
            self.assertEqual(row["consensus_status"],
                             "NOT_AVAILABLE_PRE_RELEASE_NO_SURPRISE_CALCULATED")
            self.assertEqual(row["OIS_event_window_status"],
                             "NO_TIMESTAMPED_HISTORICAL_OIS_QUOTES")
            self.assertIsNone(row["event_causal_conclusion"])
            self.assertIsNone(row["usd_directional_prediction"])
            self.assertFalse(row["tradable_reaction_event"])
            self.assertEqual(row["eurusd_ecb_reference"]["interpretation"],
                             "NEXT_REFERENCE_COMPARISON_NOT_INTRADAY_OR_CAUSAL")
            self.assertEqual(row["ust_2y"]["end_of_day_ust_3_30pm_et_not_intraday_tick"],True)
            self.assertLess(row["eurusd_ecb_reference"]["pre_fixing_day"],
                            row["eurusd_ecb_reference"]["first_later_fixing_day"])
        for k in ("source_market_fixes_independently_verified_at_event",
                  "claim_actual_surprise_against_consensus",
                  "claim_intraday_repricing_or_OIS",
                  "claim_causal_response",
                  "claim_out_of_sample_predictive_effect",
                  "ready_for_economic_fx_strength_model",
                  "eligible_for_backtest",
                  "safe_to_publish_new_D",
                  "safe_to_update_pair_theses","writes_live_data"):
            self.assertFalse(r[k],k)

    def test_ecb_same_day_is_before_bls_never_after(self):
        report=run()
        feb=report["events"][0]
        fx=feb["eurusd_ecb_reference"]
        self.assertEqual(feb["release_day"],"2026-02-11")
        self.assertEqual(fx["pre_fixing_day"],"2026-02-11")
        self.assertEqual(fx["event_date_fixing_role"],"PRE_RELEASE_NOT_RESPONSE")
        self.assertEqual(fx["pre_fixing_eurusd"],1.19)
        self.assertEqual(fx["first_later_fixing_day"],"2026-02-12")
        self.assertEqual(fx["first_later_fixing_eurusd"],1.1874)
        self.assertAlmostEqual(fx["next_fixing_eurusd_change_pct"],-0.21849,places=5)
        self.assertEqual(fx["direction_usd_vs_eur"],"USD_STRONGER")
        self.assertEqual(feb["ust_2y"]["daily_observed_move_bp"],7.0)

    def test_good_friday_ecb_closed_and_us_bonds_thin(self):
        row=run()["events"][2]
        self.assertEqual(row["release_day"],"2026-04-03")
        self.assertEqual(row["ust_2y"]["interpretation"],
                         "HOLIDAY_REDUCED_MARKET_ACTIVITY")
        self.assertEqual(row["eurusd_ecb_reference"]["event_date_fixing_role"],
                         "NONE_MARKET_HOLIDAY")
        self.assertIsNone(row["eurusd_ecb_reference"]["event_date_fixing_if_available"])
        self.assertEqual(row["eurusd_ecb_reference"]["pre_fixing_day"],"2026-04-02")
        self.assertEqual(row["eurusd_ecb_reference"]["first_later_fixing_day"],
                         "2026-04-07")
        self.assertTrue(row["eurusd_ecb_reference"]["extended_interval"])

    def test_july_early_close_is_not_normal_daily_session(self):
        row=run()["events"][5]
        self.assertEqual(row["release_day"],"2026-07-02")
        self.assertEqual(row["ust_2y"]["interpretation"],
                         "HOLIDAY_REDUCED_MARKET_ACTIVITY")
        self.assertIn("EARLY_CLOSE",row["ust_2y"]["session_warning"])

    def test_september_2026_previous_treasury_sample_has_four_day_gap(self):
        x=run()["events"][-1]
        self.assertEqual(x["release_day"],"2026-10-02")
        self.assertEqual(x["ust_2y"]["pre_reference_day"],"2026-09-28")
        self.assertEqual(x["ust_2y"]["pre_gap_calendar_days"],4)
        self.assertEqual(x["ust_2y"]["daily_observed_move_bp"],-9.0)
        self.assertEqual(x["ust_2y"]["interpretation"],
                         "MULTI_SESSION_PRE_REFERENCE")
        self.assertEqual(x["eurusd_ecb_reference"]["pre_fixing_day"],"2026-10-02")
        self.assertEqual(x["eurusd_ecb_reference"]["first_later_fixing_day"],
                         "2026-10-05")
        self.assertAlmostEqual(x["eurusd_ecb_reference"]["next_fixing_eurusd_change_pct"],
                               -0.18708,places=5)

    def test_no_fabricated_treasury_quote_or_ecb_first_later_fixing(self):
        for corrupt in (
            lambda x:x["rates"]["USD"]["history2"]["dates"].remove("2026-10-02"),
            lambda x:x["rates"]["USD"]["history2"]["values"].append(8.0),
            lambda x:x["fx"]["rows"][-1].update(Date="2028-01-01"),
            lambda x:x["fx"]["rows"][0].update(USD=0),
            lambda x:x["bls"]["first_release_values"][8].update(value=6.3),
            lambda x:x["ois"][0].update(backtest_eligible_as_official=True),
            lambda x:x["contracts"][0].update(official_ois_quote=True),
        ):
            with self.subTest(edit=str(corrupt)):
                z=inputs()
                corrupt(z)
                with self.assertRaises(ValueError):
                    inventory(**z)

    def test_no_asof_extrapolation_or_evidence_relabel(self):
        z=inputs()
        z["as_of"]=date(2026,10,24)
        with self.assertRaisesRegex(ValueError,"fixed at 2026-10-23"):
            inventory(**z)
        q=inputs()
        q["rates"]["USD"]["quality"]="RESEARCH_ESTIMATED"
        with self.assertRaisesRegex(ValueError,"Treasury 2Y current source"):
            inventory(**q)
        q=inputs()
        q["fx"]["source"]="Not the ECB"
        with self.assertRaisesRegex(ValueError,"ECB daily EUR/USD"):
            inventory(**q)

    def test_no_deceptive_simple_macro_correlation_or_trade_conclusion(self):
        report=run()
        text=markdown(report)
        self.assertIn("No pre-release consensus",text)
        self.assertIn("ECB event-day fixing is BEFORE BLS",text)
        self.assertIn("No OIS event-window data",text)
        self.assertIn("No model promotion",text)
        self.assertNotIn("Sharpe",text)
        self.assertNotIn("profit",text)
        self.assertEqual(report,run(),"the audit must be deterministic")
        self.assertEqual(len(report["method_fingerprint_sha256"]),64)


if __name__=="__main__":
    unittest.main()
