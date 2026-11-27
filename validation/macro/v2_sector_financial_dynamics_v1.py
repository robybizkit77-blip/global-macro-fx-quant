"""Current descriptive sector and financial dynamics, no causal/FX signal.
Explicit source specs. Monthly/quarterly/weekly/daily clocks are separate.
Stock changes are not lending flows, nor break-adjusted growth.
"""
import json
import math
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo
from validation.macro.v2_g8_observed_feature_bridge_v1 import ROOT, FX
from validation.macro.v2_labour_inflation_dynamics_v1 import rate_dynamics
from validation.macro.v2_current_activity_momentum_v1 import momentum

SCHEMA="GMFQ_G8_SECTOR_FINANCIAL_DYNAMICS_RESEARCH_V1"
# Exact existing archive IDs. No substitute series for unavailable sectors.
# id, frequency, pillar, measurement, unit (only when archive metadata is blank).
SPECS={
"USD":[("US_HOUST_history_HOUST","M","housing","QUANTITY",""),
       ("US_PERMIT_history_PERMIT","M","housing","QUANTITY",""),
       ("US_HSN1F_history_HSN1F","M","housing","QUANTITY",""),
       ("US_MORTGAGE30US_history_MORTGAGE30US","W","housing","RATE",""),
       ("US_TOTBKCR_history_value","W","credit","STOCK",""),
       ("US_SLOOS_CI_LARGE_MIDDLE_history_value","Q","credit","BALANCE",""),
       ("US_WALCL_history_value","W","liquidity","STOCK",""),
       ("US_WRESBAL_history_value","W","liquidity","STOCK",""),
       ("US_M2SL_history_value","M","liquidity","STOCK",""),
       ("US_CFNAI_LEAD_INDICATOR_history_CFNAI","M","survey","INDEX","index")],
"EUR":[("EA_ECFIN_BCS_LEAD_INDICATORS_history_Industry","M","manufacturing","BALANCE","balance pp"),
       ("EA_ECFIN_BCS_LEAD_INDICATORS_history_Services","M","services","BALANCE","balance pp"),
       ("EA_ECFIN_BCS_LEAD_INDICATORS_history_Construction","M","housing","BALANCE","balance pp"),
       ("EA_ECFIN_BCS_LEAD_INDICATORS_history_ESI","M","survey","INDEX","index"),
       ("EA_HH_LOANS_history_value","M","credit","STOCK","EUR millions"),
       ("EA_NFC_LOANS_history_value","M","credit","STOCK","EUR millions"),
       ("EA_EXCESS_LIQUIDITY_history_value","D","liquidity","STOCK",""),
       ("EA_M3_history_value","M","liquidity","STOCK","EUR millions")],
"GBP":[("UK_MORTGAGE_APPROVALS_HOUSE_PURCHASE_SA_history_value","M","housing","QUANTITY",""),
       ("UK_SECURED_LENDING_YOY_history_value","M","housing","RATE",""),
       ("UK_MORTGAGE_RATE_2Y_75LTV_history_value","M","housing","RATE",""),
       ("UK_M4_SA_history_value","M","liquidity","STOCK",""),
       ("UK_BOE_RESERVE_BALANCES_history_value","W","liquidity","STOCK",""),
       ("UK_BOE_APF_LOAN_history_value","W","liquidity","STOCK","")],
"JPY":[("JP_BANK_CREDIT_DOMESTIC_BANKS_history_value","M","credit","STOCK",""),
       ("JP_NEW_LOANS_RATE_history_value","M","credit","RATE",""),
       ("JP_TANKAN_LENDING_ATTITUDE_history_value","Q","credit","BALANCE",""),
       ("JP_BOJ_TANKAN_LEAD_INDICATORS_history_Large_Manufacturing_Actual","Q","manufacturing","BALANCE","DI points"),
       ("JP_BOJ_TANKAN_LEAD_INDICATORS_history_Large_Nonmanufacturing_Actual","Q","services","BALANCE","DI points"),
       ("JP_M3_SA_history_value","M","liquidity","STOCK",""),
       ("JP_BOJ_RESERVE_BALANCES_history_value","M","liquidity","STOCK",""),
       ("JP_BOJ_TOTAL_ASSETS_history_value","M","liquidity","STOCK","")],
"CHF":[("CH_MORTGAGE_CREDIT_DOMESTIC_history_value","M","housing","STOCK",""),
       ("CH_MORTGAGE_RATE_FIXED_3_5Y_history_value","M","housing","RATE",""),
       ("CH_BANK_CREDIT_CUSTOMERS_history_value","M","credit","STOCK",""),
       ("CH_M3_history_value","M","liquidity","STOCK",""),
       ("CH_SNB_SIGHT_DEPOSITS_DOMESTIC_BANKS_history_value","M","liquidity","STOCK",""),
       ("CH_SNB_TOTAL_ASSETS_history_value","M","liquidity","STOCK","")],
"CAD":[("CA_MORTGAGE_OUTSTANDING_UNINSURED_history_value","M","housing","STOCK",""),
       ("CA_SLOS_MORTGAGE_LENDING_history_value","Q","housing","BALANCE",""),
       ("CA_BUSINESS_LOANS_OUTSTANDING_history_value","M","credit","STOCK",""),
       ("CA_SLOS_BUSINESS_LENDING_history_value","Q","credit","BALANCE",""),
       ("CA_BOC_TOTAL_ASSETS_history_value","M","liquidity","STOCK",""),
       ("CA_M2PP_SA_history_value","M","liquidity","STOCK",""),
       ("CA_SETTLEMENT_BALANCES_history_value","M","liquidity","STOCK",""),
       ("CA_BOC_BOS_LEAD_INDICATORS_history_BOS_Activity_Indicator","Q","survey","INDEX","index")],
"AUD":[("AU_CREDIT_INVESTOR_HOUSING_SA_history_value","M","housing","STOCK",""),
       ("AU_CREDIT_OWNER_OCC_HOUSING_SA_history_value","M","housing","STOCK",""),
       ("AU_CREDIT_OTHER_PERSONAL_SA_history_value","M","credit","STOCK",""),
       ("AU_BROAD_MONEY_SA_history_value","M","liquidity","STOCK",""),
       ("AU_EXCHANGE_SETTLEMENT_BALANCES_history_value","W","liquidity","STOCK",""),
       ("AU_RBA_TOTAL_ASSETS_history_value","W","liquidity","STOCK",""),
       ("AU_OECD_CLI_LEAD_INDICATOR_history_OECD_CLI_AUS","M","survey","INDEX","index")],
"NZD":[],
}
def parse(raw,freq):
    if not isinstance(raw,str): raise ValueError("date not text")
    q=re.fullmatch(r"(\d{4})-?Q([1-4])",raw)
    if q:
        if freq!="Q": raise ValueError("quarter alias on nonquarterly series")
        y,m=int(q[1]),int(q[2])*3
        return 4*y+(m-1)//3,f"{y}Q{(m-1)//3+1}"
    if re.fullmatch(r"\d{4}/\d{2}",raw): raw=raw.replace("/","-")
    if re.fullmatch(r"\d{4}-\d{2}",raw): raw+="-01"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T00:00:00Z",raw): raw=raw[:10]
    try: d=date.fromisoformat(raw)
    except ValueError:
        for fmt in ("%d/%m/%Y","%d %b %Y"):
            try: d=datetime.strptime(raw,fmt).date();break
            except ValueError: pass
        else: raise ValueError("unsupported period label "+raw)
    if freq=="M": return 12*d.year+d.month-1,d.strftime("%Y-%m")
    if freq=="Q": return 4*d.year+(d.month-1)//3,f"{d.year}Q{(d.month-1)//3+1}"
    return d.toordinal(),d.isoformat()
