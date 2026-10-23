#!/usr/bin/env node
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('site/control-room-preview/home-navigation-v10.js','utf8');
const start=source.indexOf('function romePreviousWeekday('),
      end=source.indexOf('function mountHomeFreshnessAudit(',start);
assert(start!==-1&&end>start,'morning readout must be testable without DOM');
const get=file=>JSON.parse(fs.readFileSync('live_data/sections/'+file+'.json','utf8'));
const inputs=[get('ECB_G8_PRICE_HISTORY'),get('D'),get('PAIR_SETUP_OPERATIONAL_VIEW'),
  get('NATIVE_RATES_DATA'),get('OIS_OPERATIONAL_VIEW'),get('NEWS_PULSE_OPERATIONAL'),
  get('CALENDAR_OPERATIONAL_VIEW')];
const FX=['USD','EUR','GBP','JPY','AUD','CAD','NZD','CHF'];
const ctx={FX,num:x=>typeof x==='number'&&Number.isFinite(x)?x:null,
  romeTodayIso:(now=new Date())=>{
    const parts=new Intl.DateTimeFormat('en-US',{timeZone:'Europe/Rome',
      year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(now);
    const v=k=>parts.find(p=>p.type===k)?.value;
    return v('year')+'-'+v('month')+'-'+v('day');
  },
  fresh:(x,max)=>typeof x==='string' && Number.isFinite(Date.parse(x)) &&
    (Date.parse('2026-10-23')-Date.parse(x))/86400000 <= max &&
    (Date.parse('2026-10-23')-Date.parse(x))/86400000 >= 0,
  officialPricingCurrent:x=>x?.operational_status==='GREEN_OFFICIAL'&&
    x.official_status==='ACTIVE'&&x.quality==='OFFICIAL_CERTIFIED'&&
    x.backtest_eligible_as_official===true,
  canonicalPairMacroBaseline:(setup,model)=>setup?.macro_baseline_asof===model?.asOf?model.asOf:null};
vm.createContext(ctx);
vm.runInContext(source.slice(start,end),ctx);
const date=new Date('2026-10-23T06:00:00Z');
const inspect=(a=inputs,t=date)=>ctx.homeMorningStudySources(...a,t);
const result=inspect();
assert.equal(result.total,5);
assert.equal(result.confirmed,5,JSON.stringify(result));
assert.equal(result.mode,'DAILY_VERIFIED_WITH_GAPS');
assert.equal(result.prior,'2026-10-22');
assert.equal(result.fxDay,'2026-10-22');
assert.equal(result.vixDay,'2026-10-22');
assert.equal(result.sourceEffect,'NONE');
assert.equal(result.rateRecent.length,6);
assert.equal(result.rateLag.join(','),'NZD,CHF');
assert.equal(result.official.length,4);
assert.equal(result.estimated.length,2);
assert.equal(result.withoutOis.join(','),'EUR,NZD');
assert.equal(result.macroDay,'2026-09-25');

function altered(index,mutate){
 const x=structuredClone(inputs);mutate(x[index]);return inspect(x);
}
assert.equal(altered(0,x=>{x.last_as_of='2026-10-21'}).checks.fx,false);
assert.equal(altered(0,x=>{x.rows.at(-1).USD=null}).checks.fx,false);
assert.equal(altered(2,x=>{x.price_audit.status='FAIL'}).checks.pairs,false);
assert.equal(altered(2,x=>{x.price_asof='2026-10-21'}).checks.pairs,false);
assert.equal(altered(1,x=>{x.risk.VIX.last_date='2026-10-21'}).checks.vix,false);
assert.equal(altered(5,x=>{x.generated_at_utc='2026-10-22T06:52:00Z'}).checks.news,false);
assert.equal(altered(6,x=>{x.generated_at_utc=null}).checks.calendar,false);
// Local 00:30 Rome Friday is still Thu UTC: do not call calendar stale.
assert.equal(altered(5,x=>{x.generated_at_utc='2026-10-22T22:30:00Z'}).checks.news,true);
assert.equal(ctx.romePreviousWeekday(new Date('2026-10-26T07:00:00Z')),'2026-10-23');
const monday=structuredClone(inputs);
monday[0].last_as_of='2026-10-23';monday[0].rows.at(-1).Date='2026-10-23';
monday[2].price_asof='2026-10-23';
monday[1].risk.VIX.last_date='2026-10-23';monday[1].risk.VIX.dates[monday[1].risk.VIX.dates.length-1]='2026-10-23';
monday[5].generated_at_utc='2026-10-26T05:20:00Z';
monday[6].generated_at_utc='2026-10-26T05:20:00Z';
assert.equal(inspect(monday,new Date('2026-10-26T07:00:00Z')).prior,'2026-10-23');
assert(source.includes('gmfq-morning-study-readiness'),'readiness line must mount in existing Home research composition');
assert(source.includes('DATAI_INCOMPLETE')===false,'do not introduce an unvalidated status');
assert(source.includes("mountHomeFreshnessAudit(doc,ff.status"),'Home must render after all same-source feeds arrive');
assert(source.includes('morning.confirmed+\'/5 fonti giornaliere verificate'),'the status needs to show a precise daily-source count');
console.log('CONTROL_ROOM_HOME_0800_STUDY_READINESS_SOURCE_PARITY_PASS');
