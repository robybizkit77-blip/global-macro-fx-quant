'use strict';
/* Source-contract snapshot for the 11-route Next liquidity dossier.
 * Research-only MACRO_SERIES candidates cannot be promoted into NATIVE_LIQ_DATA.
 */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const load=(name)=>JSON.parse(fs.readFileSync(path.join(root,name),'utf8'));
const policy=load('validation/liquidity/LIQUIDITY_SOURCE_POLICY_V1_2026-10-12.json');
const runtime=load('live_data/sections/NATIVE_LIQ_DATA.json');
const research=load('live_data/sections/MACRO_SERIES.json');
const sourceGate=require(path.join(root,'site/fx-quant-v2/next/liquidity-source-policy-gate-v1.js'));
const page=require(path.join(root,'site/fx-quant-v2/next/liquidity-credit-studio.js'));
const FX=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'],roles=['liquidity','credit','conditions'];
assert.equal(sourceGate.AS_OF,policy.as_of,'Published provenance date must match canonical registry snapshot');
assert.equal(policy.policy.fail_closed,true);
assert.equal(policy.policy.no_proxy_substitution,true);
for(const ccy of FX){
  const summary=sourceGate.review(ccy);
  assert.equal(summary.entries.length,3,ccy);
  for(const role of roles){
    const input=policy.mapped[ccy+'.'+role]||null;
    const mapped=sourceGate.MAP[ccy][role];
    assert.deepEqual(mapped,input?{ready:input.automation_ready===true,status:input.status}:null,
      ccy+'.'+role+' source contract snapshot drift');
    const current=sourceGate.check(ccy,role);
    assert(current.narrative.length>30,ccy+'.'+role+' must explain the source constraint');
    if(input?.automation_ready===true&&ccy+'.'+role!=='USD.conditions')
      assert(current.ready,ccy+'.'+role+' mapped but erroneously withheld');
    if(!input?.automation_ready)assert(!current.ready,ccy+'.'+role+' falsely auto-certified');
  }
}
assert.equal(sourceGate.check('USD','conditions').code,'VARIANT_NOT_ALIGNED');
assert(sourceGate.check('USD','conditions').withheld);
const sourceSLOOS=research.USD.find(x=>x.id==='US_SLOOS_CI_LARGE_MIDDLE_history_value');
assert(sourceSLOOS);
const nativeSLOOS=runtime.USD.conditions;
const matched=sourceSLOOS.dates.indexOf(nativeSLOOS.last_date);
assert(matched>=0,'Require the comparable native vintage to remain identifiable');
// Equal values at the overlapping date are evidence for a mapping review,
// not an authorization to change the registry or substitute the newer edition.
assert(Number.isFinite(sourceSLOOS.values[matched])&&Number.isFinite(nativeSLOOS.last_value));
assert(sourceSLOOS.last_date>=nativeSLOOS.last_date,'Research SLOOS cannot roll back the known native date');
assert.equal(sourceGate.check('USD','conditions').withheld,true,'Keep explicit source quarantine until registry review');
assert.equal(runtime.CAD.credit,null);
assert(research.CAD.some(x=>x.id==='CA_BUSINESS_LOANS_OUTSTANDING_history_value'));
assert.equal(sourceGate.check('CAD','credit').code,'NO_APPROVED_MAPPING');
const fmt=(x,n=2)=>Number(x).toLocaleString('it-IT',{minimumFractionDigits:n,maximumFractionDigits:n});
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const api=(ccy)=>({get:k=>k==='liquidity'?runtime:null,FX,
 FLAGS:Object.fromEntries(FX.map(x=>[x,x])),NAMES:Object.fromEntries(FX.map(x=>[x,x])),
 state:{liqCcy:ccy},plot:()=>'<svg></svg>',
 pageHero:(a,b,c)=>'<h1>'+b+'</h1><p>'+c+'</p>',esc,fmt,
 date:x=>x,dayNow:()=>'2026-11-14'});
for(const ccy of FX){
 const html=page.render(api(ccy));
 assert.equal((html.match(/data-liq-country=/g)||[]).length,8,ccy);
 assert.equal((html.match(/data-liq-role=/g)||[]).length,3,ccy);
 const detail=html.indexOf('<details class="drivers-source-provenance-fold"><summary>Fonti e storico</summary>');
 assert(detail>html.indexOf('PERCHÉ CONTA PER IL CAMBIO'),ccy);
 assert(html.indexOf('data-liq-role=')>detail,ccy+' technical evidence must be in the disclosure');
 assert(html.indexOf('COPERTURA')<0,ccy+' remove duplicate coverage badge');
 assert(!html.includes('[object Object]')&&!/\bundefined\b/.test(html),ccy);
}
const usd=page.render(api('USD'));
const usConditions=usd.split('data-liq-role="conditions"')[1]?.split('</div>')[0]||'';
assert.match(usConditions,/data-source-safety="withheld"/);
assert.match(usConditions,/Dato sospeso · variante da armonizzare/);
assert.match(usConditions,/SLOOS IN VERIFICA/);
assert.doesNotMatch(usConditions,/Ultimo 2026-07-01 · 0,00/);
const cad=page.render(api('CAD'));
const caCredit=cad.split('data-liq-role="credit"')[1]?.split('</div>')[0]||'';
assert.match(caCredit,/MAPPATURA ASSENTE/);
assert.match(caCredit,/Misura non verificabile/);
console.log('NEXT_LIQUIDITY_SOURCE_POLICY_PASS',JSON.stringify({
  currencies:FX.length,channels:FX.length*roles.length,asof:sourceGate.AS_OF,
  usdSLOOS:'WITHHELD_UNRESOLVED_VARIANT',cadCredit:'RESEARCH_NOT_PROMOTED'
}));

const residual=load('live_data/sections/ESTIMATED_RESIDUAL_GAPS.json');
const proxy=residual.lanes['CHF.credit'].lending_rate_proxy;
assert(proxy,'CHF production loan-price proxy required');
const renderCHF=(data= residual,ccy='CHF',plots=[])=>page.render({...api(ccy),get:k=>k==='liquidity'?runtime:k==='residualResearch'?data:null,dayNow:()=>new Date().toISOString().slice(0,10),plot:x=>{plots.push(x);return '<svg></svg>';}});
const plots=[],chf=renderCHF(residual,'CHF',plots);
assert.match(chf,/SNB · COSTO DEI NUOVI FINANZIAMENTI/);
assert.match(chf,/Proxy del costo del credito, non degli standard di concessione/);
assert(chf.includes(fmt(proxy.values.at(-1),2)+'%'));
assert(chf.includes(fmt(proxy.contract_counts.at(-1),0)));
const chart=plots.find(x=>x.label==='Costo del credito · proxy ufficiale CHF');assert(chart);
assert.deepEqual(chart.lines[0].values,proxy.dates.map((label,i)=>({label,value:proxy.values[i]})));
assert(!renderCHF(residual,'EUR').includes('SNB · COSTO DEI NUOVI FINANZIAMENTI'));
const bad=structuredClone(residual);bad.lanes['CHF.credit'].lending_rate_proxy.maturity='over_1_to_2_years';
assert(!renderCHF(bad).includes('SNB · COSTO DEI NUOVI FINANZIAMENTI'));
console.log('NEXT_CHF_LOAN_RATE_ACTUAL_PASS',proxy.latest_observation,proxy.values.at(-1),proxy.dates.length);
