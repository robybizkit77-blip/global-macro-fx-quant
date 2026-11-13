'use strict';
/* G8 editorial UX gate: no dense data grid on the first read.
 * The price-only ranking and four provenance-rich axes MUST remain available.
 */
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'../..'),base='site/fx-quant-v2/next/';
const read=p=>fs.readFileSync(path.join(root,p),'utf8');
const json=p=>JSON.parse(read(p));
const win={},ctx={window:win};
for(const file of ['pair-rankings.js','currency-data-fallback.js','g8-growth-shadow.js',
 'g8-macro-gap-scenarios.js','g8-inflation-labour-shadow.js','g8-rates-shadow.js',
 'currency-strength-reading.js','g8-macro-pricing-bridge.js','macro-strength-estimated-v1.js','currency-studio.js'])
 vm.runInNewContext(read(base+file),ctx,{filename:file,timeout:5000});
const data={macroSeries:json('live_data/sections/MACRO_SERIES.json'),
 currencyPrices:json('live_data/sections/ECB_G8_PRICE_HISTORY.json'),
 rates:json('live_data/sections/NATIVE_RATES_DATA.json'),
 macro:json('live_data/sections/MACRO_THERMOMETER_DATA.json'),
 cb:json('live_data/sections/NATIVE_CB_DATA.json'),
 cbEstimated:json('live_data/sections/CB_PRICING_ESTIMATED.json'),
 ois:json('site/fx-quant-v2/ois-pricing-snapshot.json'),
 cotHistory:json('live_data/sections/V250_COT_CHART_DATA.json'),
 pairs:json('live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json'),
 chfResearch:json('site/fx-quant-v2/chf-snb-paired-history.json'),
 nzdPostroll:json('site/fx-quant-v2/nzd-b2-postroll-web-research.json'),
 chfSpot:json('live_data/sections/CHF_SNB_10Y_SPOT_CONTEXT.json'),
 nzdDirectionalProxy:json('live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json'),
  macroObserved:json('site/control-room-preview/macro-v3-current-evidence.json'),
  calendar:json('live_data/sections/CALENDAR_OPERATIONAL_VIEW.json')
};
const FX=['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'],now='2026-11-12';
const fmt=(x,n=2)=>typeof x==='number'&&Number.isFinite(x)?
 x.toLocaleString('it-IT',{minimumFractionDigits:n,maximumFractionDigits:n}):'—';
const sign=(x,n=2,u='')=>typeof x==='number'&&Number.isFinite(x)?
 (x>0?'+':x<0?'−':'')+fmt(Math.abs(x),n)+u:'—';
const esc=x=>String(x??'').replace(/&/g,'&amp;').replace(/</g,'&lt;')
 .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const flags=Object.fromEntries(FX.map(x=>[x,x]));
const est=win.FXQuantMacroEstimated.evaluate({
 observed:data.macroObserved,prices:data.currencyPrices,ois:data.ois,rates:data.rates,
 model:data.pairs,now,rankingFn:win.FXQuantPairRankings.currencyRanking});
assert.equal(est.status,'STIMA_OPERATIVA_NON_VALIDATA',est.reason);
const args={get:key=>key==='estimatedMacro'?est:data[key],FX,FLAGS:flags,NAMES:flags,
 pageHero:()=>'<header>Valute G8</header>',esc,fmt,sign,date:x=>x,
 finite:x=>typeof x==='number'&&Number.isFinite(x),
 validDay:x=>/^\d{4}-\d{2}-\d{2}$/.test(x||''),dayNow:()=>now};
const origin=win.FXQuantCurrencyStrength.analyze({prices:data.currencyPrices,
 macro:data.macro.currencies,rates:data.rates,ois:data.ois.currencies,
 cot:data.cotHistory,now,rankingFn:win.FXQuantPairRankings.currencyRanking});
