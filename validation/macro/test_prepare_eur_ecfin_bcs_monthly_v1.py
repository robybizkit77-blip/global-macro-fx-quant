import json,unittest
from datetime import datetime,timezone
from validation.macro.prepare_eur_ecfin_bcs_monthly_v1 import CONFIG,month_end,query,prepare_row,prepare
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
IDS=list(CONFIG)
def months(n):return [f"{2022+i//12:04d}-{i%12+1:02d}" for i in range(n)]
def v(i,n):return (100 if i.endswith(("ESI","EEI")) else -8)+(n%13)*.7
def row(i):
    ds=[month_end(d) for d in months(48)];vs=[v(i,n) for n in range(48)]
    return {"id":i,"source_file":"EA_ECFIN_BCS_LEAD_INDICATORS_history.csv","unit":"","frequency":"","dates":ds,"values":vs,"last_date":ds[-1],"last_value":vs[-1]}
def raw(i,shift=0,future=False,bad=False):
    _,f,_=query(i,"2022-01");ds=months(60 if future else 58)
    categories={k:{"category":{"index":{x:0}}} for k,x in f.items()}
    categories["time"]={"category":{"index":{d:n for n,d in enumerate(ds)}}}
    if bad:categories["geo"]["category"]["index"]={"EU27_2020":0}
    return json.dumps({"id":[*f,"time"],"size":[*[1]*len(f),len(ds)],"dimension":categories,"value":{str(n):v(i,n)+shift for n in range(len(ds))}}).encode()
class Tests(unittest.TestCase):
    def test_exact_and_idempotent_all(self):
        for i in IDS:
            x=row(i);r=prepare_row(x,i,NOW,lambda u:raw(i))
            self.assertEqual(r["status"],"READY");self.assertEqual(x["last_date"],"2026-10-31")
            self.assertEqual(prepare_row(x,i,NOW,lambda u:raw(i))["status"],"NO_CHANGE")
    def test_identity_and_future(self):
        for opts in ({"shift":5},{"future":True},{"bad":True}):
            with self.assertRaises((ValueError,KeyError)):prepare_row(row(IDS[0]),IDS[0],NOW,lambda u:raw(IDS[0],**opts))
    def test_isolated_failure(self):
        data={"EUR":[row(i) for i in IDS],"USD":[]}
        def fetch(url):
            i=next(i for i in IDS if CONFIG[i] in url)
            if i==IDS[0]:raise OSError("unavailable")
            return raw(i)
        out,r=prepare(data,now=NOW,fetcher=fetch)
        self.assertEqual([x["status"] for x in r["series"]],["WITHHELD"]+["READY"]*6)
        self.assertEqual(out["EUR"][0],data["EUR"][0])
if __name__=="__main__":unittest.main()
