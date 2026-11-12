'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const base=path.resolve(__dirname,'../..');
const read=p=>fs.readFileSync(path.join(base,p),'utf8');
const load=p=>JSON.parse(read(p));
const {analyze,macroAxis,ratesAxis,pricingAxis}=require(path.join(base,'site/fx-quant-v2/next/currency-strength-reading.js'));
const {currencyRanking}=require(path.join(base,'site/fx-quant-v2/next/pair-rankings.js'));
const FX=['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'];
const prices=load('live_data/sections/ECB_G8_PRICE_HISTORY.json');
const m=load('live_data/sections/MACRO_THERMOMETER_DATA.json').currencies;
const r=load('live_data/sections/NATIVE_RATES_DATA.json');
const o=load('site/fx-quant-v2/ois-pricing-snapshot.json').currencies;
const c=load('live_data/sections/V250_COT_CHART_DATA.json');
const now=prices.last_as_of;
const view=analyze({prices,macro:m,rates:r,ois:o,cot:c,now,rankingFn:currencyRanking});
const known=currencyRanking(prices,now,FX);
assert(view.rows.length===8&&known.items.length===8);
assert.deepEqual(view.rows.map(x=>x.ccy),known.items.map(x=>x.ccy),'Only price determines ordinal ranking');
for(const row of view.rows){
 assert(row.reading.label.length>7);
 assert(row.macro.text.includes('Inflazione')||row.macro.text.includes('inflazione'));
 assert(row.rates.text.includes('2Y')||row.rates.text.includes('variazione'));
 assert(row.pricing.text.includes('6M')||row.pricing.text.includes('6 mesi'));
 assert(row.evidenceCount>=0&&row.evidenceCount<=4);
 assert(!/\bundefined\b|\bNaN\b/.test(JSON.stringify(row)));
 assert.equal(row.price.position,view.rows.indexOf(row)+1,'Price-only order');
}
assert(view.limitations.some(x=>x.includes('non è un punteggio')));
// Secondary USD/EUR/CHF quotes and directional NZD proxies can never silently
// promote an official weekly 6M repricing score.
for(const ccy of ['USD','EUR','CHF','NZD']){
 assert.equal(view.rows.find(x=>x.ccy===ccy).pricing.ok,false,ccy+' must remain unverified');
}
assert.equal(view.rows.find(x=>x.ccy==='GBP').pricing.ok,true,'Only verified official 6M moves');
const sample={kind:'FUTURES',quality:'FONTE UFFICIALE',as_of:'2026-11-10',
 horizons:{'6m':{rate:4,change_1w_bp:8,as_of:'2026-11-10'}}};
assert.equal(pricingAxis(sample,'2026-11-12').ok,true);
assert.equal(pricingAxis({...sample,quality:'STIMA INDICATIVA'},'2026-11-12').ok,false);
assert.equal(pricingAxis({...sample,as_of:'2026-11-13'},'2026-11-12').ok,false);
assert.equal(pricingAxis({...sample,horizons:{'6m':{...sample.horizons['6m'],change_1w_bp:null}}},'2026-11-12').ok,false);
assert.equal(pricingAxis(sample,'2026-11-25').ok,false,'Stale expectation history must fail closed');
assert.equal(macroAxis({inflation:{latest_value:2,direction:'SALE',as_of:'2026-03'},
 labour:{latest_value:4,direction:'SCENDE',as_of:'2026-03'}},'2026-11-12').ok,false);
assert.equal(ratesAxis({date:'2026-10-01','2Y':4,weekly2_validation:
 {start_date:'2026-09-24',end_date:'2026-10-01',change_bp:25,source:'Official history'}},'2026-11-12').ok,false);
assert.equal(ratesAxis({date:'2026-11-12','2Y':4,weekly2_validation:
 {start_date:'2026-11-05',end_date:'2026-11-12',change_bp:25,source:'Official history'}},'2026-11-11').ok,false);
const missing=analyze({prices:{},macro:{},rates:{},ois:{},cot:{},now,rankingFn:currencyRanking});
assert.equal(missing.rows.length,8);
assert(missing.rows.every(x=>!x.price.ok&&!x.macro.ok&&!x.rates.ok&&!x.pricing.ok&&x.evidenceCount===0));
const html=read('site/fx-quant-v2/next/index.html');
assert(html.includes('currency-strength-reading.js?v=1')&&html.includes('currency-studio.js?v=15'));
assert(html.indexOf('currency-strength-reading.js')<html.indexOf('currency-studio.js'));
const studio=read('site/fx-quant-v2/next/currency-studio.js');
for(const label of ['strengthBoard()+strengthFocus()','CHI SI MUOVE E PERCHÉ','strength-pair-fold','strength-method-fold']){
 assert(studio.includes(label),'G8 Country Desk must retain '+label);
}
console.log('G8_MACRO_RATES_PRICING_PRICE_V1_PASS: 8 currencies, 20-day price rank only, 6M quality filter, stale/missing and no lookahead');
