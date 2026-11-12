'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'../..');
const read=p=>fs.readFileSync(path.join(root,p),'utf8');
const load=p=>JSON.parse(read(p));
const dir='site/fx-quant-v2/next/';
const ctx={window:{}};
for(const name of ['pair-rankings.js','currency-data-fallback.js',
 'g8-growth-shadow.js','g8-macro-gap-scenarios.js','g8-inflation-labour-shadow.js',
 'g8-rates-shadow.js','currency-strength-reading.js','currency-studio.js'])
 vm.runInNewContext(read(dir+name),ctx,{filename:name,timeout:5000});
const F=ctx.window.FXQuantInflationLabourShadow;
const C=ctx.window.FXQuantCurrencies,Strength=ctx.window.FXQuantCurrencyStrength,
 Ranking=ctx.window.FXQuantPairRankings;
const FX=['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'],now='2026-11-12';
const data={
 macroSeries:load('live_data/sections/MACRO_SERIES.json'),
 currencyPrices:load('live_data/sections/ECB_G8_PRICE_HISTORY.json'),
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
 nzdDirectionalProxy:load('live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json')
};
const m=F.analyze({macroSeries:data.macroSeries,now});
assert.equal(m.schema,'GMFQ_FXV2_G8_INFLATION_LABOUR_SHADOW_V1');
assert.equal(m.estimates,10,'Ten historical repo gaps must be openly estimated');
assert.equal(m.alreadyObserved,6,'Six periods already observed and must never be estimated');
assert.deepEqual(Array.from(m.retrospectiveCandidates),['CHF_labour'],
 'Only the CHF unemployment drift clears fixed predeclared same-horizon criteria');
const observed=new Set(['USD_labour','EUR_inflation','CAD_labour',
 'AUD_inflation','NZD_inflation','NZD_labour']);
const targets={USD:{inflation:'2026-10',labour:'2026-10'},
 EUR:{inflation:'2026-10',labour:'2026-10'},GBP:{inflation:'2026-10',labour:'2026-10'},
 JPY:{inflation:'2026-10',labour:'2026-10'},CHF:{inflation:'2026-10',labour:'2026-10'},
 AUD:{inflation:'2026-09',labour:'2026-10'},NZD:{inflation:'2026-09',labour:'2026-09'},
 CAD:{inflation:'2026-10',labour:'2026-10'}};
for(const c of FX){
 for(const axis of ['inflation','labour']){
  const x=m.currencies[c][axis],key=c+'_'+axis;
  assert.equal(x.ccy,c);assert.equal(x.axis,axis);
  assert.equal(x.targetPeriod,targets[c][axis],key+' target economic month/quarter');
  assert.equal(x.eligibleForCore,false);
  assert.equal(x.eligibleForTrading,false);
  if(observed.has(key)){
   assert.equal(x.status,'GIA_OSSERVATO',key);
   assert.equal(x.forecast,null,'Do not overwrite existing observation: '+key);
   assert.equal(x.backtest,null,'No test needed for an already-observed period');
  }else{
   assert(Number.isFinite(x.forecast),key+' must have an explicit numeric scenario');
   assert(x.horizonSteps>=1&&x.horizonSteps<=3,key+' bounded missing horizon');
   assert(x.backtest.count>=24,key+' historical pseudo-OOS examples');
   assert(x.uncertainty.low<=x.forecast&&x.forecast<=x.uncertainty.high);
   assert.match(x.uncertainty.interpretation,/NOT_CONFIDENCE_INTERVAL/);
   assert.equal(x.skillValidatedPIT,false);
   if(key==='CHF_labour'){
    assert.equal(x.status,'MODELLO_RETROSPETTIVO_PROMETTENTE');
    assert(x.backtest.gainPct>=10&&x.backtest.firstHalfGainPct>=0&&
      x.backtest.secondHalfGainPct>=0&&x.backtest.directionHitPct>=60);
   }else{
    assert.equal(x.status,'SCENARIO_BASELINE_NON_VALIDATO',key);
    assert.equal(x.forecast,x.observedValue,key+' fallback cannot claim trend skill');
    assert(Number.isFinite(x.driftScenario),key+' trend is only an alternate');
   }
  }
 }
}
assert.equal(m.currencies.USD.inflation.sourceQuality,'CPI_INDEX_YOY_DERIVED_FROM_HISTORICAL_INDEX');
assert(m.currencies.USD.inflation.sourceQualityAudit.missingHistoricalPeriods>=1,
 'Missing October 2025 CPI source month must be documented, not interpolated');
assert.equal(m.currencies.USD.inflation.sourceQualityAudit.imputedHistoricalMonths,0);
assert(m.currencies.USD.labour.sourceQualityAudit.identicalMonthRowsDeduplicated>=4,
 'Same-month duplicate US unemployment observations are only exact-value deduplicated');
