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
const {parse,render,toRome,verifiedValue,watchlistAgenda}=require('../site/fx-quant-v2/next/calendar-operational-reading.js');
assert.match(html,/calendar-operational-reading\.js\?v=7/);
assert.match(html,/calendar-operational-reading\.css\?v=4/);
assert.match(app,/calendar:'\.\.\/\.\.\/\.\.\/live_data\/sections\/CALENDAR_OPERATIONAL_VIEW\.json'/);
assert.match(app,/FXQuantMacroCalendar\?\.render\?\.\(calendarFeed,dayNow\(\),Date\.now\(\),n\)/);
assert.match(app,/operationalCalendar/);
assert.match(css,/max-width:860px/);
assert.match(css,/cal-event-actions/);
assert.match(css,/focus-visible/);
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
const cadSeed=JSON.parse(read('live_data/sections/MACRO_RELEASE_OFFICIAL_SEED_V1.json')).events
 .filter(e=>e.ccy==='CAD'&&e.title==='Consumer Price Index'&&e.date>='2026-11-16');
assert.deepEqual(cadSeed.slice(0,2).map(e=>[e.date,e.reference_period]),
 [['2026-11-16','October 2026'],['2026-12-14','November 2026']]);
const cadFixture={events:cadSeed.map(e=>({...e,status:'UPCOMING'}))};
const cadBefore=parse(cadFixture,'2026-11-16',Date.parse('2026-11-16T13:29Z'));
assert.equal(cadBefore.events[0].romeTime,'14:30');
assert.equal(cadBefore.events[0].actual,null);
const cadAfter=parse(cadFixture,'2026-11-16',Date.parse('2026-11-16T13:30Z'));
assert.equal(cadAfter.needsReview[0].reference,'October 2026');
assert.equal(cadAfter.needsReview[0].actual,null);
assert.equal(cadAfter.events[0].reference,'November 2026');
const cadHtml=render(cadFixture,'2026-11-16',Date.parse('2026-11-16T13:29Z'));
assert.match(cadHtml,/Canada · indice dei prezzi al consumo \(CPI\)/);
assert(cadHtml.includes(cadSeed[0].source_url));
const swissCalendar={events:[{ccy:'CHF',date:'2026-11-16',time_local:'09:00',timezone:'Europe/Zurich',
 event_type:'GROWTH',title:'Swiss GDP flash',source_family:'SECO',status:'UPCOMING'}]};
const swissActual={category:'MACRO_OFFICIAL_ACTUAL',confidence:'A',event_key:'CHF|2026-11-16|GROWTH|Swiss GDP flash',
 ccy:'CHF',event_type:'GROWTH',as_of:'2026-11-16',title:'Svizzera · PIL flash, trimestre su trimestre: +0,2%',
 source_url:'https://www.seco.admin.ch/en/gdp-flash',first_runner_observed_at_utc:'2026-11-16T10:53:39Z'};
const newsWith=item=>({schema:'GMFQ_NEWS_PULSE_OPERATIONAL_V1',items:[item]});
const swissAt=(clock,item=swissActual)=>parse(swissCalendar,'2026-11-16',Date.parse('2026-11-16T'+clock+'Z'),newsWith(item));
assert.equal(swissAt('07:59').events.length,1);
assert.equal(swissAt('10:53:38').needsReview.length,1,'A clock alone cannot verify the outcome');
assert.equal(swissAt('10:53:39').published.length,1);
assert.equal(swissAt('10:53:39').needsReview.length,0);
for(const field of [{as_of:'2026-11-15'},{ccy:'CAD'},{event_type:'INFLATION'},
 {event_key:'CHF|2026-11-16|GROWTH|Swiss GDP final'},{category:'MACRO'},{confidence:'B'},
 {first_runner_observed_at_utc:'2026-11-16T07:59:59Z'},{source_url:'javascript:alert(1)'}]){
 assert.equal(swissAt('11:00',{...swissActual,...field}).needsReview.length,1);
}
const swissPublished=render(swissCalendar,'2026-11-16',Date.parse('2026-11-16T11:00Z'),newsWith(swissActual));
assert.match(swissPublished,/Pubblicati oggi/);
assert.match(swissPublished,/PIL flash, trimestre su trimestre: \+0,2%/);
assert(swissPublished.includes(swissActual.source_url));
assert(!swissPublished.includes('Oggi · risultato ancora da verificare'));
assert.equal(parse(swissCalendar,'2026-11-17',Date.parse('2026-11-17T11:00Z'),newsWith(swissActual)).published.length,0);
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
for(const route of ['rates','currencies','pairs']){
 assert(safe.includes('data-cal-research="'+route+'"'),
  'Every macro event should offer a direct research route: '+route);
}
assert(safe.includes('data-cal-currency="GBP"')&&safe.includes('data-cal-pair="EURGBP"'),
 'UK GDP research path must select GBP and a canonical EUR/GBP example');
