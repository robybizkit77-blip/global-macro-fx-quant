#!/usr/bin/env node
/* Date/quality contract only: exact source age must control Rates tutor copy. */
'use strict';
const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const source=fs.readFileSync('payload/part-07.txt','utf8');
const start=source.indexOf('function v233RatesFreshness(d,todayIso){');
const end=source.indexOf('function v478RatesTutor(c,d){',start);
assert(start>=0&&end>start,'Missing exact Rates source-age implementation');
const context={Date,Intl,Number};
vm.runInNewContext(source.slice(start,end),context,{timeout:1500});
const guard=context.v233RatesFreshness;
assert.equal(typeof guard,'function');
const raw=JSON.parse(fs.readFileSync('live_data/sections/NATIVE_RATES_DATA.json','utf8'));
const today='2026-10-30';
for(const c of ['CHF','NZD']){
  const got=guard(raw[c],today);
  assert.equal(got.current,false,c+' must not drive a current FX narrative');
  assert.equal(got.historic,true,c+' officially verified historical source');
  assert.equal(got.date,raw[c].date);
}
assert.equal(guard(raw.CHF,today).ageDays,30);
assert.equal(guard(raw.NZD,today).ageDays,14);
for(const c of ['USD','EUR','GBP','JPY','CAD','AUD']){
  assert.equal(guard(raw[c],today).current,true,c+' recent official pair unexpectedly gated');
}
const fresh=structuredClone(raw.USD);
fresh.date='2026-10-25';
fresh.history2.last_date=fresh.history10.last_date=fresh.date;
assert.equal(guard(fresh,today).current,true,'5-day maximum remains current');
fresh.date='2026-10-24';
fresh.history2.last_date=fresh.history10.last_date=fresh.date;
assert.equal(guard(fresh,today).current,false,'6-day old pair must be historical');
fresh.date='2026-10-31';
fresh.history2.last_date=fresh.history10.last_date=fresh.date;
assert.equal(guard(fresh,today).current,false,'future observations must fail closed');
fresh.date='2026-10-29';
fresh.history2.last_date=fresh.history10.last_date=fresh.date;
fresh.history2.last_value+=0.01;
assert.equal(guard(fresh,today).current,false,'broken canonical history tail must fail closed');
fresh.history2.last_value-=0.01;
fresh.quality='RESEARCH_ESTIMATED';
assert.equal(guard(fresh,today).current,false,'secondary proxy cannot be official');
assert(source.includes('const age=v233RatesFreshness(d);'),'Final visible Rates render lacks age gate');
assert(source.includes('DIREZIONE ATTUALE NON DISPONIBILE'),'No explicit suspended current momentum copy');
assert(source.includes('Nessun supporto o pressione FX corrente'),'Live FX promotion not neutralized');
assert(source.includes("v233RateCard('2Y · '+date"),'Historical value card missing');
console.log('RATES_DESK_G8_SOURCE_AGE_20261030_GREEN: CHF/NZD historic, other 6 recent, forged source withheld');
