"""Read-only candidate for the last two survey contracts and Canadian loan stock.
Reuse existing official collectors; never publish or certify first-release PIT here.
"""
import argparse, copy, json, math
from datetime import datetime, timezone
from pathlib import Path
from validation.liquidity import probe_ecb_eur_bls_actual_v1 as ecb
from validation.liquidity import refresh_ecb_eur_nfc_credit_v1 as eur
from validation.liquidity import refresh_boe_gbp_secured_credit_v1 as gbp
from validation.macro import prepare_cad_boc_lending_v1 as cad

ROOT=Path(__file__).resolve().parents[2]
IDS={"EUR":"EA_BLS_CREDIT_STANDARDS_ENTERPRISES_history_value",
     "GBP":"UK_CCS_CORPORATE_CREDIT_AVAILABILITY_history_value",
     "CAD":"CA_BUSINESS_LOANS_OUTSTANDING_history_value"}
def need(ok,why):
    if not ok: raise ValueError(why)

def qhistory(row):
    ds=row["dates"]; vs=row["values"]
    qs=[ecb.quarter_index(d) for d in ds]
    need(len(ds)==len(vs)>=4 and ds[-1]==row["last_date"] and vs[-1]==row["last_value"],"invalid survey history")
    need(all(b-a==1 for a,b in zip(qs,qs[1:])) and all(type(v) in (int,float) and math.isfinite(v) and abs(v)<=100 for v in vs),"invalid survey observations")
    return dict(zip(qs,vs))

def replace_history(row,obs):
    ds=sorted(obs); dates=[ecb.quarter_label(q) for q in ds]; values=[obs[q] for q in ds]
    row.update(dates=dates,values=values,last_date=dates[-1],last_value=values[-1])
    qhistory(row)

def ecb_candidate(row,records,today):
    old=qhistory(row)
    current=today.year*4+(today.month-1)//3
    need(max(records)<=current,"future ECB release")
    shifted={q-1:v for q,v in records.items()}
    prior=row.get("current_vintage_provenance",{})
    reference=prior.get("period_semantics")=="OBSERVED_QUARTER_PRECEDES_PUBLICATION"
    compare=shifted if reference else records
    overlap=set(old)&set(compare)
    need(len(overlap)>=24 and set(old)<=set(compare),"ECB full-window parity absent")
    need(all(abs(old[q]-compare[q])<=.1 for q in overlap),"ECB vintage or quarter convention mismatch")
    need(max(shifted)>=max(old)-int(not reference),"ECB survey regression")
    out=copy.deepcopy(row)
    replace_history(out,shifted)
    out["current_vintage_provenance"]={"status":"ECB_CURRENT_REVISED_HISTORY_NOT_PIT","source_series_id":ecb.KEY,
       "source_url":ecb.API,"period_semantics":"OBSERVED_QUARTER_PRECEDES_PUBLICATION",
       "publication_quarters":[ecb.quarter_label(q+1) for q in sorted(shifted)],
       "positive_means":"tightening","source_series_first_release_PIT_certified":False}
    return out

def gbp_candidate(row,report,today):
    old=qhistory(row)
    need(report["series_id"]=="BOE_CCS_CORPORATE_AVAILABILITY_ACTUAL" and report["positive_means"]=="increased_availability","incorrect BoE survey identity")
    ds=report["dates"]; vs=report["values"]
    fresh=qhistory(dict(dates=ds,values=vs,last_date=report["latest_observation"],last_value=vs[-1]))
    current=today.year*4+(today.month-1)//3
    overlap=set(old)&set(fresh)
    need(max(fresh)<current and max(fresh)>=max(old) and len(overlap)>=4,"BoE survey stale, future or insufficient overlap")
    need(all(abs(old[q]-fresh[q])<=.11 for q in overlap),"BoE actual survey overlap mismatch")
    out=copy.deepcopy(row)
    replace_history(out,{**old,**fresh})
    out["current_vintage_provenance"]={"status":"BOE_ACTUAL_SURVEY_WITH_RETAINED_HISTORY_NOT_PIT",
       "source_series_id":report["series_id"],"source_url":report["source_url"],
       "period_semantics":"OBSERVED_QUARTER","positive_means":"increased_availability",
       "verified_overlap":len(overlap),"retained_prefix_not_reverified":True,
       "source_series_first_release_PIT_certified":False}
    return out

