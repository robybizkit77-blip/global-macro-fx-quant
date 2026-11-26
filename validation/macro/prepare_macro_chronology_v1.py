"""Correct storage chronology only: no new observations, revisions, or scoring."""
import argparse,copy,json,math,re
from datetime import date
from pathlib import Path
SOURCE=Path(__file__).resolve().parents[2]/"live_data/sections/MACRO_SERIES.json"
CONFIG={("USD","US_UNRATE_history_value"):"month",**{("JPY","JPY_RATES_2016_2026_"+t):"day" for t in ("2Y","5Y","10Y","30Y")}}
def need(ok,msg):
    if not ok:raise ValueError(msg)
def key(raw,mode):
    if mode=="month":
        need(isinstance(raw,str) and re.fullmatch(r"\d{4}-\d{2}(-01)?",raw),"unexpected monthly date")
        return date.fromisoformat(raw[:7]+"-01").strftime("%Y-%m")
    need(isinstance(raw,str) and re.fullmatch(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}",raw),"unexpected daily date")
    return date(*map(int,re.split("[-/]",raw))).isoformat()
def reconcile(row,mode):
    ds=row["dates"];vs=row["values"]
    need(len(ds)==len(vs)>0 and ds[-1]==row["last_date"] and vs[-1]==row["last_value"],"invalid existing row")
    obs={}
    for d,v in zip(ds,vs):
        need(isinstance(v,(float,int)) and not isinstance(v,bool) and math.isfinite(v),"invalid existing value")
        stamp=key(d,mode)
        need(stamp not in obs or obs[stamp]==v,"conflicting values at normalized date "+stamp)
        obs[stamp]=v
    dates=sorted(obs);values=[obs[d] for d in dates]
    need({(key(d,mode),v) for d,v in zip(ds,vs)}==set(zip(dates,values)),"semantic history changed")
    changed=(ds!=dates or vs!=values)
    before=row["last_date"]
    if changed:row.update(dates=dates,values=values,last_date=dates[-1],last_value=values[-1])
    return {"status":"READY" if changed else "NO_CHANGE","before":before,"after":dates[-1],"before_count":len(ds),"after_count":len(dates),"identical_duplicates_removed":len(ds)-len(dates),"semantic_values_preserved":True}
def prepare(current):
    out=copy.deepcopy(current);receipts=[]
    for (ccy,ident),mode in CONFIG.items():
        try:
            hits=[r for r in out[ccy] if r["id"]==ident];need(len(hits)==1,"nonunique row")
            row=copy.deepcopy(hits[0]);rec=reconcile(row,mode);hits[0].update(row)
        except (ValueError,KeyError,TypeError,IndexError) as e:rec={"status":"WITHHELD","reason":str(e)}
        receipts.append({"ccy":ccy,"id":ident,**rec})
    return out,{"schema":"GMFQ_MACRO_CHRONOLOGY_V1","series":receipts,"status":"READY" if any(r["status"]=="READY" for r in receipts) else "NO_CHANGE_OR_WITHHELD","first_release_PIT_certified":False,"affects_fx_core":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",type=Path,required=True);p.add_argument("--receipt",type=Path,required=True);a=p.parse_args()
    need(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary outputs only")
    out,rec=prepare(json.loads(SOURCE.read_text()));a.candidate.parent.mkdir(parents=True,exist_ok=True);a.receipt.parent.mkdir(parents=True,exist_ok=True)
    a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n");a.receipt.write_text(json.dumps(rec,sort_keys=True)+"\n");print(json.dumps(rec,sort_keys=True))
if __name__=="__main__":main()
