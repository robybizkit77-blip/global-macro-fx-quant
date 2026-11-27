"""Align fifteen native liquidity lanes with verified full official current vintages."""
import argparse,copy,csv,io,json,math,statistics
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlencode,urlsplit
from validation.macro import prepare_us_monthly_revised_v1 as us,prepare_chf_snb_revised_v1 as ch,prepare_aud_rba_stocks_revised_v1 as au,prepare_cad_boc_revised_v1 as ca
from validation.macro import prepare_us_weekly_daily_revised_v1 as usw, prepare_gbp_boe_revised_v1 as gb, prepare_chf_snb_balance_mortgage_v1 as chb, prepare_chf_mona_credit_v1 as chc, prepare_jpy_boj_reserve_average_v1 as jp
from validation.macro import prepare_us_quarterly_cfna_revised_v1 as usq, prepare_jpy_tankan_actual_v1 as jpt, prepare_cad_boc_quarterly_v1 as caq
ROOT=Path(__file__).resolve().parents[2]
CONFIG={
 ("USD","liquidity"):("US_M2SL_history_value","M2SL","M2","Billions of U.S. dollars, seasonally adjusted","M","FRED_PUBLISHED_CURRENT_REVISED_HISTORY_NOT_PIT"),
 ("CHF","money"):("CH_M3_history_value","EPB@SNB.snbmonagg{B,GM3}","M3","CHF millions","M","SNB_CURRENT_REVISED_HISTORY_NOT_PIT"),
 ("AUD","money"):("AU_BROAD_MONEY_SA_history_value","DMABMS","Broad money","AUD billions","M","RBA_CURRENT_REVISED_HISTORY_NOT_PIT"),
 ("AUD","credit"):("AU_CREDIT_BUSINESS_CURRENT_SA_history_value","DLCACSFBS","Credito imprese","AUD billions","M","RBA_CURRENT_REVISED_HISTORY_NOT_PIT"),
 ("AUD","liquidity"):("AU_EXCHANGE_SETTLEMENT_BALANCES_history_value","ARBALESBW","Exchange Settlement balances","AUD millions","W","RBA_CURRENT_REVISED_HISTORY_NOT_PIT"),
 ("CAD","liquidity"):("CA_SETTLEMENT_BALANCES_history_value","V41886561","Settlement balances","CAD millions","M","BOC_CURRENT_REVISED_HISTORY_NOT_PIT"),
 ("USD","credit"):("US_TOTBKCR_history_value","TOTBKCR","Credito bancario totale","Billions of U.S. Dollars","W","FRED_PUBLISHED_CURRENT_REVISED_HISTORY_NOT_PIT"),
 ("GBP","liquidity"):("UK_BOE_RESERVE_BALANCES_history_value","RPWB56A","BoE — reserve balances","GBP millions","W","BOE_IADB_CURRENT_REVISED_HISTORY_NOT_PIT"),
 ("JPY","liquidity"):("JP_BOJ_RESERVE_BALANCES_history_value","BOJ_MBLONG_AVERAGE_RESERVE_BALANCES","BoJ — reserve balances","100 million yen","M","BOJ_CURRENT_REVISED_HISTORY_NOT_PIT"),
 ("CHF","liquidity"):("CH_SNB_SIGHT_DEPOSITS_DOMESTIC_BANKS_history_value","EPB@SNB.snbbipo{GB}","SNB — sight deposits","CHF millions","M","SNB_CURRENT_REVISED_HISTORY_NOT_PIT"),
 ("CHF","credit"):("CH_BANK_CREDIT_CUSTOMERS_history_value","BSTA@SNB.MONA_B.BIL.AKT.FKU{B,T,T,T,T,T,A40}","Credito bancario","CHF millions","M","SNB_CURRENT_REVISED_HISTORY_NOT_PIT"),
 ("USD","conditions"):("US_SLOOS_CI_LARGE_MIDDLE_history_value","DRTSCILM","SLOOS — standard credito imprese","Percent, not seasonally adjusted","Q","FRED_PUBLISHED_CURRENT_REVISED_HISTORY_NOT_PIT"),
 ("GBP","credit"):("UK_SECURED_LENDING_YOY_history_value","LPMVTYI","Credito garantito / secured lending YoY","Percent","M","BOE_IADB_CURRENT_REVISED_HISTORY_NOT_PIT"),
 ("JPY","conditions"):("JP_TANKAN_LENDING_ATTITUDE_history_value","TK99F0000612GCQ00000","Tankan — lending attitude","% points","Q","BOJ_CURRENT_REVISED_HISTORY_NOT_PIT"),
 ("CAD","conditions"):("CA_SLOS_BUSINESS_LENDING_history_value","SLOS_BUS_LEND","SLOS — condizioni credito imprese","Balance of opinion","Q","BOC_CURRENT_REVISED_HISTORY_NOT_PIT"),
}
def need(ok,why):
    if not ok:raise ValueError(why)
