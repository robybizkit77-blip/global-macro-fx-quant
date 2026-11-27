'use strict';
/* Archived CHF/NZD context cannot become a 5/20 verdict. Reconciled B2 is separate. */
const assert=require('node:assert/strict'),fs=require('node:fs');
const j=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const rates=j('live_data/sections/NATIVE_RATES_DATA.json');
const pairs=j('live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json');
const prices=j('live_data/sections/ECB_G8_PRICE_HISTORY.json');
const aud=j('site/fx-quant-v2/aud-rba-f2-history-research.json');
const chf=j('site/fx-quant-v2/chf-snb-paired-history.json');
const nzd=j('site/fx-quant-v2/nzd-b2-postroll-web-research.json');
const reconciled=j('site/fx-quant-v2/nzd-rbnz-b2-reconciled-research.json');
const estimateFeed=j('site/fx-quant-v2/chf-2y-estimate-research.json');
const legacy=j('site/fx-quant-v2/chf-nzd-benchmark-research.json');
const mod=require('../site/fx-quant-v2/next/fx-rates-bridge.js');
// Preserve the archived 6 Nov FX fixture; assess the independent, later NZD
// publisher archive at its actual capture date without leaking it into 6 Nov.
const now='2026-11-08',asof='2026-11-06';
const fixturePairs={...pairs,price_asof:asof};
const researchDate=nzd.source_capture_date;
const todayUTC=new Date().toISOString().slice(0,10);
assert(/^\d{4}-\d{2}-\d{2}$/.test(researchDate) && researchDate>= '2026-11-11' &&
       researchDate<=todayUTC,'RBNZ research capture must be dated and not in the future');
assert(nzd.source_release_date>='2026-11-11' && nzd.source_release_date<=researchDate,
       'RBNZ release must be dated before capture');
assert.equal(nzd.source_capture_method,'PUBLIC_OFFICIAL_PAGE_MANUAL_RESEARCH_NOT_AUTOMATED_FETCH');
assert.equal(nzd.automated_access_authorized,false);
assert.equal(nzd.independent_xlsx_reconciled,false);
assert.equal(nzd.eligible_for_core,false);
assert.equal(nzd.eligible_for_fx_pair_engine,false);
assert.equal(nzd.eligible_for_backtests,false);
assert.equal(nzd.benchmark_roll_date,'2026-10-30');
assert(nzd.daily_observations.length>=8,'Latest official B2 archive must retain the eight confirmed post-roll dates');
const nov10=nzd.daily_observations.find(x=>x.date==='2026-11-10');
assert(nov10&&nov10['2Y']===3.77&&nov10['10Y']===4.71,'10 Nov official NZD 2Y/10Y rates changed unexpectedly');
assert(nzd.daily_observations.at(-1).date>=nov10.date,'NZD archive regressed');
for(const rec of nzd.daily_observations){
 const stored=legacy.NZD.after_roll.find(x=>x.date===rec.date);
 if(stored)assert(stored['2Y']===rec['2Y']&&stored['10Y']===rec['10Y'],
  'NZD overlapping published research must reconcile '+rec.date);
}
const chfContext=mod.researchedSources(rates,'EURCHF',asof,now,chf,nzd);
const nzdContext=mod.researchedSources(rates,'NZDUSD',researchDate,researchDate,chf,nzd);
const crossContext=mod.researchedSources(rates,'CHFNZD',researchDate,researchDate,chf,nzd);
assert.equal(mod.researchedSources(rates,'NZDUSD',asof,now,chf,nzd).length,0,
 'RBNZ archive published 11 Nov must never appear in an archived 6 Nov decision');
