'use strict';
/* Date/contract/fixing verification tests. Every assertion is read-only. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const load=p=>JSON.parse(fs.readFileSync(path.join(root,p),'utf8'));
const readingApi=require('../site/fx-quant-v2/assets/ois-same-contract-reading-v1.js');
const adapter=require('../site/fx-quant-v2/assets/ois-rates-fx-context-v1.js');
const futures=load('site/fx-quant-v2/ois-same-contract-repricing-research.json');
const estimates=load('live_data/sections/CB_PRICING_ESTIMATED.json');
const rates=load('live_data/sections/NATIVE_RATES_DATA.json');
const fx=load('live_data/sections/ECB_G8_PRICE_HISTORY.json');
const today=new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Rome',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
// The latest ECB fixing is an observation, NOT today's clock date. Futures may legitimately be newer.
assert.ok(fx.last_as_of<=today,'ECB fixing cannot be from the future');
const tenors=['3m','6m','12m'];
const clone=x=>JSON.parse(JSON.stringify(x));
const observed={};
for(const c of ['USD','EUR','CHF']){
 const z=estimates.currencies[c],shown={horizons:{}};
 assert.equal(z.status,'ESTIMATED_ACTIVE',c);
 for(const t of tenors){
  const h=z.horizons[t];
  shown.horizons[t]={rate:h.rate,contract:h.contract,as_of:h.quote_as_of,
    kind:'FUTURES SECONDARI',quality:'STIMA INDICATIVA'};
 }
 const reading=readingApi.interpret(c,futures,shown);
 if(reading.status==='NON_VERIFICABILE'){
  assert.deepEqual(reading.matchedTenors,[]);
  assert.ok(tenors.every(t=>
    futures.currencies[c][t].status==='QUARANTINED_CURRENT_DAY'&&
    futures.currencies[c][t].contract===shown.horizons[t].contract&&
    futures.currencies[c][t].as_of===shown.horizons[t].as_of),
    c+' must have source-matched quarantined futures');
  const model=adapter.evaluate(c,reading,rates,fx,today);
  assert.equal(model.status,'NOT_VERIFIED');
  assert.equal(model.trade_signal,null);
  assert.equal(model.policy_probability,null);
  observed[c]={model,reading,rate:adapter.rateTwoYear(c,rates,today),
    fx:adapter.fxFixing(c,fx,today)};
  continue;
 }
 assert.equal(reading.status,'LETTURA_DESCRITTIVA_FUTURES');
 assert.ok(reading.matchedTenors.length>0);
 for(const t of reading.matchedTenors){
  assert.equal(reading.sourceDates[t],shown.horizons[t].as_of);
  const v=futures.currencies[c][t].one_day;
  assert.equal(reading.oneDayBp[t],readingApi.validMove(futures.currencies[c][t],v,1)?
    v.change_bp:null);
 }
 const model=adapter.evaluate(c,reading,rates,fx,today);
 assert.equal(model.status,'READ_ONLY_TRIANGULATION');
 assert.equal(model.trade_signal,null);
 assert.equal(model.policy_probability,null);
 assert.equal(model.read_only,true);
 assert.ok(model.fxText.includes('Fixing BCE'));
 assert.ok(model.summary.includes('non dimostrano causalità'));
 assert.equal(model.fx.state,'FIXING_VERIFIED');
 const hist=rates[c].history2;
 const delta=Math.round((hist.values.at(-1)-hist.values.at(-2))*100000)/1000;
 assert.equal(model.rate.changeBp,delta,'derive 2Y delta from last two dated bars, never opaque chg2_bp');
 assert.equal(model.rate.deltaMismatch,
   Math.abs(delta-rates[c].chg2_bp)>0.2);
 observed[c]={model,reading,rate:model.rate,fx:model.fx};
}
assert.equal(observed.USD.rate.state,'HISTORY_VERIFIED');
assert.equal(observed.EUR.rate.state,'HISTORY_VERIFIED');
assert.equal(observed.CHF.rate.state,'DATED_HISTORICAL');
assert.equal(observed.CHF.model.aligned.length,0);
assert.match(observed.CHF.model.rateText,/troppo datata/);
for(const tenor of ['6m','12m']){
 const active=observed.USD.model.status==='READ_ONLY_TRIANGULATION';
  const isAligned=active&&observed.USD.rate.day===observed.USD.reading.sourceDates[tenor]&&
    Number.isFinite(observed.USD.reading.oneDayBp?.[tenor]);
 assert.equal(observed.USD.model.aligned.includes(tenor),isAligned,
  'USD 2Y and '+tenor+' futures are aligned only with the same observed date');
}
const eurRateDate=observed.EUR.model.rate.day;
const eurFuturesDate=observed.EUR.reading.sourceDates['12m'];
assert.equal(observed.EUR.model.aligned.includes('12m'),eurRateDate===eurFuturesDate,
  'EUR 2Y and 12M futures must share their real observation date');
const eurMixedDates={...observed.EUR.reading,
 sourceDates:{...observed.EUR.reading.sourceDates,
  '12m':eurFuturesDate===eurRateDate?'2026-11-04':eurRateDate}};
assert.equal(adapter.evaluate('EUR',eurMixedDates,rates,fx,today).aligned.includes('12m'),false,
  'Different 2Y and futures observation dates must never be silently joined');
assert.equal(observed.USD.fx.pair,'EUR/USD');
assert.equal(observed.EUR.fx.pair,'EUR/USD');
assert.equal(observed.CHF.fx.pair,'EUR/CHF');
assert.ok(Math.abs(observed.USD.fx.changePct-
  (fx.rows.at(-1).USD/fx.rows.at(-2).USD-1)*100)<0.0002);
assert.ok(Math.abs(observed.CHF.fx.changePct-
  (fx.rows.at(-1).CHF/fx.rows.at(-2).CHF-1)*100)<0.0002);
// A source carrying an apparent current date without consistent dated 2Y
// history is unsafe, even if chg2_bp claims a large or attractive move.
const badRates=clone(rates);
badRates.USD['2Y']+=0.1;
assert.equal(adapter.rateTwoYear('USD',badRates,today).state,'NOT_VERIFIED');
const futureRates=clone(rates);
futureRates.USD.date='2099-01-01';
assert.equal(adapter.rateTwoYear('USD',futureRates,today).state,'NOT_VERIFIED');
const duplicated=clone(rates);
duplicated.USD.history2.dates[duplicated.USD.history2.dates.length-2]=
  duplicated.USD.history2.last_date;
assert.equal(adapter.rateTwoYear('USD',duplicated,today).state,'NOT_VERIFIED');
const dishonest=clone(rates);
dishonest.USD.chg2_bp=999;
const computed=adapter.rateTwoYear('USD',dishonest,today);
assert.equal(computed.changeBp,observed.USD.rate.changeBp);
assert.equal(computed.deltaMismatch,true);
// A future or forged ECB FX fixing must never be treated as a verified price.
const badFx=clone(fx);badFx.rows.at(-1).Date='2099-01-01';
assert.equal(adapter.fxFixing('USD',badFx,today).state,'NOT_VERIFIED');
const negativeFx=clone(fx);negativeFx.rows.at(-1).CHF=-1;
assert.equal(adapter.fxFixing('CHF',negativeFx,today).state,'NOT_VERIFIED');
// Latest futures contract day differs from official 2Y day: source separation.
const early=clone(futures);
early.currencies.USD['12m'].as_of='2026-11-04';
const staleReading={...observed.USD.reading,
 latestDate:'2026-11-05',sourceDates:{...observed.USD.reading.sourceDates,'12m':'2026-11-04'}};
const mixed=adapter.evaluate('USD',staleReading,rates,fx,today);
assert.equal(mixed.aligned.includes('12m'),false);
// Do not silently turn CHF's September Treasury observation into 5 Nov.
assert.equal(adapter.rateTwoYear('CHF',rates,today).day,'2026-09-30');
assert.equal(adapter.evaluate('USD',null,rates,fx,today).status,'NOT_VERIFIED');
console.log('FXV2_OIS_2Y_FX_CONTEXT_PASS',JSON.stringify({
  currencies:3,usd2y:observed.USD.model.rate.changeBp,
  eur2y:observed.EUR.model.rate.changeBp,
  chf2y_as_of:observed.CHF.model.rate.day,
  checked_fx_fixing_date:observed.USD.model.fx.date,
  dated_evidence_only:true,no_core_mutation:true,
  policy_probability:null,trade_signal:null
}));