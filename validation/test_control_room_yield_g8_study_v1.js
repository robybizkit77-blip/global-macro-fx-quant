'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs');
const src=fs.readFileSync('site/control-room-preview/home-navigation-v10.js','utf8');
const a=src.indexOf('function yieldStudySnapshot(raw,derived){');
const b=src.indexOf('function renderYieldStudy(',a);
assert(a>=0&&b>a,'G8 yield snapshot pure helper missing');
const FX=['USD','EUR','GBP','JPY','AUD','CAD','NZD','CHF'];
const num=x=>typeof x==='number'&&Number.isFinite(x)?x:null;
const live=JSON.parse(fs.readFileSync('live_data/sections/NATIVE_RATES_DATA.json','utf8'));
// This fixture must age relative to the latest real official observation,
// not an immutable Oct-23 test clock that later makes valid Oct-26 data
// appear from the future and aborts the published v10 build.
const latest=FX.map(ccy=>live[ccy]?.date).filter(x=>/^20\\d{2}-\\d{2}-\\d{2}$/.test(x||'')).sort().at(-1);
assert(latest,'official rates have no valid dated observations');
const now=Date.parse(latest+'T00:00:00Z');
const age=iso=>{
 if(!/^20\d{2}-\d{2}-\d{2}$/.test(iso||''))return null;
 const d=Date.parse(iso+'T00:00:00Z');
 return Number.isFinite(d)?Math.round((now-d)/86400000):null;
};
const f=new Function('FX','num','romeCalendarAge',src.slice(a,b)+';return yieldStudySnapshot;')
 (FX,num,age);
const rows=f(live,{});
assert.equal(rows.covered,8,'eight existing G8 observed yield pairs');
assert.equal(rows.recent,FX.filter(ccy=>age(live[ccy].date)<=4).length,
  'recent count follows actual age, not a hard-coded Oct-23 vintage');
assert.equal(rows.scenarios,0,'no model must be silently invented');
for(const x of rows.rows) {
 assert(Number.isFinite(x.v2)&&Number.isFinite(x.v10)&&Number.isFinite(x.slopeBp),x.ccy);
 assert.equal(x.asof,live[x.ccy].date);
 assert(Math.abs(x.slopeBp-Math.round(100*(x.v10-x.v2)*10)/10)<1e-10);
}
for(const row of rows.rows)
  assert.equal(row.status,age(row.asof)>4?'HISTORICAL':'RECENT',
               'every valid issuer observation must follow the 4-day window');
function invalid(ccy,fn){
 const bad=structuredClone(live);fn(bad[ccy]);const o=f(bad,{}).rows.find(x=>x.ccy===ccy);
 assert.equal(o.status,'UNAVAILABLE','reject modified '+ccy);
 assert.equal(o.slopeBp,null,'no invented current slope');
}
invalid('EUR',x=>x['2Y']+=0.01);
invalid('USD',x=>x.history10.dates.pop());
invalid('AUD',x=>x.quality='ESTIMATED_ONLY');
const future=new Date(now+86400000).toISOString().slice(0,10);
invalid('JPY',x=>x.date=future);
const fake=structuredClone(live);fake.CHF.date=future;
assert.equal(f(fake,{}).rows.find(x=>x.ccy==='CHF').status,'UNAVAILABLE',
 'date relabeling cannot upgrade archived yields');
const estim={CHF:{estimate2:true,estimate10:true,proxy:'EUR',
 estimatedAsOf2:live.EUR.date,estimatedAsOf10:live.EUR.date,
 v2:.24,v10:.5,r2_2:.14,r2_10:.19,confidence2:'BASSA',confidence10:'BASSA'}};
if(rows.rows.find(x=>x.ccy==='CHF').status==='HISTORICAL'&&
   rows.rows.find(x=>x.ccy==='EUR').status==='RECENT')
  assert.equal(f(live,estim).rows.find(x=>x.ccy==='CHF').scenario?.proxy,'EUR');
else
  assert.equal(f(live,estim).rows.find(x=>x.ccy==='CHF').scenario,null);
assert.equal(f(live,estim).rows.find(x=>x.ccy==='CHF').slopeBp,29.9,
 'the observed CHF slope remains the historical same-date one');
estim.CHF.estimatedAsOf10=new Date(Date.parse(live.EUR.date+'T00:00:00Z')-86400000).toISOString().slice(0,10);
assert.equal(f(live,estim).rows.find(x=>x.ccy==='CHF').scenario,null,
 'mismatched scenario dates must not create a mixed-date estimate');
assert(src.includes("host.dataset.coreEffect='NONE'")&&src.includes("host.dataset.pairEffect='NONE'"));
assert(src.includes('renderYieldStudy(doc,feeds[2],feeds[3],feeds[5])'),'RBNZ web-review is a separate sixth feed, not canonical Rates');
console.log('G8_YIELD_DATED_STUDY_NO_PROMOTION_PASS',JSON.stringify({covered:rows.covered,recent:rows.recent,historical:rows.covered-rows.recent,no_core_effect:true}));