assert.equal(chfContext.length,1);
assert.equal(nzdContext.length,1);
assert.equal(crossContext.length,2);
assert.equal(chfContext[0].lastDate,'2026-10-30');
assert.equal(chfContext[0].count,23);
assert.equal(nzdContext[0].lastDate,nzd.daily_observations.at(-1).date);
assert.equal(nzdContext[0].count,nzd.daily_observations.length);
assert.equal(nzdContext[0].intervals,nzd.daily_observations.length-1);
assert.match(nzdContext[0].text,/Copertura temporale sufficiente/);
assert.match(nzdContext[0].text,/riconciliazione XLSX/);
assert.match(nzdContext[0].text,/Nessun collegamento/);
assert(!mod.snapshot(rates,prices,'EURCHF',asof,now,aud,chf,nzd).ready);
const archivedRates={...rates,NZD:{...rates.NZD,date:'2026-10-16'}};
assert(!mod.snapshot(archivedRates,prices,'NZDUSD',asof,now,aud,chf,nzd).ready);
const currentNZD=mod.snapshot(rates,prices,'NZDUSD',asof,now,aud,chf,nzd);
if(currentNZD.ready)assert(currentNZD.short&&currentNZD.lag<=3&&currentNZD.rows.every(x=>x.date<=asof),
 'Current archive reconstruction requires actual matched dates, never future research');
assert(!mod.snapshot(rates,prices,'CHFNZD',asof,now,aud,chf,nzd).ready);
const all=Object.keys(pairs.pairs).map(key=>mod.snapshot(rates,prices,key,asof,now,aud,chf,nzd));
assert.equal(all.length,28);
// Historical 6 Nov FX fixing is intentionally compared with the currently
// observed rate inputs. That current government coverage can change after
// 6 Nov; it must not be mistaken for an immutable 15-pair observation.
const shortCount=all.filter(x=>x.ready&&x.short).length;
assert(shortCount>=10&&shortCount<=28,
 'At least ten genuinely date-aligned sovereign/FX comparisons are required');
assert(all.filter(x=>x.ready).every(x=>x.short&&x.lag>=0&&x.lag<=3),
 'No stale or insufficient-source comparison may count as ready');
const mediumCount=all.filter(x=>x.ready&&x.medium).length;
assert(mediumCount<=shortCount&&
 all.filter(x=>x.ready&&x.medium).every(x=>x.short&&x.lag>=0&&x.lag<=3),
 '20-interval comparisons must be a subset of valid, same-date short comparisons');
