#!/usr/bin/env python3
"""Real-data and tampered-fixture regression for source-dated Market Pulse V25."""
from datetime import date
from pathlib import Path
import copy, json, sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'validation'))
import build_news_pulse_operational_v1 as pulse

TODAY=date(2026,11,10)
def load(path):
    return json.loads((ROOT/path).read_text(encoding='utf-8'))

# Immutable observed 10 November sample: regression must not break when live sources roll.
snapshot=load('validation/fixtures/market_pulse_v25_observed_2026_11_10.json')
fx=snapshot['fx']
rates=snapshot['rates']
risk=snapshot['cross_asset']
fx_items=pulse.fx_fixing_items(fx,TODAY)
rate_items=pulse.government_curve_items(rates,TODAY)
cross_items=pulse.cross_asset_items(risk,TODAY)
assert len(fx_items)==3,('FX cross fixing coverage',fx_items)
assert len(rate_items)==3,('Dated US/EUR/JPY 2Y and 10Y',rate_items)
assert len(cross_items)==5,('S&P/Nasdaq/VIX/IG/HY',cross_items)
assert set(x['category'] for x in fx_items)=={'MARKET_FX_ECB_FIXING'}
assert set(x['category'] for x in rate_items)=={'MARKET_GOVERNMENT_RATES'}
assert {x['category'] for x in cross_items}=={
    'MARKET_EQUITY_CLOSE','MARKET_VOLATILITY_CLOSE','MARKET_CREDIT_OAS'}
assert {x['as_of'] for x in fx_items+rate_items}=={'2026-11-09'}
assert {x['as_of'] for x in cross_items}=={'2026-11-05','2026-11-06','2026-11-09'}
assert all(x.get('source') and x.get('quality') and x.get('_date') for x in fx_items+rate_items+cross_items)
assert all('non prova' in x['detail'] or 'non è' in x['detail'] for x in fx_items+rate_items+cross_items)
assert next(x for x in cross_items if x['category']=='MARKET_VOLATILITY_CLOSE')['title'].find('-5.72 punti')>=0
assert next(x for x in cross_items if x['title'].startswith('Credito HY'))['title'].find('-6.0 pb')>=0
assert next(x for x in rate_items if x['ccy']=='USD')['title'].find('+5.0 pb')>=0
# ECB base is 1 EUR: USDJPY = JPY per USD, AUDCAD = CAD per AUD.
prior,latest=fx['rows'][-2:]
actual={x['pair']:x for x in fx_items}
for name,base,quote in [('EURUSD','EUR','USD'),('USDJPY','USD','JPY'),('AUDCAD','AUD','CAD')]:
    old=prior[quote]/prior[base]
    new=latest[quote]/latest[base]
    delta=(new/old-1)*100
    assert f'{delta:+.2f}%' in actual[name]['title'],name
# Old or future sessions cannot masquerade as fresh verified market news.
assert not pulse.fx_fixing_items(fx,date(2026,11,6))
assert not pulse.government_curve_items(rates,date(2026,11,6))
assert not pulse.cross_asset_items(risk,date(2026,10,27))
assert not pulse.cross_asset_items(risk,date(2026,11,21))
tampered=copy.deepcopy(risk)
tampered['streams']['VIX']['quality']='WITHHELD'
assert len(pulse.cross_asset_items(tampered,TODAY))==4
tampered=copy.deepcopy(risk)
tampered['streams']['VIX']['history'][-1][1]=999.
assert len(pulse.cross_asset_items(tampered,TODAY))==4
tampered=copy.deepcopy(fx)
tampered['rows'][-1]['AUD']=None
assert len(pulse.fx_fixing_items(tampered,TODAY))==2
tampered=copy.deepcopy(rates)
tampered['USD']['history2']['values'][-1]=99.
assert len(pulse.government_curve_items(tampered,TODAY))==2
# Optional missing lanes must fail closed rather than write synthetic fallbacks.
assert pulse.load_market_input(ROOT/'does-not-exist-market-input-v25.json')=={}
# No commodities, geopolitics, macro-release surprise unless sourced separately.
assert not any('COMMODITY' in x['category'] or 'GEOPOLITIC' in x['category'] for x in fx_items+rate_items+cross_items)
# Source snapshots move independently. Today's coverage is reported, never faked and
# never required to stay at the frozen sample's exact dates or counts.
from datetime import datetime
from zoneinfo import ZoneInfo
current_day=datetime.now(ZoneInfo('Europe/Rome')).date()
fx_live=pulse.fx_fixing_items(load('live_data/sections/ECB_G8_PRICE_HISTORY.json'),current_day)
rates_live=pulse.government_curve_items(load('live_data/sections/NATIVE_RATES_DATA.json'),current_day)
cross_live=pulse.cross_asset_items(load('site/fx-quant-v2/cross-asset-live-data.json'),current_day)
for observation in fx_live+rates_live+cross_live:
    assert observation['_date']<=current_day and observation.get('source') and observation.get('quality')
print('MARKET_PULSE_V25_REAL_SOURCE_PASS: frozen FX 3/3, government curves 3/3, cross-asset 5/5; as-of, missing, stale, future, unit and ECB quote guards; current source coverage FX={} rates={} cross={}.'.format(len(fx_live),len(rates_live),len(cross_live)))
