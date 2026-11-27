'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const load=p=>JSON.parse(fs.readFileSync(path.join(root,p),'utf8'));
const {read}=require(path.join(root,'site/fx-quant-v2/next/rates-economic-reading.js'));
const gov=load('live_data/sections/NATIVE_RATES_DATA.json');
const money=load('site/fx-quant-v2/ois-pricing-snapshot.json').currencies;
const today='2026-11-10';
const names=['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'];
for(const c of names){
 const r=gov[c],h2=r?.history2,h10=r?.history10;
 const ten=new Map((h10?.dates||[]).map((x,i)=>[x,h10.values[i]]));
 const pairs=(h2?.dates||[]).map((d,i)=>({d,y2:h2.values[i],y10:ten.get(d)}))
   .filter(x=>/^\d{4}-\d{2}-\d{2}$/.test(x.d)&&x.d<=r.date&&x.d<=today&&
     Number.isFinite(x.y2)&&Number.isFinite(x.y10)).sort((a,b)=>a.d.localeCompare(b.d));
 const end=pairs.at(-1),prev=pairs.at(-2);
 const args={country:c,now:today,asof:end?.d,previous:prev?.d,
  bp2:end&&prev?(end.y2-prev.y2)*100:null,
  bp10:end&&prev?(end.y10-prev.y10)*100:null,
  kind:money[c]?.kind,quality:money[c]?.quality,h6:money[c]?.horizons?.['6m']};
 const x=read(args);
 assert(x.headline.length>20&&x.meaning.length>30&&x.pricingEvidence.length>25&&x.watch.length>25,c);
 assert(!/undefined|NaN|Infinity/.test(x.headline+x.meaning+x.pricingEvidence+x.watch),c);
 if(end&&prev)assert(x.meaning.includes(end.d)&&x.meaning.includes(prev.d),c+' source dates');
 if(end?.d!=='2026-11-09'&&args.h6?.as_of!==end?.d&&
   args.h6?.rate!==null&&args.h6?.rate!==undefined&&args.h6?.as_of<=today&&end&&prev)
  assert(x.pricingEvidence.includes('non sono simultanee'),c+' different dates');
}
const mk=(bp2,bp10,asof='2026-11-09',extra={})=>read({
 country:'USD',now:today,asof,previous:asof<'2026-11-06'?'2026-09-29':'2026-11-06',bp2,bp10,
 kind:'OIS',quality:'FONTE UFFICIALE',
 h6:{rate:4.10,as_of:asof,change_1d_bp:2},...extra
});
assert.match(mk(-12,-3).meaning,/bull steepening/);
assert.match(mk(-3,-12).meaning,/bull flattening/);
assert.match(mk(12,3).meaning,/bear flattening/);
assert.match(mk(3,12).meaning,/bear steepening/);
assert.match(mk(-12,-3).headline,/2Y guida/);
assert.match(mk(-3,-12).headline,/10Y guida/);
assert.match(mk(-3,-12,'2026-09-30').headline,/storica/);
assert.match(mk(-3,-12,'2026-09-30').friction,/storica/);
assert.match(mk(-12,-3).support,/tratto breve/);
assert.match(mk(-3,-12).nextCheck,/tratto lungo/);
assert.match(mk(4,8,'2026-11-09',{h6:{rate:4.10,as_of:'2026-11-06',change_1d_bp:17}}).friction,/date diverse/);
assert.match(mk(4,8,'2026-11-09',{h6:{rate:4.10,as_of:'2026-11-09'}}).friction,/Manca una variazione verificata/);

assert.match(mk(4,8,'2026-11-09',{h6:{rate:4.10,as_of:'2026-11-06',change_1d_bp:17}}).pricingEvidence,
 /non sono simultanee/);
assert.doesNotMatch(mk(4,8,'2026-11-09',{h6:{rate:4.10,as_of:'2026-11-06',change_1d_bp:17}}).pricingEvidence,
 /Variazione 1D/);
assert.match(mk(4,8).pricingEvidence,/Variazione 1D/);
assert.match(mk(4,8,'2026-11-09',{h6:{rate:4.10,as_of:'2026-11-09',change_1d_bp:null}}).pricingEvidence,
 /Manca una variazione 1D/);
