'use strict';
/* Historical QA retained at original path; covers current G8 extension. */
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const base=path.resolve(__dirname,'..');
const {model,render,parsePeriod,coverage}=require(path.join(base,'site/fx-quant-v2/next/recession-traffic-light-v1.js'));
const catalog=JSON.parse(fs.readFileSync(path.join(base,'live_data/sections/MACRO_SERIES.json'),'utf8'));
const asof='2026-11-23',dayNow=()=>asof;
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
assert.deepEqual(coverage,['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD']);
const expected=['Immobiliare','Lavoro','Manifattura','Indicatore anticipatore','Consumi e domanda','Credito'];
for(const currency of coverage){
 const rows=model(catalog,asof,currency);
 assert.equal(rows.length,6,'All G8 economies need the same six named areas');
 assert.deepEqual(rows.map(r=>r.name),expected);
 for(const row of rows){
  assert.ok(['red','amber','green','neutral'].includes(row.signal.tone));
  assert.ok(row.items.every(v=>v===null||typeof v.period==='string'));
  if(!row.expected)assert.equal(row.signal.tone,'neutral');
  if(row.signal.tone!=='neutral')assert.equal(row.items.filter(v=>v&&v.verdict!==null).length,row.expected);
 }
 const html=render({catalog,esc,dayNow,country:currency});
 assert.match(html,/Il semaforo economico/);
 assert.match(html,/Consultazione 2026-11-23/);
 assert.match(html,/periodi mostrati NON equivalgono alle date di pubblicazione/i);
 assert.match(html,/data-ms-country="USD"/);
 assert.match(html,/data-ms-country="NZD"/);
 assert.match(html,/aria-label="Semaforo economico /);
 assert.match(html,/non sono un ranking di forza FX/i);
 assert.ok(!/(?:NaN|undefined)/.test(html),'No broken JS placeholders in rendered HTML');
}
// Specific gaps must remain neutral, not model-generated or backfilled.
const nz=model(catalog,asof,'NZD');
for(const key of ['house','industry','leading','credit']){
 assert.equal(nz.find(r=>r.key===key).signal.tone,'neutral');
}
assert.match(render({catalog,esc,dayNow,country:'USD'}),/SLOOS/);
assert.match(render({catalog,esc,dayNow,country:'USD'}),/osservazioni datate/i);
assert.match(render({catalog,esc,dayNow,country:'GBP'}),/Regno Unito/);
assert.match(render({catalog,esc,dayNow,country:'JPY'}),/BoJ/);
assert.match(render({catalog,esc,dayNow,country:'NZD'}),/Nessuna serie idonea nel feed attuale/);
// Underlying data may not be available after a severe lag: no false green/red.
for(const currency of coverage){
 assert.ok(model({},asof,currency).every(x=>x.signal.tone==='neutral'));
 assert.ok(model(catalog,'2028-11-23',currency).every(x=>x.signal.tone==='neutral'));
}
const samples={
 '2026Q2':'2026-06-30','2026-Q3':'2026-09-30',
 '31/07/2026':'2026-07-31','31 Jul 2026':'2026-07-31',
 'Jul-26':'2026-07-31','2026/09':'2026-09-30',
 '2026-07-01T00:00:00Z':'2026-07-01',
 '2026-07-01':'2026-07-01'};
for(const [input,output] of Object.entries(samples))
 assert.equal(parsePeriod(input),output,'Date parser should support source notation '+input);
assert.equal(parsePeriod('2026-02-30'),null,'Reject invalid calendar dates');
const legacy=render({catalog,esc,dayNow}); // default USA for existing callers
assert.match(legacy,/Stati Uniti/);
// No future observations, no duplicate-date pair: same-date revisions do not
// masquerade as successive releases in the comparison engine.
const artificial={USD:[{id:'US_PERMIT_history_PERMIT',dates:['2026-07','2026-08','2026-08','2027-01'],
 values:[120,125,127,999],frequency:'M',source_file:'source.csv'}]};
const one=model(artificial,asof,'USD').find(r=>r.key==='house');
assert.equal(one.items[0].current,127);
assert.equal(one.items[0].previous,120);
assert.equal(one.items[0].period,'2026-08');
assert.equal(one.signal.tone,'neutral','Missing second housing metric cannot be silently ignored');
console.log('OK: G8 economic semaphore — 8 economies, 6 areas, data age, dates, source gaps, HTML');
