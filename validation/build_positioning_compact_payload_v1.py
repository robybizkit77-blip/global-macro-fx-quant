import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'live_data' / 'sections' / 'D.json'
OUT = ROOT / 'validation' / 'POSITIONING_COMPACT_PAYLOAD_V1_2026-10-07.json'

CURRENCIES = ['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']

def classify_pct(p):
    if p is None:
        return 'WITHHELD'
    if p >= 80:
        return 'EXTREME_LONG'
    if p <= 20:
        return 'EXTREME_SHORT'
    if p >= 60:
        return 'LONG_BIAS'
    if p <= 40:
        return 'SHORT_BIAS'
    return 'NEUTRAL_MID'

src = json.loads(SRC.read_text())
macro = src.get('macro', {})

currencies = {}
for c in CURRENCIES:
    d = macro.get(c, {})
    pct = d.get('cot_pct')
    currencies[c] = {
        'currency': c,
        'percentile_2y': pct,
        'positioning_read': classify_pct(pct),
        'delta_net_1w': None,
        'net_oi_pct': None,
        'flow_status': 'WITHHELD_SOURCE_NOT_AVAILABLE',
        'imbalance_alert': None,
        'note_it': 'Contesto positioning limitato al percentile COT già presente nel runtime. Delta Net 1W e Net/OI restano withheld finché il dataset CFTC canonico non è collegato.'
    }

out = {
    'schema': 'GMFQ_POSITIONING_COMPACT_PAYLOAD_V1',
    'status': 'RESEARCH_ONLY_PARTIAL_SOURCE_NOT_PROMOTED',
    'purpose': 'Compact positioning context from currently available runtime COT percentile only. No fabricated flow or Net/OI fields.',
    'source': {
        'runtime_file': 'live_data/sections/D.json',
        'available_field': 'macro.<CCY>.cot_pct',
        'canonical_full_cot_dataset_connected': False
    },
    'currencies': currencies,
    'guards': {
        'fabricates_missing_flow': False,
        'fabricates_missing_net_oi': False,
        'changes_engine_rules': False,
        'changes_live_data': False,
        'production_promotion': False,
        'trade_signal': False
    }
}
OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False) + '\n')
print(json.dumps({'count': len(currencies), 'reads': {c:v['positioning_read'] for c,v in currencies.items()}}, ensure_ascii=False))
