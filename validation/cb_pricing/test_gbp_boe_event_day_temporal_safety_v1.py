#!/usr/bin/env python3
"""Adversarial BoE decision-day daily-curve replay: no post-event inference.

All inputs and payload assignments live in TemporaryDirectory only.
The 2026-11-05 policy date is sourced from canonical repo metadata; test
curve values are SYNTHETIC and are never market observations or published.
"""
from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from unittest.mock import patch

from validation.cb_pricing import (
    build_gbp_boe_ois_candidate as builder,
    apply_gbp_boe_ois_candidate as applier,
)
from validation import check_cb_pricing_source_registry as registry

ROOT = Path(__file__).resolve().parents[2]


def fixture(day):
    assert day in {"2026-11-04", "2026-11-05", "2026-11-06"}
    values = {"3m": 4.25, "6m": 4.5, "12m": 4.7}
    return {
        "schema": "GMFQ_CB_PRICING_SOURCE_SNAPSHOT_V1",
        "currency": "GBP", "status": "SOURCE_SNAPSHOT_ONLY",
        "as_of": day,
        "source": "Bank of England · estimated sterling OIS yield curves · daily OIS archive",
        "source_url": "https://www.bankofengland.co.uk/statistics/yield-curves",
        "official_archive": "https://www.bankofengland.co.uk/-/media/boe/files/statistics/yield-curves/latest-yield-curve-data.zip",
        "instrument": "UK instantaneous OIS forward curve based on SONIA",
        "quotation": "annualised continuously-compounded forward rate, percent",
        "workbook": "SYNTHETIC_QA_NO_MARKET_PUBLICATION.xlsx",
        "sheet": "1. fwds, short end",
        "observations": {
            "current": {"date": day, **values},
            "t_minus_1": {"date": "2026-11-03", "3m": 4.2, "6m": 4.4, "12m": 4.6},
            "t_minus_5": {"date": "2026-10-29", "3m": 4.15, "6m": 4.3, "12m": 4.55},
        },
        "change_1d_bp": {"3m": 5, "6m": 10, "12m": 10},
        "change_1w_bp": {"3m": 10, "6m": 20, "12m": 15},
        "validation": {
            "official_source": True, "exact_tenor_columns": True,
            "no_interpolation": True, "homogeneous_sessions": True,
        },
    }


class EventDayContractTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.ois = self.dir / "OIS.json"
        self.native = self.dir / "NATIVE.json"
        self.payload = self.dir / "part-00.txt"
        self.snapshot = self.dir / "snapshot.json"
        self.candidate = self.dir / "candidate.json"
        self.ois.write_bytes((ROOT / "live_data/sections/OIS_DATA.json").read_bytes())
        self.native.write_bytes((ROOT / "live_data/sections/NATIVE_CB_DATA.json").read_bytes())
        self.sync_payload()

    def sync_payload(self):
        a=json.loads(self.ois.read_text())
        b=json.loads(self.native.read_text())
        self.payload.write_bytes(
            applier.OIS_MARKER +
            json.dumps(a,ensure_ascii=False,separators=(",",":")).encode() + b";\n" +
            applier.NATIVE_MARKER +
            json.dumps(b,ensure_ascii=False,separators=(",",":")).encode() + b";\n"
        )

    def build(self, day):
        self.snapshot.write_text(json.dumps(fixture(day)))
        with patch.object(builder,"OIS",self.ois), patch.object(builder,"REGISTRY",registry.REGISTRY), \
             patch.object(sys,"argv",["build","--snapshot",str(self.snapshot),"--output",str(self.candidate)]), \
             redirect_stdout(StringIO()):
            builder.main()
        return json.loads(self.candidate.read_text())

    def apply(self):
        with patch.object(applier,"OIS",self.ois),patch.object(applier,"NATIVE",self.native), \
             patch.object(applier,"PAYLOAD",self.payload), \
             patch.object(sys,"argv",["apply","--candidate",str(self.candidate)]), \
             redirect_stdout(StringIO()):
            applier.main()

    def check_registry(self):
        output=StringIO()
        with patch.object(registry,"OIS",self.ois),redirect_stdout(output):
            code=registry.main()
        return code,json.loads(output.getvalue())

    def test_replay_same_decision_day_has_levels_but_no_policy_delta(self):
        candidate=self.build("2026-11-05")
        self.assertFalse(candidate["policy_comparison_temporally_aligned"])
        self.assertEqual(candidate["direction"],"DECISION_DAY_TIMESTAMP_UNVERIFIED_NO_POLICY_REPRICING")
        self.assertEqual(candidate["policy_decision_date"],"2026-11-05")
        for t in ("3m","6m","12m"):
            self.assertIsNone(candidate["horizons"][t]["policy_delta_bp"])
            self.assertIsNone(candidate["cuts_hikes_priced"][t+"_bp"])
            self.assertIsInstance(candidate["horizons"][t]["rate"],float)
            self.assertIsInstance(candidate["horizons"][t]["change_1d_bp"],float)
        self.apply()
        data=json.loads(self.ois.read_text())["currencies"]["GBP"]
        native=json.loads(self.native.read_text())["GBP"]["market_pricing"]
        self.assertFalse(data["policy_comparison_temporally_aligned"])
        self.assertEqual(data["direction"],"DECISION_DAY_TIMESTAMP_UNVERIFIED_NO_POLICY_REPRICING")
        self.assertEqual(native["freshness_status"],"DECISION_DAY_TIMING_UNVERIFIED")
        self.assertIn("WITHHELD",data["policy_reference_note"])
        self.assertEqual(native["as_of"],"2026-11-05")
        for t in ("3m","6m","12m"):
            self.assertIsNone(data["horizons"][t]["policy_delta_bp"])
            self.assertFalse(data["horizons"][t]["policy_comparison_temporally_aligned"])
        # Check both sections against exact same signed payload without
        # writing, moving or promoting ANY repository bytes.
        raw=self.payload.read_bytes()
        self.assertEqual(applier.extract(raw,applier.OIS_MARKER)[0],
                         json.loads(self.ois.read_text()))
        self.assertEqual(applier.extract(raw,applier.NATIVE_MARKER)[0],
                         json.loads(self.native.read_text()))
        self.assertEqual(self.check_registry()[0],0)
        # Attack: a same-day inferred hike must fail-closed.
        tamper=json.loads(self.ois.read_text())
        tamper["currencies"]["GBP"]["horizons"]["6m"]["policy_delta_bp"]=45.0
        self.ois.write_text(json.dumps(tamper))
        code, result=self.check_registry()
        self.assertEqual(code,2)
        self.assertTrue(any("UNALIGNED_POLICY_DECISION 6m" in x for x in result["failures"]))
        # Attack: an implied hike in the aggregate must also fail-closed.
        tamper["currencies"]["GBP"]["horizons"]["6m"]["policy_delta_bp"]=None
        tamper["currencies"]["GBP"]["cuts_hikes_priced"]["6m_bp"]=45.0
        self.ois.write_text(json.dumps(tamper))
        code, result=self.check_registry()
        self.assertEqual(code,2)
        self.assertTrue(any("decision-day priced hikes must be null" in x for x in result["failures"]))

    def test_next_day_is_eligible_for_explicit_descriptive_policy_spread(self):
        c=self.build("2026-11-06")
        self.assertTrue(c["policy_comparison_temporally_aligned"])
        self.assertEqual(c["direction"],"UP")
        self.assertEqual(c["horizons"]["6m"]["policy_delta_bp"],50)
        self.apply()
        self.assertEqual(self.check_registry()[0],0)
        x=json.loads(self.ois.read_text())["currencies"]["GBP"]
        self.assertTrue(x["policy_comparison_temporally_aligned"])
        self.assertEqual(x["horizons"]["6m"]["policy_delta_bp"],50)

    def test_predecision_archive_cannot_override_latest_policy(self):
        with self.assertRaisesRegex(SystemExit,"predates newest official"):
            self.build("2026-11-04")

    def test_tampered_event_day_candidate_cannot_be_applied(self):
        c=self.build("2026-11-05")
        c["horizons"]["6m"]["policy_delta_bp"]=45
        self.candidate.write_text(json.dumps(c))
        with self.assertRaisesRegex(SystemExit,"must be withheld"):
            self.apply()


if __name__ == "__main__":
    main(verbosity=2)
