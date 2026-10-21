/* Exact production Rates dossier function, tested with a synthetic
   separately-certified fifth source. No browser, network or data mutation. */
'use strict';
const fs=require('node:fs'),assert=require('node:assert/strict');
const source=fs.readFileSync('site/control-room-preview/home-navigation-v10.js','utf8');
const from=source.indexOf('function marketSourceReadinessHtml(view,operational){');
const to=source.indexOf('\nfunction mountMarketResearch(',from);
assert(from>0&&to>from);
const FX=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
const FLAG=Object.fromEntries(FX.map(c=>[c,'']));
const htmlEscape=x=>String(x).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;');
const today='2026-10-21',dateAge=d=>(Date.parse(today+'T00:00:00Z')-Date.parse(d+'T00:00:00Z'))/86400000;
const fresh=(day,days)=>typeof day==='string'&&dateAge(day)>=0&&dateAge(day)<=days;
const fn=new Function('FX','FLAG','htmlEscape','fresh',source.slice(from,to)+
 ';return marketSourceReadinessHtml;')(FX,FLAG,htmlEscape,fresh);
const view=JSON.parse(fs.readFileSync('live_data/sections/OIS_SOURCE_READINESS_VIEW.json','utf8'));
const op=JSON.parse(fs.readFileSync('live_data/sections/OIS_OPERATIONAL_VIEW.json','utf8'));
function ids(html){return [...html.matchAll(/data-source-ccy="([A-Z]{3})"/g)].map(x=>x[1]);}
const baseline=fn(view,op);
assert.deepEqual(ids(baseline),['USD','EUR','CHF','NZD']);
assert(baseline.includes('4 dossier di accesso'));
assert(!baseline.includes('Stato delle fonti da aggiornare'));
const confirmed=structuredClone(op),revised=structuredClone(view);
confirmed.currencies.USD=structuredClone(op.currencies.GBP);
confirmed.summary.green_official++;
confirmed.summary.operational_green++;
confirmed.summary.operational_withheld--;
delete revised.currencies.USD;
revised.blocked_currency_count--;
revised.operational_summary=structuredClone(confirmed.summary);
const next=fn(revised,confirmed);
assert.deepEqual(ids(next),['EUR','CHF','NZD']);
assert(next.includes('3 dossier di accesso'));
assert(!next.includes('USD ·'));
assert(next.includes('Nessun dato indicativo è promosso'));
const before=fn(view,confirmed);
assert(before.includes('Stato delle fonti da aggiornare'),'old registry cannot be called current');
assert.deepEqual(ids(before),[],'stale registry must fail closed');
const forged=structuredClone(revised);
forged.currencies.EUR.usable_for_policy_pricing=true;
assert.deepEqual(ids(fn(forged,confirmed)),[]);
const fake=structuredClone(confirmed);
fake.currencies.EUR.operational_status='GREEN_OFFICIAL';
assert.deepEqual(ids(fn(revised,fake)),[],'official promotion with stale dossier must fail closed');
console.log('CONTROL_ROOM_SOURCE_PENDING_DOSSIERS_DYNAMIC_CERTIFIED_FIFTH_SOURCE_PASS',{current:4,after:3,negative:3});
