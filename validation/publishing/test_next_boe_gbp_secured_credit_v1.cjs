'use strict';
/* Official BoE LPMVTYI household-secured annual credit growth, not BoE reserves. */
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'../..');
const mortgage=require(path.join(root,'site/fx-quant-v2/next/gbp-boe-secured-credit-research-v1.js'));
const reserve=require(path.join(root,'site/fx-quant-v2/next/gbp-boe-reserves-research-v1.js'));
const studio=require(path.join(root,'site/fx-quant-v2/next/liquidity-credit-studio.js'));
const native=JSON.parse(fs.readFileSync(path.join(root,'live_data/sections/NATIVE_LIQ_DATA.json'),'utf8'));
const entry=fs.readFileSync(path.join(root,'site/fx-quant-v2/next/index.html'),'utf8');
assert.match(entry,/gbp-boe-secured-credit-research-v1\.js\?v=\d+/);
assert.equal(mortgage.schema,'GMFQ_NEXT_GBP_BOE_SECURED_CREDIT_GROWTH_V1');
assert.equal(mortgage.status,'VERIFIED_BOE_LPMVTYI_SECURED_GROWTH_RESEARCH_ONLY');
assert.equal(mortgage.publisher,'Bank of England');
assert.equal(mortgage.series_id,'LPMVTYI');
assert.equal(mortgage.category,'secured_household_credit_yoy_growth');
assert.equal(mortgage.frequency,'M');
assert.equal(mortgage.unit,'percent_yoy');
assert.equal(mortgage.seasonally_adjusted,true);
assert.equal(mortgage.first_release_pit_verified,false);
assert.equal(mortgage.observation_is_not_publication_date,true);
assert.equal(mortgage.eligible_for_fx_core,false);
assert.equal(mortgage.eligible_for_backtest,false);
assert.equal(mortgage.official_september_release_date,'2026-10-29');
assert.equal(mortgage.last_observation,mortgage.dates.at(-1));
assert.equal(mortgage.dates.length,mortgage.values.length);
assert(mortgage.dates.length>=24);
assert(mortgage.source_url.startsWith('https://www.bankofengland.co.uk/boeapps/database/'));
for(let i=0;i<mortgage.dates.length;i++){
 const d=mortgage.dates[i],v=mortgage.values[i];
 assert.match(d,/^\d{4}-\d{2}$/);
 assert(Number.isFinite(v)&&v>-15&&v<25);
 if(i>0){
  const prev=mortgage.dates[i-1];
  assert.equal(
   ((+d.slice(0,4))*12+(+d.slice(5)))-
   ((+prev.slice(0,4))*12+(+prev.slice(5))),1,
   'BoE monthly source cannot have a silent gap');
 }
}
for(const [date,ref] of [['2026-07',3.6],['2026-08',3.6],['2026-09',3.4]]){
 const at=mortgage.dates.indexOf(date);
 assert(at>=0,'BoE official reference month missing '+date);
 assert(Math.abs(mortgage.values[at]-ref)<.16,'Official BoE variant drift '+date);
}
assert(Number.isFinite(native.GBP.credit.last_value));
assert.equal(reserve.series_id,'RPWB56A');
const fmt=(v,n=2)=>Number(v).toLocaleString('it-IT',{minimumFractionDigits:n,maximumFractionDigits:n});
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const FX=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
const api=ccy=>({
 get:k=>k==='liquidity'?native:null,FX,FLAGS:Object.fromEntries(FX.map(x=>[x,x])),
 NAMES:Object.fromEntries(FX.map(x=>[x,x])),state:{liqCcy:ccy},
 plot:()=>'<svg></svg>',pageHero:()=>'<h1>FX</h1>',esc,fmt,date:x=>x,
 dayNow:()=>new Date().toISOString().slice(0,10)
});
const html=studio.render(api('GBP'));
assert.match(html,/class="drivers-gbp-credit-bridge"/);
assert.match(html,/LPMVTYI destagionalizzato/);
assert.match(html,/punti percentuali/);
assert.match(html,/non<\/b> al credito aziendale/);
assert.match(html,/LPMVTYI/);
assert(html.includes(fmt(mortgage.values.at(-1),1)+'% annuo nel '+mortgage.last_observation),
 'The published credit growth figure must follow the latest verified source period');
assert(html.includes(fmt(mortgage.values.at(-2),1)+'% del mese precedente'),
 'Prior-month comparison must be grounded in the source sidecar');
