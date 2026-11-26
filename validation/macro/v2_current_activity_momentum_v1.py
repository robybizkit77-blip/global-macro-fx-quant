"""Current-vintage descriptive activity momentum, separate from GDP shadow scoring.

Explicit fixed source selection; no mixing nominal demand with real activity,
no cross-country aggregate, no historical PIT or trading signal.
"""
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from validation.macro.v2_g8_observed_feature_bridge_v1 import (
    ROOT, normalized_source, period, index_to_period,
)

# Currency, exact source ID, frequency, economic concept. Japan retail is
# excluded because its price basis is not established by the stored label.
SOURCES = {
    "USD": [("US_INDPRO_history_value","M","REAL_INDUSTRIAL_OUTPUT"),
            ("US_PCEC96_history_value","M","REAL_CONSUMPTION")],
    "EUR": [("EA_IP_history_value","M","REAL_INDUSTRIAL_OUTPUT"),
            ("EA_RETAIL_VOL_history_value","M","REAL_RETAIL_VOLUME")],
    "GBP": [("UK_PRODUCTION_history_value","M","REAL_PRODUCTION"),
            ("UK_RETAIL_VOL_history_value","M","REAL_RETAIL_VOLUME")],
    "JPY": [("JP_IIP_history_value","M","REAL_INDUSTRIAL_OUTPUT")],
    "CHF": [("CH_PRODUCTION_history_value","M","REAL_INDUSTRIAL_OUTPUT"),
            ("CH_RETAIL_REAL_history_value","M","REAL_RETAIL_VOLUME")],
    "CAD": [("CA_REAL_GDP_M_history_value","M","REAL_GDP_BY_INDUSTRY"),
            ("CA_RETAIL_VOLUME_history_value","M","REAL_RETAIL_VOLUME")],
    "AUD": [("AU_HOUSEHOLD_SPENDING_history_value","M","NOMINAL_HOUSEHOLD_SPENDING")],
    "NZD": [("NZ_RETAIL_VOLUME_Q_history_value","Q","REAL_RETAIL_VOLUME")],
}


def momentum(data, frequency):
    """Rates on consecutive economic periods, no filling, no period skipping."""
    t = max(data)
    rates = []
    for end in (t-2, t-1, t):
        needed = list(range(end-5,end+1)) if frequency == "M" else [end-1,end]
        if any(i not in data for i in needed):
            rates.append(None)
            continue
        x = [data[i][1] for i in needed]
        if any(v <= 0 for v in x):
            raise ValueError("positive index/volume levels required")
        rates.append(100*(sum(x[3:])/sum(x[:3])-1) if frequency == "M"
                     else 100*(x[-1]/x[-2]-1))
    a,b,c = rates
    vel = c-b if b is not None and c is not None else None
    acc = c-2*b+a if all(v is not None for v in rates) else None
    prev = b-a if a is not None and b is not None else None
    return {"reference_period":data[t][0],
            "level":data[t][1], "momentum_pct":c,
            "previous_momentum_pct":b, "velocity_pp":vel,
            "acceleration_pp":acc,
            "turning_point":("DOWN_TO_UP" if prev is not None and vel is not None and prev < 0 < vel
                             else "UP_TO_DOWN" if prev is not None and vel is not None and prev > 0 > vel
                             else "NONE" if prev is not None and vel is not None else None),
            "horizon":"ROLLING_3M_OVER_PREVIOUS_3M" if frequency=="M" else "QOQ",
            "change_interval":"MONTH" if frequency=="M" else "QUARTER"}


def build(series, *, today):
    result = {}
    for c, specs in SOURCES.items():
        out = []
        for rid, freq, concept in specs:
            rows = [r for r in series[c] if r.get("id")==rid]
            if len(rows)!=1:
                raise ValueError("missing/duplicate "+rid)
            row=rows[0]
            provenance=row.get("current_vintage_provenance") or {}
            if (row.get("frequency")!=freq or row.get("category")!="Crescita"
                or provenance.get("source_series_first_release_PIT_certified") is not False
                or provenance.get("historical_levels_may_be_revised_again") is not True
                or not provenance.get("status","").endswith("NOT_PIT")):
                raise ValueError("source contract drift "+rid)
            data,_=normalized_source(row,freq)
            newest=max(data)
            cutoff=period(today.strftime("%Y-%m") if freq=="M" else
                          f"{today.year:04d}-{((today.month-1)//3+1)*3:02d}",freq)[0]
            if newest>cutoff or period(row["last_date"],freq)[0]!=newest or data[newest][1]!=row["last_value"]:
                raise ValueError("latest observation mismatch "+rid)
            out.append({"series_id":rid,"label":row["label"],"unit":row["unit"],
                        "concept":concept,"nominal_not_real":concept.startswith("NOMINAL"),
                        "source_provenance":provenance["status"], **momentum(data,freq)})
        result[c]=out
    return {"schema":"GMFQ_G8_CURRENT_ACTIVITY_MOMENTUM_RESEARCH_V1",
            "as_of":today.isoformat(),"countries":result,
            "gdp_shadow_score_unchanged":True,
            "no_cross_country_momentum_aggregation":True,
            "no_historical_pit_replay":True,"safe_to_publish_D":False,
            "safe_to_update_pairs":False,"writes_live_data":False}


def run():
    return build(json.loads((ROOT/"live_data/sections/MACRO_SERIES.json").read_text()),
                 today=datetime.now(ZoneInfo("Europe/Rome")).date())

if __name__=="__main__":
    print(json.dumps(run(),sort_keys=True))
