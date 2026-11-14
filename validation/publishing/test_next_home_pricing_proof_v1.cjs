'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const ROOT=path.resolve(__dirname,'../..'),site='site/fx-quant-v2/next/';
const read=p=>fs.readFileSync(path.join(ROOT,p),'utf8');
const json=p=>JSON.parse(read(p));
new vm.Script(read(site+'home-pricing-proof-v1.js'),{filename:'home-pricing-proof-v1.js'});
globalThis.FXQuantPricingHistory=require('../../site/fx-quant-v2/next/rates-pricing-history-v1.js');
globalThis.FXQuantPricingMoves=require('../../site/fx-quant-v2/next/rates-pricing-moves-v1.js');
globalThis.FXQuantRelativePricing=require('../../site/fx-quant-v2/next/rates-relative-pricing-v1.js');
globalThis.FXQuantPairMonetary=require('../../site/fx-quant-v2/next/pair-monetary-bridge-v1.js');
const {inspectPair,inspectSessionWindow,horizonReading,choose,pairReturn,render}=require('../../site/fx-quant-v2/next/home-pricing-proof-v1.js');
const prices=json('live_data/sections/ECB_G8_PRICE_HISTORY.json'),
 pairs=json('live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json'),
 history=json(site+'rates-pricing-history-v1.json'),
 today=history.as_of;
const args={prices,pairs,history,today};
assert.equal(prices.last_as_of,'2026-11-13');
assert.equal(pairs.pair_count,28);
const selected=choose(args);
assert.equal(selected.length,2,'Expected one real USD pair and one real non-USD pair with same-date price check');
assert(selected[0].pair.includes('USD'),'First pair must contain USD');
assert(!selected[1].pair.includes('USD'),'Second example must avoid concentration on the USD');
assert(selected.every(x=>x.to<=today&&x.from<x.to));
for(const x of selected){
 assert(pairs.pairs[x.pair],'No invented FX pair '+x.pair);
 assert(['HISTORICAL_COMMON','HISTORICAL_PROXY_REFERENCE'].includes(x.pricingType));
 assert(['SEGNI_COHERENTI','SEGNI_DIVERGENTI','MOVIMENTO_CONTENUTO'].includes(x.comparison));
 assert(Number.isFinite(x.monetaryBp)&&Number.isFinite(x.fxPct));
 assert(x.sourceDates.money===x.sourceDates.spot,
  'FX and 6M moves must end on exactly the same source date');
 const fx=pairReturn(prices,x.pair,x.from,x.to,today);
 assert(fx&&Math.abs(x.fxPct-fx.percent)<.00001);
 const archive=globalThis.FXQuantPairMonetary.historicalWindow(history,x.base,x.quote,today,'1d');
 assert.equal(x.monetaryBp,archive.relativeBp,'Home must reuse pair dossier currency-priced 6M archive');
}
const eur=inspectPair('EURUSD',args);
assert(eur&&eur.from==='2026-11-11'&&eur.to==='2026-11-12');
assert.equal(eur.monetaryBp,-2.75,'EUR/USD must retain verified common 6M -2.75bp reference');
const html=render(args);
assert(html.includes('id="home-pricing-proof"'));
assert.equal((html.match(/class="home-pricing-proof-card"/g)||[]).length,2);
assert(html.includes('DALLE ASPETTATIVE AI CAMBI'));
assert(html.includes('non per attrattività di trading'));
assert(html.includes('non la prova che i tassi abbiano causato'));
assert(html.includes('rates-pricing-history-v1.json'));
assert(html.includes('ECB_G8_PRICE_HISTORY.json'));
assert(html.includes('ois-same-contract-repricing-research.json'));
for(const x of selected){
 assert(html.includes('data-home-pricing-pair="'+x.pair+'"'));
 assert(html.includes('data-command="pair:'+x.pair+'"'));
 assert(html.includes('data-home-pricing-to="'+x.to+'"'));
}
const reversed=structuredClone(pairs);
reversed.pairs.USDEUR=reversed.pairs.EURUSD;
const fwd=inspectPair('EURUSD',args);
const inv=inspectPair('USDEUR',{...args,pairs:reversed});
if(fwd&&inv){
 assert(Math.abs(fwd.monetaryBp+inv.monetaryBp)<.011,
  'Reverse currency repricing must invert the sign');
 assert(Math.sign(fwd.fxPct)===-Math.sign(inv.fxPct),
  'Reverse ECB pair must invert direction, not reuse the wrong quote');
}
const missingDate=structuredClone(prices);
missingDate.rows=missingDate.rows.filter(r=>r.Date!=='2026-11-11');
assert.equal(inspectPair('EURUSD',{...args,prices:missingDate}),null,
 'Absent same-date EUR/USD fixing must never be imputed');
const forged=structuredClone(prices);
forged.source_url='https://not-ecb.example/eurfxref-hist.xml';
assert.equal(choose({...args,prices:forged}).length,0);
assert.equal(render({...args,prices:forged}),'',
 'A source-confused FX price archive must not produce an invented Home chart');

const eur5=inspectSessionWindow('EURUSD',args,5,eur.to);
assert(eur5&&eur5.from==='2026-11-05'&&eur5.to==='2026-11-12',
 'EURUSD 5 BCE sessions require two source-backed 6M endpoints');
assert.equal(inspectSessionWindow('EURUSD',args,20,eur.to),null,
 'No invented EURUSD 20-session reference when October endpoint is missing');
const aud20=inspectSessionWindow('AUDCAD',args,20,'2026-11-12');
assert(aud20&&aud20.from==='2026-10-15'&&aud20.to==='2026-11-12',
 'AUDCAD 20-session date range must use BCE fixing sessions');
