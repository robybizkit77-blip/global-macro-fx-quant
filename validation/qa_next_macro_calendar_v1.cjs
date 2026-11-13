'use strict';
/* Calendar in News: source dates, Rome conversion, no fabricated surprises. */
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'..');
const read=p=>fs.readFileSync(path.join(root,p),'utf8');
const lib=read('site/fx-quant-v2/next/calendar-operational-reading.js');
const html=read('site/fx-quant-v2/next/index.html');
const app=read('site/fx-quant-v2/next/app.js');
const css=read('site/fx-quant-v2/next/calendar-operational-reading.css');
new vm.Script(lib,{filename:'calendar-operational-reading.js'});
new vm.Script(app,{filename:'app.js'});
const {parse,render,toRome,verifiedValue}=require('../site/fx-quant-v2/next/calendar-operational-reading.js');
assert.match(html,/calendar-operational-reading\.js\?v=2/);
assert.match(html,/calendar-operational-reading\.css\?v=2/);
assert.match(app,/calendar:'\.\.\/\.\.\/\.\.\/live_data\/sections\/CALENDAR_OPERATIONAL_VIEW\.json'/);
assert.match(app,/FXQuantMacroCalendar\?\.render/);
assert.match(app,/operationalCalendar/);
assert.match(css,/max-width:860px/);
const data=JSON.parse(read('live_data/sections/CALENDAR_OPERATIONAL_VIEW.json'));
const now='2026-11-11', testNowMs=Date.parse('2026-11-11T12:00:00Z');
const result=parse(data,now,testNowMs);
assert(Array.isArray(result.events));
assert(result.events.every(x=>x.date>=now),'Do not show a past appointment as upcoming');
assert(result.events.every(x=>x.ccy&&x.why&&x.verify&&x.pairs));
assert(result.events.every(x=>x.consensus===null),'Existing 0-consensus official feed cannot invent consensus values');
assert.equal(result.consensusReady,0);
assert.equal(result.events.filter(x=>x.kind==='Pubblicazione macro').length,result.macro);
assert.equal(result.events.filter(x=>x.kind==='Riunione banca centrale').length,result.meetings);
assert.deepEqual(toRome('2026-11-12','07:00','Europe/London'),{
 date:'2026-11-12',time:'08:00',timestamp:Date.parse('2026-11-12T07:00:00Z')});
assert.equal(toRome('2026-11-16','09:00','Europe/Zurich').time,'09:00');
assert.equal(toRome('2026-11-19','11:30','Australia/Sydney').time,'01:30');
assert.equal(toRome('2026-11-20','08:30','Asia/Tokyo').time,'00:30');
assert.equal(toRome('2026-07-10','08:00','America/New_York').time,'14:00');
assert.equal(toRome('2026-11-16',null,'Europe/Zurich'),null);
assert.equal(toRome('2026-03-29','02:30','Europe/Rome'),null,'Nonexistent DST local hour is not invented');
const uk=result.events.find(e=>e.ccy==='GBP'&&e.title.includes('GDP'));
if(uk)assert.equal(uk.romeTime,'08:00');
const nz=result.events.find(e=>e.ccy==='NZD'&&e.title.includes('Gross domestic product'));
if(nz)assert.equal(nz.romeTime,null,'An official event without local release hour must not get an invented hour');
assert.equal(verifiedValue({consensus:0.4,consensus_status:'NOT_PRESENT'},'consensus'),null);
assert.equal(verifiedValue({consensus:0.4,consensus_status:'VERIFIED',consensus_source:'Reuters'},'consensus'),null,
 'No point-in-time consensus without pre-release vintage');
assert.equal(verifiedValue({actual:0.4,status:'UPCOMING',actual_status:'OFFICIAL_VERIFIED',
 actual_first_observed_at_utc:'2026-11-11T08:00:00Z'},'actual'),null);
const malicious=structuredClone(data);
malicious.events.unshift({ccy:'GBP',date:'2026-11-12',time_local:'07:00',timezone:'Europe/London',
 event_type:'GROWTH',status:'UPCOMING',title:'<img src=x onerror=alert(1)>',
 consensus_status:'NOT_PRESENT',consensus:99});
