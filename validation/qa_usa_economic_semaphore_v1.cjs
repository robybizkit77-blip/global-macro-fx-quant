'use strict';
/* Historical QA retained at original path; covers current G8 extension. */
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const base=path.resolve(__dirname,'..');
const {model,render,parsePeriod,cycleMetric,cycleHistory,inflationContext,wageContext,externalContext,turningPointMonitor,macroNarrative,countryInterpretation,overviewCountry,regimePosition,chartTail,countryHistories,matchedActivityWindows,relativeActivity,comparableExports,exportSparkline,coverage}=require(path.join(base,'site/fx-quant-v2/next/recession-traffic-light-v1.js'));
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
// Live archive updates may remove the last stale US observation. Assert the
// warning exactly when the current model has a stale item, then exercise it
// unconditionally with an intentionally later consultation date.
const usHasStale=model(catalog,asof,'USD').some(r=>r.items.some(x=>x?.stale));
const usCurrentHtml=render({catalog,esc,dayNow,country:'USD'});
assert.equal(/osservazioni datate/i.test(usCurrentHtml),usHasStale);
const staleUS=model(catalog,'2028-11-23','USD');
assert.ok(staleUS.some(r=>r.items.some(x=>x?.stale)));
assert.match(render({catalog,esc,dayNow:()=> '2028-11-23',country:'USD'}),/osservazioni datate/i);
assert.match(render({catalog,esc,dayNow,country:'GBP'}),/Regno Unito/);
assert.match(render({catalog,esc,dayNow,country:'JPY'}),/BoJ/);
assert.match(render({catalog,esc,dayNow,country:'NZD'}),/Nessuna serie idonea nel feed attuale/);
assert.equal(nz.find(r=>r.key==='leading').signal.tone,'green','RBNZ one-year unemployment expectations cover NZD leading surveys');
 // A quarter-end survey label is not a publication date. Only the documented
 // already-observed terminal M15 vintage may enter the current descriptive view.
 const m15={id:'NZ_RBNZ_M15_BUSINESS_EXPECTATIONS_recent_Unemp_1Y',source_file:'NZ_RBNZ_M15_BUSINESS_EXPECTATIONS_recent.csv',dates:['2026-03','2026-06','2026-09','2026-12'],values:[5.18,5.5,5.22,5.25],last_date:'2026-12',last_value:5.25,current_vintage_provenance:{status:'RBNZ_M15_CURRENT_PUBLISHED_SURVEY_NOT_PIT',source_series_id:'RBNZ_M15_AGGREGATE_WEIGHTED_MEAN_Unemp_1Y',source_url:'https://rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/m/m15/hm15.xlsx',reference_period_semantics:'survey quarter; observed availability upper bound, not certified release date',source_series_first_release_PIT_certified:false,source_payload_sha256:'a'.repeat(64),available_by_date:'2026-11-26'}};
 const m15Item=(row,day)=>model({NZD:[row]},day,'NZD').find(r=>r.key==='leading').items[0];
 assert.equal(m15Item(m15,'2026-11-25').period,'2026-09');
 assert.equal(m15Item(m15,'2026-11-27').period,'2026-12');
 assert.equal(m15Item(m15,'2026-11-27').current,5.25);
 assert.equal(m15Item(m15,'2026-11-27').cycle.observations,4);
 assert.equal(m15Item({...m15,current_vintage_provenance:null},'2026-11-27').period,'2026-09');
 assert.equal(m15Item({...m15,current_vintage_provenance:{...m15.current_vintage_provenance,available_by_date:'2026-11-28'}},'2026-11-27').period,'2026-09');
 assert.equal(m15Item({...m15,dates:['2026-03','2026-06','2026-09','2027-03'],last_date:'2027-03'},'2026-11-27').period,'2026-09');

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

// Pin historical fallback cases to dated test data; the live archive now advances.
const oldCatalog=structuredClone(catalog);
const truncate=(ccy,id,cutoff)=>{
 const r=oldCatalog[ccy].find(x=>x.id===id);
 assert.ok(r,'Missing fixture source '+id);
 const keep=r.dates.map((p,i)=>({p,i})).filter(x=>parsePeriod(x.p)<=cutoff);
 r.dates=keep.map(x=>x.p);r.values=keep.map(x=>r.values[x.i]);
};
truncate('EUR','EA_ECFIN_BCS_LEAD_INDICATORS_history_Services','2026-07-31');
truncate('EUR','EA_RETAIL_VOL_history_value','2026-07-31');
truncate('USD','US_INDPRO_history_value','2026-07-31');
truncate('USD','US_NEWORDER_history_NEWORDER','2026-07-31');
truncate('USD','US_SLOOS_CI_LARGE_MIDDLE_history_value','2025-12-31');
truncate('USD','US_TOTBKCR_history_value','2026-07-31');
// An old service survey remains readable, but cannot silently stay green/red.
const euroStale=model(oldCatalog,'2026-11-24','EUR').find(x=>x.key==='services');
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
const euroUpgraded=model(oldCatalog,'2026-11-24','EUR',freshEuro).find(x=>x.key==='services');
assert.equal(euroUpgraded.signal.tone,'green','Fresh official EA21 survey supersedes July');
assert.equal(euroUpgraded.items[0].period,'2026-10');
assert.equal(euroUpgraded.items[0].current,3.8);
assert.match(render({catalog:oldCatalog,esc,dayNow:()=>'2026-11-24',country:'EUR',overlay:freshEuro}),/teibs020/);
const wrongEuro=structuredClone(freshEuro);
wrongEuro.series[0].source_series_id='UNRELATED';
assert.equal(model(oldCatalog,'2026-11-24','EUR',wrongEuro).find(x=>x.key==='services').signal.tone,'neutral');
const olderEuro=structuredClone(freshEuro);
olderEuro.series[0].dates=['2026-05','2026-06'];
assert.equal(model(oldCatalog,'2026-11-24','EUR',olderEuro).find(x=>x.key==='services').signal.tone,'neutral');
const euroNextYear=model(oldCatalog,'2028-01-01','EUR',freshEuro).find(x=>x.key==='services');
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
const currentUS=model(oldCatalog,'2026-11-24','USD',USfresh).find(x=>x.key==='industry');
assert.equal(currentUS.signal.tone,'green');
assert.equal(currentUS.signalSource,'fallback');
assert.equal(currentUS.items.length,3,'Preserve two dated official canonical indicators for context');
assert.equal(currentUS.items[0].period,'2026-10');
assert.equal(currentUS.expected,1,'Only the current official substitute is signal eligible');
assert.match(render({catalog:oldCatalog,esc,dayNow:()=>'2026-11-24',country:'USD',overlay:USfresh}),
 /Segnale da fonte supplementare aggiornata/);