def key(d,f):
    if f=="Q" and len(d)==7 and d[4:6]=="-Q":
        year=int(d[:4]);q=int(d[-1]);need(1<=q<=4,"invalid quarter")
        return f"{year:04d}-Q{q}"
    if "/" in d:d=datetime.strptime(d,"%d/%m/%Y").date().isoformat()
    elif " " in d:d=datetime.strptime(d,"%d %b %Y").date().isoformat()
    if f=="M":
        datetime.strptime(d[:7],"%Y-%m");return d[:7]
    day=datetime.strptime(d,"%Y-%m-%d").date()
    if f=="Q":
        need(day.day==1 and day.month in (1,4,7,10),"invalid quarter start")
        return f"{day.year:04d}-Q{(day.month-1)//3+1}"
    return day.isoformat()
def history(row,f,now,signed=False,current_quarter=False):
    ds=row["dates"];vs=row["values"]
    need(len(ds)==len(vs)>=24 and ds[-1]==row["last_date"] and vs[-1]==row["last_value"],"invalid terminal fields")
    keys=[key(d,f) for d in ds]
    need(keys==sorted(set(keys)) and all(type(v) in (float,int) and math.isfinite(v) and (signed or v>=0) for v in vs),"invalid history")
    if f=="M":
        ordinal=lambda m:int(m[:4])*12+int(m[5:7])
        need(keys[-1]<now.strftime("%Y-%m") and all(ordinal(b)-ordinal(a)==1 for a,b in zip(keys,keys[1:])),"monthly gap/future")
    elif f=="Q":
        ordinal=lambda q:int(q[:4])*4+int(q[-1])-1
        current=now.year*4+(now.month-1)//3
        need(ordinal(keys[-1])<=current-int(not current_quarter) and all(ordinal(b)-ordinal(a)==1 for a,b in zip(keys,keys[1:])),"quarterly gap/future")
    else:
        need(keys[-1]<=now.date().isoformat() and all((datetime.fromisoformat(b)-datetime.fromisoformat(a)).days==7 for a,b in zip(keys,keys[1:])),"weekly gap/future")
    return dict(zip(keys,vs))
def load_us_m2_full(row,now,fetcher=us.fetch):
    # The shared household parser deliberately trims history to October 2019.
    # Native liquidity starts in January 2016: retrieve and verify the entire
    # requested official vintage rather than truncating or splicing histories.
    series="M2SL";start=key(row["dates"][0],"M")
    raw,final=fetcher("https://fred.stlouisfed.org/series/"+series)
    need(urlsplit(final).hostname=="fred.stlouisfed.org" and urlsplit(final).path.rstrip("/")=="/series/"+series,"wrong FRED metadata endpoint")
    us.metadata(raw,series,"M2","Billions of Dollars")
    url="https://fred.stlouisfed.org/graph/fredgraph.csv?"+urlencode({"id":series,"cosd":start+"-01"})
    raw,final=fetcher(url)
    need(urlsplit(final).hostname=="fred.stlouisfed.org" and urlsplit(final).path=="/graph/fredgraph.csv","wrong FRED CSV endpoint")
    reader=csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    need(reader.fieldnames in (["observation_date",series],["DATE",series]),"wrong M2 CSV identity")
    obs={};seen=set()
    for rec in reader:
        d=datetime.strptime(rec[reader.fieldnames[0]],"%Y-%m-%d")
        m=d.strftime("%Y-%m")
        need(d.day==1 and m not in seen,"invalid or duplicate M2 month")
        seen.add(m)
        if rec[series] in ("","."):continue
        v=float(rec[series])
        need(m<now.strftime("%Y-%m") and math.isfinite(v) and v>0,"future or invalid M2 value")
        if m>=start:obs[m]=v
    ds=sorted(obs);need(len(ds)>=24 and ds[0]==start,"M2 source does not cover native start")
    vs=[obs[d] for d in ds]
    row.update(dates=ds,values=vs,last_date=ds[-1],last_value=vs[-1])
    history(row,"M",now)
    return row
