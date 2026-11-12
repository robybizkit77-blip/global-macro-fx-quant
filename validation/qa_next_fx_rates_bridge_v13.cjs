'use strict';
/* Next V13: 2Y sovereign-vs-FX matched-date observations, NOT historical OIS. */
const fs=require('node:fs'),assert=require('node:assert/strict');
const {snapshot,commonObservations,metrics,brief,build}=require('../site/fx-quant-v2/next/fx-rates-bridge.js');
const json=s=>JSON.parse(fs.readFileSync(s,'utf8'));
const rates=json('live_data/sections/NATIVE_RATES_DATA.json');
const prices=json('live_data/sections/ECB_G8_PRICE_HISTORY.json');
const pairs=json('live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json');
// Archived Nov 06 as-of fixture stays fixed while the live market calendar advances.
const today='2026-11-08',asof='2026-11-06';
const fixturePairs={...pairs,price_asof:asof};

const unfav=brief(snapshot(rates,prices,'AUDCAD',asof,today));
assert.equal(unfav.ready,false,'Sparse dated AUD rates must be withheld in short verdict');
assert.equal(unfav.tone,'unavailable');

const eu=snapshot(rates,prices,'EURUSD',asof,today);
const ca=snapshot(rates,prices,'USDCAD',asof,today);
assert(eu.ready&&ca.ready,'Official USD EUR CAD 2Y and ECB daily common observations should validate');
assert.equal(eu.latest.date,'2026-11-06');
assert.equal(eu.lag,0,'Archived Nov 06 fixing must join with Nov 06 rates');
assert.equal(eu.short.n,5);
assert.equal(eu.short.days,7);
assert.equal(eu.short.direction,'STESSO SEGNO');
assert.equal(eu.medium.direction,'SEGNO OPPOSTO');
assert.equal(eu.medium.days,39);
assert.equal(ca.short.direction,'STESSO SEGNO');
assert.equal(ca.medium,null,'USDCAD missing consistent 20-session calendar must be withheld');
// Exact common-date arithmetic, independently computed from start/end market observations.
for(const record of [eu,ca]){
 const first=record.rows.at(-6),last=record.rows.at(-1);
 assert(first&&last&&record.short,'Five genuine common intervals required');
 assert(Math.abs(record.short.fxPct-(last.spot/first.spot-1)*100)<1e-9,'FX return must use common endpoints');
 assert(Math.abs(record.short.spreadBp-(last.spread-first.spread))<1e-9,'2Y spread change must use common endpoints');
 assert.equal(record.short.end,record.latest.date,'Short horizon must end at latest actual common date');
}
const paired=commonObservations(rates,prices,'EURUSD',asof,today);
assert(paired.length>200);
for(const r of paired){
 assert(r.date<=asof&&r.date<=rates.EUR.date&&r.date<=rates.USD.date&&r.date<=prices.last_as_of,'Forward-dated observation leaked');
 assert(Number.isFinite(r.spread)&&Number.isFinite(r.spot));
}
const latestRow=prices.rows.find(r=>r.Date===eu.latest.date);
const yieldAt=(ccy,day)=>{const h=rates[ccy].history2,i=h.dates.indexOf(day);assert(i>=0,'Historical rate date missing: '+ccy);return h.values[i]};
assert(latestRow&&Math.abs(eu.latest.spread-(yieldAt('EUR',eu.latest.date)-yieldAt('USD',eu.latest.date))*100)<1e-7);
assert(Math.abs(eu.latest.spot-latestRow.USD/latestRow.EUR)<1e-9);
assert(!snapshot(rates,prices,'AUDCAD',asof,today).ready,'Weekly AUD rates must not be passed off as daily five-session evidence');
assert(!snapshot(rates,prices,'EURCHF',asof,today).ready,'CHF rates stale despite FX having latest prices');
assert(!snapshot(rates,prices,'NZDUSD',asof,today).ready,'NZD rates stale despite FX having latest prices');
assert(snapshot(rates,prices,'EURGBP',asof,today).ready,'FX/rates comparison does not require a structural trade favourite');
assert(!snapshot(rates,prices,'EURUSD',asof,'2027-01-01').ready,'Stale joined data must be hidden');
assert(!snapshot(rates,{},'EURUSD',asof,today).ready,'No ECB price data, no inference');
assert(!snapshot({},prices,'EURUSD',asof,today).ready,'No 2Y data, no inference');
const estimated=JSON.parse(JSON.stringify(rates));
estimated.USD.quality='STIMA';
assert(!snapshot(estimated,prices,'EURUSD',asof,today).ready,'Estimated 2Y should not look like official data');
const later=JSON.parse(JSON.stringify(prices));
later.rows.push({...later.rows.at(-1),Date:'2026-11-09',USD:9});
const lastAfter=commonObservations(rates,later,'EURUSD',asof,today).at(-1);
assert.equal(lastAfter.date,'2026-11-06','Post-snapshot fixing must be excluded');
const badRate=JSON.parse(JSON.stringify(rates));
badRate.EUR.history2.dates.push('2026-11-09');
badRate.EUR.history2.values.push(50);
assert.equal(commonObservations(badRate,prices,'EURUSD',asof,today).at(-1).date,'2026-11-06');
const sign=(v,n=1,s='')=>Number.isFinite(v)?(v>0?'+':v<0?'−':'')+Math.abs(v).toFixed(n)+s:'—';
const fmt=(v,n=2)=>Number.isFinite(v)?v.toFixed(n):'—';
const date=v=>v||'n.d.';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let charts=0,lastChart=null;
const base={get:k=>({rates,currencyPrices:prices,pairs:fixturePairs})[k],state:{pair:'EURUSD',pairPriceWindow:60},plot:o=>{charts++;lastChart=o;return '<div class="chart fixture"><svg role="img"></svg></div>'},sign,fmt,date,esc,dayNow:()=>today};
const html=build(base).render();
assert.equal(charts,1);
assert.equal(lastChart.lines.length,1);
assert.equal(lastChart.lines[0].name,'EUR 2Y − USD 2Y');
assert.equal(lastChart.lines[0].values.at(-1).label,'2026-11-06');
assert.equal(lastChart.unit,' bp');
assert.match(html,/data-rate-asof="2026-11-06"/);
assert.match(html,/data-horizon="5"/);
assert.match(html,/data-horizon="20"/);
assert.match(html,/Segnali diversi tra breve e medio periodo/);
assert.doesNotMatch(html,/NON è stato abbinato a un tasso di un altro giorno/,'No mismatch warning when matched date equals fixing date');
assert.match(html,/non OIS/);
assert.match(html,/non inferiamo che i tassi causino/);
assert.match(html,/spot|zero-coupon/,'Different rate benchmarks must be caveated');
base.state.pair='USDCAD';
const cadHtml=build(base).render();
assert.match(cadHtml,/data-horizon="5"/);
assert.doesNotMatch(cadHtml,/data-horizon="20"/);
assert.match(cadHtml,/osservazioni troppo rade/);
base.state.pair='AUDCAD';
const audHtml=build(base).render();
assert.match(audHtml,/storico troppo discontinuo/i);
assert.doesNotMatch(audHtml,/<svg/,'No invalid AUD rates chart should render');
base.state.pair='EURCHF';
assert.match(build(base).render(),/troppo vecchia/i);
const malicious=JSON.parse(JSON.stringify(rates));
malicious.USD.source='<img src=x onerror=alert(1)>';
base.state.pair='EURUSD';
const injected=build({...base,get:k=>({rates:malicious,currencyPrices:prices,pairs:fixturePairs})[k]}).render();
assert(injected.includes('&lt;img')&&!injected.includes('<img'),'Untrusted source strings must be escaped');

