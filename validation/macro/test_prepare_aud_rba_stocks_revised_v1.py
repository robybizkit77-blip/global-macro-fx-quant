import unittest
from datetime import datetime,timezone,date,timedelta
from unittest.mock import patch
from validation.macro.prepare_aud_rba_stocks_revised_v1 import CONFIG,prepare,prepare_row,parse
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
IDENT="AU_RBA_TOTAL_ASSETS_history_value"
OTHER="AU_EXCHANGE_SETTLEMENT_BALANCES_history_value"
def row(ident):
    return {"id":ident,"source_file":ident.removesuffix("_value")+".csv","frequency":"W","unit":"AUD millions",
       "dates":["2025-01-01","2025-01-08"],"values":[100,101],"last_date":"2025-01-08","last_value":101}
def fixture():
    lines=["Title,Total assets,Exchange settlement balances","Units,$ million,$ million","Frequency,Weekly,Weekly","Series ID,ARBAATAW,ARBALESBW"]
    for n in range(26):
        d=date(2025,1,1)+timedelta(days=7*n)
        lines.append(f"{d.isoformat()},{100+n},{100+n}")
    return ("\n".join(lines)+"\n").encode()
class RbaTests(unittest.TestCase):
    def test_full_history_and_idempotence(self):
        x=row(IDENT)
        r=prepare_row(x,IDENT,NOW,fixture())
        self.assertEqual(r["status"],"READY")
        self.assertEqual(len(x["dates"]),26)
        self.assertTrue(x["current_vintage_provenance"]["stock_level_not_break_adjusted_growth"])
        self.assertEqual(prepare_row(x,IDENT,NOW,fixture())["status"],"NO_CHANGE")
    def test_wrong_unit_and_title(self):
        with self.assertRaises(ValueError):parse(fixture().replace(b"$ million",b"Percent"),IDENT,NOW)
        with self.assertRaises(ValueError):parse(fixture().replace(b"Total assets",b"Other assets"),IDENT,NOW)
    def test_table_download_once(self):
        calls=[]
        def fetch(url):
            calls.append(url);return fixture()
        original={"AUD":[row(IDENT),row(OTHER)],"EUR":[]}
        with patch.dict(CONFIG,{IDENT:CONFIG[IDENT],OTHER:CONFIG[OTHER]},clear=True):
            out,r=prepare(original,now=NOW,fetcher=fetch)
        self.assertEqual(len(calls),1)
        self.assertEqual([x["status"] for x in r["series"]],["READY","READY"])
        self.assertEqual(out["EUR"],original["EUR"])
    def test_scale_mismatch_rejected(self):
        x=row(IDENT);x.update(values=[100000,101000],last_value=101000)
        with self.assertRaises(ValueError):prepare_row(x,IDENT,NOW,fixture())
    def test_exact_new_rate_and_business_stock_sources(self):
        import calendar
        for ident in ("AU_CREDIT_BUSINESS_CURRENT_SA_history_value","AU_MORTGAGE_RATE_OWNER_OCC_OUTSTANDING_history_value","AU_BUSINESS_LENDING_RATE_MEDIUM_OUTSTANDING_history_value"):
            table,code,title,freq,unit,target=CONFIG[ident]
            dates=[date(2024+n//12,n%12+1,calendar.monthrange(2024+n//12,n%12+1)[1]) for n in range(33)]
            vals=[1500+n if table=="d2" else 5+n/100 for n in range(33)]
            def feed(mult=1,bad_code=False,bad_unit=False):
                u="$ billion" if table=="d2" else "Per cent per annum"
                lines=["Title,"+title,"Units,"+("wrong" if bad_unit else u),"Frequency,Monthly","Series ID,"+("WRONG" if bad_code else code)]
                return ("\n".join(lines+[f"{d.isoformat()},{v*mult}" for d,v in zip(dates,vals)])+"\n").encode()
            def old():
                ds=[d.strftime("%d/%m/%Y") for d in dates[:31]]
                return {"id":ident,"source_file":ident.removesuffix("_value")+".csv","frequency":"M","unit":unit,"dates":ds,"values":vals[:31],"last_date":ds[-1],"last_value":vals[30]}
            x=old()
            self.assertEqual(prepare_row(x,ident,NOW,feed())["status"],"READY")
            self.assertEqual(x["last_date"],"30/09/2026")
            self.assertEqual(prepare_row(x,ident,NOW,feed())["status"],"NO_CHANGE")
            for bad in (feed(mult=1.2),feed(bad_code=True),feed(bad_unit=True)):
                with self.assertRaises(ValueError):prepare_row(old(),ident,NOW,bad)
if __name__=="__main__":unittest.main()
