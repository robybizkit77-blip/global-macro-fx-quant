import json,unittest
from datetime import datetime,timezone
from validation.macro.prepare_cad_boc_quarterly_v1 import CONFIG,prepare,prepare_row
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
IDS=list(CONFIG)
def stamp(n):return f"{2020+n//4}-{1+3*(n%4):02d}-01"
def row(ident):
    code,label,freq,unit,file=CONFIG[ident]
    ds=[stamp(n) for n in range(26)]
    if not freq:ds=[f"{d[:4]}Q{(int(d[5:7])-1)//3+1}" for d in ds]
    return {"id":ident,"source_file":file,"frequency":freq,"unit":unit,"dates":ds,"values":[n/10-1 for n in range(26)],"last_date":ds[-1],"last_value":1.5}
def source(url,wrong=False,offset=0,missing=None,future=False):
    code,label,*_=next(v for v in CONFIG.values() if "/"+v[0]+"/" in url)
    obs=[{"d":stamp(n),code:{"v":str(n/10-1+offset)}} for n in range(28 if future else 27) if n!=missing]
    return json.dumps({"seriesDetail":{code:{"label":"wrong" if wrong else label,"dateFormat":"quarterly"}},"observations":obs}).encode()
class QuarterlyBoCTests(unittest.TestCase):
    def test_revised_window_idempotent(self):
        for ident in IDS:
            x=row(ident);r=prepare_row(x,ident,NOW,source)
            self.assertEqual(r["status"],"READY")
            self.assertEqual(x["last_date"],"2026-07-01" if x["frequency"] else "2026Q3")
            self.assertEqual(prepare_row(x,ident,NOW,source)["status"],"NO_CHANGE")
    def test_reject_identity_gap_future_and_mismatch(self):
        for ident in IDS:
            for kwargs in ({"wrong":True},{"missing":5},{"future":True},{"offset":10}):
                with self.assertRaises(ValueError):prepare_row(row(ident),ident,NOW,lambda u:source(u,**kwargs))
    def test_independent_failure(self):
        original={"CAD":[row(i) for i in IDS],"USD":[]}
        def fail(url):
            if "/"+CONFIG[IDS[0]][0]+"/" in url:raise OSError("unavailable")
            return source(url)
        out,r=prepare(original,now=NOW,fetcher=fail)
        self.assertEqual([x["status"] for x in r["series"]],["WITHHELD"]+["READY"]*4)
        self.assertEqual(out["CAD"][0],original["CAD"][0]);self.assertEqual(out["USD"],original["USD"])
if __name__=="__main__":unittest.main()
