'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'../..');
const read=p=>fs.readFileSync(path.join(root,p),'utf8');
const load=p=>JSON.parse(read(p));
const base='site/fx-quant-v2/next/';
const ctx={window:{}};
for(const p of ['pair-rankings.js','currency-data-fallback.js','g8-rates-shadow.js','currency-strength-reading.js','currency-studio.js'])
 vm.runInNewContext(read(base+p),ctx,{filename:p,timeout:5000});
const F=ctx.window.FXQuantCurrencyFallback,Strength=ctx.window.FXQuantCurrencyStrength;
const FX=['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'];
const prices=load('live_data/sections/ECB_G8_PRICE_HISTORY.json');
const macroSeries=load('live_data/sections/MACRO_SERIES.json');
const estimated=load('live_data/sections/CB_PRICING_ESTIMATED.json');
const macro=load('live_data/sections/MACRO_THERMOMETER_DATA.json');
const rates=load('live_data/sections/NATIVE_RATES_DATA.json');
const chfResearch=load('site/fx-quant-v2/chf-snb-paired-history.json');
const nzdResearch=load('site/fx-quant-v2/nzd-b2-postroll-web-research.json');
const chfSpot=load('live_data/sections/CHF_SNB_10Y_SPOT_CONTEXT.json');
const nzdDirectionalProxy=load('live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json');
const ois=load('site/fx-quant-v2/ois-pricing-snapshot.json');
const cot=load('live_data/sections/V250_COT_CHART_DATA.json');
const cb=load('live_data/sections/NATIVE_CB_DATA.json');
const pairs=load('live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json');
const now='2026-11-12';
const context=F.evaluate({macroSeries,estimated,rates,chfResearch,nzdResearch,now});
assert.equal(Object.keys(context.currencies).length,8);
for(const ccy of FX){
 const g=context.currencies[ccy].growth;
 assert.equal(g.status,'STORICO_DESCRITTIVO',ccy+' must surface an observed growth series');
 assert(g.label.includes('2026-'),'Growth display must show observation period: '+ccy);
 assert.equal(g.forecastValue,null,'No fabricated nowcast: '+ccy);
}
for(const ccy of ['USD','EUR','CHF']){
 const raw=estimated.currencies[ccy],quote=raw.horizons['6m'];
 const p=context.currencies[ccy].pricingProxy;
 // The live overlay refreshes per contract. If the 6M quote belongs to a
 // different day than as_of, the model correctly WITHHOLDS the proxy.
 // Never make CI demand an invented same-day snapshot.
 if(raw.as_of!==quote.quote_as_of){
  assert.equal(p.status,'NON_DISPONIBILE',ccy+' mismatched 6M snapshot must be withheld');
  assert.equal(p.asof,null);
 }
 if(p.status==='PROXY_INFORMATIVO'){
  assert.equal(raw.as_of,quote.quote_as_of,ccy+' quote date must match the snapshot');
  assert.equal(quote.quote_timestamp_verified,true);
  assert(p.label.includes('proxy'));
  assert(!p.label.startsWith('+')&&!p.label.startsWith('−'),'Rate levels do not show change sign');
  assert.match(p.description,/non fornisce un repricing settimanale verificato/);
 }else{
  assert.equal(p.status,'NON_DISPONIBILE',ccy+' must never fabricate a proxy');
 }
 // A deterministic, source-qualified and same-day fixture must still pass.
 // Its deliberately mismatched twin must fail: this tests the strict gate
 // independently of whichever live contract refreshed most recently.
 const fixture=structuredClone(estimated);
 fixture.currencies[ccy]={...raw,as_of:'2026-11-11',horizons:{...raw.horizons,
  '6m':{...quote,quote_as_of:'2026-11-11'}}};
 const matched=F.pricingProxy(fixture,ccy,now);
 assert.equal(matched.status,'PROXY_INFORMATIVO',ccy+' valid dated 6M fixture should be usable');
 assert.match(matched.description,/non fornisce un repricing settimanale verificato/);
 fixture.currencies[ccy].horizons['6m'].quote_as_of='2026-11-10';
 assert.equal(F.pricingProxy(fixture,ccy,now).status,'NON_DISPONIBILE',
  ccy+' mismatched fixture must be withheld');
}
assert.equal(context.currencies.NZD.pricingProxy.status,'NON_DISPONIBILE');
// CHF/NZD research is visible but never a valid live 2Y weekly confirmation.
assert.equal(context.currencies.CHF.ratesResearch.status,'STORICO_UFFICIALE_NON_OPERATIVO');
assert.equal(context.currencies.NZD.ratesResearch.status,'RICERCA_MANUALE_NON_CERTIFICATA');
assert.equal(context.currencies.CHF.ratesResearch.asof,'2026-10-30');
assert.equal(context.currencies.NZD.ratesResearch.asof,'2026-11-10');
assert.match(context.currencies.CHF.ratesResearch.description,/NON è un rendimento live/);
assert.match(context.currencies.NZD.ratesResearch.description,/manca la riconciliazione XLSX/);
assert.equal(context.currencies.USD.ratesResearch.status,'NON_DISPONIBILE');
const shadow=ctx.window.FXQuantG8RatesShadow.analyze({
 research:context,chfHistory:chfResearch,nzdResearch,spot:chfSpot,
 nzdMarket:nzdDirectionalProxy,now});