def prepare(macro,native,now,ecb_fetch=eur.fetch,ccs_fetch=gbp.ccs_fetch,cad_fetch=cad.fetch):
    m=copy.deepcopy(macro); n=copy.deepcopy(native); receipts=[]
    for c,ident in IDS.items():
        role="credit" if c=="CAD" else "conditions"
        try:
            hits=[r for r in m[c] if r["id"]==ident];need(len(hits)==1,"unique macro row required")
            src=hits[0]; dst=n[c][role]
            if c=="EUR":
                records=ecb.parse(ecb_fetch(ecb.API),now.date())
                out=ecb_candidate(src,records,now.date())
                if dst is not None:
                    # Native legacy history has publication quarter labels.
                    base=dict(dst)
                    if qhistory(dst)==qhistory(src) and src.get("current_vintage_provenance",{}).get("period_semantics")=="OBSERVED_QUARTER_PRECEDES_PUBLICATION":
                        base["current_vintage_provenance"]=src["current_vintage_provenance"]
                    check=ecb_candidate(base,records,now.date())
                    need(qhistory(check)==qhistory(out),"ECB native and macro candidate mismatch")
            elif c=="GBP":
                url=gbp.ccs_latest_url(ccs_fetch(gbp.CCS_INDEX),now.date())
                report=gbp.parse_ccs(ccs_fetch(url),url,today=now.date())
                out=gbp_candidate(src,report,now.date())
                if dst is not None:
                    check=gbp_candidate(dst,report,now.date())
                    need(qhistory(check)==qhistory(out),"BoE native and macro candidate mismatch")
            else:
                need(src["unit"]=="CAD millions" and src["frequency"]=="M","Canadian loan unit mismatch")
                out=copy.deepcopy(src)
                cad.prepare_row(out,ident,now,cad_fetch)
                need(out["current_vintage_provenance"]["source_series_id"]=="V122667770","Canadian source identity mismatch")
                if dst is not None:
                    old=dict(zip(dst["dates"],dst["values"])); fresh=dict(zip(out["dates"],out["values"]))
                    need(set(old)<=set(fresh) and all(abs(fresh[d]-v)<=max(abs(v),1)*.01 for d,v in old.items()),"Canadian native overlap mismatch")
            new_native={k:out[k] for k in ("label","dates","values","last_date","last_value")}
            changed=src!=out or dst!=new_native
            src.update(out);n[c][role]=new_native
            receipts.append(dict(ccy=c,role=role,id=ident,status="READY" if changed else "NO_CHANGE",
              after=out["last_date"],latest=out["last_value"],source_series_id=out["current_vintage_provenance"]["source_series_id"],
              count=len(out["dates"])))
        except (OSError,RuntimeError,ValueError,KeyError,TypeError,IndexError) as exc:
            receipts.append(dict(ccy=c,role=role,id=ident,status="WITHHELD",reason=str(exc)))
    return m,n,{"series":receipts,"first_release_PIT_certified":False,"continuity_certified":False,"published":False}

def main():
    p=argparse.ArgumentParser();p.add_argument("--output",type=Path,required=True);a=p.parse_args()
    need(a.output.resolve().is_relative_to(Path("/tmp")),"temporary output only")
    m,n,r=prepare(json.loads((ROOT/"live_data/sections/MACRO_SERIES.json").read_text()),
                  json.loads((ROOT/"live_data/sections/NATIVE_LIQ_DATA.json").read_text()),datetime.now(timezone.utc))
    a.output.mkdir(parents=True,exist_ok=True)
    for name,obj in (("macro.json",m),("native.json",n),("receipt.json",r)):
        (a.output/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(r,sort_keys=True))
    need(all(x["status"] in ("READY","NO_CHANGE") for x in r["series"]),"one or more source contracts withheld")
if __name__=="__main__":main()