const eurBrief=brief(eu),cadBrief=brief(ca);
assert(eurBrief.ready&&cadBrief.ready);
assert.equal(eurBrief.asof,'2026-11-06');
assert.equal(eurBrief.tone,'mixed','5 common intervals concordant but 20 discordant');
assert.match(eurBrief.label,/5 intervalli concordi · 20 discordi/);
assert.equal(cadBrief.tone,'aligned','Five intervals aligned in archived USD/CAD fixture');
assert.match(cadBrief.label,/5 intervalli concordi · 20 non verificabili/);
const pairModule=require('../site/fx-quant-v2/next/decision-journey.js');
const fxModel=pairModule.build({
 ...base,
 get:k=>({rates,currencyPrices:prices,pairs:fixturePairs})[k],
 state:{pair:'EURUSD',pairPriceWindow:60,pairShowReferences:true}
});
const home=fxModel.overview(),dossier=fxModel.pair();
assert.match(dossier,/data-rates-tone="mixed"/,'EUR/USD dossier must preserve mixed short/medium 2Y evidence even if not shortlisted');
assert.match(home,/data-rates-tone="aligned"/);
assert.match(home,/GOV 2Y, non OIS/);
assert.match(home,/06\/11\/2026|2026-11-06/,'Rates brief must carry matched date');
assert.match(dossier,/decision-gate-rates/);
assert.match(dossier,/5 intervalli concordi/);
assert.match(dossier,/20 discordi/);
assert.match(dossier,/TRADE ATTRACTIVENESS/);
assert.match(dossier,/Non stiamo confrontando curve OIS/);
const audModel=pairModule.build({
 ...base,get:k=>({rates,currencyPrices:prices,pairs:fixturePairs})[k],
 state:{pair:'AUDCAD',pairPriceWindow:60}
});
assert.match(audModel.pair(),/2Y governativi non verificabili/);
assert.doesNotMatch(audModel.pair(),/data-rates-tone="mixed"/);
const noRateHome=pairModule.build({
 ...base,get:k=>({currencyPrices:prices,pairs:fixturePairs})[k],
 state:{pair:'EURUSD',pairPriceWindow:60}
}).overview();
assert.match(noRateHome,/2Y governativi non verificabili/);
assert.doesNotMatch(noRateHome,/data-rates-tone="mixed"/);