assert.equal(shadow.schema,'GMFQ_G8_RATES_SHADOW_V1');
assert.equal(shadow.currencies.CHF.status,'STIMA_MODELLO_RICERCA',JSON.stringify(shadow.currencies.CHF));
assert(shadow.currencies.CHF.estimate2Y>0.18&&shadow.currencies.CHF.estimate2Y<0.25);
assert(shadow.currencies.CHF.pseudoOOSCount>=10);
assert(shadow.currencies.CHF.modelMAEBp<shadow.currencies.CHF.flatBaselineMAEBp);
// A current ASX observation two trading days after the RBNZ anchor is NOT
// an admissible one-day pass-through. This is a valid absence, not a failing model.
const nzdLive=shadow.currencies.NZD;
assert(['NON_DISPONIBILE','STIMA_SCENARIO_NON_CALIBRATA'].includes(nzdLive.status));
if(nzdLive.status==='NON_DISPONIBILE'){
 assert.match(nzdLive.reason,/NZD: non c’è un movimento futures omogeneo del giorno successivo/);
 assert.equal(nzdLive.eligibleForCore,false);
 assert.equal(nzdLive.eligibleForBacktests,false);
}else{
 assert.equal(nzdLive.estimate2Y,3.80);
 assert.equal(nzdLive.lower2Y,3.77);
 assert.equal(nzdLive.upper2Y,3.83);
}
// Deterministic SAME-NEXT-DAY synthetic fixture keeps the sensitivity
// calculation covered, without turning any actual Nov 12 futures quote into
// a fictitious Nov 11 market observation.
const nzdNextDay=structuredClone(nzdDirectionalProxy);
nzdNextDay.as_of='2026-11-11';
nzdNextDay.source_url='https://www.asx.com.au/data/futures/reports/EODWebMarketSummary261111ZFT.htm';
const syntheticNZD=ctx.window.FXQuantG8RatesShadow.analyze({
 research:context,chfHistory:chfResearch,nzdResearch,spot:chfSpot,
 nzdMarket:nzdNextDay,now
}).currencies.NZD;
assert.equal(syntheticNZD.status,'STIMA_SCENARIO_NON_CALIBRATA',JSON.stringify(syntheticNZD));
const nzdAnchor=nzdResearch.daily_observations.at(-1)['2Y'];
assert.equal(syntheticNZD.estimate2Y,Math.round((nzdAnchor-0.015)*1000)/1000);
assert.equal(syntheticNZD.lower2Y,Math.round((nzdAnchor-0.03)*1000)/1000);
assert.equal(syntheticNZD.upper2Y,nzdAnchor);
assert.equal(shadow.currencies.CHF.eligibleForCore,false);
assert.equal(shadow.currencies.NZD.eligibleForCore,false);
const badSpot=structuredClone(chfSpot);badSpot.as_of='2026-11-13';
assert.equal(ctx.window.FXQuantG8RatesShadow.chf({research:context,chfHistory:chfResearch,spot:badSpot,now}).status,'NON_DISPONIBILE');
const badASX=structuredClone(nzdDirectionalProxy);badASX.as_of='2026-11-12';
assert.equal(ctx.window.FXQuantG8RatesShadow.nzd({research:context,nzdResearch,nzdMarket:badASX,now}).status,'NON_DISPONIBILE');
const badASXProvenance=structuredClone(nzdDirectionalProxy);badASXProvenance.governance.core_score_effect='ACTIVE';
assert.equal(ctx.window.FXQuantG8RatesShadow.nzd({research:context,nzdResearch,nzdMarket:badASXProvenance,now}).status,'NON_DISPONIBILE');
assert.equal(ctx.window.FXQuantG8RatesShadow.analyze({
 research:context,chfHistory:chfResearch,nzdResearch,spot:chfSpot,
 nzdMarket:nzdDirectionalProxy,now:'2026-12-10'}).currencies.CHF.status,'NON_DISPONIBILE');