assert.match(mk(4,8,'2026-11-09',{h6:{rate:4.10,as_of:'2026-12-01',change_1d_bp:4}}).pricingEvidence,
 /non abbiamo un 6M/i);
const page=fs.readFileSync(path.join(root,'site/fx-quant-v2/next/index.html'),'utf8');
const rates=fs.readFileSync(path.join(root,'site/fx-quant-v2/next/rates-studio.js'),'utf8');
const app=fs.readFileSync(path.join(root,'site/fx-quant-v2/next/app.js'),'utf8');
assert(page.includes('rates-economic-reading.js?v=21'));
assert.match(page,/rates-studio\.js\?v=\d+/);
assert(page.indexOf('rates-working-model-v1.js')<page.indexOf('rates-studio.js'));
assert(page.includes('rates-relative-pricing-v1.js?v=1'));
assert.match(page,/rates-pricing-history-v1\.js\?v=[1-9]\d*/);
assert.match(page,/rates-pricing-moves-v1\.js\?v=[3-9]\d*/);
assert.match(page,/rates-studio\.css\?v=\d+/);
assert(/app\.js\?v=[\w.-]+/.test(page));
assert(rates.includes('fxRelativeEvidence(c,other)'), 'Rates first read needs a FX handoff');
assert(rates.includes('root.FXQuantRatesBridge.snapshot('),
 'FX movement must come from certified common-date 2Y/ECB bridge, not a new correlation');
assert(rates.includes('data-fx-proof=')&&rates.includes('data-rates-openpair='),
 'Verified/unavailable evidence tiers and real pair deep links are mandatory');
assert(app.includes("e.target.closest('[data-rates-openpair]')")&&
 app.includes("if(!openPair(ratesOpenPair.dataset.ratesOpenpair))return;")&&
 app.includes("const pair=resolvePair(key);")&&
 app.includes("Object.hasOwn(available,reverse)?reverse:null"),
 'Pair handoff must fail closed if pair source is absent');
const ratesCss=fs.readFileSync(path.join(root,'site/fx-quant-v2/next/rates-studio.css'),'utf8');
assert(ratesCss.includes('.rates-fx-handoff')&&ratesCss.includes('max-width:600px')&&
 ratesCss.includes(':focus-visible'),'Rates evidence design must be responsive and keyboard accessible');
assert(page.indexOf('rates-economic-reading.js')<page.indexOf('rates-studio.js'));
assert(rates.includes('m.headline')&&rates.includes('m.pricingEvidence')&&rates.includes('m.watch'));
const scriptWindow={window:{}};
vm.runInNewContext(fs.readFileSync(path.join(root,'site/fx-quant-v2/next/currency-data-fallback.js'),'utf8'),scriptWindow);
vm.runInNewContext(fs.readFileSync(path.join(root,'site/fx-quant-v2/next/g8-rates-shadow.js'),'utf8'),scriptWindow);
vm.runInNewContext(fs.readFileSync(path.join(root,'site/fx-quant-v2/assets/rates-working-model-v1.js'),'utf8'),scriptWindow.window);
vm.runInNewContext(rates,scriptWindow);
vm.runInNewContext(fs.readFileSync(path.join(root,'site/fx-quant-v2/next/research-editorials.js'),'utf8'),scriptWindow);
const spot=load('live_data/sections/CHF_SNB_10Y_SPOT_CONTEXT.json');
const chf=load('site/fx-quant-v2/chf-snb-paired-history.json');
const nzd=load('site/fx-quant-v2/nzd-b2-postroll-web-research.json');
const data={rates:gov,chfSpot:spot,chfResearch:chf,nzdPostroll:nzd,ois:{currencies:money}};
const liveDay=[spot.as_of,nzd.source_capture_date].sort().at(-1);
function render(ccy,overrides={},plots=[],editorial=false,today=liveDay){
 const fxData={...data,...overrides};
 const api={
  get:key=>fxData[key],FX:names,FLAGS:{},NAMES:{},state:{ccy,against:'USD'},
  plot:spec=>{plots.push(spec);return '';},editorial:()=>'<aside id="rates-test-editorial"></aside>',
  esc:x=>String(x??''),fmt:(x,n)=>Number.isFinite(x)?x.toFixed(n):'—',
  sign:()=>'',date:x=>x||'—',finite:Number.isFinite,
  validDay:x=>typeof x==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(x),
  dayNow:()=>today
 };
 return editorial?scriptWindow.window.FXQuantResearchEditorial.create(api).render('rates'):
  scriptWindow.window.FXQuantRates.render(api);
}
const chfPlots=[];
const chfLatest=chf.observations.at(-1);
const chfHtml=render('CHF',{},chfPlots);
assert.match(chfHtml,new RegExp('SNB 10Y spot '+spot.as_of));
assert.match(chfHtml,new RegExp('data-gov-paired="CHF".*'+chfLatest.date));
assert.match(chfHtml,new RegExp('data-gov-reference="CHF".*'+chfLatest.date));
const chfTile=chfHtml.match(/<button[^>]*data-rate-ccy="CHF"[^>]*>.*?<\/button>/)[0];
const chfStats=chfHtml.slice(chfHtml.indexOf('class="rates-stats"'),chfHtml.indexOf('data-gov-reference'));
assert(chfHtml.indexOf(chfTile)<chfHtml.indexOf('class="rates-stats"')&&
 chfHtml.indexOf('class="rates-stats"')<chfHtml.indexOf('rates-test-editorial'),
 'The selector and summary must precede the reading');
