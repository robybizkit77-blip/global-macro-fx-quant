"""Align six native liquidity lanes with verified full official current vintages."""
import argparse,copy,csv,io,json,math,statistics
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlencode,urlsplit
from validation.macro import prepare_us_monthly_revised_v1 as us,prepare_chf_snb_revised_v1 as ch,prepare_aud_rba_stocks_revised_v1 as au,prepare_cad_boc_revised_v1 as ca
ROOT=Path(__file__).resolve().parents[2]
CONFIG={
 ("USD","liquidity"):("US_M2SL_history_value","M2SL","M2","Billions of U.S. dollars, seasonally adjusted","M","FRED_PUBLISHED_CURRENT_REVISED_HISTORY_NOT_PIT"),
 ("CHF","money"):("CH_M3_history_value","EPB@SNB.snbmonagg{B,GM3}","M3","CHF millions","M","SNB_CURRENT_REVISED_HISTORY_NOT_PIT"),
 ("AUD","money"):("AU_BROAD_MONEY_SA_history_value","DMABMS","Broad money","AUD billions","M","RBA_CURRENT_REVISED_HISTORY_NOT_PIT"),
 ("AUD","credit"):("AU_CREDIT_BUSINESS_CURRENT_SA_history_value","DLCACSFBS","Credito imprese","AUD billions","M","RBA_CURRENT_REVISED_HISTORY_NOT_PIT"),
 ("AUD","liquidity"):("AU_EXCHANGE_SETTLEMENT_BALANCES_history_value","ARBALESBW","Exchange Settlement balances","AUD millions","W","RBA_CURRENT_REVISED_HISTORY_NOT_PIT"),
 ("CAD","liquidity"):("CA_SETTLEMENT_BALANCES_history_value","V41886561","Settlement balances","CAD millions","M","BOC_CURRENT_REVISED_HISTORY_NOT_PIT"),
}
def need(ok,why):
    if not ok:raise ValueError(why)
def key(d,f):
    if "/" in d:d=datetime.strptime(d,"%d/%m/%Y").date().isoformat()
    if f=="M":
        datetime.strptime(d[:7],"%Y-%m");return d[:7]
    return datetime.strptime(d,"%Y-%m-%d").date().isoformat()
def history(row,f,now):
    ds=row["dates"];vs=row["values"]
    need(len(ds)==len(vs)>=24 and ds[-1]==row["last_date"] and vs[-1]==row["last_value"],"invalid terminal fields")
    keys=[key(d,f) for d in ds]
    need(keys==sorted(set(keys)) and all(math.isfinite(v) and v>=0 for v in vs),"invalid history")
    if f=="M":
        ordinal=lambda m:int(m[:4])*12+int(m[5:7])
        need(keys[-1]<now.strftime("%Y-%m") and all(ordinal(b)-ordinal(a)==1 for a,b in zip(keys,keys[1:])),"monthly gap/future")
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
    if ccy=="USD":load_us_m2_full(row,now)
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
            old=history(dst,f,now);canonical=history(src,f,now)
            candidate=dict(copy.deepcopy(dst),id=ident,source_file=src["source_file"],unit=unit,frequency=f)
            candidate=loader(c,ident,candidate,now)
            full=history(candidate,f,now)
            need(set(old)<=set(full) and set(canonical)<=set(full) and max(full)==max(canonical),"native window or source vintage differs")
            need(all(abs(full[d]-v)<=1e-6 for d,v in canonical.items()),"macro vintage mismatch")
            errors=[abs(full[d]-v)/max(1,abs(v)) for d,v in old.items()]
            audit={"median_relative_revision":statistics.median(errors),"max_relative_revision":max(errors),"exact_overlap":sum(e<=1e-10 for e in errors)}
            print("G8_NATIVE_PARITY_DIAGNOSTIC",c,role,json.dumps(audit,sort_keys=True))
            need(audit["median_relative_revision"]<=.005 and audit["max_relative_revision"]<=.05,"native full-window identity mismatch")
            dates=candidate["dates"];values=candidate["values"];before=dst["last_date"];changed=dst["dates"]!=dates or dst["values"]!=values
            if changed:dst.update(dates=dates,values=values,last_date=dates[-1],last_value=values[-1])
            receipts.append(dict(ccy=c,role=role,id=ident,status="READY" if changed else "NO_CHANGE",before=before,after=dst["last_date"],source_series_id=series,full_count=len(full),canonical_exact_overlap=len(canonical),native_overlap=len(old),**audit))
        except (OSError,ValueError,KeyError,TypeError) as exc:
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
