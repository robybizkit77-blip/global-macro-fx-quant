'use strict';
/* Next V17: dated CHF & post-roll NZD research must NEVER become 5/20 FX/2Y verdict. */
const assert=require('node:assert/strict'),fs=require('node:fs');
const j=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const rates=j('live_data/sections/NATIVE_RATES_DATA.json');
const pairs=j('live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json');
const prices=j('live_data/sections/ECB_G8_PRICE_HISTORY.json');
const aud=j('site/fx-quant-v2/aud-rba-f2-history-research.json');
const chf=j('site/fx-quant-v2/chf-snb-paired-history.json');
const nzd=j('site/fx-quant-v2/nzd-b2-postroll-web-research.json');
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
assert(mediumCount>=10&&mediumCount<=all.filter(x=>x.ready&&x.short).length,
 '20-interval research coverage must be supported by validated short comparisons');
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
const page=fs.readFileSync('site/fx-quant-v2/next/index.html','utf8');
const app=fs.readFileSync('site/fx-quant-v2/next/app.js','utf8');
const journey=fs.readFileSync('site/fx-quant-v2/next/decision-journey.js','utf8');
assert(page.includes('fx-rates-bridge.js?v=17')&&page.includes('app.js?v=18'));
assert(app.includes("chfResearch:'../chf-snb-paired-history.json'"));
assert(app.includes("nzdPostroll:'../nzd-b2-postroll-web-research.json'"));
assert(journey.includes("get('chfResearch')")&&journey.includes("get('nzdPostroll')"));
console.log('NEXT_V17_SOURCE_PROVENANCE_PASS',JSON.stringify({CHF:chfContext[0].lastDate,NZD:nzdContext[0].lastDate,NZD_intervals:nzdContext[0].intervals,short:shortCount,medium:mediumCount,core_changed:false}));