assert(chfTile.includes('10Y osservato <b>'+spot.value_percent.toFixed(3)+'%</b> · '+spot.as_of));
assert(chfStats.includes('Gov 10Y · Osservato</span><strong>'+spot.value_percent.toFixed(3)+'%</strong><small>SNB spot · '+spot.as_of));
assert(chfStats.includes('10Y − 2Y · Storico')&&chfStats.includes('Coppia SNB · '+chfLatest.date));
const ratesResearch=scriptWindow.window.FXQuantCurrencyFallback.researchRatesAxis('CHF',chf,null,gov,liveDay);
const chfEstimate=scriptWindow.window.FXQuantG8RatesShadow.chf({
 research:{currencies:{CHF:{ratesResearch}}},chfHistory:chf,spot,now:liveDay});
if(chfEstimate.status==='STIMA_MODELLO_RICERCA'){
 assert.match(chfHtml,/data-gov-estimate="CHF"/);
 assert(chfTile.includes(chfEstimate.estimate2Y.toFixed(3)+'%</strong><small>2Y stimato · '+spot.as_of));
 assert(chfStats.includes('Gov 2Y · Stima</span><strong>'+chfEstimate.estimate2Y.toFixed(3)+'%</strong><small>Stima al '+spot.as_of));
 assert(chfHtml.includes(chfEstimate.lower2Y.toFixed(3)+'–'+chfEstimate.upper2Y.toFixed(3)));
}
const chfGovPlot=chfPlots.find(x=>x.label==='Storico governativi CHF');
assert.deepEqual(Array.from(chfGovPlot.lines,x=>x.values.at(-1).label),[chfLatest.date,chfLatest.date]);
assert.deepEqual(Array.from(chfGovPlot.lines,x=>x.values.at(-1).value),[chfLatest['2Y'],chfLatest['10Y']]);
const chfFxPlot=chfPlots.find(x=>x.label.startsWith('Spread governativi'));
assert(chfFxPlot.lines[0].values.every(x=>x.label<=gov.CHF.date),'Research observations must not enter FX comparison');
const invalidChf=render('CHF',{chfResearch:{...chf,eligible_for_core:true}});
assert.match(invalidChf,new RegExp('2Y storico · '+gov.CHF.date));
assert.doesNotMatch(invalidChf,/data-gov-paired=/);
assert.doesNotMatch(invalidChf,/data-gov-estimate="CHF"/);
const essay=render('CHF',{},[],true);
assert.match(essay,new RegExp('Nella serie storica SNB del '+chfLatest.date));
assert.match(essay,/bull flattening/);
assert.doesNotMatch(essay,new RegExp('Al '+gov.CHF.date+' il governativo'));
const market=load('live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json');
const anchor=load('site/fx-quant-v2/nzd-asx-government-anchor-v1.json');
const research=load('site/fx-quant-v2/chf-nzd-benchmark-research.json');
const quoteDay=new Date(Date.parse(anchor.government_as_of+'T00:00:00Z')+86400000).toISOString().slice(0,10);
// Explicit historical canonical state for the estimate fallback exercise.
const staleGov={...gov,NZD:{...gov.NZD,date:anchor.government_as_of}};
const scenario={
 rates:staleGov,
 nzdAsxGovernmentAnchor:anchor,
 nzdBenchmarkResearch:{...research,NZD:{...research.NZD,latest_date:anchor.government_as_of,
  latest_2Y:anchor['2Y'],latest_10Y:anchor['10Y'],
  after_roll:[research.NZD.after_roll[0],{date:anchor.government_as_of,'2Y':anchor['2Y'],'10Y':anchor['10Y']}] }},
 nzdDirectionalProxy:{...market,as_of:quoteDay,
  source_url:'https://www.asx.com.au/data/futures/reports/EODWebMarketSummary'+quoteDay.slice(2).replace(/-/g,'')+'ZFT.htm',
  horizons:{'6m':{...market.horizons['6m'],implied_bank_bill_rate:anchor.asx_6m_rate-.04,
   expiration:anchor.asx_6m_expiration,expiry_label:anchor.asx_6m_contract}}}
};
const nzdPlots=[];
const scenarioToday=[liveDay,quoteDay].sort().at(-1);
const estimateHtml=render('NZD',scenario,nzdPlots,false,scenarioToday);
const expected2Y=(anchor['2Y']-.04).toFixed(3);
const expected10Y=(anchor['10Y']-.04).toFixed(3);
assert.match(estimateHtml,/data-gov-estimate="NZD"/);
assert(estimateHtml.includes(expected2Y+'%')&&estimateHtml.includes(expected10Y+'%'));
assert(estimateHtml.includes('Stima al '+quoteDay));
assert.match(render('NZD',scenario,[],true,scenarioToday),new RegExp('Stima dei governativi NZD al '+quoteDay));
assert(nzdPlots.find(x=>x.label==='Storico governativi NZD').lines[0].values.every(x=>x.label<quoteDay),
 'Estimated yields must not appear in the observed chart');
