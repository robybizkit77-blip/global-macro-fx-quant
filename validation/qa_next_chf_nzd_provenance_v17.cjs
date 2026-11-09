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
// Preserve the reviewed 6 Nov fixture; the production FX fixing moves independently.
const now='2026-11-08',asof='2026-11-06';
const fixturePairs={...pairs,price_asof:asof};
assert.equal(nzd.source_release_date,'2026-11-06');
assert.equal(nzd.source_capture_method,'PUBLIC_OFFICIAL_PAGE_MANUAL_RESEARCH_NOT_AUTOMATED_FETCH');
assert.equal(nzd.automated_access_authorized,false);
assert.equal(nzd.independent_xlsx_reconciled,false);
assert.equal(nzd.eligible_for_core,false);
assert.equal(nzd.eligible_for_fx_pair_engine,false);
assert.equal(nzd.eligible_for_backtests,false);
assert.equal(nzd.benchmark_roll_date,'2026-10-30');
assert.equal(nzd.daily_observations.length,5);
assert.equal(nzd.daily_observations.at(-1).date,'2026-11-05');
assert.equal(nzd.daily_observations.at(-1)['2Y'],3.78);
assert.equal(nzd.daily_observations.at(-1)['10Y'],4.74);
for(const rec of nzd.daily_observations.filter(x=>['2026-10-30','2026-11-03','2026-11-04'].includes(x.date))){
 const stored=legacy.NZD.after_roll.find(x=>x.date===rec.date);
 assert(stored&&stored['2Y']===rec['2Y']&&stored['10Y']===rec['10Y'],'NZD overlapping published research must reconcile '+rec.date);
}
const chfContext=mod.researchedSources(rates,'EURCHF',asof,now,chf,nzd);
const nzdContext=mod.researchedSources(rates,'NZDUSD',asof,now,chf,nzd);
const crossContext=mod.researchedSources(rates,'CHFNZD',asof,now,chf,nzd);
assert.equal(chfContext.length,1);
assert.equal(nzdContext.length,1);
assert.equal(crossContext.length,2);
assert.equal(chfContext[0].lastDate,'2026-10-30');
assert.equal(chfContext[0].count,23);
assert.equal(nzdContext[0].lastDate,'2026-11-05');
assert.equal(nzdContext[0].count,5);
assert.equal(nzdContext[0].intervals,4);
assert.match(nzdContext[0].text,/Manca 1 intervallo/);
assert.match(nzdContext[0].text,/riconciliazione XLSX/);
assert.match(nzdContext[0].text,/Nessun collegamento/);
assert(!mod.snapshot(rates,prices,'EURCHF',asof,now,aud,chf,nzd).ready);
assert(!mod.snapshot(rates,prices,'NZDUSD',asof,now,aud,chf,nzd).ready);
assert(!mod.snapshot(rates,prices,'CHFNZD',asof,now,aud,chf,nzd).ready);
const all=Object.keys(pairs.pairs).map(key=>mod.snapshot(rates,prices,key,asof,now,aud,chf,nzd));
assert.equal(all.length,28);
assert.equal(all.filter(x=>x.ready&&x.short).length,15);
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
 const context=mod.researchedSources(rates,which==='CHF'?'EURCHF':'NZDUSD',asof,now,which==='CHF'?altered:chf,which==='NZD'?altered:nzd);
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
 ['wrong release',x=>x.source_release_date='2026-11-15'],
 ['not permitted automatic download',x=>x.source_capture_method='AUTOMATED_RBNZ_SCRAPER'],
 ['future web capture',x=>x.source_capture_date='2026-11-15'],
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
assert.match(html,/data-source-context="NZD"/);
assert.match(html,/4\/5 intervalli/);
assert.match(html,/riconciliazione XLSX/);
assert.doesNotMatch(html,/<svg/);
state.pair='CHFNZD';
html=mod.build(api).render();
assert.match(html,/data-source-context="NZD"/);
assert.match(html,/data-source-context="CHF"/);
state.pair='EURUSD';
html=mod.build({...api,plot:()=>'<svg></svg>'}).render();
assert.doesNotMatch(html,/data-source-context=/,'Official fully current pair must not show irrelevant CHF/NZD source context');
const page=fs.readFileSync('site/fx-quant-v2/next/index.html','utf8');
const app=fs.readFileSync('site/fx-quant-v2/next/app.js','utf8');
const journey=fs.readFileSync('site/fx-quant-v2/next/decision-journey.js','utf8');
assert(page.includes('fx-rates-bridge.js?v=17')&&page.includes('app.js?v=17'));
assert(app.includes("chfResearch:'../chf-snb-paired-history.json'"));
assert(app.includes("nzdPostroll:'../nzd-b2-postroll-web-research.json'"));
assert(journey.includes("get('chfResearch')")&&journey.includes("get('nzdPostroll')"));
console.log('NEXT_V17_SOURCE_PROVENANCE_PASS',JSON.stringify({CHF:chfContext[0].lastDate,NZD:nzdContext[0].lastDate,NZD_intervals:nzdContext[0].intervals,short:all.filter(x=>x.ready&&x.short).length,medium:mediumCount,core_changed:false}));
