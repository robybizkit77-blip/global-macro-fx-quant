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
assert.match(cad,/2026-08/);
assert.match(cad,/Fonte: Bank of Canada/);
const creditCard=cad.split('data-liq-role="credit"')[1].split('</div>')[0];
assert.match(creditCard,/Misura non verificabile/);
assert.doesNotMatch(creditCard,/(9\d{5}) milioni CAD/);
assert(!studio.render(api('USD')).includes('drivers-cad-official'));
console.log('CAD_OFFICIAL_CREDIT_RESEARCH_SIDECAR_PASS',JSON.stringify({
 observations:source.dates.length,latest:source.latest_observation,
 lastValue:source.values.at(-1),canonicalCadCredit: native.CAD.credit,
 fxRankingUnchanged:true,firstReleaseUnverified:true
}));
