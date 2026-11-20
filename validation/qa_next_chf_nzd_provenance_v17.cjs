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
assert(!mod.snapshot(rates,prices,'NZDUSD',asof,now,aud,chf,nzd).ready);
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
assert(!mod.snapshot(rates,prices,'NZDUSD',liveAsOf,comparisonDay,aud,chf,nzd,reconciled).nzdResearch);
const chfRead=(data,history,asOf=liveAsOf,clock=comparisonDay)=>
 mod.snapshot(data,prices,'AUDCHF',asOf,clock,aud,history,nzd,reconciled);
const audChf=chfRead(rates,chf);
const estimated=(key,source,clock=comparisonDay)=>
 mod.snapshot(rates,prices,key,liveAsOf,clock,aud,chf,nzd,reconciled,source);
assert(!estimated('AUDCAD',estimateFeed).estimate,'The CHF estimate is scoped to AUD/CHF');
assert(!estimated('AUDCHF',{...estimateFeed,eligible_for_core:true}).estimate);
assert(!estimated('AUDCHF',estimateFeed,'2026-12-05').estimate,'Too-old inputs cannot produce a fresh estimate');
const chf2y=estimated('AUDCHF',estimateFeed);
if(aud.last_observation_date==='2026-11-18'&&comparisonDay==='2026-11-20'&&
   estimateFeed.observations.some(x=>x.date==='2026-11-18')){
 const e=chf2y.estimate;
 assert(e,'The verified live inputs must produce an estimate');
 assert.equal(e.start,'2026-11-09');
 assert.equal(e.end,'2026-11-18');
 assert.equal(e.weekdays,7);
 assert(Math.abs(e.aud2Bp-5.6)<1e-9&&Math.abs(e.chf10Bp-15)<1e-9);
 assert(e.spreadBp<0&&e.low<0&&e.high>0&&e.uncertain);
 assert.equal(chf2y.ready,false);
 assert.match(mod.brief(chf2y).label,/Stima differenziale 2Y.*segno incerto/);
}
assert(!chfRead(rates,chf,asof,now).historical,'A later RBA vintage cannot reach the archived desk');
assert(!chfRead(rates,{...chf,eligible_for_core:true}).historical,'Invalid CHF research cannot feed the historical comparison');
if(aud.last_observation_date==='2026-11-18'&&chf.last_observation_date==='2026-10-30'&&liveAsOf>='2026-11-18'){
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
const get=k=>({rates,pairs:fixturePairs,currencyPrices:prices,audDailyResearch:aud,chfResearch:chf,nzdPostroll:nzd})[k];
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
const researchGet=k=>({rates,pairs:researchPairs,currencyPrices:prices,audDailyResearch:aud,
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
console.log('NEXT_V17_SOURCE_PROVENANCE_PASS',JSON.stringify({CHF:chfContext[0].lastDate,NZD:nzdContext[0].lastDate,NZD_intervals:nzdContext[0].intervals,short:shortCount,medium:mediumCount,core_changed:false}));
