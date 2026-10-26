#!/usr/bin/env python3
"""Why EURJPY lacks full continuous prior-only 52W FX+2Y exact-date OOS.

Only previously published ECB FX, ECB EUR2Y and independently downloaded
Japan Ministry of Finance JGB 2Y observations. No imputation, no promotion.
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path

from validation.beta import weekly_fx_2y_shadow_oos_v1 as beta
from validation.rates.audit_jpy_2y_mof_chronology_v1 import (
    normalize_source, propose_verified_latest_publisher_candidate,
    parse_mof_csv, HIST_URL, CURR_URL
)

SCHEMA="GMFQ_EURJPY_2Y_WEEKLY_CALENDAR_FORENSICS_V1"


def analyze_calendar(fx_dates, eur_dates, jpy_dates, *, start, end):
    """Account for missing weeks and days, never equate different day prices."""
    if not isinstance(start, date) or not isinstance(end,date) or start>end:
        raise ValueError("invalid audit range")
    fx,eur,jpy=map(set,(fx_dates,eur_dates,jpy_dates))
    common=fx & eur & jpy
    if not all(all(type(d) is date for d in x) for x in (fx,eur,jpy)):
        raise ValueError("non-date source index")
    start_friday=beta.friday(start)
    last_friday=beta.friday(end)
    weeks=[]
    last_week=None
    current_run=0
    runs=[]
    while start_friday<=last_friday:
        mon=start_friday-timedelta(days=4)
        dset={mon+timedelta(days=i) for i in range(5)}
        live={k:sorted(x & dset) for k,x in
              (("fx",fx),("eur2y",eur),("jpy2y",jpy),("exact_triple",common))}
        ready=bool(live["exact_triple"])
        dates={k:([d.isoformat() for d in v]) for k,v in live.items()}
        ends={k:(v[-1].isoformat() if v else None) for k,v in live.items()}
        if not live["fx"]:
            reason="NO_ECB_FX_OBSERVATION_IN_WEEK"
        elif not live["eur2y"]:
            reason="NO_ECB_EUR2Y_OBSERVATION_IN_WEEK"
        elif not live["jpy2y"]:
            reason="NO_MOF_JPY2Y_OBSERVATION_IN_WEEK"
        elif not ready:
            reason="UNMATCHED_EUR_JPY_FX_DATES_DESPITE_BOTH_PUBLISHING"
        else:
            reason=None
        if ready:
            current_run+=1
        else:
            if current_run:
                runs.append({"end":last_week.isoformat(),"weeks":current_run})
            current_run=0
        weeks.append({
            "week_end":start_friday.isoformat(),
            "exact_common_dates":dates["exact_triple"],
            "last_each_date":ends,
            "status":"TRIPLE_SAME_DATE_PRESENT" if ready else reason,
            "each_source_dates":dates if not ready else None,
        })
        last_week=start_friday
        start_friday+=timedelta(days=7)
    if current_run:
        runs.append({"end":last_week.isoformat(),"weeks":current_run})
    max_run=max((r["weeks"] for r in runs),default=0)
    # The paired-week return count in an uninterrupted run is weeks-1;
    # to produce ONE held-out OOS observation it takes 52 training returns
    # + 1 testing return = 54 consecutive fixing anchor weeks.
    minimum_fixing_weeks=54
    return {
        "schema":SCHEMA,
        "start_date":start.isoformat(),"end_date":end.isoformat(),
        "number_weeks":len(weeks),
        "exact_common_week_count":sum(w["status"]=="TRIPLE_SAME_DATE_PRESENT" for w in weeks),
        "weeks_no_triple":sum(w["status"]!="TRIPLE_SAME_DATE_PRESENT" for w in weeks),
        "longest_consecutive_exact_week_span":max_run,
        "theoretical_minimum_consecutive_weekly_fixings_for_first_52w_oos":minimum_fixing_weeks,
        "full_exact_week_panel_ready":max_run>=minimum_fixing_weeks,
        "gaps":[w for w in weeks if w["status"]!="TRIPLE_SAME_DATE_PRESENT"],
        "weeks":weeks,
        "all_rates_on_same_date":True,
        "asynchronous_cross_day_returns_used":False,
        "missing_values_interpolated":False,
        "first_published_pit_vintages_certified":False,
        "beta_promoted":False,
    }


def official_eurjpy_readiness(fx_source, rates_source, historical_bytes,
                             current_bytes, *, as_of="2026-10-26"):
    validated=propose_verified_latest_publisher_candidate(
        normalize_source(rates_source),historical_bytes,current_bytes)
    if validated["source_comparison"]["matched"] != 273:
        raise ValueError("MoF source original 273/273 attestation absent")
    historical=parse_mof_csv(historical_bytes,source=HIST_URL)
    current=parse_mof_csv(current_bytes,source=CURR_URL)
    for d in set(historical)&set(current):
        if historical[d]!=current[d]:
            raise ValueError("MoF official file overlap differs")
    full={**historical,**current}
    cutoff=beta.strict_date(as_of)
    fx=beta.official_fx(fx_source,cutoff)
    eur,block=beta.rate_history("EUR",rates_source,cutoff)
    if block:
        raise ValueError("ECB EUR2Y source invalid: "+block)
    earliest=max(beta.strict_date(fx_source["first_as_of"]), min(eur),min(full))
    ending=min(cutoff,max(eur),max(full),max(fx))
    c=analyze_calendar(fx,eur,full,start=earliest,end=ending)
    # This keeps original triple-date methodology unchanged.
    weekly=beta.weekly_points(fx,eur,full,"EUR","JPY")
    observations=beta.consecutive_returns(weekly)
    oos=beta.strict_oos(observations)
    c["observed_triple_weekly_points"]=len(weekly)
    c["consecutive_pair_return_rows"]=len(observations)
    c["historical_oos_rows"]=len(oos)
    c["original_eur2y_observation_dates"]=len(eur)
    c["original_mof_jpy2y_observation_dates"]=len(full)
    c["mo_f_source_verified"]=True
    c["mof_historical_sha256"]=hashlib.sha256(historical_bytes).hexdigest()
    c["mof_current_sha256"]=hashlib.sha256(current_bytes).hexdigest()
    c["source_benchmark_equivalence_certified"]=False
    if oos:
        c["status"]="EXACT_WEEKLY_PSEUDO_OOS_CANDIDATE_EXISTS"
    else:
        c["status"]="NO_52W_PRIOR_ONLY_EXACT_DATE_OOS"
    return c


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mof-historical-csv",type=Path,required=True)
    parser.add_argument("--mof-current-csv",type=Path,required=True)
    parser.add_argument("--as-of",default="2026-10-26")
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    if not args.out.resolve().is_relative_to(Path("/tmp")):
        parser.error("research-only receipt must live under /tmp")
    x=official_eurjpy_readiness(
        json.loads(beta.FX_PATH.read_text(encoding="utf-8")),
        json.loads(beta.RATE_PATH.read_text(encoding="utf-8")),
        args.mof_historical_csv.read_bytes(),args.mof_current_csv.read_bytes(),
        as_of=args.as_of)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(x,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in x.items() if k!="weeks"},sort_keys=True))


if __name__=="__main__":
    main()
