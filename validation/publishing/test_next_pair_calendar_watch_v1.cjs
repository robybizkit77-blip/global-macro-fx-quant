'use strict';
/* FX pair catalyst: only source-dated official calendar events, no invented
 * outcome, surprise, market reaction, or false future relative to local date. */
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'../..'),next='site/fx-quant-v2/next/';
const read=p=>fs.readFileSync(path.join(root,p),'utf8');
const json=p=>JSON.parse(read(p));
const ranking=require(path.join(root,next,'pair-rankings.js'));
const calendar=json('live_data/sections/CALENDAR_OPERATIONAL_VIEW.json');
const date='2026-11-12';
const pair=k=>({key:k,base:k.slice(0,3),quote:k.slice(3)});
const uk=ranking.pairCatalystWatch(pair('GBPUSD'),calendar,date);
assert.equal(uk.status,'TODAY_UNVERIFIED');
assert.equal(uk.ccy,'GBP');
assert.equal(uk.date,'2026-11-12');
assert(uk.text.includes('Era in calendario oggi GBP'));
assert(uk.text.includes('L’esito non è verificato'));
assert(uk.text.includes('dato effettivo, consenso e reazione di tassi e cambio'));
assert(!uk.text.includes('Prossimo evento pertinente: GBP'));
const swiss=ranking.pairCatalystWatch(pair('EURCHF'),calendar,date);
assert.equal(swiss.status,'FUTURE');
assert.equal(swiss.ccy,'CHF');
assert.equal(swiss.date,'2026-11-16');
assert(swiss.text.includes('data provvisoria'));
const australia=ranking.pairCatalystWatch(pair('AUDCAD'),calendar,date);
assert.equal(australia.status,'FUTURE');
assert.equal(australia.ccy,'AUD');
assert.equal(australia.date,'2026-11-19');
assert(australia.text.includes('occupazione e disoccupazione'));
const japan=ranking.pairCatalystWatch(pair('USDJPY'),calendar,date);
assert.equal(japan.status,'FUTURE');
assert.equal(japan.ccy,'JPY');
assert.equal(japan.date,'2026-11-20');
assert(japan.text.includes('persistenza dell’inflazione'));
const futureMeeting=ranking.pairCatalystWatch(pair('EURUSD'),calendar,date);
assert.equal(futureMeeting.status,'FUTURE');
assert.equal(futureMeeting.date,'2026-12-09');
assert(futureMeeting.text.includes('percorso dei tassi già prezzato'));
for(const v of ['GBPUSD','EURCHF','AUDCAD','USDJPY','EURUSD']){
 const a=ranking.pairCatalystWatch(pair(v),calendar,date);
 assert(!a.text.includes('ha sorpreso')&&!a.text.includes('mercato è salito'),
  'Never infer actual or price response from an upcoming schedule');
}
const stale={...calendar,last_checked_at_utc:'2026-11-01T00:00:00Z'};
assert.equal(ranking.pairCatalystWatch(pair('GBPUSD'),stale,date).status,'UNAVAILABLE');
const futureCheck={...calendar,last_checked_at_utc:'2026-11-13T00:00:00Z'};
assert.equal(ranking.pairCatalystWatch(pair('GBPUSD'),futureCheck,date).status,'UNAVAILABLE');
const forged={...calendar,events:[{...calendar.events[0],
 date:'2026-11-12',quality:'UNVERIFIED',title:'FAKE'},{...calendar.events[1]}]};
const foreign=ranking.pairCatalystWatch(pair('GBPUSD'),forged,date);
assert.equal(foreign.status,'NONE');
assert(!foreign.text.includes('FAKE'));
assert.equal(ranking.pairCatalystWatch({key:'GBPUSD',base:'AUD',quote:'USD'},calendar,date).status,'UNAVAILABLE');
assert.equal(ranking.pairCatalystWatch(pair('GBPUSD'),calendar,'2026-12-20').status,'UNAVAILABLE');
const app=read(next+'app.js'),index=read(next+'index.html');
assert(app.includes("pairCatalystWatch?.("));
assert(app.includes("activePair,get('calendar'),dayNow()"));
assert(app.includes('pairs-event-watch'));
assert(index.includes('pair-rankings.js?v=7'));
assert(index.includes('app.js?v=18.43-paircalendar1'));
console.log('NEXT_PAIR_CALENDAR_WATCH_V1_PASS: GBP Q3 today unverified, CHF provisional, AUD labor, JPY inflation, Fed path; source-date guards');
