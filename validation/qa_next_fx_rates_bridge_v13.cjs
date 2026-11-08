'use strict';
/* Next V13: 2Y sovereign-vs-FX matched-date observations, NOT historical OIS. */
const fs=require('node:fs'),assert=require('node:assert/strict');
const {snapshot,commonObservations,metrics,brief,build}=require('../site/fx-quant-v2/next/fx-rates-bridge.js');
const json=s=>JSON.parse(fs.readFileSync(s,'utf8'));
const rates=json('live_data/sections/NATIVE_RATES_DATA.json');
const prices=json('live_data/sections/ECB_G8_PRICE_HISTORY.json');
const pairs=json('live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json');
const today='2026-11-08',asof=pairs.price_asof;

const unfav=brief(snapshot(rates,prices,'AUDCAD',asof,today));
assert.equal(unfav.ready,false,'Sparse dated AUD rates must be withheld in short verdict');
assert.equal(unfav.tone,'unavailable');

const eu=snapshot(rates,prices,'EURUSD',asof,today);
const ca=snapshot(rates,prices,'USDCAD',asof,today);
assert(eu.ready&&ca.ready,'Official USD EUR CAD 2Y and ECB daily common observations should validate');
assert.equal(eu.latest.date,'2026-11-05');
assert.equal(eu.lag,1,'Never imply the Nov 06 FX fixing was matched to Nov 05 rates');
assert.equal(eu.short.n,5);
assert.equal(eu.short.days,7);
assert.equal(eu.short.direction,'STESSO SEGNO');
assert.equal(eu.medium.direction,'SEGNO OPPOSTO');
assert.equal(eu.medium.days,41);
assert.equal(ca.short.direction,'SEGNO OPPOSTO');
assert.equal(ca.medium,null,'USDCAD missing consistent 20-session calendar must be withheld');
assert(Math.abs(eu.short.spreadBp-10.04002386000002)<1e-7,'EURUSD 2Y spread change exact');
assert(Math.abs(eu.short.fxPct-0.8445642407906684)<1e-7,'EURUSD matched-date FX return exact');
assert(Math.abs(ca.short.spreadBp-4)<1e-8,'USDCAD 2Y differential change exact');
const paired=commonObservations(rates,prices,'EURUSD',asof,today);
assert(paired.length>200);
for(const r of paired){
 assert(r.date<=asof&&r.date<=rates.EUR.date&&r.date<=rates.USD.date&&r.date<=prices.last_as_of,'Forward-dated observation leaked');
 assert(Number.isFinite(r.spread)&&Number.isFinite(r.spot));
}
const latestRow=prices.rows.find(r=>r.Date===eu.latest.date);
assert(latestRow&&Math.abs(eu.latest.spread-(rates.EUR['2Y']-rates.USD['2Y'])*100)<1e-7);
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
assert.equal(lastAfter.date,'2026-11-05','Post-snapshot FX observation must be rejected');
const badRate=JSON.parse(JSON.stringify(rates));
badRate.EUR.history2.dates.push('2026-11-09');
badRate.EUR.history2.values.push(50);
assert.equal(commonObservations(badRate,prices,'EURUSD',asof,today).at(-1).date,'2026-11-05');
const sign=(v,n=1,s='')=>Number.isFinite(v)?(v>0?'+':v<0?'−':'')+Math.abs(v).toFixed(n)+s:'—';
const fmt=(v,n=2)=>Number.isFinite(v)?v.toFixed(n):'—';
const date=v=>v||'n.d.';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let charts=0,lastChart=null;
const base={get:k=>({rates,currencyPrices:prices,pairs})[k],state:{pair:'EURUSD',pairPriceWindow:60},plot:o=>{charts++;lastChart=o;return '<div class="chart fixture"><svg role="img"></svg></div>'},sign,fmt,date,esc,dayNow:()=>today};
const html=build(base).render();
assert.equal(charts,1);
assert.equal(lastChart.lines.length,1);
assert.equal(lastChart.lines[0].name,'EUR 2Y − USD 2Y');
assert.equal(lastChart.lines[0].values.at(-1).label,'2026-11-05');
assert.equal(lastChart.unit,' bp');
assert.match(html,/data-rate-asof="2026-11-05"/);
assert.match(html,/data-horizon="5"/);
assert.match(html,/data-horizon="20"/);
assert.match(html,/Segnali diversi tra breve e medio periodo/);
assert.match(html,/NON è stato abbinato a un tasso di un altro giorno/);
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
const injected=build({...base,get:k=>({rates:malicious,currencyPrices:prices,pairs})[k]}).render();
assert(injected.includes('&lt;img')&&!injected.includes('<img'),'Untrusted source strings must be escaped');

