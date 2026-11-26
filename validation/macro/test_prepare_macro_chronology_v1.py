import unittest,json,copy
from validation.macro.prepare_macro_chronology_v1 import SOURCE,CONFIG,reconcile,prepare,key
def row(ds,vs):return dict(dates=ds,values=vs,last_date=ds[-1],last_value=vs[-1])
class Tests(unittest.TestCase):
    def test_equal_duplicate_only(self):
        x=row(["2026-04","2026-04-01","2026-05"],[4.3,4.3,4.2])
        self.assertEqual(reconcile(x,"month")["identical_duplicates_removed"],1)
        self.assertEqual(x["dates"],["2026-04","2026-05"])
        self.assertEqual(reconcile(x,"month")["status"],"NO_CHANGE")
        y=row(["2026-04","2026-04-01"],[4.3,4.4]);old=copy.deepcopy(y)
        with self.assertRaises(ValueError):reconcile(y,"month")
        self.assertEqual(y,old)
    def test_sort_preserves_observations(self):
        x=row(["2026/8/31","2026/8/7","2026/8/3"],[1.743,1.611,1.562])
        self.assertEqual(reconcile(x,"day")["after"],"2026-08-31")
        self.assertEqual(x["values"],[1.562,1.611,1.743])
        self.assertEqual(reconcile(x,"day")["status"],"NO_CHANGE")
    def test_current_archive_exact_scope(self):
        before=json.loads(SOURCE.read_text());after,receipt=prepare(before)
        self.assertEqual(len(receipt["series"]),5)
        self.assertTrue(all(r["status"] in ("READY","NO_CHANGE") for r in receipt["series"]),receipt)
        self.assertEqual(set(before),set(after))
        for c in before:
            self.assertEqual([r["id"] for r in before[c]],[r["id"] for r in after[c]])
            for a,b in zip(before[c],after[c]):
                ident=(c,a["id"])
                if ident not in CONFIG:self.assertEqual(a,b);continue
                mode=CONFIG[ident]
                self.assertEqual({(key(d,mode),v) for d,v in zip(a["dates"],a["values"])},set(zip(b["dates"],b["values"])))
                self.assertEqual(b["dates"],sorted(set(b["dates"])))
        self.assertEqual(prepare(after)[0],after)
if __name__=="__main__":unittest.main()
