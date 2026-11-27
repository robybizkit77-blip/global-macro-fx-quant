"""Apply only verified EUR/GBP survey candidates via existing section/manifest tools.
CAD is proven but deliberately deferred until native admission guards are migrated.
"""
import argparse,copy,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
from validation.macro.prepare_final_liquidity_contracts_v1 import prepare,IDS
ROOT=Path(__file__).resolve().parents[2]
MANAGED=("live_data/sections/MACRO_SERIES.json","live_data/sections/NATIVE_LIQ_DATA.json",
         "live_data/manifest.v2.json","payload/part-00.txt","payload/part-01.txt")
def need(ok,why):
    if not ok:raise ValueError(why)
def run(*args):
    subprocess.run([sys.executable,*args],cwd=ROOT,check=True)
def read(name):
    return json.loads((ROOT/"live_data/sections"/(name+".json")).read_text())
def main():
    p=argparse.ArgumentParser();p.add_argument("--output",type=Path,required=True);p.add_argument("--apply",action="store_true");p.add_argument("--strict",action="store_true");a=p.parse_args()
    need(a.output.resolve().is_relative_to(Path("/tmp")),"temporary output required")
    before_m=read("MACRO_SERIES");before_n=read("NATIVE_LIQ_DATA")
    m,n,r=prepare(before_m,before_n,datetime.now(timezone.utc))
    # Never admit the Canadian native channel before its own source-policy migration.
    m["CAD"]=copy.deepcopy(before_m["CAD"]);n["CAD"]=copy.deepcopy(before_n["CAD"])
    receipts={x["ccy"]:x for x in r["series"]}
    need(set(receipts)=={"EUR","GBP","CAD"},"unexpected source receipt scope")
    for c in before_m:
        need(len(before_m[c])==len(m[c]),"macro row count changed")
        for old,new in zip(before_m[c],m[c]):
            need(old["id"]==new["id"],"macro order changed")
            if old!=new:need(c in ("EUR","GBP") and old["id"]==IDS[c] and receipts[c]["status"]=="READY","unexpected macro change")
        need(set(before_n[c])==set(n[c]),"native role count changed")
        for k in before_n[c]:
            if before_n[c][k]!=n[c][k]:need(c in ("EUR","GBP") and k=="conditions" and receipts[c]["status"]=="READY","unexpected native change")
    for c in ("EUR","GBP"):
        if receipts[c]["status"] in ("READY","NO_CHANGE"):
            row=next(x for x in m[c] if x["id"]==IDS[c])
            need(all(row[k]==n[c]["conditions"][k] for k in ("dates","values","last_date","last_value")),"native/macro mismatch")
    if a.strict:need(all(receipts[c]["status"] in ("READY","NO_CHANGE") for c in ("EUR","GBP")),"survey source withheld")
    a.output.mkdir(parents=True,exist_ok=True)
    r["cad_native_deferred"]=True
    r["production_persistence_performed"]=False
    for name,old,new in (("MACRO_SERIES",before_m,m),("NATIVE_LIQ_DATA",before_n,n)):
        path=a.output/(name+".json")
        path.write_text(json.dumps(new,ensure_ascii=False,indent=2)+"\n")
        if a.apply and old!=new:
            run("validation/update_live_direct_section.py","--section",name,"--replacement",str(path),"--apply")
            run("validation/build_live_manifest_v2.py","--write","live_data/manifest.v2.json")
    if a.apply:
        run("validation/check_live_update_contract.py")
        run("validation/rebuild_live_data_runtime.py","--verify-only")
        run("validation/check_liquidity_remaining_blockers_v1.py")
        need(read("MACRO_SERIES")==m and read("NATIVE_LIQ_DATA")==n,"applied section parity failure")
        dirty=set(subprocess.check_output(["git","diff","--name-only"],cwd=ROOT,text=True).splitlines())
        need(dirty<=set(MANAGED),"unexpected tracked changes: "+str(dirty))
    (a.output/"receipt.json").write_text(json.dumps(r,sort_keys=True)+"\n")
    print(json.dumps(r,sort_keys=True))
if __name__=="__main__":main()
