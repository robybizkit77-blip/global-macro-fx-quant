'use strict';
/* Operational estimated Macro Strength V1 must NEVER copy legacy 2026-09-25
 * directional votes or silently claim statistically validated trade signals. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ROOT=path.resolve(__dirname,'../..');
const read=p=>JSON.parse(fs.readFileSync(path.join(ROOT,p),'utf8'));
const next='site/fx-quant-v2/next/';
const modulePath=path.join(ROOT,next,'macro-strength-estimated-v1.js');
const engine=require(modulePath),rank=require(path.join(ROOT,next,'pair-rankings.js'));
const doc=read('site/control-room-preview/macro-v3-current-evidence.json');
const prices=read('live_data/sections/ECB_G8_PRICE_HISTORY.json');
const ois=read('site/fx-quant-v2/ois-pricing-snapshot.json');
const rates=read('live_data/sections/NATIVE_RATES_DATA.json');
const model=read('live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json');
const FX=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
const now=doc.generated_europe_rome_day;
const run=(options={})=>engine.evaluate({
 observed:doc,prices,ois,rates,model,now,rankingFn:rank.currencyRanking,...options
});
const result=run();
assert.equal(result.status,'STIMA_OPERATIVA_NON_VALIDATA',result.reason);
assert.equal(result.schema,'GMFQ_MACRO_STRENGTH_ESTIMATED_V1');
assert.equal(result.asof,doc.generated_europe_rome_day);
assert.equal(result.legacyMacroAsOf,'2026-09-25');
assert.equal(result.priceAsOf,prices.last_as_of);
assert.deepEqual(result.coverage.currencies,8);
assert.deepEqual(result.coverage.pairs,28);
// The separately published Macro feed can still serve its previous snapshot in PR CI.
const gbpGrowth=doc.countries.GBP.growth;
const jpyGrowth=doc.countries.JPY.growth;
const chfGrowth=doc.countries.CHF.growth;
assert.equal(result.coverage.withGDPAcceleration,FX.filter(ccy=>{
 const g=doc.countries[ccy].growth,p=g.prior_documented_quarter;
 const qnum=s=>Number(s.slice(0,4))*4+Number(s.slice(-1));
 return p&&/^\d{4}Q[1-4]$/.test(p.reference_quarter)&&
  qnum(g.reference_quarter)-qnum(p.reference_quarter)===1&&
  /^\d{4}-\d{2}-\d{2}$/.test(p.publisher_release_day)&&p.publisher_release_day<=now&&
  Number.isFinite(p.nonannualized_qoq_descriptive_pct)&&
  g.later_revisions_not_identical_to_first_release===true;
 }).length);
if(gbpGrowth.reference_quarter==='2026Q3'&&gbpGrowth.prior_documented_quarter)
 assert.equal(result.by.GBP.growthTrend,1);
if(jpyGrowth.reference_quarter==='2026Q3'&&jpyGrowth.prior_documented_quarter)
 assert.equal(result.by.JPY.growthTrend,-1);
if(chfGrowth.reference_quarter==='2026Q3'&&chfGrowth.prior_documented_quarter)
 assert.equal(result.by.CHF.growthTrend,-1);
assert.equal(result.coverage.official6M,4,'Do not promote USD/EUR/CHF indicative or NZD proxy to OIS');
assert.deepEqual(result.method,{economic:0.5,policy:0.3,price:0.2,
 gdpAcceleration:0.45,gdpLevel:0.2,labour:0.35,
 fixedHeuristic:true,validatedOutOfSample:false,entrySignals:false});
assert.equal(new Set(result.currencies.map(x=>x.ccy)).size,8);
assert.equal(new Set(result.pairs.map(x=>x.key)).size,28);
assert.deepEqual(new Set(result.pairs.map(x=>x.key)),new Set(Object.keys(model.pairs)));
assert(result.currencies.every((x,i)=>x.rank===i+1&&Number.isFinite(x.score)&&
 Math.abs(x.score)<=1&&x.priceRank>0));
assert(result.pairs.every(x=>x.source==='STIMA_ESPLICITA_V1'&&
 x.valid===false&&Number.isFinite(x.scoreGap)&&
 ['STIMA PARZIALE','STIMA COMPLETA'].includes(x.quality)));
assert(result.pairs.every(x=>x.favored===null||
 [x.base,x.quote].includes(x.favored)));
assert(result.currencies.some(x=>x.rate.quality==='ASSENTE'),
 'A withheld rate must stay missing, never silently imputed');
assert.equal(result.by.USD.growthTrend,1);
assert.equal(result.by.EUR.growthTrend,-1);
assert(result.by.USD.macroScore>result.by.EUR.macroScore);
assert.equal(result.by.CHF.rate.quality,'ASSENTE');
assert.equal(result.by.NZD.rate.quality,'PROXY');
assert.equal(result.by.NZD.rate.kind,'BANK_BILL_6M_DIRECTIONAL_PROXY');
const nzdProxy=ois.currencies.NZD.horizons['6m'];
assert.equal(result.by.NZD.rate.changeBp,nzdProxy.change_1w_bp);
assert.equal(result.by.NZD.rate.asof,nzdProxy.as_of);
assert.equal(result.by.NZD.rate.score,
 nzdProxy.change_1w_bp>=5?0.35:nzdProxy.change_1w_bp<=-5?-0.35:0,
 'The 6M bank-bill weekly move is used directionally at discounted weight, never as a policy/OIS estimate');
assert.equal(result.by.NZD.rate.quality==='UFFICIALE',false,'Bank-bill proxy must never count as official OIS');
const missingNZProxy=structuredClone(ois);
missingNZProxy.currencies.NZD.horizons['6m'].change_1w_bp=null;
const fallbackNZD=run({ois:missingNZProxy}).by.NZD.rate;
assert.notEqual(fallbackNZD.kind,'BANK_BILL_6M_DIRECTIONAL_PROXY');
assert(['ASSENTE','PROXY'].includes(fallbackNZD.quality));
if(fallbackNZD.quality==='PROXY')assert.equal(fallbackNZD.kind,'GOV_2Y_PROXY');
assert.equal(run({ois:missingNZProxy,rates:{...rates,NZD:{...rates.NZD,weekly2_validation:null}}}).by.NZD.rate.quality,'ASSENTE');
assert.equal(result.by.USD.rate.kind,'GOV_2Y_PROXY');
assert.equal(result.by.GBP.rate.kind,'OIS');
assert.equal(result.by.JPY.rate.kind,'FUTURES');
assert(result.warning.includes('non backtest'));
const journeyModule=require(path.join(ROOT,next,'decision-journey.js'));
for(const key of ['EURUSD','AUDCAD','GBPJPY']){
 const updated=journeyModule.profile(key,model,prices,now,result);
 const frozen=journeyModule.profile(key,model,prices,now);
 const estimatedPair=result.pairs.find(x=>x.key===key);
 assert.equal(updated.source,'STIMA_ESPLICITA_V1',key+' current price thesis is estimated');
 assert.equal(updated.asof,result.priceAsOf,key+' uses the latest fixing, not legacy model price');
 assert.equal(updated.fav,estimatedPair.favored,key+' follows estimated relative preference');
 assert.equal(updated.quality,estimatedPair.quality,key+' displays estimated source quality');
 assert(updated.closes.length>=22,key+' retains actual ECB daily series');
 assert.equal(updated.research,false,key+' daily price is not a validated trade');
 assert.equal(frozen.source,'STORICO_D',key+' archived model remains auditable');
}

const frozen=structuredClone(model);
for(const item of Object.values(frozen.pairs)) {
 item.setup.structuralFav='XYZ';
 item.decision_frame.fav='XYZ';
}
const changed=run({model:frozen});
assert.equal(changed.status,result.status);
assert.deepEqual(changed.currencies,result.currencies);
assert.deepEqual(changed.pairs,result.pairs,
 'Legacy structural D votes must not influence ranking or current estimated bias');
function plusDays(iso,delta){
 return new Date(Date.parse(iso+'T12:00:00Z')+delta*864e5).toISOString().slice(0,10);
}
assert.equal(run({now:plusDays(now,8)}).status,'STIMA_SOSPESA','Seven day age gate');
assert.equal(run({now:plusDays(now,-1)}).status,'STIMA_SOSPESA','Future source gate');
const fake=structuredClone(doc);fake.safe_to_recompute_structural_pair_theses=true;
assert.equal(run({observed:fake}).status,'STIMA_SOSPESA','Reject fake certified core flags');
const missing=structuredClone(doc);missing.countries.NZD.inflation=null;
assert.equal(run({observed:missing}).status,'STIMA_SOSPESA','Missing G8 pillars fail closed');
// Exact strict GDP acceleration thresholds: binary representation must
// not turn 0.4 - 0.3 into a material acceleration (or its mirror).
const boundary=structuredClone(doc.countries.AUD);
for(const [current,prior,expected] of [[.4,.3,0],[.3,.4,0],[.400001,.3,1],[.299999,.4,-1],[.399999,.3,0]]){
 boundary.growth.nonannualized_qoq_descriptive_pct=current;
 boundary.growth.prior_documented_quarter.nonannualized_qoq_descriptive_pct=prior;
 assert.equal(engine.inputCountry(boundary,now).gTrend,expected);
}
boundary.labour.change_over_three_observation_intervals_pp=.3-.2;
assert.equal(engine.inputCountry(boundary,now).labour,-1);
boundary.labour.change_over_three_observation_intervals_pp=.2-.3;
assert.equal(engine.inputCountry(boundary,now).labour,1);
const futureGDP=structuredClone(doc);futureGDP.countries.USD.growth.publisher_release_day='2099-11-12';
assert.equal(run({observed:futureGDP}).status,'STIMA_SOSPESA','No future GDP');
const oldPrice=structuredClone(prices);oldPrice.last_as_of='2026-09-25';
assert.equal(run({prices:oldPrice}).status,'STIMA_SOSPESA','FX/observed as-of mismatch');
const badKeys=structuredClone(model);delete badKeys.pairs.EURUSD;
assert.equal(run({model:badKeys}).status,'STIMA_SOSPESA','No partial 27/28 sample');
const index=fs.readFileSync(path.join(ROOT,next,'index.html'),'utf8');
const app=fs.readFileSync(path.join(ROOT,next,'app.js'),'utf8');
const pair=fs.readFileSync(path.join(ROOT,next,'pair-rankings.js'),'utf8');
const currency=fs.readFileSync(path.join(ROOT,next,'currency-studio.js'),'utf8');
const narrative=fs.readFileSync(path.join(ROOT,next,'pair-desk-narrative.js'),'utf8');
const journey=fs.readFileSync(path.join(ROOT,next,'decision-journey.js'),'utf8');
assert(/macro-strength-estimated-v1\.js\?v=[5-9]\d*/.test(index));
assert(index.indexOf('pair-rankings.js')<index.indexOf('macro-strength-estimated-v1.js'));
assert(index.indexOf('macro-strength-estimated-v1.js')<index.indexOf('app.js'));
assert(app.includes("get('estimatedMacro')")&&app.includes('function estimatedMacro()'));
assert(pair.includes("get('estimatedMacro')")&&
 pair.includes('Il vecchio modello del 25 settembre rimane archivio'));
assert(currency.includes("get('estimatedMacro')"));
assert(journey.includes("estimatedMacro:get('estimatedMacro')"));
assert(narrative.includes("estimatedMacro?.status==='STIMA_OPERATIVA_NON_VALIDATA'"));
console.log('MACRO_STRENGTH_ESTIMATED_V1_PASS: 8 G8 + 28 canonical pairs, dates, partial sources, legacy independence, future/stale gates and website wiring');
