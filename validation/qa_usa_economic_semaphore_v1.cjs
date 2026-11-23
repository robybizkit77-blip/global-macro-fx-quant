'use strict';
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const base=path.resolve(__dirname,'..');
const {model,render}=require(path.join(base,'site/fx-quant-v2/next/recession-traffic-light-v1.js'));
const catalog=JSON.parse(fs.readFileSync(path.join(base,'live_data/sections/MACRO_SERIES.json'),'utf8'));
const dayNow=()=> '2026-11-23';
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const rows=model(catalog,dayNow());
assert.equal(rows.length,6);
assert.deepEqual(rows.map(x=>x.name),['Immobiliare','Lavoro','Manifattura','Indicatore anticipatore','Consumi e domanda','Credito']);
for(const row of rows){
 assert.ok(row.items.every(x=>x===null||typeof x.period==='string'));
 assert.ok(['red','amber','green','neutral'].includes(row.signal.tone));
}
const html=render({catalog,esc,dayNow});
assert.match(html,/Il semaforo economico/);
assert.match(html,/Consultazione 2026-11-23/);
assert.match(html,/presenza di dati datati/i);
assert.match(html,/SLOOS/);
assert.match(html,/periodi mostrati NON equivalgono alle date di pubblicazione/i);
assert.ok(!html.includes('NaN') && !html.includes('undefined'));
const empty=model({},dayNow());
assert.ok(empty.every(x=>x.signal.tone==='neutral'));
const ancient=model(catalog,'2028-11-23');
assert.ok(ancient.every(x=>x.signal.tone==='neutral'));
console.log('OK: semaforo macro, provenienza, limiti temporali e fallback');
