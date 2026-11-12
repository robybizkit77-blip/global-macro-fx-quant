'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'../..');
const read=p=>fs.readFileSync(path.join(root,p),'utf8');
const load=p=>JSON.parse(read(p));
const dir='site/fx-quant-v2/next/';
const ctx={window:{}};
for(const file of ['pair-rankings.js','currency-data-fallback.js','currency-strength-reading.js','g8-growth-shadow.js','currency-studio.js'])
  vm.runInNewContext(read(dir+file),ctx,{filename:file,timeout:5000});
const F=ctx.window.FXQuantGrowthShadow, C=ctx.window.FXQuantCurrencies,
 B=ctx.window.FXQuantCurrencyStrength, R=ctx.window.FXQuantPairRankings;
const FX=['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'];
const data={
macroSeries:load('live_data/sections/MACRO_SERIES.json'),
currencyPrices:load('live_data/sections/ECB_G8_PRICE_HISTORY.json'),
rates:load('live_data/sections/NATIVE_RATES_DATA.json'),
macro:load('live_data/sections/MACRO_THERMOMETER_DATA.json'),
cb:load('live_data/sections/NATIVE_CB_DATA.json'),
cbEstimated:load('live_data/sections/CB_PRICING_ESTIMATED.json'),
ois:load('site/fx-quant-v2/ois-pricing-snapshot.json'),
cotHistory:load('live_data/sections/V250_COT_CHART_DATA.json'),
pairs:load('live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json')
};
const now='2026-11-12',model=F.analyze({macroSeries:data.macroSeries,now});
assert.equal(model.status,'RESEARCH_ONLY_NOT_PIT');
assert.equal(Object.keys(model.currencies).length,8);
assert.equal(model.qualified.join(','),'USD','Only real-consumption US selected series clears preset rules on current snapshot');
const usd=model.currencies.USD;
assert.equal(usd.seriesId,'US_PCEC96_history_value');
assert.equal(usd.nextObservationPeriod,'2026-10');
assert.equal(usd.forecast.unit,'%');
assert(usd.forecast.nextChange>0&&usd.forecast.nextChange<1);
assert(usd.backtest.testObservations>=24);
assert(usd.backtest.improvementPct>=10);
assert(usd.backtest.firstHalfImprovementPct>=0);
assert(usd.backtest.secondHalfImprovementPct>=0);
assert(usd.backtest.directionalAgreementPct>=60);
assert(usd.quality==='RETROSPECTIVE_NOT_POINT_IN_TIME');
assert(usd.restrictions.some(x=>x.includes('NON point-in-time')));
for(const c of FX.filter(x=>x!=='USD')){
  assert.equal(model.currencies[c].candidate,false,'No false model edge '+c);
  assert.equal(model.currencies[c].forecast,null,'Never show numerical estimate for failed gate '+c);
}
const altered=JSON.parse(JSON.stringify(data.macroSeries));
const sample=altered.USD.find(x=>x.id===usd.seriesId);
sample.dates.push('2027-01-01');
sample.values.push(99999999999);
const future=F.analyze({macroSeries:altered,now});
assert.equal(future.currencies.USD.forecast.nextChange,usd.forecast.nextChange,
  'A future release must never affect the estimate or backtest');
assert.equal(F.analyze({macroSeries:data.macroSeries,now:'2027-03-12'}).currencies.USD.forecast,null,
  'Outdated source is not a current estimate');
const corrupt=JSON.parse(JSON.stringify(data.macroSeries));
corrupt.USD.find(x=>x.id===usd.seriesId).dates.push('2026-09-01');
corrupt.USD.find(x=>x.id===usd.seriesId).values.push(16000);
assert.equal(F.analyze({macroSeries:corrupt,now}).currencies.USD.status,'UNAVAILABLE',
  'Duplicate dates must fail closed');
const original=B.analyze({prices:data.currencyPrices,macro:data.macro.currencies,
 rates:data.rates,ois:data.ois.currencies,cot:data.cotHistory,now,rankingFn:R.currencyRanking});
const fmt=(x,n=2)=>typeof x==='number'&&Number.isFinite(x)?x.toLocaleString('it-IT',{minimumFractionDigits:n,maximumFractionDigits:n}):'—';
const sign=(x,n=2,unit='')=>typeof x==='number'&&Number.isFinite(x)?(x>0?'+':x<0?'−':'')+fmt(Math.abs(x),n)+unit:'—';
const esc=x=>String(x??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const flags=Object.fromEntries(FX.map(x=>[x,x]));
const params={get:key=>data[key],FX,FLAGS:flags,NAMES:flags,esc,fmt,sign,
 pageHero:()=>'<header>G8</header>',date:x=>x,finite:x=>typeof x==='number'&&Number.isFinite(x),
 validDay:x=>/^\d{4}-\d\d-\d\d$/.test(x||''),dayNow:()=>now};
for(const ccy of FX){
  const html=C.render({...params,state:{ccy,csOther:ccy==='EUR'?'USD':'EUR',csReturnWindow:20}});
  assert(html.includes('class="strength-shadow-fold"'),'Optional disclosure exists '+ccy);
  assert(html.includes('NON POINT-IN-TIME'),'Shadow never masquerades as validated PIT '+ccy);
  assert(html.includes('nessun effetto sul ranking FX'),'Shadow cannot imply trade edge '+ccy);
  if(ccy==='USD')assert(html.includes('Proiezione della <strong>prossima variazione della serie</strong>'));
  else assert(html.includes('La previsione resta <strong>non pubblicata</strong>'));
  assert.equal((html.match(/class="strength-row /g)||[]).length,8,'Price order unchanged '+ccy);
  assert(!/\bNaN\b|\bundefined\b|\[object Object\]/.test(html),'No broken G8 output '+ccy);
}
const next=B.analyze({prices:data.currencyPrices,macro:data.macro.currencies,
 rates:data.rates,ois:data.ois.currencies,cot:data.cotHistory,now,rankingFn:R.currencyRanking});
assert.deepEqual(next.rows.map(x=>x.ccy),original.rows.map(x=>x.ccy));
assert.deepEqual(next.rows.map(x=>x.evidenceCount),original.rows.map(x=>x.evidenceCount));
const html=read(dir+'index.html');
assert(html.indexOf('g8-growth-shadow.js?v=1')<html.indexOf('currency-studio.js?v=13'));
assert(html.includes('currency-studio.css?v=7'));
console.log('G8_SHADOW_V1_PASS: US-only research candidate, eight benchmark evaluations, stale/future/PIT guards, unchanged FX rankings');
