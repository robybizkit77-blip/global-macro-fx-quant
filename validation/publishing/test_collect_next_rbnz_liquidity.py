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

    def test_workbook_overlap_and_continuity(self):
        months=[f"{i//12:04d}-{i%12+1:02d}" for i in range(2023*12+9,2026*12+9)]
        d10={k:{"liquidity":100+i} for i,k in enumerate(months)}
        c50={k:{"money":1000+i,"credit":2000+i} for i,k in enumerate(months)}
        payload={"period":months[-1],"history":{k:{**d10[k],**c50[k]} for k in months[-5:]}}
        self.assertEqual(len(m.backfill_monthly(payload,[d10,c50])),36)
        d10[months[-1]]={"liquidity":999}
        with self.assertRaisesRegex(ValueError,"overlap mismatch"):
            m.backfill_monthly(payload,[d10,c50])
        d10[months[-1]]={"liquidity":135}
        del c50[months[0]]
        with self.assertRaisesRegex(ValueError,"incomplete"):
            m.backfill_monthly(payload,[d10,c50])

    def test_workbook_identity_and_rounding(self):
        from datetime import datetime
        rows=[[None]*24 for _ in range(7)]
        rows[0][0]="D10 Influences on Settlement Cash"
        rows[1][1]="($NZ million)"
        rows[3][0]="Date"
        rows[3][23]="9.  Average settlement cash"
        rows[6][0]=datetime(2026,7,31)
        rows[6][23]=28302.8994
        self.assertEqual(m.workbook_series(rows,"d10"),{"2026-07":{"liquidity":28303}})
        rows[3][23]="Cash at end of month"
        with self.assertRaisesRegex(ValueError,"identity"):
            m.workbook_series(rows,"d10")
