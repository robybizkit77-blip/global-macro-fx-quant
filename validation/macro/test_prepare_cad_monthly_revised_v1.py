import csv,io,unittest
from datetime import datetime,timezone
from unittest.mock import patch
from validation.macro.prepare_cad_monthly_revised_v1 import CONFIG,prepare,prepare_row,parse
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
MED="CA_CPI_MEDIAN_YOY_history_value"
TRIM="CA_CPI_TRIM_YOY_history_value"
EMP="CA_EMPLOYMENT_history_value"
def row(ident):
    _,file,unit,_=CONFIG[ident]
    return {"id":ident,"source_file":file,"unit":unit,"frequency":"M","dates":["2024-01","2024-02"],"values":[2,3],"last_date":"2024-02","last_value":3}
def fixture(duplicate=False):
    f=io.StringIO();w=csv.writer(f)
    w.writerow(["REF_DATE","GEO","Alternative measures","UOM","SCALAR_FACTOR","VECTOR","VALUE"])
    for n in range(30):
        y=2024+n//12;m=n%12+1;d=f"{y}-{m:02d}"
        w.writerow([d,"Canada","Measure of core inflation based on a weighted median approach, CPI-median (year-over-year percent change)","Percent","units","v108785714",2+n/100])
        w.writerow([d,"Canada","Measure of core inflation based on a trimmed mean approach, CPI-trim (year-over-year percent change)","Percent","units","v108785715",3+n/100])
        w.writerow([d,"Canada","Measure of core inflation based on a weighted median approach, CPI-median (index, 198901=100)","Index","units","v1481215115",100+n])
        if duplicate and n==1:w.writerow([d,"Canada","Measure of core inflation based on a weighted median approach, CPI-median (year-over-year percent change)","Percent","units","v108785714",5])
    return f.getvalue()
class StatCanBatchTests(unittest.TestCase):
    def test_distinguishes_rates_from_index(self):
        x=row(MED);result=prepare_row(x,MED,NOW,fixture())
        self.assertEqual(result["after"],"2026-06")
        self.assertEqual(result["vector"],"v108785714")
        self.assertEqual(len(x["dates"]),30)
        self.assertEqual(prepare_row(x,MED,NOW,fixture())["status"],"NO_CHANGE")
    def test_duplicate_source_is_rejected(self):
        with self.assertRaises(ValueError):parse(fixture(True),"median")
    def test_download_reuse_and_isolated_failure(self):
        original={"CAD":[row(MED),row(TRIM),row(EMP)],"EUR":[]}
        calls=[]
        def fetch(pid):
            calls.append(pid)
            if pid=="14100287":raise OSError("unavailable")
            return fixture()
        with patch.dict(CONFIG,{i:CONFIG[i] for i in (MED,TRIM,EMP)},clear=True):
            out,receipt=prepare(original,now=NOW,fetcher=fetch)
        self.assertEqual(calls,["18100256","14100287"])
        self.assertEqual([r["status"] for r in receipt["series"]],["READY","READY","WITHHELD"])
        self.assertEqual(out["CAD"][-1],original["CAD"][-1])
        self.assertEqual(out["EUR"],original["EUR"])
if __name__=="__main__":unittest.main()
