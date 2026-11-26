'use strict';
/* EUR NFC bank loans — official ECB BSI stock, separate research and FX. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const source=require(path.join(root,'site/fx-quant-v2/next/eur-ecb-nfc-credit-research-v1.js'));
const studio=require(path.join(root,'site/fx-quant-v2/next/liquidity-credit-studio.js'));
const native=JSON.parse(fs.readFileSync(path.join(root,'live_data/sections/NATIVE_LIQ_DATA.json'),'utf8'));
const html=fs.readFileSync(path.join(root,'site/fx-quant-v2/next/index.html'),'utf8');
assert.match(html,/eur-ecb-nfc-credit-research-v1\.js\?v=\d+/);
assert.equal(source.schema,'GMFQ_NEXT_EUR_ECB_NFC_CREDIT_RESEARCH_V1');
assert.equal(source.status,'VERIFIED_ECB_BSI_NFC_STOCK_RESEARCH_ONLY');
assert.equal(source.publisher,'European Central Bank / ESCB');
assert.equal(source.series_id,'BSI.M.U2.N.A.A20.A.1.U2.2240.Z01.E');
assert.equal(source.category,'nfc_loans_stock');
assert.equal(source.frequency,'M');
assert.equal(source.unit,'milioni EUR');
assert.equal(source.seasonally_adjusted,false);
assert.equal(source.eligible_for_fx_core,false);
assert.equal(source.eligible_for_backtest,false);
assert.equal(source.first_release_pit_verified,false);
assert.equal(source.observation_is_not_publication_date,true);
assert(source.source_url.startsWith('https://data.ecb.europa.eu/data/datasets/BSI/'));
assert.equal(source.latest_observation,source.dates.at(-1));
assert.equal(source.dates.length,source.values.length);
assert(source.dates.length>=10);
for(let i=0;i<source.dates.length;i++){
 const d=source.dates[i],v=source.values[i];
 assert.match(d,/^\d{4}-\d{2}$/);
 assert(Number.isFinite(v)&&v>3000000&&v<9000000);
 if(i>0) {
  const prev=source.dates[i-1],diff=((+d.slice(0,4))*12+(+d.slice(5)))-((+prev.slice(0,4))*12+(+prev.slice(5)));
  assert.equal(diff,1,'month gap or duplicate');
  assert(Math.abs(v/source.values[i-1]-1)<.1);
 }
}
assert(source.dates.includes('2026-07'));
assert(Math.abs(source.values[source.dates.indexOf('2026-07')]/5481083.172910931-1)<.02);
const FX=['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'];
const fmt=(v,n=2)=>Number(v).toLocaleString('it-IT',{minimumFractionDigits:n,maximumFractionDigits:n});
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const api=k=>({get:x=>x==='liquidity'?native:null,FX,
 FLAGS:Object.fromEntries(FX.map(x=>[x,x])),NAMES:Object.fromEntries(FX.map(x=>[x,x])),
 state:{liqCcy:k},plot:()=>'<svg></svg>',
 pageHero:(a,b,c)=>'<h1>'+b+'</h1>',esc,fmt,date:x=>x,
 dayNow:()=>'2026-11-14'});
const eur=studio.render(api('EUR'));
assert.match(eur,/class="drivers-cad-official drivers-eur-official"/);
assert.match(eur,/BCE \/ ESCB/);
assert.match(eur,/Prestiti alle imprese dell’Eurozona/);
assert.match(eur,/Il cumulato di due mesi/);
const monthly=source.values.at(-1)/source.values.at(-2)-1;
const twoMonths=source.values.at(-1)/source.values.at(-3)-1;
assert.match(eur,monthly>0&&twoMonths<0?/non è ancora una sequenza di accelerazione/:
 monthly>0&&twoMonths>0?/non provano che le banche stiano allentando gli standard/:
 /non è sufficiente a certificare un impulso positivo al credito/);
assert.match(eur,/vintage di prima pubblicazione non verificato/);
assert.match(eur,/Fonte: BCE/);
const coreFact=eur.split('data-liq-role="credit"')[1].split('</div>')[0];
assert(coreFact.includes('Ultimo '+native.EUR.credit.last_date+' · '+fmt(native.EUR.credit.last_value,2)),'ECB research must preserve current canonical EUR.credit value and date');
assert(!studio.render(api('USD')).includes('drivers-eur-official'));
assert(!studio.render(api('CAD')).includes('drivers-eur-official'));
console.log('EUR_ECB_NFC_RESEARCH_SIDECAR_PASS',JSON.stringify({
 sourceDate:source.latest_observation,observations:source.dates.length,
 latest:source.values.at(-1),nativeAsOf:native.EUR.credit.last_date,
 firstReleaseUnverified:true,sourceOnly:true
}));

 // The source is real when its producer has run; otherwise this explicitly
 // synthetic fixture tests the renderer only, never the published data.
 const liquidity=source.excess_liquidity||{
  series_id:'ILM.D.U2.C.EXLIQ.U2.EUR',
  source_url:'https://data.ecb.europa.eu/data/datasets/ILM/ILM.D.U2.C.EXLIQ.U2.EUR',
  frequency:'D',unit:'milioni EUR',first_release_pit_verified:false,
  eligible_for_fx_core:false,eligible_for_backtest:false,
  dates:Array.from({length:30},(_,i)=>new Date(Date.UTC(2026,9,15+i)).toISOString().slice(0,10)),
  values:Array.from({length:30},(_,i)=>2100000-i*1000),
  latest_observation:'2026-11-13'
 };
 const original=globalThis.FXQuantEURNFCCreditResearch,before=JSON.stringify(native);
 const current=ccy=>({...api(ccy),dayNow:()=>new Date().toISOString().slice(0,10)});
 try{
  globalThis.FXQuantEURNFCCreditResearch={...source,excess_liquidity:liquidity};
  const plots=[];
  const rendered=studio.render({...current('EUR'),plot:x=>{plots.push(x);return '<svg></svg>';}});
  assert.match(rendered,/BCE \/ EUROSISTEMA · LIQUIDITÀ IN ECCESSO/);
  assert(rendered.includes(fmt(liquidity.values.at(-1)/1000,2)+' miliardi EUR'));
  const chart=plots.find(x=>x.label==='Liquidità · fonte ufficiale separata EUR');
  assert(chart);
  assert.equal(chart.lines[0].values.at(-1).label,liquidity.latest_observation);
  assert.equal(chart.lines[0].values.at(-1).value,liquidity.values.at(-1));
  assert(!studio.render(current('USD')).includes('BCE / EUROSISTEMA · LIQUIDITÀ IN ECCESSO'));
  for(const changed of [{series_id:'ILM.D.U2.C.OTHER.U2.EUR'},{unit:'miliardi EUR'},{source_url:'https://example.com'}]){
   globalThis.FXQuantEURNFCCreditResearch={...source,excess_liquidity:{...liquidity,...changed}};
   assert(!studio.render(current('EUR')).includes('BCE / EUROSISTEMA · LIQUIDITÀ IN ECCESSO'));
  }
 }finally{globalThis.FXQuantEURNFCCreditResearch=original;}
 assert.equal(JSON.stringify(native),before);
 console.log('NEXT_ECB_EXLIQ_CHART_PASS',source.excess_liquidity?'actual':'synthetic rendering fixture',liquidity.latest_observation);

 // BLS signed values and period alignment: synthetic rendering fixture only
 // until the existing collector writes the official sidecar.
 const survey=source.lending_conditions||{
  series_id:'BLS.Q.U2.ALL.O.E.Z.B3.ST.S.WFNET',
  source_url:'https://data.ecb.europa.eu/data/datasets/BLS/BLS.Q.U2.ALL.O.E.Z.B3.ST.S.WFNET',
  frequency:'Q',unit:'net_percentage_balance',positive_means:'tightening',
  reference_period_is_previous_quarter:true,first_release_pit_verified:false,
  eligible_for_fx_core:false,eligible_for_backtest:false,
  dates:['2025-Q4','2026-Q1','2026-Q2','2026-Q3'],
  publication_quarters:['2026-Q1','2026-Q2','2026-Q3','2026-Q4'],
  values:[-2,4,7,8.55],latest_observation:'2026-Q3'
 };
 try{
  globalThis.FXQuantEURNFCCreditResearch={...source,lending_conditions:survey};
  const plots=[];
  const rendered=studio.render({...current('EUR'),plot:x=>{plots.push(x);return '<svg></svg>';}});
  assert.match(rendered,/BCE · BANK LENDING SURVEY/);
  assert(rendered.includes('Periodo osservato '+survey.latest_observation+' · trimestre di pubblicazione '+survey.publication_quarters.at(-1)));
  const chart=plots.find(x=>x.label==='Condizioni di credito · fonte ufficiale separata EUR');
  assert(chart);
  assert.deepEqual(chart.lines[0].values,survey.dates.map((label,i)=>({label,value:survey.values[i]})));
  assert(!studio.render(current('USD')).includes('BCE · BANK LENDING SURVEY'));
  for(const changed of [{series_id:'WRONG'},{positive_means:'easing'},{publication_quarters:survey.dates},{eligible_for_fx_core:true}]){
   globalThis.FXQuantEURNFCCreditResearch={...source,lending_conditions:{...survey,...changed}};
   assert(!studio.render(current('EUR')).includes('BCE · BANK LENDING SURVEY'));
  }
 }finally{globalThis.FXQuantEURNFCCreditResearch=original;}
 assert.equal(JSON.stringify(native),before);
 console.log('NEXT_ECB_BLS_CHART_PASS',source.lending_conditions?'actual':'synthetic rendering fixture',survey.latest_observation);