// Do not assert a fabricated minimum number of 20-interval observations when
// the official sovereign series have changed their date coverage.
// Check production clock separately. Research sidecars must not silently promote
// stale CHF/NZD rates or create a 5/20 signal from non-core provenance.
const liveAsOf=pairs.price_asof;
assert(/^\d{4}-\d{2}-\d{2}$/.test(liveAsOf),'Live FX as-of date missing');
for(const pair of ['EURCHF','NZDUSD','CHFNZD']){
 const live=mod.snapshot(rates,prices,pair,liveAsOf,liveAsOf,aud,chf,nzd);
 assert(!live.researchOnly,'CHF/NZD research must not overwrite official 2Y');
 if(live.ready){
  assert(live.lag>=0&&live.lag<=3&&live.age>=0&&live.age<=5&&live.short,
   'Only verified contemporary sovereign 2Y may validate '+pair);
 }else assert.equal(mod.brief(live).ready,false,'Stale/noncanonical CHF/NZD must remain unavailable: '+pair);
}
const comparisonDay=[aud.publication_date,reconciled.publication_date,liveAsOf].sort().at(-1);
const audNzd=(b2,now=comparisonDay)=>mod.snapshot(rates,prices,'AUDNZD',liveAsOf,now,aud,chf,nzd,b2);
const withB2=audNzd(reconciled);
if(aud.last_observation_date==='2026-11-18'&&reconciled.last_observation_date==='2026-11-19'&&comparisonDay==='2026-11-20'){
 assert(withB2.ready&&withB2.researchOnly&&withB2.nzdResearch);
 assert.equal(withB2.short.start,'2026-11-11');
 assert.equal(withB2.short.end,'2026-11-18');
 assert(Math.abs(withB2.short.spreadBp+8.4)<1e-9);
 assert.equal(withB2.medium,null,'Fourteen post-roll dates cannot support 20 intervals');
}
assert(!audNzd(reconciled,'2026-11-06').nzdResearch,'Future RBNZ research cannot leak into archived analysis');
for(const changed of [
 {...reconciled,eligible_for_core:true},
 {...reconciled,benchmark_2Y:'May 2028'},
 {...reconciled,html_xlsx_matched_dates:reconciled.html_xlsx_matched_dates.slice(0,5)}
]){
 assert(!audNzd(changed).nzdResearch,'Failed provenance must disable the B2 comparison overlay');
}
// Reconciled B2 research is available for every non-CHF NZD cross, independently of AUD.
for(const pair of ['AUDNZD','NZDUSD','EURNZD','GBPNZD','NZDCAD','NZDJPY']){
 const live=mod.snapshot(rates,prices,pair,liveAsOf,comparisonDay,aud,chf,nzd,reconciled);
 const useResearch=reconciled.last_observation_date>=rates.NZD.date;
 if(useResearch){
  assert(live.nzdResearch&&live.researchOnly,pair+' must expose reconciled NZD research');
  assert.match(live.kind,/RBNZ B2 RICERCA/);
  assert(live.rows.every(row=>row.date>=reconciled.benchmark_roll_date),'No cross-roll stitching');
  if(live.ready)assert(live.short&&live.lag>=0&&live.lag<=3&&live.age>=0&&live.age<=5);
  if(live.rows.length<21)assert.equal(live.medium,null);
 }
 assert(!mod.snapshot(rates,prices,pair,liveAsOf,'2026-11-06',aud,chf,nzd,reconciled).nzdResearch);
 assert(!mod.snapshot(rates,prices,pair,liveAsOf,comparisonDay,aud,chf,nzd,{...reconciled,eligible_for_core:true}).nzdResearch);
}
assert(!mod.snapshot(rates,prices,'NZDCHF',liveAsOf,comparisonDay,aud,chf,nzd,reconciled).nzdResearch,'CHF remains a separate estimated or observed comparison');
const chfRead=(data,history,asOf=liveAsOf,clock=comparisonDay)=>
 mod.snapshot(data,prices,'AUDCHF',asOf,clock,aud,history,nzd,reconciled);
const audChf=chfRead(rates,chf);
const estimated=(key,source,clock=comparisonDay)=>
 mod.snapshot(rates,prices,key,liveAsOf,clock,aud,chf,nzd,reconciled,source);
assert(!estimated('AUDCAD',estimateFeed).estimate,'The estimate only supplies a CHF leg');
assert(!estimated('AUDCHF',{...estimateFeed,eligible_for_core:true}).estimate);
const staleClock=new Date(Date.parse(liveAsOf+'T12:00:00Z')+31*864e5).toISOString().slice(0,10);
assert(!estimated('AUDCHF',estimateFeed,staleClock).estimate,'Too-old inputs cannot produce a fresh estimate');
const chf2y=estimated('AUDCHF',estimateFeed);
if(aud.last_observation_date==='2026-11-18'&&comparisonDay==='2026-11-20'&&
   estimateFeed.observations.some(x=>x.date==='2026-11-18')){
 const e=chf2y.estimate;
 assert(e,'The verified live inputs must produce an estimate');
 assert.equal(e.start,'2026-11-09');
 assert.equal(e.end,'2026-11-18');
 assert.equal(e.weekdays,7);
 assert.equal(e.observedCurrency,'AUD');
 assert(Math.abs(e.observed2Bp-5.6)<1e-9&&Math.abs(e.chf10Bp-15)<1e-9);
 assert(e.spreadBp<0&&e.low<0&&e.high>0&&e.uncertain);
 assert.equal(chf2y.ready,false);
 assert.match(mod.brief(chf2y).label,/Stima differenziale 2Y.*segno incerto/);
}
const chfCrosses=['AUDCHF','CADCHF','CHFJPY','EURCHF','GBPCHF','NZDCHF','USDCHF'];
const comparisonFixture=liveAsOf==='2026-11-19'&&comparisonDay==='2026-11-20'&&
 estimateFeed.observations.some(r=>r.date==='2026-11-19');
