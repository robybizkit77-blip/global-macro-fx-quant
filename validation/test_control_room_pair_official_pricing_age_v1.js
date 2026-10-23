/* One source eligibility contract for Home, Rates and Pair FX G8 panels.
 * Simulates the calendar boundary only. Never edits market prices or models. */
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const source=fs.readFileSync('site/control-room-preview/home-navigation-v10.js','utf8');
const start=source.indexOf('function officialPricingCurrent(x){');
const end=source.indexOf('function htmlEscape(',start);
assert(start>=0&&end>start,'Missing shared official-source guard');
const clamp=(s,t)=>Math.round((Date.parse(t+'T00:00:00Z')-Date.parse(s+'T00:00:00Z'))/86400000);
const today='2026-10-23';
const fresh=(s,max)=>typeof s==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(s)&&
 Number.isFinite(clamp(s,today))&&clamp(s,today)>=0&&clamp(s,today)<=max;
const num=x=>typeof x==='number'&&Number.isFinite(x)?x:null;
const official=new Function('fresh','num',source.slice(start,end)+';return officialPricingCurrent;')(fresh,num);
const feed=JSON.parse(fs.readFileSync('live_data/sections/OIS_OPERATIONAL_VIEW.json','utf8'));
const real=Object.entries(feed.currencies).filter(([,x])=>official(x)).map(([k])=>k).sort();
// A certified source can publish metadata without a complete current curve.
// Only a source passing all age, horizon and quote eligibility gates belongs
// in Home/Rates/Pair real coverage; do not force an outdated four-source set.
const candidates=['AUD','CAD','GBP','JPY'];
assert(real.length>=1,'at least one presently complete certified fixture for boundary tests');
assert(real.every(ccy=>candidates.includes(ccy)),
  'only independently certified source families can be promoted');
for(const ccy of candidates){
  const h=feed.currencies[ccy].horizons;
  if(['3m','6m','12m'].some(t=>!Number.isFinite(h[t]?.rate)))
    assert(!real.includes(ccy),ccy+' incomplete source must not be promoted');
}
const x=structuredClone(feed.currencies.GBP);
x.as_of='2026-10-19'; // four Rome calendar days
assert.equal(official(x),true,'official age day four remains usable');
x.as_of='2026-10-18'; // five days
assert.equal(official(x),false,'official age day five is historical, not current');
x.as_of='2026-10-24';
assert.equal(official(x),false,'future as-of not current');
x.as_of='2026-10-22';
const negative=[
 ['estimated',v=>v.operational_status='GREEN_ESTIMATED'],
 ['withheld',v=>v.operational_status='WITHHELD'],
 ['quality',v=>v.quality='ESTIMATED_INFORMATIONAL'],
 ['inactive',v=>v.official_status='WITHHELD'],
 ['no backtest certification',v=>v.backtest_eligible_as_official=false],
 ['no 3m',v=>v.horizons['3m'].rate=null],
 ['no 6m policy delta',v=>v.horizons['6m'].policy_delta_bp=null],
 ['bad 12m',v=>v.horizons['12m'].rate=NaN],
];
for(const [label,mutate] of negative){
 const bad=structuredClone(x);mutate(bad);
 assert.equal(official(bad),false,label);
}
assert.equal(official(x),true);
assert.equal(source.includes('const oisCurrent=FX.filter(k=>{\n  const x=ois?.currencies?.[k];\n  return officialPricingCurrent(x);'),true,'Home must reuse eligibility');
assert(source.includes("const oisDay=o?.as_of,oisState=officialPricingCurrent(o);"),'Pair source leg must reuse eligibility');
assert(source.includes("const ok=officialPricingCurrent(o);"),'Pair 6m repricing must reuse eligibility');
assert(source.includes("if(!officialPricingCurrent(x))return [];"),'Rates curve must reuse eligibility');
assert(source.includes("return officialPricingCurrent(r);"),'Rates chart must reconcile same eligibility');
console.log('CONTROL_ROOM_OIS_HOME_RATES_PAIR_4_DAY_SOURCE_PARITY_PASS',
 JSON.stringify({certified:real,positiveBoundary:4,rejectedBoundary:5,negative:negative.length}));
