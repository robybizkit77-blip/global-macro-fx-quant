#!/usr/bin/env python3
"""Six remaining G8 Growth official-web evidence bridges; never model sources.

Publisher metrics are often different from observed historical index levels:
EUR published monthly % change != EA index, UK 3m/3m != index, CHF GDP
quarterly != monthly production. Cross-check source statements and current
registry observations *independently*; no rewrite or imputation.

Read-only source adapters for existing shared 24-slot evidence control plane.
"""
from __future__ import annotations

import json
from datetime import datetime, date, timedelta, timezone
from urllib.parse import urlsplit

from validation.macro.v2_shadow_features_v1 import ROOT, require, timestamp
from validation.macro.v2_pit_g8_evidence_adapters_v1 import source, event
from validation.macro.v2_growth_inflation_g8_desk_inventory_v1 import parse_reference_period

FIXTURE=ROOT/"validation/macro/fixtures/v2_pit_g8_six_growth_web_bridges_v1.json"
OBSERVED=ROOT/"live_data/sections/MACRO_SERIES.json"
SCHEMA="GMFQ_MACRO_V2_SIX_G8_GROWTH_PUBLISHER_WEB_BRIDGES_V1"
# Pinned independently from dated official publisher pages/repository observed
# source definitions; no source value is inferred from current revised levels.
PINS={
 "USD":{
  "id":"US_G17_IP_2017_BASE_PUBLISHED_ONE_DECIMAL","freq":"M","unit":"index 2017=100, SA, published 0.1 index rounding",
  "sem":"TOTAL_INDUSTRIAL_PRODUCTION_MONTHLY_SA_INDEX_NOT_CANONICAL_EXACT_VALUE",
  "publisher":"Federal Reserve Board","runtime_id":"US_INDPRO_history_value","runtime_freq":"M",
  "runtime_period":"2026-08","runtime_val":103.0682,"runtime_unit":"Index 2017=100",
  "source_period":"2026-08","source_value":103.1,
  "source_url":"https://www.federalreserve.gov/RELEASES/g17/20260918/table0.htm",
  "release":"2026-09-18","clock":"2026-09-18T09:15:00-04:00",
  "stage":"PRELIMINARY_ROUNDED",
  "relation":"SAME_INDUSTRY_INDEX_CONCEPT_BUT_DIFFERENT_NUMERICAL_PRECISION_OR_POSSIBLY_REVISION",
 },
 "EUR":{
  "id":"EA_IP_MOM_CHANGE_OFFICIAL_RELEASE_PCT","freq":"M",
  "unit":"percent month-on-month, SA industrial production",
  "sem":"EA21_INDUSTRIAL_PRODUCTION_MOM_PERCENT_NOT_2021_BASE_INDEX",
  "publisher":"Eurostat","runtime_id":"EA_IP_history_value","runtime_freq":"M",
  "runtime_period":"2026-07","runtime_val":98.3,"runtime_unit":"Index 2021=100",
  "source_period":"2026-07","source_value":-0.1,
  "source_url":"https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/4-16092026-ap",
  "release":"2026-09-16","clock":None,"stage":"FIRST_ESTIMATE_MOM",
  "relation":"MISMATCH_INDEX_LEVEL_VERSUS_MOM_PERCENT_NO_SUBSTITUTION",
 },
 "GBP":{
  "id":"UK_IOP_3M3M_GROWTH_RATE_OFFICIAL","freq":"M",
  "unit":"percent three-month-on-three-month UK production output",
  "sem":"ROLLING_THREE_MONTH_VOLUME_CHANGE_ENDING_JULY_NOT_MONTHLY_INDEX",
  "publisher":"UK Office for National Statistics",
  "runtime_id":"UK_PRODUCTION_history_value","runtime_freq":"M",
  "runtime_period":"2026-07","runtime_val":98.5,"runtime_unit":"Index",
  "source_period":"2026-07","source_value":-0.5,
  "source_url":"https://www.ons.gov.uk/economy/economicoutputandproductivity/output/bulletins/indexofproduction/july2026",
  "release":"2026-09-11","clock":"2026-09-11T07:00:00+01:00",
  "stage":"FIRST_ROLLING_THREE_MONTH_ESTIMATE",
  "relation":"MISMATCH_INDEX_LEVEL_VERSUS_3M3M_PERCENT_NO_SUBSTITUTION",
 },
 "JPY":{
  "id":"JP_METI_IIP_MAY_2026_SA_2020_INDEX","freq":"M",
  "unit":"index 2020=100, SA industrial production",
  "sem":"METI_MAY_2026_INDEX_SOURCE_PAGE_NOT_PERIOD_SPECIFIC_IMMUTABLE_HTML",
  "publisher":"Ministry of Economy, Trade and Industry Japan",
  "runtime_id":"JP_IIP_history_value","runtime_freq":"M",
  "runtime_period":"2026-07","runtime_val":104.4,"runtime_unit":"Index 2020=100",
  "source_period":"2026-05","source_value":103.0,
  "source_url":"https://www.meti.go.jp/english/statistics/tyo/iip/",
  "release":"2026-06-30","clock":None,
  "stage":"MAY_PRELIMINARY_AS_DESCRIBED_BY_DATED_PUBLISHER_WEB_INDEX",
  "relation":"SAME_2020_INDEX_CONCEPT_DIFFERENT_REFERENCE_MONTH_NO_BACKFILL",
 },
 "CHF":{
  "id":"CH_SECO_SPORTS_ADJUSTED_GDP_QOQ","freq":"Q",
  "unit":"percent quarterly real GDP adjusted for sporting events",
  "sem":"SPECIALLY_SPORTS_ADJUSTED_QUARTERLY_GDP_NOT_MONTHLY_INDUSTRIAL_INDEX",
  "publisher":"Swiss State Secretariat for Economic Affairs",
  "runtime_id":"CH_PRODUCTION_history_value","runtime_freq":"M",
  "runtime_period":"2026-06","runtime_val":122.0,"runtime_unit":"Index 2021=100",
  "source_period":"2026Q2","source_value":1.5,
  "source_url":"https://www.seco.admin.ch/en/gross-domestic-product",
  "release":"2026-09-03","clock":None,
  "stage":"SEPTEMBER_QUARTERLY_GDP_2026Q2_REPORT",
  "relation":"MISMATCH_DIFFERENT_INDICATOR_GDP_Q_VS_INDUSTRIAL_PRODUCTION_M",
 },
 "CAD":{
  "id":"STATCAN_GDP_INDUSTRY_36_10_0434_01_LEVEL","freq":"M",
  "unit":"million chained 2017 CAD, SAAR real GDP by industry",
  "sem":"MONTHLY_GDP_INDUSTRY_CHAINED_VOLUME_SAAR_LEVEL_NOT_QOQ_PERCENT",
  "publisher":"Statistics Canada",
  "runtime_id":"CA_REAL_GDP_M_history_value","runtime_freq":"M",
  "runtime_period":"2026-06","runtime_val":2369309,
  "runtime_unit":"million chained 2017 CAD SAAR",
  "source_period":"2026-06","source_value":2369309,
  "source_url":"https://www150.statcan.gc.ca/n1/daily-quotidien/260828/t001b-eng.htm",
  "release":"2026-08-28","clock":None,
  "stage":"PUBLISHER_JUNE_MONTHLY_GDP_INDUSTRY_LEVEL",
  "relation":"SOURCE_LEVEL_NUMERICALLY_MATCHES_CANONICAL_BUT_SERIES_ID_NOT_APPROVED",
 },
}
REVISED_EUR={
 "period":"2026-07","value":-0.3,
 "url":"https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/4-15102026-ap",
 "day":"2026-10-15","clock":None,"stage":"RETROSPECTIVE_REVISION_MOM",
}
HOSTS={
 "USD":"www.federalreserve.gov","EUR":"ec.europa.eu",
 "GBP":"www.ons.gov.uk","JPY":"www.meti.go.jp",
 "CHF":"www.seco.admin.ch","CAD":"www150.statcan.gc.ca",
}
NOTES={
 "USD":"Fed one-decimal 103.1 published index is NOT exactly 103.0682 canonical; raw source release values may be revised",
 "EUR":"Eurostat first -0.1% MoM and later revised -0.3% MoM are NOT the 98.3 index level in runtime",
 "GBP":"ONS -0.5% is a ROLLING three-month-on-three-month movement, NOT 98.5 index level",
 "JPY":"METI web source for 2026 May is a mutable official index; original-day bytes and July first observation not imported",
 "CHF":"Swiss sports-adjusted GDP quarterly +1.5% is NOT monthly industry index 122.0 or automatically comparable to AUD/NZD GDP",
 "CAD":"StatCan 2,369,309 level is publisher table value but exact source mapping to canonical history needs review",
}