for(const selectedPair of selected){
 for(const n of [5,20]){
  const win=inspectSessionWindow(selectedPair.pair,args,n,selectedPair.to);
  if(!win)continue;
  const dates=prices.rows.map(r=>r.Date).sort(),endIndex=dates.indexOf(win.to);
  assert.equal(win.from,dates[endIndex-n],'Use exactly N BCE dates');
  assert.equal(win.to,selectedPair.to,'All horizons end at the daily card date');
  assert.equal(win.sourceDates.money,win.sourceDates.spot,'Monetary and FX ends agree');
  assert(Number.isFinite(win.monetaryBp)&&Number.isFinite(win.fxPct));
 }
}
const missingHorizon=structuredClone(history);
missingHorizon.currencies.AUD.tenors['6m']=
 missingHorizon.currencies.AUD.tenors['6m'].filter(p=>p.date!==aud20.from);
assert.equal(inspectSessionWindow('AUDCAD',{...args,history:missingHorizon},20,'2026-11-12'),null,
 'Missing monetary start is never estimated');
const contractBreak=structuredClone(history);
contractBreak.currencies.USD.tenors['6m'].find(p=>p.date===eur5.from).contract='WRONG_CONTRACT';
assert.equal(inspectSessionWindow('EURUSD',{...args,history:contractBreak},5,eur5.to),null,
 'Do not compare different listed futures contracts');
const missingPriceHorizon=structuredClone(prices);
missingPriceHorizon.rows=missingPriceHorizon.rows.filter(p=>p.Date!==aud20.to);
assert.equal(inspectSessionWindow('AUDCAD',{...args,prices:missingPriceHorizon},20,aud20.to),null,
 'A missing BCE price endpoint is not interpolated');
assert.equal(inspectSessionWindow('AUDCAD',{...args,prices:forged},20,aud20.to),null,
 'Forged BCE price provenance must fail');
assert.equal(inspectSessionWindow('AUDCAD',args,20,'2026-11-17'),null,
 'Do not inspect dates after as-of');
assert(html.includes('Verifica anche 5 e 20 sedute'));
assert(html.includes('data-home-pricing-sessions="5"'));
assert(html.includes('data-home-pricing-sessions="20"'));
assert(html.includes('Non disponibile:'),'Unavailable must be explicit');


const coherent={pair:'EURUSD',base:'EUR',quote:'USD',monetaryBp:2,fxPct:.3,comparison:'SEGNI_COHERENTI'};
const divergent={...coherent,fxPct:-.3,comparison:'SEGNI_DIVERGENTI'};
const quiet={...coherent,monetaryBp:0.01,comparison:'MOVIMENTO_CONTENUTO'};
assert(horizonReading(coherent,[{comparison:'SEGNI_COHERENTI'},null])
 .includes('stessa coerenza di segno compare anche a 5 sedute'));
assert(horizonReading(divergent,[{comparison:'SEGNI_COHERENTI'},null])
 .includes('A 5 sedute tassi relativi e cambio hanno lo stesso segno'),
 'Cross-window change should not be described as persistence');
assert(horizonReading(quiet,[null,null]).includes('Non ci sono confronti verificabili'));
assert(horizonReading(coherent,[{comparison:'SEGNI_COHERENTI'},{comparison:'SEGNI_COHERENTI'}])
 .includes('anche sulle finestre a 5 e 20 sedute'));
assert(horizonReading(coherent,[{comparison:'SEGNI_DIVERGENTI'},{comparison:'SEGNI_COHERENTI'}])
 .includes('a 20 sedute tassi relativi e cambio hanno lo stesso segno'));
assert(html.includes('finestre sono sovrapposte'), 'Overlapping horizons require a nonindependence disclosure');
assert(html.includes('Nel confronto breve'), 'Home should render a synthetic-free readable FX conclusion');

const earlier=inspectPair('EURUSD',{...args,today:'2026-11-10'});
assert(!earlier||earlier.to<='2026-11-10',
 'Only the latest available prior observations may be used, never dates after the stated as-of');
assert.equal(inspectPair('NOTPAIR',args),null);
const early=render({...args,today:'2026-11-10'});
assert(!early.includes('data-home-pricing-to="2026-11-12"'),
 'Historical evidence must respect requested as-of, not look ahead');
const source=read(site+'app.js'),index=read(site+'index.html');
assert(index.indexOf('pair-monetary-bridge-v1.js?v=2')<
 index.indexOf('home-pricing-proof-v1.js?v=3')&&
 index.indexOf('home-pricing-proof-v1.js?v=3')<
 index.indexOf('app.js?v=18.58-home-money-pricing'),
 'Home module must load after monetary archive validators and before App');
assert(index.includes('home-pricing-proof-v1.css?v=2'));
assert(source.includes("window.FXQuantHomePricingProof?.render?.("));
assert(source.includes("if(hourly)return moneyProof?"));
assert(source.includes("post+moneyProof+'<section class=\"morning-prose\"'"));
assert(source.includes(' +moneyProof\n +\'<section class="dashboard-main dashboard-reading-chart">'),
 'Legacy fallback Home also needs the same source-first monetary comparison');
const css=read(site+'home-pricing-proof-v1.css');
assert(css.includes('.home-pricing-proof-multi-row'));
assert(css.includes('.home-pricing-proof-grid')&&css.includes('max-width:720px')&&css.includes(':focus-visible'));
console.log('NEXT_HOME_6M_FX_PROOF_PASS: date-aligned EURUSD, 28-pair source selection, nonUSD cross, inversion, no look-ahead, document links');