const fakeFred=structuredClone(USfresh);
fakeFred.series[0].source_series_id='WRONG';
assert.equal(model(oldCatalog,'2026-11-24','USD',fakeFred).find(x=>x.key==='industry').signal.tone,'neutral');
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
assert.equal(model(oldCatalog,'2026-11-24','USD',UScredit).find(x=>x.key==='credit').signal.tone,'red',
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
assert.equal(model(oldCatalog,'2026-11-24','EUR',EAfresh).find(x=>x.key==='demand').signal.tone,'green');
assert.equal(model(oldCatalog,'2028-01-01','EUR',EAfresh).find(x=>x.key==='demand').signal.tone,'neutral');

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
const heatmap=render({catalog:oldCatalog,esc,dayNow:()=>'2026-11-24',country:'USD',overlay:USfresh});
assert.equal((heatmap.match(/class="sem-matrix-cell (?:green|red|amber|neutral)" title=/g)||[]).length,56,'56 accessible direction cells');
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

const hs={...sample('INDPRO',[104,106],monthlyDates.slice(-2)),quality:'SOURCE_REVISED_RESEARCH_NOT_PIT',
 history:{schema:'GMFQ_SEMAPHORE_CONTIGUOUS_HISTORY_V1',frequency:'M',source_series_id:'INDPRO',
 dates:monthlyDates,values:[100,101,102,103,104,105,106,107,108,109,110,111,104,106],
 observations:14,max_observations:36,quality:'SINGLE_SOURCE_REVISED_VINTAGE_NOT_PIT'}};
assert.equal(cycleHistory(hs,'2026-11-24','M').dates.length,14);
assert.equal(cycleMetric({id:'INDPRO',upGood:true},hs,'2026-11-24','M').phase,'expansion');
for(const patch of [{source_series_id:'WRONG'},{values:[...hs.history.values.slice(0,-1),999]},
 {dates:hs.history.dates.map((d,i)=>i===2?'2024-01':d)},{quality:'MANUALLY_VERIFIED_SNAPSHOT_NOT_PIT'},
 {observations:99},{frequency:'Q'}]){
 const bad={...hs,history:{...hs.history,...patch}};
 assert.equal(cycleHistory(bad,'2026-11-24','M').dates.length,2);
 assert.equal(cycleMetric({id:'INDPRO',upGood:true},bad,'2026-11-24','M').phase,null);
}
assert.equal(cycleHistory({...hs,quality:'SOURCE_VERIFIED_MANUAL_NONPIT'},'2026-11-24','M').dates.length,2);
console.log('ECONOMIC_CYCLE_CONTIGUOUS_HISTORY_PASS');
// Integration test: real collected source identities must reach the browser,
 // including official D1 archives and the distinct NZ proxies.
const liveOverlay=JSON.parse(fs.readFileSync(path.join(base,'site/fx-quant-v2/next/semaphore-supplement-v1.json'),'utf8'));
const liveDay=liveOverlay.as_of;
assert.match(liveDay,/^\d{4}-\d{2}-\d{2}$/);
const sourceCase=(ccy,key,allowed)=>{
 const ids=Array.isArray(allowed)?allowed:[allowed];
 const matches=liveOverlay.series.filter(s=>s.ccy===ccy&&s.area===key);
 assert.equal(matches.length,1,'Expected exactly one selected source '+ccy+' '+key);
 const x=matches[0],id=x.source_series_id;
 assert.ok(ids.includes(id),'Unexpected collected series '+id+'; permitted '+ids.join(', '));
 const row=model({},liveDay,ccy,{schema:liveOverlay.schema,series:[x]}).find(r=>r.key===key);
 assert.notEqual(row.signal.tone,'neutral','Valid collected source must reach browser: '+id);
 assert.equal(row.items[0].cycle.observations,x.history.observations);
 const fake=structuredClone(x);fake.source_series_id='WRONG';
 assert.equal(model({},liveDay,ccy,{schema:liveOverlay.schema,series:[fake]}).find(r=>r.key===key).signal.tone,'neutral');
 return x;
};
for(const [key,id] of [['house',['ABS_TOTAL_DWELLING_APPROVALS_SA','RBA_HOUSING_CREDIT_GROWTH_MM']],['credit','RBA_BUSINESS_CREDIT_GROWTH_MM']]){
 const x=sourceCase('AUD',key,id);
 const old={id:key==='house'?'AU_CREDIT_OWNER_OCC_HOUSING_SA_history_value':'AU_CREDIT_BUSINESS_CURRENT_SA_history_value',dates:['2026-06','2026-07'],values:[100,101],frequency:'M'};
 const row=model({AUD:[old]},liveDay,'AUD',{schema:liveOverlay.schema,series:[x]}).find(r=>r.key===key);
 assert.equal(row.signalSource,'fallback');
 assert.equal(row.items[0].cycle.observations,36);
}
sourceCase('NZD','house',['QNZR368BIS','STATSNZ_NEWDWELLINGS_SA']);
const anz=sourceCase('NZD','leading','ANZ_NZD_OWN_ACTIVITY_OUTLOOK_ROUNDED');
const priorLeading={id:'NZ_RBNZ_M15_BUSINESS_EXPECTATIONS_recent_Unemp_1Y',dates:['2026-Q2','2026-Q3'],values:[5.2,5.1],frequency:'Q'};
assert.equal(model({NZD:[priorLeading]},liveDay,'NZD',{schema:liveOverlay.schema,series:[anz]}).find(r=>r.key==='leading').signalSource,'fallback');
console.log('ECONOMIC_CYCLE_SOURCE_WIRING_PASS');


 // Inflation context must not affect the seven activity rows or convert
 // an index-level change into a false annual inflation rate.
const inflationDay='2026-11-25';
for(const c of coverage){
 const info=inflationContext(catalog,inflationDay,c);
 assert.ok(info.length>=2);
 assert.ok(info[0].available,'Headline source must exist for '+c);
 assert.ok(info[1].available,'Core source must exist for '+c);
 assert.ok(info.every(x=>!x.available||Number.isFinite(x.value)));
 assert.equal(model(catalog,inflationDay,c).length,7);
 assert.match(render({catalog,esc,dayNow:()=>inflationDay,country:c}),/Inflazione · pressioni sui prezzi/);
}
const example={USD:[{id:'US_CPIAUCSL_history_value',frequency:'M',dates:['2025-08','2025-09','2026-08','2026-09'],values:[100,100,102,103]}]};
const v=inflationContext(example,inflationDay,'USD')[0];
assert.ok(Math.abs(v.value-3)<1e-8);
assert.ok(Math.abs(v.change-1)<1e-8);
assert.equal(v.direction,'accelera');
assert.equal(v.period,'2026-09');
assert.equal(inflationContext(example,'2027-04-01','USD')[0].direction,null);
const missingLag=structuredClone(example);
missingLag.USD[0].values[1]=null;
assert.equal(inflationContext(missingLag,inflationDay,'USD')[0].available,false);
// A documented missing base may retain September, without inventing October YoY.
const officialGap={USD:[{...example.USD[0],dates:['2025-08','2025-09','2026-08','2026-09','2026-10'],values:[100,100,102,103,104],
 current_vintage_provenance:{status:'FRED_PUBLISHED_CURRENT_REVISED_HISTORY_NOT_PIT',source_series_id:'CPIAUCSL',gap_not_imputed:true,official_missing_periods:['2025-10']}}]};
const gapResult=inflationContext(officialGap,inflationDay,'USD')[0];
assert.equal(gapResult.period,'2026-09');assert.equal(gapResult.latestIndexPeriod,'2026-10');
assert.equal(gapResult.annualGap,true);assert.equal(gapResult.direction,null);
const undocumentedGap=structuredClone(officialGap);delete undocumentedGap.USD[0].current_vintage_provenance;
assert.equal(inflationContext(undocumentedGap,inflationDay,'USD')[0].available,false);
const inflationGap=structuredClone(example);
inflationGap.USD[0].dates[2]='2026-07';
assert.equal(inflationContext(inflationGap,inflationDay,'USD')[0].direction,null);
const nzInflation=inflationContext({NZD:[{id:'NZ_CPI_HEADLINE_YOY_history_value',frequency:'Q',dates:['2026-06','2026-09-01'],values:[4.1,3.7]}]},inflationDay,'NZD')[0];
assert.equal(nzInflation.period,'2026-Q3');
assert.equal(nzInflation.direction,'rallenta');
assert.equal(nzInflation.basis,'REPORTED_YOY');
console.log('ECONOMIC_CYCLE_INFLATION_CONTEXT_PASS');

 // Wage context uses actual nominal earnings, never expectations or employment.
{
 const wageDay='2026-11-25';
 for(const ccy of coverage){
   const row=wageContext(catalog,wageDay,ccy)[0];
   assert.ok(row);
   assert.equal(row.available,['USD','EUR','AUD'].includes(ccy),'Current catalog wage coverage '+ccy);
   assert.equal(model(catalog,wageDay,ccy).length,7);
   assert.match(render({catalog,esc,dayNow:()=>wageDay,country:ccy}),/Salari · crescita nominale effettiva/);
 }
 const wageFixture={USD:[{id:'US_AHE_TOTAL_PRIVATE_history_value',frequency:'M',dates:['2025-08','2025-09','2026-08','2026-09'],values:[30,30,31.2,31.5]}]};
 const w=wageContext(wageFixture,wageDay,'USD')[0];
 assert.ok(Math.abs(w.value-5)<1e-8);
 assert.ok(Math.abs(w.change-1)<1e-8);
 assert.equal(w.direction,'accelera');
 assert.equal(wageContext(wageFixture,'2027-04-01','USD')[0].direction,null);
 const expectationsOnly={NZD:[{id:'NZ_RBNZ_M15_BUSINESS_EXPECTATIONS_recent_Wage_1Y',frequency:'Q',dates:['2026-Q2','2026-Q3'],values:[2.81,2.82]}]};
 assert.equal(wageContext(expectationsOnly,wageDay,'NZD')[0].available,false);
 const eurWages={EUR:[{id:'EA_NEGOTIATED_WAGES_YOY_history_value',frequency:'Q',dates:['2026-Q1','2026-Q2'],values:[2.57,2.45]}]};
 assert.equal(wageContext(eurWages,wageDay,'EUR')[0].direction,'rallenta');
}
console.log('ECONOMIC_CYCLE_WAGE_CONTEXT_PASS');

{
 const wageDay='2026-11-25';
 const wageCases=[
 ['GBP','KAC3','https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/earningsandworkinghours/timeseries/kac3/lms','M',['2026-08','2026-09'],[3.8,3.6]],
 ['CAD','STATCAN_14100063_HOURLY_WAGE_YOY','https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410006301','M',['2026-09','2026-10'],[3.1,3.4]],
 ['JPY','LCEAMN01JPQ659S','https://fred.stlouisfed.org/series/LCEAMN01JPQ659S','Q',['2026-Q1','2026-Q2'],[4.58,5.0]]
 ];
 for(const [ccy,id,page,freq,dates,values] of wageCases){
   const record={ccy,area:'wages',source_series_id:id,source_page:page,source_file:'test fixture',frequency:freq,unit:'% a/a',metric_kind:'points',quality:'SOURCE_REVISED_RESEARCH_NOT_PIT',dates,values,
   history:{schema:'GMFQ_SEMAPHORE_CONTIGUOUS_HISTORY_V1',source_series_id:id,frequency:freq,dates,values,observations:2,max_observations:freq==='M'?36:12,quality:'SINGLE_SOURCE_REVISED_VINTAGE_NOT_PIT'}};
   const ov={schema:'GMFQ_G8_SEMAPHORE_SUPPLEMENT_V1',series:[],wage_context:{schema:'GMFQ_G8_WAGE_CONTEXT_V1',series:[record]}};
   const row=wageContext({},wageDay,ccy,ov)[0];
   assert.equal(row.available,true);
   assert.equal(row.value,values[1]);
   assert.equal(row.direction,values[1]>values[0]?'accelera':'rallenta');
   assert.equal(wageContext({},wageDay,ccy,{...ov,wage_context:{...ov.wage_context,series:[{...record,source_page:'https://wrong.example/'}]}})[0].available,false);
   assert.equal(wageContext({},wageDay,ccy,{...ov,wage_context:{...ov.wage_context,series:[{...record,history:{...record.history,values:[0,0]}}]}})[0].available,false);
   assert.equal(wageContext({},'2028-01-01',ccy,ov)[0].direction,null);
 }
}
console.log('ECONOMIC_CYCLE_WAGE_SUPPLEMENT_PASS');

{
 const chAnnual={ccy:'CHF',area:'wages',source_series_id:'FSO_SWI_NOMINAL_ANNUAL',source_page:'https://statistik.admin.ch/en/asset/36503589',frequency:'A',unit:'% a/a',quality:'SOURCE_VERIFIED_MANUAL_NONPIT',scope:'ANNUAL_ACTUAL_NOT_QUARTERLY',manual_verified_on:'2026-11-25',official_release_date:'2026-04-21',manual_expires_on:'2027-04-30',dates:['2023','2024','2025'],values:[1.7,1.8,1.8]};
 const overlay={schema:'GMFQ_G8_SEMAPHORE_SUPPLEMENT_V1',series:[],wage_context:{schema:'GMFQ_G8_WAGE_CONTEXT_V1',series:[chAnnual]}};
 const w=wageContext({},'2026-11-25','CHF',overlay)[0];
 assert.equal(w.available,true);
 assert.equal(w.direction,null);
 assert.equal(w.freq,'A');
 assert.equal(w.value,1.8);
 assert.equal(wageContext({},'2027-04-30','CHF',overlay)[0].available,false);
 assert.match(render({catalog,esc,dayNow:()=> '2026-11-25',country:'CHF',overlay}),/dato annuale: momentum corrente non valutabile/);
}
console.log('ECONOMIC_CYCLE_CH_WAGE_ANNUAL_PASS');

{
 const day='2026-11-25';
 const keys={USD:'NAEXKP06USQ659S',GBP:'NAEXKP06GBQ659S',JPY:'NAEXKP06JPQ659S',CHF:'NAEXKP06CHQ659S',CAD:'NAEXKP06CAQ659S',AUD:'NAEXKP06AUQ659S',NZD:'NAEXKP06NZQ659S',EUR:'EUROSTAT_EA21_P6_REAL_EXPORTS_YOY'};
 for(const ccy of coverage){
   const id=keys[ccy],page=ccy==='EUR'?'https://ec.europa.eu/eurostat/databrowser/view/namq_10_gdp/default/table?lang=en':'https://fred.stlouisfed.org/series/'+id;
   const record={ccy,area:'external',source_series_id:id,source_page:page,source_file:'fixture',frequency:'Q',unit:'% a/a reale',metric_kind:'points',quality:'SOURCE_REVISED_RESEARCH_NOT_PIT',dates:['2026-Q1','2026-Q2'],values:[-2,-1],
    history:{schema:'GMFQ_SEMAPHORE_CONTIGUOUS_HISTORY_V1',source_series_id:id,frequency:'Q',dates:['2025-Q4','2026-Q1','2026-Q2'],values:[-3,-2,-1],observations:3,max_observations:12,quality:'SINGLE_SOURCE_REVISED_VINTAGE_NOT_PIT'}};
   const wrap=x=>({schema:'GMFQ_G8_SEMAPHORE_SUPPLEMENT_V1',series:[],external_context:{schema:'GMFQ_G8_EXTERNAL_CONTEXT_V1',series:[x]}});
   const r=externalContext(day,ccy,wrap(record));
   assert.equal(r.available,true);assert.equal(r.value,-1);assert.equal(r.direction,'accelera');
   assert.equal(r.regime,'volumi in calo annuo');assert.equal(r.persistence,2);
   assert.equal(externalContext(day,ccy,wrap({...record,unit:'% a/a nominale'})).available,false);
   assert.equal(externalContext(day,ccy,wrap({...record,source_page:'https://wrong.example'})).available,false);
   assert.equal(externalContext(day,ccy,wrap({...record,history:{...record.history,dates:['2025-Q3','2026-Q1','2026-Q2']}})).available,false);
   assert.equal(externalContext('2028-01-01',ccy,wrap(record)).direction,null);
   assert.equal(model(catalog,day,ccy,wrap(record)).length,7);
   assert.match(render({catalog,esc,dayNow:()=>day,country:ccy,overlay:wrap(record)}),/Domanda estera · esportazioni reali/);
 }
}
console.log('ECONOMIC_CYCLE_EXTERNAL_CONTEXT_PASS');

{
 const day='2026-11-25';
 const metric={id:'fixture_diffusion',name:'Indice attività',kind:'points',upGood:true,diffusionThreshold:50,minimum:.2};
 const cyc=values=>cycleMetric(metric,{dates:values.map((_,i)=>'2026-'+String(7+i).padStart(2,'0')),values},day,'M');
 assert.equal(cyc([49,47,48]).reversal,'INITIAL_REVERSAL');
 assert.equal(cyc([49,47,48,49]).reversal,'PERSISTENT_REVERSAL');
 assert.equal(cyc([46,47,48,49]).reversal,null);
 assert.equal(cyc([49,47,47.05,48]).reversal,null);
 assert.equal(cyc([52,54,53]).reversal,'INITIAL_REVERSAL');
 assert.equal(cyc([49,47]).historySufficient,false);
 const row=(key,values,extra={})=>({key,name:key,signal:{tone:'amber'},signalSource:'original',items:[{metric,period:'2026-10',date:'2026-10-31',verdict:1,cycle:cyc(values),...extra}]});
 const rows=[row('industry',[49,47,48,49]),row('services',[49,47,48]),row('demand',[46,47,48,49]),row('jobs',[49,49,49,49])];
 const t=turningPointMonitor(rows);
 assert.equal(t.coverage,4);assert.equal(t.up.length,2);assert.equal(t.improving.length,3);assert.equal(t.eligible,true);
 assert.match(t.judgment,/possibile svolta favorevole/);
 assert.equal(turningPointMonitor(rows.slice(0,3)).eligible,false);
 const conflicting=turningPointMonitor([...rows,row('credit',[52,54,53])]);
 assert.equal(conflicting.down.length,1);assert.match(conflicting.judgment,/non è ancora concorde/);
 const nonaligned=turningPointMonitor([...rows,row('leading',[49,47,48],{date:'2026-01-31'})]);
 assert.equal(nonaligned.eligible,false);
 assert.equal(turningPointMonitor([row('stale',[49,47,48],{stale:true})]).coverage,0);
 const mixed={...rows[0],items:[...rows[0].items,...row('industry',[52,54,53]).items]};
 assert.equal(turningPointMonitor([mixed]).up.length,0);
 for(const ccy of coverage)assert.match(render({catalog,esc,dayNow:()=>day,country:ccy}),/Turning Point Monitor · segnali di svolta/);
}
console.log('ECONOMIC_CYCLE_TURNING_POINT_PASS');

{
 const row=(name,tone,date='2026-10-31')=>({name,signal:{tone},signalSource:'original',items:[{date,verdict:tone==='green'?1:tone==='red'?-1:0,cycle:{level:null}}]});
 const rows=[row('Lavoro','green'),row('Consumi','green'),row('Servizi','green'),row('Credito','red')];
 const core={label:'CPI core',available:true,value:3.2,direction:'accelera',period:'2026-10',freq:'M'};
 const wage={label:'Salari orari',available:true,value:2.4,direction:'rallenta',period:'2026-10',freq:'M'};
 const external={available:true,value:-1.2,direction:'accelera',period:'2026-Q3'};
 const t={judgment:'Svolte locali.'};
 const n=macroNarrative(rows,[core],[wage],external,t);
 assert.match(n.growth,/miglioramento è più diffuso/);
 assert.match(n.growth,/Peggiorano credito/);
 assert.match(n.policy,/divergono/);
 assert.match(n.trade,/Volumi inferiori/);
 assert.match(n.trade,/accelera/);
 assert.match(n.watch,/perderebbe credibilità/);
 assert.match(macroNarrative(rows.slice(0,2),[],[],{},t).growth,/insufficienti/);
 assert.match(macroNarrative([...rows,row('Manifattura','green','2025-01-01')],[],[],{},t).growth,/insufficienti/);
 const old=macroNarrative(rows,[{...core,stale:true}],[{...wage,freq:'A'}],{...external,stale:true},t);
 assert.match(old.prices,/non determinabile/);assert.match(old.prices,/non valutabile/);
 assert.match(old.trade,/insufficiente/);assert.doesNotMatch(old.policy,/divergono/);
 const cooling=macroNarrative(rows,[{...core,direction:'rallenta'}],[wage],external,t);
 assert.match(cooling.policy,/non una garanzia di tagli/);
 for(const ccy of coverage)assert.match(render({catalog,esc,dayNow:()=> '2026-11-25',country:ccy}),/Cosa vedo davvero · giudizio macro/);
}
console.log('ECONOMIC_CYCLE_MACRO_NARRATIVE_PASS');

{
 for(const ccy of coverage){
   const html=render({catalog,esc,dayNow:()=> '2026-11-25',country:ccy});
   const order=['class="sem-g8-table"','class="sem-desk-reading"','class="sem-desk-turn"','class="sem-desk-context"','class="sem-table"'];
   const indices=order.map(x=>html.indexOf(x));
   assert.ok(indices.every(x=>x>=0)&&indices.every((x,i)=>i===0||x>indices[i-1]),'Narrative must precede detailed evidence: '+ccy);
   assert.equal((html.match(/class="sem-desk-detail"/g)||[]).length,3);
   assert.match(html,/<details class="sem-desk-evidence">/,'Indicator evidence is available but collapsed initially');
   assert.equal((html.match(/Cosa vedo davvero · giudizio macro/g)||[]).length,1);
   assert.equal((html.match(/class="sem-row /g)||[]).length,7);
 }
}
console.log('ECONOMIC_CYCLE_EDITORIAL_HIERARCHY_PASS');

{
 const today='2026-11-25';
 const fixture=(tone,phase)=>({key:'industry',name:'Manifattura',signal:{tone},signalSource:'original',items:[{period:'2026-10',verdict:1,cycle:{phase}}]});
 const t={up:[],down:[]};
 const o=overviewCountry([fixture('green','recovery')],[],[],{},t,{aligned:false});
 assert.equal(o.tone,'neutral');assert.equal(o.cells[0].phase,'recovery');
 assert.equal(overviewCountry([fixture('neutral','recovery')],[],[],{},t,{aligned:false}).cells[0].phase,null);
 const mixed=fixture('amber','recovery');mixed.items.push({period:'2026-10',verdict:-1,cycle:{phase:'slowdown'}});
 assert.equal(overviewCountry([mixed],[],[],{},t,{aligned:false}).cells[0].phase,null);
 const ov=JSON.parse(fs.readFileSync(path.join(base,'site/fx-quant-v2/next/semaphore-supplement-v1.json'),'utf8'));
 for(const ccy of coverage){
   const e=externalContext(today,ccy,ov);
   assert.ok(e.available,'Missing validated export series '+ccy);
   assert.match(exportSparkline(today,ccy,ov,e,esc),/<polyline points=/);
   assert.equal(exportSparkline(today,ccy,ov,{...e,stale:true},esc),'');
   const html=render({catalog,esc,dayNow:()=>today,country:ccy,overlay:ov});
   assert.equal((html.match(/class="sem-country-card (?:green|red|amber|neutral)/g)||[]).length,8);
   assert.equal((html.match(/class="sem-matrix-cell /g)||[]).length,56);
   assert.equal((html.match(/class="sem-export-trend"/g)||[]).length,8);
   assert.ok(html.indexOf('class="sem-g8-table"')<html.indexOf('class="sem-country-board"'),'The central matrix precedes optional comparative cards');
   assert.match(html,/Radar delle svolte/);
   assert.equal(model(catalog,today,ccy,ov).length,7);
 }
}
console.log('ECONOMIC_CYCLE_G8_DASHBOARD_PASS');

{
 const row=(key,name,tone)=>({key,name,signal:{tone}});
 const us=[row('house','Immobiliare','red'),row('jobs','Lavoro','amber'),row('industry','Manifattura','red'),row('services','Servizi','amber'),row('leading','Anticipatori','red'),row('demand','Consumi','amber'),row('credit','Credito','green')];
 const h={label:'CPI headline',available:true,value:3.7,direction:'accelera',freq:'M'};
 const core={label:'CPI core',available:true,value:2.4,direction:'accelera',freq:'M',stale:true};
 const exportRate={available:true,value:2,direction:'rallenta',freq:'Q'};
 const usView=countryInterpretation(us,[h,core],[],exportRate,{aligned:true});
 assert.equal(usView.label,'Perdita di slancio produttivo');
 assert.match(usView.economy,/Lavoro e consumi non danno ancora/);
 assert.match(usView.policy,/manca una conferma corrente dal core/);
 assert.match(usView.policy,/dilemma/);
 assert.match(usView.watch,/lavoro e consumi/);
 const async=countryInterpretation(us,[h,core],[],exportRate,{aligned:false});
 assert.equal(async.tone,'red');
 assert.equal(async.aggregateTone,'neutral');
 assert.match(async.quality,/Periodi non allineati/);
 assert.equal(countryInterpretation(us.slice(0,2),[],[],{}, {aligned:false}).tone,'neutral');
 const eu=us.map(r=>({...r,signal:{tone:({house:'red',jobs:'amber',industry:'green',services:'red',leading:'red',demand:'red',credit:'green'})[r.key]}}));
 const euView=countryInterpretation(eu,[],[],{...exportRate,direction:'accelera'},{aligned:false});
 assert.equal(euView.label,'Debolezza interna');
 assert.match(euView.economy,/sostegno esterno/);
 for(const ccy of coverage){
   const html=render({catalog,esc,dayNow:()=> '2026-11-25',country:ccy});
   assert.equal((html.match(/class="sem-country-quality /g)||[]).length,8);
   assert.equal((html.match(/Il dilemma monetario/g)||[]).length,8);
   assert.equal((html.match(/class="sem-country-comment watch"/g)||[]).length,8);
 }
}
console.log('ECONOMIC_CYCLE_COUNTRY_INTERPRETATION_PASS');

{
 const position=(breadth,direction,extra={})=>regimePosition({reading:{aligned:true,breadth},head:{available:true,value:2.7,direction,period:'2026-10'},cells:[{periods:['2026-09','2026-10']}],...extra});
 assert.equal(position(-1,'accelera').quadrant,'down_up');
 assert.equal(position(1,'accelera').quadrant,'up_up');
 assert.equal(position(-1,'rallenta').quadrant,'down_down');
 assert.equal(position(1,'rallenta').quadrant,'up_down');
 assert.equal(position(0,'accelera').quadrant,null);
 assert.equal(position(1,'stabile').quadrant,null);
 assert.equal(position(1,'accelera',{reading:{aligned:false,breadth:1}}).quadrant,null);
 assert.equal(position(1,'accelera',{head:{available:true,value:2.7,direction:'accelera',period:'2026-10',stale:true}}).quadrant,null);
 assert.equal(position(1,'accelera',{cells:[{periods:['2026-01']}]}).quadrant,null);
 for(const ccy of coverage){
  const html=render({catalog,esc,dayNow:()=> '2026-11-25',country:ccy});
  assert.equal((html.match(/class="sem-regime-quadrant /g)||[]).length,4);
  assert.match(html,/Mappa attività \/ inflazione/);
  assert.match(html,/Fuori mappa/);
  assert.match(html,/Non misura l’accelerazione del PIL/);
 }
}
console.log('ECONOMIC_CYCLE_REGIME_MAP_PASS');

{
 const date='2026-11-25';
 const sample={dates:['2026-06','2026-07','2026-08','2026-10','2026-11'],values:[1,2,3,4,5]};
 assert.equal(chartTail(sample,date,'M'),null);
 assert.equal(chartTail({dates:['2026-Q1','2026-Q2','2026-Q3'],values:[1,2,3]},date,'Q').length,3);
 assert.equal(chartTail({dates:['2026-Q1','2026-Q2','2026-Q3','2026-Q3'],values:[1,2,3,4]},date,'Q'),null);
 assert.equal(chartTail({dates:['2023','2024','2025'],values:[1.7,1.8,1.8]},date,'A').length,3);
 const d=Array.from({length:15},(_,i)=>new Date(Date.UTC(2024,i,1)).toISOString().slice(0,10));
 const v=Array.from({length:15},(_,i)=>100+i);
 const yoy=chartTail({dates:d,values:v},date,'M',true);
 assert.equal(yoy.length,3);assert.ok(Math.abs(yoy[0].value-12)<1e-9);
 const ov=JSON.parse(fs.readFileSync(path.join(base,'site/fx-quant-v2/next/semaphore-supplement-v1.json'),'utf8'));
 for(const ccy of coverage){
   const rows=model(catalog,date,ccy,ov),inflation=inflationContext(catalog,date,ccy),wages=wageContext(catalog,date,ccy,ov),external=externalContext(date,ccy,ov);
   const h=countryHistories(catalog,date,ccy,ov,rows,{inflation,wages,external});
   assert.equal(h.exports.length,1,ccy+' export history');
   assert.equal(h.exports[0].points.length,12);
   assert.equal(h.exports[0].points.at(-1).value,external.value);
   assert.ok(h.inflation.length>=1,ccy+' inflation history');
   for(const x of Object.values(h).flat())assert.ok(x.points.length>=3&&x.unit&&x.source);
   const html=render({catalog,esc,dayNow:()=>date,country:ccy,overlay:ov});
   assert.equal((html.match(/class="sem-history-panel"/g)||[]).length,4);
   assert.match(html,/Da dove arriva l’economia/);
   if(ccy==='CHF')assert.ok(h.wages.some(x=>x.freq==='A'&&x.stale&&x.manual));
   if(ccy==='NZD')assert.ok(h.wages.some(x=>x.manual&&x.points.length===12));
 }
}
console.log('ECONOMIC_CYCLE_COUNTRY_HISTORY_PASS');

{
 const row=(tone,period='2026-09',prior='2026-08',freq='M')=>({key:'industry',name:'Manifattura',signal:{tone},signalSource:'original',items:[{period,prior,freq,verdict:tone==='green'?1:-1}]});
 assert.equal(matchedActivityWindows(row('green')),'M:2026-08→2026-09');
 assert.equal(matchedActivityWindows(row('green','2026-09','2026-07')),null);
 assert.equal(matchedActivityWindows(row('green','2026-Q3','2026-Q2','Q')),'Q:2026-Q2→2026-Q3');
 const peers=relativeActivity({USD:[row('green')],EUR:[row('red')],GBP:[row('red','2026-08','2026-07')],JPY:[row('red','2026-Q3','2026-Q2','Q')]},'USD');
 assert.equal(peers.find(x=>x.ccy==='EUR').favorsSelected.length,1);
 assert.equal(peers.find(x=>x.ccy==='GBP').aligned.length,0);
 assert.equal(peers.find(x=>x.ccy==='JPY').aligned.length,0);
 const date='2026-11-25',ov=JSON.parse(fs.readFileSync(path.join(base,'site/fx-quant-v2/next/semaphore-supplement-v1.json'),'utf8'));
 const overview=Object.fromEntries(coverage.map(c=>[c,{external:externalContext(date,c,ov)}]));
 const common=comparableExports(date,ov,overview);
 assert.equal(common.rows.length,8);
 assert.equal(common.period,'2026-Q2');
 assert.equal(common.prior,'2026-Q1');
 for(const r of common.rows){
   const source=ov.external_context.series.find(x=>x.ccy===r.ccy);
   const i=source.history.dates.indexOf(common.period);
   assert.equal(r.value,source.history.values[i]);
   assert.equal(r.change,source.history.values[i]-source.history.values[i-1]);
 }
 for(const ccy of coverage)assert.match(render({catalog,esc,dayNow:()=>date,country:ccy,overlay:ov}),/Chi sta cambiando rispetto agli altri/);
}
console.log('ECONOMIC_CYCLE_RELATIVE_DIVERGENCES_PASS');

{
 const today='2026-11-25',dates=Array.from({length:24},(_,i)=>new Date(Date.UTC(2024,10+i,1)).toISOString().slice(0,7)),values=dates.map((_,i)=>300+i);
 const make=(ccy,id,source_page,unit,values)=>({ccy,area:'core',source_series_id:id,source_page,unit,frequency:'M',metric_kind:'points',quality:'SOURCE_REVISED_RESEARCH_NOT_PIT',dates:dates.slice(-2),values:values.slice(-2),source_file:'QA fixture',history:{schema:'GMFQ_SEMAPHORE_CONTIGUOUS_HISTORY_V1',frequency:'M',source_series_id:id,quality:'SINGLE_SOURCE_REVISED_VINTAGE_NOT_PIT',dates,values,observations:24,max_observations:36}});
 const us=make('USD','CPILFESL','https://fred.stlouisfed.org/series/CPILFESL','Index 1982-1984=100',values);
 const uk=make('GBP','DKO8','https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/dko8/mm23','% a/a',dates.map((_,i)=>2+i/100));
 const ov=JSON.parse(fs.readFileSync(path.join(base,'site/fx-quant-v2/next/semaphore-supplement-v1.json'),'utf8'));
 ov.inflation_context={schema:'GMFQ_G8_INFLATION_CONTEXT_V1',series:[us,uk]};
 const missingCore=structuredClone(catalog);
 for(const ccy of ['USD','GBP','EUR','CAD'])missingCore[ccy]=missingCore[ccy].filter(r=>!/(CPILFESL|CORE_YOY|CPI_MEDIAN_YOY|CPI_TRIM_YOY)/.test(r.id));
 const u=inflationContext(missingCore,today,'USD',ov).find(x=>/core/i.test(x.label));
 const k=inflationContext(missingCore,today,'GBP',ov).find(x=>/core/i.test(x.label));
 const gapDates=dates.filter(p=>p!=='2025-10'),gapValues=dates.map((p,i)=>({p,v:values[i]})).filter(x=>x.p!=='2025-10').map(x=>x.v);
 const gap={...us,exact_lag_history:{schema:'GMFQ_US_CORE_EXACT_LAG_V1',source_series_id:'CPILFESL',dates:gapDates,values:gapValues}};
 const gapCore=inflationContext(catalog,today,'USD',{...ov,inflation_context:{...ov.inflation_context,series:[gap]}}).find(x=>/core/i.test(x.label));
 assert.equal(gapCore.period,'2026-09');assert.equal(gapCore.latestIndexPeriod,'2026-10');assert.equal(gapCore.annualGap,true);assert.equal(gapCore.direction,null);
 const eur=make('EUR','EUROSTAT_EA21_HICP_CORE_YOY','https://ec.europa.eu/eurostat/databrowser/view/prc_hicp_minr/default/table?lang=en','% a/a',dates.map((_,i)=>2+i/100));
 const e=inflationContext(missingCore,today,'EUR',{...ov,inflation_context:{...ov.inflation_context,series:[eur]}}).find(x=>/core/i.test(x.label));
 assert.equal(e.period,'2026-10');assert.equal(e.value,2.23);
 const cadPage='https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810025601';
 const median=make('CAD','STATCAN_18100256_MEDIAN_YOY',cadPage,'% a/a',dates.map((_,i)=>2+i/100));
 const trim=make('CAD','STATCAN_18100256_TRIM_YOY',cadPage,'% a/a',dates.map((_,i)=>1+i/100));
 const canada=inflationContext(missingCore,today,'CAD',{...ov,inflation_context:{...ov.inflation_context,series:[median,trim]}});
 assert.equal(canada.find(x=>/median/i.test(x.label)).value,2.23);
 assert.equal(canada.find(x=>/trim/i.test(x.label)).value,1.23);
 assert.equal(canada.find(x=>/trim/i.test(x.label)).period,'2026-10');
 assert.equal(u.period,'2026-10');assert.equal(k.period,'2026-10');assert.ok(Math.abs(u.value-(323/311-1)*100)<1e-9);assert.equal(k.value,2.23);
 assert.equal(inflationContext(catalog,today,'USD',{...ov,inflation_context:{...ov.inflation_context,series:[{...us,source_page:'https://example.com'}]}}).find(x=>/core/i.test(x.label)).period,inflationContext(catalog,today,'USD').find(x=>/core/i.test(x.label)).period);
}
{
 const aud=inflationContext(catalog,'2026-11-25','AUD');
 const filtered=aud.filter(x=>/core|trimmed|median|\btrim\b/i.test(x.label));
 assert.equal(filtered.length,1);
 assert.match(filtered[0].id,/TRIMMED_MEAN_M_YOY/);
}
console.log('ECONOMIC_CYCLE_CORE_RECOVERY_PASS');

{
 const svc={ccy:'CAD',area:'services',id:'SEM_G8_CAD_SERVICES',label:'PIL reale settore servizi',frequency:'M',unit:'mln CAD reali SAAR',dates:['2026-07','2026-08'],values:[100,99],source_series_id:'36100434_SERVICES_T003',source_page:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610043401',metric_kind:'percent',quality:'SOURCE_REVISED_RESEARCH_NOT_PIT',up_good:true};
 const ov={schema:'GMFQ_G8_SEMAPHORE_SUPPLEMENT_V1',series:[svc]};
 assert.equal(model({},'2026-11-25','CAD',ov).find(x=>x.key==='services').signal.tone,'red');
 assert.equal(model({},'2026-12-10','CAD',ov).find(x=>x.key==='services').signal.tone,'neutral');
}
