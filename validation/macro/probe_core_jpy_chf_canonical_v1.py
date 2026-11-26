"""Read-only full-window identity checks for already operational core CPI sources."""
import json,statistics
from datetime import datetime,timezone
from validation.macro.prepare_chf_snb_revised_v1 import SOURCE,need
from validation.macro.collect_g8_semaphore_gaps_v1 import JP_CORE_URL,CH_CORE_URL,parse_jp_core,parse_ch_core,fetch_issuer
def main():
    d=json.loads(SOURCE.read_text());now=datetime.now(timezone.utc).date()
    for ccy,ident,url,parser in [
        ("JPY","JP_CPI_CORE_YOY_history_value",JP_CORE_URL,parse_jp_core),
        ("CHF","CH_CPI_CORE1_YOY_history_value",CH_CORE_URL,parse_ch_core)]:
        row=next(r for r in d[ccy] if r["id"]==ident)
        need(row["unit"]=="Percent YoY" and row["frequency"]=="M","legacy definition mismatch")
        old=dict(zip(row["dates"],row["values"]));need(len(old)==len(row["dates"])>=36,"duplicate history")
        obs=dict(parser(fetch_issuer(url),now));overlap=sorted(set(old)&set(obs))
        need(len(overlap)>=24,"insufficient overlap")
        err=[abs(obs[p]-old[p]) for p in overlap]
        print("CORE_IDENTITY",ccy,json.dumps({"source":url,"legacy_count":len(old),"source_count":len(obs),"overlap":len(overlap),"missing":sorted(set(old)-set(obs)),"exact_1dp":sum(round(obs[p],1)==round(old[p],1) for p in overlap),"median_abs":statistics.median(err),"max_abs":max(err),"latest_date":max(obs),"latest":obs[max(obs)],"new":{p:obs[p] for p in sorted(obs) if p>max(old)}}))
if __name__=="__main__":main()