assert(safe.includes('href="#pairs?pair=EURGBP"'),'Calendar links must open the specific pair in a new tab');
assert(safe.includes('cal-event-evidence')&&safe.includes('Fonte, consenso e verifiche dopo l’evento'),
 'Source, consensus, quality and post-event controls must remain accessible');
const swissUpcoming=render(swissCalendar,'2026-11-16',Date.parse('2026-11-16T07:59Z'));
assert(swissUpcoming.includes('Svizzera · PIL flash')&&swissUpcoming.includes('Titolo originale: Swiss GDP flash'),
 'Italian first-read titles must preserve exact original event name in evidence');
assert(app.includes("e.target.closest('[data-cal-research]')")&&
 app.includes("if(mode==='pairs'&&openPair(calendarResearch.dataset.calPair))return;")&&
 app.includes("if(location.hash==='#'+mode)render();"),
 'Click handler must open verified FX research with no duplicate route painting');
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
assert(postHtml.includes('data-cal-pair="EURGBP"'),
 'A past scheduled UK release remains research-accessible without a fabricated actual');
assert(!postHtml.includes('BUY GBP')&&!postHtml.includes('LONG EURGBP'),
 'Calendar must not generate long/short instructions');
const missingTime=structuredClone(data);
missingTime.events.unshift({ccy:'USD',date:'2026-11-12',title:'FOMC press briefing',
 event_type:'CENTRAL_BANK_DECISION',status:'UPCOMING'});
const noClock=parse(missingTime,'2026-11-12',Date.parse('2026-11-12T13:00:00Z'));
assert(noClock.needsReview.some(e=>e.title==='FOMC press briefing'&&
 e.reviewReason==='ORARIO_NON_VERIFICATO'),
 'Same-day item without trusted hour must not be asserted future');
const nextDay=parse(historicalData,'2026-11-13',Date.parse('2026-11-13T12:00:00Z'));
assert(!nextDay.needsReview.some(e=>e.ccy==='GBP'),'Do not keep stale prior-day event indefinitely');

const agendaSeed={...cadFixture,schema:'GMFQ_CALENDAR_OPERATIONAL_VIEW_V3',last_checked_at_utc:'2026-11-16T10:00:00Z'};
const overnight={ccy:'USD',date:'2026-11-15',time_local:'19:30',timezone:'America/New_York',
 title:'Overnight release',event_type:'INFLATION',importance:'HIGH',quality:'OFFICIAL_CONFIRMED',status:'UPCOMING'};
const sameDayUnknown={...overnight,ccy:'EUR',date:'2026-11-16',time_local:null,title:'Ora sconosciuta'};
const nextDayUnknown={...sameDayUnknown,date:'2026-11-17',title:'Riunione in attesa di orario'};
const cadOctober=agendaSeed.events[0];
const agendaFixture={...agendaSeed,last_checked_at_utc:'2026-11-15T22:00:00Z',events:[
 nextDayUnknown,cadOctober,overnight,sameDayUnknown,
 {...nextDayUnknown,importance:'MEDIUM',title:'Evento secondario'},
 {...nextDayUnknown,quality:'UNVERIFIED',title:'Evento non ufficiale'}
]};
const agendaAt=time=>watchlistAgenda(agendaFixture,'2026-11-16',Date.parse(time));
const earlyAgenda=agendaAt('2026-11-15T23:15Z');
assert.deepEqual(earlyAgenda.map(e=>[e.ccy,e.day,e.romeTime]),[
 ['USD','2026-11-16','01:30'],['CAD','2026-11-16','14:30'],['EUR','2026-11-17',null]
]);
assert.match(earlyAgenda[1].label,/Canada · indice dei prezzi al consumo/);
assert.equal(agendaAt('2026-11-16T13:30Z')[0].title,nextDayUnknown.title);
assert.equal(watchlistAgenda(agendaFixture,'2026-11-25',Date.parse('2026-11-25T10:00Z')),null);
assert.equal(watchlistAgenda({...agendaFixture,last_checked_at_utc:'2026-11-17T00:00Z'},
 '2026-11-16',Date.parse('2026-11-16T13:30Z')),null);
assert(render(agendaFixture,'2026-11-16',Date.parse('2026-11-16T13:29Z'))
 .includes('data-cal-event="'+earlyAgenda[1].key+'"'));

const empty=parse(null,now);assert.equal(empty.total,0);
assert(render(null,now).includes('Calendario non disponibile'));
const newYearFixture={...agendaFixture,events:[
 ...agendaFixture.events,{...nextDayUnknown,date:'2027-01-05'}
]};
assert.deepEqual(parse(newYearFixture,'2027-01-01',Date.parse('2027-01-01T12:00:00Z'))
 .events.map(e=>e.day),['2027-01-05']);
assert.equal(parse(newYearFixture,'2027-01-06',Date.parse('2027-01-06T12:00:00Z')).total,0);
console.log('NEXT_MACRO_CALENDAR_G8_LIFECYCLE_TODAY_POSTEVENT_NO_FAKE_ACTUAL_PASS');
