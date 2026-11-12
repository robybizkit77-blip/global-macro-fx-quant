'use strict';
/* Real-data contract: one honest, readable desk narrative for every one of the
 * canonical 28 FX crosses. No invented trade edge or same-day money-market spread.
 */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const read=p=>JSON.parse(fs.readFileSync(path.join(root,p),'utf8'));
const next='site/fx-quant-v2/next/';
const engine=require(path.join(root,next+'decision-journey.js'));
const rates=require(path.join(root,next+'fx-rates-bridge.js'));
const desk=require(path.join(root,next+'pair-desk-narrative.js'));
const model=read('live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json');
const prices=read('live_data/sections/ECB_G8_PRICE_HISTORY.json');
const macro=read('live_data/sections/MACRO_THERMOMETER_DATA.json').currencies;
const ois=read('site/fx-quant-v2/ois-pricing-snapshot.json');
const cot=read('live_data/sections/V250_COT_CHART_DATA.json');
const gov=read('live_data/sections/NATIVE_RATES_DATA.json');
const aud=read('site/fx-quant-v2/aud-rba-f2-history-research.json');
const chf=read('site/fx-quant-v2/chf-snb-paired-history.json');
const nzd=read('site/fx-quant-v2/nzd-b2-postroll-web-research.json');
// Keep source dates point-in-time: live monetary quotes must not be rejected
// solely because the regression test froze a previous trading session.
const now=prices.last_as_of;
assert.match(now,/^\d{4}-\d{2}-\d{2}$/,'Use the dated canonical FX snapshot');
const esc=x=>String(x).replace(/[&<>"']/g,c=>({
 '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
})[c]);
const keys=Object.keys(model.pairs||{}).sort();
assert.equal(keys.length,28,'exactly 28 pair snapshots');
const seen=new Set();
for(const key of keys){
 const profile=engine.profile(key,model,prices,now);
 const ratesView=rates.snapshot(gov,prices,key,model.price_asof,now,aud,chf,nzd);
 const args={key,model,macro,ois,cot,profile,ratesView,now,esc};
 const result=desk.interpret(args);
 const html=desk.render(args);
 assert.equal(result.available,true,key+' source snapshot exists');
 assert.equal(result.key,key);
 assert.equal(result.asof,model.price_asof);
 assert.ok(result.judgment.length>25);
 assert.ok(result.watch.length>25);
 assert.ok(result.macro.includes(key.slice(0,3)+':')&&result.macro.includes(key.slice(3)+':'),key+' bilateral macro');
 assert.ok(result.pricing.includes('Non calcoliamo uno spread monetario')||
   result.pricing.includes('nessuna conclusione sul repricing relativo'),key+' avoids false OIS spread');
 assert.ok(result.positioning.includes('COT settimanale')||
   result.positioning.includes('non conferma'),key+' COT provenance');
 assert.ok(html.includes('data-serafini-pair="'+key+'"'),key+' render');
 assert.ok(html.includes('baseline macro del modello'),key+' baseline provenance');
 assert.ok(!/undefined|NaN|Infinity/.test(html),key+' no fabricated numeric output');
 seen.add(key);
}
assert.equal(seen.size,28);
const usd=desk.countryMacro('USD',macro,now);
assert.match(usd,/inflazione/);
assert.match(usd,/disoccupazione/);
const fut=structuredClone(macro);
fut.USD.inflation.as_of='2026-12';
assert.ok(!desk.countryMacro('USD',fut,now).includes('inflazione '),
 'do not use future inflation observation');
const futureCot=structuredClone(cot);
futureCot.USD.dates[futureCot.USD.dates.length-1]='2026-12-01';
assert.equal(desk.cotObs('USD',futureCot,now),null,'no future COT');
const mismatch=desk.interpret({
 key:'EURUSD',model,macro,ois,cot,now,esc,
 profile:{key:'EURUSD',fresh:false,closes:[],asof:'2026-11-06'},
 ratesView:{ready:false}
});
assert.match(mismatch.price,/sospendiamo la conferma/);
assert.match(mismatch.relation,/non è disponibile/);
const goodPair='AUDCAD';
const pairArgs={key:goodPair,model,macro,ois,cot,now,
 profile:engine.profile(goodPair,model,prices,now),
 ratesView:rates.snapshot(gov,prices,goodPair,model.price_asof,now,aud,chf,nzd)};
const x=desk.interpret(pairArgs);
for(const ccy of ['AUD','CAD']){
 const usable=desk.pricingObs(ccy,ois,now);
 assert.match(x.pricing,usable?new RegExp(ccy+' futures/proxy 6M'):
  new RegExp(ccy+' senza 6M verificabile'),
  ccy+' live quote must obey its point-in-time observation date');
}
// Synthetic fixture tests presentation independently from the live quote clock.
const alignedOis=structuredClone(ois);
for(const ccy of ['AUD','CAD']){
 alignedOis.currencies[ccy]={kind:'FUTURES',quality:'FONTE UFFICIALE',
  as_of:now,horizons:{'6m':{as_of:now,rate:3.25,change_1d_bp:1.5}}};
}
const aligned=desk.interpret({...pairArgs,ois:alignedOis});
assert.match(aligned.pricing,/AUD futures\/proxy 6M/);
assert.match(aligned.pricing,/CAD futures\/proxy 6M/);
assert.match(aligned.pricing,/Non calcoliamo uno spread monetario/);
alignedOis.currencies.AUD.horizons['6m'].as_of='2099-01-01';
const future=desk.interpret({...pairArgs,ois:alignedOis});
assert.match(future.pricing,/AUD senza 6M verificabile/);
assert.doesNotMatch(future.pricing,/AUD futures\/proxy 6M/,
 'Future-dated monetary inputs must never enter a current pair narrative');
const index=fs.readFileSync(path.join(root,next+'index.html'),'utf8');
const app=fs.readFileSync(path.join(root,next+'app.js'),'utf8');
const journey=fs.readFileSync(path.join(root,next+'decision-journey.js'),'utf8');
assert.match(index,/pair-desk-narrative\.js\?v=18/);
assert.ok(index.indexOf('pair-desk-narrative.js')<index.indexOf('decision-journey.js'));
assert.match(journey,/FXQuantPairDesk\.render/);
assert.ok(app.includes("route==='overview'||route==='pairs'"),
 'do not duplicate the generic pair essay before the new narrative');
console.log('NEXT_PAIR_DESK_V18_PASS: 28/28 source-dated pairs, no future macro/COT, no false OIS spread, no duplicated pair essay.');
