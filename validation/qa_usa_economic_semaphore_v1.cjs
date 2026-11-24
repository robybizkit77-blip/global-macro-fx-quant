'use strict';
/* Historical QA retained at original path; covers current G8 extension. */
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const base=path.resolve(__dirname,'..');
const {model,render,parsePeriod,cycleMetric,coverage}=require(path.join(base,'site/fx-quant-v2/next/recession-traffic-light-v1.js'));
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
const manualPsi=structuredClone(NZpsi);
manualPsi.series[0].quality='SOURCE_VERIFIED_MANUAL_NONPIT';
manualPsi.series[0].manual_verified_on='2026-11-24';
manualPsi.series[0].source_page='https://businessnz.org.nz/psi/pre-election-drinks';
manualPsi.series[0].source_file='BusinessNZ · verifica manuale 2026-11-24';
assert.equal(model(catalog,'2026-11-24','NZD',manualPsi).find(x=>x.key==='services').signal.tone,'green');
assert.match(render({catalog,esc,dayNow:()=>'2026-11-24',country:'NZD',overlay:manualPsi}),/verificato manualmente/);
assert.equal(model(catalog,'2027-04-01','NZD',manualPsi).find(x=>x.key==='services').signal.tone,'neutral');
const manualTampered=structuredClone(manualPsi);
manualTampered.series[0].source_page='https://somethingelse.com/fake';
assert.equal(model(catalog,'2026-11-24','NZD',manualTampered).find(x=>x.key==='services').signal.tone,'neutral');

// An old service survey remains readable, but cannot silently stay green/red.
const euroStale=model(catalog,'2026-11-24','EUR').find(x=>x.key==='services');
assert.equal(euroStale.signal.tone,'neutral','July services data are stale in late November');
assert.ok(euroStale.items[0].stale,'Explicit stale marker needed');
assert.equal(euroStale.items[0].verdict,null,'Stale observation must not generate a direction');
const freshEuro={
 schema:'GMFQ_G8_SEMAPHORE_SUPPLEMENT_V1',series:[{
  ccy:'EUR',area:'services',id:'SEM_G8_EUR_SERVICES',
  source_series_id:'TEIBS020_BS-SCI-BAL_SA_EA21',
  label:'DG ECFIN services confidence (EA21, SA)',unit:'saldo fiducia',
  frequency:'M',metric_kind:'points',quality:'SOURCE_REVISED_RESEARCH_NOT_PIT',
  dates:['2026-09','2026-10'],values:[3.1,3.8],
  source_file:'Eurostat / DG ECFIN teibs020',
  source_page:'https://ec.europa.eu/eurostat/databrowser/view/teibs020/default/table?lang=en'
 }]};
const euroUpgraded=model(catalog,'2026-11-24','EUR',freshEuro).find(x=>x.key==='services');
assert.equal(euroUpgraded.signal.tone,'green','Fresh official EA21 survey supersedes July');
assert.equal(euroUpgraded.items[0].period,'2026-10');
assert.equal(euroUpgraded.items[0].current,3.8);
assert.match(render({catalog,esc,dayNow:()=>'2026-11-24',country:'EUR',overlay:freshEuro}),/teibs020/);
const wrongEuro=structuredClone(freshEuro);
wrongEuro.series[0].source_series_id='UNRELATED';
assert.equal(model(catalog,'2026-11-24','EUR',wrongEuro).find(x=>x.key==='services').signal.tone,'neutral');
const olderEuro=structuredClone(freshEuro);
olderEuro.series[0].dates=['2026-05','2026-06'];
assert.equal(model(catalog,'2026-11-24','EUR',olderEuro).find(x=>x.key==='services').signal.tone,'neutral');
const euroNextYear=model(catalog,'2028-01-01','EUR',freshEuro).find(x=>x.key==='services');
assert.equal(euroNextYear.signal.tone,'neutral');
// New official current observation may replace an incomplete/stale primary composite
// without erasing historical canonical series in the detail.
const USfresh={
 schema:'GMFQ_G8_SEMAPHORE_SUPPLEMENT_V1',series:[{
  ccy:'USD',area:'industry',id:'SEM_G8_USD_INDUSTRY',source_series_id:'INDPRO',
  label:'Produzione industriale Fed (indice reale SA)',unit:'indice 2017=100',
  dates:['2026-09','2026-10'],values:[103.0,103.4],frequency:'M',
  metric_kind:'percent',up_good:true,quality:'SOURCE_REVISED_RESEARCH_NOT_PIT',
  source_file:'Federal Reserve via FRED',source_page:'https://fred.stlouisfed.org/series/INDPRO'
 }]};