def calculate(data,freq,kind):
    t=max(data)
    # For daily/weekly series choose exact calendar endpoints; no weekend or holiday interpolation.
    if freq in ("D","W"):
        step=1 if freq=="D" else 7
        v=lambda i:data[i][1] if i in data else None
        x,y,z=v(t),v(t-step),v(t-2*step)
        if kind=="STOCK":
            a=100*(x/y-1) if y and y>0 and x>0 else None
            b=100*(y/z-1) if y and z and z>0 and y>0 else None
            return dict(reference_period=data[t][0],level=x,momentum_pct=a,
                        velocity_pp=a-b if a is not None and b is not None else None,acceleration_pp=None,
                        horizon="EXACT_CALENDAR_DAY" if freq=="D" else "EXACT_7_CALENDAR_DAYS")
        v1=x-y if y is not None else None
        return dict(reference_period=data[t][0],level=x,velocity_pp=v1,
                    acceleration_pp=v1-(y-z) if v1 is not None and z is not None else None)
    if kind=="QUANTITY": return momentum(data,freq)
    if kind=="STOCK":
        # End-of-period balances, not average flows: compare exact period endpoints.
        step=3 if freq=="M" else 1
        def rate(end):
            a,b=data.get(end),data.get(end-step)
            return 100*(a[1]/b[1]-1) if a and b and a[1]>0 and b[1]>0 else None
        a,b,c=rate(t),rate(t-1),rate(t-2)
        return dict(reference_period=data[t][0],level=data[t][1],momentum_pct=a,
                    velocity_pp=a-b if a is not None and b is not None else None,
                    acceleration_pp=a-2*b+c if None not in (a,b,c) else None,
                    horizon="STOCK_3M_ENDPOINT" if freq=="M" else "STOCK_QOQ_ENDPOINT")
    return rate_dynamics(data)
