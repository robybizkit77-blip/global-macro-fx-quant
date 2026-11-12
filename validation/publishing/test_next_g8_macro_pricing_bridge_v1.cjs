'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'../..'),base='site/fx-quant-v2/next/';
const read=p=>fs.readFileSync(path.join(root,p),'utf8');
const load=p=>JSON.parse(read(p));
const ctx={window:{}};
for(const name of ['pair-rankings.js','currency-data-fallback.js',
 'g8-growth-shadow.js','g8-macro-gap-scenarios.js',
 'g8-inflation-labour-shadow.js','g8-rates-shadow.js',
 'currency-strength-reading.js','g8-macro-pricing-bridge.js',
 'currency-studio.js'])
 vm.runInNewContext(read(base+name),ctx,{filename:name,timeout:5000});
const W=ctx.window,F=W.FXQuantG8Transmission,R=W.FXQuantPairRankings,
 S=W.FXQuantCurrencyStrength,C=W.FXQuantCurrencies;
const FX=['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'],now='2026-11-12';
const data={
 macroSeries:load('live_data/sections/MACRO_SERIES.json'),
 currencyPrices:load('live_data/sections/ECB_G8_PRICE_HISTORY.json'),
 rates:load('live_data/sections/NATIVE_RATES_DATA.json'),
 macro:load('live_data/sections/MACRO_THERMOMETER_DATA.json'),
 cb:load('live_data/sections/NATIVE_CB_DATA.json'),
 cbEstimated:load('live_data/sections/CB_PRICING_ESTIMATED.json'),
 ois:load('site/fx-quant-v2/ois-pricing-snapshot.json'),
 cotHistory:load('live_data/sections/V250_COT_CHART_DATA.json'),
 pairs:load('live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json'),
 chfResearch:load('site/fx-quant-v2/chf-snb-paired-history.json'),
 nzdPostroll:load('site/fx-quant-v2/nzd-b2-postroll-web-research.json'),
 chfSpot:load('live_data/sections/CHF_SNB_10Y_SPOT_CONTEXT.json'),
 nzdDirectionalProxy:load('live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json')
};
const original=S.analyze({prices:data.currencyPrices,
 macro:data.macro.currencies,rates:data.rates,ois:data.ois.currencies,
 cot:data.cotHistory,now,rankingFn:R.currencyRanking});
const growth=W.FXQuantG8MacroGap.analyze({macroSeries:data.macroSeries,now});
const labour=W.FXQuantInflationLabourShadow.analyze({macroSeries:data.macroSeries,now});
const d=F.analyze({rows:original.rows,ois:data.ois.currencies,
 growth:growth.currencies,labour:labour.currencies,now});