def load_full(ccy,ident,row,now):
    if ident=="US_M2SL_history_value":load_us_m2_full(row,now)
    elif ident in usw.CONFIG:usw.prepare_row(row,ident,now,usw.fetch)
    elif ident in usq.CONFIG:usq.prepare_row(row,ident,now,usq.fetch)
    elif ident in jpt.CONFIG:jpt.prepare_row(row,ident,now,jpt.fetch)
    elif ident in caq.CONFIG:caq.prepare_row(row,ident,now,caq.fetch)
    elif ident in gb.CONFIG:gb.prepare_row(row,ident,now,gb.fetch)
    elif ident in jp.CONFIG:jp.prepare_row(row,now,jp._fetch_workbook())
    elif ident in chb.CONFIG:chb.prepare_row(row,ident,now,chb.fetch)
    elif ident in chc.CONFIG:chc.prepare_row(row,ident,now,chc.fetch)
    elif ccy=="CHF":ch.prepare_row(row,ident,now,ch.fetch)
    elif ccy=="CAD":ca.prepare_row(row,ident,now,ca.fetch)
    elif ccy=="AUD":
        table=au.CONFIG[ident][0]
        au.prepare_row(row,ident,now,au.fetch(au.BASE+table+"-data.csv"))
    return row
def prepare(macro,native,now,loader=load_full):
    need(now.utcoffset() is not None,"aware clock required")
    out=copy.deepcopy(native);receipts=[]
    for (c,role),(ident,series,label,unit,f,status) in CONFIG.items():
        try:
            hits=[x for x in macro[c] if x["id"]==ident];need(len(hits)==1,"unique macro source required")
            src=hits[0];dst=out[c][role];p=src.get("current_vintage_provenance",{})
            need(src["label"]==dst["label"]==label and src["unit"]==unit and src["frequency"]==f and p.get("status")==status and p.get("source_series_id")==series and p.get("source_series_first_release_PIT_certified") is False,"unverified macro identity")
            signed=role=="conditions" or ident=="UK_SECURED_LENDING_YOY_history_value"
            current_quarter=ident=="US_SLOOS_CI_LARGE_MIDDLE_history_value"
            old=history(dst,f,now,signed,current_quarter);canonical=history(src,f,now,signed,current_quarter)
            candidate=dict(copy.deepcopy(dst),id=ident,source_file=src["source_file"],unit=unit,frequency=f)
            candidate=loader(c,ident,candidate,now)
            full=history(candidate,f,now,signed,current_quarter)
            need(set(old)<=set(full) and set(canonical)<=set(full) and max(full)==max(canonical),"native window or source vintage differs")
            need(all(abs(full[d]-v)<=1e-6 for d,v in canonical.items()),"macro vintage mismatch")
            errors=[abs(full[d]-v) if signed else abs(full[d]-v)/max(1,abs(v)) for d,v in old.items()]
            audit={"median_relative_revision":statistics.median(errors),"max_relative_revision":max(errors),"exact_overlap":sum(e<=1e-10 for e in errors)}
            print("G8_NATIVE_PARITY_DIAGNOSTIC",c,role,json.dumps(audit,sort_keys=True))
            if signed:
                limits=(.12,.6) if ident=="UK_SECURED_LENDING_YOY_history_value" else ((.15,1) if c=="USD" else ((.1,2) if c=="JPY" else (.011,.1)))
                need(statistics.median(errors)<=limits[0] and max(errors)<=limits[1],"native signed series overlap mismatch")
                audit={"median_absolute_revision":statistics.median(errors),"max_absolute_revision":max(errors),"exact_overlap":sum(e<=1e-10 for e in errors)}
            else:need(audit["median_relative_revision"]<=.005 and audit["max_relative_revision"]<=.05,"native full-window identity mismatch")
            dates=candidate["dates"];values=candidate["values"];before=dst["last_date"];changed=dst["dates"]!=dates or dst["values"]!=values
            if changed:dst.update(dates=dates,values=values,last_date=dates[-1],last_value=values[-1])
            receipts.append(dict(ccy=c,role=role,id=ident,status="READY" if changed else "NO_CHANGE",before=before,after=dst["last_date"],source_series_id=series,full_count=len(full),canonical_exact_overlap=len(canonical),native_overlap=len(old),**audit))
        except (OSError,RuntimeError,ValueError,KeyError,TypeError,IndexError) as exc:
            out[c][role]=copy.deepcopy(native[c][role])
            receipts.append(dict(ccy=c,role=role,id=ident,status="WITHHELD",reason=str(exc)))
    return out,{"schema":"GMFQ_G8_NATIVE_LIQUIDITY_PARITY_V1","series":receipts,"status":"READY" if any(x["status"]=="READY" for x in receipts) else "NO_CHANGE_OR_WITHHELD","first_release_PIT_certified":False,"macro_mutated":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",type=Path,required=True);p.add_argument("--receipt",type=Path,required=True);a=p.parse_args()
    need(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary output only")
    macro=json.loads((ROOT/"live_data/sections/MACRO_SERIES.json").read_text());native=json.loads((ROOT/"live_data/sections/NATIVE_LIQ_DATA.json").read_text())
    out,receipt=prepare(macro,native,datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True);a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n");a.receipt.write_text(json.dumps(receipt,sort_keys=True)+"\n");print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
