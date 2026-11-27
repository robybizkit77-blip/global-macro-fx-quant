'use strict';
/* Independent economic-interpretation contract: no new market quotes, no
 * reclassification of the restricted credit research, no fictitious flows.
 */
const assert=require('node:assert/strict');
const path=require('node:path');
const fs=require('node:fs');
const root=path.resolve(__dirname,'../..');
const audit=require(path.join(root,'site/fx-quant-v2/next/fx-driver-market-audit.js'));
const now='2026-11-14';
const ccy='USD', pair='EURUSD';
const withPricing=(change1d=null,change1w=null)=>({currencies:{
 USD:{kind:'FUTURES SECONDARI',quality:'STIMA INDICATIVA',horizons:{
  '6m':{rate:4.515,as_of:'2026-11-13',change_1d_bp:change1d,change_1w_bp:change1w}}}
}});
const levelOnly=audit.policy(ccy,withPricing(),now);
assert(levelOnly.ready);
assert.match(levelOnly.text,/non una variazione 1D\/1W certificata/);
assert.doesNotMatch(levelOnly.text,/1D [+−]\d/);
const change=audit.policy(ccy,withPricing(0,8),now);
assert(change.ready);
assert.match(change.text,/1D 0 pb/);
assert.match(change.text,/1W \+8 pb/);
assert.match(change.text,/OIS, futures e proxy non sono intercambiabili/);
const stale=audit.policy(ccy,{currencies:{USD:{horizons:{'6m':{rate:4.5,as_of:'2026-08-14'}}}}},now);
assert.match(stale.text,/^Storico:/);
assert.equal(audit.policy(ccy,{currencies:{USD:{horizons:{'6m':{rate:null,as_of:'2026-11-13'}}}}},now).ready,false);
const model=(date='2026-11-13')=>({
 price_asof:date,
 pairs:{EURUSD:{setup:{structuralFav:'USD',quality:'CON RISCHI',price:{state:'BAD'}}}}
});
const fx=audit.fx('USD',model(),now);
assert(fx.ready);
assert.match(fx.text,/in contrasto con la direzione favorita/);
assert.match(fx.text,/non prova che liquidità o politica monetaria abbiano causato/);
assert.equal(audit.fx('USD',model('2026-10-15'),now).ready,false);
assert.equal(audit.fx('USD',{},now).ready,false);
const asyncRisk={streams:{
 VIX:{date:'2026-11-13',value:19.3,previous:18.7},
 HY_OAS:{date:'2026-11-12',value:3.2,previous:3.3}
}};
assert.match(audit.riskCheck(asyncRisk,now),/non hanno la stessa data/);
const stress={streams:{
 VIX:{date:'2026-11-13',value:21,previous:18},
 HY_OAS:{date:'2026-11-13',value:3.4,previous:3.2}
}};
assert.match(audit.riskCheck(stress,now),/pressione sul rischio da verificare/);
stress.streams.HY_OAS.value=3.1;
assert.match(audit.riskCheck(stress,now),/non concordi/);
const escapes=x=>String(x??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const rendered=audit.render({get:key=>({
 ois:withPricing(),pairs:model(),risk:asyncRisk
})[key],esc:escapes,dayNow:()=>now},'USD');
assert.match(rendered,/DATI E DATE · TESI ≠ INGRESSO/);
assert.equal((rendered.match(/class="drivers-market-item"/g)||[]).length,2);
assert.match(rendered,/non hanno la stessa data/);
assert.doesNotMatch(rendered,/segnale (di )?(acquisto|vendita)/i);
// Real dataset support: run all eight G8 variants but never assume Core
// currency rank or the FX quote is current.
const pairs=JSON.parse(fs.readFileSync(path.join(root,'live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json'),'utf8'));
const pricing=JSON.parse(fs.readFileSync(path.join(root,'site/fx-quant-v2/ois-pricing-snapshot.json'),'utf8'));
const risk=JSON.parse(fs.readFileSync(path.join(root,'site/fx-quant-v2/cross-asset-live-data.json'),'utf8'));
const ccys=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
for(const c of ccys){
 const t=audit.review(c,{now,ois:pricing,pairs,risk});
 assert(t.policy.text.length>30&&t.fx.text.length>30&&t.risk.length>30,c);
}
console.log('NEXT_FX_DRIVER_MARKET_AUDIT_PASS',JSON.stringify({fixtureCases:12,currencies:ccys.length,sourceGuard:'read-only, no causal flow inference, separate dates'}));

// The Banks sheet explains the policy constraint and only uses dated,
// source-matched market moves via the same reader as Tassi & OIS.
require(path.join(root,'site/fx-quant-v2/next/rates-pricing-moves-v1.js'));
const banks=require(path.join(root,'site/fx-quant-v2/next/central-bank-studio.js'));
assert.equal(banks.classifyAction({action:'Invariato, con un voto per un rialzo'}).tone,'neutral');
const loadFile=p=>JSON.parse(fs.readFileSync(path.join(root,p),'utf8'));
const inputs={
 cb:loadFile('live_data/sections/NATIVE_CB_DATA.json'),
 macro:loadFile('live_data/sections/MACRO_THERMOMETER_DATA.json'),
 ois:pricing,
 oisOperational:loadFile('live_data/sections/OIS_OPERATIONAL_VIEW.json'),
 oisSameContract:loadFile('site/fx-quant-v2/ois-same-contract-repricing-research.json'),
 nzdDirectionalProxy:loadFile('live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json'),
 pairs,risk
};
const latestQuote=Object.values(pricing.currencies).flatMap(x=>Object.values(x.horizons))
 .map(x=>x.as_of).filter(Boolean).sort().at(-1);
const page=(c,data=inputs,today=latestQuote)=>banks.render({
 get:key=>data[key],FX:ccys,FLAGS:{},NAMES:{},state:{cbCcy:c},
 pageHero:(eyebrow,title,description)=>'<h1>'+title+'</h1><p>'+description+'</p>',
 esc:escapes,fmt:(v,d)=>v.toFixed(d),date:x=>x,dayNow:()=>today
});
for(const c of ccys){
 const html=page(c);
 const lead=html.split('<div class="drivers-bank-story">')[1].split('<div class="bank-policy-first">')[0];
 assert.doesNotMatch(lead,/%|punti base|\bOIS\b|\b6M\b/);
 for(const heading of ["Cosa va","Cosa frena","Cosa guardare"])assert(lead.includes("<h3>"+heading+"</h3>"));
 assert.match(html,/WANT · COSA COMUNICA/);
 assert.match(html,/CAN · MARGINE DI MANOVRA/);
 assert.match(html,/COSA PREZZA IL MERCATO/);
 assert.match(html,/CONFERMA SUL FOREX/);
 assert.match(html,/<details class="drivers-fold drivers-bank-sources"><summary>Approfondisci evidenze macro, riferimenti di mercato e fonti/);
 assert.equal((html.match(/aria-pressed="true"/g)||[]).length,1);
 assert(html.includes('data-bank-target="'+c+'"'),c);
 assert.equal((html.match(/Tasso ufficiale <strong>/g)||[]).length,1);
}
const suspicious=withPricing(15,20);
assert.match(page('USD',{...inputs,ois:suspicious,oisSameContract:null},now),
 /La variazione giornaliera o settimanale resta da verificare/);
assert.doesNotMatch(page('USD',{...inputs,ois:suspicious,oisSameContract:null},now),/1D \+15 pb/);
const verified={
 schema:'GMFQ_FXV2_SAME_CONTRACT_FUTURES_MOVES_V1',
 snapshot_research_only:true,eligible_for_fx_engine:false,eligible_for_policy_repricing_signals:false,
 official_ois_created:false,eligible_for_backtests_as_official_ois:false,
 currencies:{USD:{'6m':{
  status:'VERIFIED_SAME_CONTRACT_PRICE_CHANGE',source_type:'SECONDARY_LISTED_FUTURES_NOT_OIS',
  official_ois:false,contract:'ZQJ2027',as_of:'2026-11-13',rate_pct:4.515,change_1d_bp:1,
  one_day:{same_contract:true,same_expiration:true,from_date:'2026-11-12',to_date:'2026-11-13',
   current_rate_pct:4.515,reference_rate_pct:4.505,change_bp:1}
 }}}
};
suspicious.currencies.USD.horizons['6m'].contract='ZQJ2027';
assert.match(page('USD',{...inputs,ois:suspicious,oisSameContract:verified},now),/1D \+1 pb/);
assert.match(page('USD',{...inputs,ois:suspicious,oisSameContract:verified},now),
 /la stima dei tassi dei prossimi mesi è in rialzo/);
assert.match(page('USD',{...inputs,ois:suspicious,oisSameContract:verified},'2026-11-23'),
 /Ultimo riferimento storico a sei mesi/);
assert.doesNotMatch(page('USD',{...inputs,ois:suspicious,oisSameContract:verified},'2026-11-23'),/1D \+1 pb/);
assert.doesNotMatch(page('USD',{...inputs,ois:suspicious,oisSameContract:verified},'2026-11-23'),
 /la stima dei tassi dei prossimi mesi è in rialzo/);
assert.match(page('USD',{...inputs,ois:suspicious},'2026-11-12'),/Aspettative a sei mesi da verificare/);
const poisoned={...inputs,cb:{USD:{...inputs.cb.USD,context:'<script>alert(1)</script>'}}};
assert.match(page('USD',poisoned,now),/&lt;script&gt;/);
assert.doesNotMatch(page('USD',poisoned,now),/<script>/);
console.log('NEXT_CENTRAL_BANK_FIRST_READ_PASS: 8 banks, source checks, unavailable, historical and verified moves');
