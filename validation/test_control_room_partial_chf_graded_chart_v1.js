'use strict';
/* Prove 8 visible currency groups with ONLY actually validated listed-contract
 * expiry references: the CHF source has 12M and no usable 3M/6M on Oct30.
 * Never interpolate or relabel a futures settlement as an official OIS.
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
const rows=api.marketResearchGraded(srcFeed,bb);
assert.equal(rows.length,8,'G8 must be visible from actually sourced current points');
assert.deepEqual(new Set(rows.map(x=>x.k)),new Set(FX));
const chf=rows.find(x=>x.k==='CHF');
assert(chf,'CHF source-graded futures must not be fully hidden');
assert.equal(chf.tier,'PROXY');
assert.equal(chf.joined,false);
assert.equal(chf.verifiedTenors,1);
assert.deepEqual(chf.pts,[null,null,0.39]);
assert.deepEqual(chf.dates,[null,null,'2026-10-30']);
assert.deepEqual(chf.missingTenors,['3m','6m']);
assert.equal(rows.filter(x=>x.verifiedTenors===3).length,7);
const html=api.marketResearchGradedSvg(rows);
assert(html.includes('data-currencies="8"'));
const group=html.match(/<g data-graded-ccy="CHF"[\s\S]*?<\/g>/);
assert(group,'CHF individual source evidence must be drawn');
assert(group[0].includes('data-verified-tenors="1"'));
assert(group[0].includes('data-joined="false"'));
assert(group[0].includes('CHF 12M 0.390% · 2026-10-30 · PROXY · SCADENZA ISOLATA NON CURVA'));
assert(!group[0].includes('CHF 3M')&&!group[0].includes('CHF 6M'));
assert(!group[0].includes('<polyline'),'never connect unavailable contract tenors');
assert.equal((group[0].match(/<circle /g)||[]).length,1);
const bad=structuredClone(srcFeed);
bad.currencies.CHF.horizons['12m'].quote_timestamp_verified=false;
const missing=api.marketResearchGraded(bad,bb);
assert(!missing.find(x=>x.k==='CHF'),'unverified CHF must disappear rather than infer an OIS curve');
const wrongExpiry=structuredClone(srcFeed);
wrongExpiry.currencies.CHF.horizons['12m'].expiration='2029-12-14';
assert(!api.marketResearchGraded(wrongExpiry,bb).find(x=>x.k==='CHF'),
 'future contract outside 12M expiry window must not be coerced to OIS');
const wrongMath=structuredClone(srcFeed);
wrongMath.currencies.CHF.horizons['12m'].futures_price=97;
assert(!api.marketResearchGraded(wrongMath,bb).find(x=>x.k==='CHF'),
 'wrong 100-price minus yield identity must be rejected');
assert(!html.includes('CHF 3M 0.000%')&&!html.includes('CHF 6M 0.000%'),
 'missing points cannot become zero-rate placeholders');
console.log('CHF_PARTIAL_FUTURES_G8_VISIBLE_NO_SYNTHETIC_CURVE_PASS',
 JSON.stringify({currencies:rows.length,chf_tenors:chf.verifiedTenors,
 official_ois_claims:0,synthetic_points:0}));
