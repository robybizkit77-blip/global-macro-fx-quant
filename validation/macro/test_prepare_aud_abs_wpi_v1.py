import calendar,copy,unittest
from datetime import datetime,timezone
from validation.macro.prepare_aud_abs_wpi_v1 import ID,TITLE,prepare
NOW=datetime(2026,11,27,tzinfo=timezone.utc)
def fixture():
    dates=[]; values=[]; rows=[]
    for n in range(43):
        y=2016+n//4;m=(3,6,9,12)[n%4];v=3.2 if n<42 else 3.5
        dates.append(f"{calendar.monthrange(y,m)[1]:02d}/{m:02d}/{y}");values.append(v)
        rows.append(f"<tr><th>{('Mar','Jun','Sep','Dec')[n%4]}-{y%100:02d}</th><td>0.8</td><td>{v}</td></tr>")
    html="<p>Reference period September 2026</p><div><h4>"+TITLE+"</h4><table><tr><th></th><th>Quarterly (%)</th><th>Annual (%)</th></tr>"+"".join(rows)+"</table></div>"
    return {"AUD":[{"id":ID,"unit":"Percent","frequency":"Q","source_file":"AU_WPI_YOY_history.csv","dates":dates[:-1],"values":values[:-1],"last_date":dates[-2],"last_value":values[-2]}]},html
class Tests(unittest.TestCase):
    def test_ready_idempotent(self):
        old,html=fixture(); original=copy.deepcopy(old)
        new,r=prepare(old,now=NOW,fetcher=lambda _:html)
        self.assertEqual(old,original);self.assertEqual(r["series"][0]["status"],"READY")
        self.assertEqual(new["AUD"][0]["last_value"],3.5);self.assertEqual(new["AUD"][0]["last_date"],"30/09/2026")
        self.assertEqual(prepare(new,now=NOW,fetcher=lambda _:html)[1]["series"][0]["status"],"NO_CHANGE")
    def test_fail_closed(self):
        old,html=fixture()
        for bad in (html.replace(TITLE,"Original private sector"),html.replace("Annual (%)","Index"),html.replace("Sep-26","Dec-26"),html.replace("<td>3.2</td>","<td>5.0</td>"),html.replace("Mar-16","Mar-15")):
            new,r=prepare(old,now=NOW,fetcher=lambda _:bad)
            self.assertEqual(new,old);self.assertEqual(r["series"][0]["status"],"WITHHELD")
if __name__=="__main__":unittest.main()
