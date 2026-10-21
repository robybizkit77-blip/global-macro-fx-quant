/* Deterministic negative and expansion tests for the READ-ONLY Rates chart.
 * Synthetic fifth certified lane is used only in memory. Never mutates data. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs');
const source=fs.readFileSync('site/control-room-preview/home-navigation-v10.js','utf8');
const a=source.indexOf('function marketResearchCurves(data){');
const b=source.indexOf('\nfunction marketResearchSvg(',a);
assert(a>=0&&b>a,'Canonical Rates renderer not found');
const FX=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
const DAY='2026-10-21';
const age=s=>(Date.parse(DAY+'T00:00:00Z')-Date.parse(s+'T00:00:00Z'))/86400000;
const fresh=(day,max)=>typeof day==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(day)&&
 Number.isFinite(age(day))&&age(day)>=0&&age(day)<=max;
const num=x=>typeof x==='number'&&Number.isFinite(x)?x:null;
const guardStart=source.indexOf('function officialPricingCurrent(x){');
const guardEnd=source.indexOf('function htmlEscape(',guardStart);
assert(guardStart>=0&&guardEnd>guardStart,'Canonical shared OIS source guard not found');
const guard=source.slice(guardStart,guardEnd);
const curves=new Function('FX','fresh','num',guard+source.slice(a,b)+
 ';return marketResearchCurves;')(FX,fresh,num);
const real=JSON.parse(fs.readFileSync('live_data/sections/OIS_OPERATIONAL_VIEW.json','utf8'));
const official=Object.entries(real.currencies).filter(([c,r])=>
 r.operational_status==='GREEN_OFFICIAL'&&r.official_status==='ACTIVE'&&
 r.quality==='OFFICIAL_CERTIFIED'&&r.backtest_eligible_as_official===true&&fresh(r.as_of,4))
 .map(([c])=>c).sort();
assert.deepEqual(curves(real).map(x=>x.k).sort(),official,'live certified scope reconciliation');
assert(official.includes('GBP'),'need one verified source as synthetic template');
const novel=structuredClone(real);
const clone=structuredClone(real.currencies.GBP);
clone.source='SYNTHETIC_OFFICIAL_FIFTH_SOURCE_FIXTURE_NOT_FOR_PUBLICATION';
novel.currencies.USD=clone;
const approved=[...official.filter(c=>c!=='USD'),'USD'].sort();
assert.deepEqual(curves(novel).map(x=>x.k).sort(),approved,
 'fifth independently certified source must appear without a hardcoded currency list');
function excluded(mut,label){
 const changed=structuredClone(novel);mut(changed.currencies.USD);
 assert(!curves(changed).some(x=>x.k==='USD'),label);
}
excluded(x=>x.operational_status='GREEN_ESTIMATED','estimated cannot become official');
excluded(x=>x.operational_status='WITHHELD','withheld cannot become official');
excluded(x=>x.quality='ESTIMATED_INFORMATIONAL','secondary quality rejected');
excluded(x=>x.official_status='WITHHELD','not active official source');
excluded(x=>x.backtest_eligible_as_official=false,'not certified as official');
excluded(x=>x.as_of='2026-10-15','dated but stale source');
excluded(x=>x.horizons['6m'].policy_delta_bp=null,'incomplete tenor excluded');
excluded(x=>x.horizons['12m'].policy_delta_bp=NaN,'non-finite delta excluded');
console.log('CONTROL_ROOM_DYNAMIC_CERTIFIED_G8_SCOPE_FIFTH_SOURCE_FAIL_CLOSED_PASS',
 JSON.stringify({current:official.length,expanded:approved.length,negative:8}));
