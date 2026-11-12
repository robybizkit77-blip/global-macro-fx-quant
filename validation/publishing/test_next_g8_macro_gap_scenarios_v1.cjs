'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'../..');
const read=p=>fs.readFileSync(path.join(root,p),'utf8');
const load=p=>JSON.parse(read(p));
const base='site/fx-quant-v2/next/';
const window={},ctx={window};
for(const name of ['pair-rankings.js','currency-data-fallback.js',
 'g8-growth-shadow.js','g8-macro-gap-scenarios.js','g8-rates-shadow.js',
 'currency-strength-reading.js','currency-studio.js'])
 vm.runInNewContext(read(base+name),ctx,{filename:name,timeout:5000});
const M=window.FXQuantG8MacroGap,C=window.FXQuantCurrencies;
const currencies=['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'];
const macroSeries=load('live_data/sections/MACRO_SERIES.json'),now='2026-11-12';
const x=M.analyze({macroSeries,now});
assert.equal(x.schema,'GMFQ_G8_MACRO_GAP_SCENARIOS_V1');
assert.equal(x.readyCount,8);
assert.deepEqual(Array.from(x.modelCandidates),['USD','CAD'],'Only USD & CAD qualify under fixed same-horizon rules');
const periods={USD:['2026-09','2026-10',1],EUR:['2026-07','2026-10',3],
 GBP:['2026-08','2026-10',2],JPY:['2026-07','2026-10',3],
 CHF:['2026-07','2026-10',3],CAD:['2026-06','2026-10',4],
 AUD:['2026-06','2026-09',1],NZD:['2026-06','2026-09',1]};
for(const c of currencies){
 const z=x.currencies[c],p=periods[c];
 assert.equal(z.sourcePeriod,p[0],c+' correct observed reference period');
 assert.equal(z.targetPeriod,p[1],c+' completed target period, not release day');
 assert.equal(z.horizonSteps,p[2],c+' same horizon used in OOS test');
 assert.equal(z.eligibleForCore,false,c+' never new observed/core macro');
 assert.equal(z.eligibleForTradeBacktests,false,c+' no PIT FX backtest');
 assert.equal(z.quality,'REVISED_HISTORY_NOT_POINT_IN_TIME');
 assert(z.backtest.points>=16,c+' enough pseudo-OOS examples');
 assert(Number.isFinite(z.scenarioValue)&&Number.isFinite(z.deltaFromObserved));
 assert(z.rangeLow<=z.scenarioValue&&z.scenarioValue<=z.rangeHigh);
 assert.match(z.rangeKind,/NOT_CONFIDENCE_INTERVAL/);
 assert(z.source.length>4);
 if(['USD','CAD'].includes(c)){
  assert.equal(z.status,'MODELLO_RETROSPETTIVO_PROMETTENTE');
  assert(z.backtest.improvementPct>=10);
  assert(z.backtest.firstHalfGainPct>=0&&z.backtest.secondHalfGainPct>=0);
  assert(z.backtest.directionHitPct>=60);
 }else assert.equal(z.status,'SCENARIO_NON_VALIDATO',c+' must not claim predictive edge');
}
assert(x.currencies.USD.scenarioValue>16977.6&&x.currencies.USD.scenarioValue<17100);
assert(x.currencies.CAD.scenarioValue>2369309&&x.currencies.CAD.scenarioValue<2400000);
assert.equal(x.currencies.AUD.reportedRate,true);
assert.equal(x.currencies.NZD.reportedRate,true);
assert.equal(x.currencies.NZD.deltaUnit,'punti percentuali');
assert.notEqual(x.currencies.NZD.deltaUnit,x.currencies.USD.deltaUnit);
const altered=structuredClone(macroSeries);
altered.USD.find(s=>s.id==='US_PCEC96_history_value').dates.push('2027-01-01');
altered.USD.find(s=>s.id==='US_PCEC96_history_value').values.push(1e13);
assert.equal(M.analyze({macroSeries:altered,now}).currencies.USD.scenarioValue,
 x.currencies.USD.scenarioValue,'Future observation cannot leak into model');
