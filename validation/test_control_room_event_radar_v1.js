#!/usr/bin/env node
'use strict';
// Deterministic boundary test: exercise the SAME pure eventRadarRows function
// embedded in the active Preview. No API calls or fabricated production feed.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const src=fs.readFileSync('site/control-room-preview/home-navigation-v10.js','utf8');
const start=src.indexOf('function eventRadarRows(data,now=new Date()){');
const end=src.indexOf('async function mountHomeEventRadar(doc){',start);
assert(start>=0&&end>start,'active Event Risk source function not found');
const extracted=src.slice(start,end);
const FX=['USD','EUR','GBP','JPY','AUD','CAD','NZD','CHF'];
const context={
  FX,
  romeTodayIso:()=> '2026-10-22',
  fresh:(d,days)=>d==='2026-10-22'&&days===3,
  Date,Set
};
vm.createContext(context);
vm.runInContext(extracted,context);
const radar=context.eventRadarRows;
assert.equal(typeof radar,'function');
const now=new Date('2026-10-22T12:00:00Z');
const base={
 schema:'GMFQ_CALENDAR_OPERATIONAL_VIEW_V3',
 status:'ACTIVE_CB_PLUS_MACRO_OFFICIAL_WITH_SECONDARY_CONTEXT',
 generated_at_utc:'2026-10-22T10:00:00Z',
 scope:{central_bank_schedule:'ACTIVE_OFFICIAL',
   macro_release_schedule:'ACTIVE_OFFICIAL_VERIFIED_SEED',
   consensus_context_only:true,core_score_impact:0},
 events:[
  {ccy:'NZD',date:'2026-10-22',event_type:'INFLATION',
    title:'NZ CPI (may already be published)',quality:'OFFICIAL_CONFIRMED',
    importance:'HIGH',source_layer:'MACRO_RELEASE_OFFICIAL_SEED_V1',
    source_family:'Stats NZ',consensus_status:'AVAILABLE',
    consensus:'0.8%',consensus_provider:'FOREX_FACTORY_FAIR_ECONOMY_WEEKLY'},
  {ccy:'JPY',date:'2026-10-23',event_type:'INFLATION',
    title:'Japan CPI',quality:'OFFICIAL_CONFIRMED',importance:'HIGH',
    source_layer:'MACRO_RELEASE_OFFICIAL_SEED_V1',source_family:'Japan statistics',
    time_local:'08:30',timezone:'Asia/Tokyo',
    consensus_status:'AVAILABLE',consensus:'2.1%',
    consensus_provider:'FOREX_FACTORY_FAIR_ECONOMY_WEEKLY'},
  {ccy:'USD',date:'2026-10-28',event_type:'CENTRAL_BANK_DECISION',
    title:'Federal Reserve decision',quality:'OFFICIAL_SCHEDULE_FROM_CERTIFIED_CB_LAYER',
    source_layer:'NATIVE_CB_DATA',bank:'Fed',importance:'HIGH'},
  {ccy:'CHF',date:'2026-11-03',event_type:'INFLATION',
    title:'Swiss CPI provisional date',quality:'OFFICIAL_PROVISIONAL',
    source_layer:'MACRO_RELEASE_OFFICIAL_SEED_V1',
    source_family:'FSO',importance:'STANDARD'}
 ]
};
const rows=radar(structuredClone(base),now);
assert.equal(rows.length,3,'do not display same-day publication as upcoming');
assert.deepEqual(Array.from(rows,x=>x.ccy),['JPY','USD','CHF']);
assert.equal(rows[0].timeLocal,'08:30');
assert.equal(rows[0].timezone,'Asia/Tokyo');
assert.equal(rows[0].consensus,'2.1%');
assert.equal(rows[0].isCB,false);
assert.equal(rows[1].isCB,true);
assert.equal(rows[1].consensus,null);
assert.equal(rows[2].quality,'OFFICIAL_PROVISIONAL');

function mutate(f){
  const x=structuredClone(base);f(x);return radar(x,now);
}
assert.equal(mutate(x=>x.scope.core_score_impact=1).length,0);
assert.equal(mutate(x=>x.scope.consensus_context_only=false).length,0);
assert.equal(mutate(x=>x.generated_at_utc='2026-10-26T09:00:00Z').length,0);
assert.equal(mutate(x=>x.generated_at_utc='not-a-timestamp').length,0);
assert.equal(mutate(x=>x.events=[]).length,0);
assert.equal(mutate(x=>x.schema='WRONG').length,0);

const invalid=mutate(x=>{
 x.events[1].quality='ESTIMATED';
 x.events[2].source_layer='UNVERIFIED';
 x.events[3].date='2026-12-24';
});
assert.equal(invalid.length,0,'reject unverified/proxy/far-dated inputs');

const spoofed=mutate(x=>{
 x.events[1].consensus_provider='UNVERIFIED PROVIDER';
 x.events[1].time_local='25:99';
});
assert.equal(spoofed.length,3);
assert.equal(spoofed[0].consensus,null,'consensus remains secondary-only');
assert.equal(spoofed[0].timeLocal,null,'invalid time cannot be represented as verified');

assert(src.includes('const rows=eventRadarRows(calendar);'));
assert(src.includes("host.dataset.signalEffect='NONE'"));
assert(src.includes("at<=today"),'today must be excluded without source availability time');
assert(src.includes('data-event-quality'));
console.log('CONTROL_ROOM_EVENT_RISK_FUTURE_PIT_GUARDS_PASS');