def build(series,today):
    out={}
    for c in FX:
        rows={r["id"]:r for r in series[c]}
        result=[]
        for rid,freq,pillar,kind,unit in SPECS[c]:
            row=rows.get(rid,{})
            base=dict(series_id=rid,label=row.get("label",rid),frequency=freq,pillar=pillar)
            try:
                p=row.get("current_vintage_provenance") or {}
                if p.get("source_series_first_release_PIT_certified") is not False or not p.get("status","").endswith("NOT_PIT"):
                    raise ValueError("unverified source metadata")
                if row.get("frequency") not in ("",None,freq) or p.get("source_frequency") not in (None,freq):
                    raise ValueError("source frequency conflict")
                dates,values=row["dates"],row["values"]
                if len(dates)!=len(values) or len(dates)<2: raise ValueError("invalid history")
                data={}
                for raw,value in zip(dates,values):
                    idx,label=parse(raw,freq)
                    if not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value): raise ValueError("invalid value")
                    if idx in data and data[idx][1]!=value: raise ValueError("conflicting periods")
                    data[idx]=(label,value)
                t=max(data)
                if t>parse(today.isoformat(),freq)[0] or t!=parse(row["last_date"],freq)[0] or data[t][1]!=row["last_value"]:
                    raise ValueError("latest date or value mismatch")
                result.append(dict(base,measurement=kind,unit=row.get("unit") or unit,quality=p["status"],**calculate(data,freq,kind)))
            except (ValueError,KeyError,TypeError,ArithmeticError) as exc:
                result.append(dict(base,measurement="WITHHELD",quality="SOURCE_CHECK_FAILED",reason=str(exc)))
        out[c]=result
    return dict(schema=SCHEMA,as_of=today.isoformat(),countries=out,safe_to_publish_D=False,
                safe_to_update_pairs=False,writes_live_data=False,no_cross_country_aggregation=True,
                historical_PIT_certified=False)
def run():
    return build(json.loads((ROOT/"live_data/sections/MACRO_SERIES.json").read_text()),
                 datetime.now(ZoneInfo("Europe/Rome")).date())
