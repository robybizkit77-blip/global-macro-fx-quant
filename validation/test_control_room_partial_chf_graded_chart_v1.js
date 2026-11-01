'use strict';
/* Test current independently-audited G8 curve slots AND a synthetic
 * partial CHF source fixture. The real CHF source gained valid March 2027
 * 6M evidence: never freeze 2026-10-30 interim source coverage in CI.
 * Neither real nor synthetic futures are official OIS policy curves.
 */
const assert=require('node:assert/strict'),fs=require('node:fs');
const addon=require('../site/control-room-preview/ois-pricing-estimates-v1.js');
const src=fs.readFileSync('site/control-room-preview/home-navigation-v10.js','utf8');
const start=src.indexOf('function marketResearchGraded(ois,proxy){');
const finish=src.indexOf('function marketResearchSecondary(data){',start);
assert(start>=0&&finish>start,'source-graded plot API must exist');
const fragment=src.slice(start,finish);
const FX=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
const now='2026-11-01';
const today=()=>now,number=x=>typeof x==='number'&&Number.isFinite(x)?x:null;
const freshness=(str,max)=>{
 if(!/^\d{4}-\d\d-\d\d$/.test(str||''))return false;
 const dt=Date.parse(str+'T00:00:00Z');
 const gap=(Date.parse(now+'T00:00:00Z')-dt)/86400000;
 return Number.isInteger(gap)&&gap>=0&&gap<=max;
};
const api=new Function('window','FX','romeTodayIso','num','fresh','COLOR','fmt',
 fragment+';return {marketResearchGraded,marketResearchGradedSvg};')(
 {GMFQ_OIS_RESEARCH_V1:{matrix:addon.matrix}},FX,today,number,freshness,
 Object.fromEntries(FX.map((c,i)=>[c,['#fff','#ccc','#999','#888','#777','#666','#555','#444'][i]])),
 (v,n=2)=>Number(v).toFixed(n));
const srcFeed=JSON.parse(fs.readFileSync('live_data/sections/OIS_OPERATIONAL_VIEW.json'));
const bb=JSON.parse(fs.readFileSync('live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json'));
const liveRows=api.marketResearchGraded(srcFeed,bb);
const liveMatrix=addon.matrix(srcFeed,bb,now);
const primary=addon.view(liveMatrix);
const actualCoverage=FX.filter(k=>liveMatrix.find(r=>r.ccy===k)&&
  ['3m','6m','12m'].every(t=>Number.isFinite(liveMatrix.find(r=>r.ccy===k).points[t]?.value))).length;
assert(primary.includes('data-g8-estimated-curve-coverage="8/8"'));
assert(primary.includes('data-complete-tenors="'+actualCoverage+'/8"'),
 'Complete-tenor tally must follow independently verified current source');
assert.equal(liveRows.length,8,'All eight currencies must be displayed');
const chfLive=liveMatrix.find(r=>r.ccy==='CHF');
assert(chfLive&&['3m','6m','12m'].every(t=>Number.isFinite(chfLive.points[t]?.value)),
 'Actual CHF accrual-start mapped 3M/6M/12M futures should remain visible');
// The negative fixture models missing 3M/6M quotes WITHOUT changing repo feeds.
const partialFeed=structuredClone(srcFeed);
for(const term of ['3m','6m']){
  partialFeed.currencies.CHF.horizons[term].quote_timestamp_verified=false;
}
const rows=api.marketResearchGraded(partialFeed,bb);
const partialPrimary=addon.view(addon.matrix(partialFeed,bb,now));
assert(partialPrimary.includes('data-complete-tenors="7/8"'));
const primaryChf=partialPrimary.match(/<article class="gmfq-mini-curve" data-chart-ccy="CHF"[\s\S]*?<\/article>/);
assert(primaryChf,'CHF must have its own primary mini-chart even with one tenor');
assert(primaryChf[0].includes('data-points="1"'));
assert(primaryChf[0].includes('data-joined="false"'));
assert(primaryChf[0].includes('Solo 12M'));
assert(primaryChf[0].includes('PUNTO ISOLATO, NON CURVA'));
assert(primaryChf[0].includes('<svg ')&&primaryChf[0].includes('<circle '));
assert(!primaryChf[0].includes('<path '),'one CHF dot must never draw an implied futures curve');

assert.equal(rows.length,8,'G8 must be visible from actually sourced current points');
assert.deepEqual(new Set(rows.map(x=>x.k)),new Set(FX));
const chf=rows.find(x=>x.k==='CHF');
assert(chf,'CHF source-graded futures must not be fully hidden');
assert.equal(chf.tier,'PROXY');
assert.equal(chf.joined,false);
assert.equal(chf.verifiedTenors,1);
assert.deepEqual(chf.pts,[null,null,srcFeed.currencies.CHF.horizons['12m'].rate]);
assert.deepEqual(chf.dates,[null,null,'2026-10-30']);
assert.deepEqual(chf.missingTenors,['3m','6m']);
assert.equal(rows.filter(x=>x.verifiedTenors===3).length,7);
const html=api.marketResearchGradedSvg(rows);
assert(html.includes('data-currencies="8"'));
const group=html.match(/<g data-graded-ccy="CHF"[\s\S]*?<\/g>/);
assert(group,'CHF individual source evidence must be drawn');
assert(group[0].includes('data-verified-tenors="1"'));
assert(group[0].includes('data-joined="false"'));
assert(group[0].includes('CHF 12M '+srcFeed.currencies.CHF.horizons['12m'].rate.toFixed(3)+
 '% · '+srcFeed.currencies.CHF.horizons['12m'].quote_as_of+' · PROXY · SCADENZA ISOLATA NON CURVA'));
assert(!group[0].includes('CHF 3M')&&!group[0].includes('CHF 6M'));
assert(!group[0].includes('<polyline'),'never connect unavailable contract tenors');
assert.equal((group[0].match(/<circle /g)||[]).length,1);
const bad=structuredClone(partialFeed);
bad.currencies.CHF.horizons['12m'].quote_timestamp_verified=false;
const missing=api.marketResearchGraded(bad,bb);
assert(!missing.find(x=>x.k==='CHF'),'unverified CHF must disappear rather than infer an OIS curve');
const wrongExpiry=structuredClone(partialFeed);
wrongExpiry.currencies.CHF.horizons['12m'].expiration='2029-12-14';
assert(!api.marketResearchGraded(wrongExpiry,bb).find(x=>x.k==='CHF'),
 'future contract outside 12M expiry window must not be coerced to OIS');
const wrongMath=structuredClone(partialFeed);
wrongMath.currencies.CHF.horizons['12m'].futures_price=97;
assert(!api.marketResearchGraded(wrongMath,bb).find(x=>x.k==='CHF'),
 'wrong 100-price minus yield identity must be rejected');
assert(!html.includes('CHF 3M 0.000%')&&!html.includes('CHF 6M 0.000%'),
 'missing points cannot become zero-rate placeholders');
console.log('CHF_PARTIAL_FUTURES_G8_VISIBLE_NO_SYNTHETIC_CURVE_PASS',
 JSON.stringify({currencies:rows.length,chf_tenors:chf.verifiedTenors,
 official_ois_claims:0,synthetic_points:0}));