const corrupted=structuredClone(macroSeries);
const us=corrupted.USD.find(s=>s.id==='US_PCEC96_history_value');
us.dates.push(us.dates.at(-1));us.values.push(us.values.at(-1));
assert.equal(M.evaluate(corrupted,'USD',now).status,'NON_DISPONIBILE','duplicate historical period rejected');
const missing=structuredClone(macroSeries);
missing.CAD.find(s=>s.id==='CA_REAL_GDP_M_history_value').source_file='';
assert.equal(M.evaluate(missing,'CAD',now).status,'NON_DISPONIBILE','unproven source rejected');
assert.equal(M.analyze({macroSeries,now:'2027-04-12'}).currencies.CAD.status,'NON_DISPONIBILE','too many missing months are not fabricated');
assert.equal(M.evaluate(macroSeries,'USD','2026-11-00').status,'NON_DISPONIBILE');
const data={macroSeries,currencyPrices:load('live_data/sections/ECB_G8_PRICE_HISTORY.json'),
 rates:load('live_data/sections/NATIVE_RATES_DATA.json'),
 macro:load('live_data/sections/MACRO_THERMOMETER_DATA.json'),
 cb:load('live_data/sections/NATIVE_CB_DATA.json'),
 cbEstimated:load('live_data/sections/CB_PRICING_ESTIMATED.json'),
 ois:load('site/fx-quant-v2/ois-pricing-snapshot.json'),
 cotHistory:load('live_data/sections/V250_COT_CHART_DATA.json'),
 pairs:load('live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json'),
 chfResearch:load('site/fx-quant-v2/chf-snb-paired-history.json'),
 nzdPostroll:load('site/fx-quant-v2/nzd-b2-postroll-web-research.json'),
 chfSpot:load('live_data/sections/CHF_SNB_10Y_SPOT_CONTEXT.json'),
 nzdDirectionalProxy:load('live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json')};
const fmt=(v,n=2)=>typeof v==='number'&&Number.isFinite(v)?
 v.toLocaleString('it-IT',{minimumFractionDigits:n,maximumFractionDigits:n}):'—';
const sign=(v,n=2,u='')=>typeof v==='number'&&Number.isFinite(v)?
 (v>0?'+':v<0?'−':'')+fmt(Math.abs(v),n)+u:'—';
const esc=v=>String(v??'').replace(/&/g,'&amp;').replace(/</g,'&lt;')
 .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const flags=Object.fromEntries(currencies.map(c=>[c,c]));
const params={get:key=>data[key],FX:currencies,FLAGS:flags,NAMES:flags,
 pageHero:()=>'<header>G8</header>',date:x=>x,esc,fmt,sign,
 finite:v=>typeof v==='number'&&Number.isFinite(v),
 validDay:v=>/^\d{4}-\d\d-\d\d$/.test(v||''),dayNow:()=>now};
const positions=[];
for(const c of currencies){
 const html=C.render({...params,state:{ccy:c,csOther:c==='EUR'?'USD':'EUR',csReturnWindow:20}});
 assert(html.includes('SCENARIO '+x.currencies[c].targetPeriod),'G8 must show '+c+' scenario');
 assert(html.includes('Scenario economico per '+x.currencies[c].targetPeriod),'G8 dossier must explain '+c);
 assert(html.includes('SCENARIO MACRO · NON POINT-IN-TIME'),'Source quality visible '+c);
 assert(html.includes('nessun effetto sul ranking FX'),'No trade effect '+c);
 assert.equal((html.match(/class="strength-row /g)||[]).length,8,'8 countries unchanged');
 assert(!/\bNaN\b|\bundefined\b|\[object Object\]/.test(html),'G8 HTML remains valid');
 positions.push(html.match(/class="strength-name"><b>(.*?)<\/b><strong>/)?.[1]);
}
assert.equal(new Set(positions).size,1,'Each selected country sees the same price-sorted board');
const idx=read(base+'index.html');
assert(idx.includes('g8-macro-gap-scenarios.js?v=1'));
assert(idx.indexOf('g8-macro-gap-scenarios.js')<idx.indexOf('currency-studio.js'));
assert(idx.includes('currency-studio.js?v=10'));
console.log('G8_MACRO_GAP_SCENARIOS_V1_PASS: 8/8 dated scenarios, USD/CAD only qualified, pseudo-OOS & source/vintage guards, unchanged FX ranking');
