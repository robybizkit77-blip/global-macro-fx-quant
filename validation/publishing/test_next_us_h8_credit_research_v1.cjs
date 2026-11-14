'use strict';
/* Fed H8 via FRED: separate USD research only, never direct FX Core. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const source=require(path.join(root,'site/fx-quant-v2/next/us-h8-bank-credit-research-v1.js'));
const studio=require(path.join(root,'site/fx-quant-v2/next/liquidity-credit-studio.js'));
const native=JSON.parse(fs.readFileSync(path.join(root,'live_data/sections/NATIVE_LIQ_DATA.json'),'utf8'));
const html=fs.readFileSync(path.join(root,'site/fx-quant-v2/next/index.html'),'utf8');
assert.match(html,/us-h8-bank-credit-research-v1\.js\?v=\d+/);
assert.equal(source.schema,'GMFQ_NEXT_US_H8_CREDIT_RESEARCH_V1');
assert.equal(source.status,'VERIFIED_FED_H8_FRED_MIRROR_RESEARCH_ONLY');
assert.equal(source.series_id,'TOTBKCR');
assert.equal(source.publisher,'Board of Governors of the Federal Reserve System (US)');
assert.equal(source.frequency,'W');
assert.equal(source.seasonally_adjusted,true);
assert.equal(source.unit,'miliardi USD');
assert.equal(source.eligible_for_fx_core,false);
assert.equal(source.eligible_for_backtest,false);
assert.equal(source.first_release_pit_verified,false);
assert.equal(source.observation_is_not_publication_date,true);
assert.match(source.source_url,/^https:\/\/fred\.stlouisfed\.org\/series\/TOTBKCR$/);
assert.equal(source.latest_observation,source.dates.at(-1));
assert.equal(source.dates.length,source.values.length);
assert(source.dates.length>=10);
for(let i=0;i<source.dates.length;i++){
 const d=source.dates[i],v=source.values[i];
 assert.match(d,/^\d{4}-\d{2}-\d{2}$/);
 assert(Number.isFinite(v)&&v>15000&&v<35000);
 assert.equal(new Date(d+'T12:00:00Z').getUTCDay(),3);
 if(i>0){assert(d>source.dates[i-1]);assert(Math.abs(v/source.values[i-1]-1)<.1);}
}
const overlap=source.dates.indexOf('2026-09-09');
if(overlap!==-1)assert(Math.abs(source.values[overlap]/19866.6568-1)<.02);
const fmt=(v,n=2)=>Number(v).toLocaleString('it-IT',{minimumFractionDigits:n,maximumFractionDigits:n});
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const FX=['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'];
const api=ccy=>({get:k=>k==='liquidity'?native:null,FX,
 FLAGS:Object.fromEntries(FX.map(x=>[x,x])),NAMES:Object.fromEntries(FX.map(x=>[x,x])),
 state:{liqCcy:ccy},plot:()=>'<svg></svg>',
 pageHero:(a,b,c)=>'<h1>'+b+'</h1>',esc,fmt,date:x=>x,
 dayNow:()=>new Date().toISOString().slice(0,10)});
const usd=studio.render(api('USD'));
assert.match(usd,/class="drivers-cad-official drivers-us-official"/);
assert.match(usd,/Fed H\.8/i);
assert.match(usd,/TOTBKCR/);
assert.match(usd,/titoli bancari/);
assert.match(usd,/SLOOS/);
assert.match(usd,/non deduciamo flussi valutari/i);
const nativeCredit=usd.split('data-liq-role="credit"')[1].split('</div>')[0];
assert(!nativeCredit.includes('TOTBKCR'),'never substitute research into the canonical credit fact');
assert(!studio.render(api('EUR')).includes('drivers-us-official'),'US credit must be country-specific');
console.log('USD_FED_H8_RESEARCH_SIDECAR_PASS',JSON.stringify({
 sourceDate:source.latest_observation,observations:source.dates.length,
 latest:source.values.at(-1),lastNative:native.USD.credit.last_date,
 canonicalUnchanged:true,signal:false
}));