const history=(ccy,chf=chfResearch,nzd=nzdResearch,gov=rates,asof=now)=>
 F.researchRatesAxis(ccy,chf,nzd,gov,asof);
const chfWrongSource=structuredClone(chfResearch);
chfWrongSource.source_url='https://example.com/fake';
assert.equal(history('CHF',chfWrongSource).status,'NON_DISPONIBILE');
const chfAnchor=structuredClone(chfResearch);
chfAnchor.observations[0]['2Y']+=.2;
assert.equal(history('CHF',chfAnchor).status,'NON_DISPONIBILE');
const chfFuture=structuredClone(chfResearch);
chfFuture.observations.at(-1).date='2026-11-13';
chfFuture.last_observation_date='2026-11-13';
assert.equal(history('CHF',chfFuture).status,'NON_DISPONIBILE');
assert.equal(history('CHF',chfResearch,nzdResearch,rates,'2026-12-20').status,'NON_DISPONIBILE');
const nzdWrong=structuredClone(nzdResearch);
nzdWrong.independent_xlsx_reconciled=true;
assert.equal(history('NZD',chfResearch,nzdWrong).status,'NON_DISPONIBILE');
const nzdRoll=structuredClone(nzdResearch);
nzdRoll.benchmark_2Y='May 2028';
assert.equal(history('NZD',chfResearch,nzdRoll).status,'NON_DISPONIBILE');
const nzdFuture=structuredClone(nzdResearch);
nzdFuture.daily_observations.at(-1).date='2026-11-13';
assert.equal(history('NZD',chfResearch,nzdFuture).status,'NON_DISPONIBILE');
assert.equal(history('NZD',chfResearch,nzdResearch,rates,'2026-11-09').status,'NON_DISPONIBILE');
assert.equal(history('NZD',chfResearch,nzdResearch,rates,'2026-11-25').status,'NON_DISPONIBILE');
const nzdUntrustedSource=structuredClone(nzdResearch);
nzdUntrustedSource.source_capture_method='AUTOMATED_UNAUTHORIZED_DOWNLOAD';
assert.equal(history('NZD',chfResearch,nzdUntrustedSource).status,'NON_DISPONIBILE');

const fake={...estimated,currencies:{...estimated.currencies,
 USD:{...estimated.currencies.USD,governance:{...estimated.currencies.USD.governance,pair_engine_effect:'ACTIVE'}}}};
assert.equal(F.pricingProxy(fake,'USD',now).status,'NON_DISPONIBILE','Any impact on pair engine forbids informational quote');
assert.equal(F.pricingProxy(estimated,'USD','2026-12-10').status,'NON_DISPONIBILE','Stale quote rejected');
assert.equal(F.pricingProxy(estimated,'USD','2026-11-09').status,'NON_DISPONIBILE','Future quote rejected');
const future={USD:[{id:'US_PCEC96_history_value',category:'Crescita',frequency:'M',label:'Fake future GDP',
 dates:['2026-12','2027-01'],values:[99,999]}]};
assert.equal(F.growthAxis(future,'USD',now).status,'NON_DISPONIBILE','Future macro observations excluded');
const baseArgs={prices,macro:macro.currencies,rates,ois:ois.currencies,cot,now,
 rankingFn:ctx.window.FXQuantPairRankings.currencyRanking};
const original=Strength.analyze(baseArgs);
const enriched=Strength.analyze({...baseArgs,fallback:context});
assert.deepEqual(enriched.rows.map(x=>x.ccy),original.rows.map(x=>x.ccy),'Price order unchanged');
assert.deepEqual(enriched.rows.map(x=>x.evidenceCount),original.rows.map(x=>x.evidenceCount),
 'Proxy cannot certify official evidence');
assert.deepEqual(enriched.rows.map(x=>x.pricing.ok),original.rows.map(x=>x.pricing.ok),
 'Proxy cannot promote 6M OIS/futures weekly repricing');