const wrongContract=JSON.parse(JSON.stringify(scenario));
wrongContract.nzdDirectionalProxy.horizons['6m'].expiration='2027-09-15';
assert.doesNotMatch(render('NZD',wrongContract,[],false,scenarioToday),/data-gov-estimate=/);
const newCanonical={...gov,NZD:{...gov.NZD,date:quoteDay}};
assert.doesNotMatch(render('NZD',{...scenario,rates:newCanonical},[],false,scenarioToday),/data-gov-estimate=/);
const currentNzd=render('NZD');
if(gov.NZD.date>=nzd.daily_observations.at(-1).date&&gov.NZD.date<=liveDay){
 assert.doesNotMatch(currentNzd,/data-gov-estimate="NZD"/);
 assert.match(currentNzd,new RegExp('GOV '+gov.NZD.date));
}else{
 assert.match(currentNzd,new RegExp('data-gov-reference="NZD".*'+nzd.daily_observations.at(-1).date));
}
assert.doesNotMatch(render('CHF',{chfSpot:{...spot,source_url:'https://invalid.example'}}),/data-gov-reference=/);
const newerCHF=render('CHF',{rates:{...gov,CHF:{...gov.CHF,date:spot.as_of,'2Y':0.42,'10Y':0.61}}});
assert.match(newerCHF,new RegExp('GOV '+spot.as_of));
assert.doesNotMatch(newerCHF,/2Y stimato|10Y osservato|data-gov-reference="CHF"/);
assert.doesNotMatch(render('NZD',{nzdPostroll:{...nzd,daily_observations:{}}}),/data-gov-reference=/);
assert.doesNotMatch(render('JPY'),/data-gov-reference=/);
console.log('NEXT_RATES_V20_PASS: G8 8/8, four curve regimes, source-date and stale guards, 6M unavailable/non-simultaneous/same-date.');
