'use strict';
/* RBA adjusted business credit growth; not stock-derived and never FX Core. */
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'../..');
const source=require(path.join(root,'site/fx-quant-v2/next/aud-rba-business-credit-growth-research-v1.js'));
const studio=require(path.join(root,'site/fx-quant-v2/next/liquidity-credit-studio.js'));
const native=JSON.parse(fs.readFileSync(path.join(root,'live_data/sections/NATIVE_LIQ_DATA.json'),'utf8'));
const html=fs.readFileSync(path.join(root,'site/fx-quant-v2/next/index.html'),'utf8');
assert.match(html,/aud-rba-business-credit-growth-research-v1\.js\?v=\d+/);
assert.equal(source.schema,'GMFQ_NEXT_AUD_RBA_BUSINESS_CREDIT_GROWTH_V1');
assert.equal(source.status,'VERIFIED_RBA_FIN_AGG_BUSINESS_GROWTH_RESEARCH_ONLY');
assert.equal(source.publisher,'Reserve Bank of Australia');
assert.equal(source.category,'business_credit_growth_adjusted');
assert.equal(source.breaks_adjusted,true);
assert.equal(source.seasonally_adjusted,true);
assert.equal(source.is_credit_stock,false);
assert.equal(source.first_release_pit_verified,false);
assert.equal(source.eligible_for_fx_core,false);
assert.equal(source.eligible_for_backtest,false);
assert.equal(source.observation_is_not_publication_date,true);
assert.match(source.source_url,/^https:\/\/www\.rba\.gov\.au\/statistics\/frequency\/fin-agg\/\d{4}\/fin-agg-\d{4}\.html$/);
assert.match(source.release_date,/^\d{4}-\d{2}-\d{2}$/);
assert.match(source.observation_period,/^\d{4}-\d{2}$/);
for(const k of ['monthly_growth_pct','prior_month_growth_pct','annual_growth_pct','prior_year_growth_pct'])
 assert(Number.isFinite(source[k])&&source[k]>-20&&source[k]<30,k);
assert(new Date(source.observation_period+'-01')<new Date(source.release_date));
assert(new Date(source.release_date)<new Date(Date.now()+86400000));
const FX=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
const fmt=(v,n=2)=>Number(v).toLocaleString('it-IT',{minimumFractionDigits:n,maximumFractionDigits:n});
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const api=ccy=>({get:k=>k==='liquidity'?native:null,FX,FLAGS:Object.fromEntries(FX.map(x=>[x,x])),
 NAMES:Object.fromEntries(FX.map(x=>[x,x])),state:{liqCcy:ccy},
 plot:()=>'<svg></svg>',pageHero:()=>'<h1>Research</h1>',esc,fmt,date:x=>x,
 dayNow:()=>new Date().toISOString().slice(0,10)});
const card=studio.render(api('AUD'));
assert.match(card,/class="drivers-cad-official drivers-aud-official"/);
assert.match(card,/RBA · CRESCITA UFFICIALE CORRETTA PER DISCONTINUITÀ/);
assert.match(card,/corretta per le rotture statistiche/);
assert.match(card,/non<\/b> una percentuale ricavata dai livelli D2/);
assert.match(card,/vintage non certificata|prima vintage non certificata/i);
assert.match(card,/pubblicato \d{4}-\d{2}-\d{2}/);
assert.match(card,/Fonte: RBA/);
const nativeCredit=card.split('data-liq-role="credit"')[1]?.split('</div>')[0]||'';
assert(nativeCredit.includes('2026')&&!nativeCredit.includes('2026-09'),
 'AUD research must not change canonical 2026-07 credit');
for(const other of FX.filter(x=>x!=='AUD'))assert(!studio.render(api(other)).includes('drivers-aud-official'),other);
console.log('AUD_RBA_ADJUSTED_BUSINESS_CREDIT_PASS',JSON.stringify({
 release:source.release_date,observed:source.observation_period,
 monthly:source.monthly_growth_pct,priorMonthly:source.prior_month_growth_pct,
 yoy:source.annual_growth_pct,canonicalCreditDate:native.AUD.credit.last_date,
 sourceOnly:true,notStockDerived:true
}));
