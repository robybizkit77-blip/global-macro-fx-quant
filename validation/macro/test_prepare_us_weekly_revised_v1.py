"""Regression tests for independent revised weekly histories."""
import unittest
from datetime import datetime,timezone,date,timedelta
from unittest.mock import patch
from validation.macro.prepare_us_weekly_revised_v1 import CONFIG,prepare,prepare_row,parse_weekly,verify_metadata
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
IDENT="US_WALCL_history_value"
OTHER="US_NFCI_history_value"
def row(ident):
    fred,title,unit,adj,weekday,old=CONFIG[ident]
    start=date(2025,2,17)+timedelta(days=weekday)
    ds=[start.isoformat(),(start+timedelta(days=7)).isoformat()]
    return {"id":ident,"source_file":"US_"+fred+"_history.csv","frequency":"W","unit":old,
            "dates":ds,"values":[100,101],"last_date":ds[-1],"last_value":101}
def response(url):
    fred=next(cfg[0] for cfg in CONFIG.values() if url.endswith("/"+cfg[0]) or "id="+cfg[0]+"&" in url)
    cfg=next(v for v in CONFIG.values() if v[0]==fred)
    if "/series/" in url:
        return f"<title>{cfg[1]} ({fred}) | FRED</title><p>Units: {cfg[2]}, {cfg[3]}</p><p>Frequency: Weekly</p>".encode(),url
    start=date(2025,2,17)+timedelta(days=cfg[4])
    lines=["observation_date,"+fred]
    for n in range(30): lines.append(f"{start+timedelta(days=7*n)},{100+n}")
    return ("\n".join(lines)+"\n").encode(),url
class WeeklyTests(unittest.TestCase):
    def test_complete_history_and_idempotence(self):
        x=row(IDENT)
        self.assertEqual(prepare_row(x,IDENT,NOW,response)["status"],"READY")
        self.assertEqual(len(x["dates"]),30)
        self.assertEqual(prepare_row(x,IDENT,NOW,response)["status"],"NO_CHANGE")
    def test_weekday_drift_rejected(self):
        x=row(IDENT);x["dates"][0]="2025-02-20"
        with self.assertRaisesRegex(ValueError,"weekday"): prepare_row(x,IDENT,NOW,response)
    def test_invalid_units_rejected(self):
        with self.assertRaises(ValueError):
            verify_metadata(b"<title>Assets: Total Assets: Total Assets (WALCL)</title><p>Units: Millions of U.S. Dollars, Seasonally Adjusted</p><p>Frequency: Weekly</p>",
            "WALCL","Assets: Total Assets: Total Assets","Millions of U.S. Dollars","Not Seasonally Adjusted")
    def test_negative_financial_conditions_valid(self):
        raw=("DATE,NFCI\n"+"\n".join(f"{date(2025,2,21)+timedelta(days=7*n)},-0.5" for n in range(30))).encode()
        self.assertEqual(parse_weekly(raw,"NFCI",4,NOW.date())[-1][1],-0.5)
    def test_independent_failure(self):
        original={"USD":[row(IDENT),row(OTHER)],"EUR":[]}
        def fetcher(url):
            if "WALCL" in url:raise OSError("transport outage")
            return response(url)
        with patch.dict(CONFIG,{IDENT:CONFIG[IDENT],OTHER:CONFIG[OTHER]},clear=True):
            out,r=prepare(original,now=NOW,fetcher=fetcher)
        self.assertEqual([x["status"] for x in r["series"]],["WITHHELD","READY"])
        self.assertEqual(out["USD"][0],original["USD"][0])
        self.assertEqual(out["EUR"],original["EUR"])
if __name__=="__main__":unittest.main()
