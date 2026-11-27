'use strict';
/* Read-only official BoC CAD business loan stock and standalone research UI. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const source=require(path.join(root,'site/fx-quant-v2/next/cad-official-credit-research-v1.js'));
const studio=require(path.join(root,'site/fx-quant-v2/next/liquidity-credit-studio.js'));
const native=JSON.parse(fs.readFileSync(path.join(root,'live_data/sections/NATIVE_LIQ_DATA.json'),'utf8'));
const pp=path.join(root,'site/fx-quant-v2/next/index.html');
const html=fs.readFileSync(pp,'utf8');
assert.match(html,/cad-official-credit-research-v1\.js\?v=\d+/);
assert.equal(source.schema,'GMFQ_NEXT_CAD_BUSINESS_CREDIT_OFFICIAL_RESEARCH_V1');
assert.equal(source.publisher,'Bank of Canada');
assert.equal(source.series_id,'V122667770');
assert.equal(source.category,'outstanding_business_loans');
assert.equal(source.frequency,'M');
assert.equal(source.units,'milioni CAD');
assert.equal(source.eligible_for_fx_core,false);
assert.equal(source.eligible_for_backtest,false);
assert.equal(source.first_release_pit_verified,false);
assert.equal(source.observation_is_not_publication_date,true);
assert(source.source_url.startsWith('https://www.bankofcanada.ca/rates/'));
assert.equal(source.latest_observation,source.dates.at(-1));
assert.equal(source.values.length,source.dates.length);
assert(source.dates.length>=5);
for(let i=0;i<source.dates.length;i++){
 const d=source.dates[i],v=source.values[i];
 assert.match(d,/^\d{4}-\d{2}$/);
 assert(Number.isFinite(v)&&v>300000&&v<1800000);
 if(i>0){
  assert(source.dates[i-1]<d);
  assert(Math.abs(v/source.values[i-1]-1)<.12);
 }
}
assert(source.dates.includes('2026-08'));
const dateIndex=source.dates.indexOf('2026-08');
assert(Math.abs(source.values[dateIndex]-944614)/944614<.03);
const FX=['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'];
const fmt=(v,n=2)=>Number(v).toLocaleString('it-IT',{minimumFractionDigits:n,maximumFractionDigits:n});
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const api=k=>({get:x=>x==='liquidity'?native:null,FX,
 FLAGS:Object.fromEntries(FX.map(x=>[x,x])),NAMES:Object.fromEntries(FX.map(x=>[x,x])),
 state:{liqCcy:k},plot:()=>'<svg></svg>',pageHero:(a,b,c)=>'<h1>'+b+'</h1>',
 esc,fmt,date:x=>x,dayNow:()=>'2026-11-14'});
const cad=studio.render(api('CAD'));
assert.match(cad,/class="drivers-cad-official"/);
assert.match(cad,/fonte ufficiale canadese separata/i);
assert.match(cad,/stock bancario, non il flusso di nuovi prestiti/i);
assert.match(cad,/non certifica/i);
assert.match(cad,/V122667770/);
assert(cad.includes(source.latest_observation),'Render current official source date');
assert.match(cad,/Fonte: Bank of Canada/);
const creditCard=cad.split('data-liq-role="credit"')[1].split('</div>')[0];
const gate=require(path.join(root,'site/fx-quant-v2/next/liquidity-source-policy-gate-v1.js'));
const mapping=gate.check('CAD','credit');
const macro=JSON.parse(fs.readFileSync(path.join(root,'live_data/sections/MACRO_SERIES.json'),'utf8'));
if(mapping.ready){
 const row=macro.CAD.find(x=>x.id==='CA_BUSINESS_LOANS_OUTSTANDING_history_value');
 assert(row&&native.CAD.credit);
 assert.equal(row.current_vintage_provenance.source_series_id,'V122667770');
 assert.equal(row.current_vintage_provenance.source_series_first_release_PIT_certified,false);
 for(const k of ['dates','values','last_date','last_value'])assert.deepEqual(native.CAD.credit[k],row[k]);
 assert(creditCard.includes(row.last_date));
 assert(creditCard.includes(fmt(row.last_value,2)));
 assert.doesNotMatch(creditCard,/Misura non verificabile/);
}else{
 assert.equal(native.CAD.credit,null);
 assert.match(creditCard,/Misura non verificabile/);
}
assert(!studio.render(api('USD')).includes('drivers-cad-official'));
console.log('CAD_OFFICIAL_CREDIT_RESEARCH_SIDECAR_PASS',JSON.stringify({
 observations:source.dates.length,latest:source.latest_observation,
 lastValue:source.values.at(-1),canonicalCadCredit: native.CAD.credit,
 fxRankingUnchanged:true,firstReleaseUnverified:true
}));

// Daily issuer observations cannot silently replace the monthly statistical vintage.
 const lynx=source.settlement_balances||{
  series_id:'BOC_LYNX_ACTUAL_DAILY',source_url:'https://www.bankofcanada.ca/rates/indicators/market-operations-indicators/',
  frequency:'D',unit:'milioni CAD',preliminary_may_be_revised:true,
  canonical_monthly_equivalence_verified:false,eligible_for_fx_core:false,eligible_for_backtest:false,
  dates:['2026-11-18','2026-11-19','2026-11-20','2026-11-23'],values:[70900,75200,76900,77400],
  latest_observation:'2026-11-23'
 };
 const original=globalThis.FXQuantCADCreditResearch,before=JSON.stringify(native);
 const current=ccy=>({...api(ccy),dayNow:()=>new Date().toISOString().slice(0,10)});
 try{
  globalThis.FXQuantCADCreditResearch={...source,settlement_balances:lynx};
  const plots=[];
  const rendered=studio.render({...current('CAD'),plot:x=>{plots.push(x);return '<svg></svg>';}});
  assert.match(rendered,/BANK OF CANADA · SALDI LYNX GIORNALIERI/);
  assert(rendered.includes(fmt(lynx.values.at(-1)/1000,3)+' miliardi CAD'));
  assert.match(rendered,/equivalenza con lo storico mensile non verificata/);
  const chart=plots.find(x=>x.label==='Liquidità · fonte ufficiale separata CAD');
  const historic=plots.find(x=>x.label==='Liquidità · storico originario CAD');
  assert(chart&&historic);
  assert.equal(chart.lines[0].values.at(-1).label,lynx.latest_observation);
  assert.equal(chart.lines[0].values.at(-1).value,lynx.values.at(-1));
  assert.equal(historic.lines[0].values.at(-1).label,native.CAD.liquidity.last_date);
  assert(!studio.render(current('EUR')).includes('SALDI LYNX GIORNALIERI'));
  for(const changed of [{series_id:'BOC_TOTAL_SETTLEMENT_BALANCES'},{unit:'miliardi CAD'},{canonical_monthly_equivalence_verified:true}]){
   globalThis.FXQuantCADCreditResearch={...source,settlement_balances:{...lynx,...changed}};
   assert(!studio.render(current('CAD')).includes('SALDI LYNX GIORNALIERI'));
  }
 }finally{globalThis.FXQuantCADCreditResearch=original;}
 assert.equal(JSON.stringify(native),before);
 console.log('NEXT_CAD_LYNX_CHART_PASS',source.settlement_balances?'actual':'synthetic rendering fixture',lynx.latest_observation);

const survey=source.lending_conditions||{
 series_id:'SLOS_BUS_LEND',source_url:'https://www.bankofcanada.ca/publications/slos/',
 frequency:'Q',unit:'net_balance_pct_points',positive_means:'tightening',negative_means:'easing',
 first_release_pit_verified:false,eligible_for_fx_core:false,eligible_for_backtest:false,
 dates:['2025-10-01','2026-01-01','2026-04-01','2026-07-01'],
 values:[2,0,-1.04,-6.48],latest_observation:'2026-07-01'
};
try{
 globalThis.FXQuantCADCreditResearch={...source,lending_conditions:survey};
 const plots=[];
 const rendered=studio.render({...current('CAD'),plot:x=>{plots.push(x);return '<svg></svg>';}});
 assert.match(rendered,/CONDIZIONI DI CREDITO SLOS/);
 const graph=plots.find(x=>x.label==='Condizioni di credito · fonte ufficiale separata CAD');
 assert(graph);
 assert.deepEqual(graph.lines[0].values,survey.dates.map((label,i)=>({label,value:survey.values[i]})));
 assert.match(rendered,/Negativo = allentamento, positivo = irrigidimento/);
 assert(!studio.render(current('USD')).includes('CONDIZIONI DI CREDITO SLOS'));
 globalThis.FXQuantCADCreditResearch={...source,lending_conditions:{...survey,positive_means:'easing'}};
 assert(!studio.render(current('CAD')).includes('CONDIZIONI DI CREDITO SLOS'));
}finally{globalThis.FXQuantCADCreditResearch=original;}
console.log('NEXT_CAD_SLOS_CHART_PASS',source.lending_conditions?'actual':'synthetic rendering fixture',survey.latest_observation);
