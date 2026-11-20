#!/usr/bin/env python3
from copy import deepcopy
from datetime import datetime
from io import BytesIO
import unittest

from openpyxl import Workbook

from reconcile_fxv2_nzd_b2_postroll_v1 import GOV_GROUP, SERIES, WEB_SCHEMA, reconcile


DAYS = ["2026-10-30", "2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05", "2026-11-06"]
RELEASE = "2026-11-09"


def workbook(*, release=RELEASE, bad_bond=False, wrong_group=False):
    wb = Workbook()
    data = wb.active
    data.title = "Data"
    ids = (*SERIES, ("2 year", "%pa", "INM.DS02.NZZC"))
    data.append([None, "Swap rates close" if wrong_group else GOV_GROUP,
                 GOV_GROUP, GOV_GROUP, GOV_GROUP, "Swap rates close"])
    data.append([None, *(s[0] for s in ids)])
    data.append(["Notes"])
    data.append(["Unit", *(s[1] for s in ids)])
    data.append(["Series Id", *(s[2] for s in ids)])
    for day in ["2026-10-29", *DAYS]:
        data.append([datetime.fromisoformat(day), 3.96, 4.90,
                     3.95 if bad_bond else 3.96, 4.90, 99])
    info = wb.create_sheet("Table Description")
    info.append(["Published By", "Reserve Bank of New Zealand"])
    info.append(["Table", "Daily wholesale interest rates (% pa) - B2"])
    info.append(["Source", "NZFMA"])
    info.append(["Published Date", datetime.fromisoformat(release)])
    with BytesIO() as stream:
        wb.save(stream)
        return stream.getvalue()


class ReconciledPostRoll(unittest.TestCase):
    def setUp(self):
        self.web = {"schema": WEB_SCHEMA, "release_date": RELEASE, "as_of": DAYS[-1],
                    "post_roll_table_rows": [{"date": day, "2Y": 3.96, "10Y": 4.90} for day in DAYS]}

    def test_reconciled_rows_start_on_roll_and_are_research_only(self):
        raw = workbook()
        receipt = reconcile(self.web, b"published web", raw)
        self.assertEqual(receipt["html_xlsx_matched_dates"], DAYS)
        self.assertEqual(receipt["observations"], self.web["post_roll_table_rows"])
        self.assertFalse(receipt["eligible_for_fx_pair_engine"])
        self.assertIs(reconcile(self.web, b"same rows different markup", raw, receipt), receipt)

    def test_same_day_different_source_and_changes_stop_publication(self):
        for args, message in (({"release": "2026-11-10"}, "different release"),
                              ({"bad_bond": True}, "named bond disagree"),
                              ({"wrong_group": True}, "series ID changed")):
            with self.subTest(args=args), self.assertRaisesRegex(ValueError, message):
                reconcile(self.web, b"published web", workbook(**args))
        web = deepcopy(self.web)
        web["post_roll_table_rows"][-1]["2Y"] = 3.97
        with self.assertRaisesRegex(ValueError, "exact matching"):
            reconcile(web, b"published web", workbook())

    def test_rollback_is_blocked(self):
        raw = workbook()
        previous = reconcile(self.web, b"published web", raw)
        previous["publication_date"] = "2026-11-10"
        with self.assertRaisesRegex(ValueError, "source rollback"):
            reconcile(self.web, b"published web", raw, previous)


if __name__ == "__main__":
    unittest.main()
