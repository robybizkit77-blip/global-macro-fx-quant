"""Read-only official BoE quoted mortgage rate identity proof."""
import json,statistics
from datetime import datetime,timezone
from validation.macro.prepare_gbp_boe_revised_v1 import SOURCE,day,query,fetch,observations,need
def main():
    key="UK_MORTGAGE_RATE_2Y_75LTV_history_value"
    rows=[r for r in json.loads(SOURCE.read_text())["GBP"] if r["id"]==key]
    need(len(rows)==1,"unique legacy row")
    row=rows[0];need(row["frequency"]=="M" and row["unit"]=="Percent","wrong local identity")
    old={day(d):float(v) for d,v in zip(row["dates"],row["values"])}
    need(len(old)==len(row["dates"])>=36,"duplicate or short history")
    code="IUMBV34";url=query(code,min(old));obs=observations(fetch(url),code,"M",0,20,datetime.now(timezone.utc))
    need(set(old)<=set(obs),"full history missing")
    errors=[abs(obs[d]-old[d]) for d in old]
    changes=[{"date":d.isoformat(),"old":old[d],"official":obs[d]} for d in sorted(old) if abs(obs[d]-old[d])>1e-6]
    print("GBP_MORTGAGE_IDENTITY",json.dumps({"series":code,"url":url,"overlap":len(old),"exact":sum(e<=1e-6 for e in errors),"median_abs":statistics.median(errors),"max_abs":max(errors),"differences":changes,"new":{d.isoformat():obs[d] for d in sorted(obs) if d>max(old)}}))
if __name__=="__main__":main()
