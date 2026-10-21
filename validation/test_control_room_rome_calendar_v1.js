'use strict';
/* Deterministic timezone contract for the Italy-facing Control Room.
   Runs without network, browser or edits to historical market observations. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {romeTodayIso:oisRomeToday}=require('../site/control-room-preview/ois-pricing-estimates-v1.js');
const {romeAgeDays,readApproved,verifyPublicNzd}=require('./control_room_nzd_public_contract_v1.js');
const nav=fs.readFileSync('site/control-room-preview/home-navigation-v10.js','utf8');
const a=nav.indexOf('function romeTodayIso('),b=nav.indexOf('function htmlEscape(',a);
assert(a>0&&b>a,'Rome date helpers must be in canonical UI adapter');
const snippet=nav.slice(a,b);
assert(snippet.includes('function romeCalendarAge('));
assert(snippet.includes('function fresh('));
function navAt(instant){
 class TestDate extends Date {
   constructor(...args){super(...(args.length?args:[instant]));}
 }
 return new Function('Date','Intl',snippet+';return {romeTodayIso,romeCalendarAge,fresh};')(TestDate,Intl);
}
const cases=[
 ['2026-03-28T22:30:00Z','2026-03-28'], // before spring Sunday midnight
 ['2026-03-28T23:30:00Z','2026-03-29'], // 00:30 CET, UTC is still Saturday
 ['2026-03-29T22:30:00Z','2026-03-30'], // 00:30 CEST, UTC is Sunday
 ['2026-10-24T21:30:00Z','2026-10-24'],
 ['2026-10-24T22:30:00Z','2026-10-25'], // 00:30 CEST
 ['2026-10-25T22:30:00Z','2026-10-25'], // 23:30 CET
 ['2026-10-25T23:30:00Z','2026-10-26'], // 00:30 CET
 ['2026-10-21T00:05:00Z','2026-10-21']
];
for(const [instant,expected] of cases){
 const moment=new Date(instant),v=navAt(instant);
 assert.equal(v.romeTodayIso(),expected,'v10 adapter local day '+instant);
 assert.equal(oisRomeToday(moment),expected,'OIS addon local day '+instant);
 assert.equal(v.romeCalendarAge(expected),0,'today valid '+instant);
 assert.equal(v.fresh(expected,0),true,'display today valid '+instant);
 assert.equal(v.romeCalendarAge('2026-10-16',moment),romeAgeDays('2026-10-16',moment));
}
const midnight=navAt('2026-10-25T23:30:00Z');
assert.equal(midnight.romeCalendarAge('2026-10-25'),1);
assert.equal(midnight.romeCalendarAge('2026-10-27'),-1);
assert.equal(midnight.fresh('2026-10-27',5),false,'future official date is rejected');
assert.equal(midnight.fresh('2026-10-25',0),false,'yesterday is not today');
assert.equal(midnight.fresh('2026-10-25',1),true,'yesterday valid when allowed');
assert.equal(midnight.fresh('2026-02-30',5),false,'impossible source date rejected');
const {approved,canonical}=readApproved('.');
const onRomeMidnight=new Date('2026-10-20T22:30:00Z'); // 00:30 CEST on 21 Oct
assert.equal(oisRomeToday(onRomeMidnight),'2026-10-21');
assert.equal(romeAgeDays('2026-10-16',onRomeMidnight),5);
assert.equal(verifyPublicNzd(canonical.NZD,approved,canonical.NZD,'',onRomeMidnight).operationally_recent,false);
assert.equal(navAt('2026-10-20T22:30:00Z').fresh('2026-10-16',4),false);
const stillPriorDay=new Date('2026-10-20T21:30:00Z'); // 23:30 CEST 20 Oct
assert.equal(romeAgeDays('2026-10-16',stillPriorDay),4);
assert.equal(verifyPublicNzd(canonical.NZD,approved,canonical.NZD,'',stillPriorDay).operationally_recent,true);
assert.equal(navAt('2026-10-20T21:30:00Z').fresh('2026-10-16',4),true);
assert(nav.includes('const today=romeTodayIso(),nowMonth=today.slice(0,7)'));
assert(nav.includes('function crossGoldAge(iso){\n return romeCalendarAge(iso);'));
assert(!nav.includes('new Date().toISOString().slice(0,10)'));
console.log('CONTROL_ROOM_ROME_CIVIL_DAY_DST_SOURCE_FRESHNESS_PASS',cases.length);