const eurBrief=brief(eu),cadBrief=brief(ca);
assert(eurBrief.ready&&cadBrief.ready);
assert.equal(eurBrief.asof,'2026-11-05');
assert.equal(eurBrief.tone,'mixed','5 common intervals concordant but 20 discordant');
assert.match(eurBrief.label,/5 intervalli concordi · 20 discordi/);
assert.equal(cadBrief.tone,'divergent','5-step USD/CAD should differ, 20 unavailable');
assert.match(cadBrief.label,/5 intervalli discordi · 20 non verificabili/);
const pairModule=require('../site/fx-quant-v2/next/decision-journey.js');
const fxModel=pairModule.build({
 ...base,
 get:k=>({rates,currencyPrices:prices,pairs})[k],
 state:{pair:'EURUSD',pairPriceWindow:60,pairShowReferences:true}
});
const home=fxModel.overview(),dossier=fxModel.pair();
assert.match(home,/data-rates-tone="mixed"/);
assert.match(home,/data-rates-tone="divergent"/);
assert.match(home,/GOV 2Y, non OIS/);
assert.match(home,/05\/11\/2026|2026-11-05/,'Rates brief must carry matched date');
assert.match(dossier,/decision-gate-rates/);
assert.match(dossier,/5 intervalli concordi/);
assert.match(dossier,/20 discordi/);
assert.match(dossier,/TRADE ATTRACTIVENESS/);
assert.match(dossier,/Non stiamo confrontando curve OIS/);
const audModel=pairModule.build({
 ...base,get:k=>({rates,currencyPrices:prices,pairs})[k],
 state:{pair:'AUDCAD',pairPriceWindow:60}
});
assert.match(audModel.pair(),/2Y governativi non verificabili/);
assert.doesNotMatch(audModel.pair(),/data-rates-tone="mixed"/);
const noRateHome=pairModule.build({
 ...base,get:k=>({currencyPrices:prices,pairs})[k],
 state:{pair:'EURUSD',pairPriceWindow:60}
}).overview();
assert.match(noRateHome,/2Y governativi non verificabili/);
assert.doesNotMatch(noRateHome,/data-rates-tone="mixed"/);

const model=fs.readFileSync('site/fx-quant-v2/next/decision-journey.js','utf8');
const page=fs.readFileSync('site/fx-quant-v2/next/index.html','utf8');
assert(model.includes('FXQuantRatesBridge')&&model.includes('ratesEvidence'),'Pair dossier must integrate rates comparison');
const dossierFn=model.slice(model.indexOf('  function pair(){'),model.indexOf('  return {overview,pair,data};'));
assert(!/\bconst window\s*=/.test(dossierFn),'A local window variable hides global browser module access');
assert(dossierFn.includes('const chartWindow='),'Price chart lookback must not shadow the Window global');
assert(page.includes('fx-rates-bridge.js?v=14'));
assert(page.indexOf('fx-rates-bridge.js?v=14')<page.indexOf('decision-journey.js?v=14'));
assert(page.includes('editorial-v4.css?v=14'));
console.log('NEXT_V14_FX_RATES_PASS: common observation dates, 5/20 horizons, sovereign 2Y versus FX, basis risk, no OIS fiction');
