'use strict';
/* Prove eight currencies, dynamic source-verified CHF SARON accrual-start
 * points and no joined indicative futures curves. Tests work both on old
 * 12M-only captures and the new valid 3M/6M/12M collector output.
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
const audited=addon.matrix(srcFeed,bb,now),primary=addon.view(audited);
const auditChf=audited.find(x=>x.ccy==='CHF');
const terms=['3m','6m','12m'];
const active=terms.filter(t=>typeof auditChf.points[t]?.value==='number');
const full=audited.filter(x=>terms.every(t=>typeof x.points[t]?.value==='number'));
assert(primary.includes('data-g8-estimated-curve-coverage="8/8"'));
assert(primary.includes('data-complete-tenors="'+full.length+'/8"'));
const primaryChf=primary.match(/<article class="gmfq-mini-curve" data-chart-ccy="CHF"[\s\S]*?<\/article>/);
assert(primaryChf,'CHF must have a primary mini-chart');
assert(primaryChf[0].includes('data-points="'+active.length+'"'));
assert(primaryChf[0].includes('data-joined="false"'));
assert(!primaryChf[0].includes('<path '),'indicative CHF futures must stay unjoined');
assert.equal((primaryChf[0].match(/<circle /g)||[]).length,active.length);
assert(active.length>=1,'available CHF quotes must not disappear from the public research chart');

assert.equal(rows.length,8,'all eight currency groups must be present');
assert.deepEqual(new Set(rows.map(x=>x.k)),new Set(FX));
const chf=rows.find(x=>x.k==='CHF');
assert(chf,'CHF source-graded futures must not be fully hidden');
assert.equal(chf.tier,'PROXY');
assert.equal(chf.joined,false);
assert.equal(chf.verifiedTenors,active.length);
assert.deepEqual(chf.pts,terms.map(t=>auditChf.points[t]?.value??null));
assert.deepEqual(chf.dates,terms.map(t=>auditChf.points[t]?.date??null));
assert.deepEqual(chf.missingTenors,terms.filter(t=>!active.includes(t)));
assert.equal(rows.filter(x=>x.verifiedTenors===3).length,full.length);

const html=api.marketResearchGradedSvg(rows);
assert(html.includes('data-currencies="8"'));
const group=html.match(/<g data-graded-ccy="CHF"[\s\S]*?<\/g>/);
assert(group);
assert(group[0].includes('data-verified-tenors="'+active.length+'"'));
assert(group[0].includes('data-joined="false"'));
assert(!group[0].includes('<polyline'),'individual CHF futures must not be connected');
assert.equal((group[0].match(/<circle /g)||[]).length,active.length);
for(const t of active){
 assert(group[0].includes('CHF '+t.toUpperCase()),
  'observed, individually audited CHF future should appear: '+t);
}

const invalid=structuredClone(srcFeed);
for(const t of terms)invalid.currencies.CHF.horizons[t].quote_timestamp_verified=false;
assert(!api.marketResearchGraded(invalid,bb).find(x=>x.k==='CHF'),
 'no unverified CHF horizons may be used');
const wrongExpiry=structuredClone(srcFeed);
wrongExpiry.currencies.CHF.horizons['12m'].expiration='2029-12-14';
const withoutWrongExpiry=api.marketResearchGraded(wrongExpiry,bb).find(x=>x.k==='CHF');
assert(!withoutWrongExpiry||withoutWrongExpiry.pts[2]===null,
 '12M expiry substitution cannot become 12M future');
const wrongMath=structuredClone(srcFeed);
wrongMath.currencies.CHF.horizons['12m'].futures_price=97;
const withoutWrongMath=api.marketResearchGraded(wrongMath,bb).find(x=>x.k==='CHF');
assert(!withoutWrongMath||withoutWrongMath.pts[2]===null,
 'wrong futures 100 minus price cannot become 12M level');
assert(!html.includes('CHF 3M 0.000%')&&!html.includes('CHF 6M 0.000%'),
 'missing points cannot become zero-rate placeholders');

console.log('CHF_PARTIAL_FUTURES_G8_VISIBLE_NO_SYNTHETIC_CURVE_PASS',
 JSON.stringify({currencies:rows.length,chf_tenors:chf.verifiedTenors,
 official_ois_claims:0,synthetic_points:0}));
