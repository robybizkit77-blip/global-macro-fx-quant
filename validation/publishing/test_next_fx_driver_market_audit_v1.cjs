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