const currentUS=model(catalog,'2026-11-24','USD',USfresh).find(x=>x.key==='industry');
assert.equal(currentUS.signal.tone,'green');
assert.equal(currentUS.signalSource,'fallback');
assert.equal(currentUS.items.length,3,'Preserve two dated official canonical indicators for context');
assert.equal(currentUS.items[0].period,'2026-10');
assert.equal(currentUS.expected,1,'Only the current official substitute is signal eligible');
assert.match(render({catalog,esc,dayNow:()=>'2026-11-24',country:'USD',overlay:USfresh}),
 /Segnale da fonte supplementare aggiornata/);
const fakeFred=structuredClone(USfresh);
fakeFred.series[0].source_series_id='WRONG';
assert.equal(model(catalog,'2026-11-24','USD',fakeFred).find(x=>x.key==='industry').signal.tone,'neutral');
const UScredit=structuredClone(USfresh);
UScredit.series[0].area='credit';
UScredit.series[0].id='SEM_G8_USD_CREDIT';
UScredit.series[0].source_series_id='DRTSCILM';
UScredit.series[0].source_page='https://fred.stlouisfed.org/series/DRTSCILM';
UScredit.series[0].frequency='Q';
UScredit.series[0].metric_kind='points';
UScredit.series[0].unit='net tightening share';
UScredit.series[0].dates=['2026-Q2','2026-Q3'];
UScredit.series[0].values=[1.0,8.0];
UScredit.series[0].up_good=false;
assert.equal(model(catalog,'2026-11-24','USD',UScredit).find(x=>x.key==='credit').signal.tone,'red',
  'Credit tightening increases should be an adverse signal');
const EAfresh={
 schema:'GMFQ_G8_SEMAPHORE_SUPPLEMENT_V1',series:[{
  ccy:'EUR',area:'demand',id:'SEM_G8_EUR_DEMAND',
  source_series_id:'STS_TRTU_M_EA21_VOL_SLS_G47_SCA_I21',
  label:'Eurostat real retail index',unit:'indice 2021=100',
  dates:['2026-08','2026-09'],values:[102.1,103.0],
  frequency:'M',metric_kind:'percent',up_good:true,quality:'SOURCE_REVISED_RESEARCH_NOT_PIT',
  source_file:'Eurostat',source_page:'https://ec.europa.eu/eurostat/databrowser/view/sts_trtu_m/default/table?lang=en'
 }]};
assert.equal(model(catalog,'2026-11-24','EUR',EAfresh).find(x=>x.key==='demand').signal.tone,'green');
assert.equal(model(catalog,'2028-01-01','EUR',EAfresh).find(x=>x.key==='demand').signal.tone,'neutral');

const nextSources={
 schema:'GMFQ_G8_SEMAPHORE_SUPPLEMENT_V1',
 series:[{
  ccy:'GBP',area:'industry',id:'SEM_G8_GBP_INDUSTRY',
  source_series_id:'ONS_K222_DIOP',source_file:'ONS',
  source_page:'https://www.ons.gov.uk/economy/economicoutputandproductivity/output/timeseries/k222/diop',
  label:'Indice della produzione industriale UK (volumi reali SA)',
  unit:'indice CVMSA',frequency:'M',metric_kind:'percent',up_good:true,
  dates:['2026-08','2026-09'],values:[99.2,99.9],
  quality:'SOURCE_REVISED_RESEARCH_NOT_PIT'
 },{
  ccy:'NZD',area:'house',id:'SEM_G8_NZD_HOUSE',
  source_series_id:'STATSNZ_NEWDWELLINGS_SA',source_file:'Stats NZ',
  source_page:'https://www.stats.govt.nz/information-releases/building-consents-issued-september-2026/',
  label:'New dwellings consented SA',unit:'dwellings SA',
  frequency:'M',metric_kind:'percent',up_good:true,
  dates:['2026-08','2026-09'],values:[3495,3218],
  quality:'SOURCE_REVISED_RESEARCH_NOT_PIT'
 }]};
