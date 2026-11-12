'use strict';
/* A bilateral FX research sentence must identify whether a stronger estimated
 * macro ranking comes from genuine favorable scores or only LESS WEAKNESS.
 * No price look-ahead, OIS fiction, or change to the underlying ranking. */
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'../..'),next='site/fx-quant-v2/next/';
const json=p=>JSON.parse(fs.readFileSync(path.join(root,p),'utf8'));
const raw=p=>fs.readFileSync(path.join(root,p),'utf8');
const ranking=require(path.join(root,next,'pair-rankings.js'));
const engine=require(path.join(root,next,'macro-strength-estimated-v1.js'));
const rate=(quality='UFFICIALE')=>({quality,kind:quality==='PROXY'?'GOV_2Y_PROXY':'FUTURES'});
const estimate={
 status:'STIMA_OPERATIVA_NON_VALIDATA',
 by:{AUD:{macroScore:-.35,rate:rate()},CAD:{macroScore:-.15,rate:rate()},
  GBP:{macroScore:.55,rate:rate()},JPY:{macroScore:.30,rate:rate()},
  EUR:{macroScore:-.6,rate:rate()},USD:{macroScore:.65,rate:rate()},
  CHF:{macroScore:.2,rate:rate()},NZD:{macroScore:-.35,rate:rate()}}
};
const pair=(key,favored,macroState='FAVOREVOLE',policyState='FAVOREVOLE',extra={})=>({
 key,base:key.slice(0,3),quote:key.slice(3),favored,macroState,policyState,
 source:'STIMA_ESPLICITA_V1',fiveState:'COERENTE',aligned:true,opposite:false,...extra
});
const read=(p,e=estimate)=>ranking.pairDriverReading(p,e);
const lessWeak=read(pair('AUDCAD','CAD'));
assert.match(lessWeak,/Entrambi i punteggi macro stimati sono deboli/);
assert.match(lessWeak,/CAD è meno debole di AUD, non necessariamente forte/);
assert.doesNotMatch(lessWeak,/forza assoluta di CAD|AUD è meno debole/);
const bothPositive=read(pair('GBPJPY','GBP'));
assert.match(bothPositive,/Entrambi i punteggi macro stimati sono favorevoli/);
assert.match(bothPositive,/GBP prevale solo relativamente su JPY/);
const contrasting=read(pair('EURUSD','USD'));
assert.match(contrasting,/USD con punteggio favorevole e EUR con punteggio debole/);
const weakness=read(pair('CADNZD','CAD'),{
 ...estimate,by:{...estimate.by,CAD:{macroScore:0,rate:rate()},NZD:{macroScore:-.35,rate:rate()}}
});
assert.match(weakness,/soprattutto dal punteggio debole di NZD/);
assert.match(weakness,/non da una forza marcata di CAD/);
const against=read(pair('EURUSD','USD','CONTRARIA','FAVOREVOLE'));
assert.match(against,/La macro stimata favorisce EUR, non USD/);
const ratesProxy=structuredClone(estimate);ratesProxy.by.EUR.rate.quality='PROXY';
assert.match(read(pair('EURUSD','USD'),ratesProxy),/2Y governativo non è una conferma OIS/);
const noRates=structuredClone(estimate);noRates.by.EUR.rate.quality='ASSENTE';
assert.match(read(pair('EURUSD','USD','FAVOREVOLE','ASSENTE'),noRates),
 /manca una variazione settimanale utilizzabile/);
assert.doesNotMatch(read(pair('EURUSD','USD','FAVOREVOLE','ASSENTE'),noRates),
 /riferimenti monetari sostengono/);
const contraryRates=read(pair('EURUSD','USD','FAVOREVOLE','CONTRARIA'));
assert.match(contraryRates,/riferimenti monetari indicano EUR in senso contrario/);
const mixed5=read(pair('EURUSD','USD','FAVOREVOLE','FAVOREVOLE',
 {aligned:true,opposite:false,fiveState:'CONTRARIO'}));
assert.match(mixed5,/20 fixing BCE coerenti, ultimi 5 contrari/);
assert.match(mixed5,/timing da verificare/);
const recovery=read(pair('EURUSD','USD','FAVOREVOLE','FAVOREVOLE',
 {aligned:false,opposite:true,fiveState:'COERENTE'}));
assert.match(recovery,/20 fixing BCE contrari, ultimi 5 coerenti/);
assert.match(recovery,/non inversione dimostrata/);
const noEdge=read(pair('EURUSD',null,'NON DISTINTA','NON DISTINTA'));
assert.match(noEdge,/non assegna una direzione fondamentale/);
assert(!noEdge.includes('LONG')&&!noEdge.includes('SHORT'));
assert.equal(read(null),null);
assert.equal(read(pair('EURUSD','USD'),{...estimate,status:'STIMA_SOSPESA'}),null);
assert.equal(read({...pair('EURUSD','USD'),source:'LEGACY_D'}),null);
assert.equal(read({...pair('EURUSD','USD'),base:'GBP'}),null);
const bad=structuredClone(estimate);delete bad.by.EUR.rate;
assert.equal(read(pair('EURUSD','USD'),bad),null);
// Live 28 pairs must be explained, not re-ranked or silently sourced from
// the archived September D macro model.
const observed=json('site/control-room-preview/macro-v3-current-evidence.json');
const live=engine.evaluate({
 observed,prices:json('live_data/sections/ECB_G8_PRICE_HISTORY.json'),
 ois:json('site/fx-quant-v2/ois-pricing-snapshot.json'),
 rates:json('live_data/sections/NATIVE_RATES_DATA.json'),
 model:json('live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json'),
 now:observed.generated_europe_rome_day,rankingFn:ranking.currencyRanking
});
assert.equal(live.status,'STIMA_OPERATIVA_NON_VALIDATA',live.reason);
assert.equal(live.pairs.length,28);
for(const p of live.pairs){
 const narrative=read(p,live);
 assert.equal(typeof narrative,'string',p.key+' must have an independent bilateral reading');
 assert(narrative.length>80&&narrative.length<650,p.key+' story is too generic or excessively long');
 assert(!/\\bNaN\\b|\\bundefined\\b|rendimento atteso|entrata long|entrata short/i.test(narrative),
  p.key+' story cannot be a signal or fabricated probability');
 assert(p.favored===p.base||p.favored===p.quote||
  narrative.includes('non assegna una direzione fondamentale'));
}
const app=raw(next+'app.js'),index=raw(next+'index.html');
assert(app.includes('pairDriverReading?.(activePair,estimate)'), 'Selected first read must consume the current bilateral view');
assert(app.includes('const headline=driverReading||activePair?.thesisReason'), 'Missing estimates must fail closed');
assert(index.includes('pair-rankings.js?v=8'));
assert(index.includes('app.js?v=18.43-drivers1'));
console.log('NEXT_PAIR_RELATIVE_DRIVERS_V1_PASS: 28 FX pairs; stronger-versus-less-weak macro, monetary proxies and 5/20 price divergences; no ranking changes');
