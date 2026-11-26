import unittest
from datetime import datetime,timezone
from validation.macro.prepare_aud_abs_cpi_context_v1 import CONFIG,MONTHS,prepare
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
def dates():
    return [f"{2025+(3+n)//12}-{(3+n)%12+1:02d}" for n in range(19)]
def html(missing=False):
    h="<p>Reference period October 2026</p><table><tr><th></th><th>All groups CPI (%)</th><th>Trimmed mean (%)</th></tr>"
    for n,d in enumerate(dates()):
        if missing and n==5:continue
        m=list(MONTHS)[int(d[5:])-1]
        h+=f"<tr><th>{m}-{d[2:4]}</th><td>{3+n/10}</td><td>3.6</td></tr>"
    return h+"</table>"
def fixture():
    ds=dates()[:16];rows=[]
    for i,(column,unit) in CONFIG.items():
        vs=[3+n/10 if column==1 else 3.6 for n in range(16)]
        rows.append(dict(id=i,unit=unit,frequency="M",dates=ds,values=vs,last_date=ds[-1],last_value=vs[-1]))
    return {"AUD":rows+[{"id":"AU_CPI_HEADLINE_Q_YOY_history_value"}],"USD":[]}
class Tests(unittest.TestCase):
    def test_update_noop_scope(self):
        original=fixture();out,r=prepare(original,now=NOW,fetcher=lambda u:html())
        self.assertEqual([a["status"] for a in r["series"]],["READY","READY"])
        self.assertEqual([a["after"] for a in r["series"]],["2026-10","2026-10"])
        self.assertEqual(out["AUD"][-1],original["AUD"][-1])
        self.assertEqual([a["status"] for a in prepare(out,now=NOW,fetcher=lambda u:html())[1]["series"]],["NO_CHANGE","NO_CHANGE"])
    def test_missing_period_and_wrong_variant(self):
        original=fixture();out,r=prepare(original,now=NOW,fetcher=lambda u:html(True))
        self.assertEqual(out,original)
        self.assertTrue(all(a["status"]=="WITHHELD" for a in r["series"]))
        out,r=prepare(original,now=NOW,fetcher=lambda u:html().replace("Trimmed mean (%)","Weighted median (%)"))
        self.assertEqual(out,original)
if __name__=="__main__":unittest.main()
