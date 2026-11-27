"""Descriptive labour and inflation dynamics from existing verified macro sources.
Rates: changes in percentage points, never percentage changes of rates.
Employment counts: consecutive 3m/3m or QoQ volume momentum.
No FX scores, historic PIT or aggregation across economic concepts.
"""
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from validation.macro.v2_g8_observed_feature_bridge_v1 import (
    ROOT, FX, period, normalized_source, transformed_series, pillar_feature,
)
from validation.macro.v2_current_activity_momentum_v1 import momentum

SCHEMA="GMFQ_G8_LABOUR_INFLATION_DYNAMICS_RESEARCH_V1"
# Explicit additional series, frequency, dimension, economic measurement.
EXTRA={
"USD":[("US_CPILFESL_history_value","M","inflation","YOY_INDEX"),
       ("US_PCEPILFE_history_value","M","inflation","YOY_INDEX"),
       ("US_PCEPI_history_value","M","inflation","YOY_INDEX"),
       ("US_JTSHIR_history_JTSHIR","M","labour","RATE"),
       ("US_JTSJOL_history_value","M","labour","COUNT"),
       ("US_JTSQUR_history_JTSQUR","M","labour","RATE"),
       ("US_PAYEMS_history_value","M","labour","COUNT"),
       ("US_AHE_TOTAL_PRIVATE_history_value","M","labour","YOY_INDEX")],
"EUR":[("EA_HICP_CORE_YOY_history_value","M","inflation","RATE"),
       ("EA_HICP_SERVICES_YOY_history_value","M","inflation","RATE")],
"GBP":[("UK_CPI_CORE_YOY_history_value","M","inflation","RATE"),
       ("UK_PAYE_PAYROLLED_EMPLOYEES_SA_history_value","M","labour","COUNT"),
       ("UK_EMPLOYMENT_RATE_history_value","M","labour","RATE")],
"JPY":[("JP_CPI_CORE_YOY_history_value","M","inflation","RATE"),
       ("JP_EMPLOYED_history_value","M","labour","COUNT")],
"CHF":[("CH_CPI_CORE1_YOY_history_value","M","inflation","RATE")],
"CAD":[("CA_CPI_MEDIAN_YOY_history_value","M","inflation","RATE"),
       ("CA_CPI_TRIM_YOY_history_value","M","inflation","RATE"),
       ("CA_EMPLOYMENT_history_value","M","labour","COUNT")],
"AUD":[("AU_CPI_HEADLINE_M_YOY_context_value","M","inflation","RATE"),
       ("AU_CPI_TRIMMED_MEAN_M_YOY_context_value","M","inflation","RATE"),
       ("AU_CPI_TRIMMED_MEAN_Q_YOY_history_value","Q","inflation","RATE"),
       ("AU_EMPLOYMENT_history_value","M","labour","COUNT")],
"NZD":[("NZ_CORE_INFLATION_SFM_Q_history_value","Q","inflation","RATE"),
       ("NZ_EMPLOYED_history_value","Q","labour","COUNT")],
}

def rate_dynamics(data):
    t=max(data)
    val=lambda i:data[i][1] if i in data else None
    x,y,z=val(t),val(t-1),val(t-2)
    v=x-y if y is not None else None
    old=y-z if y is not None and z is not None else None
    return {"reference_period":data[t][0],"level":x,"previous_level":y,
            "velocity_pp":v,"acceleration_pp":v-old if v is not None and old is not None else None,
            "turning_point":("DOWN_TO_UP" if old<0<v else "UP_TO_DOWN" if old>0>v else "NONE")
            if old is not None and v is not None else None}

def build(series,heat,registry,today):
    out={}
    for c in FX:
        rows={r["id"]:r for r in series[c]}
        results=[]
        for dim in ("labour","inflation"):
            reg=registry[c+"."+dim]
            rid=(reg.get("historical_replay_evidence") or {}).get("macro_series_id") or reg["series_id"]+"_history_value"
            row=rows[rid]
            freq=reg["frequency"]
            pillar_feature(c,dim,reg,row,heat["currencies"][c][dim],today)
            data=transformed_series(normalized_source(row,freq)[0],reg["transformation"])
            results.append(dict(series_id=rid,label=row["label"],pillar=dim,frequency=freq,
                measurement="RATE",unit="%" if dim=="labour" else "% YoY",quality="REGISTERED_CURRENT_REVISED_NOT_PIT",
                **rate_dynamics(data)))
        for rid,freq,dim,kind in EXTRA[c]:
            try:
                row=rows[rid]
                provenance=row.get("current_vintage_provenance") or {}
                if (row.get("frequency")!=freq or provenance.get("source_series_first_release_PIT_certified") is not False
                    or not provenance.get("status","").endswith("NOT_PIT") or row.get("category")!=("Lavoro" if dim=="labour" else "Inflazione")):
                    raise ValueError("source metadata mismatch")
                raw=normalized_source(row,freq)[0]
                t=max(raw)
                if period(row["last_date"],freq)[0]!=t or raw[t][1]!=row["last_value"]:
                    raise ValueError("latest source mismatch")
                cutoff=12*today.year+today.month-1 if freq=="M" else 4*today.year+(today.month-1)//3
                if t>cutoff: raise ValueError("future observation")
                data=transformed_series(raw,"yoy_pct_from_index") if kind=="YOY_INDEX" else raw
                if max(data)!=t: raise ValueError("latest annual comparison missing")
                result=momentum(data,freq) if kind=="COUNT" else rate_dynamics(data)
                results.append(dict(series_id=rid,label=row["label"],pillar=dim,frequency=freq,
                    measurement="COUNT_MOMENTUM" if kind=="COUNT" else "RATE",
                    unit=row["unit"] if kind=="COUNT" else "% YoY" if kind=="YOY_INDEX" or dim=="inflation" else "%",
                    quality=provenance["status"],**result))
            except (ValueError,KeyError,TypeError,ArithmeticError) as exc:
                results.append(dict(series_id=rid,label=rid,pillar=dim,frequency=freq,
                    measurement="WITHHELD",quality="SOURCE_CHECK_FAILED",reason=str(exc)))
        out[c]=results
    return dict(schema=SCHEMA,as_of=today.isoformat(),countries=out,
                safe_to_publish_D=False,safe_to_update_pairs=False,no_cross_country_aggregation=True,
                historical_PIT_certified=False,writes_live_data=False)

def run():
    load=lambda p:json.loads((ROOT/p).read_text())
    return build(load("live_data/sections/MACRO_SERIES.json"),load("live_data/sections/MACRO_THERMOMETER_DATA.json"),
                 load("validation/macro/MACRO_SOURCE_REGISTRY_2026-10-08.json")["series"],
                 datetime.now(ZoneInfo("Europe/Rome")).date())