const data={currencyPrices:prices,macroSeries,cbEstimated:estimated,macro,rates,ois,cotHistory:cot,cb,pairs,chfResearch,nzdPostroll:nzdResearch,chfSpot,nzdDirectionalProxy};
const esc=x=>String(x??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const fmt=(x,n=2)=>finite(x)?x.toFixed(n):'—';
const sign=(x,n=2,suffix='')=>finite(x)?(x>0?'+':x<0?'−':'')+fmt(Math.abs(x),n)+suffix:'—';
const flags=Object.fromEntries(FX.map(k=>[k,k]));
const html=ctx.window.FXQuantCurrencies.render({
 get:k=>data[k],FX,FLAGS:flags,NAMES:flags,pageHero:()=>'<header>G8</header>',
 esc,fmt,sign,date:x=>x||'n.d.',finite,validDay:x=>/^\d{4}-\d\d-\d\d$/.test(x||''),dayNow:()=>now,
 state:{ccy:'USD',csOther:'EUR',csReturnWindow:20}
});
assert(html.includes('Consumi reali'), 'Observed growth reaches G8 UI');
const makeHtml=ccy=>ctx.window.FXQuantCurrencies.render({
 get:k=>data[k],FX,FLAGS:flags,NAMES:flags,pageHero:()=>'<header>G8</header>',
 esc,fmt,sign,date:x=>x||'n.d.',finite,validDay:x=>/^\d{4}-\d\d-\d\d$/.test(x||''),dayNow:()=>now,
 state:{ccy,csOther:ccy==='CHF'?'EUR':'USD',csReturnWindow:20}
});
const chfHtml=makeHtml('CHF'),nzdHtml=makeHtml('NZD');
assert(chfHtml.includes('0.210% · STIMA')||chfHtml.includes('0,210% · STIMA'), 'CHF shadow estimate in G8 board');
if(nzdLive.status==='STIMA_SCENARIO_NON_CALIBRATA')
 assert(nzdHtml.includes('3.800% · STIMA')||nzdHtml.includes('3,800% · STIMA'), 'NZD explicit scenario in G8 board');
else
 assert(!nzdHtml.includes('3.800% · STIMA')&&!nzdHtml.includes('3,800% · STIMA'),
  'Expired NZD sensitivity must not remain on the G8 board');
assert(chfHtml.includes('2Y · stima (non quotazione)'));
if(nzdLive.status==='STIMA_SCENARIO_NON_CALIBRATA')
 assert(nzdHtml.includes('2Y · stima (non quotazione)'));
assert(chfHtml.includes('NON è un rendimento live'));
assert(nzdHtml.includes('manca la riconciliazione XLSX'));
assert(chfHtml.includes('intervallo di sensibilità/errore indicativo'), 'Uncertainty shown for CHF');
if(nzdLive.status==='STIMA_SCENARIO_NON_CALIBRATA')
 assert(nzdHtml.includes('SCENARIO')||nzdHtml.includes('Scenario'), 'NZD uncalibrated sensitivity must be labelled');
assert(!chfHtml.includes('0,238% · +'), 'CHF 2Y level is not rate change');
assert(html.includes('proxy'), 'Indicative quote reaches G8 UI');
assert(html.includes('4,50%')||html.includes('4.50%'), 'Indicative USD 6M quote is dated and displayed');
assert(!/\bNaN\b|\bundefined\b|\[object Object\]/.test(html));
const idx=read(base+'index.html');
const app=read(base+'app.js');
assert(idx.includes('currency-data-fallback.js?v=2'));
assert(idx.indexOf('currency-data-fallback.js')<idx.indexOf('currency-studio.js'));
assert(idx.includes('g8-rates-shadow.js?v=1'));
assert(idx.indexOf('g8-rates-shadow.js')<idx.indexOf('currency-studio.js'));
assert(idx.includes('currency-studio.js?v=13')&&idx.includes('app.js?v=18.43'));
assert(app.includes("cbEstimated:'../../../live_data/sections/CB_PRICING_ESTIMATED.json'"));
assert(app.includes("chfSpot:'../../../live_data/sections/CHF_SNB_10Y_SPOT_CONTEXT.json'"));
assert(app.includes("nzdDirectionalProxy:'../../../live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json'"));
console.log('G8_DATA_FALLBACK_V1_PASS: observed growth, indicative 6M proxy, no official promotion, stale/future guard, unchanged rankings');
