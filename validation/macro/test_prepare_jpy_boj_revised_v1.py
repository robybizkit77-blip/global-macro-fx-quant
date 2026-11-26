import json,unittest
from datetime import datetime,timezone
from unittest.mock import patch
from validation.macro.prepare_jpy_boj_revised_v1 import CONFIG,prepare,prepare_row
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
IDS=list(CONFIG)
def source(url):
    ident=IDS[1] if "MD02" in url else IDS[0]
    db,code,title=CONFIG[ident]
    ds=[f"{2024+i//12}{1+i%12:02d}" for i in range(34)]
    return json.dumps({"STATUS":200,"RESULTSET":[{"SERIES_CODE":code,"UNIT":"100 million yen","FREQUENCY":"MONTHLY","NAME_OF_TIME_SERIES":title or "Bank credit","VALUES":{"SURVEY_DATES":ds,"VALUES":list(range(100,134))}}]}).encode()
def row(ident):
    ds=[f"{2024+i//12}-{1+i%12:02d}" for i in range(30)]
    return {"id":ident,"unit":"100 million yen","frequency":"M","source_file":ident.removesuffix("_value")+".csv","dates":ds,"values":list(range(100,130)),"last_date":ds[-1],"last_value":129}
class BoJTests(unittest.TestCase):
    def test_full_history_and_idempotence(self):
        x=row(IDS[1]);r=prepare_row(x,IDS[1],NOW,source)
        self.assertEqual(r["after"],"2026-10");self.assertEqual(prepare_row(x,IDS[1],NOW,source)["status"],"NO_CHANGE")
    def test_wrong_legacy_identity(self):
        x=row(IDS[0]);x["values"]=[v*2 for v in x["values"]];x["last_value"]*=2
        with self.assertRaisesRegex(ValueError,"identity"):prepare_row(x,IDS[0],NOW,source)
    def test_independent_failure(self):
        old={"JPY":[row(i) for i in IDS],"EUR":[]}
        def fetch(url):
            if "MD11" in url:raise OSError("unavailable")
            return source(url)
        new,r=prepare(old,now=NOW,fetcher=fetch)
        self.assertEqual([x["status"] for x in r["series"]],["WITHHELD","READY"])
        self.assertEqual(new["JPY"][0],old["JPY"][0]);self.assertEqual(new["EUR"],old["EUR"])
    def test_empty_current_month_placeholder(self):
        def placeholder(url,actual=None):
            d=json.loads(source(url));v=d["RESULTSET"][0]["VALUES"]
            v["SURVEY_DATES"].append("202611");v["VALUES"].append(actual)
            return json.dumps(d).encode()
        x=row(IDS[1]);self.assertEqual(prepare_row(x,IDS[1],NOW,placeholder)["after"],"2026-10")
        with self.assertRaises(ValueError):prepare_row(x,IDS[1],NOW,lambda u:placeholder(u,135))
if __name__=="__main__":unittest.main()