const snbDates=new Set(estimateFeed.observations.map(r=>r.date));
for(const pair of chfCrosses){
 const result=estimated(pair,estimateFeed),e=result.estimate;
 if(comparisonFixture)assert(e,'The benchmark fixture supports the estimate for '+pair);
 if(!e)continue;
 assert(!result.ready&&!result.short,'Estimate must stay separate from observed coverage: '+pair);
 const ccy=pair.replace('CHF',''),native=rates[ccy];
 const observed=ccy==='AUD'?aud:ccy==='NZD'&&reconciled.last_observation_date>=native.date?reconciled:null;
 const observedDates=new Set(observed?observed.observations.map(r=>r.date):
  native.history2.dates.filter((d,i)=>d<=native.date&&Number.isFinite(native.history2.values[i])));
 const latestDates=[...new Set(prices.rows.filter(r=>r.Date<=liveAsOf&&r.Date<=prices.last_as_of&&
  snbDates.has(r.Date)&&observedDates.has(r.Date)&&r.CHF>0&&r[ccy]>0).map(r=>r.Date))].sort();
 assert.equal(e.observedCurrency,ccy);
 assert.equal(e.end,latestDates.at(-1),pair+' must use the latest common fixing');
 assert.equal(e.start,latestDates.at(-6),pair+' must use the sixth latest common fixing');
 const direction=pair.startsWith('CHF')?-1:1;
 assert(Math.abs(e.spreadBp-direction*(e.observed2Bp-e.chf2Bp))<1e-9);
}
if(comparisonFixture){
 const nzdEstimate=estimated('NZDCHF',estimateFeed).estimate;
 assert.match(nzdEstimate.observedSource,/RBNZ B2/);
 assert(!mod.snapshot(rates,prices,'NZDCHF',liveAsOf,comparisonDay,aud,chf,nzd,
   {...reconciled,benchmark_2Y:'May 2028'},estimateFeed).estimate);
 const baseChf=estimated('CHFJPY',estimateFeed).estimate;
 const quoteChf=estimated('JPYCHF',estimateFeed).estimate;
 assert(Math.abs(baseChf.spreadBp+quoteChf.spreadBp)<1e-9);
 assert(Math.abs(baseChf.low+quoteChf.high)<1e-9);
 assert(Math.abs((1+baseChf.fxPct/100)*(1+quoteChf.fxPct/100)-1)<1e-9);
 const confirmed={...rates,CHF:{...rates.JPY}};
 const withOfficial=mod.snapshot(confirmed,prices,'CHFJPY',liveAsOf,comparisonDay,aud,chf,nzd,reconciled,estimateFeed);
 assert(withOfficial.ready&&!withOfficial.estimate,'Observed aligned rates supersede the estimate');
}
assert(!chfRead(rates,chf,asof,now).historical,'A later RBA vintage cannot reach the archived desk');
assert(!chfRead(rates,{...chf,eligible_for_core:true}).historical,'Invalid CHF research cannot feed the historical comparison');
if(aud.last_observation_date==='2026-11-18'&&rates.AUD.date===aud.last_observation_date&&chf.last_observation_date==='2026-10-30'&&liveAsOf>='2026-11-18'){
 assert(!audChf.ready&&!audChf.short&&!audChf.medium,'Archived matched 2Y does not become a live verdict');
 assert.equal(audChf.historical.asof,'2026-10-30');
 assert.equal(audChf.historical.short.start,'2026-10-23');
 assert.equal(audChf.historical.medium.start,'2026-10-01');
 assert(Math.abs(audChf.historical.short.spreadBp-0.4)<1e-9);
 assert(Math.abs(audChf.historical.medium.spreadBp+3.2)<1e-9);
 assert(!mod.brief(audChf).ready);
 const newAnchor=chf.observations.at(-2);
 const advanced={...rates,CHF:{...rates.CHF,...newAnchor}};
 assert.deepEqual(chfRead(advanced,chf).historical,audChf.historical,'The CHF anchor can advance within the validated archive');
}
if(rates.AUD.date!==aud.last_observation_date){
 assert(!audChf.historical,'Do not construct an anchored AUD/CHF historical comparison from mismatched native and research endpoints');
 assert(!audChf.estimate,'Do not use stale F2 as an anchored AUD estimate leg');
}
const before=JSON.stringify(rates);
for(const x of all)assert(typeof x.ready==='boolean');
assert.equal(JSON.stringify(rates),before,'Research must not mutate native rates');
const testAlter=(which,description,mutate)=>{
 const altered=JSON.parse(JSON.stringify(which==='CHF'?chf:nzd));
 mutate(altered);
 const context=mod.researchedSources(rates,which==='CHF'?'EURCHF':'NZDUSD',
  which==='CHF'?asof:researchDate,which==='CHF'?now:researchDate,
  which==='CHF'?altered:chf,which==='NZD'?altered:nzd);
 assert.equal(context.length,0,'Invalid source must not show research claim: '+description);
};
[
 ['fake eligibility',x=>x.eligible_for_core=true],
 ['non-source',x=>x.source_url='https://invalid.example'],
 ['mismatched canonical anchor',x=>x.observations[0]['2Y']+=.01],
 ['future observation',x=>x.last_observation_date='2026-11-13'],
 ['source revision',x=>x.observations[1].curve_bp=999],
 ['bad source SHA',x=>x.source_response_sha256='no-proof'],
 ['wrong reported count',x=>x.observation_count=12]
].forEach(([label,f])=>testAlter('CHF',label,f));
[
 ['wrong release',x=>x.source_release_date='2099-11-15'],
 ['not permitted automatic download',x=>x.source_capture_method='AUTOMATED_RBNZ_SCRAPER'],
 ['future web capture',x=>x.source_capture_date='2099-11-15'],
 ['fake XLSX reconciliation',x=>x.independent_xlsx_reconciled=true],
 ['unreviewed production promotion',x=>x.eligible_for_fx_pair_engine=true],
 ['old-benchmark splicing',x=>x.daily_observations.unshift({date:'2026-10-29','2Y':3.77,'10Y':4.87})],
 ['source roll altered',x=>x.benchmark_roll_date='2026-10-29'],
 ['duplicate observation',x=>x.daily_observations[1].date=x.daily_observations[0].date],
 ['bad yield',x=>x.daily_observations.at(-1)['2Y']=100],
 ['unknown source',x=>x.source_url='https://invalid.example']
].forEach(([label,f])=>testAlter('NZD',label,f));
const date=s=>s,fmt=(v,n=2)=>Number(v).toFixed(n);
const sign=(v,n=2,u='')=>(v>0?'+':'')+Number(v).toFixed(n)+u;
const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const state={pair:'EURCHF',pairPriceWindow:60};
const get=k=>({rates:archivedRates,pairs:fixturePairs,currencyPrices:prices,audDailyResearch:aud,chfResearch:chf,nzdPostroll:nzd})[k];
const api={get,state,plot:()=>{throw Error('Stale CHF/NZD must not draw a current FX/rates chart')},fmt,sign,date,esc,dayNow:()=>now};
let html=mod.build(api).render();
assert.match(html,/data-source-context="CHF"/);
assert.match(html,/2026-10-30/);
assert.match(html,/non certificato come quotazione corrente/);
assert.doesNotMatch(html,/<svg/);
state.pair='NZDUSD';
html=mod.build(api).render();
assert.doesNotMatch(html,/data-source-context="NZD"/,'Do not backdate 11 Nov NZD research into 6 Nov');
assert.doesNotMatch(html,/<svg/);
state.pair='CHFNZD';
html=mod.build(api).render();
assert.doesNotMatch(html,/data-source-context="NZD"/,'Archived cross must exclude future NZD research');
assert.match(html,/data-source-context="CHF"/);
// The same source becomes visible on its verified publication/capture date,
// as research context only; it cannot create a current FX/2Y trading signal.
const researchPairs={...pairs,price_asof:researchDate};
const researchGet=k=>({rates:archivedRates,pairs:researchPairs,currencyPrices:prices,audDailyResearch:aud,
  chfResearch:chf,nzdPostroll:nzd})[k];
