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
const expected=['Immobiliare','Lavoro','Manifattura','Servizi','Indicatore anticipatore','Consumi e domanda','Credito'];
for(const currency of coverage){
 const rows=model(catalog,asof,currency);
 assert.equal(rows.length,7,'All G8 economies need the same seven named areas');
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
// Services signals are descriptive activity/survey momentum, not service CPI.
for(const c of coverage){
 const services=model(catalog,asof,c).find(x=>x.key==='services');
 assert.ok(services,'Services must be present for '+c);
}
assert.equal(model(catalog,asof,'EUR').find(x=>x.key==='services').expected,1);
assert.equal(model(catalog,asof,'JPY').find(x=>x.key==='services').expected,1);
assert.equal(model(catalog,asof,'USD').find(x=>x.key==='services').signal.tone,'neutral');
assert.match(render({catalog,esc,dayNow,country:'EUR'}),/Inflazione servizi \(contesto, fuori dal semaforo\)/);
assert.match(render({catalog,esc,dayNow,country:'JPY'}),/Tankan grandi imprese non manifatturiere/);
assert.match(render({catalog,esc,dayNow,country:'USD'}),/sette aree/);
// Specific gaps must remain neutral, not model-generated or backfilled.
const nz=model(catalog,asof,'NZD');
for(const key of ['house','industry','credit']){
 assert.equal(nz.find(r=>r.key===key).signal.tone,'neutral');
}
assert.match(render({catalog,esc,dayNow,country:'USD'}),/SLOOS/);
assert.match(render({catalog,esc,dayNow,country:'USD'}),/osservazioni datate/i);
assert.match(render({catalog,esc,dayNow,country:'GBP'}),/Regno Unito/);
assert.match(render({catalog,esc,dayNow,country:'JPY'}),/BoJ/);
assert.match(render({catalog,esc,dayNow,country:'NZD'}),/Nessuna serie idonea nel feed attuale/);
assert.equal(nz.find(r=>r.key==='leading').signal.tone,'green','RBNZ one-year unemployment expectations cover NZD leading surveys');
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
// Supplemental observations are allowed only for a missing category, and
// must carry an exact schema, source identity, freshness and revised-data label.
const overlay={
 schema:'GMFQ_G8_SEMAPHORE_SUPPLEMENT_V1',
 series:[{
  ccy:'AUD',area:'industry',id:'SEM_G8_AUD_INDUSTRY',
  label:'Manufacturing growth QoQ',unit:'% QoQ',frequency:'Q',
  metric_kind:'points',quality:'SOURCE_REVISED_RESEARCH_NOT_PIT',
  dates:['2026-Q1','2026-Q2'],values:[1.40122,-1.93794],
  source_file:'OECD tramite FRED',source_page:'https://fred.stlouisfed.org/series/PRMNTO01AUQ657S',
  observation_as_of:'2026-Q2'
 }]
};
const aud=model(catalog,asof,'AUD',overlay);
const manufacturing=aud.find(x=>x.key==='industry');
assert.equal(manufacturing.signal.tone,'red');
assert.equal(manufacturing.items[0].period,'2026-Q2');
assert.equal(model(catalog,asof,'USD',overlay).find(x=>x.key==='industry').expected,2,
 'Supplement must not replace canonical USD industry metrics');
assert.equal(model(catalog,asof,'NZD',overlay).find(x=>x.key==='industry').signal.tone,'neutral',
 'Supplement for AUD must not leak to NZD');
assert.match(render({catalog,esc,dayNow,country:'AUD',overlay}),/Fonte e metodologia/);
const tampered=structuredClone(overlay);
tampered.series[0].quality='NOT_VERIFIED';
assert.equal(model(catalog,asof,'AUD',tampered).find(x=>x.key==='industry').signal.tone,'neutral');
const tooOld=model(catalog,'2028-11-23','AUD',overlay);
assert.equal(tooOld.find(x=>x.key==='industry').signal.tone,'neutral');

// PSI has two independent dimensions: 50-level and recent change.
const NZpsi={schema:'GMFQ_G8_SEMAPHORE_SUPPLEMENT_V1',series:[{
 ccy:'NZD',area:'services',id:'SEM_G8_NZD_SERVICES',
 label:'BNZ–BusinessNZ PSI servizi destagionalizzato',unit:'indice diffusione (soglia 50)',
 dates:['2026-09','2026-10'],values:[50.9,51.7],frequency:'M',
 metric_kind:'points',diffusion_threshold:50,
 quality:'SOURCE_REVISED_RESEARCH_NOT_PIT',
 source_file:'BusinessNZ',source_page:'https://businessnz.org.nz/psi'
}]};
const nzServices=model(catalog,'2026-11-24','NZD',NZpsi).find(x=>x.key==='services');
assert.equal(nzServices.signal.tone,'green');
assert.equal(nzServices.items[0].metric.diffusionThreshold,50);
const nzHTML=render({catalog,esc,dayNow:()=>'2026-11-24',country:'NZD',overlay:NZpsi});
assert.match(nzHTML,/Livello: espansione \(PSI sopra 50\)/);
assert.match(nzHTML,/Direzione: indice in accelerazione/);
assert.match(nzHTML,/Industria e servizi · direzione del ciclo/);
const psiDecel=structuredClone(NZpsi);
psiDecel.series[0].values=[55,52];
assert.equal(model(catalog,'2026-11-24','NZD',psiDecel).find(x=>x.key==='services').signal.tone,'red');
const psiDecelHTML=render({catalog,esc,dayNow:()=>'2026-11-24',country:'NZD',overlay:psiDecel});
assert.match(psiDecelHTML,/Livello: espansione \(PSI sopra 50\)/);
assert.match(psiDecelHTML,/Direzione: indice in rallentamento/);
const psiFake=structuredClone(NZpsi);
psiFake.series[0].source_page='https://example.com/psi';
assert.equal(model(catalog,'2026-11-24','NZD',psiFake).find(x=>x.key==='services').signal.tone,'neutral');
const psiWrongArea=structuredClone(NZpsi);
psiWrongArea.series[0].ccy='AUD';
assert.equal(model(catalog,'2026-11-24','AUD',psiWrongArea).find(x=>x.key==='services').signal.tone,'neutral');
console.log('OK: G8 economic semaphore — 8 economies, 7 areas, data age, dates, source gaps, HTML');
