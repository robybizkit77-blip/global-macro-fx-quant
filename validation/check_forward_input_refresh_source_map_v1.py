#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MAP=ROOT/'validation/FORWARD_INPUT_REFRESH_SOURCE_MAP_V1_2026-10-12.json'
REG=ROOT/'validation/macro/MACRO_SOURCE_REGISTRY_2026-10-08.json'


def main()->int:
    m=json.loads(MAP.read_text())
    r=json.loads(REG.read_text())
    assert m['schema']=='GMFQ_FORWARD_INPUT_REFRESH_SOURCE_MAP_V1'
    assert m['scope']['required_macro_streams']==10
    streams=m['streams']
    assert len(streams)==10
    keys=[x['key'] for x in streams]
    assert len(keys)==len(set(keys))
    expected={f'{c}.{d}' for c in ['USD','EUR','JPY','CAD','AUD'] for d in ['inflation','labour']}
    assert set(keys)==expected,(set(keys),expected)
    for x in streams:
        key=x['key']; rr=r['series'][key]
        assert rr['source_adapter_status']=='READY',(key,rr.get('source_adapter_status'))
        adapter=rr.get('adapter') or rr.get('certified_adapter',{}).get('adapter')
        workflow=rr.get('workflow') or rr.get('certified_adapter',{}).get('workflow') or rr.get('live_certification',{}).get('workflow')
        assert adapter==x['adapter'],(key,adapter,x['adapter'])
        assert workflow==x['workflow'],(key,workflow,x['workflow'])
        hist=rr.get('historical_replay_evidence',{})
        registry_macro_id=hist.get('macro_series_id')
        if registry_macro_id:
            assert registry_macro_id==x['macro_series_id'],(key,registry_macro_id,x['macro_series_id'])
        assert (ROOT/x['adapter']).is_file(),(key,x['adapter'])
        assert (ROOT/x['workflow']).is_file(),(key,x['workflow'])
    pit=ROOT/m['pit_refresh_entrypoint']
    assert pit.is_file(),m['pit_refresh_entrypoint']
    rules=m['rules']
    assert rules['source_generation_read_only'] is True
    assert rules['single_series_pit_refresh_required'] is True
    assert rules['batch_direct_write_forbidden'] is True
    assert rules['partial_refresh_cannot_advance_shared_boundary'] is True
    assert rules['automatic_publication'] is False
    assert rules['main_write'] is False and rules['gh_pages_write'] is False
    print(json.dumps({'status':'PASS','streams':10,'keys':sorted(keys),'pit_refresh_entrypoint':m['pit_refresh_entrypoint']},indent=2))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
