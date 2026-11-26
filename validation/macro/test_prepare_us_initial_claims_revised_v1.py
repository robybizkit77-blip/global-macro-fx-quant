import unittest
from datetime import date,datetime,timedelta,timezone
from validation.macro.prepare_us_initial_claims_revised_v1 import IDENT,prepare_row
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
START=date(2026,4,4)
def source(url):
    if "/series/" in url:return b"<html><title>Initial Claims (ICSA) | FRED</title><body>Units: Number, Seasonally Adjusted Frequency: Weekly</body></html>",url
    return ("observation_date,ICSA\n"+"\n".join(f"{START+timedelta(days=7*i)},{200000+1000*i}" for i in range(34))).encode(),url
def row():
    ds=[str(START+timedelta(days=7*i-1)) for i in range(26)]
    return {"id":IDENT,"unit":"Persons","frequency":"W","source_file":"US_ICSA_history.csv","dates":ds,"values":[200000+1000*i for i in range(26)],"last_date":ds[-1],"last_value":225000}
class Tests(unittest.TestCase):
    def test_friday_migration_and_noop(self):
        x=row();r=prepare_row(x,NOW,source);self.assertEqual(r["shift_days"],1)
        self.assertEqual(x["dates"][0],"2026-04-04")
        self.assertEqual(prepare_row(x,NOW,source)["status"],"NO_CHANGE")
    def test_reject_wrong_week(self):
        x=row();x["values"]=[v+1000 for v in x["values"]];x["last_value"]+=1000
        with self.assertRaises(ValueError):prepare_row(x,NOW,source)
if __name__=="__main__":unittest.main()
