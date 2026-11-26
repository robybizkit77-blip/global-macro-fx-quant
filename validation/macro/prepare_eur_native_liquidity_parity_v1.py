"""Synchronize exact certified ECB histories to native EUR lanes; retain full window."""
import argparse,copy,json,math,statistics
from datetime import datetime,timezone,date
from pathlib import Path
from validation.macro.prepare_eur_ecb_bsi_monthly_revised_v1 import observations,CONFIG as BSI
from validation.macro.prepare_eur_ecb_daily_revised_v1 import prepare_row as daily_prepare
from validation.liquidity.refresh_ecb_eur_nfc_credit_v1 import fetch
ROOT=Path(__file__).resolve().parents[2]
CONFIG={
 "liquidity":("EA_EXCESS_LIQUIDITY_history_value","ILM.D.U2.C.EXLIQ.U2.EUR","Liquidità in eccesso"),
 "money":("EA_M3_history_value","BSI.M.U2.Y.V.M30.X.1.U2.2300.Z01.E","M3"),
 "credit":("EA_NFC_LOANS_history_value","BSI.M.U2.N.A.A20.A.1.U2.2240.Z01.E","Prestiti imprese"),
}
def need(ok,why):
    if not ok:raise ValueError(why)
def history(row,role):
    ds=row["dates"];vs=row["values"];length=10 if role=="liquidity" else 7
    need(len(ds)==len(vs)>=40 and ds[-1]==row["last_date"] and vs[-1]==row["last_value"],"invalid terminal fields")
    keys=[d[:length] for d in ds]
    need(keys==sorted(set(keys)) and all(math.isfinite(v) for v in vs),"invalid or duplicate history")
    return dict(zip(keys,vs))
def prepare(macro,native,now,fetcher=fetch):
    need(now.utcoffset() is not None,"aware clock required")
    out=copy.deepcopy(native);receipts=[]
    for role,(ident,key,label) in CONFIG.items():
        try:
            hits=[x for x in macro["EUR"] if x["id"]==ident];need(len(hits)==1,"unique macro source required")
            src=hits[0];dst=out["EUR"][role];p=src.get("current_vintage_provenance",{})
            need(src["label"]==dst["label"]==label and p.get("status")=="ECB_CURRENT_REVISED_HISTORY_NOT_PIT" and p.get("source_series_id")==key and p.get("source_series_first_release_PIT_certified") is False,"unverified macro source identity")
            old=history(dst,role);canonical=history(src,role)
            if role=="liquidity":
                row=dict(dst,id=ident,source_file=src["source_file"],unit="EUR millions",frequency="D")
                daily_prepare(row,ident,now,fetcher)
                full=history(row,role)
                dates=[d+"T00:00:00.000Z" for d in full]
            else:
                _,_,lo,hi=BSI[ident]
                full,_,_=observations(key,min(old),now,fetcher,lo,hi)
                full=dict(sorted(full.items()));dates=list(full)
            need(set(old)<=set(full) and set(canonical)<=set(full) and max(full)==max(canonical),"full native history does not match macro vintage or coverage")
            need(all(abs(full[d]-v)<=1e-6 for d,v in canonical.items()),"source vintage differs from macro; hold native copy")
            errors=[abs(full[d]-v)/max(1,abs(v)) for d,v in old.items()]
            need(statistics.median(errors)<=.002 and max(errors)<=.02,"native source identity mismatch")
            values=list(full.values());before=dst["last_date"];changed=dst["dates"]!=dates or dst["values"]!=values
            if changed:dst.update(dates=dates,values=values,last_date=dates[-1],last_value=values[-1])
            receipts.append({"ccy":"EUR","role":role,"id":ident,"status":"READY" if changed else "NO_CHANGE","before":before,"after":dst["last_date"],"source_series_id":key,"full_count":len(full),"canonical_exact_overlap":len(canonical),"native_overlap":len(old),"max_relative_revision":max(errors)})
        except (OSError,ValueError,KeyError,TypeError) as exc:
            out["EUR"][role]=copy.deepcopy(native["EUR"][role])
            receipts.append({"ccy":"EUR","role":role,"id":ident,"status":"WITHHELD","reason":str(exc)})
    return out,{"schema":"GMFQ_EUR_NATIVE_LIQUIDITY_PARITY_V1","series":receipts,"status":"READY" if any(x["status"]=="READY" for x in receipts) else "NO_CHANGE_OR_WITHHELD","first_release_PIT_certified":False,"macro_mutated":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",type=Path,required=True);p.add_argument("--receipt",type=Path,required=True);a=p.parse_args()
    need(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary output only")
    macro=json.loads((ROOT/"live_data/sections/MACRO_SERIES.json").read_text());native=json.loads((ROOT/"live_data/sections/NATIVE_LIQ_DATA.json").read_text())
    out,receipt=prepare(macro,native,datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True);a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n");a.receipt.write_text(json.dumps(receipt,sort_keys=True)+"\n");print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
