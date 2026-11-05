#!/usr/bin/env python3
"""Deterministic tests of the FXV2 08:00 public delivery evidence policy."""
import datetime as dt
import unittest
from zoneinfo import ZoneInfo
from check_fxv2_morning_public_v1 import FILES, RESEARCH_REQUIRED, evaluate, attach_source_evidence, research_sources_usable

ROME = ZoneInfo("Europe/Rome")
SHA = "a" * 64


def rows():
    return [{"path": name, "http": 200, "status": "MATCH",
             "expected_sha256": SHA, "public_sha256": SHA} for name in FILES]


class MorningProofTest(unittest.TestCase):
    def test_joint_public_delivery_and_source_gaps_are_separate(self):
        public = evaluate(dt.datetime(2026, 11, 5, 7, 50, tzinfo=ROME), rows())
        checks = [
            {"area": "governments", "item": c, "as_of": "2026-11-04",
             "state": "ON_CADENCE"}
            for c in ["USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"]
        ] + [
            {"area": "ois_v2_research_tenor", "item": c + " " + t,
             "as_of": "2026-11-04", "state": "ON_CADENCE"}
            for c in ["USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"]
            for t in ["3m", "6m", "12m"]
        ] + [
            {"area": "positioning", "item": c+" CFTC weekly",
             "as_of": "2026-10-27", "state": "ON_CADENCE"}
            for c in ["USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"]
        ] + [
            {"area": area, "item": item, "as_of": "2026-11-04",
             "state": "ON_CADENCE"}
            for area,items in RESEARCH_REQUIRED.items() for item in sorted(items)
        ]
        audit = {"schema": "GMFQ_FXV2_FRESHNESS_AUDIT_V1",
                 "as_of_rome": "2026-11-05",
                 "status": "DATA_GAPS_PRESENT",
                 "summary": {"checks": len(checks), "v2_pages": 12, "fx_pairs": 28,
                             "gaps": 4, "late_or_invalid": 3},
                 "checks": checks, "hard_errors": []}
        decision = {"schema": "GMFQ_FXV2_READINESS_DUAL_TRACK_V1",
                    "as_of_rome": "2026-11-05",
                    "research": {"website_pages": 12, "rate_pricing_horizons": 24,
                                 "state": "AVAILABLE_WITH_SOURCE_QUALITY_LIMITS"},
                    "trading_core": {"pair_count": 28,
                                     "state": "NOT_REVALIDATED_FROM_RESEARCH",
                                     "baseline_macro_as_of": "2026-09-25"}}
        mixed = attach_source_evidence(public, audit, decision)
        self.assertTrue(mixed["on_time_proven"])
        self.assertFalse(mixed["all_sections_ready_with_current_data"])
        self.assertEqual(mixed["source_evidence"]["unresolved_gaps"], 4)
        self.assertEqual(len(mixed["source_evidence"]["canonical_gov_as_of"]), 8)
        self.assertEqual(sum(map(len, mixed["source_evidence"]["pricing_tenor_as_of"].values())), 24)
        self.assertEqual(mixed["joint_status"], "PUBLIC_BY_0800_RESEARCH_AVAILABLE_CORE_SOURCE_GAPS_VISIBLE")
        self.assertTrue(mixed["research_usable_by_0800"])
        self.assertTrue(mixed["source_evidence"]["research_sources_on_cadence"])
        self.assertFalse(mixed["source_evidence"]["data_currentness_proven"])
        self.assertEqual(mixed["source_evidence"]["trading_core_readiness"],
                         "NOT_REVALIDATED_FROM_RESEARCH")
        self.assertEqual(mixed["source_evidence"]["macro_legacy_baseline_as_of"], "2026-09-25")
        self.assertFalse(mixed["signal_model_revalidated"])
        audit["status"] = "DATE_CHECKS_PASS"
        audit["summary"]["gaps"] = 0
        audit["summary"]["late_or_invalid"] = 0
        complete = attach_source_evidence(public, audit, decision)
        self.assertTrue(complete["all_sections_ready_with_current_data"])
        self.assertEqual(complete["joint_status"], "PUBLIC_BY_0800_DATA_CADENCE_CHECKS_PASS")
        self.assertFalse(attach_source_evidence(public, None, decision)
                         ["all_sections_ready_with_current_data"])
        bad = dict(audit)
        bad["as_of_rome"] = "2026-11-04"
        self.assertEqual(attach_source_evidence(public, bad, decision)["joint_status"],
                         "PUBLIC_BY_0800_SOURCE_AUDIT_MISSING")
        incomplete = dict(audit)
        incomplete["checks"] = audit["checks"][:-1]
        incomplete["summary"] = dict(audit["summary"], checks=len(incomplete["checks"]))
        self.assertFalse(attach_source_evidence(public, incomplete, decision)
                         ["all_sections_ready_with_current_data"])
        delayed = evaluate(dt.datetime(2026, 11, 5, 8, 20, tzinfo=ROME), rows())
        self.assertFalse(attach_source_evidence(delayed, audit, decision)
                         ["all_sections_ready_with_current_data"])


    def test_missing_or_stale_research_critical_feed_never_green(self):
        public = evaluate(dt.datetime(2026, 11, 5, 7, 53, tzinfo=ROME), rows())
        all_checks = [
            {"area": area, "item": item, "as_of": "2026-11-04",
             "state": "ON_CADENCE"}
            for area, items in RESEARCH_REQUIRED.items() for item in sorted(items)
        ] + [
            {"area": "positioning", "item": c+" CFTC weekly",
             "as_of": "2026-10-27", "state": "ON_CADENCE"}
            for c in ["USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"]
        ] + [
            {"area": "ois_v2_research_tenor", "item": c+" "+t,
             "as_of": "2026-11-04", "state": "ON_CADENCE"}
            for c in ["USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"]
            for t in ("3m","6m","12m")
        ] + [
            {"area": "governments", "item": c, "as_of": "2026-09-30",
             "state": "DELAYED"}
            for c in ["USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"]
        ]
        audit = {
            "schema": "GMFQ_FXV2_FRESHNESS_AUDIT_V1",
            "as_of_rome": "2026-11-05", "status": "DATA_GAPS_PRESENT",
            "checks": all_checks, "hard_errors": [],
            "summary": {"checks": len(all_checks), "v2_pages":12,"fx_pairs":28,
                        "gaps":8,"late_or_invalid":8}
        }
        ready = {
            "schema":"GMFQ_FXV2_READINESS_DUAL_TRACK_V1",
            "as_of_rome":"2026-11-05",
            "research":{"website_pages":12,"rate_pricing_horizons":24,
                        "state":"AVAILABLE_WITH_SOURCE_QUALITY_LIMITS"},
            "trading_core":{"pair_count":28,"state":"NOT_REVALIDATED_FROM_RESEARCH",
                            "baseline_macro_as_of":"2026-09-25"}
        }
        good = attach_source_evidence(public,audit,ready)
        self.assertTrue(good["research_usable_by_0800"])
        self.assertFalse(good["all_sections_ready_with_current_data"])
        self.assertEqual(good["source_evidence"]["unresolved_gaps"],8)
        for area,item in [
            ("ois_v2_research_tenor","NZD 6m"),
            ("rates_research","CHF SNB same-date spot pair (not Core)"),
            ("prices","ECB G8 matched-date fixing"),
            ("cross_asset_live","VIX Cboe"),
            ("calendar","refresh operativo"),
            ("positioning","NZD CFTC weekly")
        ]:
            broken=[dict(x) for x in all_checks]
            row=next(x for x in broken if x["area"]==area and x["item"]==item)
            row["state"]="DELAYED"
            late=dict(audit,checks=broken)
            out=attach_source_evidence(public,late,ready)
            self.assertFalse(out["research_usable_by_0800"],(area,item))
            self.assertEqual(out["joint_status"],"PUBLIC_BY_0800_SOURCE_GAPS_VISIBLE")
        invalid=dict(audit,hard_errors=[{"reason":"invalid research source"}],
                     status="AUDIT_FAILED")
        self.assertFalse(attach_source_evidence(public,invalid,ready)
                         ["research_usable_by_0800"])
        delayed=evaluate(dt.datetime(2026,11,5,8,1,tzinfo=ROME),rows())
        self.assertFalse(attach_source_evidence(delayed,audit,ready)
                         ["research_usable_by_0800"])
        self.assertFalse(attach_source_evidence(public,None,ready)
                         ["research_usable_by_0800"])

    def test_complete_before_deadline(self):
        result = evaluate(dt.datetime(2026, 11, 4, 7, 51, tzinfo=ROME), rows())
        self.assertEqual(result["status"], "PASS_12_PAGES_PUBLIC_BY_0800")
        self.assertTrue(result["on_time_proven"])
        self.assertEqual(result["public_files_verified"], len(FILES))
        self.assertFalse(result["economic_data_freshness_certified"])

    def test_observed_after_deadline_is_not_proof_of_lateness_or_on_time(self):
        result = evaluate(dt.datetime(2026, 11, 4, 12, 35, tzinfo=ROME), rows())
        self.assertEqual(result["status"], "VERIFIED_AFTER_0800_ON_TIME_UNPROVEN")
        self.assertFalse(result["on_time_proven"])

    def test_missing_page_fails(self):
        result = evaluate(dt.datetime(2026, 11, 4, 7, 50, tzinfo=ROME), rows()[:-1])
        self.assertEqual(result["status"], "FAIL_PUBLIC_FILES_NOT_MATCHED")

    def test_duplicate_page_fails(self):
        rs = rows()
        rs[-1] = rs[0].copy()
        self.assertFalse(evaluate(dt.datetime(2026, 11, 4, 7, 50, tzinfo=ROME), rs)["on_time_proven"])

    def test_http_hash_drift_fails(self):
        rs = rows()
        rs[0]["public_sha256"] = "b" * 64
        self.assertEqual(evaluate(dt.datetime(2026, 11, 4, 7, 50, tzinfo=ROME), rs)["status"],
                         "FAIL_PUBLIC_FILES_NOT_MATCHED")

    def test_http_404_fails(self):
        rs = rows()
        rs[2]["http"] = 404
        rs[2]["status"] = "MISMATCH_OR_UNAVAILABLE"
        self.assertFalse(evaluate(dt.datetime(2026, 11, 4, 7, 50, tzinfo=ROME), rs)["on_time_proven"])

    def test_weekend_not_certified(self):
        result = evaluate(dt.datetime(2026, 11, 7, 7, 50, tzinfo=ROME), rows())
        self.assertEqual(result["status"], "NOT_WEEKDAY")

    def test_dst_summer(self):
        result = evaluate(dt.datetime(2026, 7, 1, 7, 55, tzinfo=ROME), rows())
        self.assertTrue(result["on_time_proven"])

    def test_exact_0800(self):
        result = evaluate(dt.datetime(2026, 11, 4, 8, 0, tzinfo=ROME), rows())
        self.assertTrue(result["on_time_proven"])


if __name__ == "__main__":
    unittest.main()
