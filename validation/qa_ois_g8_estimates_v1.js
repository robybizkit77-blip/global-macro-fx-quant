/* Deterministic fixture/guard validation for the view-only G8 estimates. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const modulePath=path.join(root,'site/control-room-preview/ois-pricing-estimates-v1.js');
const {matrix,view,fresh}=require(modulePath);
const ois=JSON.parse(fs.readFileSync(path.join(root,'live_data/sections/OIS_OPERATIONAL_VIEW.json'),'utf8'));
const proxy=JSON.parse(fs.readFileSync(path.join(root,'live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json'),'utf8'));
const v=matrix(ois,proxy,'2026-10-20'),m=Object.fromEntries(v.map(r=>[r.ccy,r]));
assert.equal(v.length,8);
for(const code of ['GBP','JPY','CAD','AUD'])assert.equal(m[code].tier,'OFFICIAL',code);
for(const code of ['USD','CHF'])assert.equal(m[code].tier,'PROXY',code);
assert.equal(m.EUR.tier,'MIXED');
assert.equal(m.EUR.points['3m'].date,'2026-10-16');
assert.equal(m.EUR.points['12m'].date,'2026-10-19');
assert.equal(m.NZD.tier,'SCENARIO');
assert.equal(m.NZD.points['3m'].value,2.99);
assert.equal(m.NZD.points['6m'].value,3.33);
assert.equal(m.NZD.points['12m'].value,3.74);
assert.deepEqual(m.NZD.points['6m'].range,[3.08,3.58]);
for(const row of v){
 assert.equal(row.allow_official_promotion,false);
 assert.equal(row.allow_repricing,false);
 assert.equal(row.bias_effect,'NONE');
 assert.equal(row.pair_effect,'NONE');
 assert.equal(row.backtest_official,false);
}
assert.equal(m.GBP.official_ois,true);
for(const code of ['USD','EUR','CHF','NZD'])assert.equal(m[code].official_ois,false);
assert.equal(fresh('2026-10-19','2026-10-20'),true);
assert.equal(fresh('2026-10-22','2026-10-20'),false);
assert.equal(fresh('2026-10-10','2026-10-20'),false);
assert.equal(fresh('not-a-date','2026-10-20'),false);
// No auto-refresh of stale research levels, and no interpolation of missing official tenors.
const stale=matrix(ois,proxy,'2026-11-12');
assert.equal(stale.filter(x=>x.tier!=='WITHHELD').length,0);
const noFuture=structuredClone(ois);
noFuture.currencies.EUR.secondary_quote_context.cross_date_join_allowed=true;
assert.equal(matrix(noFuture,proxy,'2026-10-20').find(r=>r.ccy==='EUR').tier,'WITHHELD');
const noQuote=structuredClone(ois);
noQuote.currencies.CHF.horizons['6m'].quote_timestamp_verified=false;
assert.equal(matrix(noQuote,proxy,'2026-10-20').find(r=>r.ccy==='CHF').points['6m'],undefined);
const noBB=structuredClone(proxy);
noBB.governance.substitutes_for_ois_level=true;
assert.equal(matrix(ois,noBB,'2026-10-20').find(r=>r.ccy==='NZD').tier,'WITHHELD');
const escaped=view(matrix(ois,proxy,'2026-10-20'));
assert(escaped.includes('data-ccy="NZD"'));
assert(escaped.includes('DATE NON SINCRONIZZATE'));
assert(escaped.includes('non intervallo statistico'));
assert(!escaped.includes('GREEN_OFFICIAL'));
// The loader and publisher must explicitly list the addon, never a legacy page.
const loader=fs.readFileSync(path.join(root,'site/control-room-preview/index.html'),'utf8');
const pub=fs.readFileSync(path.join(root,'.github/workflows/publish-control-room-home-v10.yml'),'utf8');
assert(loader.includes('ois-pricing-estimates-v1.js'));
assert(pub.includes('cp site/control-room-preview/ois-pricing-estimates-v1.js'));
assert(!/\\bcron:/.test(pub));
console.log('GMFQ_OIS_G8_RESEARCH_MATRIX_PASS 8/8 grouped official/proxy/mixed/scenario, zero core effect');
