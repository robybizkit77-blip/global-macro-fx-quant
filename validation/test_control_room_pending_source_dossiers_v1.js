/* Exact production Rates dossier function, tested with a synthetic
   separately-certified fifth source. No browser, network or data mutation. */
'use strict';
const fs=require('node:fs'),assert=require('node:assert/strict');
const source=fs.readFileSync('site/control-room-preview/home-navigation-v10.js','utf8');
const from=source.indexOf('function marketSourceReadinessHtml(view,operational,graded=[]){');
const to=source.indexOf('\nfunction mountMarketResearch(',from);
assert(from>0&&to>from);
const FX=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
const FLAG=Object.fromEntries(FX.map(c=>[c,'']));
const htmlEscape=x=>String(x).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;');
const view=JSON.parse(fs.readFileSync('live_data/sections/OIS_SOURCE_READINESS_VIEW.json','utf8'));
const op=JSON.parse(fs.readFileSync('live_data/sections/OIS_OPERATIONAL_VIEW.json','utf8'));
// Pin the source-freshness clock to the certified fixture's date. The live
// timestamp is checked elsewhere; a source-transition unit test must not
// change verdict when the daily publisher advances from 21 to 22 October.
assert.match(view.as_of,/^20\d{2}-\d{2}-\d{2}$/);
const today=view.as_of,dateAge=d=>(Date.parse(today+'T00:00:00Z')-Date.parse(d+'T00:00:00Z'))/86400000;
const fresh=(day,days)=>typeof day==='string'&&dateAge(day)>=0&&dateAge(day)<=days;
const num=x=>x===null||x===undefined||x===''?null:Number.isFinite(Number(x))?Number(x):null;
const fmt=(x,d=2)=>Number(x).toFixed(d);
const fn=new Function('FX','FLAG','htmlEscape','fresh','num','fmt',source.slice(from,to)+
 ';return marketSourceReadinessHtml;')(FX,FLAG,htmlEscape,fresh,num,fmt);
function ids(html){return [...html.matchAll(/data-source-ccy="([A-Z]{3})"/g)].map(x=>x[1]);}
const pending=FX.filter(c=>['WITHHELD','GREEN_ESTIMATED'].includes(op.currencies[c]?.operational_status));
assert.deepEqual(Object.keys(view.currencies).sort(),[...pending].sort(),'readiness identities must match source status');
const baseline=fn(view,op);
assert.deepEqual(ids(baseline),pending,'the Home must disclose all pending sources');
assert(baseline.includes(pending.length+' dossier di accesso'));
assert(!baseline.includes('Stato delle fonti da aggiornare'));
// Study-only quotes are visible even though the OFFICIAL source still needs access.
const eur=fn(view,op,[{k:'EUR',tier:'MIXED',pts:[2.5125,2.8325,3.0975],
 dates:['2026-10-30','2026-10-30','2026-11-02']}]);
assert(eur.includes('data-source-study="EUR" data-study-points="3"'));
assert(eur.includes('6M ≈2.833% (2026-10-30)'));
assert(eur.includes('fonte ufficiale ancora non certificata'));
assert(eur.includes('NON curva OIS')===false); // never falsely declare a curve
const confirmed=structuredClone(op),revised=structuredClone(view);
assert(pending.includes('USD'),'test requires an initially pending USD lane');
confirmed.currencies.USD=structuredClone(op.currencies.GBP);
// When USD was GREEN_ESTIMATED, promotion increases official sources without
// increasing total GREEN. Rebuild counts from the simulated live states.
const statuses=FX.map(c=>confirmed.currencies[c].operational_status);
confirmed.summary={
 g8_total:FX.length,
 green_official:statuses.filter(x=>x==='GREEN_OFFICIAL').length,
 green_estimated:statuses.filter(x=>x==='GREEN_ESTIMATED').length,
 operational_green:statuses.filter(x=>x.startsWith('GREEN_')).length,
 operational_withheld:statuses.filter(x=>x==='WITHHELD').length
};
delete revised.currencies.USD;
revised.blocked_currency_count=Object.keys(revised.currencies).filter(
 c=>confirmed.currencies[c].operational_status==='WITHHELD').length;
revised.operational_summary=structuredClone(confirmed.summary);
const after=pending.filter(c=>c!=='USD');
const next=fn(revised,confirmed);
assert.deepEqual(ids(next),after,'newly certified source must leave unresolved dossiers');
assert(next.includes(after.length+' dossier di accesso'));
assert(!next.includes('USD ·'));
assert(next.includes('Nessun dato indicativo è promosso'));
const before=fn(view,confirmed);
assert(before.includes('Stato delle fonti da aggiornare'),'old registry cannot be called current');
assert.deepEqual(ids(before),[],'stale registry must fail closed');
const expired=structuredClone(view);
expired.as_of=new Date(Date.parse(today+'T00:00:00Z')-4*86400000).toISOString().slice(0,10);
assert.deepEqual(ids(fn(expired,op)),[],'expired 4-day source-registry timestamp must fail closed');
const forged=structuredClone(revised);
forged.currencies.EUR.usable_for_policy_pricing=true;
assert.deepEqual(ids(fn(forged,confirmed)),[]);
const fake=structuredClone(confirmed);
fake.currencies.EUR.operational_status='GREEN_OFFICIAL';
assert.deepEqual(ids(fn(revised,fake)),[],'official promotion with stale dossier must fail closed');
console.log('CONTROL_ROOM_SOURCE_PENDING_DOSSIERS_DYNAMIC_CERTIFIED_FIFTH_SOURCE_PASS',{
 current:pending.length,after:after.length,estimated:op.summary.green_estimated,
 negative:4,as_of:today
});