// Explicit Nov 09 lag fixture: do not pair the Nov 09 FX fixing with Nov 06 sovereign rates.
const lagRates=JSON.parse(JSON.stringify(rates));
lagRates.EUR.date='2026-11-06';lagRates.USD.date='2026-11-06';
const lagPairs={...fixturePairs,price_asof:'2026-11-09'};
const lag=snapshot(lagRates,prices,'EURUSD',lagPairs.price_asof,lagPairs.price_asof);
assert(lag.ready&&lag.latest.date==='2026-11-06'&&lag.lag===3,'Dated mismatch must be preserved');
const lagHtml=build({...base,get:k=>({rates:lagRates,currencyPrices:prices,pairs:lagPairs})[k],state:{pair:'EURUSD',pairPriceWindow:60},dayNow:()=>lagPairs.price_asof}).render();
assert.match(lagHtml,/NON è stato abbinato a un tasso di un altro giorno/,'Lag disclaimer required');

// Production snapshot: market dates advance; verify actual overlap and fail-closed gating.
const liveAsOf=pairs.price_asof;
assert(/^\d{4}-\d{2}-\d{2}$/.test(liveAsOf),'Live model as-of date missing');
for(const pair of ['EURUSD','USDCAD','EURGBP','AUDCAD','EURCHF','NZDUSD']){
 const joined=commonObservations(rates,prices,pair,liveAsOf,liveAsOf);
 const observed=snapshot(rates,prices,pair,liveAsOf,liveAsOf);
 assert.deepEqual(observed.latest,joined.at(-1),'Latest shared date must come from observed data: '+pair);
 assert(joined.every(x=>x.date<=liveAsOf&&x.date<=rates[pair.slice(0,3)].date&&x.date<=rates[pair.slice(3)].date),
   'Forward-dated or cross-date observations are not valid: '+pair);
 if(observed.ready){
  assert(observed.lag>=0&&observed.lag<=3&&observed.age>=0&&observed.age<=5&&observed.short,
   'Current FX/2Y was promoted despite stale or insufficient observations: '+pair);
  assert(brief(observed).ready,'Valid matched-date brief should be available: '+pair);
 }else assert.equal(brief(observed).ready,false,'Unavailable FX/2Y must stay unavailable: '+pair);
}
const model=fs.readFileSync('site/fx-quant-v2/next/decision-journey.js','utf8');
const page=fs.readFileSync('site/fx-quant-v2/next/index.html','utf8');
assert(model.includes('FXQuantRatesBridge')&&model.includes('ratesEvidence'),'Pair dossier must integrate rates comparison');
const dossierFn=model.slice(model.indexOf('  function pair(){'),model.indexOf('  return {overview,pair,data};'));
assert(!/\bconst window\s*=/.test(dossierFn),'A local window variable hides global browser module access');
assert(dossierFn.includes('const chartWindow='),'Price chart lookback must not shadow the Window global');
assert(page.includes('fx-rates-bridge.js?v=17'));
assert(/decision-journey\.js\?v=[\w.-]+/.test(page)&&
 page.indexOf('fx-rates-bridge.js')<page.indexOf('decision-journey.js'),
 'Rates bridge must load before the versioned decision engine');
assert(page.includes('editorial-v4.css?v=18'));
console.log('NEXT_V14_FX_RATES_PASS: frozen Nov 06 matched-date fixture, live date gating, sovereign 2Y versus FX, no OIS fiction');