def _visible(day,clock):
    if clock is None:
        return datetime.combine(date.fromisoformat(day)+timedelta(days=1),
                                datetime.min.time(),tzinfo=timezone.utc).isoformat()
    return timestamp(clock).isoformat()


def _check_event(row,pin,*,currency,is_revision=False):
    period=REVISED_EUR["period"] if is_revision else pin["source_period"]
    value=REVISED_EUR["value"] if is_revision else pin["source_value"]
    day=REVISED_EUR["day"] if is_revision else pin["release"]
    clock=REVISED_EUR["clock"] if is_revision else pin["clock"]
    url=REVISED_EUR["url"] if is_revision else pin["source_url"]
    stage=REVISED_EUR["stage"] if is_revision else pin["stage"]
    require(row.get("observation_period")==period
            and type(row.get("reported_value")) in (float,int)
            and row["reported_value"]==value
            and row.get("published_on")==day
            and row.get("source_clock")==clock
            and row.get("source_url")==url
            and timestamp(row.get("conservative_visible_from_utc"))==timestamp(_visible(day,clock))
            and row.get("publication_stage")==stage
            and row.get("kind")==("REVISION_WEB" if is_revision else "FIRST_WEB"),
            "official Growth publication event/metric/vintage tampered: "+currency)
    p=urlsplit(url)
    require(p.scheme=="https" and p.hostname==HOSTS[currency] and
            bool(p.path) and not p.username and not p.password,
            "Growth official publisher source domain mismatch")
    require(date.fromisoformat(day)>=date.fromisoformat(period[:4]+"-"+
             ({"2026Q2":"04","2026Q3":"07"}.get(period,period[5:7]))+"-01"),
            "Growth publication cannot predate economic reference quarter/month")
    return event(period,"REVISION_WEB" if is_revision else "FIRST_WEB",
                 _visible(day,clock),value,url)