assert.equal(d.schema,'GMFQ_G8_TRANSMISSION_V1');
assert.equal(d.status,'INTERPRETATION_ONLY');
assert.equal(Object.keys(d.currencies).length,8);
for(const ccy of FX){
 const x=d.currencies[ccy];
 assert(x.macro.observed.includes('Inflazione'));
 assert(x.macro.observed.includes('disoccupazione'));
 assert(x.headline.length>25);
 assert(x.comparison.text.length>30);
 assert(x.watch.includes('consenso')&&x.watch.includes('sorprese'));
 assert.equal(x.governance.influencesRanking,false);
 assert.equal(x.governance.influencesPairEngine,false);
 assert.equal(x.governance.officialPolicyProbability,false);
 assert.equal(x.governance.causalityClaim,false);
 assert.equal(x.governance.needsEventAlignedStudy,true);
 assert(x.price.text.includes('20 fixing BCE')||x.price.state==='NON_DISPONIBILE');
}
for(const ccy of ['GBP','JPY','CAD','AUD']){
 const x=d.currencies[ccy];
 assert.equal(x.market.tier,'VERIFICATO',ccy);
 assert(Number.isFinite(x.market.bp),ccy);
 assert.equal(x.market.asof,data.ois.currencies[ccy].as_of);
}
for(const ccy of ['USD','EUR','CHF']){
 const x=d.currencies[ccy];
 assert.equal(x.market.tier,'NON_VERIFICATO',ccy);
 assert.equal(x.market.bp,null,ccy);
 assert.match(x.comparison.text,/Senza una variazione 6M verificata/);
 assert(!x.headline.includes('pb settimanali'),ccy+' secondary level is not repricing');
}
assert.equal(d.currencies.NZD.market.tier,'PROXY');
assert.equal(d.currencies.NZD.market.bp,3);
assert.match(d.currencies.NZD.market.text,/NON misura un OIS RBNZ/);
assert.equal(d.currencies.NZD.market.asof,data.ois.currencies.NZD.as_of,'Live NZD pricing proxy must use its actual dated source, not a hard-coded prior session');
assert.equal(d.currencies.GBP.macro.pressure,'RESTRITTIVA_CONDIZIONALE');
assert.equal(d.currencies.JPY.macro.pressure,'RESTRITTIVA_CONDIZIONALE');
// This is a LIVE weekly change, not an eternally falling 6M reference.
// At exactly -2 bp the model deliberately classifies the move as limited.
const jpyBp=data.ois.currencies.JPY.horizons['6m'].change_1w_bp;
const jpySide=jpyBp>2?'SALE':jpyBp< -2?'SCENDE':'POCO_VARIATO';
assert.equal(d.currencies.JPY.market.bp,jpyBp);
assert.equal(d.currencies.JPY.market.side,jpySide);
assert.equal(d.currencies.JPY.comparison.state,
 jpySide==='SCENDE'?'DIVERGENZA_DA_STUDIARE':
 jpySide==='SALE'?'SEGNI_COMPATIBILI':'POCO_MOVIMENTO');
// Preserve an independent negative-shock scenario even if today's move is flat.
const jpyShockRow=structuredClone(original.rows.find(x=>x.ccy==='JPY'));
const jpyShockOis=structuredClone(data.ois.currencies.JPY);
jpyShockRow.pricing.change=-3;
jpyShockOis.horizons['6m'].change_1w_bp=-3;
const jpyShock=F.one({row:jpyShockRow,ois:jpyShockOis,
 growth:growth.currencies.JPY,labour:labour.currencies.JPY,now});
assert.equal(jpyShock.market.side,'SCENDE');
assert.equal(jpyShock.comparison.state,'DIVERGENZA_DA_STUDIARE');
assert.equal(d.currencies.GBP.comparison.state,'SEGNI_COMPATIBILI');
assert.equal(d.currencies.CAD.macro.pressure,'TENSIONE_CRESCITA_PREZZI');
assert.equal(d.currencies.CAD.comparison.state,'NON_UNIVOCO');
assert(d.currencies.CHF.scenarioNotes.some(x=>x.includes('Scenario disoccupazione')));
assert(d.currencies.USD.scenarioNotes.some(x=>x.includes('Scenario')));
assert(d.currencies.CAD.scenarioNotes.some(x=>x.includes('Scenario')));
assert(!d.currencies.EUR.scenarioNotes.some(x=>x.includes('Scenario')),
 'Unqualified macro extrapolation never becomes a transmission fact');
