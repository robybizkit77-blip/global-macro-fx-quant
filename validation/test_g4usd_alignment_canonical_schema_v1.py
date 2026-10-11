#!/usr/bin/env python3
import csv, importlib.util, tempfile
from pathlib import Path

ENGINE=Path(__file__).with_name('g4usd_front_end_macro_cb_alignment_v1.py')
spec=importlib.util.spec_from_file_location('eng',ENGINE)
eng=importlib.util.module_from_spec(spec); spec.loader.exec_module(eng)


def write_rows(path,rows,fields=('reference_period','release_date','value','availability_status')):
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)


def main():
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/'ok.csv'
        write_rows(p,[
          {'reference_period':'2020-01','release_date':'2020-02-10','value':'2.0','availability_status':'AVAILABLE_STRICT_PIT'},
          {'reference_period':'2020-02','release_date':'2020-03-10','value':'2.2','availability_status':'AVAILABLE_STRICT_PIT'},
          {'reference_period':'2020-03','release_date':'','value':'','availability_status':'UNAVAILABLE_OFFICIAL_NOT_PUBLISHED'},
          {'reference_period':'2020-04','release_date':'2020-05-10','value':'2.5','availability_status':'AVAILABLE_STRICT_PIT'},
        ])
        rows=eng.load_macro(p)
        assert rows==[('2020-02-10',2.0),('2020-03-10',2.2),('2020-05-10',2.5)]
        assert eng.change_pair(rows,'2020-04-01')==(0.2,2.2,2.0) or abs(eng.change_pair(rows,'2020-04-01')[0]-0.2)<1e-12
        assert eng.change_pair(rows,'2020-05-01')[1:]==(2.2,2.0)
        assert eng.change_pair(rows,'2020-06-01')[1:]==(2.5,2.2)
        assert eng.classify(0.1,0.2,0.3)=='ALIGNED'
        assert eng.classify(0.1,0.2,-0.3)=='MIXED'
        assert eng.classify(0.1,-0.2,-0.3)=='CONTRADICTORY'
        assert eng.classify(0.0,0.2,0.3)=='MIXED'

        bad=Path(td)/'bad.csv'
        write_rows(bad,[{'reference_period':'2020-01','release_date':'2020-02-10','value':'2.0','availability_status':'AVAILABLE_STRICT_PIT'}],fields=('reference_period','release_date','value','availability_status','extra'))
        try:
            eng.load_macro(bad)
            raise AssertionError('non-canonical schema was accepted')
        except ValueError as e:
            assert 'non-canonical macro schema' in str(e)

        bad_gap=Path(td)/'bad-gap.csv'
        write_rows(bad_gap,[{'reference_period':'2020-03','release_date':'2020-04-10','value':'2.3','availability_status':'UNAVAILABLE_OFFICIAL_NOT_PUBLISHED'}])
        try:
            eng.load_macro(bad_gap)
            raise AssertionError('official gap with data was accepted')
        except ValueError as e:
            assert 'official-unavailable' in str(e)

    print('G4USD_ALIGNMENT_CANONICAL_SCHEMA_PREFLIGHT_PASS')

if __name__=='__main__': main()
