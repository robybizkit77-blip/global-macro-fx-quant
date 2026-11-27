import unittest,json
from datetime import datetime,timezone
from unittest.mock import patch
from validation.macro.prepare_eur_gbp_revised_v1 import CONFIG,prepare,prepare_row
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
KEY=("GBP","UK_CPI_CORE_YOY_history_value")
OTHER=("GBP","UK_RETAIL_VOL_history_value")
def row(k):
    source,unit,code=CONFIG[k]
    return {"id":k[1],"source_file":source,"unit":unit,"frequency":"M",
            "dates":["2026-01","2026-02"],"values":[2,3],"last_date":"2026-02","last_value":3}
def fetch(url):
    core="dko8" in url
    desc={"cdid":"DKO8" if core else "J5EK","title":"CPI 12mth: Excluding Energy, food, alcoholic beverages & tobacco" if core else "RSI:Volume Seasonally Adjusted:All Retailers inc fuel:All Business Index"}
    return json.dumps({"description":desc,"months":[{"year":"2026","month":m,"value":v} for m,v in [("JAN","2"),("FEB","3"),("MAR","4")]]}).encode()
class RevisedTests(unittest.TestCase):
    def test_ons_full_history(self):
        x=row(KEY)
        self.assertEqual(prepare_row(*KEY,x,NOW,fetch)["status"],"READY")
        self.assertEqual(x["last_date"],"2026-03")
        self.assertEqual(prepare_row(*KEY,x,NOW,fetch)["status"],"NO_CHANGE")
    def test_identity_and_failure_isolation(self):
        original={"GBP":[row(KEY),row(OTHER)],"EUR":[]}
        def broken(url):
            if "dko8" in url:raise OSError("unavailable")
            return fetch(url)
        with patch.dict(CONFIG,{KEY:CONFIG[KEY],OTHER:CONFIG[OTHER]},clear=True):
            new,receipt=prepare(original,now=NOW,fetcher=broken)
        self.assertEqual(new["GBP"][0],original["GBP"][0])
        self.assertEqual(new["EUR"],original["EUR"])
        self.assertEqual([r["status"] for r in receipt["series"]],["WITHHELD","READY"])
    def test_wrong_source(self):
        x=row(KEY)
        with self.assertRaises(ValueError):prepare_row(*KEY,x,NOW,lambda url:fetch("retail"))
    def test_uk_production_full_revised_window_and_identity(self):
        k=("GBP","UK_PRODUCTION_history_value")
        x=row(k)
        months=[(f"{2022+n//12}-{n%12+1:02d}",100+n/20) for n in range(48)]
        x.update(dates=[d for d,v in months[:-2]],values=[v*0.98 for d,v in months[:-2]],last_date=months[-3][0],last_value=months[-3][1]*0.98)
        import calendar
        def source(url):
            return json.dumps({"description":{"cdid":"K222","title":"IOP: B-E: PRODUCTION: CVMSA","unit":"Index, base year = 100"},
                "months":[{"year":d[:4],"month":calendar.month_abbr[int(d[5:])],"value":str(v)} for d,v in months]}).encode()
        self.assertEqual(prepare_row(*k,x,NOW,source)["status"],"READY")
        self.assertEqual(x["last_date"],months[-1][0])
        self.assertEqual(prepare_row(*k,x,NOW,source)["status"],"NO_CHANGE")
    def test_uk_employment_period_identity(self):
        k=("GBP","UK_EMPLOYMENT_RATE_history_value")
        x=row(k)
        import calendar
        months=[(f"{2022+n//12}-{n%12+1:02d}",74+(n%3)*0.4) for n in range(48)]
        x.update(dates=[d for d,v in months[1:-1]],values=[v for d,v in months[1:-1]],last_date=months[-2][0],last_value=months[-2][1])
        def source(url):
            return json.dumps({"description":{"cdid":"LF24","title":"Employment rate (aged 16 to 64, seasonally adjusted): %","unit":"%"},
                "months":[{"year":d[:4],"month":calendar.month_abbr[int(d[5:])],"value":str(v)} for d,v in months]}).encode()
        self.assertEqual(prepare_row(*k,x,NOW,source)["status"],"READY")
        self.assertEqual(x["current_vintage_provenance"]["definition"]["legacy_period_shift_months"],0)
        self.assertEqual(prepare_row(*k,x,NOW,source)["status"],"NO_CHANGE")
    def test_ea_labour_revisions(self):
        k=("EUR","EA_UNEMP_history_value")
        x=row(k)
        x.update(dates=["2026-08","2026-09-01"],values=[6.4,6.5],last_date="2026-09-01",last_value=6.5)
        filters={"freq":"M","s_adj":"SA","age":"TOTAL","unit":"PC_ACT","sex":"T","geo":"EA21"}
        payload={"id":[*filters,"time"],"size":[*[1 for _ in filters],2],
            "dimension":{**{k:{"category":{"index":{v:0}}} for k,v in filters.items()},
              "time":{"category":{"index":{"2026-08":0,"2026-09":1}}}},"value":{"0":6.5,"1":6.5}}
        source=lambda url:json.dumps(payload).encode()
        self.assertEqual(prepare_row(*k,x,NOW,source)["status"],"READY")
        self.assertEqual(x["dates"],["2026-08","2026-09"])
        self.assertEqual(x["values"],[6.5,6.5])
        self.assertEqual(prepare_row(*k,x,NOW,source)["status"],"NO_CHANGE")
        payload["dimension"]["geo"]["category"]["index"]={"EA20":0}
        with self.assertRaises(ValueError):prepare_row(*k,x,NOW,source)
    def test_ea_employment_quarterly(self):
        k=("EUR","EA_EMPLOYMENT_history_value")
        x=row(k)
        dates=[f"{2023+n//4}-Q{n%4+1}" for n in range(15)]
        values=[170000+n*100 for n in range(15)]
        x.update(frequency="Q",dates=dates[:-1],values=values[:-1],last_date=dates[-2],last_value=values[-2])
        filters={"freq":"Q","unit":"THS_PER","na_item":"EMP_DC","s_adj":"SCA","geo":"EA21"}
        payload={"id":[*filters,"time"],"size":[*[1 for _ in filters],len(dates)],
            "dimension":{**{k:{"category":{"index":{v:0}}} for k,v in filters.items()},
              "time":{"category":{"index":{d:i for i,d in enumerate(dates)}}}},"value":values}
        source=lambda url:json.dumps(payload).encode()
        self.assertEqual(prepare_row(*k,x,NOW,source)["status"],"READY")
        self.assertEqual(x["last_date"],"2026-Q3")
        self.assertEqual(prepare_row(*k,x,NOW,source)["status"],"NO_CHANGE")
        payload["value"]=[v*1.1 for v in values]
        with self.assertRaises(ValueError):prepare_row(*k,x,NOW,source)
if __name__=="__main__":unittest.main()
