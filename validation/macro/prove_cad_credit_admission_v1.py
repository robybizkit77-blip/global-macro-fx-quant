"""Controlled CAD credit admission: exact official vintage, native and registry.
Default is temporary candidate only. --apply is restricted to an isolated PR
checkout; no persistence, publication, ranking change or PIT certification.
"""
import argparse,copy,json,os,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
from validation.macro import prepare_cad_boc_lending_v1 as cad
ROOT=Path(__file__).resolve().parents[2]
POLICY=ROOT/"validation/liquidity/LIQUIDITY_SOURCE_POLICY_V1_2026-10-12.json"
GATE=ROOT/"site/fx-quant-v2/next/liquidity-source-policy-gate-v1.js"
IDENT="CA_BUSINESS_LOANS_OUTSTANDING_history_value"
KEY="V122667770"
def need(ok,msg):
    if not ok:raise ValueError(msg)
def read(name):
    return json.loads((ROOT/"live_data/sections"/(name+".json")).read_text())
def run(*args):
    subprocess.run([sys.executable,*args],cwd=ROOT,check=True)
def candidate(macro,native,policy,now,fetcher=cad.fetch):
    m=[r for r in macro["CAD"] if r["id"]==IDENT]
    need(len(m)==1,"unique Canadian loan series required")
    src=m[0];row=copy.deepcopy(src);proof=src["current_vintage_provenance"]
    need(proof["source_series_id"]==KEY and proof["source_series_first_release_PIT_certified"] is False,"source not certified")
    result=cad.prepare_row(row,IDENT,now,fetcher)
    need(result["status"] in ("READY","NO_CHANGE"),"source unavailable")
    need(all(src[k]==row[k] for k in ("dates","values","last_date","last_value")),"macro vintage differs from issuer; existing producer must refresh first")
    out=copy.deepcopy(native);old=out["CAD"]["credit"]
    new={k:row[k] for k in ("label","dates","values","last_date","last_value")}
    if old is not None:
        prior=dict(zip(old["dates"],old["values"]));fresh=dict(zip(new["dates"],new["values"]))
        need(set(prior)<=set(fresh) and all(abs(fresh[d]-v)<=max(abs(v),1)*.01 for d,v in prior.items()),"Canadian native history regression or large revision")
    out["CAD"]["credit"]=new
    pol=copy.deepcopy(policy)
    need("CAD.credit" not in pol["mapped"],"controlled first admission only")
    pol["mapped"]["CAD.credit"]={"label":src["label"],"publisher":"Bank of Canada",
      "status":"AUTOMATION_CONTRACT_VERIFIED_NATIVE_PARITY","source_contract":"Credit extended to corporate sector — outstanding business loans, total",
      "frequency":"MONTHLY","automation_ready":True,"series_mapping_status":"EXACT_SERIES_KEY_FULL_HISTORY_PARITY",
      "series_key":KEY,"source_url":proof["source_url"],"macro_series_id":IDENT,
      "verification":{"as_of":now.date().isoformat(),"run_id":45993982322,"job_id":140488626565,"receipt_status":"READY",
      "native_last_date":new["last_date"],"native_last_value":new["last_value"],"source_first_release_PIT_certified":False,"continuity_certified":False,
      "evidence_scope":"SOURCE_AND_ISOLATED_CANDIDATE_PROOF_NOT_PRODUCTION_PUBLICATION"}}
    pol["coverage"].update(total_subseries=len(pol["mapped"]),source_mapped_subseries=len(pol["mapped"]),
      automation_ready_subseries=sum(x.get("automation_ready") is True for x in pol["mapped"].values()),
      mapping_pending_subseries=sum(x.get("automation_ready") is not True for x in pol["mapped"].values()))
    return out,pol,{"series_id":KEY,"period":new["last_date"],"value":new["last_value"],"count":len(new["dates"]),
      "source_rechecked":True,"macro_native_exact":True,"registry_candidate_only":True,"production_published":False,"continuity_certified":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--output",type=Path,required=True);p.add_argument("--apply",action="store_true");a=p.parse_args()
    need(a.output.resolve().is_relative_to(Path("/tmp")),"temporary output required")
    macro=read("MACRO_SERIES");native=read("NATIVE_LIQ_DATA");policy=json.loads(POLICY.read_text())
    out,pol,receipt=candidate(macro,native,policy,datetime.now(timezone.utc))
    a.output.mkdir(parents=True,exist_ok=True)
    dest=a.output/"native.json";dest.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    (a.output/"policy.json").write_text(json.dumps(pol,ensure_ascii=False,indent=2)+"\n")
    if a.apply:
        need(os.environ.get("GITHUB_EVENT_NAME")=="pull_request","isolated PR apply only")
        run("validation/update_live_direct_section.py","--section","NATIVE_LIQ_DATA","--replacement",str(dest),"--apply")
        run("validation/build_live_manifest_v2.py","--write","live_data/manifest.v2.json")
        POLICY.write_text(json.dumps(pol,ensure_ascii=False,indent=2)+"\n")
        gate=GATE.read_text()
        marker='  "credit": null,'
        need(gate.count(marker)==1,"ambiguous CAD source gate")
        GATE.write_text(gate.replace(marker,'  "credit": {\n   "ready": true,\n   "status": "AUTOMATION_CONTRACT_VERIFIED_NATIVE_PARITY"\n  },'))
        run("validation/check_live_update_contract.py")
        run("validation/rebuild_live_data_runtime.py","--verify-only")
        run("validation/check_liquidity_remaining_blockers_v1.py")
        need(read("MACRO_SERIES")==macro and read("NATIVE_LIQ_DATA")==out,"unexpected mutation")
        subprocess.run(["node","validation/publishing/test_next_liquidity_source_policy_v1.cjs"],cwd=ROOT,check=True)
        receipt["isolated_apply_verified"]=True
    (a.output/"receipt.json").write_text(json.dumps(receipt,sort_keys=True)+"\n")
    print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
