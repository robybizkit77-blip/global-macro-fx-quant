#!/usr/bin/env python3
"""Research desk synthesis: BLS first release vs daily rates/ECB and evidence gaps.

NOT the certified G8 Macro scores or a trading signal. Read-only.
"""
import argparse,json
from pathlib import Path
from validation.macro.v2_shadow_features_v1 import ROOT,require
from validation.macro.v2_bls_us_u3_2026_shadow_replay_v1 import replay
from validation.macro.v2_us_labour_market_association_audit_v1 import run as market
RECEIPT="GMFQ_MACRO_V2_USD_LABOUR_RESEARCH_DESK_BRIEF_V1"
def build():
    b=replay(at="2026-10-23T12:00:00Z")
    m=market()
    require(b["releases_2026_visible_at_cutoff"]==9 and
            b["latest_reference_period"]=="2026-09" and
            m["coverage"]["BLS_releases"]==9 and
            m["coverage"]["OIS_true_release_aligned_windows"]==0,
            "the BLS history/market sources are not ready for summary")
    last=b["nine_first_release_snapshots"][-1]
    require(last["u3_first_release_percent"]==4.2 and
            last["training_median"]==4.2 and
            last["not_a_current_macro_score"] is True,
            "descriptive USD labour evidence changed")
    require(m["sources"]["history_rates_last_date"]<="2026-10-23" and
            m["sources"]["history_fx_last_date"]<="2026-10-23",
            "future market references in desk brief")
    return {"schema":RECEIPT,
      "as_of":"2026-10-23",
      "currency":"USD","pillar":"labour",
      "status":"HISTORICAL_DESCRIPTIVE_RESEARCH_NOT_PRODUCTION",
      "what_happened":{
        "latest_observation_period":"2026-09",
        "first_published_at":last["first_published_at_utc"],
        "u3_percent":last["u3_first_release_percent"],
        "reference_training_events":last["training_first_releases"],
        "prior_median_u3_percent":last["training_median"],
        "relative_intensity_descriptive":last["labour_tightness_descriptive_only"],
        "cannot_infer_direction_of_usd_from_u3_alone":True,
      },
      "what_changed":{
        "prior_u3_2026_08_percent":b["nine_first_release_snapshots"][-2]["u3_first_release_percent"],
        "latest_u3_2026_09_percent":last["u3_first_release_percent"],
        "change_percentage_points":round(last["u3_first_release_percent"]-
                        b["nine_first_release_snapshots"][-2]["u3_first_release_percent"],2),
        "monthly_velocity_signal":None,
      },
      "market_response_evidence":{
        "bls_events":m["coverage"]["BLS_releases"],
        "treasury_2y_daily_associations":m["coverage"]["UST2Y_daily_pairs_with_event_observation"],
        "ecb_next_fixing_comparisons":m["coverage"]["ECB_pre_and_first_later_fixings"],
        "pre_release_consensus_windows":0,
        "event_aligned_usd_ois_windows":0,
        "rates_fx_association_not_causation":True,
      },
      "inferences_withheld":[
        "DATA_SURPRISE_AGAINST_PRE_RELEASE_CONSENSUS",
        "SAME_CONTRACT_USD_OIS_REPRICING",
        "INTRADAY_TREASURY_2Y_REACTION",
        "VALIDATED_FX_CAUSAL_OR_PREDICTIVE_EFFECT",
        "CANONICAL_G8_GROWTH_LABOUR_INFLATION_SCORE",
      ],
      "next_required_evidence":[
        "DATED_PRE_RELEASE_CONSENSUS",
        "LICENSED_RELEASE_TIMED_USD_OIS_AND_TREASURY",
        "AUTHORIZED_FX_TICK_PROVENANCE_AND_INDEPENDENT_REVIEW",
      ],
      "full_PIT_vintage_certified":False,
      "eligible_for_live_macro_score":False,
      "eligible_for_backtest":False,
      "safe_to_publish_new_D":False,
      "safe_to_update_pair_theses":False,
      "writes_live_data":False,
    }
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",type=Path)
    a=parser.parse_args();data=build()
    if a.out:
        require(a.out.resolve().is_relative_to(Path("/tmp")),"research output only in /tmp")
        a.out.parent.mkdir(parents=True,exist_ok=True)
        a.out.write_text(json.dumps(data,indent=2)+"\n")
    print(json.dumps({"status":data["status"],"latest_u3":data["what_happened"]["u3_percent"],
       "missing_required":len(data["inferences_withheld"])}))
if __name__=="__main__":main()