state.pair='NZDUSD';
const researchHtml=mod.build({...api,get:researchGet,dayNow:()=>researchDate}).render();
assert.match(researchHtml,/data-source-context="NZD"/);
assert.match(researchHtml,/riconciliazione XLSX/);
assert.doesNotMatch(researchHtml,/<svg/,'Research context does not manufacture an FX rate chart');
state.pair='EURUSD';
html=mod.build({...api,plot:()=>'<svg></svg>'}).render();
assert.doesNotMatch(html,/data-source-context=/,'Official fully current pair must not show irrelevant CHF/NZD source context');
if(audChf.historical){
 const observed=mod.build({...api,state:{pair:'AUDCHF'},dayNow:()=>comparisonDay,
   get:k=>({rates,pairs,currencyPrices:prices,audDailyResearch:aud,chfResearch:chf,nzdPostroll:nzd})[k]}).render();
 assert.match(observed,/data-historical-rate-asof=/);
 assert.match(observed,/ultimo confronto osservato al/);
 assert.doesNotMatch(observed,/data-rate-asof=|data-horizon=/);
}
if(chf2y.estimate){
 const mixed=mod.build({...api,state:{pair:'AUDCHF'},dayNow:()=>comparisonDay,
   get:k=>({rates,pairs,currencyPrices:prices,audDailyResearch:aud,chfResearch:chf,chf2yEstimate:estimateFeed})[k]}).render();
 assert.match(mixed,/data-estimated-rate-asof=/);
 assert.match(mixed,/2Y stimato/);
 assert.match(mixed,/Fascia basata sull’errore storico/);
 assert.doesNotMatch(mixed,/data-rate-asof=|data-horizon=/);
}
const page=fs.readFileSync('site/fx-quant-v2/next/index.html','utf8');
const app=fs.readFileSync('site/fx-quant-v2/next/app.js','utf8');
const journey=fs.readFileSync('site/fx-quant-v2/next/decision-journey.js','utf8');
assert(/fx-rates-bridge\.js\?v=\d+"/.test(page)&&/app\.js\?v=[\w.-]+"/.test(page));
assert(app.includes("chfResearch:'../chf-snb-paired-history.json'"));
assert(app.includes("nzdPostroll:'../nzd-b2-postroll-web-research.json'"));
assert(app.includes("nzdReconciled:'../nzd-rbnz-b2-reconciled-research.json'")&&journey.includes("get('nzdReconciled')"));
assert(journey.includes("get('chfResearch')")&&journey.includes("get('nzdPostroll')"));
assert(app.includes('withChfCurrencyRanking?.(estimate,state.data.chf2yEstimate,now)'));