def collect_growth_bridges():
    raw=json.loads(FIXTURE.read_text(encoding="utf-8"))
    require(raw.get("schema")==SCHEMA and raw.get("review_as_of")=="2026-10-24"
            and raw.get("research_only") is True
            and raw.get("archived_original_publication_day_bytes_certified") is False
            and raw.get("canonical_growth_series_selected") is False
            and raw.get("eligible_for_macro_scoring") is False,
            "six Growth source evidence grade promoted without certification")
    entries=raw.get("streams")
    require(isinstance(entries,list) and len(entries)==6
            and [x.get("currency") for x in entries]==list(PINS),
            "six exact Growth official publisher candidates required")
    observed=json.loads(OBSERVED.read_text(encoding="utf-8"))
    require(set(observed)=={"USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"},
            "G8 current series observation inventory unexpectedly changed")
    result=[]
    for x in entries:
        c=x["currency"];p=PINS[c]
        mandatory={
            "candidate_series_id":"id","frequency":"freq","unit":"unit",
            "period_semantics":"sem","publisher":"publisher",
            "canonical_observed_source_id":"runtime_id",
            "canonical_observed_frequency":"runtime_freq",
            "canonical_observed_period":"runtime_period",
            "canonical_observed_value":"runtime_val",
            "canonical_observed_unit":"runtime_unit",
            "metric_relation":"relation",
        }
        for key,pkey in mandatory.items():
            require(x.get(key)==p[pkey],
                    "Growth source versus current metric identity/units drift: "+c+" "+key)
        require(x.get("original_day_html_bytes_proven") is False,
                "original source availability not proven for "+c)
        cand=[y for y in observed[c] if y.get("id")==p["runtime_id"]]
        require(len(cand)==1 and cand[0].get("frequency")==p["runtime_freq"]
                and cand[0].get("unit")==p["runtime_unit"]
                and type(cand[0].get("last_value")) in (int,float)
                and cand[0]["last_value"]==p["runtime_val"],
                "canonical CURRENT observation changed; no first-release promotion")
        period=parse_reference_period(cand[0].get("last_date"),p["runtime_freq"])
        require(period and period[0].strftime("%Y-%m")==p["runtime_period"],
                "Growth current observed reference period changed")
        ev=x.get("events")
        require(isinstance(ev,list) and len(ev)==(2 if c=="EUR" else 1),
                "event count or revision semantics changed")
        checked=[_check_event(ev[0],p,currency=c)]
        if c=="EUR":
            checked.append(_check_event(ev[1],p,currency=c,is_revision=True))
        result.append(source(c,"growth",p["id"],p["freq"],p["unit"],p["publisher"],
            period_semantics=p["sem"],
            evidence="OFFICIAL_G8_GROWTH_SIX_WEB_BRIDGES_OCT_2026",
            notes=[
                NOTES[c],
                "Research publication statement, not original release-day archived bytes or full revision chain",
                "The canonical G8 Growth series is NOT selected; date/metric agreement does not authorize Macro scoring",
                "Official local release clock with UTC offset" if p["clock"] is not None
                else "Date-only event: conservative following UTC day, not real intraday release instant",
            ],events=checked))
    require(len(result)==6 and len({v["currency"] for v in result})==6,
            "each formerly missing Growth FX currency must have exactly one bounded candidate")
    return result
