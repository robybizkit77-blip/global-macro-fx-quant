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
 'crossRiskWtiFutures','homeCommodityResearchReadout'].map(exact).join('\n')+'\nhomeCommodityResearchReadout;';
const residual=JSON.parse(fs.readFileSync('live_data/sections/ESTIMATED_RESIDUAL_GAPS.json','utf8'));
const today=['GOLD.market_proxy','BRENT.market_proxy','WTI.market_proxy'].map(k=>residual.lanes[k].proxy_as_of).sort().at(-1);
assert.match(today,/^20\d{2}-\d{2}-\d{2}$/);
const tomorrow=new Date(Date.parse(today+'T00:00:00Z')+86400000).toISOString().slice(0,10);
const context={
 num:x=>typeof x==='number'&&Number.isFinite(x)?x:null,
 romeCalendarAge:d=>{
  if(typeof d!=='string'||!/^20\d{2}-\d{2}-\d{2}$/.test(d))return null;
  const t=Date.parse(d+'T00:00:00Z'),now=Date.parse(today+'T00:00:00Z');
  return Number.isFinite(t)?(now-t)/86400000:null;
 },Date,Number,Array,Math
};
const evaluate=vm.runInNewContext(script,context);
const model=JSON.parse(fs.readFileSync('live_data/sections/D.json','utf8'));
const val=read=>JSON.parse(JSON.stringify(evaluate(read,model)));
const current=val(residual);
assert.equal(current.sourceEffect,'NONE');
assert.equal(current.pairEffect,'NONE');
assert.equal(current.gold.grade,'SECONDARY_FUTURES');
assert.equal(current.gold.asof,residual.lanes['GOLD.market_proxy'].proxy_as_of);
assert.equal(current.gold.delta,residual.lanes['GOLD.market_proxy'].change_1d_pct);
const brentAge=(Date.parse(today+'T00:00:00Z')-
  Date.parse(residual.lanes['BRENT.market_proxy'].proxy_as_of+'T00:00:00Z'))/86400000;
assert.equal(Number.isInteger(brentAge),true,'dated Brent market reference');
const historicalBrent=vm.runInNewContext(
  ['crossRiskBrent'].map(exact).join('\n')+'\ncrossRiskBrent',
  {num:context.num,romeCalendarAge:context.romeCalendarAge,Date,Number,Array,Math,crossGoldAge:context.romeCalendarAge}
)(residual);
assert.equal(historicalBrent.state,brentAge<=3?'SECONDARY_RECENT':'SECONDARY_HISTORICAL');
assert.equal(historicalBrent.asof,residual.lanes['BRENT.market_proxy'].proxy_as_of);
if(brentAge<=3){
  assert.equal(current.brent.grade,'SECONDARY_FUTURES');
  assert.equal(current.brent.asof,residual.lanes['BRENT.market_proxy'].proxy_as_of);
  assert.equal(current.brent.delta,residual.lanes['BRENT.market_proxy'].change_1d_pct);
}else{
  assert.equal(current.brent,null,'historical Brent must not appear as a current daily move');
}
assert.equal(current.wti.asof,model.risk.WTI.last_date);
assert.equal(current.wtiFutures.grade,'SECONDARY_FUTURES');
assert.equal(current.wtiFutures.symbol,'CL=F');
assert.equal(current.wtiFutures.asof,residual.lanes['WTI.market_proxy'].proxy_as_of);
assert.equal(current.wtiFutures.value,residual.lanes['WTI.market_proxy'].value);
const wtiAge=(Date.parse(today+'T00:00:00Z')-
 Date.parse(model.risk.WTI.last_date+'T00:00:00Z'))/86400000;
assert.equal(current.wti.grade,wtiAge<=3?'OFFICIAL_RECENT':'OFFICIAL_HISTORICAL');
assert.equal(current.wti.benchmark,'RWTC');
const reject=(mutate,field,reason)=>{
 const cloned=structuredClone(residual);mutate(cloned);
 assert.equal(val(cloned)[field],null,reason);
};
reject(x=>{x.governance.core_score_effect='ALLOW'},'gold','never promote score-changing proxy');
reject(x=>{x.lanes['GOLD.market_proxy'].vendor_symbol='XAUUSD'},'gold','GC futures source identity');
reject(x=>{x.lanes['BRENT.market_proxy'].vendor_symbol='RBRTE'},'brent','BZ futures source identity');
reject(x=>{x.lanes['WTI.market_proxy'].vendor_symbol='BZ=F'},'wtiFutures','CL futures source identity');
reject(x=>{x.lanes['WTI.market_proxy'].source_endpoint='https://invalid.example'},'wtiFutures','WTI source URL');
reject(x=>{x.lanes['WTI.market_proxy'].proxy_as_of=tomorrow},'wtiFutures','WTI future observation date');
reject(x=>{x.lanes['GOLD.market_proxy'].proxy_as_of=tomorrow},'gold','future dated Gold');
reject(x=>{x.lanes['BRENT.market_proxy'].proxy_as_of='2026-10-21'},'brent','old Brent not called current');
reject(x=>{x.lanes['GOLD.market_proxy'].change_1d_pct=null},'gold','missing daily return is not zero');
reject(x=>{x.lanes['BRENT.market_proxy'].source_endpoint='https://unverified.example'},'brent','Brent exact source');
assert.equal(val(null).gold,null);
assert.equal(val(null).brent,null);
assert.equal(val(null).wtiFutures,null);
const corrupted=structuredClone(model);corrupted.risk.WTI.benchmark_key='BRENT';
assert.equal(evaluate(residual,corrupted).wti,null,'different crude benchmark not treated as EIA WTI');
const noWti=structuredClone(model);noWti.risk.WTI.last_date='2026-10-30';
assert.equal(evaluate(residual,noWti).wti,null,'last-date must match historical close');
assert(src.includes("mountHomeCommodityContext(doc,model);"));
assert(src.includes("crossRiskCard('WTI_FUT',wf"),'actual v10 Cross-Asset must render CL=F card');
assert(src.includes('data-source="wti-futures"'),'dated WTI futures source must be shown');
assert(src.includes('Futures secondari ≠ prezzi spot/settlement certificati.'));
console.log('HOME_COMMODITIES_SOURCE_GRADE_DATES_PASS',JSON.stringify(current));
