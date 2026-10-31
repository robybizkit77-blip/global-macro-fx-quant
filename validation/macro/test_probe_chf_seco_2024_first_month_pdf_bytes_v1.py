"""Network-free tests for the limited 4-issuer-document CHF recovery probe."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from validation.macro.probe_chf_seco_2024_first_month_pdf_bytes_v1 import (
    SCHEMA, TARGETS, allowed_url, candidates, pdf_candidate, run,
)

def fakepdf():
    return b"%PDF-1.7\n" + b"SECO Research sample\n" * 1200 + b"%%EOF\n"


class CHFSourceProbeTests(unittest.TestCase):
    def test_exact_four_months_and_only_official_https_issuer_links(self):
        r=candidates()
        self.assertEqual(set(r),set(TARGETS))
        for month, urls in r.items():
            self.assertGreaterEqual(len(urls),2)
            for url in urls:
                self.assertEqual(allowed_url(url,month),url)
        for url in (
            "http://www.seco.admin.ch/files/2024-09_Die_Lage_auf_dem_Arbeitsmarkt_DE.pdf",
            "https://other.example/2024-09_Die_Lage_auf_dem_Arbeitsmarkt_DE.pdf",
            "https://www.seco.admin.ch@hostile.example/2024-09_Die_Lage_auf_dem_Arbeitsmarkt_DE.pdf",
            "https://www.seco.admin.ch/files/2024-10_Die_Lage_auf_dem_Arbeitsmarkt_DE.pdf",
        ):
            with self.assertRaises(ValueError):
                allowed_url(url,"2024-09")

    def test_candidate_sha_is_current_binary_only_not_any_pit_certification(self):
        month="2024-09"
        final=candidates()[month][0]
        c=pdf_candidate(fakepdf(),"application/pdf",final,month)
        self.assertEqual(len(c["sha256"]),64)
        self.assertFalse(c["publisher_day_original_HTTP_bytes_certified"])
        self.assertFalse(c["monthly_table_first_column_authenticated"])
        self.assertFalse(c["exact_SNB_first_publication_vintage_proven"])
        for content,mime,redirect in (
            (b"<html>"*4000,"text/html",final),
            (b"%PDF-1.7"+"x".encode()*16000,"application/pdf",final),
            (fakepdf(),"text/html",final),
            (fakepdf(),"application/pdf","https://other.example/file.pdf"),
        ):
            with self.assertRaises(ValueError):
                pdf_candidate(content,mime,redirect,month)

    def test_network_down_is_recorded_as_no_bytes_not_fake_first_release(self):
        def offline(url,month):
            raise TimeoutError("not available")
        with TemporaryDirectory(prefix="gmfq-chf-probe-",dir="/tmp") as d:
            report=run(output_dir=Path(d),attempt=offline)
            self.assertEqual(report["summary"]["candidate_PDF_bytes_retrieved_today"],0)
            self.assertEqual(report["summary"]["still_no_candidate_original_PDF_bytes"],4)
            self.assertEqual(report["summary"]["exact_historical_SNB_release_vintages_certified"],0)
            self.assertFalse(report["can_promote_CHF_labour_to_24_months_PIT"])
            self.assertFalse(report["writes_live_data"])
            self.assertEqual(json.loads((Path(d)/"probe_manifest.json").read_text())["schema"],SCHEMA)

    def test_one_present_day_pdf_candidate_is_not_a_first_publication(self):
        def one_month(url,month):
            if month != "2024-12":
                raise FileNotFoundError("not found")
            value=pdf_candidate(fakepdf(),"application/pdf",url,month)
            return fakepdf(),value,url
        with TemporaryDirectory(prefix="gmfq-chf-probe-",dir="/tmp") as d:
            out=run(output_dir=d,attempt=one_month)
            self.assertEqual(out["summary"]["candidate_PDF_bytes_retrieved_today"],1)
            self.assertEqual(out["summary"]["still_no_candidate_original_PDF_bytes"],3)
            self.assertFalse(out["source_day_replay_certified"])
            self.assertFalse(out["can_upgrade_2024_SECO_fixture_automatically"])
            self.assertFalse(out["can_update_D_or_28_pairs"])
            self.assertTrue(out["source_months"]["2024-12"]["captured_candidate_today"])
            self.assertIsNone(out["source_months"]["2024-09"]["captured_candidate_today"])


if __name__ == "__main__":
    unittest.main()
