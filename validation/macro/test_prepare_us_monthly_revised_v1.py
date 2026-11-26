"""Exercise the revised history guard independently of live FRED traffic."""
import unittest
from datetime import datetime,timezone
from unittest.mock import patch
from validation.macro.prepare_us_monthly_revised_v1 import CONFIG,prepare,prepare_row,metadata

NOW=datetime(2026,11,26,tzinfo=timezone.utc)
IDENT="US_INDPRO_history_value"
OTHER="US_PCEPI_history_value"
def row(ident):
    fred,file,title,unit,old=CONFIG[ident]
    return {"id":ident,"source_file":file,"frequency":"M","unit":old,
            "dates":["2019-10-01","2019-11-01"],"values":[100,101],
            "last_date":"2019-11-01","last_value":101}
def response(url):
    fred=next((cfg[0] for cfg in CONFIG.values() if url.endswith("/"+cfg[0]) or "id="+cfg[0]+"&" in url),None)
    cfg=next(v for v in CONFIG.values() if v[0]==fred)
    if "/series/" in url:
        return f"<title>{cfg[2]} ({fred}) | FRED</title><p>Units: {cfg[3]}, Seasonally Adjusted</p><p>Frequency: Monthly</p>".encode(),url
    lines=["observation_date,"+fred]
    for n in range(25):
        y=2019+(9+n)//12;m=(9+n)%12+1
        lines.append(f"{y}-{m:02d}-01,{100+n}")
    return ("\n".join(lines)+"\n").encode(),url
class BatchTests(unittest.TestCase):
    def test_full_window_and_idempotence(self):
        x=row(IDENT)
        receipt=prepare_row(x,IDENT,NOW,response)
        self.assertEqual(receipt["status"],"READY")
        self.assertEqual(x["last_date"],"2021-10-01")
        self.assertEqual(len(x["dates"]),25)
        self.assertFalse(x["current_vintage_provenance"]["source_series_first_release_PIT_certified"])
        self.assertEqual(prepare_row(x,IDENT,NOW,response)["status"],"NO_CHANGE")
    def test_metadata_mismatch(self):
        with self.assertRaises(ValueError):
            metadata(b"<title>Wrong (INDPRO)</title>","INDPRO","Industrial Production","Index 2017=100")
    def test_independent_transport_failure(self):
        original={"USD":[row(IDENT),row(OTHER)],"EUR":[]}
        def fetcher(url):
            if "INDPRO" in url: raise OSError("temporary transport outage")
            return response(url)
        with patch.dict(CONFIG,{IDENT:CONFIG[IDENT],OTHER:CONFIG[OTHER]},clear=True):
            out,receipt=prepare(original,now=NOW,fetcher=fetcher)
        self.assertEqual(out["USD"][0],original["USD"][0])
        self.assertEqual(out["EUR"],original["EUR"])
        self.assertEqual([x["status"] for x in receipt["series"]],["WITHHELD","READY"])
        self.assertEqual(original["USD"][1]["last_date"],"2019-11-01")
    def test_stale_history_cannot_regress(self):
        x=row(IDENT)
        x.update(dates=["2019-10-01","2026-09-01"],values=[100,101],last_date="2026-09-01")
        with self.assertRaises(ValueError): prepare_row(x,IDENT,NOW,response)
    def test_core_cpi_only_official_gap_is_preserved(self):
        ident="US_CPILFESL_history_value"
        x=row(ident)
        x.update(dates=["2024-10-01","2025-09-01","2025-11-01"],
                 values=[100,111,113],last_date="2025-11-01",last_value=113)
        def source(url,unexpected=False):
            if "/series/" in url:
                cfg=CONFIG[ident]
                return f"<title>{cfg[2]} ({cfg[0]}) | FRED</title><p>Units: {cfg[3]}, Seasonally Adjusted</p><p>Frequency: Monthly</p>".encode(),url
            lines=["observation_date,CPILFESL"]
            for n in range(25):
                y=2024+(9+n)//12;m=(9+n)%12+1
                d=f"{y}-{m:02d}"
                val="." if d=="2025-10" or (unexpected and d=="2026-01") else str(100+n)
                lines.append(f"{d}-01,{val}")
            return ("\n".join(lines)+"\n").encode(),url
        result=prepare_row(x,ident,NOW,source)
        self.assertEqual(result["after"],"2026-10-01")
        self.assertNotIn("2025-10-01",x["dates"])
        self.assertEqual(x["current_vintage_provenance"]["official_missing_periods"],["2025-10"])
        self.assertTrue(x["current_vintage_provenance"]["cross_gap_monthly_change_not_valid"])
        self.assertEqual(prepare_row(x,ident,NOW,source)["status"],"NO_CHANGE")
        with self.assertRaises(ValueError):
            prepare_row(x,ident,NOW,lambda u:source(u,True))
if __name__=="__main__":unittest.main()
