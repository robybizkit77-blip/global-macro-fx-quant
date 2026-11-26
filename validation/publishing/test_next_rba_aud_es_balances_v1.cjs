'use strict';
/* AUD weekly official RBA ES reserves: no Core writes, no FX flow inference. */
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'../..');
const source=require(path.join(root,'site/fx-quant-v2/next/aud-rba-es-balances-research-v1.js'));
require(path.join(root,'site/fx-quant-v2/next/aud-rba-business-credit-growth-research-v1.js'));
const studio=require(path.join(root,'site/fx-quant-v2/next/liquidity-credit-studio.js'));
const native=JSON.parse(fs.readFileSync(path.join(root,'live_data/sections/NATIVE_LIQ_DATA.json'),'utf8'));
const idx=fs.readFileSync(path.join(root,'site/fx-quant-v2/next/index.html'),'utf8');
assert.match(idx,/aud-rba-es-balances-research-v1\.js\?v=\d+/);
assert.equal(source.schema,'GMFQ_NEXT_AUD_RBA_ES_BALANCES_V1');
assert.equal(source.status,'VERIFIED_RBA_WEEKLY_ES_BALANCE_RESEARCH_ONLY');
assert.equal(source.publisher,'Reserve Bank of Australia');
assert.equal(source.source_contract,'RBA weekly balance sheet / Exchange Settlement balances');
assert.equal(source.unit,'milioni AUD');
assert.equal(source.frequency,'W');
assert.equal(source.first_release_pit_verified,false);
assert.equal(source.source_release_timestamp_verified,false);
assert.equal(source.observation_is_not_publication_date,true);
assert.equal(source.eligible_for_fx_core,false);
assert.equal(source.eligible_for_backtest,false);
assert.equal(source.asof_canonical_overlap,'2026-09-16');
assert.equal(source.value_canonical_overlap,173965);
assert.equal(source.source_url,'https://www.rba.gov.au/statistics/balance-sheet/');
assert.match(source.source_period,/^\d{4}-\d{2}-\d{2}$/);
assert(Number.isInteger(source.latest_balance_million_aud)&&source.latest_balance_million_aud>10000);
assert(Number.isInteger(source.weekly_movement_million_aud));
assert.equal(source.latest_balance_million_aud-source.weekly_movement_million_aud,
 source.previous_implied_million_aud);
assert(new Date(source.source_period+'T12:00:00Z')<=new Date());
assert.equal(new Date(source.source_period+'T12:00:00Z').getUTCDay(),3);
const anchor=native.AUD.liquidity.dates.indexOf(source.asof_canonical_overlap);
assert(anchor>=0);
assert.equal(native.AUD.liquidity.values[anchor],source.value_canonical_overlap);
const FX=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
const fmt=(v,n=2)=>Number(v).toLocaleString('it-IT',{minimumFractionDigits:n,maximumFractionDigits:n});
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const api=ccy=>({get:k=>k==='liquidity'?native:null,FX,
 FLAGS:Object.fromEntries(FX.map(x=>[x,x])),
 NAMES:Object.fromEntries(FX.map(x=>[x,x])),
 state:{liqCcy:ccy},plot:()=>'<svg></svg>',
 pageHero:()=>'<h1>Research</h1>',esc,fmt,date:x=>x,
 dayNow:()=>new Date().toISOString().slice(0,10)});
const html=studio.render(api('AUD'));
assert.match(html,/class="drivers-aud-es-bridge"/);
assert.match(html,/SECONDO CANALE, NON SECONDA CONFERMA/);
assert.match(html,/Fonte: bilancio settimanale RBA/);
assert.match(html,/non<\/b> nuovi prestiti/);
assert.match(html,/valore precedente implicito/);
assert.match(html,/A3 AESAT giornaliera/);
assert.match(html,/liquidità netta trasferita ai mercati/);
const reserves=html.split('class="drivers-aud-es-bridge"')[1].split('</div>')[0];
const move=source.weekly_movement_million_aud;
const signed=(move>0?'+':move<0?'−':'')+
 new Intl.NumberFormat('it-IT',{useGrouping:'always'}).format(Math.abs(move));
assert(reserves.includes('Al '+source.source_period));
assert(reserves.includes(fmt(source.latest_balance_million_aud,0)+' milioni AUD'));
assert(reserves.includes(signed+' milioni sulla settimana'));
assert.match(html,/movimento pubblicato/);
const nativeFact=html.split('data-liq-role="liquidity"')[1]?.split('</div>')[0]||'';
assert(nativeFact.includes('Ultimo '+native.AUD.liquidity.last_date+' · '+fmt(native.AUD.liquidity.last_value,2)),
 'Official ES research may not silently overwrite original native RBA liquidity');
for(const c of FX.filter(x=>x!=='AUD'))
 assert(!studio.render(api(c)).includes('drivers-aud-es-bridge'),c);
console.log('RBA_ES_BALANCES_NEXT_SOURCE_ONLY_PASS',JSON.stringify({
 lastObserved:source.source_period,
 amount:source.latest_balance_million_aud,
 movement:source.weekly_movement_million_aud,
 canonicalAsOf:native.AUD.liquidity.last_date,
 sourceOnly:true,notAnFXSignal:true
}));

 // Recent weekly charts preserve the two valid dates and source semantics;
 // old native history stays separately visible and is never interpolated.
 const boe=require(path.join(root,'site/fx-quant-v2/next/gbp-boe-reserves-research-v1.js'));
 const before=JSON.stringify(native);
 for(const ccy of ['GBP','AUD']){
  const plots=[];
  const rendered=studio.render({...api(ccy),plot:x=>{plots.push(x);return '<svg></svg>';}});
  const recent=plots.find(x=>x.label==='Liquidità · ultima settimana '+ccy);
  const historical=plots.find(x=>x.label==='Liquidità · storico originario '+ccy);
  assert(recent&&historical,ccy+' needs separate recent and historical charts');
  const pts=recent.lines[0].values;
  assert.equal(pts.length,2);
  const expected=ccy==='GBP'?boe:source;
  assert.equal(pts[1].label,expected.source_period);
  assert.equal(pts[1].value,ccy==='GBP'?boe.latest_balance_million_gbp:source.latest_balance_million_aud);
  assert.equal(pts[0].value,ccy==='GBP'?boe.previous_balance_million_gbp:source.previous_implied_million_aud);
  assert.equal(Date.parse(pts[1].label)-Date.parse(pts[0].label),7*86400000);
  assert.equal(historical.lines[0].values.at(-1).label,native[ccy].liquidity.last_date);
  assert.match(rendered,/nessuna interpolazione fra periodi mancanti/);
  if(ccy==='AUD')assert.match(recent.lines[0].name,/precedente implicito/);
 }
 assert.equal(JSON.stringify(native),before);
 const original=globalThis.FXQuantAUDESBalancesResearch;
 try{
  globalThis.FXQuantAUDESBalancesResearch={...original,previous_implied_million_aud:1};
  const plots=[];
  studio.render({...api('AUD'),plot:x=>{plots.push(x);return '<svg></svg>';}});
  assert(!plots.some(x=>x.label==='Liquidità · ultima settimana AUD'));
 }finally{globalThis.FXQuantAUDESBalancesResearch=original;}
 console.log('NEXT_WEEKLY_RESERVES_CHARTS_PASS GBP AUD');
