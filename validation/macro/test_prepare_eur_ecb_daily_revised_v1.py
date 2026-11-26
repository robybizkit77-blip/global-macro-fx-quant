import csv,io,unittest
from datetime import datetime,timezone,timedelta,date
from validation.macro.prepare_eur_ecb_daily_revised_v1 import CONFIG,prepare,prepare_row
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
IDS=list(CONFIG)
def val(i,n):return [2000000+n,.03+n*.00001,129+n*.01][IDS.index(i)]
def row(i):
    _,unit,suffix,*_=CONFIG[i]
    dates=[(date(2026,9,1)+timedelta(days=n)).isoformat()+suffix for n in range(50)]
    values=[val(i,n) for n in range(50)]
    return {"id":i,"source_file":i.removesuffix("_value")+".csv","unit":unit,"frequency":"D","dates":dates,"values":values,"last_date":dates[-1],"last_value":values[-1]}
def source(i,wrong=False,missing=False,alternative=False):
    key,_,_,mult,*_=CONFIG[i];f=io.StringIO();w=csv.writer(f);w.writerow(["KEY","TIME_PERIOD","OBS_VALUE","UNIT_MULT"])
    for n in range(85):
        if missing and n==4:continue
        w.writerow([key.replace("SS_CIN","SS_CI") if alternative else key,(date(2026,9,1)+timedelta(days=n)).isoformat(),val(i,n)+(.1 if alternative else 0),"99" if wrong else mult])
    return f.getvalue()
class ECBTests(unittest.TestCase):
    def test_full_window_idempotence(self):
        for i in IDS:
            x=row(i);self.assertEqual(prepare_row(x,i,NOW,lambda u:source(i,alternative="SS_CI." in u))["status"],"READY")
            self.assertEqual(x["last_date"][:10],"2026-11-24")
            self.assertEqual(prepare_row(x,i,NOW,lambda u:source(i,alternative="SS_CI." in u))["status"],"NO_CHANGE")
    def test_missing_old_period_wrong_unit(self):
        for i in IDS:
            with self.assertRaises(ValueError):prepare_row(row(i),i,NOW,lambda u:source(i,missing=True,alternative="SS_CI." in u))
            with self.assertRaises(ValueError):prepare_row(row(i),i,NOW,lambda u:source(i,wrong=True,alternative="SS_CI." in u))
    def test_independent_failure(self):
        original={"EUR":[row(i) for i in IDS],"USD":[]}
        def fetch(url):
            i=next(i for i in IDS if CONFIG[i][0].split(".",1)[1] in url.replace("SS_CI.","SS_CIN."))
            if i==IDS[0]:raise OSError("unavailable")
            return source(i,alternative="SS_CI." in url)
        out,r=prepare(original,now=NOW,fetcher=fetch)
        self.assertEqual([x["status"] for x in r["series"]],["WITHHELD","READY","READY"])
        self.assertEqual(out["EUR"][0],original["EUR"][0])
        self.assertEqual(out["USD"],original["USD"])
if __name__=="__main__":unittest.main()
