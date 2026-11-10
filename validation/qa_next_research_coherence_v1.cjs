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
function evaluate(data,now='2026-11-10'){
 const ctx={
  get:k=>data[k]||null,finite,validDay,esc,date,fmt,sign,
  dayNow:()=>now,
  fresh:(d,window=8)=>validDay(d)&&d<=now&&
    (Date.parse(now+'T12:00:00Z')-Date.parse(d+'T12:00:00Z'))/864e5<=window,
  eurPairs:()=>data.pairs?.pairs||{},
  getPairName:key=>key.slice(0,3)+'/'+key.slice(3),
  homeScreenChart:()=>'<div class="test-chart"></div>',
  state:{homeEvidenceOpen:false,homeDossierOpen:false},
  FX:['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'],
  FLAGS:{USD:'USD',EUR:'EUR',GBP:'GBP',JPY:'JPY',CHF:'CHF',AUD:'AUD',NZD:'NZD',CAD:'CAD'},
  ROUTES:{rates:'Tassi & OIS',risk:'Rischio'}
 };
 vm.createContext(ctx);
 new vm.Script(functions+'\nvar qa={context:researchCase(),article:overview(),rates:researchBridge("rates"),risk:researchBridge("risk")};').runInContext(ctx,{timeout:1000});
 return ctx.qa;
}
const baseline=evaluate(initial);
assert.match(baseline.article,/class="market-letter market-dashboard"/);
assert.match(baseline.article,/class="letter-evidence"/);
assert.match(baseline.article,/class="dashboard-kpi-grid"/);
assert.match(baseline.article,/class="dashboard-analysis"/);
assert.match(baseline.article,/LA LETTURA FX DEL DESK/);
assert.match(baseline.article,/NZD/);
assert.match(baseline.article,/CHF/);
assert.match(baseline.article,/AUD/);
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
assert.match(baseline.article,/USD\/JPY/);
const forexOpening=baseline.article.split('<details class="dashboard-technical"')[0];
assert(forexOpening.includes('FX G8'),'Fallback Home must remain oriented toward currencies');
if(forexOpening.includes('VIX'))
 assert(forexOpening.indexOf('FX G8')<forexOpening.indexOf('VIX'),'Fallback Home cannot lead with VIX');

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
assert.match(x.article,/NZD/,'A risk shock cannot replace G8 currency analysis');
assert.match(x.article,/CHF/);
assert.equal(x.context.focus,'nasdaq');
assert.match(x.article,/data-research-kind="stress"/);
assert.match(x.article,/Il mio giudizio\./,'The Home needs an explicit market verdict');
assert.match(x.article,/disoccupazione/,'The Home must connect macro to the market narrative');
assert.match(x.article,/EUR\/USD/,'The Home must connect FX pairs to the market narrative');
assert.match(x.article,/USD\/JPY/,'The Home must surface price-vs-thesis divergence');
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
const relief=clone(stress);
relief.risk.streams.NASDAQCOM.change_1d_pct=3.2;
relief.risk.streams.VIX.previous=31;relief.risk.streams.VIX.value=23;
relief.risk.streams.HY_OAS.previous=3.45;relief.risk.streams.HY_OAS.value=3.13;
x=evaluate(relief,'2026-11-10');
assert.equal(x.context.kind,'relief');
assert.match(x.article,/La distensione sarebbe fragile/);
const bond=clone(initial);
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
malicious.pairs.pairs.EURUSD.decision_frame.relation='<img src=x onerror=alert(1)>';
const html=evaluate(malicious).article;
assert(html.includes('&lt;img'));
assert(!html.includes('<img'));
const stale=evaluate(initial,'2026-12-01');
assert.match(stale.article,/fotografia storica/,'FX source age must be explicit');
assert.match(app,/state\.data=nextData/);
assert.match(app,/cache:'no-store'/);
assert.match(app,/visibilitychange/);
const page=read('site/fx-quant-v2/next/index.html');
assert.match(page,/editorial-v4\.css\?v=18/);
assert.match(page,/app\.js\?v=18/);
console.log('NEXT_RESEARCH_COHERENCE_FX_FIRST_PASS: regimes=stress,relief,yield-selloff,fx-divergence,mixed; matched evidence; fresh/stale/missing; XSS; page continuity; cache refresh');
