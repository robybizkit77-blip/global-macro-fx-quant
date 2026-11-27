'use strict';
/* Contract test: research thesis, evidence and page continuity must share dates.
   No network, browser, external packages, or changes to FX Core. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const read=x=>fs.readFileSync(x,'utf8');
const json=x=>JSON.parse(read(x));
const app=read('site/fx-quant-v2/next/app.js');
const helperStart=app.indexOf('function researchCase(){');
const overviewStart=app.indexOf('function overview(){');
const overviewEnd=app.indexOf('\nfunction currencies(){',overviewStart);
assert(helperStart>=0&&overviewStart>helperStart&&overviewEnd>overviewStart,'Missing Next Research functions');
new vm.Script(app,{filename:'next-app.js'});
const functions=app.slice(helperStart,overviewEnd);
const chartFunctions=app.slice(app.indexOf('function historyRates(c){'),app.indexOf('function plot(opts){'))+
 app.slice(app.indexOf('function homeScreenChart('),app.indexOf('function homePairPreview(k){'));
const initial={
 currencyPrices:json('live_data/sections/ECB_G8_PRICE_HISTORY.json'),
 rates:json('live_data/sections/NATIVE_RATES_DATA.json'),
 dxy:json('live_data/sections/DXY_SYNTHETIC_ECB.json'),
 risk:json('site/fx-quant-v2/cross-asset-live-data.json'),
 pairs:json('live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json'),
 macro:json('live_data/sections/MACRO_THERMOMETER_DATA.json'),
 cot:json('live_data/sections/V247_COT_STORIES.json'),
 ois:json('site/fx-quant-v2/ois-pricing-snapshot.json'),
 cb:json('live_data/sections/NATIVE_CB_DATA.json')
};
const clone=x=>JSON.parse(JSON.stringify(x));
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const validDay=x=>typeof x==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(x);
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const date=x=>validDay(x)?x.slice(8,10)+'/'+x.slice(5,7)+'/'+x.slice(0,4):esc(x||'n.d.');
const fmt=(v,n=2)=>finite(v)?v.toLocaleString('it-IT',{minimumFractionDigits:n,maximumFractionDigits:n}):'—';
const sign=(v,n=1,suffix='')=>finite(v)?(v>0?'+':v<0?'−':'')+fmt(Math.abs(v),n)+suffix:'—';
function evaluate(data,now='2026-11-10',homeChart=null){
 const ctx={
  get:k=>data[k]||null,finite,validDay,esc,date,fmt,sign,
  dayNow:()=>now,
  fresh:(d,window=8)=>validDay(d)&&d<=now&&
    (Date.parse(now+'T12:00:00Z')-Date.parse(d+'T12:00:00Z'))/864e5<=window,
  eurPairs:()=>data.pairs?.pairs||{},
  getPairName:key=>key.slice(0,3)+'/'+key.slice(3),
  homeScreenChart:()=>'<div class="test-chart"></div>',
  choose:()=>'',plot:({lines})=>lines.map(x=>x.values.map(y=>y.label).join(',')).join(' | '),
  state:{homeEvidenceOpen:false,homeDossierOpen:false,homeChart},
  FX:['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'],
  FLAGS:{USD:'USD',EUR:'EUR',GBP:'GBP',JPY:'JPY',CHF:'CHF',AUD:'AUD',NZD:'NZD',CAD:'CAD'},
  ROUTES:{rates:'Tassi & OIS',risk:'Rischio'}
 };
 vm.createContext(ctx);
 new vm.Script((homeChart?chartFunctions:'')+functions+'\nvar qa={context:researchCase(),article:overview(),rates:researchBridge("rates"),risk:researchBridge("risk")};').runInContext(ctx,{timeout:5000});
 return ctx.qa;
}
const baseline=evaluate(initial);
assert.match(baseline.article,/class="market-letter market-dashboard"/);
assert.match(baseline.article,/class="letter-evidence"/);
assert.match(baseline.article,/class="dashboard-kpi-grid"/);
assert.match(baseline.article,/class="dashboard-analysis"/);
assert.match(baseline.article,/LA LETTURA FX DEL DESK/);
// This historical synthetic test is anchored on 10 November. The real
// repository now contains ECB/model snapshots dated 12 November. The
// older first read MUST withhold a current G8 ranking, not hallucinate
// strength for arbitrary currencies when a source comes from the future.
const historicalDay='2026-11-10';
const sourceAhead=[initial.currencyPrices.last_as_of,initial.pairs.price_asof]
 .some(d=>validDay(d)&&d>historicalDay);
if(sourceAhead){
 assert.match(baseline.article,/non sono allineati|manca ancora una lettura relativa verificabile/i,
  'Unsynchronized/future snapshots must suspend current FX relative claims');
 assert.match(baseline.article,/nessuna selezione automatica/i,
  'Missing same-date evidence cannot generate a Forex shortlist');
}else{
 assert.match(baseline.article,/NZD|CHF|AUD/,
  'With aligned inputs the G8 currency narratives must remain accessible');
}
assert.match(baseline.article,/FORZA RELATIVA G8/);
assert.match(baseline.article,/class="dashboard-reading-story"/);
assert.match(baseline.article,/dashboard-reading-source-links/,'Narrative must link to the underlying research');
for(const route of ['risk','rates','macro','currencies','pairs','cot','news'])
 assert.match(baseline.article,new RegExp('href="#'+route+'"'),'Missing research link '+route);
const firstReading=baseline.article.split('<details class="dashboard-technical"')[0];
assert.doesNotMatch(firstReading,/Il 2Y reagisce più direttamente|Se il front-end scende più del long-end/,
 'Home must interpret current observations, not teach generic yield definitions');

assert.match(baseline.article,/data-home-evidence/);
assert.match(baseline.article,/FORZA RELATIVA G8/);
assert.match(baseline.article,/28 coppie/);
if(sourceAhead)assert.match(baseline.article,/28 coppie/,'A suspended first read must still link the FX universe');
else assert.match(baseline.article,/USD\/JPY/,'With synchronized data validate the pair-specific comparison');
const forexOpening=baseline.article.split('<details class="dashboard-technical"')[0];
const fxPosition=forexOpening.search(/(?:FX|FOREX) G8/i);
assert(fxPosition>=0,'Fallback Home must remain explicitly oriented toward G8 Forex');
if(forexOpening.includes('VIX'))
 assert(fxPosition<forexOpening.indexOf('VIX'),'Fallback Home cannot lead with VIX');

assert.doesNotMatch(baseline.article,/data-home-evidence open/,'Quantitative layer must start collapsed');
assert(baseline.article.indexOf('dashboard-reading-story') <
       baseline.article.indexOf('dashboard-kpi-grid'),
       'The narrative must precede numerical cards');
assert.match(baseline.article,/Che cosa sta già prezzando il mercato/);
assert.match(baseline.article,/class="dashboard-dossier"/);
assert.match(baseline.article,/Che cosa mi farebbe cambiare idea/);
assert.match(baseline.rates,/Rileggi la tesi del desk/);
assert.match(baseline.risk,/Nasdaq|Le osservazioni azionario/);
assert(!baseline.article.includes('desk-path-grid'));
const stress=clone(initial);
for(const k of ['NASDAQCOM','VIX','HY_OAS'])stress.risk.streams[k].date='2026-11-09';
stress.risk.streams.NASDAQCOM.change_1d_pct=-4;
stress.risk.streams.VIX.previous=20;stress.risk.streams.VIX.value=31;
stress.risk.streams.HY_OAS.previous=3.1;stress.risk.streams.HY_OAS.value=3.45;
stress.pairs.price_asof=initial.currencyPrices.last_as_of;
let x=evaluate(stress,'2026-11-10');
assert.equal(x.context.kind,'stress');
assert.match(x.article,/href="#currencies"/,
 'Even during an equity-led shock the user must reach the currency evidence');
assert.match(x.article,/href="#pairs"/,
 'Equity stress cannot remove the direct 28-pair research path');
assert.match(x.article,/dashboard-reading-source-links/,
 'Even in a risk shock the user must reach G8 currencies and paired FX research');
if(sourceAhead)assert.match(x.article,/non sono allineati|nessuna selezione automatica/i,
 'Risk-off must not bypass missing or future-dated Forex snapshots');
assert.equal(x.context.focus,'nasdaq');
assert.match(x.article,/data-research-kind="stress"/);
assert.match(x.article,/Il mio giudizio\./,'The Home needs an explicit market verdict');
assert.match(x.article,/disoccupazione/,'The Home must connect macro to the market narrative');
if(!sourceAhead)assert.match(x.article,/EUR\/USD/,'The Home must connect dated FX pairs to the market narrative');
else assert.doesNotMatch(x.article,/Nel dossier EUR\/USD al/,'Future pair dossiers must be withheld');
if(!sourceAhead)assert.match(x.article,/USD\/JPY/,'Aligned data should surface price-versus-thesis divergence');
else assert.match(x.article,/nessuna selezione automatica/i,
 'Unaligned future FX snapshot cannot be promoted during a historical risk shock');
assert.match(x.article,/Credito High Yield/);
assert.match(x.article,/Fixing FX 10\/11\/2026/);
const mismatchedPricing=clone(stress);
mismatchedPricing.ois.currencies.USD.horizons['6m'].as_of='2026-11-06';
mismatchedPricing.ois.currencies.USD.horizons['6m'].change_1d_bp=9;
const mismatchView=evaluate(mismatchedPricing,'2026-11-10');
assert.match(mismatchView.article,/Non coincide con la data del focus/);
assert.doesNotMatch(mismatchView.article,/La variazione dichiarata è/);
const matchedPricing=clone(stress);
matchedPricing.ois.currencies.USD.horizons['6m'].as_of='2026-11-09';
matchedPricing.ois.currencies.USD.horizons['6m'].change_1d_bp=5;
assert.match(evaluate(matchedPricing,'2026-11-10').article,
 /La variazione dichiarata è/);
const futurePricing=clone(stress);
futurePricing.ois.currencies.USD.horizons['6m'].as_of='2026-11-20';
assert.match(evaluate(futurePricing,'2026-11-10').article,
 /non abbiamo una scadenza monetaria USA a sei mesi utilizzabile/);
assert.doesNotMatch(evaluate(futurePricing,'2026-11-10').article,
 /20\/11\/2026/,'Future-dated monetary reference must not appear in the analysis');
const later=clone(stress);
later.dxy.as_of='2026-11-11';
later.pairs.price_asof='2026-11-12';
later.cot.EUR={signal:'EXTREME SHORT',today:'CFTC al 2026-11-13: fondi net short'};
later.cot.AUD={signal:'EXTREME SHORT',today:'CFTC al 2026-11-13: fondi net short'};
later.macro.currencies.USD.inflation.as_of='2026-12';
const historical=evaluate(later,'2026-11-10').article;
assert.doesNotMatch(historical,/1[1-3]\/11\/2026|2026-12|Il COT aggiunge una sfumatura|Nel dossier EUR\/USD al/,
 'Future FX quotes, pair narratives, positioning and macro periods must be withheld');
const dated=clone(later);
dated.dxy.as_of='2026-11-09';
dated.pairs.price_asof='2026-11-09';
dated.cot.EUR.today='CFTC al 2026-11-03: fondi net short';
const datedHistory=evaluate(dated,'2026-11-10').article;
assert.match(datedHistory,/proxy del dollaro ricavato dai fixing BCE ha registrato/);
assert.match(datedHistory,/Nel dossier EUR\/USD al 09\/11\/2026/);
assert.match(datedHistory,/Il COT aggiunge una sfumatura: sull’euro/);
assert.doesNotMatch(datedHistory,/anche sul dollaro australiano il posizionamento/,
 'Each positioning entry has its own date');
const chartOnly={risk:{streams:{NASDAQCOM:{
 date:'2026-11-11',change_1d_pct:9.99,publisher:'FRED',
 history:[['2026-11-09',100],['2026-11-10',101],['2026-11-11',111]]
}}}};
const chart=evaluate(chartOnly,'2026-11-10','nasdaq').article;
assert.match(chart,/Ultimo 10\/11\/2026/);
assert.match(chart,/2026-11-09,2026-11-10/);
assert.doesNotMatch(chart,/11\/11\/2026|2026-11-11|9,99%/,
 'The chart and its annotation use the same historical cutoff');
const relief=clone(stress);
relief.risk.streams.NASDAQCOM.change_1d_pct=3.2;
relief.risk.streams.VIX.previous=31;relief.risk.streams.VIX.value=23;
relief.risk.streams.HY_OAS.previous=3.45;relief.risk.streams.HY_OAS.value=3.13;
x=evaluate(relief,'2026-11-10');
assert.equal(x.context.kind,'relief');
assert.match(x.article,/La distensione sarebbe fragile/);
const bond=clone(initial);
// Isolate this rates-only scenario from moving real cross-asset fixtures.
// A live NASDAQ/VIX/HY 'relief' day must not pre-empt the synthetic bond case.
for(const k of ['NASDAQCOM','VIX','HY_OAS'])bond.risk.streams[k].date='2026-11-03';
bond.rates.USD.date='2026-11-12';bond.rates.USD.chg2_bp=12;bond.rates.USD.chg10_bp=8;
bond.dxy.as_of='2026-11-12';bond.pairs.price_asof='2026-11-12';
x=evaluate(bond,'2026-11-12');
assert.equal(x.context.kind,'yield-selloff');
assert.equal(x.context.focus,'rates');
assert.match(x.article,/(?:FX|FOREX) G8/,'New rates must not hijack the Forex-first Home');
assert.doesNotMatch(x.article,/data-research-kind="stress"/);
const fx=clone(bond);
fx.rates.USD.chg2_bp=4;fx.rates.USD.chg10_bp=0;
fx.dxy.previous_value=101;fx.dxy.value=99;
x=evaluate(fx,'2026-11-12');
assert.equal(x.context.kind,'fx-divergence');
assert.equal(x.context.focus,'dxy');
assert.match(x.article,/(?:FX|FOREX) G8/,'USD/2Y divergence stays a secondary FX diagnostic');
const outOfSync=clone(stress);
outOfSync.risk.streams.VIX.date='2026-11-08';
assert.notEqual(evaluate(outOfSync,'2026-11-10').context.kind,'stress');
const fxMissing=clone(initial);fxMissing.currencyPrices.rows=[];
const noFx=evaluate(fxMissing,'2026-11-10');
assert.match(noFx.article,/non sono allineati/,'Missing G8 must never turn into fabricated market leadership');
const empty=evaluate({});
assert.equal(empty.context.kind,'mixed');
assert.match(empty.article,/letter-proof-empty/);
const malicious=clone(initial);
malicious.pairs.price_asof='2026-11-10';
malicious.pairs.pairs.EURUSD.decision_frame.relation='<img src=x onerror=alert(1)>';
const html=evaluate(malicious).article;
assert(html.includes('&lt;img'));
assert(!html.includes('<img'));
const staleDay=new Date(Date.parse(initial.currencyPrices.last_as_of+'T12:00:00Z')+18*864e5).toISOString().slice(0,10);
const stale=evaluate({...initial,pairs:{...initial.pairs,price_asof:initial.currencyPrices.last_as_of}},staleDay);
assert.match(stale.article,/fotografia storica/,'Aligned old FX sources must show their age');
if(initial.pairs.price_asof!==initial.currencyPrices.last_as_of){
 assert.match(evaluate(initial,staleDay).article,/non sono allineati/,
  'A newer fixing must not be passed off as a matching Pair snapshot');
}
assert.match(app,/state\.data=nextData/);
assert.match(app,/cache:'no-store'/);
assert.match(app,/visibilitychange/);
const page=read('site/fx-quant-v2/next/index.html');
assert.match(page,/editorial-v4\.css\?v=18/);
assert.match(page,/<script\b[^>]*src="\.\/app\.js\?v=18(?:\.[^"]+)?"/);
assert.match(page,/<script\b[^>]*src="\.\/macro-approved-layout\.js\?v=[^"]+"/);
assert(page.indexOf('macro-approved-layout.js?v=')<page.indexOf('macro-studio.js?v='),'Approved layout must load before Macro Studio');

const momentumApi=require('../site/fx-quant-v2/next/currency-strength-reading.js');
const momentumDate=initial.currencyPrices.last_as_of;
const momentum=momentumApi.momentum(initial.currencyPrices,momentumDate);
assert.equal(momentum.items.length,8);
assert.equal(momentum.asof,momentumDate);
assert(momentum.from<momentum.mid&&momentum.mid<momentum.asof);
assert(momentum.items.every(x=>finite(x.delta)&&Math.abs(x.delta-(x.recent-x.prior))<1e-10));
assert.equal(momentumApi.momentum({...initial.currencyPrices,rows:initial.currencyPrices.rows.slice(-10)},momentumDate),null);
assert.equal(momentumApi.momentum({...initial.currencyPrices,rows:[...initial.currencyPrices.rows,initial.currencyPrices.rows.at(-1)]},momentumDate),null);
assert.equal(momentumApi.momentum(initial.currencyPrices,staleDay),null);
const fxBasket=['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'];
const fixture={...initial.currencyPrices,last_as_of:'2026-11-16',rows:Array.from({length:11},(_,i)=>({
 Date:new Date(Date.UTC(2026,10,6+i)).toISOString().slice(0,10),
 ...Object.fromEntries(fxBasket.map(c=>[c,c==='USD'?Math.exp(i<6?i*.001:.005-(i-5)*.002):1]))
}))};
const usdImpulse=momentumApi.momentum(fixture,'2026-11-16').items.find(x=>x.ccy==='USD');
assert(usdImpulse.recent>0&&usdImpulse.prior<0&&usdImpulse.delta>0);
assert.equal(usdImpulse.label,'Passa in positivo');
assert.equal(usdImpulse.tone,'positive');

const pairEvidence=require('../site/fx-quant-v2/next/pair-rankings.js').pairEvidenceView;
const shortEvidence=pairEvidence({base:'AUD',quote:'USD',favored:'USD',thesisStrength:'PARZIALE',tradeAttractiveness:'DA VALIDARE',move5Percent:-.8,pricePercent:-1.5});
assert.deepEqual(shortEvidence.thesis,['amber','Parziale']);
assert.deepEqual(shortEvidence.five,['green','A favore']);
assert.deepEqual(shortEvidence.twenty,['green','A favore']);
assert.deepEqual(shortEvidence.timing,['amber','Da validare']);
const earlyEvidence=pairEvidence({base:'AUD',quote:'USD',favored:'USD',thesisStrength:'PARZIALE',tradeAttractiveness:'BASSA ORA',move5Percent:.6,pricePercent:-1.5});
assert.deepEqual(earlyEvidence.five,['red','Contrario']);
assert.deepEqual(earlyEvidence.twenty,['green','A favore']);
assert.deepEqual(earlyEvidence.timing,['red','Sfavorevole ora']);
assert.deepEqual(pairEvidence({base:'AUD',quote:'USD',favored:null,move5Percent:1}).five,['neutral','Non valutabile']);
assert.deepEqual(pairEvidence({base:'AUD',quote:'USD',favored:'USD',move5Percent:-.02}).five,['amber','Indeciso']);

const creditMarket=require('../site/fx-quant-v2/next/liquidity-credit-studio.js').creditMarket;
const creditDate='2026-11-24';
const fixtureCredit={streams:Object.fromEntries([['IG_OAS','BAMLC0A0CM',.98,.94],['HY_OAS','BAMLH0A0HYM2',3.76,3.52]].map(([k,id,value,previous])=>[k,{date:'2026-11-20',value,previous,quality:'PUBLISHED_SOURCE_RESEARCH_ONLY',not_intraday:true,source_url:'https://fred.stlouisfed.org/graph/fredgraph.csv?id='+id}]))};
const spreadRead=creditMarket(fixtureCredit,creditDate);
assert.deepEqual(spreadRead.map(x=>x.bp),[4,24]);
assert(spreadRead.every(x=>x.tone==='down'));
assert(creditMarket(fixtureCredit,'2026-12-20').every(x=>!x.ok));
assert(creditMarket(fixtureCredit,'2026-11-19').every(x=>!x.ok));
const pricingMoves=require('../site/fx-quant-v2/next/rates-pricing-moves-v1.js');
const pricingInputs={snapshot:initial.ois,operational:json('live_data/sections/OIS_OPERATIONAL_VIEW.json'),
 research:json('site/fx-quant-v2/ois-same-contract-repricing-research.json'),
 nzd:json('live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json'),today:initial.currencyPrices.last_as_of};
const firstRead=pricingMoves.overviewModel(pricingInputs);
assert.equal(firstRead.rows.length,8);
assert(firstRead.official.every(r=>r.source==='official'&&finite(r.week)));
assert.equal(firstRead.weekly,firstRead.rows.filter(r=>finite(r.week)).length);
const ratesHtml=pricingMoves.renderOverview(pricingInputs);
assert.equal((ratesHtml.match(/class="rates-first-row"/g)||[]).length,8);
assert.match(ratesHtml,/Perché conta per il Forex/);
assert.match(ratesHtml,/non OIS ufficiali/);
const blankRates=pricingMoves.overviewModel({today:pricingInputs.today});
assert.equal(blankRates.weekly,0);
assert.equal(blankRates.daily,0);
assert(blankRates.rows.every(r=>r.tone==='neutral'));

const cbStudio=require('../site/fx-quant-v2/next/central-bank-studio.js');
const cbToday=initial.currencyPrices.last_as_of;
const cbFixture={...initial,oisOperational:json('live_data/sections/OIS_OPERATIONAL_VIEW.json'),
 oisSameContract:json('site/fx-quant-v2/ois-same-contract-repricing-research.json'),
 nzdDirectionalProxy:json('live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json')};
const cbFx=['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'];
for(const ccy of cbFx){
 const html=cbStudio.render({get:k=>cbFixture[k],FX:cbFx,FLAGS:{},NAMES:{},state:{cbCcy:ccy},
 pageHero:()=>'',esc,fmt,date,dayNow:()=>cbToday});
 assert.equal((html.match(/class="bank-first-axis/g)||[]).length,3);
 assert.equal((html.match(/data-bank-country=/g)||[]).length,8);
 for(const heading of ["Cosa va","Cosa frena","Cosa guardare"])assert(html.includes("<h3>"+heading+"</h3>"));
 assert.doesNotMatch(html,/undefined|NaN/);
}

const riskView=require('../site/fx-quant-v2/next/risk-evidence-reading.js');
const riskDeskTest=riskView.editorial({ready:true,stale:false,changes:{SP500:{change:1},NASDAQCOM:{change:-1},VIX:{change:1},HY_OAS:{change:-1},IG_OAS:{change:0}},monitor:'Controlla la diffusione'});
assert.match(riskDeskTest.support,/S&P 500 in rialzo/);
assert.match(riskDeskTest.support,/Credito HY in restringimento/);
assert.match(riskDeskTest.friction,/Nasdaq Composite in calo/);
assert.match(riskDeskTest.friction,/VIX in rialzo/);
assert.equal(riskDeskTest.watch,'Controlla la diffusione');
const riskDate=Object.values(initial.risk.streams).map(x=>x.date).filter(Boolean).sort().at(-1);
const riskAlignedView=riskView.read(initial.risk.streams,riskDate);
const riskLatestView=riskView.latestObservations(initial.risk.streams,riskDate);
assert.deepEqual(riskLatestView.map(x=>x.key),['SP500','NASDAQCOM','DJIA','SX5E','VIX','HY_OAS','IG_OAS']);
const riskOverviewHtml=riskView.renderFirstRead(initial.risk.streams,riskDate,riskAlignedView);
assert.equal((riskOverviewHtml.match(/class="risk-first-latest-item /g)||[]).length,7);
assert.match(riskOverviewHtml,/Dow Jones/);
assert.match(riskOverviewHtml,/Euro Stoxx 50/);
assert.match(riskOverviewHtml,/Date diverse: non sono una conferma simultanea/);
if(riskAlignedView.ready)assert.equal((riskOverviewHtml.match(/class="risk-first-common-item /g)||[]).length,5);
assert(riskView.latestObservations({},riskDate).every(x=>!x.ok));
assert(riskView.latestObservations(initial.risk.streams,'2099-01-01').every(x=>!x.ok));
assert(riskView.latestObservations(initial.risk.streams,'2000-01-01').every(x=>!x.ok));

const calendarFocus=require('../site/fx-quant-v2/next/calendar-operational-reading.js');
const newsFocus=require('../site/fx-quant-v2/next/news-evidence-reading.js');
const agendaFixture={asof:'2026-11-24T08:00:00Z',events:[
 {importance:'HIGH',quality:'OFFICIAL_CALENDAR',day:'2026-11-25',title:'Near'},
 {importance:'MEDIUM',quality:'OFFICIAL_CALENDAR',day:'2026-11-25',title:'Medium'},
 {importance:'HIGH',quality:'OFFICIAL_CALENDAR',day:'2026-12-02',title:'Far'},
 {importance:'HIGH',quality:'UNVERIFIED',day:'2026-11-25',title:'Unverified'}
]};
const calendarNow=Date.parse('2026-11-24T12:00:00Z');
assert.deepEqual(calendarFocus.nearCatalysts(agendaFixture,'2026-11-24',calendarNow).map(x=>x.title),['Near']);
assert.equal(calendarFocus.nearCatalysts({...agendaFixture,asof:'2026-11-01T08:00:00Z'},'2026-11-24',calendarNow).length,0);
assert.deepEqual(newsFocus.focusPulse([
 {id:'recent',importance:'HIGH',asof:'2026-11-23'},
 {id:'medium',importance:'MEDIUM',asof:'2026-11-23'},
 {id:'old',importance:'HIGH',asof:'2026-11-01'},
 {id:'future',importance:'HIGH',asof:'2026-11-25'}
],'2026-11-24').map(x=>x.id),['recent']);

const cotCtx={window:{}};
vm.createContext(cotCtx);
for(const file of ['cot-evidence-reading.js','cot-report-reading-v26.js','cot-studio.js']){
 new vm.Script(read('site/fx-quant-v2/next/'+file)).runInContext(cotCtx);
}
const cotData={cotHistory:json('live_data/sections/V250_COT_CHART_DATA.json'),
 cotPriorReference:json('site/fx-quant-v2/design-studio-cot-v1-data.json'),currencyPrices:initial.currencyPrices};
const cotFX=['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'];
const cotHtml=cotCtx.window.FXQuantCOT.render({get:k=>cotData[k],FX:cotFX,
 FLAGS:Object.fromEntries(cotFX.map(c=>[c,c])),state:{ccy:'USD',cotMetric:'net',cotWindow:52},
 plot:()=>'',pageHero:()=>'',esc,fmt,sign,date,finite,validDay,
 dayNow:()=>initial.currencyPrices.last_as_of,qBadge:()=>''});
const cotPanel=cotHtml.split('<section class="cot-flow-overview"')[1]?.split('</section>')[0];
assert(cotPanel,'G8 gross flow overview required');
assert.equal((cotPanel.match(/class="cot-flow-row /g)||[]).length,8);
assert.equal((cotPanel.match(/class="cot-flow-axis /g)||[]).length,16);
assert.doesNotMatch(cotPanel,/undefined|NaN/);
assert.match(cotPanel,/OI stimato/);
assert.match(cotPanel,/non ordini o identità/);

const libraryDesk=require('../site/fx-quant-v2/next/research-library.js');
const libraryFixture=[
 {type:'daily',file:'daily.html',date:'2026-11-23',title:'Briefing'},
 {type:'macro',file:'macro.html',date:'2026-11-20',title:'Macro'},
 {type:'cot',file:'cot.html',date:'2026-11-17',title:'COT'},
 {type:'ois',file:'ois.html',date:'2026-11-20',title:'OIS'}
];
const librarySummary=libraryDesk.catalogSummary(libraryFixture,libraryFixture.slice(0,3),'2026-11-24');
assert.equal(librarySummary.total,4);
assert.equal(librarySummary.confirmed,3);
assert.equal(librarySummary.current,2);
assert.equal(librarySummary.overdue,1);
assert.equal(librarySummary.unverified,1);
assert.equal(librarySummary.daily.status.state,'previous');
assert.equal(libraryDesk.catalogSummary(libraryFixture,[],'2026-11-24').confirmed,0);
require('./publishing/test_next_home_thesis_recalc_v1.cjs');
console.log('NEXT_RESEARCH_COHERENCE_FX_FIRST_PASS: regimes=stress,relief,yield-selloff,fx-divergence,mixed; matched evidence; fresh/stale/missing; XSS; page continuity; cache refresh');

// All consumers use the same source-dated issuer context; exact figures stay in evidence.
const issuer=require('../site/fx-quant-v2/next/issuer-release-context.js');
const release={ccy:'AUD',quality:'OFFICIAL_RECURRING_RELEASE_OBSERVED_NOT_EVENT_REACTION',as_of:'2026-11-25',reference_period:'October 2026',source:'ABS',source_url:'https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/oct-2026',event_key:'AUD|2026-11-25|INFLATION|Consumer Price Index, Australia',metrics:[{id:'AU_CPI_HEADLINE_YOY',value_percent:4.9,previous_period_percent:4.3},{id:'AU_CPI_TRIMMED_MEAN_YOY',value_percent:3.8,previous_period_percent:3.6}]};
const releaseSnapshot={schema:'GMFQ_MACRO_V3_G8_28PAIR_PUBLIC_OBSERVED_CONTEXT_V1',countries:{AUD:{issuer_releases:[release]}}};
assert.equal(issuer.rows(releaseSnapshot,['AUD','AUD'],'2026-11-25').length,1);
assert.equal(issuer.rows(releaseSnapshot,['AUD'],'2026-11-24').length,0);
assert.equal(issuer.rows(releaseSnapshot,['USD'],'2026-11-25').length,0);
assert.match(issuer.narrative(releaseSnapshot,['AUD'],'2026-11-25'),/accelera/);
assert.doesNotMatch(issuer.narrative(releaseSnapshot,['AUD'],'2026-11-25'),/%/);
assert.match(issuer.render(releaseSnapshot,['AUD'],'2026-11-25'),/4,9%/);
assert.match(issuer.render(releaseSnapshot,['AUD'],'2026-11-25'),/3,8%/);
for(const path of ['macro-approved-layout.js','central-bank-studio.js','currency-studio.js','rates-studio.js','app.js'])assert.match(read('site/fx-quant-v2/next/'+path),/FXQuantIssuerContext/);
console.log('SHARED_ISSUER_CONTEXT_CONSUMERS_PASS');

{
 const shadow=require('../site/fx-quant-v2/next/macro-multifactor-shadow-v1.js');
 const cycle=require('../site/fx-quant-v2/next/recession-traffic-light-v1.js');
 const catalog=JSON.parse(read('live_data/sections/MACRO_SERIES.json'));
 const supplement=JSON.parse(read('site/fx-quant-v2/next/semaphore-supplement-v1.json'));
 const observed=JSON.parse(read('site/control-room-preview/macro-v3-current-evidence.json'));
 const day=observed.generated_europe_rome_day;
 assert.equal(shadow.FAMILY.reduce((s,x)=>s+x[2],0),100);
 assert.deepEqual(shadow.dimensions({direction:1,level:null,acceleration:null,persistence:null}),{value:1,coverage:.5});
 assert.deepEqual(shadow.dimensions({}),{value:null,coverage:0});
 assert.equal(shadow.area({signal:{tone:'neutral'},items:[]}),null);
 assert.equal(shadow.finance(null,{value:1,coverage:.8,evidence:[]}).coverage,.4);
 for(const country of cycle.coverage){
  const rows=cycle.model(catalog,day,country,supplement);
  const result=shadow.evaluate({country,rows,observed,day});
  assert.equal(result.families.length,8);
  assert.equal(result.affectsFxRanking,false);
  assert.equal(result.eligibleForTrading,false);
  assert.equal(result.pointInTimeCertified,false);
  assert.ok(result.effectiveCoverage>=0&&result.effectiveCoverage<=100);
  assert.ok(result.score===null||result.score>=0&&result.score<=10);
  assert.ok(result.families.every(x=>x.score===null||x.score>=0&&x.score<=10));
  assert.doesNotMatch(shadow.render(result,String),/NaN|undefined/);
  assert.match(shadow.render(result,String),/non modifica il ranking FX/);
  assert.equal(shadow.evaluate({country,rows:[],observed:null,day}).score,null);
 }
 assert.equal(shadow.gdp({...observed,safe_to_republish_D:true},'USD',day),null);
 assert.equal(shadow.money({...observed,sector_financial_status:'WITHHELD'},'USD',day),null);
 const next= new Date(Date.parse(day)+8*864e5).toISOString().slice(0,10);
 assert.equal(shadow.gdp(observed,'USD',next),null);
 for(const path of ['macro-approved-layout.js','currency-studio.js']) assert.match(read('site/fx-quant-v2/next/'+path),/FXQuantMacroMultifactorShadow/);
 for(const path of ['macro-strength-estimated-v1.js','pair-rankings.js']) assert.doesNotMatch(read('site/fx-quant-v2/next/'+path),/FXQuantMacroMultifactorShadow/);
 console.log('G8_MULTIFACTOR_MACRO_SHADOW_PASS');
}

{
 const bank=require('../site/fx-quant-v2/next/central-bank-studio.js');
 const engine=require('../site/fx-quant-v2/next/recession-traffic-light-v1.js');
 const catalog=JSON.parse(read('live_data/sections/MACRO_SERIES.json'));
 const overlay=JSON.parse(read('site/fx-quant-v2/next/semaphore-supplement-v1.json'));
 const today=JSON.parse(read('site/control-room-preview/macro-v3-current-evidence.json')).generated_europe_rome_day;
 for(const country of engine.coverage){
  const x=bank.policyMacroContext({engine,catalog,overlay,country,today});
  assert.equal(x.researchOnly,true);
  assert.ok([...x.prices,...x.wages].every(a=>a.available&&!a.stale&&['M','Q'].includes(a.freq)));
  assert.equal(x.jobs,engine.model(catalog,today,country,overlay).find(r=>r.key==='jobs').signal.tone);
  assert.doesNotMatch(bank.renderPolicyMacroContext(x,String,x=>x.toFixed(2)),/undefined|NaN/);
 }
 const fake={inflationContext:()=>[{available:true,value:3,freq:'M'},{available:true,value:3,freq:'M',direction:null}],wageContext:()=>[{available:true,value:2,freq:'A',stale:true}],model:()=>[{key:'jobs',signal:{tone:'red'}}]};
 const x=bank.policyMacroContext({engine:fake,catalog:{},country:'CHF',today});
 assert.equal(x.missingWages,true);
 assert.match(x.sentences.join(' '),/direzione non interamente verificata/);
 assert.match(x.sentences.join(' '),/deterioramento/);
 assert.equal(bank.policyMacroContext({catalog:{},country:'CHF',today}),null);
 console.log('CB_CAN_CANONICAL_CONTEXT_PASS');
}

{
 const score=require('../site/fx-quant-v2/next/rates-research-score-v1.js');
 const pricing=require('../site/fx-quant-v2/next/rates-pricing-moves-v1.js');
 const archive=require('../site/fx-quant-v2/next/rates-pricing-history-v1.js');
 const load=p=>JSON.parse(read(p));
 const snapshot=load('site/fx-quant-v2/ois-pricing-snapshot.json'),operational=load('live_data/sections/OIS_OPERATIONAL_VIEW.json'),research=load('site/fx-quant-v2/ois-same-contract-repricing-research.json'),nzd=load('live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json'),history=load('site/fx-quant-v2/next/rates-pricing-history-v1.json'),rates=load('live_data/sections/NATIVE_RATES_DATA.json');
 const today=load('site/control-room-preview/macro-v3-current-evidence.json').generated_europe_rome_day;
 for(const currency of ['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']){
  const x=score.evaluate({pricing,archive,snapshot,operational,research,nzd,history,rates,today,currency,other:'EUR'});
  assert.equal(x.affectsFxRanking,false);assert.equal(x.eligibleForTrading,false);
  assert.ok(x.row.score===null||x.row.score>=0&&x.row.score<=10);
  if(x.row.quality!=='UFFICIALE')assert.equal(x.row.officialScore,null);
  if(x.row.week===null)assert.equal(x.row.score,null);
  if(x.relative){assert.equal(x.row.asof,x.peer.asof);assert.equal(x.row.referenceFrom,x.peer.referenceFrom);assert.ok(Math.abs(x.relative.bp-(x.row.week-x.peer.week))<1e-10);}
  assert.doesNotMatch(score.render(x,String),/undefined|NaN/);
 }
 const fake=bp=>({readCurrency:()=>({kind:'FUTURES SECONDARI',source:'test',rows:[{tenor:'6m',asof:'2026-11-27',rate:3,week:bp===null?null:{bp,method:'CONTRATTO IDENTICO · RICERCA SECONDARIA',from:'2026-11-20'}}]})});
 for(const [bp,expected] of [[25,10],[-25,0],[0,5],[null,null],[100,10]]){
  const x=score.evaluate({pricing:fake(bp),currency:'USD',today:'2026-11-27'});
  assert.equal(x.row.score,expected);assert.equal(x.row.officialScore,null);
 }
 assert.equal(score.evaluate({pricing:fake(25),currency:'USD',today:'2026-12-05'}).row.score,null);
 assert.equal(score.sovereign({date:'2026-11-27','2Y':3.0307479,weekly2_validation:{start_date:'2026-11-20',end_date:'2026-11-27',start_value:3.12506375,end_value:3.0307479,change_bp:-9.4}},'2026-11-27').bp,-9.4);
 const h={kind:'FUTURES',tenors:{'6m':[{date:'2026-11-13',rate:3,contract:'A',source_class:'OFFICIAL_TENOR',derived:false},{date:'2026-11-20',rate:3.1,contract:'A',source_class:'OFFICIAL_TENOR',derived:false},{date:'2026-11-27',rate:3.3,contract:'A',source_class:'OFFICIAL_TENOR',derived:false}]}};
 assert.equal(score.observedWeeklyPair(h,{asof:'2026-11-27',rate:3.3,week:{bp:20}}).acceleration,10);
 h.tenors['6m'][0].contract='B';
 assert.equal(score.observedWeeklyPair(h,{asof:'2026-11-27',rate:3.3,week:{bp:20}}),null);
 for(const path of ['macro-strength-estimated-v1.js','pair-rankings.js'])assert.doesNotMatch(read('site/fx-quant-v2/next/'+path),/FXQuantRatesResearchScore/);
 console.log('RATES_RESEARCH_SCORE_EXACT_INTERVAL_PASS');
}

{
 const score=require('../site/fx-quant-v2/next/positioning-research-score-v1.js');
 const desk=require('../site/fx-quant-v2/next/cot-report-reading-v26.js');
 const history=JSON.parse(read('live_data/sections/V250_COT_CHART_DATA.json'));
 const archive=JSON.parse(read('site/fx-quant-v2/design-studio-cot-v1-data.json'));
 const today=JSON.parse(read('site/control-room-preview/macro-v3-current-evidence.json')).generated_europe_rome_day;
 for(const currency of ['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']){
  const x=score.evaluate({currency,history,archive,desk,today});
  assert.ok(x);
  assert.equal(x.affectsFxRanking,false);
  assert.equal(x.eligibleForTrading,false);
  assert.equal(x.pointInTimeCertified,false);
  assert.ok(x.score===null||x.score>=0&&x.score<=10);
  if(x.score!==null){
   const clip=v=>Math.max(-1,Math.min(1,v));
   assert.ok(Math.abs(x.score-(5+5*(.6*clip(x.flow1/2)+.4*clip(x.previous3/2))))<1e-10);
   assert.ok(Math.abs(x.acceleration-(x.flow1-x.previous3))<1e-10);
  }
  assert.doesNotMatch(score.render(x,String),/undefined|NaN/);
  const old=new Date(Date.parse(x.asof)+15*864e5).toISOString().slice(0,10);
  assert.equal(score.evaluate({currency,history,archive,desk,today:old}).score,null);
 }
 const bad=JSON.parse(JSON.stringify(history));bad.USD.net[bad.USD.net.length-1]+=100;
 assert.equal(score.evaluate({currency:'USD',history:bad,archive,desk,today}),null);
 for(const file of ['macro-strength-estimated-v1.js','pair-rankings.js'])assert.doesNotMatch(read('site/fx-quant-v2/next/'+file),/FXQuantPositioningResearchScore/);
 console.log('POSITIONING_RESEARCH_SCORE_G8_PASS');
}

{
 const score=require('../site/fx-quant-v2/next/price-research-score-v1.js');
 const ranker=require('../site/fx-quant-v2/next/pair-rankings.js').currencyRanking;
 const momentum=require('../site/fx-quant-v2/next/currency-strength-reading.js').momentum;
 const prices=JSON.parse(read('live_data/sections/ECB_G8_PRICE_HISTORY.json'));
 const today=prices.last_as_of;
 const FX=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
 const args={prices,today,ranker,momentum};
 const rows=FX.map(currency=>score.evaluate({...args,currency}));
 assert.ok(rows.every(x=>x&&x.score>=0&&x.score<=10&&x.annualizedVolatility>=0&&x.affectsFxRanking===false&&x.eligibleForTrading===false));
 assert.ok(Math.abs(rows.reduce((s,x)=>s+x.score,0)-40)<1e-10);
 for(const x of rows){
  assert.ok(Math.abs(x.acceleration-(x.recent5-x.prior5))<1e-10);
  assert.equal(x.asof,today);
  assert.doesNotMatch(score.render(x,String),/undefined|NaN/);
 }
 const equal={...prices,rows:prices.rows.map(r=>({...r,...Object.fromEntries(FX.map(c=>[c,1]))}))};
 assert.ok(FX.every(currency=>score.evaluate({...args,prices:equal,currency}).score===5));
 const duplicate={...prices,rows:[...prices.rows.slice(0,-1),prices.rows.at(-2)]};
 assert.equal(score.evaluate({...args,prices:duplicate,currency:'USD'}),null);
 const future=new Date(Date.parse(today)+6*864e5).toISOString().slice(0,10);
 assert.equal(score.evaluate({...args,today:future,currency:'USD'}),null);
 assert.equal(score.evaluate({...args,prices:{...prices,source:'other'},currency:'USD'}),null);
 for(const file of ['macro-strength-estimated-v1.js','pair-rankings.js'])assert.doesNotMatch(read('site/fx-quant-v2/next/'+file),/FXQuantPriceResearchScore/);
 console.log('PRICE_RESEARCH_SCORE_G8_PASS');
}

{
 const mod=require('../site/fx-quant-v2/next/global-fx-research-composite-v1.js');
 const currency='USD', flags={affectsFxRanking:false,eligibleForTrading:false};
 const macro={...flags,country:currency,score:7,effectiveCoverage:75};
 const rates={...flags,row:{currency,quality:'UFFICIALE',officialScore:6,score:6}};
 const positioning={...flags,currency,score:4,quality:'ESTIMATED_OI_RESEARCH',asof:'2026-11-17'};
 const price={...flags,currency,score:8,quality:'OFFICIAL_REFERENCE_FIXINGS',asof:'2026-11-26'};
 const args={currency,macro,rates,positioning,price};
 const x=mod.evaluate(args);
 assert.equal(x.baseline.known,90);
 assert.ok(Math.abs(x.baseline.lower-5.7)<1e-9);
 assert.ok(Math.abs(x.baseline.upper-6.7)<1e-9);
 assert.ok(Math.abs(x.baseline.conditional-5.7/.9)<1e-9);
 assert.equal(x.baseline.complete,false);
 assert.equal(x.rank,null);
 assert.equal(x.affectsFxRanking,false);
 assert.equal(x.eligibleForTrading,false);
 assert.equal(x.pointInTimeCertified,false);
 const y=mod.evaluate({...args,rates:{...flags,row:{currency,quality:'SECONDARIA',score:6}}});
 assert.equal(y.baseline.known,60);
 assert.equal(y.indicative.known,90);
 assert.ok(Math.abs(y.indicative.conditional-x.baseline.conditional)<1e-9);
 const z=mod.evaluate({currency});
 assert.equal(z.baseline.known,0);assert.equal(z.baseline.lower,0);assert.equal(z.baseline.upper,10);
 assert.equal(z.baseline.conditional,null);
 const full=mod.evaluate({...args,macro:{...macro,effectiveCoverage:100}});
 assert.equal(full.baseline.complete,true);
 assert.equal(full.baseline.lower,full.baseline.upper);
 for(const a of [x,y,z,full])assert.doesNotMatch(mod.render(a,String),/NaN|undefined/);
 const invalid=mod.evaluate({...args,price:{...price,currency:'EUR'}});
 assert.equal(invalid.baseline.known,75);
 for(const file of ['macro-strength-estimated-v1.js','pair-rankings.js'])assert.doesNotMatch(read('site/fx-quant-v2/next/'+file),/FXQuantGlobalResearchComposite/);
 console.log('GLOBAL_FX_RESEARCH_COMPOSITE_BOUNDS_PASS');
}

{
 const base='../site/fx-quant-v2/next/';
 const mod=require(base+'global-fx-research-composite-v1.js');
 const macro=require(base+'macro-multifactor-shadow-v1.js');
 const cycle=require(base+'recession-traffic-light-v1.js');
 const rates=require(base+'rates-research-score-v1.js');
 const pricing=require(base+'rates-pricing-moves-v1.js');
 const archive=require(base+'rates-pricing-history-v1.js');
 const cot=require(base+'positioning-research-score-v1.js');
 const desk=require(base+'cot-report-reading-v26.js');
 const price=require(base+'price-research-score-v1.js');
 const ranker=require(base+'pair-rankings.js').currencyRanking;
 const momentum=require(base+'currency-strength-reading.js').momentum;
 const load=p=>JSON.parse(read(p)), prefix='site/fx-quant-v2/next/';
 const catalog=load('live_data/sections/MACRO_SERIES.json'),overlay=load(prefix+'semaphore-supplement-v1.json'),observed=load('site/control-room-preview/macro-v3-current-evidence.json'),today=observed.generated_europe_rome_day;
 const rateArgs={pricing,archive,snapshot:load('site/fx-quant-v2/ois-pricing-snapshot.json'),operational:load('live_data/sections/OIS_OPERATIONAL_VIEW.json'),research:load('site/fx-quant-v2/ois-same-contract-repricing-research.json'),nzd:load('live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json'),history:load(prefix+'rates-pricing-history-v1.json'),rates:load('live_data/sections/NATIVE_RATES_DATA.json'),today};
 const cotArgs={history:load('live_data/sections/V250_COT_CHART_DATA.json'),archive:load('site/fx-quant-v2/design-studio-cot-v1-data.json'),desk,today};
 const priceArgs={prices:load('live_data/sections/ECB_G8_PRICE_HISTORY.json'),today,ranker,momentum};
 for(const currency of cycle.coverage){
  const a=macro.evaluate({country:currency,rows:cycle.model(catalog,today,currency,overlay),observed,day:today});
  const b=rates.evaluate({...rateArgs,currency});
  const c=cot.evaluate({...cotArgs,currency});
  const d=price.evaluate({...priceArgs,currency});
  const x=mod.evaluate({currency,macro:a,rates:b,positioning:c,price:d}),e=x.enhanced;
  assert.ok(e.coverage>=0&&e.coverage<=100);
  if(e.complete){
   assert.equal(e.coverage,100);
   assert.ok(e.score>=0&&e.score<=10);
   assert.ok(Math.abs(e.score-e.values.reduce((s,f)=>s+f.weight*f.score/100,0))<1e-10);
   assert.ok(e.estimatedWeight>=15&&e.estimatedWeight<=100);
   assert.ok(e.score>=x.baseline.lower-1e-8&&e.score<=x.baseline.upper+1e-8);
  }else assert.equal(e.score,null);
  assert.equal(x.affectsFxRanking,false);
  assert.doesNotMatch(mod.render(x,String),/NaN|undefined/);
  console.log('ENHANCED_G8',currency,JSON.stringify({score:e.score,coverage:e.coverage,estimatedWeight:e.estimatedWeight,coreCoverage:x.baseline.known,rates:e.rates?.quality,macro:e.macro?.score}));
  const missing=mod.evaluate({currency,macro:a,rates:b,positioning:null,price:d});
  assert.equal(missing.enhanced.score,null);
  assert.ok(missing.enhanced.coverage<=85);
 }
 assert.equal(mod.ratesEnhanced({quality:'NON VERIFICATA'}),null);
 const gov={kind:'GOV_2Y_NOT_OIS',bp:-19,from:'2026-11-18',to:'2026-11-25',source:'Official sovereign curve'};
 assert.equal(mod.ratesEnhanced({quality:'NON VERIFICATA',gov}).score,3.1);
 assert.equal(mod.macroEnhanced({families:[],effectiveCoverage:0}),null);
 assert.equal(mod.evaluate({currency:'USD'}).enhanced.coverage,0);
 console.log('GLOBAL_FX_ENHANCED_COVERAGE_PASS');
}

{
 const rates=require('../site/fx-quant-v2/next/rates-research-score-v1.js');
 const comp=require('../site/fx-quant-v2/next/global-fx-research-composite-v1.js');
 const points=[['2026-11-19',4.58],['2026-11-26',4.48],['2026-11-27',4.515]].map(([date,rate])=>({date,rate,contract:'ZQK2027',source_class:'SECONDARY_SAME_CONTRACT',derived:false}));
 const h={kind:'FUTURES SECONDARI',source:'Secondary dated futures archive',tenors:{'6m':points}};
 const last={asof:'2026-11-27',rate:4.515,contract:'ZQK2027',week:null};
 const r=rates.recentSecondaryWeek(h,last,'2026-11-27');
 assert.equal(r.bp,-10); assert.equal(r.to,'2026-11-26');
 assert.equal(comp.ratesEnhanced({quality:'NON VERIFICATA',asof:last.asof,recentSecondaryWeek:r}).score,3);
 assert.equal(rates.recentSecondaryWeek(h,{...last,rate:4.6},'2026-11-27'),null);
 assert.equal(rates.recentSecondaryWeek(h,{...last,week:{bp:1}},'2026-11-27'),null);
 assert.equal(rates.recentSecondaryWeek(h,last,'2026-12-05'),null);
 assert.equal(rates.recentSecondaryWeek({...h,tenors:{'6m':points.map((p,i)=>i===0?{...p,contract:'ZQJ2027'}:p)}},last,'2026-11-27'),null);
 assert.equal(rates.recentSecondaryWeek({...h,tenors:{'6m':points.map((p,i)=>i===0?{...p,derived:true}:p)}},last,'2026-11-27'),null);
 console.log('ENHANCED_RECENT_EXACT_SECONDARY_WEEK_PASS');
}

{
 const base='../site/fx-quant-v2/next/';
 const position=require(base+'positioning-research-score-v1.js');
 const desk=require(base+'cot-report-reading-v26.js');
 const composite=require(base+'global-fx-research-composite-v1.js');
 const load=p=>JSON.parse(read(p));
 const history=load('live_data/sections/V250_COT_CHART_DATA.json'),archive=load('site/fx-quant-v2/design-studio-cot-v1-data.json');
 const officialOI=load('site/fx-quant-v2/next/cot-official-oi-v1.json');
 for(const currency of Object.keys(history)){
  const last=history[currency].dates.at(-1),args={currency,history,archive,desk,today:last};
  const estimated=position.evaluate(args),observed=position.evaluate({...args,officialOI});
  const row=officialOI.currencies[currency];
  if(officialOI.as_of===last){
   const h=history[currency],n=h.dates.length-1;
   assert.equal(position.officialOpenInterest(officialOI,currency,{date:last,long:h.long[n],short:h.short[n],net:h.net[n],netoi:h.netoi[n]}),row.open_interest);
   if(estimated.score!==null){
    assert.equal(observed.quality,'OFFICIAL_OI_RESEARCH');
    assert.equal(observed.openInterest,row.open_interest);
    assert.ok(Math.abs(observed.flow1-(h.net[n]-h.net[n-1])*100/row.open_interest)<1e-10);
    const a=composite.evaluate({currency,positioning:estimated}).enhanced,b=composite.evaluate({currency,positioning:observed}).enhanced;
    assert.equal(a.estimatedWeight-b.estimatedWeight,15);
    assert.equal(a.coverage,b.coverage);
    assert.match(position.render(observed,String),/OI ufficiale CFTC/);
   }
  }else assert.equal(observed.quality,estimated.quality);
  for(const patch of [{date:'2000-01-01'},{market_code:'000000'},{long:-1},{open_interest:1},{source_url:'https://example.com'}]){
   const bad={...officialOI,currencies:{...officialOI.currencies,[currency]:{...row,...patch}}};
   assert.equal(position.evaluate({...args,officialOI:bad}).quality,estimated.quality);
  }
  assert.equal(position.evaluate({...args,officialOI:{...officialOI,affects_fx_ranking:true}}).quality,estimated.quality);
  console.log('OFFICIAL_OI_G8',currency,JSON.stringify({quality:observed.quality,oi:observed.openInterest,score:observed.score}));
 }
 console.log('OFFICIAL_OI_RESEARCH_CONSUMER_PASS');
}

{
 const html=read('site/fx-quant-v2/next/index.html');
 const nav=html.split('id="nav"',1).length; // preserve existing route IDs and URLs
 const block=html.split('id="nav"')[1].split('</nav>')[0];
 const routes=[...block.matchAll(/data-route="([^"]+)"/g)].map(m=>m[1]);
 assert.equal(routes.length,11);assert.equal(new Set(routes).size,11);
 assert.deepEqual(routes,['overview','macro','banks','rates','currencies','pairs','cot','risk','liquidity','news','library']);
 assert.equal((block.match(/class="nav-heading nav-subheading"/g)||[]).length,7);
 assert.match(app,/homeG8Read\(\)\+homeFxRankStrip\(\)/);
 assert.match(app,/data-control-room-diagnostics/);
 assert.match(app,/officialOI:get\('cotOfficialOI'\)/);
 assert.match(app,/ranker:w.FXQuantPairRankings\?\.currencyRanking/);
 assert.match(app,/composite.evaluate\(\{currency,macro,rates,positioning,price\}\)/);
 console.log('CONTROL_ROOM_SEVEN_AREAS_AND_REUSED_RESEARCH_PASS');
}

{
 const base='site/fx-quant-v2/next/';
 const cb=read(base+'central-bank-studio.js'),rates=read(base+'rates-studio.js');
 const cr=cb.slice(cb.indexOf(' function render(api)'));
 assert(cr.indexOf('WANT · COSA COMUNICA')<cr.indexOf('drivers-bank-sources'));
 assert(cr.indexOf('CAN · MARGINE DI MANOVRA')<cr.indexOf('drivers-bank-sources'));
 const rr=rates.slice(rates.lastIndexOf(' function render(){'));
 assert(rr.indexOf('rates-jumps')<rr.indexOf('renderOverview')&&rr.indexOf('renderOverview')<rr.indexOf('rates-hero'));
 assert(rr.indexOf('id="rates-expected"')<rr.indexOf('id="rates-government"'));
 assert(rr.indexOf('id="rates-government"')<rr.indexOf('id="rates-fx"'));
 assert.match(rr,/data-rates-openbank/);
 assert.match(app,/state.cbCcy=bankFromRates.dataset.ratesOpenbank/);
 console.log('MONETARY_POLICY_RATES_HIERARCHY_PASS');
}

{
 const base='site/fx-quant-v2/next/';
 const cs=read(base+'currency-studio.js'),cot=read(base+'cot-studio.js');
 assert(cs.indexOf('data-fx-enhanced-summary')<cs.indexOf('class="strength-quant-fold"'));
 assert(cs.indexOf('class="strength-quant-fold"')<cs.indexOf('FXQuantGlobalResearchComposite?.render(composite,esc)'));
 assert(app.indexOf('class="pairs-three-answers"')<app.indexOf('class="pairs-optional-panel pairs-evidence"'));
 assert.match(cot,/Storico delle rilevazioni e metodo COT/);
 console.log('FOREX_RESEARCH_HIERARCHY_PASS');
}

{
 const liq=read('site/fx-quant-v2/next/liquidity-credit-studio.js');
 assert.match(app,/class="risk-next-step"/);
 assert.match(app,/href="\.\.\/cross-asset\.html"/);
 assert.match(liq,/Gli spread IG\/HY misurano il rischio di mercato, non gli standard dei prestiti bancari/);
 assert.match(liq,/Verifica dati, copertura e fonti bancarie/);
 console.log('CROSS_ASSET_BANK_CREDIT_SEPARATION_PASS');
}

{
 const lib=read('site/fx-quant-v2/next/research-library.js');
 assert.match(app,/id="desk-calendar" tabindex="-1"/);
 assert.match(app,/id="desk-news" tabindex="-1"/);
 assert(app.indexOf('id="desk-calendar"')<app.indexOf('id="desk-news"'));
 assert.match(lib,/<details class="rl-disclaimer"><summary>Stato delle pubblicazioni/);
 assert.match(lib,/id="library-summary"/);
 assert.match(lib,/latestPerType/);
 console.log('EVENTS_LIBRARY_HIERARCHY_PASS');
}