const delta=mortgage.values.at(-1)-mortgage.values.at(-2);
const formatted=(delta<0?'−':delta>0?'+':'')+fmt(Math.abs(delta),1);
assert(html.includes(formatted+' <b>punti percentuali</b>'),
 'Monthly change of the annual growth rate is in percentage points');
if(mortgage.last_observation==='2026-09')
 assert.match(html,/Money and Credit · 29 ottobre/);
else
 assert(!html.includes('Money and Credit · 29 ottobre'),
  'September 2026 release is not evidence about later reporting months');
assert.match(html,/non sono due misure confrontabili/);
assert.match(html,/fonte separata dal feed FX/);
assert.match(html,/RPWB56A/);
const original=html.split('data-liq-role="credit"')[1]?.split('</div>')[0]||'';
assert(original.includes('Ultimo '+native.GBP.credit.last_date+' · '+fmt(native.GBP.credit.last_value,2)),
 'Research-only September data must not silently change GBP native credit');
for(const ccy of FX.filter(x=>x!=='GBP')){
 assert(!studio.render(api(ccy)).includes('drivers-gbp-credit-bridge'),
  'GBP official secured credit source must be country-scoped: '+ccy);
}
console.log('BOE_GBP_SECURED_CREDIT_NEXT_PASS',JSON.stringify({
 latest:mortgage.last_observation,growthYoY:mortgage.values.at(-1),
 previous:mortgage.values.at(-2),nativeDate:native.GBP.credit.last_date,
 monthlyObservations:mortgage.dates.length,
 sourceOnly:true,pitVerified:false,fxSignal:false
}));

const growthPlots=[];
studio.render({...api('GBP'),plot:x=>{growthPlots.push(x);return '<svg></svg>';}});
const growth=growthPlots.find(x=>x.label==='Credito · fonte ufficiale separata GBP');
assert(growth,'GBP secured credit chart missing');
assert.deepEqual(growth.lines[0].values,mortgage.dates.map((d,i)=>({label:d,value:mortgage.values[i]})).slice(-80));
assert.match(growth.lines[0].name,/% annua/);
const oldMortgage=globalThis.FXQuantGBPBoESecuredCreditResearch;
try{
 const modified=structuredClone(mortgage);modified.values[0]=-0.2;modified.values[1]=0;
 globalThis.FXQuantGBPBoESecuredCreditResearch=modified;
 const plots=[];studio.render({...api('GBP'),plot:x=>{plots.push(x);return '<svg></svg>';}});
 const v=plots.find(x=>x.label==='Credito · fonte ufficiale separata GBP').lines[0].values;
 if(modified.values.length<=80)assert.deepEqual(v.slice(0,2).map(p=>p.value),[-0.2,0]);
}finally{globalThis.FXQuantGBPBoESecuredCreditResearch=oldMortgage;}
console.log('NEXT_GBP_SECURED_GROWTH_CHART_PASS',mortgage.last_observation);

const ccs=mortgage.lending_conditions;
assert(ccs,'Expected verified production CCS sidecar');
const ccsPlots=[];
const ccsHtml=studio.render({...api('GBP'),plot:x=>{ccsPlots.push(x);return '<svg></svg>';}});
assert.match(ccsHtml,/BANK OF ENGLAND · CREDIT CONDITIONS SURVEY/);
assert.match(ccsHtml,/Positivo = maggiore disponibilità, negativo = minore disponibilità/);
const ccsChart=ccsPlots.find(x=>x.label==='Condizioni di credito · fonte ufficiale separata GBP');
assert(ccsChart);
assert.deepEqual(ccsChart.lines[0].values,ccs.dates.map((label,i)=>({label,value:ccs.values[i]})));
assert(!studio.render(api('USD')).includes('BANK OF ENGLAND · CREDIT CONDITIONS SURVEY'));
const priorCCS=globalThis.FXQuantGBPBoESecuredCreditResearch;
try{
 globalThis.FXQuantGBPBoESecuredCreditResearch={...mortgage,lending_conditions:{...ccs,positive_means:'tightening'}};
 assert(!studio.render(api('GBP')).includes('BANK OF ENGLAND · CREDIT CONDITIONS SURVEY'));
}finally{globalThis.FXQuantGBPBoESecuredCreditResearch=priorCCS;}
console.log('NEXT_GBP_CCS_CHART_PASS',ccs.latest_observation,ccs.values.at(-1));