const safe=render(malicious,now,testNowMs);
assert(safe.includes('&lt;img src=x onerror=alert(1)&gt;'));
assert(!safe.includes('<img src=x'));
assert(safe.includes('Consenso: non certificato'));
assert(safe.includes('Effettivo: non ancora pubblicato/verificato'));
assert(safe.includes('Quali dati potrebbero cambiare le tesi FX?'));
assert.match(safe,/Altri \d+ eventi del calendario/);
// Historical date-sensitive regression needs its own immutable event fixture:
// the production calendar rightly removes 12 Nov GDP after its release.
// The real live feed above is still checked for schema, XSS and missing values.
const historicalData={...structuredClone(data),
 last_checked_at_utc:'2026-11-11T23:33:00Z',
 events:[...data.events,{
  ccy:'GBP',date:'2026-11-12',time_local:'07:00',
  timezone:'Europe/London',event_type:'GROWTH',
  status:'UPCOMING',importance:'HIGH',quality:'OFFICIAL_CONFIRMED',
  title:'UK GDP first quarterly estimate',source_family:'ONS',
  consensus_status:'NOT_PRESENT',actual_status:'NOT_PRESENT'
 }]
};
// Real clock regression: UK GDP scheduled at 08:00 Rome on 12 November.
// After the release window it must move to "review", NOT become an actual.
const before=parse(historicalData,'2026-11-12',Date.parse('2026-11-12T06:30:00Z'));
assert(before.events.some(e=>e.ccy==='GBP'&&e.title.includes('GDP')));
assert(!before.needsReview.some(e=>e.ccy==='GBP'));
const after=parse(historicalData,'2026-11-12',Date.parse('2026-11-12T13:00:00Z'));
assert(!after.events.some(e=>e.ccy==='GBP'&&e.title.includes('GDP')),
 'Elapsed UK release must not remain in next-up list');
assert(after.needsReview.some(e=>e.ccy==='GBP'&&e.reviewReason==='ORARIO_PROGRAMMATO_TRASCORSO'));
const postHtml=render(historicalData,'2026-11-12',Date.parse('2026-11-12T13:00:00Z'));
assert(postHtml.includes('Oggi · risultato ancora da verificare'));
assert(postHtml.includes('Orario programmato trascorso'));
assert(postHtml.includes('Effettivo: non verificato dal feed'));
// UTC 23:33 on 11 November is already 00:33 on 12 November in Rome.
assert(!postHtml.includes('Feed non ricontrollato oggi'),
 'UTC day must not create a false Rome-local staleness warning');
assert(postHtml.includes('12/11/2026')&&postHtml.includes('00:33'));
const oldFeed=structuredClone(historicalData);
oldFeed.last_checked_at_utc='2026-11-11T12:00:00Z';
assert(render(oldFeed,'2026-11-12',Date.parse('2026-11-12T13:00:00Z'))
 .includes('Feed non ricontrollato oggi'),
 'Truly prior-day Rome feed must be disclosed as stale');
assert(postHtml.includes('Prossimi eventi'));
const missingTime=structuredClone(data);
missingTime.events.unshift({ccy:'USD',date:'2026-11-12',title:'FOMC press briefing',
 event_type:'CENTRAL_BANK_DECISION',status:'UPCOMING'});
const noClock=parse(missingTime,'2026-11-12',Date.parse('2026-11-12T13:00:00Z'));
assert(noClock.needsReview.some(e=>e.title==='FOMC press briefing'&&
 e.reviewReason==='ORARIO_NON_VERIFICATO'),
 'Same-day item without trusted hour must not be asserted future');
const nextDay=parse(historicalData,'2026-11-13',Date.parse('2026-11-13T12:00:00Z'));
assert(!nextDay.needsReview.some(e=>e.ccy==='GBP'),'Do not keep stale prior-day event indefinitely');

const empty=parse(null,now);assert.equal(empty.total,0);
assert(render(null,now).includes('Calendario non disponibile'));
assert.equal(parse(data,'2027-01-01').total,0);
console.log('NEXT_MACRO_CALENDAR_G8_LIFECYCLE_TODAY_POSTEVENT_NO_FAKE_ACTUAL_PASS');