// Weekly CHF is a dated ranking input. The pair thesis and its official
// rate data stay on their existing path, even when the estimate is strong.
const rankingDay='2026-11-20';
const weeklyFeed={...estimateFeed,observations:estimateFeed.observations.filter(row=>row.date<=rankingDay)};
const makeRanking=(quality='ASSENTE')=>{
 const currencies=Object.keys(rates).map(ccy=>({ccy,score:ccy==='USD'?.06:0,
  rate:{quality:ccy==='CHF'?quality:'UFFICIALE'}}));
 return {status:'STIMA_OPERATIVA_NON_VALIDATA',method:{policy:.3},currencies,pairs,
  by:Object.fromEntries(currencies.map(row=>[row.ccy,row]))};
};
const original=makeRanking();
const weekly=mod.withChfCurrencyRanking(original,weeklyFeed,rankingDay);
const weeklyRate=weekly.by.CHF.rankingRate;
assert.equal(weeklyRate.start,'2026-11-13');
assert.equal(weeklyRate.asof,rankingDay);
assert(weeklyRate.low<0&&weeklyRate.high>0);
assert.equal(weeklyRate.score,0,'A range crossing zero supplies context, not a directional vote');
assert.equal(weekly.by.CHF.score,original.by.CHF.score);
assert.equal(weekly.by.CHF.rate,original.by.CHF.rate);
assert.equal(weekly.pairs,original.pairs);
assert.equal(mod.withChfCurrencyRanking(weekly,weeklyFeed,rankingDay),weekly);
const stronger=structuredClone(weeklyFeed);
stronger.observations.at(-1).yield_percent=.90;
const supported=mod.withChfCurrencyRanking(original,stronger,rankingDay);
assert.equal(supported.by.CHF.rankingRate.score,.25);
assert.equal(supported.by.CHF.score,.075);
assert.equal(supported.currencies[0].ccy,'CHF');
assert.equal(supported.pairs,original.pairs);
stronger.observations.at(-1).yield_percent=.30;
assert.equal(mod.withChfCurrencyRanking(original,stronger,rankingDay).by.CHF.rankingRate.score,-.25);
stronger.observations.at(-1).yield_percent=.72;
assert.equal(mod.withChfCurrencyRanking(original,stronger,rankingDay).by.CHF.rankingRate.score,0,
 'Even a positive range needs to clear the existing 5 bp threshold');
