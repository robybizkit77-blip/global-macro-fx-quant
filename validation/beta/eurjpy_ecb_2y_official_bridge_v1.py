#!/usr/bin/env python3
"""Research-only ECB 2Y missing-day restoration against original ECB SDMX CSV.

Never fill with model estimates, different-day rates or re-date official
quotes. Do not overwrite the live 2Y mirror, Core or original Beta.
"""
from __future__ import annotations

import csv
from datetime import date
import io
import json
import math
import re

from validation.beta import weekly_fx_2y_shadow_oos_v1 as beta
from validation.beta.eurjpy_weekly_calendar_forensics_v1 import (
    official_eurjpy_readiness
)

SCHEMA="GMFQ_EURJPY_ECB_OFFICIAL_SEP_2026_2Y_REPAIR_SHADOW_V1"
ECB_SERIES="YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y"
ECB_URL=("https://data-api.ecb.europa.eu/service/data/YC/"
         "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y?"
         "startPeriod=2026-09-21&endPeriod=2026-09-25&format=csvdata")
TARGETS=("2026-09-23","2026-09-24","2026-09-25")


def parse_ecb_sdmx_original_csv(raw):
    if not isinstance(raw,bytes) or not raw:
        raise ValueError("original ECB SDMX CSV bytes required")
    try:
        txt=raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("ECB SDMX CSV must be UTF8") from exc
    reader=csv.DictReader(io.StringIO(txt))
    if not reader.fieldnames or not {"KEY","TIME_PERIOD","OBS_VALUE"}.issubset(reader.fieldnames):
        raise ValueError("ECB official SDMX keyed obs header required")
    observed={}
    for row in reader:
        if row.get("KEY")!=ECB_SERIES:
            raise ValueError("wrong ECB AAA 2Y series")
        raw_date=row.get("TIME_PERIOD")
        if not isinstance(raw_date,str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}",raw_date):
            raise ValueError("invalid ECB 2Y day")
        dt=date.fromisoformat(raw_date)
        if not (date(2026,9,21)<=dt<=date(2026,9,25)):
            raise ValueError("ECB 2Y response has observations outside requested bounds")
        if dt in observed:
            raise ValueError("duplicate ECB 2Y day")
        try:
            v=float(row.get("OBS_VALUE") or "")
        except ValueError as exc:
            raise ValueError("missing ECB 2Y official value") from exc
        if not math.isfinite(v):
            raise ValueError("nonfinite official ECB 2Y")
        observed[dt]=v  # ECB annual percent rate, not decimal / 100
    if not observed:
        raise ValueError("ECB official 2Y response contained no values")
    return observed


def repair_eur_2y_history_in_memory(rates, original_csv):
    if not isinstance(rates,dict) or "EUR" not in rates:
        raise ValueError("EUR 2Y source absent")
    source=rates["EUR"]
    if (source.get("quality")!="FULL_CURRENT_OFFICIAL" or
        "European Central Bank" not in str(source.get("source")) or
        "AAA Svensson" not in str(source.get("source"))):
        raise ValueError("wrong ECB AAA 2Y publisher/instrument")
    original,reason=beta.rate_history("EUR",rates,date(2026,10,26))
    if reason:
        raise ValueError("unaligned original EUR2Y "+reason)
    values=parse_ecb_sdmx_original_csv(original_csv)
    old_overlap=sorted(set(original)&set(values))
    if not old_overlap:
        raise ValueError("no independent ECB series overlap to verify data definition")
    # This older mirror used up to ten decimals. The SDMX publisher may
    # quote to at least 6dp; require <=0.000005 percent difference (0.0005bp).
    mismatches=[(d.isoformat(),original[d],values[d]) for d in old_overlap
                if abs(original[d]-values[d])>0.000005]
    if mismatches:
        raise ValueError("existing EUR2Y vs original ECB data disagree: "+str(mismatches))
    patched={d:v for d,v in original.items()}
    restored=[]
    for day in TARGETS:
        d=date.fromisoformat(day)
        if d in values and d not in patched:
            patched[d]=values[d]
            restored.append(day)
    if not restored:
        raise ValueError("ECB SDMX gave no new original missing EUR2Y days")
    if not any(s in restored for s in ("2026-09-24","2026-09-25")):
        raise ValueError("no same-day overlapping 2026-09-24/25 EUR2Y restoration")
    import copy
    amended=copy.deepcopy(rates)
    ranked=sorted(patched.items())
    amended["EUR"]["history2"]["dates"]=[d.isoformat() for d,v in ranked]
    amended["EUR"]["history2"]["values"]=[v for d,v in ranked]
    # Current EUR2Y as-of remains original, no re-dating.
    if amended["EUR"]["date"]!=ranked[-1][0].isoformat():
        raise ValueError("ECB EUR source current as-of changed unexpectedly")
    receipt={
        "schema":SCHEMA,
        "status":"RESTORED_OFFICIAL_SAME_DAY_RESEARCH_ONLY",
        "official_ecb_series":ECB_SERIES,
        "official_ecb_source_url":ECB_URL,
        "overlap_confirmed_with_stored_eur2y_dates":[d.isoformat() for d in old_overlap],
        "restored_days":restored,
        "source_observation_count":len(values),
        "original_repo_2y_days":len(original),
        "new_research_2y_days":len(ranked),
        "no_interpolation":True,
        "no_week_date_shifting":True,
        "model_beta_promoted":False,
        "official_historical_first_release_vintage_verified":False,
        "live_data_modified":False,
    }
    return amended,receipt


def verify_full_eurjpy_beta_shadow(fx,rates,ecb_bytes,mof_history,mof_current,
                                   *,as_of="2026-10-26"):
    amended,receipt=repair_eur_2y_history_in_memory(rates,ecb_bytes)
    before=official_eurjpy_readiness(fx,rates,mof_history,mof_current,as_of=as_of)
    after=official_eurjpy_readiness(fx,amended,mof_history,mof_current,as_of=as_of)
    # Also use the identical already-preregistered 52W prior-only OLS; do
    # not relabel candidate output as PIT or independently executable hedges.
    full=beta.audit_with_official_jpy_source(
        fx,amended,mof_history,mof_current,as_of=as_of)
    eurjpy=next(x for x in full["pairs"] if x["pair"]=="EURJPY")
    receipt["before_same_day_consecutive_week_span"]=before["longest_consecutive_exact_week_span"]
    receipt["after_same_day_consecutive_week_span"]=after["longest_consecutive_exact_week_span"]
    receipt["before_historical_oos_rows"]=before["historical_oos_rows"]
    receipt["after_historical_oos_rows"]=after["historical_oos_rows"]
    receipt["new_eurjpy_oos_rows"]=eurjpy["historical_oos_observations"]
    receipt["pair_count_with_any_shadow_oos"]=full["pairs_with_any_oos"]
    receipt["gap_statuses_after"]=[g["status"] for g in after["gaps"]]
    receipt["matched_on_actual_same_day"]=True
    receipt["trading_performance_certified"]=False
    receipt["historical_pit_certified"]=False
    if not (after["historical_oos_rows"]>0 and
            eurjpy["historical_oos_observations"]>0):
        raise ValueError("independent official ECB restoration did not unlock the strict 52W test")
    return receipt
