#!/usr/bin/env python3
import io, tempfile, json
from pathlib import Path
from openpyxl import Workbook
from inspect_rbnz_b2_official_workbook_v1 import inspect

def run():
    with tempfile.TemporaryDirectory() as d:
        wb=Workbook();ws=wb.active;ws.title="Daily close"
        ws.append(["Secondary market government bond closing yields (%pa)"])
        ws.append(["Date","2 year","10 year"])
        ws.append(["2026-10-16",3.85,5.05])
        p=Path(d)/"hb2-daily-close.xlsx";wb.save(p)
        # Fixture is synthetic: test workbook inventory only, not data correctness.
        # Generated fixture is smaller than genuine B2 file, so pad with irrelevant XLSX metadata?
        from zipfile import ZipFile,ZIP_DEFLATED
        with ZipFile(p,"a",compression=ZIP_DEFLATED) as z:
            z.writestr("gmfq_fixture_padding.txt","a"*30000,compress_type=0)
        x=inspect(p)
        assert x["status"]=="REVIEW_REQUIRED_NOT_CERTIFIED"
        assert x["writes_live_data"] is False
        assert x["sha256"] and x["worksheets"][0]["sheet"]=="Daily close"
        assert any("government bond" in str(v).lower() for v in x["worksheets"][0]["headings"])
        try:inspect(Path(d)/"not-official.xlsx")
        except FileNotFoundError:pass
        else:raise AssertionError("foreign file must be rejected")
    print("RBNZ_B2_WORKBOOK_INVENTORY_QA_GREEN")
if __name__=="__main__":run()