for(const q of ['UFFICIALE','PROXY']){
 const preferred=makeRanking(q);
 assert.equal(mod.withChfCurrencyRanking(preferred,weeklyFeed,rankingDay),preferred);
}
const missingStart={...weeklyFeed,observations:weeklyFeed.observations.filter(row=>row.date!=='2026-11-13')};
assert.equal(mod.withChfCurrencyRanking(original,missingStart,rankingDay),original);
assert.equal(mod.withChfCurrencyRanking(original,weeklyFeed,'2026-11-26'),original);
assert.equal(mod.withChfCurrencyRanking(original,weeklyFeed,'2026-11-19'),original);
assert.equal(mod.withChfCurrencyRanking(original,{...weeklyFeed,eligible_for_core:true},rankingDay),original);
console.log('NEXT_V17_SOURCE_PROVENANCE_PASS',JSON.stringify({CHF:chfContext[0].lastDate,NZD:nzdContext[0].lastDate,NZD_intervals:nzdContext[0].intervals,short:shortCount,medium:mediumCount,core_changed:false}));

 // G8 narrative must agree with the already reconciled B2 source without changing scores.
 const currencyFallback=require('../site/fx-quant-v2/next/currency-data-fallback.js');
 const legacyNzd={...rates,NZD:{...rates.NZD,date:'2026-10-16'}};
 const b2Day=reconciled.publication_date;
 const b2Axis=currencyFallback.researchRatesAxis('NZD',chf,null,legacyNzd,b2Day,reconciled);
 assert.equal(b2Axis.status,'RICERCA_RBNZ_RICONCILIATA');
 assert.equal(b2Axis.asof,reconciled.last_observation_date);
 assert.equal(b2Axis.eligibleForCore,false);
 assert.match(b2Axis.description,/tabella ed Excel riconciliati/);
 assert.doesNotMatch(b2Axis.description,/manca la riconciliazione/);
 for(const bad of [{...reconciled,eligible_for_core:true},{...reconciled,html_xlsx_matched_dates:[]},{...reconciled,benchmark_2Y:'May 2028'}])
  assert.equal(currencyFallback.researchRatesAxis('NZD',chf,null,legacyNzd,b2Day,bad).status,'NON_DISPONIBILE');
 assert.equal(currencyFallback.researchRatesAxis('NZD',chf,null,legacyNzd,'2099-01-01',reconciled).status,'NON_DISPONIBILE');
 assert.equal(currencyFallback.researchRatesAxis('NZD',chf,null,legacyNzd,'2026-11-06',reconciled).status,'NON_DISPONIBILE');
 assert.equal(currencyFallback.researchRatesAxis('NZD',chf,null,{...legacyNzd,NZD:{date:'2099-01-01'}},b2Day,reconciled).status,'NON_DISPONIBILE');
 assert.match(require('node:fs').readFileSync('site/fx-quant-v2/next/currency-studio.js','utf8'),/nzdReconciled:get\('nzdReconciled'\)/);
 console.log('NZD_G8_RECONCILED_CONTEXT_PASS');
