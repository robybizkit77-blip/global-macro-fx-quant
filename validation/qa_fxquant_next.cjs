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
    await page.waitForFunction(r=>document.querySelector('#crumb-page')?.textContent===({overview:'Panoramica',currencies:'Valute G8',pairs:'Coppie FX',macro:'Scenario macro',rates:'Tassi & OIS',cot:'COT',risk:'Rischio',news:'Notizie'})[r],route);
    if(route!=='overview'){
      assert(await page.locator('main .research-essay').count()===1,'Narrative research missing on '+route);
      assert(await page.locator('main .research-essay .essay-prose p').count()===3,'Research incomplete on '+route);
      assert(await page.locator('main .research-essay a[href^="#"]').count()===1,'Research handoff link missing on '+route);
    }
    const h1=await page.locator('main h1').first().innerText();
    assert(h1.length>12,'Missing heading '+route);
    const overflow=await page.evaluate(()=>({scroll:document.documentElement.scrollWidth,client:document.documentElement.clientWidth}));
    assert(overflow.scroll<=overflow.client+2,'Horizontal overflow on '+route+' '+width+': '+JSON.stringify(overflow));
    await page.screenshot({path:evidence+'/'+route+'-'+width+'.png',fullPage:route==='overview'||route==='pairs'||route==='cot'||route==='rates'||route==='macro'||route==='currencies'});
    results.push({width,route,h1,overflow:'PASS'});
   }

   // NEXT V6: the lead topic must be explained by the evidence and default chart.
   await page.evaluate(()=>{location.hash='#overview'});
   await page.waitForFunction(()=>document.querySelector('.market-letter')!==null);
   assert(await page.locator('.market-letter .letter-opening').count()===1,'Narrative opening missing');
   assert(await page.locator('.dashboard-kpi').count()===4,'Dashboard market indicators missing');
   assert(await page.locator('.dashboard-chart-grid').count()===1,'Dashboard chart and desk analysis not side by side');
   assert(await page.locator('.dashboard-dossier').count()===1,'Optional deep research panel missing');
   assert(await page.locator('.decision-overview').count()===1,'FX research-to-decision summary missing');
   assert((await page.locator('.decision-summary').innerText()).includes('VERDETTO OPERATIVO'),'Operational verdict missing');
   assert(await page.locator('.decision-overview .decision-case-rates').count()>=1,'Home FX shortlist missing dated 2Y source evidence');
   assert((await page.locator('.decision-overview .decision-case-rates').first().innerText()).includes('non OIS'),'Home must identify sovereign 2Y, never OIS');
   assert(await page.locator('.dashboard-dossier').evaluate(el=>!el.open),'Deep research must not displace charts by default');
   assert(await page.locator('.letter-argument .letter-section').count()>=4,'Research reasoning too shallow');
   const evidenceRows=await page.locator('.letter-evidence .letter-proof-row').count();
   assert(evidenceRows>=2,'Supporting observations missing');
   assert(await page.locator('.letter-chart-visual .chart svg').count()>0,'Lead-chart evidence missing');
   const regime=await page.locator('.letter-evidence').getAttribute('data-research-kind');
   assert(['stress','relief','bond-rally','yield-selloff','fx-divergence','mixed'].includes(regime),'Unknown research case');
   if(regime==='stress'||regime==='relief'){
    assert((await page.locator('.letter-chart-visual .chart-legend').innerText()).includes('Nasdaq'),'Risk story must open on Nasdaq evidence');
    assert((await page.locator('.letter-proof-list').innerText()).includes('Credito High Yield'),'Risk story has no credit corroboration');
   }
   await page.locator('[data-hchart="vix"]').click();
   assert((await page.locator('.letter-chart-visual .chart-legend').innerText()).includes('VIX'),'Chart switch to VIX failed');
   await page.locator('[data-hwindow="5"]').click();
   assert(await page.locator('.letter-chart-visual .chart svg').count()>0,'5-observation VIX chart missing');
   await page.locator('#quicklaunch').click();
   assert(await page.locator('#quick-layer').evaluate(el=>el.classList.contains('open')),'Quick search did not open');
   await page.locator('#quick-input').fill('EURGBP');
   await page.locator('[data-command="pair:EURGBP"]').click();
   assert((await page.locator('#crumb-page').innerText())==='Coppie FX','Quick search failed to navigate to pair dossier');
   assert((await page.locator('.focus-headline').first().innerText()).includes('EUR/GBP'),'Quick search did not update selected pair');
   assert(await page.locator('.decision-deepdive').count()===1,'FX thesis and timing audit missing');
   assert(await page.locator('.decision-price-grid .chart svg').count()===1,'Real ECB daily pair chart missing');
   assert((await page.locator('.decision-footer').innerText()).includes('Nessun livello'),'H4 data limitation must remain visible');
   assert(await page.locator('.decision-evidence-cell').count()===3,'5D/20D price evidence and historical range missing');
   assert(await page.locator('.decision-daily-watch').count()===1,'No next-fixing monitoring conditions');
   assert(await page.locator('.decision-watch-line').count()===0,'EUR/GBP has no validated favourite; must not invent directional thresholds');
   assert(await page.locator('.decision-rates-bridge').count()===1,'Rates/FX companion is absent in EUR/GBP research dossier');
   assert(await page.locator('.decision-gate-rates').count()===1,'Rates verdict must be visible without scrolling through the full dossier');
   assert((await page.locator('.decision-gate-rates').innerText()).includes('non OIS'),'Top decision rates evidence must be labeled sovereign, non OIS');
   const rateDebug=await page.evaluate(()=>({loaded:!!window.FXQuantRatesBridge,now:new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Rome',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date()),text:document.querySelector('.decision-rates-bridge')?.innerText?.slice(0,700),chartCount:document.querySelectorAll('.decision-rates-bridge .chart svg').length}));
   console.log('FX_NEXT_V13_RATES_DIAGNOSTIC',JSON.stringify(rateDebug));
   assert(await page.locator('.decision-rates-bridge .chart svg').count()===1,'Valid same-date EUR/GBP 2Y differential chart is missing');
   assert(await page.locator('.decision-rates-bridge [data-horizon="5"]').count()===1,'Rates/FX short comparison missing');
   assert((await page.locator('.decision-rates-bridge').innerText()).includes('non OIS'),'Sovereign 2Y versus OIS distinction missing');
   assert(await page.locator('.decision-price-grid [data-reference-line]').count()===0,'No structural thesis may draw misleading FX reference lines');
   assert(await page.locator('[data-v12-reference-toggle]').count()===0,'No toggle for invalid references');
   assert(await page.locator('.decision-watch-unavailable').count()===1,'A pair without a validated favourite must show why levels are unavailable');
   assert((await page.locator('.decision-watch-caveat').innerText()).includes('non supporti o resistenze intraday'),'Reference levels must not be presented as trade levels');
   assert((await page.locator('.decision-price-context').innerText()).includes('sedute'),'Relative-horizon interpretation missing');
   await page.locator('[data-v9-price-window="20"]').click();
   assert(await page.locator('.decision-price-grid .chart svg').count()===1,'Daily 20-fixing chart did not update');
   // The FX selector changes the deep dive and the watchlist is interactive.
   await page.evaluate(()=>{location.hash='#pairs'});
   await page.locator('[data-pair="AUDCAD"]').click();
   assert((await page.locator('.focus-headline').first().innerText()).includes('AUD/CAD'),'Pair select failed');
   assert(await page.locator('.decision-watch-line').count()===2,'AUD/CAD with a dated price history must show favorable and contrary references');
   assert(await page.locator('.decision-rates-bridge').count()===1,'AUD/CAD FX/rates validation panel missing');
   assert(await page.locator('.decision-rates-bridge .chart').count()===0,'Sparse AUD 2Y observations must NOT produce a fake daily chart');
   assert((await page.locator('.decision-rates-bridge').innerText()).includes('discontinuo'),'Sparse AUD rates should be explained clearly');
   assert((await page.locator('.decision-gate-rates').innerText()).includes('non verificabili'),'No false FX/2Y confirmation for sparse AUD history');
   assert(await page.locator('.decision-price-grid [data-reference-line]').count()===2,'Current FX levels must appear on the price chart');
   assert(await page.locator('.decision-reference-caption').count()===1,'Chart line provenance not explained');
   await page.locator('[data-v12-reference-toggle]').click();
   assert(await page.locator('.decision-price-grid [data-reference-line]').count()===0,'Reference hide toggle failed');
   assert(await page.locator('.decision-watch-line').count()===2,'Chart toggle must not hide factual monitoring thresholds');
   await page.locator('[data-v12-reference-toggle]').click();
   assert(await page.locator('.decision-price-grid [data-reference-line]').count()===2,'Reference show toggle failed');
   assert((await page.locator('.decision-daily-watch').innerText()).includes('Sopra'),'AUD/CAD base-favoured threshold should test upside in quoted pair');
   await page.locator('[data-watch="AUDCAD"]').click();
   assert((await page.locator('[data-watch="AUDCAD"]').innerText()).includes('Nella watchlist'),'Watchlist failed');

   // Information architecture: G8 is an orientation layer, not four duplicate studios.
   await page.evaluate(()=>{location.hash='#currencies'});
   await page.locator('.orient-country[data-cs-country="USD"]').click();
   assert(await page.locator('.orient-country').count()===8,'Currency G8 selector incomplete');
   assert(await page.locator('.orient-evidence-item').count()===4,'Four concise context summaries missing');
   assert(await page.locator('.orient-peer-row').count()===7,'Seven peer FX comparisons missing');
   assert(await page.locator('#content .chart').count()===0,'Duplicated research charts remain in G8 orientation');
   assert(await page.locator('#content .cs-tenor-table').count()===0,'Full OIS tenor audit still duplicated in G8');
   assert((await page.locator('.orient-status').innerText()).includes('BCE'),'ECB fixing reference missing');
   assert((await page.locator('.orient-evidence-item[data-evidence="rates"]').innerText()).includes('6M'),'Rates evidence summary absent');
   assert((await page.locator('.orient-evidence-item[data-evidence="cot"]').innerText()).includes('percentile'),'COT evidence explanation absent');
   assert(await page.locator('.orient-verdict').count()===1,'G8 editorial verdict missing');
   assert((await page.locator('.orient-intro').innerText()).includes('fixing BCE'),'G8 narrative missing price observation');
   const usdQuote=Number((await page.locator('.orient-spot>strong').innerText()).replace(',','.'));
   assert(usdQuote>0.85&&usdQuote<1,'USD/EUR inverse cross convention incorrect');
   await page.locator('.orient-country[data-cs-country="EUR"]').click();
   assert((await page.locator('.orient-spot .micro-over').innerText()).includes('EUR/USD'),'Currency context did not update to EUR');
   const eurQuote=Number((await page.locator('.orient-spot>strong').innerText()).replace(',','.'));
   assert(eurQuote>1.1&&eurQuote<1.2,'EUR/USD ECB cross calculation incorrect');
   await page.locator('#cs-other').selectOption('JPY');
   assert((await page.locator('.orient-spot .micro-over').innerText()).includes('EUR/JPY'),'Country countercurrency selector failed');
   await page.locator('[data-cs-returnwindow="60"]').click();
   assert((await page.locator('.orient-peer-controls .pill.active').first().innerText()).includes('60'),'Relative performance 60-session window switch failed');
   await page.locator('[data-cs-sort="currency"]').click();
   assert(await page.locator('.orient-peer-row').count()===7,'G8 peer sorting failed');
   await page.locator('.orient-peer-row[data-cs-other="CHF"]').click();
   assert((await page.locator('.orient-spot .micro-over').innerText()).includes('EUR/CHF'),'Peer comparison did not select CHF');
   // Research hyperlinks retain the chosen currency rather than resetting each studio.
   await page.locator('.orient-evidence-item[data-evidence="macro"] a').click();
   await page.waitForFunction(()=>document.querySelector('#crumb-page')?.textContent==='Scenario macro',{timeout:6000});
   assert(await page.locator('.macro-country.active[data-ms-country="EUR"]').count()===1,'EUR context lost opening Macro Lab');
   await page.evaluate(()=>{location.hash='#currencies'});
   await page.locator('.orient-evidence-item[data-evidence="cot"] a').click();
   await page.waitForFunction(()=>document.querySelector('#crumb-page')?.textContent==='COT',{timeout:6000});
   assert(await page.locator('.cot-country-button.active[data-ccy="EUR"]').count()===1,'EUR context lost opening COT');
   await page.evaluate(()=>{location.hash='#currencies'});
   await page.locator('[data-cs-openpair="EURCHF"]').last().click();
   assert((await page.locator('#crumb-page').innerText())==='Coppie FX','FX research handoff failed');
   assert((await page.locator('.focus-headline').first().innerText()).includes('EUR/CHF'),'FX handoff lost selected cross');
   await page.evaluate(()=>{location.hash='#currencies'});
   await page.locator('.orient-country[data-cs-country="CHF"]').click();
   assert(/\d{2}\/\d{2}\/2026/.test(await page.locator('.orient-evidence-item[data-evidence="rates"]').innerText()),'CHF observed tenor date missing');
   assert((await page.locator('.orient-checkpoint').innerText()).includes('FUTURES'),'CHF pricing type warning missing');
   await page.locator('.orient-country[data-cs-country="NZD"]').click();
   assert(/\d{2}\/\d{2}\/2026/.test(await page.locator('.orient-evidence-item[data-evidence="rates"]').innerText()),'NZD observed tenor date missing');
   assert((await page.locator('.orient-checkpoint').innerText()).includes('PROXY'),'NZD pricing proxy quality missing');
   assert(await page.locator('.orient-peer-row').count()===7,'NZD seven peer comparisons incomplete');
   // No detailed COT, macro, rates duplicate graphs or pricing audit inside the summary.
   assert(await page.locator('#content .chart').count()===0,'Detailed research chart duplicated after switching G8 countries');
   assert(await page.locator('#nav .nav-subheading').count()>=2,'Research navigation lacks intentional grouping');
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
   assert(await page.locator('.macro-narrative-edition h2').count()===1,'Editorial Macro market verdict missing');
   assert(await page.locator('.macro-verdict-line').count()===1,'Macro strength/weakness verdict missing');
   assert(await page.locator('.macro-advanced').evaluate(el=>!el.open),'Advanced Macro data should remain optional at first view');
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
   await page.locator('.macro-advanced > summary').click();
   assert(await page.locator('.macro-advanced').evaluate(el=>el.open),'Advanced Macro content did not expand');
   await page.locator('[data-ms-heat="labour"]').click();
   assert((await page.locator('.macro-heat-controls').innerText()).includes('Disoccupazione'),'Heatmap dimension toggle missing');
   await page.locator('#ms-other').selectOption('USD');
   assert((await page.locator('.macro-relative').innerText()).includes('USD'),'Cross-country macro comparison not updated');
   await page.locator('[data-ms-compare="labour"]').click();
   assert((await page.locator('.macro-relative').innerText()).includes('disoccupazione'),'Relative unemployment comparison missing');
   // COT research studio: complete G8 chart, flow, price and explanatory controls.
   await page.evaluate(()=>{location.hash='#cot'});
   assert(await page.locator('.cot-country-selector .cot-country-button').count()===8,'COT G8 selector incomplete');
   assert(/\d{2}\/\d{2}\/2026/.test(await page.locator('.cot-source-band').innerText()),'COT historical timestamp missing');
   assert(await page.locator('.cot-plot-card .chart svg').first().count()===1,'Validated COT position chart missing');
   const pricePlot=await page.locator('.cot-price-card .chart svg').count();
   if(pricePlot===0){
    assert((await page.locator('.cot-price-card .empty').innerText()).includes('Prezzo allineato non validato'),'Missing source-quality reason for unavailable COT price');
   }else assert(pricePlot===1,'Unexpected duplicate COT price charts');
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
