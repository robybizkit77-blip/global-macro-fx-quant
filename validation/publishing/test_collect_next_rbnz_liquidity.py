import unittest
from unittest.mock import patch
from validation.publishing import collect_next_rbnz_liquidity as m

class TestRBNZMonthlyBackfill(unittest.TestCase):
    def collect(self, stamps, revised=False):
        vals = dict(m.SEED)
        vals["2026-07"] = dict(liquidity=26000,money=450000,credit=620000)
        dates=[s for s in stamps]
        source=[("2026-10-30","2026-11-30","2026-09",
                 {"liquidity":{s:vals[s]["liquidity"] for s in dates}}),
                ("2026-10-30","2026-11-30","2026-09",
                 {k:{s:vals[s][k]+(1 if revised and s=="2026-08" and k=="credit" else 0)
                     for s in dates} for k in ("money","credit")})]
        previous={"history":m.SEED,"period":"2026-09","released":"2026-10-30"}
        with patch.object(m,"fetch",return_value="html"),patch.object(m,"read_table",side_effect=source):
            return m.collect_monthly(previous,"2026-11-27")
    def test_backfill(self):
        self.assertEqual(list(sorted(self.collect(["2026-07","2026-08","2026-09"])["history"])),
                         ["2026-07","2026-08","2026-09"])
    def test_revision_rejected(self):
        with self.assertRaisesRegex(ValueError,"revised"):
            self.collect(["2026-07","2026-08","2026-09"],True)
    def test_no_overlap(self):
        with self.assertRaisesRegex(ValueError,"overlap"):
            self.collect(["2026-07","2026-08"])
