'use strict';
/* Standalone visual/functional smoke test for isolated FX Quant NEXT preview.
 * Never mutates the operational FX V2 or any core data.
 */
const fs=require('fs');
const assert=require('assert');
const {chromium}=require('playwright');
const BASE=process.env.FXQN_BASE||'http://127.0.0.1:8000/site/fx-quant-v2/next/index.html';
const ROUTES=['overview','currencies','pairs','macro','rates','cot','risk','news'];
const evidence='fxquant-next-browser-evidence';
fs.mkdirSync(evidence,{recursive:true});
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const results=[];
 try{
  for(const width of [1440,390]){
   const page=await browser.newPage({viewport:{width,height:900},deviceScaleFactor:1});
   const errors=[];
   page.on('pageerror',e=>errors.push(String(e)));
   const resp=await page.goto(BASE,{waitUntil:'domcontentloaded',timeout:25000});
   assert(resp&&resp.ok(),'Home HTTP failed: '+resp?.status());
   await page.waitForFunction(()=>/fonti caricate/.test(document.getElementById('sidebar-feed')?.textContent||''),{timeout:20000});
   const sourceText=await page.locator('#sidebar-feed').innerText();
   assert(/14\/14 fonti caricate/.test(sourceText),'Feed mismatch: '+sourceText);
   for(const route of ROUTES){
    await page.evaluate(r=>{location.hash='#'+r},route);
    await page.waitForFunction(r=>document.querySelector('#crumb-page')?.textContent===({overview:'Panoramica',currencies:'Valute G8',pairs:'Coppie FX',macro:'Macro Lab',rates:'Tassi & OIS',cot:'Positioning',risk:'Risk Radar',news:'News Pulse'})[r],route);
    const h1=await page.locator('main h1').first().innerText();
    assert(h1.length>12,'Missing heading '+route);
    const overflow=await page.evaluate(()=>({scroll:document.documentElement.scrollWidth,client:document.documentElement.clientWidth}));
    assert(overflow.scroll<=overflow.client+2,'Horizontal overflow on '+route+' '+width+': '+JSON.stringify(overflow));
    await page.screenshot({path:evidence+'/'+route+'-'+width+'.png',fullPage:route==='overview'||route==='pairs'||route==='cot'||route==='rates'||route==='macro'||route==='currencies'});
    results.push({width,route,h1,overflow:'PASS'});
   }

   // NEXT EDITION: evidence-led market map, data theatre and cross-market navigation.
   await page.evaluate(()=>{location.hash='#overview'});
   await page.locator('[data-atlas="fx"]').click();
   assert((await page.locator('.lens-article h3').innerText()).includes('dollaro'),'Market atlas did not switch to FX evidence');
   await page.locator('[data-atlas="risk"]').click();
   assert((await page.locator('.lens-article').innerText()).includes('VIX'),'Market atlas risk narrative missing');
   await page.locator('[data-hchart="vix"]').click();
   assert((await page.locator('.theatre-chart .chart-legend').innerText()).includes('VIX'),'Market chart explorer did not switch to VIX');
   await page.locator('[data-hwindow="5"]').click();
   assert(await page.locator('.theatre-chart .chart svg').count()>0,'Market chart 5 observations missing');
   await page.locator('[data-home-pair="AUDCAD"]').click();
   assert((await page.locator('.fx-focus-story h3').innerText()).includes('AUD/CAD'),'FX workbench does not switch the selected pair');
   await page.locator('#quicklaunch').click();
   assert(await page.locator('#quick-layer').evaluate(el=>el.classList.contains('open')),'Quick search did not open');
   await page.locator('#quick-input').fill('EURGBP');
   await page.locator('[data-command="pair:EURGBP"]').click();
   assert((await page.locator('#crumb-page').innerText())==='Coppie FX','Quick search failed to navigate to pair dossier');
   assert((await page.locator('.focus-headline').first().innerText()).includes('EUR/GBP'),'Quick search did not update selected pair');
   // The FX selector changes the deep dive and the watchlist is interactive.
   await page.evaluate(()=>{location.hash='#pairs'});
   await page.locator('[data-pair="AUDCAD"]').click();
   assert((await page.locator('.focus-headline').first().innerText()).includes('AUD/CAD'),'Pair select failed');
   await page.locator('[data-watch="AUDCAD"]').click();
   assert((await page.locator('[data-watch="AUDCAD"]').innerText()).includes('Nella watchlist'),'Watchlist failed');

   // COUNTRY RESEARCH STUDIO: true ECB 561-session history, 7 comparable crosses,
   // synchronized government differentials, COT, macro and forward price tenors.
   await page.evaluate(()=>{location.hash='#currencies'});
   assert(await page.locator('.cs-country').count()===8,'Country G8 selector incomplete');
   assert((await page.locator('.cs-sourceband').innerText()).includes('05/11/2026'),'ECB last fixing date missing');
   assert(await page.locator('.cs-pair-table tbody tr').count()===7,'Seven FX counterparts missing');
   assert(await page.locator('.cs-two-charts .chart svg').count()===2,'FX and sovereign charts missing');
   assert(await page.locator('.cs-evidence-grid .chart svg').count()===2,'Macro and COT charts missing');
   assert(await page.locator('.cs-tenor-table tbody tr').count()===3,'Monetary pricing audit missing 3M/6M/12M');
   assert(await page.locator('.cs-story-grid article').count()===4,'Country research narrative incomplete');
   const usdQuote=await page.locator('.cs-hero-fx>b').innerText();
   assert(+usdQuote.replace(',','.')>0.85&&+usdQuote.replace(',','.')<1,'USD/EUR inverted FX quotation');
   await page.locator('[data-cs-country="EUR"]').click();
   assert((await page.locator('.cs-hero-fx>strong').innerText())==='EUR/USD','EUR USD pair cross derivation failed');
   const eurQuote=await page.locator('.cs-hero-fx>b').innerText();
   assert(+eurQuote.replace(',','.')>1.1&&+eurQuote.replace(',','.')<1.2,'EUR/USD ECB history cross rate incorrect');
   await page.locator('#cs-other').selectOption('JPY');
   assert((await page.locator('.cs-chart-head').first().innerText()).includes('EUR/JPY'),'Pair countercurrency did not update FX chart');
   await page.locator('[data-cs-pricewindow="20"]').click();
   assert(await page.locator('.cs-two-charts .chart').first().count()===1,'FX price window switch failed');
   await page.locator('[data-cs-ratesmode="curve"]').click();
   assert((await page.locator('.cs-two-charts .chart-legend').last().innerText()).includes('10Y'),'2Y and 10Y chart switch failed');
   await page.locator('[data-cs-macro="labour"]').click();
   assert((await page.locator('.cs-evidence-grid .chart-legend').first().innerText()).includes('Disoccupazione'),'Unemployment chart switch failed');
   await page.locator('[data-cs-cotwindow="52"]').click();
   assert((await page.locator('.cs-evidence-grid .chart-legend').last().innerText()).includes('Net long'),'COT 52W control failed');
   await page.locator('.cs-pair-table [data-cs-other="CHF"]').click();
   assert((await page.locator('.cs-hero-fx>strong').innerText())==='EUR/CHF','Seven counterpart comparison did not update selection');
   await page.locator('.cs-pair-table [data-cs-openpair="EURCHF"]').click();
   assert((await page.locator('#crumb-page').innerText())==='Coppie FX','Deep Dive link did not navigate');
   assert((await page.locator('.focus-headline').first().innerText()).includes('EUR/CHF'),'Deep Dive did not select correct canonical pair');
   await page.evaluate(()=>{location.hash='#currencies'});
   await page.locator('[data-cs-country="CHF"]').click();
   assert((await page.locator('.cs-sourceband').innerText()).includes('30/09/2026'),'CHF stale benchmark not visible');
   await page.locator('[data-cs-country="NZD"]').click();
   assert((await page.locator('.cs-sourceband').innerText()).includes('16/10/2026'),'NZD old government data not visible');
   assert((await page.locator('.cs-policy-status').innerText()).includes('PROXY'),'NZD rate pricing estimate not identified');
   assert(await page.locator('.cs-pair-table tbody tr').count()===7,'NZD seven-currency FX comparator not loaded');
   // Rates & OIS research: eight currencies, actual sovereign histories and source-specific tenor pricing.
   await page.evaluate(()=>{location.hash='#rates'});
   await page.locator('[data-rate-ccy="USD"]').first().click(); // isolate against prior NZD country selection
   assert(await page.locator('.rates-country').count()===8,'G8 rate countries incomplete');
   assert(await page.locator('.rates-shape-col').count()===3,'3M/6M/12M bars missing');
   assert(await page.locator('.rates-universe-table tbody tr').count()===8,'G8 pricing table incomplete');
   assert(await page.locator('.rates-primary-plot .chart svg').count()>0,'Rates yield chart absent');
   assert(await page.locator('.rates-spread .chart svg').count()>0,'Synchronized FX sovereign spread chart absent');
   const usdWarning=await page.locator('.rates-reprice').innerText();
   assert(usdWarning.includes('non le variazioni storiche 1D/1W'),'USD unavailable repricing not disclosed');
   assert((await page.locator('.rates-figure').innerText()).includes('DATE MISTE'),'Mixed-date USD pricing incorrectly looks simultaneous');
   await page.locator('[data-rs-window="20"]').click();
   assert(await page.locator('.rates-primary-plot .chart svg').count()>0,'Rates 20-day selector failed');
   await page.locator('[data-rs-gov="10y"]').click();
   assert((await page.locator('.rates-primary-plot .chart-legend').innerText()).includes('10Y'),'Rate 10Y mode failed');
   await page.locator('[data-rs-gov="slope"]').click();
   assert((await page.locator('.rates-primary-plot .chart-legend').innerText()).includes('10Y − 2Y'),'Curve slope mode failed');
   await page.locator('[data-rs-diff="10y"]').click();
   assert((await page.locator('.rates-spread .rates-graph-head').innerText()).includes('10Y'),'10Y sovereign cross-country spread failed');
   await page.locator('[data-rate-ccy="GBP"]').first().click();
   assert((await page.locator('.rates-figure').innerText()).includes('OIS'),'GBP official OIS layer missing');
   assert((await page.locator('.rates-reprice').innerText()).includes('1 settimana'),'GBP repricing 1W missing');
   await page.locator('[data-rate-ccy="CHF"]').first().click();
   assert((await page.locator('.rates-status').innerText()).includes('30/09/2026'),'CHF stale government benchmark date not disclosed');
   await page.locator('#rs-country').selectOption('NZD');
   assert((await page.locator('.rates-hero').innerText()).includes('NZD')||(await page.locator('.rates-status').innerText()).includes('NZD'),'NZD country selector failed');
   assert((await page.locator('.rates-instrument-card').innerText()).includes('PROXY DIREZIONALE'),'NZD proxy not labeled');
   await page.locator('#rs-other').selectOption('USD');
   assert((await page.locator('.rates-spread .rates-graph-head').innerText()).includes('NZD − USD'),'Cross-country switch failed');
   // Macro Dynamics Research Studio: dated multi-category indicator archive,
   // G8 within-country percentiles, real source series and quarterly frequency.
   await page.evaluate(()=>{location.hash='#macro'});
   assert(await page.locator('.macro-country').count()===8,'Macro G8 country strip incomplete');
   assert(await page.locator('.macro-heat-row').count()===8,'Macro historical heatmap incomplete');
   await page.locator('.macro-country[data-ms-country="USD"]').click();
   assert((await page.locator('.macro-studio-status').innerText()).includes('204 SERIE STORICHE'),'Full source-backed macro archive not loaded');
   assert(await page.locator('.macro-main-chart .chart svg').count()>0,'Macro indicator history plot absent');
   assert(await page.locator('.macro-audit tbody tr').count()===12,'Macro last 12 observations audit incomplete');
   assert(await page.locator('.macro-definitions details').count()>=8,'Macro glossary incomplete');
   await page.locator('[data-ms-category="Crescita"]').click();
   assert((await page.locator('.macro-chart-heading').innerText()).includes('Consumi reali'),'Macro growth default selector failed');
   await page.locator('[data-ms-view="change"]').click();
   assert((await page.locator('.macro-main-chart .chart-legend').innerText()).includes('Δ'),'Macro change chart failed');
   await page.locator('[data-ms-view="velocity"]').click();
   assert((await page.locator('.macro-main-chart .chart-legend').innerText()).includes('ΔΔ'),'Macro acceleration chart failed');
   await page.locator('[data-ms-window="12"]').click();
   assert(await page.locator('.macro-main-chart .chart svg').count()>0,'Macro 12-observation window failed');
   await page.locator('.macro-country[data-ms-country="AUD"]').click();
   assert((await page.locator('.macro-chart-heading').innerText()).includes('PIL reale QoQ'),'Quarterly AUD growth series missing');
   assert((await page.locator('.macro-chart-caption').innerText()).includes('trimestrale'),'Frequency methodology caveat missing');
   const spendingSeriesId=await page.locator('#ms-series option').filter({hasText:'Spesa famiglie'}).first().getAttribute('value');
   assert(spendingSeriesId,'Household spending series not present in AUD series list');
   await page.locator('#ms-series').selectOption(spendingSeriesId);
   assert((await page.locator('.macro-chart-heading').innerText()).includes('Spesa famiglie'),'Series selection did not change chart');
   await page.locator('.macro-country[data-ms-country="NZD"]').click();
   assert((await page.locator('.macro-chart-heading').innerText()).includes('PIL reale YoY'),'Quarterly NZD growth series missing');
   await page.locator('[data-ms-heat="labour"]').click();
   assert((await page.locator('.macro-heat-controls').innerText()).includes('Disoccupazione'),'Heatmap dimension toggle missing');
   await page.locator('#ms-other').selectOption('USD');
   assert((await page.locator('.macro-relative').innerText()).includes('USD'),'Cross-country macro comparison not updated');
   await page.locator('[data-ms-compare="labour"]').click();
   assert((await page.locator('.macro-relative').innerText()).includes('disoccupazione'),'Relative unemployment comparison missing');
   // COT research studio: complete G8 chart, flow, price and explanatory controls.
   await page.evaluate(()=>{location.hash='#cot'});
   assert(await page.locator('.cot-country-selector .cot-country-button').count()===8,'COT G8 selector incomplete');
   assert((await page.locator('.cot-source-band').innerText()).includes('27/10/2026'),'COT historical timestamp missing');
   assert(await page.locator('.cot-graph-grid .chart svg').count()===2,'COT history and price charts missing');
   assert(await page.locator('.cot-detailed-table .data-table tbody tr').count()===12,'COT last 12 weekly rows missing');
   assert(await page.locator('.cot-universe .data-table tbody tr').count()===8,'COT G8 comparison table incomplete');
   await page.locator('[data-cot-mode="gross"]').click();
   const cotLegend=await page.locator('.cot-plot-card .chart-legend').first().innerText();
   assert(cotLegend.includes('Long')&&cotLegend.includes('Short'),'COT long short overlay failed');
   await page.locator('[data-cot-mode="netoi"]').click();
   assert((await page.locator('.cot-figure-title').first().innerText()).includes('Open Interest'),'COT Net/OI graph switch failed');
   await page.locator('[data-cot-window="104"]').click();
   assert((await page.locator('.cot-figure-title').first().innerText()).includes('104 settimane'),'COT historical window control failed');
   await page.locator('.cot-country-selector [data-ccy="CHF"]').click();
   const chfText=await page.locator('.cot-hero').innerText();
   assert(chfText.includes('Gli short prevalgono'),'COT CHF net-short reading missing');
   assert((await page.locator('.cot-analysis-grid').innerText()).includes('P alto non significa net long'),'COT percentile direction caveat missing');
   await page.locator('[data-cot-filter="extreme"]').click();
   assert((await page.locator('.cot-universe tbody tr').count())>=1,'COT extreme universe filter failed');
   await page.locator('[data-cot-sort="delta1"]').click();
   assert((await page.locator('.cot-universe th').allInnerTexts()).join(' ').includes('Δ 1W'),'COT sorting failed');
   // Cross asset controls.
   await page.evaluate(()=>{location.hash='#risk'});
   await page.locator('[data-risk="SP500"]').click();
   assert((await page.locator('.panel-head h2').first().innerText()).includes('S&P 500'),'Risk switch failed');
   // News toggles.
   await page.evaluate(()=>{location.hash='#news'});
   await page.locator('[data-news-mode="official"]').click();
   assert((await page.locator('.panel-head h2').first().innerText()).includes('Comunicazioni'),'News tab failed');
   assert(errors.length===0,'Browser errors: '+errors.join(' | '));
   await page.close();
  }
  fs.writeFileSync(evidence+'/report.json',JSON.stringify({status:'PASS',base:BASE,results},null,2));
  console.log('FXQUANT_NEXT_VISUAL_AND_INTERACTION_QA_PASS',JSON.stringify({views:results.length,viewports:[1440,390],feed:'14/14',interactions:'PASS'}));
 }finally{await browser.close();}
})().catch(e=>{console.error('FXQUANT_NEXT_QA_FAIL',e.stack||e);process.exit(1)});
