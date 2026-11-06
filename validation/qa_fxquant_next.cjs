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
   assert(/12\/12 fonti caricate/.test(sourceText),'Feed mismatch: '+sourceText);
   for(const route of ROUTES){
    await page.evaluate(r=>{location.hash='#'+r},route);
    await page.waitForFunction(r=>document.querySelector('#crumb-page')?.textContent===({overview:'Panoramica',currencies:'Valute G8',pairs:'Coppie FX',macro:'Macro Lab',rates:'Tassi & OIS',cot:'Positioning',risk:'Risk Radar',news:'News Pulse'})[r],route);
    const h1=await page.locator('main h1').first().innerText();
    assert(h1.length>12,'Missing heading '+route);
    const overflow=await page.evaluate(()=>({scroll:document.documentElement.scrollWidth,client:document.documentElement.clientWidth}));
    assert(overflow.scroll<=overflow.client+2,'Horizontal overflow on '+route+' '+width+': '+JSON.stringify(overflow));
    await page.screenshot({path:evidence+'/'+route+'-'+width+'.png',fullPage:route==='overview'||route==='pairs'||route==='cot'});
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
   // Rates selectors redraw source-backed chart.
   await page.evaluate(()=>{location.hash='#rates'});
   await page.locator('[data-window="5"]').click();
   assert(await page.locator('.chart svg').count()>0,'Rates chart absent');
   await page.locator('[data-rate-mode="10y"]').click();
   assert((await page.locator('.chart-legend').innerText()).includes('10Y'),'Rate mode failed');
   // Macro selector drives the graph.
   await page.evaluate(()=>{location.hash='#macro'});
   await page.locator('[data-metric="labour"]').click();
   assert((await page.locator('.panel-head h2').first().innerText()).toLowerCase().includes('disoccupazione'),'Macro toggle failed');
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
  console.log('FXQUANT_NEXT_VISUAL_AND_INTERACTION_QA_PASS',JSON.stringify({views:results.length,viewports:[1440,390],feed:'12/12',interactions:'PASS'}));
 }finally{await browser.close();}
})().catch(e=>{console.error('FXQUANT_NEXT_QA_FAIL',e.stack||e);process.exit(1)});
