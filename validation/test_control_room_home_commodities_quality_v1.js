#!/usr/bin/env node
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const src=fs.readFileSync('site/control-room-preview/home-navigation-v10.js','utf8');
const part=(a,b)=>{
 const start=src.indexOf(a),end=src.indexOf(b,start+a.length);
 assert(start>=0&&end>start,'function source boundaries missing: '+a+' / '+b);
 return src.slice(start,end);
};
const blocks=[
 part('function validCrossGold(', 'function crossGoldAge('),
 part('function crossGoldAge(', 'function ' /* next function not matched? */)
];
// Avoid reliance on source helper adjacency: use exact boundaries for each.
const exact=(name)=>{
 const a=src.indexOf('function '+name+'(');
 assert(a>=0,name+' missing');
 const b=src.indexOf('\nfunction ',a+10);
 return src.slice(a,b>=0?b:src.length);
};
const script=['validCrossGold','crossGoldAge','crossRiskObservation','crossRiskBrent',
 'homeCommodityResearchReadout'].map(exact).join('\n')+'\nhomeCommodityResearchReadout;';
const today='2026-11-01';
const context={
 num:x=>typeof x==='number'&&Number.isFinite(x)?x:null,
 romeCalendarAge:d=>{
  if(typeof d!=='string'||!/^20\d{2}-\d{2}-\d{2}$/.test(d))return null;
  const t=Date.parse(d+'T00:00:00Z'),now=Date.parse(today+'T00:00:00Z');
  return Number.isFinite(t)?(now-t)/86400000:null;
 },Date,Number,Array,Math
};
const evaluate=vm.runInNewContext(script,context);
const residual=JSON.parse(fs.readFileSync('live_data/sections/ESTIMATED_RESIDUAL_GAPS.json','utf8'));
const model=JSON.parse(fs.readFileSync('live_data/sections/D.json','utf8'));
const val=read=>JSON.parse(JSON.stringify(evaluate(read,model)));
const current=val(residual);
assert.equal(current.sourceEffect,'NONE');
assert.equal(current.pairEffect,'NONE');
assert.equal(current.gold.grade,'SECONDARY_FUTURES');
assert.equal(current.gold.asof,'2026-10-30');
assert.equal(current.gold.delta,residual.lanes['GOLD.market_proxy'].change_1d_pct);
assert.equal(current.brent.grade,'SECONDARY_FUTURES');
assert.equal(current.brent.asof,'2026-10-30');
assert.equal(current.brent.delta,residual.lanes['BRENT.market_proxy'].change_1d_pct);
assert.equal(current.wti.asof,model.risk.WTI.last_date);
assert.equal(current.wti.grade,'OFFICIAL_HISTORICAL');
assert.equal(current.wti.benchmark,'RWTC');
const reject=(mutate,field,reason)=>{
 const cloned=structuredClone(residual);mutate(cloned);
 assert.equal(val(cloned)[field],null,reason);
};
reject(x=>{x.governance.core_score_effect='ALLOW'},'gold','never promote score-changing proxy');
reject(x=>{x.lanes['GOLD.market_proxy'].vendor_symbol='XAUUSD'},'gold','GC futures source identity');
reject(x=>{x.lanes['BRENT.market_proxy'].vendor_symbol='RBRTE'},'brent','BZ futures source identity');
reject(x=>{x.lanes['GOLD.market_proxy'].proxy_as_of='2026-11-02'},'gold','future dated Gold');
reject(x=>{x.lanes['BRENT.market_proxy'].proxy_as_of='2026-10-21'},'brent','old Brent not called current');
reject(x=>{x.lanes['GOLD.market_proxy'].change_1d_pct=null},'gold','missing daily return is not zero');
reject(x=>{x.lanes['BRENT.market_proxy'].source_endpoint='https://unverified.example'},'brent','Brent exact source');
assert.equal(val(null).gold,null);
assert.equal(val(null).brent,null);
const corrupted=structuredClone(model);corrupted.risk.WTI.benchmark_key='BRENT';
assert.equal(evaluate(residual,corrupted).wti,null,'different crude benchmark not treated as EIA WTI');
const noWti=structuredClone(model);noWti.risk.WTI.last_date='2026-10-30';
assert.equal(evaluate(residual,noWti).wti,null,'last-date must match historical close');
assert(src.includes("mountHomeCommodityContext(doc,model);"));
assert(src.includes('Futures secondari ≠ prezzi spot/settlement certificati.'));
console.log('HOME_COMMODITIES_SOURCE_GRADE_DATES_PASS',JSON.stringify(current));
