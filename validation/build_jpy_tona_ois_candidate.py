#!/usr/bin/env python3
"""Build JPY OIS + native-CB candidates from the validated TFX TONA candidate.

Fail-closed: reads the current canonical sections, changes JPY only, and writes
candidate files under validation/. It does not mutate live_data or payload.
"""
from __future__ import annotations
import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SINGLE = ROOT / "validation" / "cb_pricing" / "JPY_CB_PRICING_CANDIDATE_2026-10-08.json"
OIS = ROOT / "live_data" / "sections" / "OIS_DATA.json"
NATIVE = ROOT / "live_data" / "sections" / "NATIVE_CB_DATA.json"
OUT_OIS = ROOT / "validation" / "JPY_TONA_OIS_DATA_CANDIDATE_2026-10-08.json"
OUT_NATIVE = ROOT / "validation" / "JPY_NATIVE_CB_DATA_CANDIDATE_2026-10-08.json"
OUT_GATE = ROOT / "validation" / "JPY_TONA_OIS_GATE_2026-10-08.json"


def main() -> int:
    c = json.loads(SINGLE.read_text(encoding="utf-8"))
    if c.get("currency") != "JPY" or c.get("status") != "READY_FOR_SEPARATE_PROMOTION":
        raise SystemExit("JPY single-currency candidate is not promotion-ready")
    req = ("source_validated","asof_validated","meeting_path_validated","changes_validated","current_real","previous_real","week_real")
    if not all(c.get("validation",{}).get(k) is True for k in req):
        raise SystemExit("JPY validation gate incomplete")

    ois = json.loads(OIS.read_text(encoding="utf-8"))
    native = json.loads(NATIVE.read_text(encoding="utf-8"))
    before_ois = json.loads(json.dumps(ois))
    before_native = json.loads(json.dumps(native))

    jpy = {
        "status":"ACTIVE",
        "as_of":c["as_of"],
        "source":c["source"],
        "source_meta":{
            "official_public":True,
            "instrument":c["instrument"],
            "quotation":c["quotation"],
            "horizon_mapping":"Dec-26 / Mar-27 / Sep-27 direct TFX quarterly buckets; no interpolation"
        },
        "policy_rate":c["policy_rate"],
        "meetings":c["meeting_path"],
        "horizons":{k:{kk:vv for kk,vv in v.items() if kk != "contract"} for k,v in c["horizons"].items()},
        "cuts_hikes_priced":c["cuts_hikes_priced"],
        "direction":c["direction"],
        "change_direction_1d":c["change_direction_1d"],
        "change_direction_1w":c["change_direction_1w"],
        "validation":c["validation"],
        "provenance":c["provenance"]
    }
    ois["currencies"]["JPY"] = jpy

    n = native["JPY"]
    n["pricing_tier"] = "COMPLETO_DIRECT_TFX_SETTLEMENT_HISTORY"
    n["pricing_status"] = "TFX official TONA futures: Dec-26 1.555%; Mar-27 1.755%; Sep-27 2.119%."
    n["market_3m"] = "1.555%"
    n["market_6m"] = "1.755%"
    n["market_12m"] = "2.119%"
    n["market_pricing"] = {
        "as_of":c["as_of"],
        "instrument":c["instrument"],
        "quality":"COMPLETO_DIRECT_TFX_SETTLEMENT_HISTORY",
        "h3m":c["horizons"]["3m"]["rate"],
        "h6m":c["horizons"]["6m"]["rate"],
        "h12m":c["horizons"]["12m"]["rate"],
        "near_term":"Direct official TFX quarterly TONA buckets; 1D and nearest-session 1W history validated.",
        "source":c["source"],
        "note":c["validation"]["weekly_reference_note"],
        "freshness_status":"CURRENT_VALIDATED"
    }

    changed_ois = [k for k in before_ois["currencies"] if before_ois["currencies"][k] != ois["currencies"][k]]
    changed_native = [k for k in before_native if before_native[k] != native[k]]
    if changed_ois != ["JPY"] or changed_native != ["JPY"]:
        raise SystemExit(f"Scope violation: OIS={changed_ois}, NATIVE={changed_native}")

    OUT_OIS.write_text(json.dumps(ois,separators=(",",":"),ensure_ascii=False),encoding="utf-8")
    OUT_NATIVE.write_text(json.dumps(native,separators=(",",":"),ensure_ascii=False),encoding="utf-8")
    gate = {
        "schema":"GMFQ_JPY_TONA_OIS_GATE_V1",
        "status":"PASS",
        "currency":"JPY",
        "source":c["source"],
        "as_of":c["as_of"],
        "scope":{"ois_only_jpy":changed_ois==["JPY"],"native_only_jpy":changed_native==["JPY"]},
        "validation":c["validation"],
        "activation_ready":True
    }
    OUT_GATE.write_text(json.dumps(gate,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(gate,indent=2,ensure_ascii=False))
    return 0

if __name__ == "__main__":
    sys.exit(main())
