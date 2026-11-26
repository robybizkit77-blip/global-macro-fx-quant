import json,unittest
from datetime import datetime,timezone
from validation.macro.prepare_chf_snb_revised_v1 import CONFIG,prepare,prepare_row
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
IDS=list(CONFIG)
def row(ident):
    ds=[f"{2024+n//12}-{n%12+1:02d}" for n in range(30)]
    return {"id":ident,"source_file":ident.removesuffix("_value")+".csv","frequency":"M","unit":"CHF millions","dates":ds,"values":[1000+n for n in range(30)],"last_date":ds[-1],"last_value":1029}
def source(url,wrong=False,offset=0):
    key="GM2" if "GM2" in url else "GM3"
    return json.dumps({"timeseries":[{"metadata":{"key":"EPB@SNB.snbmonagg{B,"+key+"}","frequency":"P1M","unit":"In CHF millions" if not wrong else "percent","scale":""},"values":[{"date":f"{2024+n//12}-{n%12+1:02d}","value":1000+n+offset} for n in range(34)]}]}).encode()
class SNBTests(unittest.TestCase):
    def test_full_window_and_noop(self):
        for i in IDS:
            x=row(i)
            self.assertEqual(prepare_row(x,i,NOW,source)["status"],"READY")
            self.assertEqual(x["last_date"],"2026-10")
            self.assertEqual(prepare_row(x,i,NOW,source)["status"],"NO_CHANGE")
    def test_reject_wrong_units_and_overlap(self):
        for i in IDS:
            with self.assertRaises(ValueError):prepare_row(row(i),i,NOW,lambda u:source(u,wrong=True))
            with self.assertRaises(ValueError):prepare_row(row(i),i,NOW,lambda u:source(u,offset=500))
    def test_failure_is_independent(self):
        original={"CHF":[row(i) for i in IDS],"USD":[]}
        def fail(url):
            if "GM2" in url:raise OSError("unavailable")
            return source(url)
        out,r=prepare(original,now=NOW,fetcher=fail)
        self.assertEqual([x["status"] for x in r["series"]],["WITHHELD","READY"])
        self.assertEqual(out["CHF"][0],original["CHF"][0])
        self.assertEqual(out["USD"],original["USD"])
if __name__=="__main__":unittest.main()
