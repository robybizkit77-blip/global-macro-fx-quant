import csv,io,unittest
from datetime import datetime,timezone,timedelta,date
from validation.macro.prepare_eur_ecb_daily_revised_v1 import CONFIG,prepare,prepare_row,WEEKLY_ASSETS,WEEKLY_KEY
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
IDS=[i for i in CONFIG if i!=WEEKLY_ASSETS]
def val(i,n):return [2000000+n,.03+n*.00001,129+n*.01][IDS.index(i)]
def row(i):
    _,unit,suffix,*_=CONFIG[i]
    dates=[(date(2026,9,1)+timedelta(days=n)).isoformat()+suffix for n in range(50)]
    values=[val(i,n) for n in range(50)]
    return {"id":i,"source_file":i.removesuffix("_value")+".csv","unit":unit,"frequency":"D","dates":dates,"values":values,"last_date":dates[-1],"last_value":values[-1]}
def source(i,wrong=False,missing=False,alternative=False,sparse=False):
    key,_,_,mult,*_=CONFIG[i];f=io.StringIO();w=csv.writer(f);w.writerow(["KEY","TIME_PERIOD","OBS_VALUE","UNIT_MULT"])
    for n in range(85):
        if missing and n==4:continue
        if sparse and n%3:continue
        w.writerow([key.replace("SS_CIN","SS_CI") if alternative else key,(date(2026,9,1)+timedelta(days=n)).isoformat(),val(i,n)+(.1 if alternative else 0),"99" if wrong else mult])
    return f.getvalue()
class ECBTests(unittest.TestCase):
    def test_full_window_idempotence(self):
        for i in IDS:
            x=row(i);self.assertEqual(prepare_row(x,i,NOW,lambda u:source(i,alternative="SS_CI." in u))["status"],"READY")
            self.assertEqual(x["last_date"][:10],"2026-11-24")
            self.assertEqual(prepare_row(x,i,NOW,lambda u:source(i,alternative="SS_CI." in u))["status"],"NO_CHANGE")
    def test_alternative_calendar_compares_only_real_paired_dates(self):
        i=IDS[1];x=row(i)
        result=prepare_row(x,i,NOW,lambda u:source(i,alternative="SS_CI." in u,sparse="SS_CI." in u))
        self.assertEqual(result["status"],"READY")
        self.assertEqual(result["overlap_audit"]["alternative_overlap_count"],17)
    def test_retired_legacy_requires_real_terminal_and_exact_overlap(self):
        i=IDS[1]
        def legacy(end=date(2025,5,2),count=24):
            key=CONFIG[i][0].replace("SS_CIN","SS_CI")
            return "KEY,TIME_PERIOD,OBS_VALUE,UNIT_MULT\n"+"\n".join(f"{key},{end-timedelta(days=n)},0.1,0" for n in range(count))
        def fetch(url):
            if "SS_CI." in url:
                self.assertIn("startPeriod=2024-01-01",url)
                return legacy()
            return source(i)
        x=row(i);r=prepare_row(x,i,NOW,fetch)
        self.assertEqual(r["overlap_audit"]["variant_proof"],"POST_LEGACY_TERMINATION_TIGHT_REVISED_OVERLAP")
        self.assertEqual(r["overlap_audit"]["legacy_last_observation"],"2025-05-02")
        for bad in (legacy(date(2025,5,1)),legacy(count=0),legacy(date(2025,5,3))):
            with self.assertRaises(ValueError):
                prepare_row(row(i),i,NOW,lambda u:bad if "SS_CI." in u else source(i))
        x=row(i);x["values"]=[v+.0002 for v in x["values"]];x["last_value"]=x["values"][-1]
        with self.assertRaises(ValueError):
            prepare_row(x,i,NOW,fetch)
    def test_retired_legacy_allows_tiny_nonuniform_revisions_only_with_matching_shape(self):
        i=IDS[1];key=CONFIG[i][0];legacy_key=key.replace("SS_CIN","SS_CI")
        legacy="KEY,TIME_PERIOD,OBS_VALUE,UNIT_MULT\n"+"\n".join(f"{legacy_key},{date(2025,5,2)-timedelta(days=n)},0.1,0" for n in range(24))
        def v(n):return .03+((n*7)%11)*.001
        def fetch(url):
            if "SS_CI." in url:return legacy
            return "KEY,TIME_PERIOD,OBS_VALUE,UNIT_MULT\n"+"\n".join(f"{key},{date(2026,9,1)+timedelta(days=n)},{v(n)},0" for n in range(85))
        x=row(i);x["values"]=[v(n)+(.00005 if n%2 else -.00005) for n in range(50)];x["last_value"]=x["values"][-1]
        r=prepare_row(x,i,NOW,fetch)
        self.assertEqual(r["status"],"READY")
        self.assertEqual(r["exact_overlap"],0)
        self.assertEqual(x["values"],[v(n) for n in range(85)])
        x=row(i);x["values"]=[v(n)+(.00005 if n%2 else -.00005) for n in range(50)];x["values"][10]+=.001;x["last_value"]=x["values"][-1]
        with self.assertRaises(ValueError):prepare_row(x,i,NOW,fetch)
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
        self.assertEqual([x["status"] for x in r["series"]],["WITHHELD","READY","READY","WITHHELD"])
        self.assertEqual(out["EUR"][0],original["EUR"][0])
        self.assertEqual(out["USD"],original["USD"])
    def test_weekly_assets_exact_identity_and_no_future_or_missing_weeks(self):
        ds=[date(2025,2,28)+timedelta(days=7*n) for n in range(91)]
        labels=[f"{d.isocalendar().year:04d}-W{d.isocalendar().week:02d}" for d in ds]
        vs=[5900000+n*100 for n in range(len(ds))]
        def weekly_row():
            return {"id":WEEKLY_ASSETS,"source_file":WEEKLY_ASSETS.removesuffix("_value")+".csv","unit":"EUR millions","frequency":"W","dates":labels[:82],"values":vs[:82],"last_date":labels[81],"last_value":vs[81]}
        def feed(key=WEEKLY_KEY,mult="6",skip=None,offset=0,future=False):
            rows=[f"{key},{d},{v+offset},{mult}" for n,(d,v) in enumerate(zip(labels,vs)) if n!=skip]
            if future:rows.append(f"{key},2026-W49,5900000,6")
            return "KEY,TIME_PERIOD,OBS_VALUE,UNIT_MULT\n"+"\n".join(rows)
        x=weekly_row()
        self.assertEqual(prepare_row(x,WEEKLY_ASSETS,NOW,lambda u:feed())["status"],"READY")
        self.assertEqual(x["last_date"],labels[-1])
        self.assertEqual(prepare_row(x,WEEKLY_ASSETS,NOW,lambda u:feed())["status"],"NO_CHANGE")
        for bad in (feed(key="ILM.WRONG"),feed(mult="3"),feed(skip=5),feed(skip=85),feed(offset=900000),feed(future=True)):
            with self.assertRaises(ValueError):prepare_row(weekly_row(),WEEKLY_ASSETS,NOW,lambda u:bad)
if __name__=="__main__":unittest.main()