// Spoofed official OIS source can never promote secondary pricing.
const fake=structuredClone(data.ois.currencies.USD);
fake.quality='FONTE UFFICIALE';
fake.kind='OIS';
fake.horizons['6m'].change_1w_bp=33;
assert.equal(F.pricing(original.rows.find(x=>x.ccy==='USD'),fake,now).tier,'NON_VERIFICATO');
// NZD proxy's basis, identity, freshness and tolerance must fail closed.
const fakeNZD=structuredClone(data.ois.currencies.NZD);
fakeNZD.source='Untrusted identical labels';
assert.equal(F.pricing(original.rows.find(x=>x.ccy==='NZD'),fakeNZD,now).tier,'NON_VERIFICATO');
const staleNZD=structuredClone(data.ois.currencies.NZD);
staleNZD.as_of='2026-10-10';staleNZD.horizons['6m'].as_of='2026-10-10';
assert.equal(F.pricing(original.rows.find(x=>x.ccy==='NZD'),staleNZD,now).tier,'NON_VERIFICATO');
const futureNZD=structuredClone(data.ois.currencies.NZD);
futureNZD.as_of='2026-11-13';futureNZD.horizons['6m'].as_of='2026-11-13';
assert.equal(F.pricing(original.rows.find(x=>x.ccy==='NZD'),futureNZD,now).tier,'NON_VERIFICATO');
const macroSpoof=structuredClone(original.rows.find(x=>x.ccy==='GBP'));
macroSpoof.macro.inflationPeriod='2027-01';
assert.equal(F.macro(macroSpoof,now).pressure,'PARZIALE');
const badGrowth=structuredClone(growth.currencies.CAD);
badGrowth.pseudoOOSQualified=false;
assert.equal(F.one({row:original.rows.find(x=>x.ccy==='CAD'),
 ois:data.ois.currencies.CAD,growth:badGrowth,
 labour:labour.currencies.CAD,now}).scenarioNotes.length,0);
// The G8 country selection and all numerical ranking evidence remain identical.
const fmt=(x,n=2)=>typeof x==='number'&&Number.isFinite(x)?
 x.toLocaleString('it-IT',{minimumFractionDigits:n,maximumFractionDigits:n}):'—';
const sign=(x,n=2,suf='')=>typeof x==='number'&&Number.isFinite(x)?
 (x>0?'+':x<0?'−':'')+fmt(Math.abs(x),n)+suf:'—';
const esc=x=>String(x??'').replace(/&/g,'&amp;').replace(/</g,'&lt;')
 .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const flags=Object.fromEntries(FX.map(c=>[c,c]));
const params={get:k=>data[k],FX,FLAGS:flags,NAMES:flags,
 pageHero:()=>'<header>G8</header>',esc,fmt,sign,date:x=>x,
 finite:x=>typeof x==='number'&&Number.isFinite(x),
 validDay:x=>/^\d{4}-\d\d-\d\d$/.test(x||''),dayNow:()=>now};
for(const c of FX){
 const html=C.render({...params,state:{ccy:c,csOther:c==='EUR'?'USD':'EUR',csReturnWindow:20}});
 assert(html.includes(d.currencies[c].macro.title),c+' per-country interpretation shown');
 assert(html.includes('Da monitorare:'),c+' event-and-rates invalidation shown');
 assert(html.includes('20 fixing BCE'),c+' FX evidence described');
 assert(html.includes('consenso'),c+' no consensus/surprise inferred');
 assert.equal((html.match(/class="strength-row /g)||[]).length,8,c+' no missing board');
 assert(!/\bNaN\b|\bundefined\b|\[object Object\]/.test(html),c+' no broken HTML');
}
const after=S.analyze({prices:data.currencyPrices,
 macro:data.macro.currencies,rates:data.rates,ois:data.ois.currencies,
 cot:data.cotHistory,now,rankingFn:R.currencyRanking});
assert.deepEqual(after.rows.map(x=>x.ccy),original.rows.map(x=>x.ccy),
 'Price-only rank unaffected');
assert.deepEqual(after.rows.map(x=>x.evidenceCount),original.rows.map(x=>x.evidenceCount),
 'Shadow estimates do not increase official evidence');
const index=read(base+'index.html');
assert(index.includes('g8-macro-pricing-bridge.js?v=1'));
assert(index.indexOf('g8-macro-pricing-bridge.js')<index.indexOf('currency-studio.js'));
assert(index.includes('currency-studio.js?v=14'));
console.log('G8_MACRO_PRICING_BRIDGE_V1_PASS: 8 narratives, official vs NZD proxy vs withheld, divergent JPY, aligned GBP, no FX rank promotion');
