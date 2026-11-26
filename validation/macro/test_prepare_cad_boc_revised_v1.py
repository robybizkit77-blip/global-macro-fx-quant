import json,unittest
from datetime import datetime,timezone
from unittest.mock import patch
from validation.macro.prepare_cad_boc_revised_v1 import CONFIG,prepare,prepare_row
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
IDS=list(CONFIG)
def row(ident):
    ds=[f"{2024+n//12}-{n%12+1:02d}-01" for n in range(30)]
    return {"id":ident,"source_file":ident.removesuffix("_value")+".csv","frequency":"M","unit":"CAD millions","dates":ds,"values":[100+n for n in range(30)],"last_date":ds[-1],"last_value":129}
def source(url,wrong=False,offset=0):
    code,title=next(v for v in CONFIG.values() if v[0] in url)
    obs=[{"d":f"{2024+n//12}-{n%12+1:02d}-01",code:{"v":str(100+n+offset)}} for n in range(34)]
    return json.dumps({"seriesDetail":{code:{"label":"wrong" if wrong else title+" (Seasonally adjusted)","description":""}},"observations":obs}).encode()
class BoCTests(unittest.TestCase):
    def test_full_window_idempotence(self):
        for ident in IDS:
            x=row(ident)
            self.assertEqual(prepare_row(x,ident,NOW,source)["status"],"READY")
            self.assertEqual(x["last_date"],"2026-10-01")
            self.assertEqual(prepare_row(x,ident,NOW,source)["status"],"NO_CHANGE")
    def test_wrong_source_and_overlap(self):
        for ident in IDS:
            with self.assertRaises(ValueError):prepare_row(row(ident),ident,NOW,lambda u:source(u,wrong=True))
            with self.assertRaises(ValueError):prepare_row(row(ident),ident,NOW,lambda u:source(u,offset=200))
    def test_independent_failure(self):
        original={"CAD":[row(i) for i in IDS],"USD":[]}
        def fail(url):
            if CONFIG[IDS[0]][0] in url:raise OSError("unavailable")
            return source(url)
        out,r=prepare(original,now=NOW,fetcher=fail)
        self.assertEqual([x["status"] for x in r["series"]],["WITHHELD","READY","READY"])
        self.assertEqual(out["CAD"][0],original["CAD"][0])
        self.assertEqual(out["USD"],original["USD"])
if __name__=="__main__":unittest.main()
