import copy,csv,io,unittest
from datetime import datetime,timezone
from validation.macro.prepare_aud_oecd_cli_v1 import ID,META,parse,reconcile
class TestCLI(unittest.TestCase):
    def test_identity(self):
        now=datetime(2026,11,26,tzinfo=timezone.utc)
        def raw(meta,period):
            f=io.StringIO();w=csv.DictWriter(f,fieldnames=[*META,"TIME_PERIOD","OBS_VALUE"]);w.writeheader();w.writerow({**meta,"TIME_PERIOD":period,"OBS_VALUE":99.97});return f.getvalue().encode()
        self.assertEqual(parse(raw(META,"2026-10"),now),{"2026-10":99.97})
        with self.assertRaises(ValueError):parse(raw({**META,"REF_AREA":"USA"},"2026-10"),now)
        with self.assertRaises(ValueError):parse(raw(META,"2026-11"),now)
    def test_reconcile(self):
        now=datetime(2026,11,26,tzinfo=timezone.utc)
        months=[f"{2023+i//12}-{i%12+1:02}" for i in range(34)]
        ds=[d+"-01T00:00:00Z" for d in months[:-1]]
        row=dict(id=ID,source_file="AU_OECD_CLI_LEAD_INDICATOR_history.csv",dates=ds,values=[100.]*len(ds),last_date=ds[-1],last_value=100.)
        old=copy.deepcopy(row);obs={d:99.99 for d in months}
        self.assertEqual(reconcile(row,obs,"official",b"x",now)["status"],"READY")
        self.assertEqual(reconcile(row,obs,"official",b"x",now)["status"],"NO_CHANGE")
        bad=dict(obs);bad[months[0]]=101
        with self.assertRaises(ValueError):reconcile(old,bad,"official",b"x",now)
        with self.assertRaises(ValueError):reconcile(old,{d:99.99 for d in months[1:]},"official",b"x",now)
if __name__=="__main__":unittest.main()
