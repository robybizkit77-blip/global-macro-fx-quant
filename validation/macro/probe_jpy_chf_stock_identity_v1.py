"""Read-only historical identity diagnostics for already live BoJ/SNB stock proxies."""
import json,statistics,io,math
from openpyxl import load_workbook
from validation.estimated.refresh_jpy_reserve_balances_proxy_v1 import _row_period,_number
from datetime import datetime,timezone
from validation.macro.prepare_gbp_boe_revised_v1 import SOURCE,need
from validation.estimated.refresh_jpy_reserve_balances_proxy_v1 import _fetch_workbook,_extract_series
from validation.estimated.refresh_chf_residual_proxies_v1 import get_json,extract_single_series,monthly_observations,SIGHT_URL,SIGHT_DIMSEL
def compare(row,obs):
    need(len(row["dates"])==len(row["values"]),"legacy history mismatch")
    old={d:float(v) for d,v in zip(row["dates"],row["values"])}
    need(len(old)==len(row["dates"])>=36,"duplicate/short legacy history")
    overlap=sorted(set(old)&set(obs))
    need(len(overlap)==len(old),"source does not cover full legacy window")
    errors=[abs(obs[d]-old[d])/max(abs(old[d]),1) for d in overlap]
    return {"overlap":len(overlap),"exact":sum(abs(obs[d]-old[d])<=1e-6 for d in overlap),"median_relative":statistics.median(errors),"max_relative":max(errors),"largest_differences":[{"period":d,"legacy":old[d],"official":obs[d]} for d in sorted(overlap,key=lambda d:abs(obs[d]-old[d]),reverse=True)[:8]],"new":{d:obs[d] for d in sorted(obs) if d>max(old)}}
def main():
    doc=json.loads(SOURCE.read_text());now=datetime.now(timezone.utc);fail=[]
    for ccy,ident in (("JPY","JP_BOJ_RESERVE_BALANCES_history_value"),("CHF","CH_SNB_SIGHT_DEPOSITS_DOMESTIC_BANKS_history_value")):
        try:
            rows=[r for r in doc[ccy] if r["id"]==ident];need(len(rows)==1,"unique row required")
            row=rows[0]
            if ccy=="JPY":
                need(row["unit"]=="100 million yen" and row["frequency"]=="M","legacy identity mismatch")
                raw=_fetch_workbook();candidate=_extract_series(raw);obs=candidate["series"];meta={k:v for k,v in candidate.items() if k!="series"}
                # Test all workbook columns on the exact same historical months.
                # End-of-period and average balance concepts are not interchangeable.
                wb=load_workbook(io.BytesIO(raw),read_only=True,data_only=True)
                candidates=[]
                for ws in wb.worksheets:
                    sheet=list(ws.iter_rows(values_only=True))
                    for col in range(1,max(map(len,sheet))):
                        series={};duplicates=False
                        for line in sheet:
                            if len(line)<=col:continue
                            d=_row_period(line);v=_number(line[col])
                            if not d or v is None or v<=0:continue
                            if d in series:duplicates=True;break
                            series[d]=v
                        if duplicates or not set(row["dates"])<=set(series):continue
                        audit=compare(row,series)
                        headers=[str(line[col]) for line in sheet[:20] if len(line)>col and line[col] is not None and not isinstance(line[col],(int,float))]
                        candidates.append({"sheet":ws.title,"column":col+1,"header":headers[:10],**audit})
                wb.close()
                print("BOJ_RESERVE_WORKBOOK_VARIANTS",json.dumps(sorted(candidates,key=lambda c:c["median_relative"])[:8],sort_keys=True))
            else:
                need(row["unit"]=="CHF millions" and row["frequency"]=="M","legacy identity mismatch")
                raw,url=get_json(SIGHT_URL,{"dimSel":SIGHT_DIMSEL,"fromDate":min(row["dates"]),"toDate":now.strftime("%Y-%m")})
                key,meta,values=extract_single_series(raw,"BSTA@SNB.MONA_U.BIL.AKT.FMI.GGU{U,T,T,A40}")
                need(meta.get("frequency")=="P1M" and meta.get("unit")=="CHF" and meta.get("scale")=="3","source metadata mismatch")
                obs={d:v/1000 for d,v in monthly_observations(values,now).items()}
            print("RESIDUAL_STOCK_IDENTITY",ident,json.dumps({"source_metadata":meta,**compare(row,obs)},sort_keys=True))
        except (OSError,RuntimeError,ValueError,KeyError,TypeError) as e:
            fail.append(ident);print("RESIDUAL_STOCK_WITHHELD",ident,repr(e))
    if fail:raise SystemExit("Unproven source coverage: "+str(fail))
if __name__=="__main__":main()