assert.equal(model(catalog,'2026-11-24','GBP',nextSources).find(r=>r.key==='industry').signal.tone,'green');
assert.equal(model(catalog,'2026-11-24','NZD',nextSources).find(r=>r.key==='house').signal.tone,'red');
const forgedNZ=structuredClone(nextSources);
forgedNZ.series[1].source_page='https://another.stats.govt.nz/fake';
assert.equal(model(catalog,'2026-11-24','NZD',forgedNZ).find(r=>r.key==='house').signal.tone,'neutral');
const manualDwelling=structuredClone(nextSources);
manualDwelling.series[1].quality='SOURCE_VERIFIED_MANUAL_NONPIT';
manualDwelling.series[1].manual_verified_on='2026-11-24';
assert.equal(model(catalog,'2026-11-24','NZD',manualDwelling).find(x=>x.key==='house').signal.tone,'red');
assert.match(render({catalog,esc,dayNow:()=>'2026-11-24',country:'NZD',overlay:manualDwelling}),/verificato manualmente/);
assert.equal(model(catalog,'2027-04-01','NZD',manualDwelling).find(x=>x.key==='house').signal.tone,'neutral');
const heatmap=render({catalog,esc,dayNow:()=>'2026-11-24',country:'USD',overlay:USfresh});
assert.equal((heatmap.match(/class="sem-mini sem-cell (?:green|red|amber|neutral)" title=/g)||[]).length,56,'56 accessible direction cells');
assert.match(heatmap,/role="progressbar" aria-label="Copertura G8" aria-valuenow="\d+" aria-valuemin="0" aria-valuemax="56"/);
assert.equal((heatmap.match(/class="sem-overview-kpi /g)||[]).length,4);
assert.match(heatmap,/class="sem-method"><summary>Metodo, soglie e fonti/);
assert.equal((heatmap.match(/class="sem-area-judgment"/g)||[]).length,7);
assert.match(heatmap,/Attuale · 2026-10/);
assert.match(heatmap,/Precedente · 2026-09/);
assert.match(heatmap,/class="sem-value sem-change"/);
assert.match(heatmap,/class="sem-history"/);
console.log('OK: G8 economic semaphore — 8 economies, 7 areas, data age, dates, source gaps, HTML');

 // Phase 1 cycle engine: separate the regime from the last change and
 // require exact contiguous history for persistence/acceleration.
 const psiMetric={id:'psi',kind:'points',diffusionThreshold:50,minimum:.2,upGood:true};
 const sample=(id,values,dates=['2026-07','2026-08','2026-09','2026-10'])=>({source_series_id:id,dates,values});
 for(const [values,phase,level,dir,persist] of [
   [[40,42,43,46],'recovery',-1,1,3],
   [[62,60,58,55],'slowdown',1,-1,3],
   [[45,46,51,55],'expansion',1,1,3],
   [[52,48,46,43],'contraction',-1,-1,3]
 ]){
   const z=cycleMetric(psiMetric,sample('psi',values),'2026-11-24','M');
   assert.equal(z.phase,phase);assert.equal(z.level,level);assert.equal(z.direction,dir);
   assert.equal(z.persistence,persist);assert.equal(z.historySufficient,true);
 }
 const two=cycleMetric(psiMetric,sample('psi',[43,46],['2026-09','2026-10']),'2026-11-24','M');
 assert.equal(two.phase,'recovery');assert.equal(two.persistence,1);assert.equal(two.acceleration,null);assert.equal(two.historySufficient,false);
 const flat=cycleMetric(psiMetric,sample('psi',[55,55,55,55]),'2026-11-24','M');
 assert.equal(flat.phase,null);assert.equal(flat.level,1);assert.equal(flat.direction,0);
 const gap=cycleMetric(psiMetric,sample('psi',[45,46,48],['2026-06','2026-07','2026-10']),'2026-11-24','M');
 assert.equal(gap.direction,null);assert.equal(gap.observations,1);
 assert.equal(cycleMetric(psiMetric,sample('psi',[40,42,43,46]),'2026-11-24','M',true).phase,null);
 const nominal=cycleMetric({id:'RBA_BUSINESS_CREDIT_GROWTH_MM',kind:'points',upGood:true},
   sample('RBA_BUSINESS_CREDIT_GROWTH_MM',[.4,.6,.8,1]),'2026-11-24','M');
 assert.equal(nominal.phase,null);assert.equal(nominal.direction,1);
 const nominalStock=cycleMetric({id:'CA_MORTGAGE_OUTSTANDING_UNINSURED_history_value',upGood:true},
   sample('nominal',[100,102,105,109]),'2026-11-24','M');
 assert.equal(nominalStock.phase,null);assert.equal(nominalStock.level,null);
 const realGrowth=cycleMetric({id:'JPNPRMNTO01GPSAM',kind:'points',upGood:true},
   sample('JPNPRMNTO01GPSAM',[-3,-2,-1,-.5]),'2026-11-24','M');
 assert.equal(realGrowth.phase,'recovery');assert.equal(realGrowth.acceleration,-1);
 const monthlyDates=Array.from({length:14},(_,i)=>new Date(Date.UTC(2025,8+i,1)).toISOString().slice(0,7));
 const realLevels=cycleMetric({id:'INDPRO',upGood:true},sample('INDPRO',
   [100,101,102,103,104,105,106,107,108,109,110,111,104,106],monthlyDates),'2026-11-24','M');
 assert.equal(realLevels.basis,'REAL_ACTIVITY_YOY_GROWTH');assert.equal(realLevels.phase,'expansion');
 assert.equal(realLevels.acceleration,null);assert.equal(realLevels.historySufficient,false);
 const shortReal=cycleMetric({id:'INDPRO',upGood:true},sample('INDPRO',[100,101,102,103]),'2026-11-24','M');
 assert.equal(shortReal.phase,null);assert.equal(shortReal.direction,null);
 assert.match(nzHTML,/Lettura ciclica/);
 console.log('ECONOMIC_CYCLE_PHASE1_PASS');
