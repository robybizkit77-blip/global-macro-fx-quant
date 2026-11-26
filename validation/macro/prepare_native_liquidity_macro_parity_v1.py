"""Synchronize two exact-source native monthly histories with certified Macro data.
JPY credit: append only after exact historical overlap.
CAD M2++: verify full native history directly against BoC before replacing revised levels.
No native policy, country direction, FX scoring or unrelated lane changes.
"""
import argparse,copy,json,math,re
from datetime import datetime,timezone
from pathlib import Path
from validation.macro.prepare_cad_boc_revised_v1 import prepare_row as boc_prepare,fetch as boc_fetch
ROOT=Path(__file__).resolve().parents[2]
CONFIG={
 ("JPY","credit"):("JP_BANK_CREDIT_DOMESTIC_BANKS_history_value","DLCLAEDBLTTO","Credito bancario","100 million yen","BOJ_CURRENT_REVISED_HISTORY_NOT_PIT"),
 ("CAD","money"):("CA_M2PP_SA_history_value","V41552801","M2++","CAD millions","BOC_CURRENT_REVISED_HISTORY_NOT_PIT"),
}
def need(ok,why):
    if not ok:raise ValueError(why)
def month(d):
    need(isinstance(d,str) and re.fullmatch(r"\d{4}-(?:0[1-9]|1[0-2])(?:-01)?",d),"invalid month")
    return d[:7]
def history(row,now):
    ds=row["dates"];vs=row["values"]
    need(len(ds)==len(vs) and len(ds)>=24 and ds[-1]==row["last_date"] and vs[-1]==row["last_value"],"invalid history terminal fields")
    ms=[month(d) for d in ds]
    ord=lambda m:int(m[:4])*12+int(m[5:7])
    need(all(ord(b)-ord(a)==1 for a,b in zip(ms,ms[1:])) and ms[-1]<now.strftime("%Y-%m"),"noncontiguous or future month")
    need(all(type(v) in (float,int) and math.isfinite(v) and v>0 for v in vs),"invalid level")
    return dict(zip(ms,vs))
def prepare(macro,native,now,fetcher=boc_fetch):
    need(now.utcoffset() is not None,"aware clock required")
    out=copy.deepcopy(native);receipts=[]
    for (ccy,role),(ident,series,label,unit,source_status) in CONFIG.items():
        try:
            rows=[r for r in macro[ccy] if r["id"]==ident];need(len(rows)==1,"unique macro source required")
            src=rows[0];dst=out[ccy][role];proof=src.get("current_vintage_provenance",{})
            need(src["unit"]==unit and src["frequency"]=="M" and src["label"]==dst["label"]==label,"unit/label mismatch")
            need(proof.get("source_series_id")==series and proof.get("status")==source_status and proof.get("source_series_first_release_PIT_certified") is False,"uncertified macro source")
            old=history(dst,now);new=history(src,now);overlap=set(old)&set(new)
            need(len(overlap)>=24 and max(new)>=max(old) and max(old) in new,"insufficient overlap or source regression")
            if ccy=="JPY":
                need(all(abs(old[m]-new[m])<=1e-6 for m in overlap),"JPY credit historical mismatch; append only")
                merged={**old,**new}
                # Preserve native prefix, including exact original historical values.
                merged.update(old)
                dates=list(dst["dates"])+[m for m in sorted(new) if m>max(old)]
                values=list(dst["values"])+[new[m] for m in sorted(new) if m>max(old)]
            else:
                # The source may revise older observations: never splice a shorter
                # revised Macro window into a longer native history.
                candidate=dict(dst,id=ident,source_file=src["source_file"],frequency="M",unit=unit)
                boc_prepare(candidate,ident,now,fetcher)
                full=history(candidate,now)
                need(set(old)<=set(full) and set(new)<=set(full) and max(full)==max(new),"full official history does not match macro vintage")
                need(all(abs(full[m]-new[m])<=1e-6 for m in new),"different BoC vintage; retain prior native copy")
                dates=candidate["dates"];values=candidate["values"]
            before=dst["last_date"];changed=dst["dates"]!=dates or dst["values"]!=values
            if changed:dst.update(dates=dates,values=values,last_date=dates[-1],last_value=values[-1])
            history(dst,now)
            receipts.append(dict(ccy=ccy,role=role,id=ident,source_series_id=series,status="READY" if changed else "NO_CHANGE",before=before,after=dst["last_date"],overlap=len(overlap),revised_months=sum(1 for m in old if abs(old[m]-history(dst,now)[m])>1e-6)))
        except (OSError,ValueError,KeyError,TypeError) as exc:
            out[ccy][role]=copy.deepcopy(native[ccy][role])
            receipts.append(dict(ccy=ccy,role=role,id=ident,status="WITHHELD",reason=str(exc)))
    return out,{"schema":"GMFQ_NATIVE_LIQUIDITY_MACRO_PARITY_V1","status":"READY" if any(x["status"]=="READY" for x in receipts) else "NO_CHANGE_OR_WITHHELD","series":receipts,"first_release_PIT_certified":False,"macro_mutated":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",type=Path,required=True);p.add_argument("--receipt",type=Path,required=True);a=p.parse_args()
    need(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary output only")
    macro=json.loads((ROOT/"live_data/sections/MACRO_SERIES.json").read_text());native=json.loads((ROOT/"live_data/sections/NATIVE_LIQ_DATA.json").read_text())
    out,receipt=prepare(macro,native,datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True);a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n");a.receipt.write_text(json.dumps(receipt,sort_keys=True)+"\n");print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
