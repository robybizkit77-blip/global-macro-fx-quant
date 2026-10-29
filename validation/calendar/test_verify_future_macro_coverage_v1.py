"""Synthetic, deterministic calendar expiry tests; no invented live releases."""
from __future__ import annotations

import copy
from datetime import datetime
import unittest

from validation.calendar.verify_future_macro_coverage_v1 import G8, verify


class PublishedFutureCalendarContractTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime.fromisoformat("2026-10-29T08:00:00+01:00")
        self.seed={
            "schema":"GMFQ_MACRO_RELEASE_OFFICIAL_SEED_V1",
            "status":"ACTIVE_VERIFIED_SEED",
            "events":[{
                "ccy":ccy,"date":("2026-10-28" if ccy=="AUD" else "2026-11-03"),
                "event_type":"INFLATION","title":ccy+" issuer release",
                "quality":"OFFICIAL_CONFIRMED","importance":"HIGH",
            } for ccy in sorted(G8)]
        }
        self.cb_source={
            ccy:{"next_meeting":"2026-11-05","rate":2.5,"stance":"NEUTRAL"}
            for ccy in G8
        }
        cb=[{
            "ccy":ccy,"date":"2026-11-05",
            "current_rate":2.5,"stance":"NEUTRAL",
            "title":ccy+" central bank decision",
            "event_type":"CENTRAL_BANK_DECISION",
            "quality":"OFFICIAL_SCHEDULE_FROM_CERTIFIED_CB_LAYER",
            "source_layer":"NATIVE_CB_DATA","status":"UPCOMING",
        } for ccy in sorted(G8)]
        macro=[{
            **e,"source_layer":"MACRO_RELEASE_OFFICIAL_SEED_V1",
            "status":"UPCOMING","consensus_status":"NOT_PRESENT",
        } for e in self.seed["events"] if e["date"]>="2026-10-29"]
        self.cal={
            "schema":"GMFQ_CALENDAR_OPERATIONAL_VIEW_V3",
            "status":"ACTIVE_CB_PLUS_MACRO_OFFICIAL_WITH_SECONDARY_CONTEXT",
            "scope":{
                "core_score_impact":0,
                "consensus_context_only":True,
                "consensus_never_changes_official_date":True,
                "macro_release_currencies":sorted({e["ccy"] for e in macro}),
            },
            "coverage":{
                "g8_total":8,"cb_schedule_available":8,
                "macro_ccy_coverage":len({e["ccy"] for e in macro}),
                "upcoming_macro_events":len(macro),
                "upcoming_total_events":len(cb)+len(macro),
                "consensus_available_events":0,"previous_only_events":0,
            },
            "events":cb+macro
        }

    def test_8_source_currencies_seven_future_valid_no_invention(self):
        receipt=verify(self.cal,self.seed,self.cb_source,self.now)
        self.assertEqual(receipt["seed_currency_coverage"],8)
        self.assertEqual(receipt["future_macro_currency_coverage"],7)
        self.assertEqual(receipt["currency_without_next_seed_event"],["AUD"])
        self.assertEqual(receipt["status"],
                         "PASS_EXACT_SOURCES_WITH_DISCLOSED_FUTURE_GAPS")
        self.assertTrue(receipt["no_fabricated_events"])

    def test_expired_fed_meeting_is_disclosed_not_invented(self):
        cb=copy.deepcopy(self.cb_source)
        cb["USD"]["next_meeting"]="2026-10-28"
        cal=copy.deepcopy(self.cal)
        cal["events"]=[e for e in cal["events"]
                       if not (e.get("ccy")=="USD"
                               and e.get("event_type")=="CENTRAL_BANK_DECISION")]
        cal["coverage"]["cb_schedule_available"]=7
        cal["coverage"]["upcoming_total_events"]-=1
        receipt=verify(cal,self.seed,cb,self.now)
        self.assertEqual(receipt["currency_without_next_certified_CB_meeting"],["USD"])
        self.assertEqual(receipt["verified_CB_meetings"],7)
        self.assertEqual(receipt["cb_source_currencies"],8)
        self.assertEqual(receipt["status"],
                         "PASS_EXACT_SOURCES_WITH_DISCLOSED_FUTURE_GAPS")
        # Publishing an expired FOMC date is still forbidden.
        extra=copy.deepcopy(self.cal)
        extra["coverage"]["cb_schedule_available"]=8
        with self.assertRaises(ValueError):
            verify(extra,self.seed,cb,self.now)

    def test_stale_aud_event_cannot_be_kept_to_force_8(self):
        bad=copy.deepcopy(self.cal)
        bad["events"].append({
            **self.seed["events"][0],"status":"UPCOMING",
            "source_layer":"MACRO_RELEASE_OFFICIAL_SEED_V1",
            "consensus_status":"NOT_PRESENT"
        })
        with self.assertRaisesRegex(ValueError,"expired event"):
            verify(bad,self.seed,self.cb_source,self.now)

    def test_cannot_hide_next_official_event(self):
        bad=copy.deepcopy(self.cal)
        bad["events"]=[e for e in bad["events"]
                        if not(e.get("ccy")=="USD"
                               and e.get("event_type")!="CENTRAL_BANK_DECISION")]
        with self.assertRaises(ValueError):
            verify(bad,self.seed,self.cb_source,self.now)

    def test_cannot_fabricate_aud_event_or_backfill_coverage(self):
        bad=copy.deepcopy(self.cal)
        fake={
            **self.seed["events"][0],"ccy":"AUD",
            "date":"2026-11-04","status":"UPCOMING",
            "source_layer":"MACRO_RELEASE_OFFICIAL_SEED_V1",
            "consensus_status":"NOT_PRESENT"}
        bad["events"].append(fake)
        with self.assertRaisesRegex(ValueError,"fabricated|noncanonical"):
            verify(bad,self.seed,self.cb_source,self.now)

    def test_quality_date_and_consensus_tampering_rejected(self):
        for field,value in [("quality","INDICATIVE"),
                            ("date","2026-11-04"),
                            ("consensus_status","FUTURE_ACTUAL")]:
            with self.subTest(field=field):
                bad=copy.deepcopy(self.cal)
                e=next(x for x in bad["events"]
                       if x["event_type"]!="CENTRAL_BANK_DECISION")
                e[field]=value
                with self.assertRaises(ValueError):
                    verify(bad,self.seed,self.cb_source,self.now)

    def test_lying_coverage_or_missing_central_bank_does_not_pass(self):
        bad=copy.deepcopy(self.cal)
        bad["coverage"]["macro_ccy_coverage"]=8
        with self.assertRaises(ValueError):
            verify(bad,self.seed,self.cb_source,self.now)
        bad=copy.deepcopy(self.cal)
        bad["events"].pop(0)
        with self.assertRaises(ValueError):
            verify(bad,self.seed,self.cb_source,self.now)

    def test_source_seed_must_still_be_reviewed_g8(self):
        bad=copy.deepcopy(self.seed)
        bad["events"]=[e for e in bad["events"] if e["ccy"]!="AUD"]
        with self.assertRaisesRegex(ValueError,"original reviewed macro seed"):
            verify(self.cal,bad,self.cb_source,self.now)

    def test_rome_date_not_utc_date_at_midnight(self):
        # 23:45 UTC on Oct 28 is already Oct 29 in Rome. AUD has expired.
        instant=datetime.fromisoformat("2026-10-28T23:45:00+00:00")
        self.assertEqual(verify(self.cal,self.seed,self.cb_source,instant)["future_macro_currency_coverage"],7)


if __name__=="__main__":
    unittest.main()