const positions=Array.from(origin.rows,x=>x.ccy); // host-realm array; data model runs inside vm
for(const country of FX){
 const html=win.FXQuantCurrencies.render({...args,state:{ccy:country,csOther:country==='EUR'?'USD':'EUR',csReturnWindow:20}});
 const boardStart=html.indexOf('id="orient-strength-board"');
 const boardEnd=html.indexOf('</section>',boardStart);
 const focusStart=html.indexOf('id="orient-strength-focus"');
 const evidenceStart=html.indexOf('<details class="strength-evidence-fold">',focusStart);
 const methodStart=html.indexOf('<details class="strength-method-fold">',evidenceStart);
 assert(boardStart>=0&&boardEnd>boardStart&&focusStart>boardEnd&&evidenceStart>focusStart&&methodStart>evidenceStart);
 const board=html.slice(boardStart,boardEnd);
 const story=html.slice(focusStart,evidenceStart);
 assert.equal((board.match(/class="strength-row /g)||[]).length,8,'Always eight currency ranked narrative choices');
 assert.equal((board.match(/class="strength-brief"/g)||[]).length,8,'Macro headline per currency');
 assert.equal((board.match(/class="strength-market-brief /g)||[]).length,8,'Money-market quality per currency');
 assert.equal((board.match(/class="strength-price-brief /g)||[]).length,8,'Actual FX price strength per currency');
 assert(!board.includes('class="strength-axis'),'Dense 2Y/6M/CPI numeric grid cannot be in first glance');
 assert(!board.includes('class="strength-card"'),'Source cards must be inside disclosure');
 assert(board.includes('economia, movimento dei tassi e prezzo'),'Estimated score dimensions explicit');
 assert(board.includes('fixing BCE')&&board.includes('proxy'), 'Do not hide price/sources limitations');
 assert(story.includes('class="strength-first-reading"'),'Economics-first story required');
 assert.equal((story.match(/<p><strong>/g)||[]).length,3,
   'Exactly three connected narrative paragraphs, not a metric gallery');
 for(const phrase of ['Il quadro economico.','Che cosa stanno facendo i tassi?',
  'Che cosa mostra il Forex.','Che cosa monitorare.'])assert(story.includes(phrase),phrase+' missing');
 assert(!story.includes('La risposta del Forex.'),'Observed 20-day price is not proven a macro response');
 if(country==='GBP'){
  assert(story.includes('calendario riporta un dato sul PIL del 2026-11-12'),
   'UK today GDP event requires release-vintage caution');
  assert(story.includes('stima utilizza ancora 2026Q2'),
   'The current model must not silently present Q2 GDP as new Q3 growth');
  assert(story.includes('risultato non è verificato'),
   'No release actual/consensus inferred from a schedule');
  const staleCalendar={...data.calendar,last_checked_at_utc:'2026-10-01T00:00:00Z'};
  const staleHtml=win.FXQuantCurrencies.render({...args,state:{ccy:'GBP',csOther:'EUR',csReturnWindow:20},
   get:key=>key==='estimatedMacro'?est:key==='calendar'?staleCalendar:data[key]});
  assert(!staleHtml.includes('calendario riporta un dato sul PIL'),
   'Never use an old calendar as proof of a new event');
  const newer=JSON.parse(JSON.stringify(est));
  newer.by.GBP.macro.gdpRelease='2026-11-12';
  const newerHtml=win.FXQuantCurrencies.render({...args,state:{ccy:'GBP',csOther:'EUR',csReturnWindow:20},
   get:key=>key==='estimatedMacro'?newer:data[key]});
  assert(!newerHtml.includes('calendario riporta un dato sul PIL'),
   'Once a GDP source is integrated the missing-release caution must disappear');
 }
 if(country==='CHF'){
  assert(story.includes('contributo neutro per assunzione prudenziale'),
   'CHF must show the explicit neutral model assumption, not invent a monetary-rate trend');
  assert(story.includes('La disoccupazione osservata è poco mossa'),
   'CHF labor trend is not fabricated from rate absence');
  assert(!story.includes('Non abbiamo una variazione monetaria recente'),
   'Source gap belongs in audit; first read gives an economically grounded model view');
 }
 if(country==='NZD'){
  assert(story.includes('Il futures ASX bank-bill a sei mesi') &&
    story.includes('proxy direzionale'),
   'NZD current ASX 6M proxy must reach the first-read, not be mistaken for missing OIS');
  assert(story.includes('disoccupazione aumenta'),
   'NZD observed labor deterioration must remain in the macro narrative');
  assert(story.includes('NZD/USD')&&story.includes('AUD/NZD'),
   'NZD policy proxy must translate into relative FX pairs to watch');
 }
 assert(!story.includes('La macro rallenta ma il riferimento dei tassi sale'),
  'A low economic level cannot be sold as proven GDP deceleration');
 assert(!story.includes('class="strength-card"'),'First read must contain no detail cards');
 assert(!story.includes('Prove disponibili '),'Evidence counts belong in audit details');
 const evidence=html.slice(evidenceStart,methodStart);
 assert.match(evidence,/^<details class="strength-evidence-fold"><summary>/,
  'Native source audit closed by default');
 assert(!evidence.slice(0,130).includes(' open'),'Evidence must not open by default');
 assert(evidence.includes('class="strength-cards"'));
 assert.equal((evidence.match(/class="strength-card"/g)||[]).length,4,
  'All four source-qualified axes preserved');
 assert(evidence.includes('class="strength-shadow-fold"')&&evidence.includes('NON POINT-IN-TIME'));
 assert(evidence.includes('COT settimanale')||evidence.includes('COT'));
 assert(evidence.includes('Da monitorare:')&&evidence.includes('consenso'));
 assert(evidence.includes('Copertura della stima:'));
  assert(evidence.includes('non è testato out-of-sample'));
 assert(html.includes('class="strength-pair-fold"')&&html.includes('class="strength-method-fold"'),
  'Prior bilateral research and complete ranking accessible');
 assert.equal((html.match(/class="orient-rank-row /g)||[]).length,8,
  'Source-auditable ranking still available in method disclosure');
 assert(!/\bNaN\b|\bundefined\b|\[object Object\]/.test(html));
 const actualOrder=[...board.matchAll(/class="strength-name"><b>#[1-8]<\/b><strong>[^<]* ([A-Z]{3})<\/strong>/g)].map(m=>m[1]);
 assert.deepEqual(actualOrder,Array.from(est.currencies,x=>x.ccy),'Estimated current ordering must lead first read');
 const selected=[...board.matchAll(/class="strength-row selected [^"]+"[^>]*data-cs-country="([A-Z]{3})"/g)].map(m=>m[1]);
 assert.deepEqual(selected,[country],'Selected currency must remain navigable');
}
const idx=read(base+'index.html');
assert(idx.includes('currency-studio.js?v=16')&&idx.includes('currency-studio.css?v=7'));
assert(idx.indexOf('g8-macro-pricing-bridge.js')<idx.indexOf('currency-studio.js'));
const css=read(base+'currency-studio.css');
assert(css.includes('.strength-first-reading')&&css.includes('.strength-evidence-fold>summary'));
assert(css.includes('@media(max-width:700px)'));
assert(css.includes('@media(max-width:950px)'));
assert(css.includes('.strength-pair-fold>.orient-lead.orient-voice'));
assert(css.includes('grid-template-columns:minmax(0,1fr);gap:8px'),
  'Ranked G8 rows must stay a single vertical list instead of broken 2x4 cards');
console.log('G8_EDITORIAL_FIRST_READ_PASS: 8×8 narrative choices, three coherent paragraphs, complete collapsed evidence, estimated current rank, archived price methodology, mobile CSS');
