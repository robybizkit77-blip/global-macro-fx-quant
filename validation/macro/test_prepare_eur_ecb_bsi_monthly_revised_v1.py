import unittest
from datetime import datetime,timezone
from validation.macro.prepare_eur_ecb_bsi_monthly_revised_v1 import CONFIG,prepare_row,prepare
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
IDS=list(CONFIG)
def months(n):return [f"{2022+i//12:04d}-{i%12+1:02d}" for i in range(n)]
def v(i,n):return [7000000,5500000,17000000][IDS.index(i)]+1000*n
def row(i):
    ds=months(48);vs=[v(i,n) for n in range(48)]
    return {"id":i,"source_file":i.removesuffix("_value")+".csv","unit":"","frequency":"","dates":ds,"values":vs,"last_date":ds[-1],"last_value":vs[-1]}
def source(i,url,ambiguous=False,bad=False):
    a,b,*_=CONFIG[i];key=next(k for k in (a,b) if k.split(".",1)[1] in url)
    diff=0 if key==a or ambiguous else .01
    return "KEY,TIME_PERIOD,OBS_VALUE,UNIT_MULT\n"+"\n".join(f"{key},{d},{v(i,n)*(1+diff)},{5 if bad else 6}" for n,d in enumerate(months(58)))
class Tests(unittest.TestCase):
    def test_all_exact_sources_and_idempotence(self):
        for i in IDS:
            x=row(i);r=prepare_row(x,i,NOW,lambda u:source(i,u))
            self.assertEqual(r["status"],"READY");self.assertEqual(x["last_date"],"2026-10")
            self.assertEqual(prepare_row(x,i,NOW,lambda u:source(i,u))["status"],"NO_CHANGE")
    def test_reject_ambiguous_and_wrong_units(self):
        i=IDS[0]
        for kwargs in ({"ambiguous":True},{"bad":True}):
            with self.assertRaises(ValueError):prepare_row(row(i),i,NOW,lambda u:source(i,u,**kwargs))
    def test_independent_failure(self):
        orig={"EUR":[row(i) for i in IDS],"USD":[]}
        def fetch(u):
            i=next(i for i in IDS if any(k.split(".",1)[1] in u for k in CONFIG[i][:2]))
            if i==IDS[0]:raise OSError("unavailable")
            return source(i,u)
        out,r=prepare(orig,now=NOW,fetcher=fetch)
        self.assertEqual([x["status"] for x in r["series"]],["WITHHELD","READY","READY"])
        self.assertEqual(out["EUR"][0],orig["EUR"][0])
if __name__=="__main__":unittest.main()
