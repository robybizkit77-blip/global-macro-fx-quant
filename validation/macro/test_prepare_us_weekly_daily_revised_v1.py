import unittest
from datetime import datetime,timezone,date,timedelta
from unittest.mock import patch
from validation.macro.prepare_us_weekly_daily_revised_v1 import CONFIG,prepare,prepare_row,csv_rows
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
IDENT="US_NFCI_history_value"
OTHER="US_WALCL_history_value"
def row(ident):
    fred,title,unit,freq,adj,old=CONFIG[ident]
    return {"id":ident,"source_file":"US_"+fred+"_history.csv","frequency":freq,"unit":old,
            "dates":["2025-01-03","2025-01-10"],"values":[-1.0,-0.5],"last_date":"2025-01-10","last_value":-0.5}
def response(url):
    cfg=next(v for v in CONFIG.values() if url.endswith("/"+v[0]) or "id="+v[0]+"&" in url)
    fred,title,unit,freq,adj,old=cfg
    if "/series/" in url:
        return f"<title>{title} ({fred}) | FRED</title><p>Units: {unit}, {adj}</p><p>Frequency: Weekly</p>".encode(),url
    lines=["observation_date,"+fred]
    for n in range(25):
        d=date(2025,1,3)+timedelta(days=7*n)
        lines.append(f"{d.isoformat()},{-0.25+n/100}")
    return ("\n".join(lines)+"\n").encode(),url
class SourceTests(unittest.TestCase):
    def test_negative_values_and_idempotence(self):
        x=row(IDENT)
        self.assertEqual(prepare_row(x,IDENT,NOW,response)["status"],"READY")
        self.assertEqual(len(x["dates"]),25)
        self.assertLess(x["last_value"],0)
        self.assertEqual(prepare_row(x,IDENT,NOW,response)["status"],"NO_CHANGE")
    def test_failure_isolated(self):
        current={"USD":[row(IDENT),row(OTHER)],"EUR":[]}
        def fetcher(url):
            if "NFCI" in url:raise OSError("source unavailable")
            return response(url)
        with patch.dict(CONFIG,{IDENT:CONFIG[IDENT],OTHER:CONFIG[OTHER]},clear=True):
            out,receipt=prepare(current,now=NOW,fetcher=fetcher)
        self.assertEqual(out["USD"][0],current["USD"][0])
        self.assertEqual([x["status"] for x in receipt["series"]],["WITHHELD","READY"])
        self.assertEqual(out["EUR"],current["EUR"])
    def test_missing_existing_date_is_rejected(self):
        x=row(IDENT)
        x.update(dates=["2025-01-03","2025-01-11"],last_date="2025-01-11")
        with self.assertRaises(ValueError):prepare_row(x,IDENT,NOW,response)
    def test_future_rejected(self):
        with self.assertRaises(ValueError):csv_rows(b"DATE,NFCI\n2027-01-01,1\n","NFCI",NOW.date())
if __name__=="__main__":unittest.main()
