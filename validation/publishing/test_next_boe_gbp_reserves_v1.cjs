'use strict';
/* BoE RPWB56A equivalent, official GBP reserves, separate from FX Core. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const issuer=require(path.join(root,'site/fx-quant-v2/next/gbp-boe-reserves-research-v1.js'));
const studio=require(path.join(root,'site/fx-quant-v2/next/liquidity-credit-studio.js'));
const native=JSON.parse(fs.readFileSync(path.join(root,'live_data/sections/NATIVE_LIQ_DATA.json'),'utf8'));
const index=fs.readFileSync(path.join(root,'site/fx-quant-v2/next/index.html'),'utf8');
assert.match(index,/gbp-boe-reserves-research-v1\.js\?v=\d+/);
assert.equal(issuer.schema,'GMFQ_NEXT_GBP_BOE_WEEKLY_RESERVES_V1');
assert.equal(issuer.status,'VERIFIED_BOE_WEEKLY_RESERVE_STOCK_RESEARCH_ONLY');
assert.equal(issuer.publisher,'Bank of England');
assert.equal(issuer.series_id,'RPWB56A');
assert.equal(issuer.source_contract,'BoE Weekly Report / Sterling Liabilities / Reserves balances');
assert.equal(issuer.unit,'milioni GBP');
assert.equal(issuer.frequency,'W');
assert.equal(issuer.seasonally_adjusted,false);
assert.equal(issuer.first_release_pit_verified,false);
assert.equal(issuer.eligible_for_fx_core,false);
assert.equal(issuer.eligible_for_backtest,false);
assert.equal(issuer.observation_is_not_publication_date,true);
assert.equal(issuer.asof_canonical_overlap,'2026-09-16');
assert.equal(issuer.value_canonical_overlap,638012);
assert(issuer.source_url.startsWith('https://www.bankofengland.co.uk/weekly-report/'));
assert.match(issuer.source_period,/^\d{4}-\d{2}-\d{2}$/);
assert.match(issuer.previous_period,/^\d{4}-\d{2}-\d{2}$/);
assert.match(issuer.published_on,/^\d{4}-\d{2}-\d{2}$/);
const dt=x=>Date.parse(x+'T12:00:00Z');
assert(dt(issuer.source_period)-dt(issuer.previous_period)===7*86400000);
assert(dt(issuer.published_on)>=dt(issuer.source_period));
assert(dt(issuer.published_on)<Date.now()+86400000);
assert.equal(issuer.latest_balance_million_gbp-issuer.previous_balance_million_gbp,issuer.weekly_change_million_gbp);
assert(issuer.latest_balance_million_gbp>300000);
const anchor=native.GBP.liquidity.dates.indexOf(issuer.asof_canonical_overlap);
assert(anchor>=0);
assert.equal(native.GBP.liquidity.values[anchor],issuer.value_canonical_overlap);
const FX=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
const fmt=(v,n=2)=>Number(v).toLocaleString('it-IT',{minimumFractionDigits:n,maximumFractionDigits:n});
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const api=ccy=>({
 get:k=>k==='liquidity'?native:null,FX,FLAGS:Object.fromEntries(FX.map(x=>[x,x])),
 NAMES:Object.fromEntries(FX.map(x=>[x,x])),state:{liqCcy:ccy},
 plot:()=>'<svg></svg>',pageHero:()=>'<h1>FX</h1>',
 esc,fmt,date:x=>x,dayNow:()=>new Date().toISOString().slice(0,10)
});
const gbp=studio.render(api('GBP'));
assert.match(gbp,/class="drivers-cad-official drivers-gbp-official"/);
assert.match(gbp,/BANK OF ENGLAND · RISERVE BANCARIE UFFICIALI/);
assert.match(gbp,/RPWB56A/);
assert(gbp.includes(fmt(issuer.latest_balance_million_gbp,0)),
 'BoE reserve amount must follow the latest official source');
assert(gbp.includes(fmt(issuer.previous_balance_million_gbp,0)),
 'BoE previous amount must follow the latest official source');
const movement=(issuer.weekly_change_million_gbp>0?'+':issuer.weekly_change_million_gbp<0?'−':'')+
 String(Math.abs(issuer.weekly_change_million_gbp)).replace(/\B(?=(\d{3})+(?!\d))/g,'.');
assert(gbp.includes(movement+' milioni GBP'),
 'BoE weekly movement and sign must come from observed source');
assert(gbp.includes('pubblicazione '+issuer.published_on),
 'BoE publication date must reflect source rather than a frozen fixture');
assert.match(gbp,/fonte separata dal feed FX/);
assert.match(gbp,/EUR\/GBP e GBP\/USD/);
assert.match(gbp,/non possiamo dedurre un allentamento/);
const core=gbp.split('data-liq-role="liquidity"')[1]?.split('</div>')[0]||'';
assert(core.includes('Ultimo '+native.GBP.liquidity.last_date+' · '+fmt(native.GBP.liquidity.last_value,2)),
 'BoE research must never change the canonical weekly GBP liquidity');
for(const ccy of FX.filter(x=>x!=='GBP'))
 assert(!studio.render(api(ccy)).includes('drivers-gbp-official'),
  'BoE reserves should be limited to GBP: '+ccy);
console.log('BOE_GBP_OFFICIAL_RESERVES_RESEARCH_PASS',JSON.stringify({
 date:issuer.source_period,publication:issuer.published_on,
 stock:issuer.latest_balance_million_gbp,movement:issuer.weekly_change_million_gbp,
 coreDate:native.GBP.liquidity.last_date,marketClaim:'none',tradeSignal:false
}));
