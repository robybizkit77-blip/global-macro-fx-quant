"""Reuse the already certified BOJ M3 runtime for descriptive Macro history.
Do not collect a second independent M3 vintage; preserve the native series.
"""
from __future__ import annotations
import argparse,copy,json,math,re
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
MACRO=ROOT/"live_data/sections/MACRO_SERIES.json"
NATIVE=ROOT/"live_data/sections/NATIVE_LIQ_DATA.json"
IDENT="JP_M3_SA_history_value"
SOURCE_URL="https://www.stat-search.boj.or.jp/api/v1/getDataCode"
def need(ok,why):
    if not ok:raise ValueError(why)
def month_number(m):
    need(isinstance(m,str) and re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])",m),"invalid month")
    return int(m[:4])*12+int(m[5:7])
def history(row):
    ds=row["dates"];vs=row["values"]
    need(len(ds)==len(vs) and len(ds)>=24 and ds[-1]==row["last_date"] and vs[-1]==row["last_value"],"invalid terminal fields")
    need(all(month_number(b)-month_number(a)==1 for a,b in zip(ds,ds[1:])),"noncontiguous monthly source")
    need(all(type(v) in (int,float) and math.isfinite(v) and v>0 for v in vs),"invalid M3 level")
    return dict(zip(ds,vs))
def prepare(macro,native,now):
    need(now.utcoffset() is not None,"aware clock required")
    out=copy.deepcopy(macro)
    rows=[x for x in out["JPY"] if x["id"]==IDENT]
    need(len(rows)==1,"unique canonical M3 series required")
    row=rows[0];src=native["JPY"]["money"]
    need(row["unit"]=="100 million yen" and row["frequency"]=="M" and row["source_file"]=="JP_M3_SA_history.csv" and row["label"]==src["label"]=="M3","source identity mismatch")
    old=history(row);new=history(src)
    need(set(old)<=set(new) and max(new)>=max(old) and max(new)<now.date().isoformat()[:7],"source coverage regression or future observation")
    changed_months=[m for m in old if abs(old[m]-new[m])>1e-6]
    # The native feed has its own strict BOJ source certification and
    # bounded revisions. Descriptive copy may lag, but historical disagreement
    # outside the last three months of its previous vintage requires review.
    need(all(month_number(max(old))-month_number(m)<=2 for m in changed_months),"older M3 revision requires separate review")
    ds=[m for m in new if m>=min(old)];vs=[new[m] for m in ds]
    changed=row["dates"]!=ds or row["values"]!=vs or row.get("current_vintage_provenance",{}).get("source_series_id")!="MAM1XAM3M3MO"
    before=row["last_date"]
    if changed:
        row.update(dates=ds,values=vs,last_date=ds[-1],last_value=vs[-1],
          current_vintage_provenance={"status":"CERTIFIED_NATIVE_BOJ_CURRENT_VINTAGE_NOT_PIT",
           "source_series_id":"MAM1XAM3M3MO","source_database":"MD02","source_url":SOURCE_URL,
           "source_runtime":"NATIVE_LIQ_DATA.JPY.money","source_history_sha256":sha256(json.dumps(src,sort_keys=True,separators=(",",":")).encode()).hexdigest(),
           "source_series_first_release_PIT_certified":False,"runner_first_seen_utc":now.isoformat(),
           "historical_levels_may_be_revised_again":True})
    return out,{"schema":"GMFQ_JPY_M3_MACRO_PARITY_V1","status":"READY" if changed else "NO_CHANGE",
                "id":IDENT,"before":before,"after":ds[-1],"latest":vs[-1],"revised_months":changed_months,
                "native_mutated":False,"affects_fx_core":False,"first_release_PIT_certified":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",required=True,type=Path);p.add_argument("--receipt",required=True,type=Path);a=p.parse_args()
    need(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary output only")
    out,receipt=prepare(json.loads(MACRO.read_text()),json.loads(NATIVE.read_text()),datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True)
    a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    a.receipt.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
