"""Propagate verified recurring issuer releases to the shared V3 snapshot.
GDP: comparable quarter/revision replaces the corresponding growth observation.
Monthly CPI/PCE: distinct context, never conflated with quarterly CPI or index
levels; no changes to quantitative weights or historical PIT claims.
"""
from datetime import date
import re

def period_key(row):
    p=row["reference_period"]
    q=re.fullmatch(r"Q([1-4]) (20\d{2})",p)
    if q:
        return int(q[2])*12+int(q[1])*3
    from validation.macro.recurring_official_actuals_v1 import MONTHS
    month,year=p.split()
    return int(year)*12+MONTHS.index(month)+1

def apply(countries, rows, as_of):
    cutoff=date.fromisoformat(as_of)
    latest={}
    for row in rows:
        if row["ccy"] not in countries or date.fromisoformat(row["as_of"])>cutoff:
            continue
        family=(row["ccy"],row["event_type"])
        rank=(period_key(row),row["as_of"],{"advance":1,"second":2,"third":3}.get(row.get("publication_stage"),0))
        if family not in latest or rank>latest[family][0]:
            latest[family]=(rank,row)
    for c,row in countries.items():
        found=[r for (_,r) in latest.values() if r["ccy"]==c]
        if found:
            row["issuer_releases"]=sorted(found,key=lambda r:(r["as_of"],r["event_key"]),reverse=True)
    gdp=latest.get(("USD","GROWTH"))
    if not gdp:
        return
    row=gdp[1]
    g=countries["USD"]["growth"]
    q,y=re.fullmatch(r"Q([1-4]) (20\d{2})",row["reference_period"]).groups()
    q,y=int(q),int(y)
    quarter=f"{y}Q{q}"
    if quarter<g["reference_quarter"] or (quarter==g["reference_quarter"] and row["as_of"]<g["publisher_release_day"]):
        return
    metric=next(m for m in row["metrics"] if m["id"]=="US_REAL_GDP_SAAR")
    def record(quarter, value, stage):
        return {"reference_quarter":quarter,"publisher_release_day":row["as_of"],
            "publisher_source":row["source_url"],"reported_value":value,
            "reported_unit":"PERCENT_SAAR_ANNUALIZED","publication_stage":stage,
            "nonannualized_qoq_descriptive_pct":round(100*((1+value/100)**.25-1),6),
            "is_growth_strength_score":False,
            "national_definitions_are_not_fully_cross_country_equivalent":True,
            "later_revisions_not_identical_to_first_release":True,
            "historical_pit_training_vintages_certified":False,
            "source_first_observed_at_utc":row["first_runner_observed_at_utc"],
            "issuer_event_key":row["event_key"]}
    current=record(quarter,metric["value_percent"],row["publication_stage"].upper())
    prior=metric["previous_period_percent"]
    if prior is not None:
        prev=f"{y if q>1 else y-1}Q{q-1 if q>1 else 4}"
        current["prior_documented_quarter"]=record(prev,prior,"PRIOR_QUARTER_IN_SAME_EDITION")
        current["prior_value_from_same_bea_edition"]=True
    countries["USD"]["growth"]=current
