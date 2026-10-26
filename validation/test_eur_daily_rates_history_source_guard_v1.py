"""EUR daily 2Y/10Y old-history quarantine and safe G8 feed continuity."""
import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

from validation import build_rates_candidate_from_audit as m


class EURDailyRatesHistorySourceGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live=json.loads(m.DEFAULT_CURRENT.read_text(encoding="utf-8"))

    def test_real_known_official_tail_accepted_without_recertifying_old_history(self):
        r=m.eur_daily_append_source_gate(self.live['EUR'],'2026-10-23')
        self.assertEqual(r['source_clean_tail_from'],'2026-10-13')
        self.assertEqual(r['weekly_ref'],'2026-10-16')
        self.assertEqual(r['history_status'],m.EUR_LEGACY_STATUS)
        self.assertTrue(r['historical_legacy_basis_quarantined'])
        self.assertFalse(r['historical_first_release_pit_certified'])

    def test_legacy_provenance_cannot_be_silently_upgraded(self):
        src=copy.deepcopy(self.live['EUR'])
        src['history_status']='FULL_ECB_SAME_BASIS_2Y_10Y_RESEARCH_CANDIDATE_ONLY'
        with self.assertRaisesRegex(ValueError,"not approved"):
            m.eur_daily_append_source_gate(src,'2026-10-23')
        src['history_status']=m.EUR_LEGACY_STATUS
        src['history2_quality']='COMPLETE_SOURCE_VERIFIED'
        with self.assertRaisesRegex(ValueError,"quarantine label changed"):
            m.eur_daily_append_source_gate(src,'2026-10-23')

    def test_known_official_2y_or_10y_date_value_tampering_blocks_eur_only(self):
        for key in ['history2','history10']:
            with self.subTest(key=key):
                src=copy.deepcopy(self.live['EUR'])
                idx=src[key]['dates'].index('2026-10-15')
                src[key]['values'][idx]+=0.05
                with self.assertRaisesRegex(ValueError,"clean tail drift"):
                    m.eur_daily_append_source_gate(src,'2026-10-23')

    def test_one_tenor_different_calendar_or_unordered_history_blocks(self):
        for key in ['history2','history10']:
            src=copy.deepcopy(self.live['EUR'])
            src[key]['dates'][-2]='2026-10-19'
            with self.assertRaisesRegex(ValueError,"duplicated or unordered"):
                m.eur_daily_append_source_gate(src,'2026-10-23')

    def test_weekly_reference_must_not_use_legacy_curve_values(self):
        # Next official source observation years ahead must not use a stale
        # 7-calendar-day weekly baseline for an invented change.
        with self.assertRaisesRegex(ValueError,"gap >12"):
            m.eur_daily_append_source_gate(self.live['EUR'],'2026-11-20')
        with self.assertRaisesRegex(ValueError,"new official observation does not advance"):
            m.eur_daily_append_source_gate(self.live['EUR'],'2026-10-22')

    def run_builder(self,currencies,*,tamper_eur=False):
        src=copy.deepcopy(self.live)
        if tamper_eur:
            src['EUR']['history2']['values'][-6]+=0.2
        audit={'status':'PASS','summary':{'updates_available':list(currencies)},
               'currencies':{}}
        for c in currencies:
            d=src[c]
            audit['currencies'][c]={
                'coverage_mode':'LIVE_FETCH',
                'official':{'date':'2026-10-23','2Y':d['2Y']+.01,
                            '10Y':d['10Y']+.01}}
        with tempfile.TemporaryDirectory() as td:
            d=Path(td)
            (d/'rates.json').write_text(json.dumps(src))
            (d/'audit.json').write_text(json.dumps(audit))
            proc=subprocess.run([sys.executable,str(Path(m.__file__)),
                '--current-rates',str(d/'rates.json'),
                '--audit',str(d/'audit.json'),
                '--output',str(d/'out.json')],
                text=True,capture_output=True)
            return proc,json.loads((d/'out.json').read_text()) if (d/'out.json').exists() else None

    def test_safe_official_eur_update_only_appends_does_not_claim_history_repaired(self):
        proc,out=self.run_builder(['EUR'])
        self.assertEqual(proc.returncode,0,proc.stderr)
        receipt=json.loads(proc.stdout)
        self.assertEqual(receipt['status'],'CANDIDATE_READY')
        self.assertEqual(receipt['changed_currencies'],['EUR'])
        self.assertEqual(receipt['quarantined_currencies'],{})
        self.assertEqual(out['EUR']['history_status'],m.EUR_LEGACY_STATUS)
        self.assertEqual(out['EUR']['history2_quality'],m.EUR_LEGACY_QUALITY)
        self.assertEqual(out['EUR']['history2']['dates'][-1],'2026-10-23')
        self.assertEqual(len(out['EUR']['history2']['dates']),
                         len(self.live['EUR']['history2']['dates'])+1)
        self.assertEqual(out['EUR']['weekly2_validation']['start_date'],'2026-10-16')

    def test_eur_bad_history_quarantines_only_eur_and_other_official_ccy_advances(self):
        proc,out=self.run_builder(['EUR','CAD'],tamper_eur=True)
        self.assertEqual(proc.returncode,0,proc.stderr)
        receipt=json.loads(proc.stdout)
        self.assertEqual(receipt['status'],'CANDIDATE_READY')
        self.assertEqual(receipt['changed_currencies'],['CAD'])
        self.assertEqual(receipt['quarantined_currencies']['EUR']['status'],
                         'DAILY_OFFICIAL_NEW_SNAPSHOT_QUARANTINED')
        self.assertTrue(receipt['quarantined_currencies']['EUR']['existing_eur_history_unchanged'])
        self.assertEqual(out['EUR']['date'],self.live['EUR']['date'])
        self.assertEqual(out['CAD']['date'],'2026-10-23')

    def test_eur_only_bad_history_no_updates_preserves_source_aged_metadata_path(self):
        proc,out=self.run_builder(['EUR'],tamper_eur=True)
        self.assertEqual(proc.returncode,0,proc.stderr)
        receipt=json.loads(proc.stdout)
        self.assertEqual(receipt['status'],'NO_UPDATES')
        self.assertEqual(receipt['changed_currencies'],[])
        self.assertIn('EUR',receipt['quarantined_currencies'])
        self.assertEqual(out['EUR']['date'],self.live['EUR']['date'])

    def test_no_updates_leave_full_rates_identical(self):
        proc,out=self.run_builder([])
        self.assertEqual(proc.returncode,0,proc.stderr)
        self.assertEqual(json.loads(proc.stdout)['status'],'NO_UPDATES')
        self.assertEqual(out,self.live)


if __name__=='__main__':
    unittest.main()