assert(m.currencies.USD.inflation.observedValue>3.5&&m.currencies.USD.inflation.observedValue<4.5);
assert(m.currencies.CHF.labour.forecast>3&&m.currencies.CHF.labour.forecast<3.4);
assert.equal(m.currencies.GBP.labour.horizonSteps,2);
assert.equal(m.currencies.NZD.inflation.frequency,'Q');
const check=(series,c,axis,asof=now)=>F.evaluate(series,c,axis,asof);
const bad=structuredClone(data.macroSeries);
bad.CHF.find(x=>x.id==='CH_UNEMP_RATE_history_value').source_file='unverified.csv';
assert.equal(check(bad,'CHF','labour').status,'NON_DISPONIBILE','Wrong source file is quarantined');
const dup=structuredClone(data.macroSeries);
const arr=dup.CHF.find(x=>x.id==='CH_UNEMP_RATE_history_value');
arr.dates.push(arr.dates.at(-1));arr.values.push(arr.values.at(-1));
assert.equal(check(dup,'CHF','labour').forecast,m.currencies.CHF.labour.forecast,
 'Identical duplicate month is deduplicated without changing estimate');
assert.equal(check(dup,'CHF','labour').sourceQualityAudit.identicalMonthRowsDeduplicated,1);
arr.values[arr.values.length-1]+=0.5;
assert.equal(check(dup,'CHF','labour').status,'NON_DISPONIBILE',
 'Conflicting duplicate month must be rejected');
const future=structuredClone(data.macroSeries);
const usd=future.USD.find(x=>x.id==='US_CPIAUCSL_history_value');
usd.dates.push('2027-01-01');usd.values.push(999);
assert.deepEqual(check(future,'USD','inflation').forecast,m.currencies.USD.inflation.forecast,
 'Future observations may not leak into estimate');
assert.equal(check(data.macroSeries,'USD','inflation','2026-11-32').status,'NON_DISPONIBILE');
assert.equal(check(data.macroSeries,'GBP','labour','2027-07-12').status,'FONTE_TROPPO_VECCHIA');
const zero=structuredClone(data.macroSeries);
zero.USD.find(x=>x.id==='US_CPIAUCSL_history_value').values[20]=0;
assert.equal(check(zero,'USD','inflation').status,'NON_DISPONIBILE','Invalid CPI index rejected');
const fmt=(x,n=2)=>typeof x==='number'&&Number.isFinite(x)?
 x.toLocaleString('it-IT',{minimumFractionDigits:n,maximumFractionDigits:n}):'—';
const sign=(x,n=2,suf='')=>typeof x==='number'&&Number.isFinite(x)?
 (x>0?'+':x<0?'−':'')+fmt(Math.abs(x),n)+suf:'—';
const esc=x=>String(x??'').replace(/&/g,'&amp;').replace(/</g,'&lt;')
 .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const flags=Object.fromEntries(FX.map(c=>[c,c]));
const params={get:k=>data[k],FX,FLAGS:flags,NAMES:flags,pageHero:()=>'<header>G8</header>',
 esc,fmt,sign,date:x=>x,finite:x=>typeof x==='number'&&Number.isFinite(x),
 validDay:x=>/^\d{4}-\d\d-\d\d$/.test(x||''),dayNow:()=>now};
const baseArgs={prices:data.currencyPrices,macro:data.macro.currencies,
 rates:data.rates,ois:data.ois.currencies,cot:data.cotHistory,
 now,rankingFn:Ranking.currencyRanking};
const ref=Strength.analyze(baseArgs);
const firstRanks=[];
for(const c of FX){
 const html=C.render({...params,state:{ccy:c,csOther:c==='EUR'?'USD':'EUR',csReturnWindow:20}});
 assert(html.includes('CPI'),'CPI G8 shown for '+c);
 assert(html.includes('Disocc.'),'Unemployment G8 shown for '+c);
 assert(html.includes('Inflazione headline YoY'),'Inflation provenance in research '+c);
 assert(html.includes('Disoccupazione'),'Labour provenance in dossier '+c);
 assert(html.includes('SCENARIO MACRO · NON POINT-IN-TIME'),'No release-vintage certification claim');
 assert(html.includes('nessun effetto sul ranking FX'),'Research cannot become FX score');
 assert.equal((html.match(/class="strength-row /g)||[]).length,8);
 assert(!/\bNaN\b|\bundefined\b|\[object Object\]/.test(html),'No broken JS in G8 output');
 firstRanks.push(html.match(/class="strength-name"><b>(.*?)<\/b><strong>/)?.[1]);
}
assert.equal(new Set(firstRanks).size,1,'Selected currency cannot alter price ranking');
const after=Strength.analyze(baseArgs);
assert.deepEqual(after.rows.map(x=>x.ccy),ref.rows.map(x=>x.ccy));
assert.deepEqual(after.rows.map(x=>x.evidenceCount),ref.rows.map(x=>x.evidenceCount));
const idx=read(dir+'index.html');
assert(idx.includes('g8-inflation-labour-shadow.js?v=1'));
assert(idx.indexOf('g8-inflation-labour-shadow.js')<idx.indexOf('currency-studio.js'));
assert(idx.includes('currency-studio.js?v=10'));
console.log('G8_INFLATION_LABOUR_SHADOW_V1_PASS: 10 dated estimates, 6 observed unchanged, CHF unemployment only candidate; dates/vintage/benchmark/ranking guards');
