'use strict';
/* Current FX Quant Next design/interaction gate.
 * The prior smoke test required the old pair dossier to be permanently
 * expanded and assumed 2026-11-05 rate fixtures would remain current.
 * The approved layout instead starts with an 8-currency / 28-pair ranking,
 * and reveals a pair-specific source audit only after the user selects a row.
 *
 * This exercises the actual click path on desktop and mobile, including
 * dated macro catalysts and preservation of source provenance. It is an
 * independent browser gate, not a substitute for the detailed Final Visual
 * QA and source contracts in validation/publishing.
 */
const fs=require('node:fs');
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
const BASE=process.env.FXQN_BASE||'http://127.0.0.1:8000/site/fx-quant-v2/next/index.html';
const routes={
 overview:'Panoramica',currencies:'Valute G8',pairs:'Coppie FX',
 macro:'Scenario macro',rates:'Tassi & OIS',cot:'COT',risk:'Rischio',
 news:'Notizie',library:'Research Library'
};
const evidence='fxquant-next-browser-evidence';
fs.mkdirSync(evidence,{recursive:true});
const locator=(page,css)=>page.locator(css);
async function route(page,key){
 await page.evaluate(key=>{location.hash='#'+key},key);
 await page.waitForFunction(({key,title})=>
  document.querySelector('#content')?.dataset.view===key&&
  document.querySelector('#crumb-page')?.textContent?.trim()===title,
  {key,title:routes[key]},{timeout:20000});
}
async function inspectRoute(page,label,key){
 await route(page,key);
 const h1=await locator(page,'#content h1').first().innerText();
 assert(h1.length>12,label+' '+key+': title missing');
 const ui=await page.evaluate(()=>{
  const e=document.querySelector('#content');
  const content=e?.innerText||'';
  return {
   length:content.length,
   horizontalOverflow:document.documentElement.scrollWidth>innerWidth+2,
   badTokens:/\bundefined\b|\[object Object\]|\bNaN\b/.test(content)
  };
 });
 assert(ui.length>100,label+' '+key+': page content missing');
 assert(!ui.horizontalOverflow,label+' '+key+': horizontal overflow');
 assert(!ui.badTokens,label+' '+key+': broken data interpolations');
 if(key==='overview'){
  assert.equal(await locator(page,'.morning-dashboard').count(),1,'Dated morning desk must stay available');
  assert.equal(await locator(page,'.morning-lead h1').count(),1,'Morning lead missing');
  assert.equal(await locator(page,'.morning-archive-note').count(),1,
   'Current or archival edition must identify its date/status');
  assert.equal(await locator(page,'.morning-fx-pulse').count(),1,
   'Source-dated G8 and pair research must remain attached to Home');
 }else if(key==='currencies'){
  assert.equal(await locator(page,'#orient-strength-board .strength-row').count(),8,
   'Exactly eight estimated G8 first-read choices required');
  assert.equal(await locator(page,'.strength-first-reading > p').count(),3,
   'Country first read must connect macro, monetary references and price');
  assert.equal(await locator(page,'#g8-pricing-proof').count(),1,
   label+' source-first G8 monetary evidence missing');
  assert.equal(await locator(page,'#g8-pricing-proof .g8-pricing-metric').count(),2,
   label+' 1D and 1W monetary sources must remain available');
  assert.equal(await locator(page,'.strength-evidence-fold').count(),1,
   'Country provenance must remain accessible on demand');
 }else if(key==='pairs'){
  assert.equal(await locator(page,'.fx-rank-currency').count(),8,
   'Pair route must lead with eight currency views');
  assert.equal(await locator(page,'.fx-rank-all-list button.fx-rank-pair').count(),28,
   'All 28 canonical pair choices required');
  assert.equal(await locator(page,'.pairs-reading-compact').count(),0,
   'Dossier should start collapsed until the user chooses a cross');
  assert.equal(await locator(page,'.decision-desk-story').count(),0,
   'Old permanently expanded pair dossier must not displace the ranking');
 }else if(key==='rates'){
  const bridge=locator(page,'.rates-fx-handoff');
  assert.equal(await bridge.count(),1,label+' rates-to-FX evidence missing');
  const proof=await bridge.getAttribute('data-fx-proof');
  assert(['ready','unavailable'].includes(proof),label+' unclassified relative rates proof');
  const relative=locator(page,'#rates-relative-pricing');
  assert.equal(await relative.count(),1,label+' relative monetary repricing missing');
  assert(['NOT_ALIGNED','SAME_END_REFERENCE_UNVERIFIED','MATCHED_EXACT_INTERVAL'].includes(
   await relative.getAttribute('data-rr6-status')),
   label+' relative pricing date/provenance status is missing');
  const historyDesk=locator(page,'#rates-pricing-history');
  assert.equal(await historyDesk.count(),1,label+' historical G8 pricing chart not present');
  assert.equal(await historyDesk.locator('.ois-history-currency').count(),8,
   label+' historical G8 sparkline navigator incomplete');
  assert(await historyDesk.locator('svg').count()>=6,label+' historical G8 charts missing');
  assert.equal(await historyDesk.getAttribute('data-history-currency'),'USD',
   label+' G8 historical pricing must start with selected currency');
  const oisDesk=locator(page,'#rates-pricing-moves');
  assert.equal(await oisDesk.count(),1,label+' source-dated monetary changes missing');
  assert.equal(await oisDesk.locator('.ois-bp-row').count(),3,label+' needs 3M/6M/12M comparison');
  assert.equal(await oisDesk.locator('.ois-g8-row').count(),8,label+' needs all eight G8 monetary references');
  assert.equal(await oisDesk.getAttribute('data-pricing-window'),'1d',label+' must start with previous session');
  assert((await bridge.innerText()).includes('NON OIS'),
   label+' government yield comparison is incorrectly labeled as OIS');
 }else if(key==='cot'){
  assert.equal(await locator(page,'.cot-desk-overview').count(),1,'COT G8 overview missing');
  assert.equal(await locator(page,'.cot-desk-card').count(),4,'COT evidence cards missing');
 }else if(key==='risk'){
  assert.equal(await locator(page,'.risk-research-reading').count(),1,'Risk desk context missing');
 }else if(key==='news'){
  assert.equal(await locator(page,'.news-research-reading').count(),1,'News desk context missing');
 }
 return {route:key,h1,characters:ui.length};
}
async function g8Choice(page,label){
 await route(page,'currencies');
 const audit=locator(page,'details.strength-evidence-fold');
 assert(!(await audit.evaluate(el=>el.open)),label+' source audit opens without request');
 await audit.locator(':scope > summary').click();
 assert(await audit.evaluate(el=>el.open),label+' source audit did not open');
 assert.equal(await audit.locator('.strength-card').count(),4,label+' full country evidence missing');
 await locator(page,'#orient-strength-board [data-cs-country="NZD"]').click();
 await page.waitForFunction(()=>
  document.querySelector('.strength-row.selected')?.dataset.csCountry==='NZD');
 assert(await audit.evaluate(el=>el.open),label+' country selection closed user-opened audit');
 const note=await locator(page,'#orient-strength-focus').innerText();
 assert(note.includes('NZD'),label+' NZD reading did not update');
 assert(note.includes('Che cosa mostra il Forex.'),label+' price mislabeled as causal response');
 assert(note.includes('6M NZD')&&note.includes('proxy bank-bill'),
  label+' NZD must explain source-dated bank-bill 6M proxy');
 const proof=locator(page,'#g8-pricing-proof');
 assert.equal(await proof.getAttribute('data-g8-pricing-ccy'),'NZD',
  label+' monetary evidence did not follow NZD');
 await proof.locator('.g8-pricing-docs > summary').click();
 assert.equal(await proof.locator('.g8-pricing-docs nav a').count(),3,
  label+' all G8 money sources should be inspectable');
 await locator(page,'#orient-strength-board [data-cs-country="EUR"]').click();
 assert.equal(await locator(page,'#g8-pricing-proof').getAttribute('data-g8-pricing-ccy'),'EUR',
  label+' monetary source did not update to EUR');
 assert((await locator(page,'#g8-pricing-proof').innerText()).includes('futures secondari'),
  label+' EUR research futures must remain labeled as futures');
 assert(note.includes('Che cosa monitorare.') &&
   note.includes('NZD/USD') && note.includes('AUD/NZD'),
  label+' NZD macro/rates proxy must lead to two FX monitoring instruments');
}
async function chosenPair(page,key,label){
 const button=locator(page,'#fx-ranking-desk button.fx-rank-pair[data-pair="'+key+'"]').first();
 assert(await button.count(),label+' '+key+' not present in complete 28-pair ranking');
 await button.click();
 await page.waitForFunction(key=>{
  const selected=document.querySelector('#fx-selected-thesis');
  return !!selected?.textContent?.includes(key.slice(0,3)+'/'+key.slice(3));
 },key,{timeout:15000});
 const p=locator(page,'.pairs-reading-compact');
 assert.equal(await p.count(),1,label+' '+key+' first-read missing');
 assert.equal(await p.locator('.pairs-three-answers > div').count(),3,
  label+' thesis, trade attractiveness and entry caveat incomplete');
 const story=await p.innerText();
 for(const word of ['TESI FONDAMENTALE','TRADE ATTRACTIVENESS',
  'Rafforzerebbe il quadro','Lo indebolirebbe','Evento da monitorare'])
  assert(story.includes(word),label+' '+key+' missing '+word);
 assert(/calendario|evento|prossimo|previsto|ufficiale/i.test(story),
  label+' '+key+' no explanation of calendar source');
 return p;
}
async function pairJourney(page,label){
 await route(page,'pairs');
 await chosenPair(page,'GBPUSD',label);
 const gbp=await locator(page,'.pairs-event-watch').innerText();
 assert(!gbp.includes('ha sorpreso')&&!gbp.includes('reazione confermata'),
  label+' schedule must never invent a released value or price response');
 assert(gbp.includes('consenso'),label+' post-release checking must compare consensus');
 const details=locator(page,'details.pairs-optional-chart');
 assert.equal(await details.count(),1,label+' full dossier absent');
 assert(!(await details.evaluate(el=>el.open)),label+' full dossier not collapsed initially');
 await details.locator(':scope > summary').click();
 assert(await details.evaluate(el=>el.open),label+' full dossier cannot expand');
 assert.equal(await details.locator('.decision-desk-story[data-serafini-pair="GBPUSD"]').count(),1,
  label+' clicking GBP/USD did not build its own economic narrative');
 const paragraphCount=await details.locator('.decision-desk-story > p').count();
 assert(paragraphCount>=4&&paragraphCount<=5,
  label+' economic reasoning must contain macro, market, judgment and invalidation');
 assert.equal(await details.locator('.decision-desk-evidence').count(),1,
  label+' detailed source audit lost');
 assert.equal(await details.locator('.decision-price-grid .chart svg').count(),1,
  label+' real ECB fixing chart missing in opened dossier');
 // A new selection should change the underlying reasoning, not just the title.
 await chosenPair(page,'EURCHF',label);
 const swiss=await locator(page,'.pairs-event-watch').innerText();
 assert(swiss.includes('CHF')||swiss.includes('Calendario non aggiornato'),
  label+' EUR/CHF source-specific macro catalyst missing');
 assert(!swiss.includes('risultato pubblicato'),
  label+' upcoming GDP may not be treated as an observed release');
 const watch=locator(page,'[data-watch="EURCHF"]');
 await watch.click();
 assert((await locator(page,'[data-watch="EURCHF"]').innerText()).includes('Nella watchlist'),
  label+' selected pair could not be saved');
 await locator(page,'[data-pair-close]').click();
 assert.equal(await locator(page,'.pairs-reading-compact').count(),0,
  label+' back to 28 pairs did not close opened dossier');
 assert.equal(await locator(page,'.fx-rank-all-list button.fx-rank-pair').count(),28,
  label+' full ranking lost after closing dossier');
}
async function pairMonetaryJourney(page,label){
 await route(page,'pairs');
 await chosenPair(page,'EURGBP',label);
 const panel=locator(page,'.pair-monetary-bridge[data-pair-monetary-pair="EURGBP"]');
 assert.equal(await panel.count(),1,label+' monetary 6M bridge missing in EUR/GBP dossier');
 assert.equal(await panel.locator('.pair-monetary-kpi').count(),2,
  label+' pair pricing must show 1D and 1W separately');
 const pairText=await panel.innerText();
 assert(pairText.includes('Rispetto alla tesi macro.')&&
        pairText.includes('La verifica sul Forex.'),
  label+' source movement must be related to macro and price without false causal claims');
 assert.equal(await panel.locator('[data-pair-open-rates="EURGBP"]').count(),1,
  label+' no way to inspect monetary evidence in Rates Studio');
 await panel.locator('[data-pair-open-rates="EURGBP"]').click();
 await page.waitForFunction(()=>document.querySelector('#content')?.dataset.view==='rates');
 assert.equal(await locator(page,'#rs-country').inputValue(),'EUR',
  label+' pair source leg did not reach Rates');
 assert.equal(await locator(page,'#rs-other').inputValue(),'GBP',
  label+' pair quote leg did not reach Rates');
 assert.equal(await locator(page,'#rates-relative-pricing').count(),1);
 // Changed selection must not leave the previous pair's monetary card attached.
 await route(page,'pairs');
 await chosenPair(page,'USDJPY',label);
 assert.equal(await locator(page,'.pair-monetary-bridge').getAttribute('data-pair-monetary-pair'),
  'USDJPY',label+' pair monetary reading did not follow selection');
 const noPair=await locator(page,'.pair-monetary-bridge').innerText();
 assert(!noPair.includes('Δ6M RELATIVO · EURGBP'),'A selected pair must not retain another pair');
 await chosenPair(page,'EURUSD',label);
 const euroPanel=locator(page,'.pair-monetary-bridge[data-pair-monetary-pair="EURUSD"]');
 assert.equal(await euroPanel.count(),1,label+' EUR/USD source-first monetary card missing');
 assert.equal(await euroPanel.locator('.pair-monetary-kpi').count(),2,
  label+' EUR/USD must have two informative research references');
 const copy=await euroPanel.innerText();
 assert(copy.includes('−2,75 pb')&&copy.includes('11/11/2026')&&copy.includes('12/11/2026'),
  label+' EUR/USD must surface the actual historical common interval instead of two empty 6M cards');
 assert(!copy.includes('non allineato'),
  label+' EUR/USD has data for an archived common period, empty flags cannot dominate');
 await euroPanel.locator('.pair-monetary-source > summary').click();
 assert.equal(await euroPanel.locator('.pair-monetary-links a').count(),4,
  label+' every displayed monetary number needs inspectable source links');
}
async function relative6mJourney(page,label){
 await route(page,'rates');
 await locator(page,'#rs-country').selectOption('EUR');
 await locator(page,'#rs-other').selectOption('GBP');
 const panel=locator(page,'#rates-relative-pricing');
 assert.equal(await panel.count(),1,label+' relative 6M pricing panel missing');
 const firstStatus=await panel.getAttribute('data-rr6-status');
 assert(['SAME_END_REFERENCE_UNVERIFIED','MATCHED_EXACT_INTERVAL','NOT_ALIGNED'].includes(firstStatus),
  label+' EUR/GBP relative status is missing');
 assert((await panel.innerText()).includes(firstStatus==='NOT_ALIGNED'?
  'Non confrontabile':'pb'),label+' relative 6M source evidence not displayed');
 assert.equal(await panel.locator('.rr6-day').count()>0,true,
  label+' source aligned historic 6M differences missing');
 await locator(page,'#rates-pricing-moves [data-rs-pricing-window="1w"]').click();
 assert((await locator(page,'#rates-relative-pricing').innerText()).includes('1 SETTIMANA'),
  label+' 1W relative pricing panel must follow 1W toggle');
 await locator(page,'#rates-pricing-moves [data-rs-pricing-window="1d"]').click();
 await locator(page,'#rs-country').selectOption('USD');
 const newestStatus=await locator(page,'#rates-relative-pricing').getAttribute('data-rr6-status');
 assert(['NOT_ALIGNED','SAME_END_REFERENCE_UNVERIFIED','MATCHED_EXACT_INTERVAL'].includes(newestStatus),
  label+' source-dated USD/GBP relative comparison needs a verification status');
 if(newestStatus==='NOT_ALIGNED')
  assert((await locator(page,'#rates-relative-pricing').innerText()).includes('Non confrontabile'),
   label+' unmatched source dates must never produce a daily spread');
}
async function g8HistoryJourney(page,label){
 await route(page,'rates');
 const history=locator(page,'#rates-pricing-history');
 await history.locator('[data-rs-history-window="14"]').click();
 const selectedCountry=await locator(page,'#rs-country').inputValue();
 assert.equal(await history.getAttribute('data-history-currency'),selectedCountry,
  label+' history must follow the current selected currency, even after prior navigation');
 assert.equal(await locator(page,'#rates-pricing-history [data-rs-history-window="14"]').getAttribute('aria-pressed'),
  'true',label+' historical 14-day window not applied');
 await locator(page,'#rates-pricing-history [data-rate-ccy="EUR"]').click();
 assert.equal(await locator(page,'#rates-pricing-history').getAttribute('data-history-currency'),'EUR',
  label+' EUR history not selected from G8 grid');
 assert((await locator(page,'#rates-pricing-history').innerText()).includes('Futures secondari'),
  label+' EUR historical pricing must retain actual source category');
 await locator(page,'#rates-pricing-history [data-rs-history-window="30"]').click();
 assert.equal(await locator(page,'#rates-pricing-history [data-rs-history-window="30"]').getAttribute('aria-pressed'),
  'true');
 await locator(page,'#rs-country').selectOption('NZD');
 assert((await locator(page,'#rates-pricing-history').innerText()).includes('riferimenti 1D/1W ricostruiti'),
  label+' NZD visual chart needs derived-reference disclosure');
}
async function pricingWindowJourney(page,label){
 await route(page,'rates');
 const desk=locator(page,'#rates-pricing-moves');
 const one=desk.locator('[data-rs-pricing-window="1d"]');
 const week=desk.locator('[data-rs-pricing-window="1w"]');
 assert(await one.count()&&await week.count(),label+' 1D/1W controls missing');
 await week.click();
 assert.equal(await locator(page,'#rates-pricing-moves').getAttribute('data-pricing-window'),
  '1w',label+' weekly changes not displayed');
 await locator(page,'#rates-pricing-moves [data-rs-pricing-window="1d"]').click();
 assert.equal(await locator(page,'#rates-pricing-moves').getAttribute('data-pricing-window'),
  '1d',label+' daily changes not restored');
 await locator(page,'#rs-country').selectOption('EUR');
 assert.equal(await locator(page,'#rates-pricing-moves').getAttribute('data-pricing-kind'),
  'FUTURES SECONDARI',label+' EUR futures mislabeled OIS');
 assert((await locator(page,'#rates-pricing-moves').innerText()).includes('Nessuna curva artificiale'),
  label+' staggered EUR quotes cannot be connected');
 await locator(page,'#rs-country').selectOption('GBP');
 assert.equal(await locator(page,'#rates-pricing-moves').getAttribute('data-pricing-kind'),
  'OIS',label+' GBP official OIS lost');
}
async function calendarResearchJourney(page,label){
 await route(page,'news');
 const event=locator(page,'#macro-calendar .cal-event').first();
 assert(await event.count(),label+' no calendar macro event');
 for(const mode of ['rates','currencies','pairs']){
  assert(await event.locator('[data-cal-research="'+mode+'"]').count(),
   label+' event missing '+mode+' link');
 }
 await event.locator('[data-cal-research="rates"]').click();
 await page.waitForFunction(()=>document.querySelector('#content')?.dataset.view==='rates');
 await route(page,'news');
 await locator(page,'#macro-calendar [data-cal-research="currencies"]').first().click();
 await page.waitForFunction(()=>document.querySelector('#content')?.dataset.view==='currencies');
 await route(page,'news');
 await locator(page,'#macro-calendar [data-cal-research="pairs"]').first().click();
 await page.waitForFunction(()=>document.querySelector('#content')?.dataset.view==='pairs'&&
  document.querySelector('.pairs-reading-compact'));
 assert.equal(await locator(page,'.pairs-reading-compact').count(),1,
  label+' macro-event pair link did not open a real FX dossier');
}
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try{
  const reports=[];
  for(const viewport of [{width:1440,height:900},{width:390,height:844}]){
   const label=viewport.width>700?'desktop':'mobile';
   const page=await browser.newPage({viewport,deviceScaleFactor:1});
   const errors=[];
   page.on('pageerror',err=>errors.push(String(err)));
   try{
    const resp=await page.goto(BASE,{waitUntil:'domcontentloaded',timeout:30000});
    assert(resp&&resp.ok(),label+' page HTTP status');
    await page.waitForFunction(()=>/\d+\/\d+ fonti caricate/.test(
     document.querySelector('#sidebar-feed')?.textContent||''),null,{timeout:25000});
    const loaded=await locator(page,'#sidebar-feed').innerText();
    const count=loaded.match(/(\d+)\/(\d+) fonti caricate/);
    assert(count&&Number(count[1])===Number(count[2])&&Number(count[2])>=18,
     label+' missing source(s): '+loaded);
    if(label==='mobile'){
     await locator(page,'#menu-toggle').click();
     assert.equal(await locator(page,'#menu-toggle').getAttribute('aria-expanded'),'true',
      'Mobile navigation did not open');
     await locator(page,'#nav [data-route="pairs"]').click();
     await route(page,'pairs');
     assert.equal(await locator(page,'#menu-toggle').getAttribute('aria-expanded'),'false',
      'Mobile navigation did not close after selection');
    }
    const inspected=[];
    for(const key of Object.keys(routes))inspected.push(await inspectRoute(page,label,key));
    await g8Choice(page,label);
    await pairJourney(page,label);
    await pairMonetaryJourney(page,label);
    await calendarResearchJourney(page,label);
    await pricingWindowJourney(page,label);
    await g8HistoryJourney(page,label);
    await relative6mJourney(page,label);
    assert.equal(errors.length,0,label+' browser errors: '+errors.slice(0,4).join(' | '));
    await locator(page,'#content').screenshot({path:evidence+'/'+label+'-pair-journey.png'});
    reports.push({label,sourceCount:Number(count[1]),routes:inspected,interaction:'PASS'});
   }finally{await page.close();}
  }
  fs.writeFileSync(evidence+'/current-journey-summary.json',JSON.stringify(reports,null,2));
  console.log('FXQUANT_NEXT_CURRENT_JOURNEY_PASS',JSON.stringify(reports.map(x=>({
   label:x.label,sourceCount:x.sourceCount,routeCount:x.routes.length,interaction:x.interaction
  }))));
 }finally{await browser.close();}
})().catch(e=>{console.error('FXQUANT_NEXT_QA_FAIL',e.stack||e);process.exit(1);});
