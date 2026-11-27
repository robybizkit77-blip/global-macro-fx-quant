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
const priceModel=require('../site/fx-quant-v2/next/macro-strength-estimated-v1.js');
const rankings=require('../site/fx-quant-v2/next/pair-rankings.js');
const library=require('../site/fx-quant-v2/next/research-library.js');
const {riskCheck}=require('../site/fx-quant-v2/next/fx-driver-market-audit.js');
const {file:dailyFile}=require('../site/fx-quant-v2/next/reports/daily-latest.json');
const {files:weeklyFiles}=require('../site/fx-quant-v2/next/reports/weekly-latest.json');
const reportDir='site/fx-quant-v2/next/reports';
const BASE=process.env.FXQN_BASE||'http://127.0.0.1:8000/site/fx-quant-v2/next/index.html';
const routes={
 overview:'Panoramica',currencies:'Valute G8',pairs:'Coppie FX',
 macro:'Scenario macro',banks:'Banche Centrali',rates:'Tassi & OIS',liquidity:'Liquidità & Credito',cot:'COT',risk:'Rischio',
 news:'Notizie',library:'Research Library'
};
const evidence='fxquant-next-browser-evidence';
fs.mkdirSync(evidence,{recursive:true});
const locator=(page,css)=>page.locator(css);
const readSource=path=>JSON.parse(fs.readFileSync(path,'utf8'));
const nativeLiquidity=readSource('live_data/sections/NATIVE_LIQ_DATA.json');
const nativeEvidence=(text,ccy,role)=>{
 const row=nativeLiquidity[ccy][role];
 const value=Number(row.last_value).toLocaleString('it-IT',{minimumFractionDigits:2,maximumFractionDigits:2});
 return text.includes('Ultimo '+row.last_date+' · '+value);
};
const priceEvidence=priceModel.evaluate({
 observed:readSource('site/control-room-preview/macro-v3-current-evidence.json'),
 prices:readSource('live_data/sections/ECB_G8_PRICE_HISTORY.json'),
 ois:readSource('site/fx-quant-v2/ois-pricing-snapshot.json'),
 rates:readSource('live_data/sections/NATIVE_RATES_DATA.json'),
 model:readSource('live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json'),
 now:new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Rome',year:'numeric',month:'2-digit',day:'2-digit'}).format(),
 rankingFn:rankings.currencyRanking
});
async function route(page,key){
 await page.evaluate(key=>{location.hash='#'+key},key);
 await page.waitForFunction(({key,title})=>
  document.querySelector('#content')?.dataset.view===key&&
  document.querySelector('#crumb-page')?.textContent?.trim()===title,
  {key,title:routes[key]},{timeout:20000});
}
async function firstScreenJumps(page,label,targets){
 const height=page.viewportSize().height;
 for(const id of targets){
  const button=locator(page,'[data-section-jump="'+id+'"]');
  const bounds=await button.boundingBox();
  assert(bounds&&bounds.y>=0&&bounds.y+bounds.height<=height+1,
   label+' access to '+id+' must fit in the first screen');
 }
 for(const id of targets){
  await locator(page,'[data-section-jump="'+id+'"]').press('Enter');
  await page.waitForFunction(id=>document.activeElement?.id===id,id);
  const bounds=await locator(page,'#'+id).boundingBox();
  assert(bounds&&bounds.y>=0&&bounds.y<height,label+' jump did not reveal '+id);
  await page.evaluate(()=>window.scrollTo({top:0,behavior:'instant'}));
 }
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
  const homeDates=locator(page,'.home-reference-dates');
  assert.deepEqual(await homeDates.locator('dt').allTextContents(),
   ['Fixing BCE','Governativi USA','Prezzi delle 28 coppie'],label+' Home dates must name their source');
  assert.equal(await locator(page,'[data-home-catalyst]').count(),1,
   label+' Home must show the current calendar separately from the archived analysis');
  assert.equal(await locator(page,'.morning-dashboard').count(),1,'Dated morning desk must stay available');
  assert.equal(await locator(page,'.morning-lead h1').count(),1,'Morning lead missing');
  const hourly=locator(page,'.hourly-market-desk');
  if(!await hourly.count()){
   assert.equal(await locator(page,'.morning-archive-note').count(),1,
    'Current or archival morning edition must identify its date/status');
   assert.equal(await locator(page,'.morning-fx-pulse').count(),1,
    'Source-dated G8 and pair research must remain attached to the morning view');
  }
  if(await hourly.count()){
   const chart=hourly.locator('.hourly-opening-chart');
   if(await chart.count()){
    assert(await hourly.evaluate(root=>root.querySelector('.hourly-opening-chart')
     .compareDocumentPosition(root.querySelector('[data-home-catalyst]'))&Node.DOCUMENT_POSITION_FOLLOWING),
     label+' the event must follow the opening chart');
   }
   assert.equal(await hourly.locator('.hourly-edition-time b').innerText(),'Ultima analisi pubblicata');
   assert.equal(await hourly.locator('.hourly-edition-check b').innerText(),'Ultimo controllo delle fonti');
   const fonts=await hourly.evaluate(root=>{
    const px=selector=>{
     const el=root.querySelector(selector);
     return el?Number.parseFloat(getComputedStyle(el).fontSize):null;
    };
    return {
     headline: px('.hourly-hero .morning-deck'),
     decision: px('.hourly-decision-card p'),
     section: px('.hourly-section-head p'),
     story: px('.hourly-desk-story p')
    };
   });
   for(const [key,min] of Object.entries({headline:14.5,decision:13,section:12,story:13})){
    if(fonts[key]!==null)assert(fonts[key]>=min,
     label+' premium Home '+key+' copy became too small: '+fonts[key]+'px');
   }
  }
  const recalc=locator(page,'#fx-recalc-pulse');
  assert.equal(await recalc.count(),1,label+' Home must show one G8/28 recalculation receipt');
  const recalculationState=await recalc.getAttribute('data-recalc-state');
  assert(['same','changed','baseline','UNVERIFIED'].includes(recalculationState),
   label+' Home receipt must have a supported dated-evidence status');
  if(recalculationState==='UNVERIFIED'){
   assert.match(await recalc.innerText(),/non è attestato|ricevuta.*non valida/i,
    label+' missing or misdated proof must not be reported as a verified recalculation');
  }else{
   assert.match(await recalc.innerText(),/G8 \/ 28 COPPIE/i,
    label+' research scope must be explicit');
   const audit=recalc.locator('details.fx-recalc-details');
   assert.equal(await audit.count(),1,label+' detailed provenance must be collapsible');
   assert.equal(await audit.getAttribute('open'),null,label+' detailed audit starts collapsed');
   await audit.locator('summary').click();
   assert.equal(await audit.locator('a.fx-recalc-proof').count(),1,
    label+' original audit proof must be available');
   await audit.locator('summary').click();
  }
  const monetaryHome=locator(page,'#home-pricing-proof');
  assert.equal(await monetaryHome.count(),1,label+' Home monetary-to-FX chart missing');
  const homeCardCount=await monetaryHome.locator('.home-pricing-proof-card').count();
  assert(homeCardCount>=1&&homeCardCount<=2,
   label+' must show only one or two evidence-backed FX comparisons, never placeholders');
  assert.equal(await monetaryHome.locator('[data-home-pricing-available="false"]').count(),0,
   label+' visible Home still contains unavailable comparison rows');
  assert.equal(await monetaryHome.locator('.home-pricing-proof-sources nav a').count(),3,
   label+' must link original public monetary, futures and BCE observations');
 }else if(key==='currencies'){
  assert.equal(await locator(page,'#orient-strength-board .strength-row').count(),8,
   'Exactly eight estimated G8 first-read choices required');
  assert.equal(await locator(page,'.strength-first-reading > p').count(),3,
   'Country first read must connect supporting evidence, opposing evidence and price');
  assert.match(await locator(page,'.strength-first-reading').innerText(),/Cosa va\.[\s\S]*Cosa frena\./);
  assert.match(await locator(page,'.strength-first-watch').innerText(),/Cosa guardare\./);
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
  await firstScreenJumps(page,label,['fx-rank-g8','fx-rank-top','fx-rank-all']);
 }else if(key==='banks'){
  assert.equal(await locator(page,'#central-bank-studio [data-bank-country]').count(),8,
   label+' all eight central-bank country choices required');
  assert.equal(await locator(page,'.drivers-want-can .drivers-analysis').count(),2,
   label+' official WANT and macro CAN must be separated');
  const story=locator(page,'.drivers-bank-story');
  assert.deepEqual(await story.locator('h3').allTextContents(),['Cosa va','Cosa frena','Cosa guardare']);
  assert.doesNotMatch(await story.innerText(),/punti base|\d+(?:,\d+)?\s*%|\bOIS\b/,
   label+' technical figures must follow the plain bank first read');
  const policy=locator(page,'.drivers-bank-sources .drivers-lead');
  assert(!await policy.isVisible(),label+' exact rate and decision date must be collapsed initially');
  assert.equal(await locator(page,'.drivers-fold .drivers-fact').count(),3,
   label+' dated 3M/6M/12M pricing audit must remain accessible');
  assert.equal(await locator(page,'.drivers-links [data-bank-open]').count(),2,
   label+' policy must link directly to source rates and currency');
  assert.equal(await locator(page,'.drivers-market-audit .drivers-market-item').count(),2,
   label+' bank policy must link monetary repricing with source-dated FX validation');
 }else if(key==='liquidity'){
  assert.equal(await locator(page,'#liquidity-studio [data-liq-country]').count(),8,
   label+' all eight G8 liquidity choices required');
  if(label==='mobile'){
   for(const button of await locator(page,'#liquidity-studio [data-liq-country]').all()){
    const box=await button.boundingBox();
    assert(box&&box.height>=44&&box.y>=0&&box.y+box.height<=page.viewportSize().height,
     'All G8 liquidity buttons must be reachable on the first screen at mobile size');
   }
  }
  assert.equal(await locator(page,'.drivers-facts .drivers-fact').count(),3,
   label+' liquidity, credit and lending conditions must be separate');
  assert.equal(await locator(page,'.drivers-chart-grid .drivers-chart').count(),2,
   label+' both source-dated trend charts required');
  for(const id of ['liquidity-dossier','liquidity-charts','liquidity-market']){
   await locator(page,'.liq-section-jumps [data-section-jump="'+id+'"]').press('Enter');
   assert.equal(await page.evaluate(()=>document.activeElement?.id),id,label+' liquidity jump must focus its destination');
  }
  assert.equal(await locator(page,'#liquidity-charts .drivers-chart').count(),2);
  assert.equal(await locator(page,'#liquidity-market .liq-first-spread').count(),2);
  const liquidSources=locator(page,'.drivers-source-provenance-fold');
  assert.equal(await liquidSources.getAttribute('open'),null,label+' liquidity sources start collapsed');
  assert.match(await liquidSources.textContent(),/Copertura storica/);
  assert.equal(await locator(page,'.drivers-us-official').isVisible(),true,
   label+' dated Fed evidence belongs in the first reading');
  assert(await locator(page,'#liquidity-dossier').evaluate(dossier=>{
   const evidence=dossier.querySelector('.drivers-us-official');
   const reading=dossier.querySelector('.drivers-story');
   return evidence&&reading&&Boolean(evidence.compareDocumentPosition(reading)&Node.DOCUMENT_POSITION_FOLLOWING);
  }),label+' source-dated evidence must precede the FX interpretation');
  assert.equal(await locator(page,'.drivers-market-audit .drivers-market-item').count(),2,
   label+' liquidity hypothesis must be checked against dated 6M and FX price evidence');
 }else if(key==='rates'){
  const ratesFirstRead=await page.evaluate(()=>{
   const country=document.querySelector('.rates-country-strip');
   const chf=country?.querySelector('[data-rate-ccy="CHF"]');
   const snapshot=document.querySelector('.rates-stats');
   const government=document.querySelector('#rates-government');
   const editorial=document.querySelector('.research-essay');
   const top=element=>element?element.getBoundingClientRect().top+scrollY:null;
   return {countries:country?.querySelectorAll('button').length,selectorTop:top(country),
    chfTop:top(chf),chfHeight:chf?.getBoundingClientRect().height,
    snapshotTop:top(snapshot),governmentTop:top(government),editorialTop:top(editorial)};
  });
  assert.equal(ratesFirstRead.countries,8,label+' Rates selector must show all eight currencies');
  assert(ratesFirstRead.selectorTop<ratesFirstRead.snapshotTop&&
   ratesFirstRead.snapshotTop<ratesFirstRead.editorialTop,label+' the Rates snapshot must precede the desk reading');
  assert(ratesFirstRead.snapshotTop<ratesFirstRead.governmentTop&&
   ratesFirstRead.governmentTop<ratesFirstRead.editorialTop,label+' the government chart must precede the desk reading');
  assert(ratesFirstRead.chfTop+ratesFirstRead.chfHeight<=page.viewportSize().height,
   label+' CHF in the Rates selector must fit in the first screen');
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
  assert((await locator(page,'.rates-country-strip button').allTextContents()).every(text=>text.includes('2Y')),
   label+' the eight country tiles must identify the quoted maturity');
  assert.equal(await locator(page,'#rates-expected #rates-pricing-history, #rates-expected #rates-pricing-moves').count(),2,
   label+' monetary moves and history must share a section');
  assert.equal(await locator(page,'#rates-fx #rates-relative-pricing, #rates-fx .rates-fx-handoff').count(),2,
   label+' relative monetary and FX evidence must share a section');
  await firstScreenJumps(page,label,['rates-government','rates-expected','rates-fx']);
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
async function homeMoneyJourney(page,label){
 await route(page,'overview');
 const proof=locator(page,'#home-pricing-proof');
 assert.equal(await proof.count(),1,label+' source-backed Home pricing reading missing');
 const cards=proof.locator('.home-pricing-proof-card');
 const count=await cards.count();
 assert(count>=1&&count<=2,label+' Home needs one or two verified FX examples');
 assert.equal(await proof.locator('[data-home-pricing-available="false"]').count(),0,
  label+' unavailable 5/20-session placeholders must never be visible');
 const visible=await proof.innerText();
 assert(!/Non disponibile|non è verificabile/i.test(visible),
  label+' Home monetary comparison still discusses unavailable windows');
 const archive=proof.locator('details[data-home-pricing-archive]');
 if(await archive.count()){
  assert.equal(await archive.locator('.home-pricing-proof-card:visible').count(),0,
   label+' archived comparisons must start closed');
  await archive.locator(':scope > summary').click();
 }
 const symbols=await cards.evaluateAll(rows=>rows.map(row=>row.dataset.homePricingPair));
 assert(symbols.every(symbol=>/^[A-Z]{6}$/.test(symbol)),label+' expected validated pair symbols');
 const usdIndex=symbols.findIndex(symbol=>symbol.includes('USD'));
 if(count===2){
  assert(usdIndex>=0,label+' the two examples include one USD cross');
  const withUsd=symbols[usdIndex],withoutUsd=symbols[1-usdIndex];
  assert(!withoutUsd.includes('USD'),label+' the second example must avoid USD');
  const first=new Set([withUsd.slice(0,3),withUsd.slice(3)]);
  assert(![withoutUsd.slice(0,3),withoutUsd.slice(3)].some(x=>first.has(x)),
   label+' two selected comparisons unnecessarily repeat a currency');
 }
 for(let i=0;i<count;i++){
  const card=cards.nth(i);
  const copy=await card.innerText();
  assert(copy.includes('Δ RELATIVO 6M')&&copy.includes('CAMBIO'),
   label+' monetary and fixing returns must share observation dates');
  const fold=card.locator('details.home-pricing-proof-multi');
  assert.equal(await fold.count(),1,
   label+' selected FX pair must have at least one real longer horizon');
  await fold.locator(':scope > summary').click();
  const windows=fold.locator('.home-pricing-proof-multi-row');
  const n=await windows.count();
  assert(n>=1&&n<=2,label+' expected one or two verified 5/20-session rows');
  const observed=[];
  for(let j=0;j<n;j++){
   const row=windows.nth(j),period=await row.getAttribute('data-home-pricing-sessions');
   assert(['5','20'].includes(period),label+' unexpected horizon: '+period);
   observed.push(period);
   assert.equal(await row.getAttribute('data-home-pricing-available'),'true',
    label+' a shown horizon must have valid dated 6M/FX evidence');
   const text=(await row.innerText()).replace(/\s+/g,' ');
   assert(/Riferimento \d{2}\/\d{2}\/\d{4} · fine \d{2}\/\d{2}\/\d{4}/.test(text),
    label+' missing source-aligned date interval at '+period+' sessions');
   assert(/Δ 6M.+pb.+FX.+%/.test(text),
    label+' longer horizon missing numeric 6M/Forex comparison');
  }
  assert.equal(new Set(observed).size,n,label+' repeated 5/20-session horizon');
  const listed=await fold.locator(':scope > summary').innerText();
  for(const period of observed)assert(listed.includes(period),
   label+' accordion label omits an available horizon');
 }
 await proof.screenshot({path:evidence+'/'+label+'-verified-money-fx.png'});
 await proof.locator('.home-pricing-proof-sources:not([data-home-pricing-archive]) > summary').click();
 assert.equal(await proof.locator('.home-pricing-proof-sources nav a').count(),3);
 const pairIndex=usdIndex<0?0:usdIndex;
 const pair=symbols[pairIndex];
 await cards.nth(pairIndex).locator('[data-command]').click();
 await page.waitForFunction(k=>document.querySelector('#content')?.dataset.view==='pairs'&&
  document.querySelector('.pair-monetary-bridge')?.dataset.pairMonetaryPair===k,pair);
 assert.equal(await locator(page,'.pair-monetary-bridge').getAttribute('data-pair-monetary-pair'),
  pair,label+' no matching pair dossier opened from Home');
}
async function g8Choice(page,label){
 await route(page,'currencies');
 const audit=locator(page,'details.strength-evidence-fold');
 const headline=locator(page,'#content > .page-hero h1');
 const lead=locator(page,'#content > .page-hero .lead');
 assert.equal(await headline.count(),1,label+' currency judgement belongs in the first screen');
 assert.equal(await locator(page,'#content > .research-essay').count(),0,
  label+' the detailed editorial must follow the country judgement');
 assert.doesNotMatch(await lead.innerText(),/fixing|futures|\d+(?:,\d+)?\s*(?:%|pb\b)/i);
 assert(!(await audit.evaluate(el=>el.open)),label+' source audit opens without request');
 assert(!await locator(page,'#g8-pricing-proof').isVisible(),label+' numerical pricing belongs to the evidence fold');
 await audit.locator(':scope > summary').click();
 assert(await audit.evaluate(el=>el.open),label+' source audit did not open');
 assert.equal(await audit.locator('.strength-card').count(),4,label+' full country evidence missing');
 await locator(page,'#orient-strength-board [data-cs-country="NZD"]').click();
 await page.waitForFunction(()=>
  document.querySelector('.strength-row.selected')?.dataset.csCountry==='NZD');
 assert(await audit.evaluate(el=>el.open),label+' country selection closed user-opened audit');
 const note=await locator(page,'#orient-strength-focus').innerText();
 assert(note.includes('NZD'),label+' NZD reading did not update');
 assert.match(await headline.innerText(),/dollaro neozelandese|NZD/i,
  label+' opening judgment did not follow the selected currency');
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
 const jump=locator(page,'#orient-strength-board [data-cs-focus]');
 assert.equal(await jump.count(),1,label+' G8 ranking lost its contextual narrative path');
 assert((await jump.innerText()).includes('EUR'),label+' G8 narrative CTA did not follow selected EUR');
 await jump.click();
 await page.waitForFunction(()=>document.activeElement?.id==='orient-strength-focus');
 assert((await locator(page,'#orient-strength-focus').getAttribute('tabindex'))==='-1',
  label+' currency analysis does not support keyboard focus');
 assert.equal(await locator(page,'#orient-strength-board .strength-row.selected').count(),1,
  label+' jumping to country analysis must preserve original selection');
 assert(note.includes('Cosa guardare.') &&
   note.includes('NZD/USD') && note.includes('AUD/NZD'),
  label+' NZD macro/rates proxy must lead to two FX monitoring instruments');
}
async function scenarioMacroJourney(page,label){
 await route(page,'macro');
 const shortcuts=locator(page,'.rd-country-access [data-ms-country]');
 assert.equal(await shortcuts.count(),8,label+' Macro opening must link to all eight dossiers');
 for(const code of ['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD']){
  await locator(page,'.rd-country-access [data-ms-country="'+code+'"]').press('Enter');
  assert.equal(await page.evaluate(()=>document.activeElement?.id),'rd-country',
   label+' the dossier shortcut must move keyboard focus to the dossier');
  assert.equal(await locator(page,'.rd-country-tabs [data-ms-country="'+code+'"]').getAttribute('aria-pressed'),'true');
 }
 const countries=locator(page,'.rd-country-tabs [data-ms-country]');
 assert.equal(await countries.count(),8,label+' Scenario macro must offer all G8 economies');
 assert.equal(await locator(page,'#content > .research-essay').count(),0,label+' technical essay must follow the primary reading');
 await locator(page,'.rd-country-tabs [data-ms-country="USD"]').click();
 const usd=await locator(page,'.rd-country-body').innerText();
 const usdHeading=await locator(page,'#rd-country .rd-section-head').innerText();
 assert.match(usdHeading,/Stati Uniti/);
 const euroChoice=locator(page,'.rd-country-tabs [data-ms-country="EUR"]');
 await euroChoice.click();
 const eur=await locator(page,'.rd-country-body').innerText();
 assert.match(await locator(page,'#rd-country .rd-section-head').innerText(),/Area euro/);
 assert.notEqual(usd,eur,label+' the first read must follow the selected economy');
 assert.equal(await euroChoice.getAttribute('aria-pressed'),'true');
 const thermometers=locator(page,'[data-macro-panel="thermometers"]');
 assert(!await thermometers.evaluate(el=>el.open),label+' supporting research must be closed initially');
 await thermometers.locator(':scope > summary').click();
 const hero=locator(page,'.macro-country-hero');
 assert.match(await hero.innerText(),/Area euro/);
 const proof=hero.locator('.macro-evidence');
 assert(!await proof.evaluate(el=>el.open),label+' data and sources must be closed initially');
 await proof.locator(':scope > summary').click();
 assert.equal(await proof.locator('.macro-temperature').count(),2);
 assert(await proof.locator('.research-essay').isVisible(),label+' detailed analysis is missing');
 const explorer=locator(page,'[data-macro-panel="explorer"]');
 assert(!await explorer.evaluate(el=>el.open),label+' chart research is optional');
 await explorer.locator(':scope > summary').click();
 assert(await locator(page,'.macro-main-chart .chart').isVisible(),label+' indicator chart is missing');
}
async function macroDriversJourney(page,label){
 await route(page,'banks');
 await locator(page,'[data-bank-country="GBP"]').click();
 assert.equal(await locator(page,'[data-bank-country="GBP"]').getAttribute('aria-pressed'),'true',
  label+' selecting BoE did not update bank dossier');
 assert((await locator(page,'.drivers-selection h2').innerText()).includes('Bank of England'),
  label+' bank dossier did not follow selection');
 const bankStory=await locator(page,'.drivers-bank-story').innerText();
 assert.match(bankStory,/EUR\/GBP/);
 const bankSources=locator(page,'.drivers-bank-sources');
 assert.equal(await bankSources.getAttribute('open'),null,label+' pricing detail starts collapsed');
 await bankSources.locator(':scope > summary').click();
 const bank=await bankSources.innerText();
 assert(bank.includes('WANT')&&bank.includes('CAN')&&bank.includes('Tasso ufficiale')&&
  bank.includes('COSA PREZZA IL MERCATO')&&bank.includes('CONFERMA SUL FOREX'),
  label+' policy decision, monetary pricing and FX model must remain distinct');
 assert(bank.includes('OIS'),'BoE pricing must name the instrument');
 assert.match(bank,/Tasso ufficiale .*decisione .*prossima riunione/i);
 assert.match(await bankSources.innerText(),/3M \/ RIFERIMENTO DI MERCATO/);
 assert.match(await bankSources.innerText(),/VIX.*HY/);
 assert.equal(await bankSources.locator('a').filter({hasText:'Comunicazione ufficiale'}).count(),1,
  label+' verified BoE release link must be available');
 await locator(page,'[data-bank-open="rates"]').click();
 await page.waitForFunction(()=>document.querySelector('#content')?.dataset.view==='rates');
 assert.equal(await locator(page,'#rs-country').inputValue(),'GBP',
  label+' bank-to-rates handoff lost selected currency');
 await route(page,'banks');
 await locator(page,'[data-bank-country="NZD"]').click();
 await locator(page,'[data-bank-open="currencies"]').click();
 await page.waitForFunction(()=>document.querySelector('#content')?.dataset.view==='currencies');
 await route(page,'liquidity');
 const usH8=locator(page,'.drivers-us-official');
 assert.equal(await usH8.count(),1,
  label+' Fed H8 validated source must appear in USD dossier without overwriting native credit');
 const usH8Text=await usH8.innerText();
 assert(usH8Text.includes('TOTBKCR')&&usH8Text.includes('FRED')&&
        usH8Text.includes('titoli bancari'),
  label+' USD source identity and bank-credit stock interpretation are missing');
 const officialSloos=locator(page,'.drivers-us-sloos');
 const sloosSource=await page.evaluate(()=>window.FXQuantUSBanksCreditResearch?.lending_standards);
 assert.equal(sloosSource?.series_id,'DRTSCILM',label+' SLOOS must target large and middle-market firms');
 const [sloosPeriod,sloosNet]=sloosSource.observations.at(-1);
 const edition=new Intl.DateTimeFormat('it-IT',{month:'long',year:'numeric',timeZone:'UTC'})
  .format(new Date(sloosPeriod+'T12:00:00Z'));
 const netText=(sloosNet>0?'+':sloosNet<0?'−':'')+
  Math.abs(sloosNet).toLocaleString('it-IT',{minimumFractionDigits:1,maximumFractionDigits:1})+'%';
 assert((await officialSloos.innerText()).includes('Nell’edizione di '+edition+' il saldo netto è '+netText),
  label+' USD must show the actual period and net percentage for the verified survey');
 assert.equal(await officialSloos.locator('a').getAttribute('href'),
  'https://fred.stlouisfed.org/series/DRTSCILM',label+' SLOOS source link');
 const usSloos=locator(page,'[data-liq-role="conditions"]');
 const sloosGate=await page.evaluate(()=>window.FXQuantLiquiditySourcePolicy.check('USD','conditions'));
 assert.equal(sloosGate.ready,true,label+' reviewed official DRTSCILM contract must be mapped');
 assert.equal(await usSloos.getAttribute('data-source-safety'),'mapped',
  label+' certified USD SLOOS must be available');
 const usSloosText=await usSloos.textContent();
 assert(usSloosText.includes('CONTRATTO MAPPATO')&&!usSloosText.includes('Dato sospeso'),
  label+' source registry must explain verified status');
 const sourceContract=locator(page,'.drivers-source-provenance-fold');
 await sourceContract.locator('summary').click();
 assert(await sourceContract.evaluate(el=>el.open),label+' registry/source provenance cannot open');
 assert(await usSloos.isVisible(),label+' the provenance disclosure must reveal mapped SLOOS');
 await locator(page,'[data-liq-country="EUR"]').click();
 assert.equal(await officialSloos.count(),0,label+' Fed SLOOS belongs only in the USD dossier');
 const officialECB=locator(page,'.drivers-eur-official');
 assert.equal(await officialECB.count(),1,
  label+' certified ECB NFC series must be visible in EUR research without replacing native credit');
 const ecbText=await officialECB.innerText();
 assert(ecbText.includes('BCE')&&ecbText.includes('Il cumulato di due mesi')&&
        ecbText.includes('revisioni possibili')&&ecbText.includes('Fonte: BCE'),
  label+' EUR credit stock requires dated source and persistence narrative');
 const eurNative=await locator(page,'[data-liq-role="credit"]').textContent();
 assert(nativeEvidence(eurNative,'EUR','credit'),
  label+' ECB research must not overwrite the EUR canonical credit value');
 await locator(page,'[data-liq-country="AUD"]').click();
 assert.equal(await locator(page,'.drivers-aud-official').count(),1,
  label+' RBA adjusted business credit growth must be visible in AUD dossier');
 const audSource=await locator(page,'.drivers-aud-official').innerText();
 assert(audSource.includes('RBA')&&audSource.includes('D2')&&
        audSource.includes('pubblicato')&&audSource.includes('rotture statistiche'),
  label+' AUD card must separate official break-adjusted growth, publication date and D2 stock');
 const audES=locator(page,'.drivers-aud-es-bridge');
 assert.equal(await audES.count(),1,
  label+' RBA ES reserves must appear within the existing AUD editorial dossier');
 const audESPeriod=await page.evaluate(()=>window.FXQuantAUDESBalancesResearch?.source_period);
 const audESText=await audES.innerText();
 assert(audESPeriod&&audESText.includes('SECONDO CANALE, NON SECONDA CONFERMA')&&
        audESText.includes('bilancio settimanale RBA')&&
        audESText.includes('valore precedente implicito')&&
        audESText.includes(audESPeriod),
  label+' current RBA ES weekly evidence must stay distinct from credit growth and FX');
 const audCanonical=await locator(page,'[data-liq-role="credit"]').textContent();
 assert(nativeEvidence(audCanonical,'AUD','credit'),
  label+' AUD native credit stock must not be replaced by research source');
 const f7=await page.evaluate(()=>window.FXQuantAUDBusinessCreditGrowthResearch?.lending_rate_proxy);
 const f7Block=locator(page,'[aria-label="Costo credito imprese Australia F7"]');
 assert(f7&&await f7Block.count()===1,label+' F7 funding cost source missing');
 const f7Text=await f7Block.innerText();
 assert(f7Text.includes(f7.latest_observation)&&f7Text.includes('non degli standard di concessione'),label+' F7 cost proxy not distinguished');
 await locator(page,'[data-liq-country="NZD"]').click();
 const c60=await page.evaluate(()=>window.FXQuantNZDRBNZLiquidity?.credit_conditions);
 const c60Block=locator(page,'[aria-label="Indagine C60 Nuova Zelanda"]');
 assert(c60&&await c60Block.count()===1,label+' C60 survey source missing');
 const c60Text=await c60Block.innerText();
 assert(c60Text.includes(c60.latest_observation)&&c60Text.includes(c60.released)&&c60Text.includes('disponibilità e domanda sono misure distinte'),label+' C60 survey actual period and separate demand');
 await locator(page,'[data-liq-country="JPY"]').click();
 const bojCreditCard=locator(page,'.drivers-jpy-official');
 assert.equal(await bojCreditCard.count(),1,
  label+' official JPY credit research must be visible in the JPY country dossier');
 const bojSrc=await page.evaluate(()=>window.FXQuantJPYBankCreditResearch);
 assert.equal(bojSrc?.series_id,'DLCLAEDBLTTO',
  label+' BoJ MD11 official research source not loaded');
 const bojText=await bojCreditCard.innerText();
 const yenBillions=n=>Number(n/10).toLocaleString('it-IT',{minimumFractionDigits:2,maximumFractionDigits:2});
 assert(bojText.includes(bojSrc.last_observation)&&
        bojText.includes(yenBillions(bojSrc.values.at(-1)))&&
        bojText.includes('USD/JPY')&&bojText.includes('JGB/UST')&&
        bojText.includes('non sono nuovi prestiti'),
  label+' JPY credit stock, economic limitations and Forex confirmation missing');
 const jpyNative=await locator(page,'[data-liq-role="credit"]').textContent();
 assert(nativeEvidence(jpyNative,'JPY','credit'),
  label+' official JPY research must not overwrite the historical canonical credit record');
 await locator(page,'[data-liq-country="GBP"]').click();
 const officialBoE=locator(page,'.drivers-gbp-official');
 assert.equal(await officialBoE.count(),1,
  label+' BoE official reserves research must appear in GBP country view');
 const boeText=await officialBoE.innerText();
 const boeSources=await page.evaluate(()=>({
  reserves:window.FXQuantGBPBoEReservesResearch,
  secured:window.FXQuantGBPBoESecuredCreditResearch
 }));
 assert.equal(boeSources.reserves?.series_id,'RPWB56A',
  label+' official reserve source script has not loaded');
 assert.equal(boeSources.secured?.series_id,'LPMVTYI',
  label+' official mortgage growth source script has not loaded');
 const itAmount=n=>Number(n).toLocaleString('it-IT',{minimumFractionDigits:0,maximumFractionDigits:0});
 const itRate=n=>Number(n).toLocaleString('it-IT',{minimumFractionDigits:1,maximumFractionDigits:1});
 assert(boeText.includes(itAmount(boeSources.reserves.latest_balance_million_gbp))&&
        boeText.includes(boeSources.reserves.published_on)&&
        boeText.includes('RPWB56A')&&boeText.includes('EUR/GBP'),
  label+' GBP reserve stock must reflect the latest issuer publication and relative FX check');
 const gbpNative=await locator(page,'[data-liq-role="liquidity"]').textContent();
 assert(nativeEvidence(gbpNative,'GBP','liquidity'),
  label+' GBP research must not silently overwrite historical native reserves');
 const householdCredit=locator(page,'.drivers-gbp-credit-bridge');
 assert.equal(await householdCredit.count(),1,
  label+' BoE secured lending growth must be visible inside the existing GBP source dossier');
 const secured=await householdCredit.innerText();
 assert(secured.includes('LPMVTYI')&&
        secured.includes(itRate(boeSources.secured.values.at(-1))+'%')&&
        secured.includes(itRate(boeSources.secured.values.at(-2))+'%')&&
        secured.includes('punti percentuali')&&
        secured.includes(boeSources.secured.last_observation),
  label+' verified GBP annual household credit must follow current BoE source values and date');
 if(boeSources.secured.last_observation==='2026-09')
  assert(secured.includes('Money and Credit'),
   label+' September credit interpretation must link the issuer economic release');
 const gbpOldCredit=await locator(page,'[data-liq-role="credit"]').textContent();
 assert(nativeEvidence(gbpOldCredit,'GBP','credit'),
  label+' GBP latest research must not overwrite original old native credit source');
 const ccs=boeSources.secured.lending_conditions;
 assert(ccs,label+' verified CCS data must load in browser');
 const ccsBlock=locator(page,'.drivers-cad-official[aria-label="Indagine CCS Regno Unito"]');
 assert.equal(await ccsBlock.count(),1,label+' CCS separate evidence missing');
 const ccsText=await ccsBlock.innerText();
 assert(ccsText.includes(ccs.latest_observation)&&ccsText.includes(itRate(ccs.values.at(-1)))&&ccsText.includes('Positivo = maggiore disponibilità'),label+' CCS dates, values, and sign convention');
 await locator(page,'[data-liq-country="CHF"]').click();
 const chfDossier=locator(page,'.drivers-selection');
 const chfLines=locator(page,'[data-chf-snb-lane="CHF.credit"]');
 const chfSource=readSource('live_data/sections/ESTIMATED_RESIDUAL_GAPS.json').lanes['CHF.credit'];
 const chfAmount=Number(chfSource.proxy_value/1000).toLocaleString('it-IT',{
  minimumFractionDigits:2,maximumFractionDigits:2
 });
 const chfLineText=await chfLines.innerText();
 assert(chfLineText.includes('Linee di credito verso l’estero')&&
        chfLineText.includes(chfSource.proxy_as_of)&&chfLineText.includes(chfAmount),
  label+' CHF credit limits must retain their source scope, date and value');
 const chfText=await chfDossier.innerText();
 assert.match(chfText,/limiti accordati.*clientela estera.*separatamente gli importi utilizzati/,
  label+' CHF dossier must distinguish credit limits from utilisation');
 assert.doesNotMatch(chfText,/credito (bancario )?utilizzato/i,
  label+' CHF credit limits must not be described as loans drawn');
 assert.equal(await chfDossier.locator('a[href="https://data.snb.ch/en/topics/banken/cube/bakredinausbm"]').count(),1,
  label+' CHF credit-limit source link is missing');
 const rateProxy=chfSource.lending_rate_proxy;
 const rateBlock=locator(page,'[aria-label="Costo finanziamenti Svizzera SNB"]');
 assert(rateProxy&&await rateBlock.count()===1,label+' CHF funding cost proxy missing');
 const rateText=await rateBlock.innerText();
 assert(rateText.includes(rateProxy.latest_observation)&&rateText.includes('non degli standard di concessione'),label+' CHF loan-price scope or date missing');
 await locator(page,'[data-liq-country="CAD"]').click();
 assert.equal(await locator(page,'[data-liq-country="CAD"]').getAttribute('aria-pressed'),'true');
 const cadDossier=await locator(page,'.drivers-source-provenance-fold').textContent();
 const officialCad=locator(page,'.drivers-cad-official[aria-label="Fonte ufficiale canadese separata"]');
 assert.equal(await officialCad.count(),1,
  label+' CAD official issuer evidence must be present separately from the native feed');
 const officialText=await officialCad.innerText();
 assert(officialText.includes('Bank of Canada')&&officialText.includes('V122667770')&&officialText.includes('stock bancario'),
  label+' CAD evidence must preserve bank source, exact series and stock interpretation');
 const cadSource=require('../site/fx-quant-v2/next/cad-official-credit-research-v1.js');
  const lynx=cadSource.settlement_balances;
  if(lynx){
   const balances=locator(page,'.drivers-cad-official[aria-label="Saldi di regolamento Lynx"]');
   assert.equal(await balances.count(),1,label+' CAD daily settlement balances must be a separate issuer block');
   const amount=Number(lynx.values.at(-1)/1000).toLocaleString('it-IT',{minimumFractionDigits:3,maximumFractionDigits:3});
   const text=await balances.innerText();
   assert(text.includes(lynx.latest_observation)&&text.includes(amount)&&text.includes('esclusi i saldi RTR'),label+' CAD daily source date/value/scope missing');
   const fold=locator(page,'.drivers-fold');
   await fold.locator('summary').click();
   assert.equal(await locator(page,'.drivers-chart-grid .drivers-chart').count(),cadSource.lending_conditions?4:3,label+' CAD daily, credit and distinct monthly history charts');
   await fold.locator('summary').click();
  }
  if(cadSource.lending_conditions){
   const survey=locator(page,'.drivers-cad-official[aria-label="Indagine SLOS Canada"]');
   assert.equal(await survey.count(),1,label+' CAD SLOS issuer evidence');
   const text=await survey.innerText();
   assert(text.includes('Negativo = allentamento')&&text.includes('positivo = irrigidimento'),label+' CAD survey sign semantics');
  }
  assert(cadDossier.includes('Serie non disponibile'),
  label+' missing CAD direct credit must not be invented');
 assert(cadDossier.includes('Copertura')&&cadDossier.includes('QUALITÀ TEMPORALE'),
  label+' liquidity status must reflect actual coverage and dated sources');
 assert(cadDossier.includes('punti della survey')&&!cadDossier.includes('−208,33%'),
  label+' signed lending surveys must not be misreported as percentage changes');
 await locator(page,'[data-liq-country="JPY"]').click();
 const meaning=await locator(page,'.drivers-selection').innerText();
 assert(meaning.toLowerCase().includes('liquidità')&&meaning.toLowerCase().includes('credito'),
  label+' liquidity-to-credit divergence narrative missing');
 const jpySources=await locator(page,'.drivers-source-provenance-fold').textContent();
 assert(/STORICO|DATATO/.test(jpySources)&&jpySources.includes('osservazione precedente'),
  label+' source age and observed changes must be explicit');
 const actualJPY=readSource('live_data/sections/NATIVE_LIQ_DATA.json').JPY;
 for(const role of ['liquidity','credit','conditions']){
  const data=actualJPY[role];
  if(!data?.last_date)continue;
  const fact=locator(page,'[data-liq-role="'+role+'"]');
  assert((await fact.textContent()).includes(data.last_date),label+' JPY '+role+' must show real observation period');
 }
 const today=new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Rome',year:'numeric',month:'2-digit',day:'2-digit'}).format();
 const risk=readSource('site/fx-quant-v2/cross-asset-live-data.json');
 assert(meaning.includes('USD/JPY')&&meaning.includes(riskCheck(risk,today)),
  label+' JPY liquidity hypotheses require sourced USD/JPY and correctly dated VIX/HY');
 const detail=locator(page,'.drivers-fold');
 await detail.locator('summary').click();
 assert(await detail.evaluate(el=>el.open),label+' financial conditions source details cannot open');
 const tankan=require('../site/fx-quant-v2/next/jpy-boj-bank-credit-research-v1.js').tankan;
 assert(tankan,label+' verified JPY Tankan source is required');
 const survey=locator(page,'.drivers-cad-official[aria-label="Indagine Tankan Giappone"]');
 assert.equal(await survey.count(),1,label+' Tankan evidence must be separate');
 assert((await survey.innerText()).includes(tankan.latest_observation));
 assert.equal(await locator(page,'.drivers-chart-grid .drivers-chart').count(),3);
}
async function chosenPair(page,key,label){
 const button=locator(page,'#fx-ranking-desk button.fx-rank-pair[data-pair="'+key+'"]').first();
 assert(await button.count(),label+' '+key+' not present in complete 28-pair ranking');
 await button.click();
 await page.waitForFunction(key=>{
  const selected=document.querySelector('#fx-selected-thesis');
  return !!selected?.textContent?.includes(key.slice(0,3)+'/'+key.slice(3));
 },key,{timeout:15000});
 const detailHead=locator(page,'#fx-selected-thesis');
 await page.waitForFunction(()=>document.activeElement?.id==='fx-selected-thesis');
 await page.waitForFunction(()=>{
  const el=document.getElementById('fx-selected-thesis');
  if(!el)return false;
  const top=el.getBoundingClientRect().top;
  const header=document.querySelector('.topbar').getBoundingClientRect().bottom;
  return top>=header&&top<window.innerHeight*.70;
 });
 const top=await detailHead.evaluate(el=>el.getBoundingClientRect().top);
 assert(top>=48,label+' '+key+' dossier heading is behind sticky navigation: '+top);
 const listSelection=locator(page,'.fx-rank-all-list button.fx-rank-pair[data-pair="'+key+'"]');
 assert.equal(await listSelection.getAttribute('aria-pressed'),'true',label+' selection not exposed to assistive technology');
 const p=locator(page,'.pairs-reading-compact');
 assert.equal(await p.count(),1,label+' '+key+' first-read missing');
 const firstRead=await p.innerText();
 assert.match(firstRead,/Cosa va\.[\s\S]*Cosa frena\.[\s\S]*Cosa guardare\./);
 assert.match(await p.locator('.pairs-reading-head h2').innerText(),/nelle ultime settimane/i,
  label+' '+key+' must open on the observed move');
 assert.doesNotMatch(firstRead,/fixing|futures|\d+(?:,\d+)?\s*%|TRADE ATTRACTIVENESS/i,
  label+' '+key+' exposed technical details in the first reading');
 const quotes=p.locator('details.pairs-evidence');
 assert(!await quotes.evaluate(el=>el.open),label+' '+key+' details open without request');
 assert(!await p.locator('.pairs-price-periods').isVisible(),label+' '+key+' price numbers should be folded');
 await quotes.locator(':scope > summary').click();
 assert(await quotes.evaluate(el=>el.open),label+' '+key+' cannot inspect price and evidence');
 assert.equal(await p.locator('.pairs-three-answers > div').count(),3,
  label+' thesis, trade attractiveness and price comparison incomplete');
 const trade=await p.locator('.pairs-trade-assessment').getAttribute('data-pairs-trade-tone');
 assert(['neutral','awaiting','caution'].includes(trade),
  label+' trade status category lost its evidence-based visual treatment');
 const criteria=p.locator('.pairs-conditions article');
 assert.equal(await criteria.count(),2,label+' confirmations and invalidations must be separate');
 const confirming=(await criteria.nth(0).innerText()).trim();
 const weakening=(await criteria.nth(1).innerText()).trim();
 assert(confirming.includes('Rafforzerebbe il quadro')&&confirming.length>50,
  label+' meaningful confirmation evidence missing');
 assert(weakening.includes('Lo indebolirebbe')&&weakening.length>50,
  label+' meaningful contrary evidence missing');
 const riskText=(await p.locator('.pairs-why-no-entry').innerText()).trim();
 assert(riskText.includes('Rischio operativo.')&&
        riskText.includes('rapporto rischio/rendimento')&&
        riskText.includes('non equivale'),
  label+' '+key+' must explain source-specific risks and unvalidated entry payoff');
 assert(!/livelli H4 (confermati|verificati)|segnale di ingresso confermato/i.test(riskText),
  label+' '+key+' cannot claim verified H4 entries from ECB daily fixings');
 const story=await p.innerText();
 for(const word of ['TESI FONDAMENTALE','TRADE ATTRACTIVENESS','IL PREZZO SEGUE LA TESI?',
  'Prima di valutare un ingresso',
  'Rafforzerebbe il quadro','Lo indebolirebbe','Evento da monitorare'])
  assert(story.includes(word),label+' '+key+' missing '+word);
 for(const days of [5,20]){
  const period=p.locator('[data-pair-price-days="'+days+'"]');
  assert.equal(await period.count(),1,label+' '+key+' price horizon missing');
  const pair=priceEvidence.pairs.find(row=>row.key===key);
  const alignment=days===5?pair.fiveState:pair.aligned?'COERENTE':pair.opposite?'CONTRARIO':'INDECISO';
  const sourceTone=!pair.favored?'neutral':alignment==='COERENTE'?'support':alignment==='CONTRARIO'?'against':'neutral';
  const move=days===5?pair.move5Percent:pair.pricePercent;
  const expectedMove=(move>0?'+':move<0?'−':'')+Math.abs(move).toLocaleString('it-IT',{
   minimumFractionDigits:2,maximumFractionDigits:2
  })+'%';
  assert.equal(await period.getAttribute('data-pair-price-tone'),sourceTone,label+' '+key+' price direction reversed');
  assert.equal(await period.locator('strong').innerText(),expectedMove,label+' '+key+' price move misquoted');
 }
 assert.equal(await p.locator('.pairs-price-assessment small').innerText(),
  'Fixing BCE al '+priceEvidence.priceAsOf.split('-').reverse().join('/'),
  label+' '+key+' price comparison lost its source date');
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
 await details.locator(':scope > summary').click();
 await locator(page,'[data-pair-chart-jump]').press('Enter');
 const chart=locator(page,'#fx-pair-price-chart');
 assert(await details.evaluate(el=>el.open),label+' price shortcut did not open the analysis');
 assert.match(await chart.locator('h3').innerText(),/^GBP\/USD/);
 await page.waitForFunction(()=>{
  const chart=document.getElementById('fx-pair-price-chart');
  const top=chart?.getBoundingClientRect().top;
  const header=document.querySelector('.topbar').getBoundingClientRect().bottom;
  return document.activeElement===chart&&top>=header&&top<window.innerHeight*.70;
 });
 await chart.locator('[data-v9-price-window="20"]').click();
 assert.equal(await chart.locator('[data-v9-price-window="20"]').getAttribute('aria-pressed'),'true');
 assert(await details.evaluate(el=>el.open),label+' price window collapsed the opened analysis');
 const starts=await chart.locator('[data-fixing-start]').evaluateAll(nodes=>nodes.map(node=>node.dataset.fixingStart));
 assert.deepEqual(starts,[priceEvidence.priceFrom,priceEvidence.priceFrom5],
  label+' 20-session chart must show the exact fixing dates used by the summary');
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
 await page.waitForFunction(()=>document.activeElement?.id==='fx-ranking-desk');
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
 // Select consecutive rows without waiting for an animation between clicks.
 // Both actions must navigate to their target immediately, including on mobile.
 await locator(page,'.fx-rank-all-list [data-pair="USDJPY"]').click();
 const landed=await page.evaluate(()=>{
  const detail=document.getElementById('fx-selected-thesis');
  return {
   title:detail?.querySelector('h2')?.textContent||'',
   top:detail?.getBoundingClientRect().top,
   header:document.querySelector('.topbar').getBoundingClientRect().bottom,
   height:window.innerHeight
  };
 });
 assert.match(landed.title,/USD\/JPY/);
 assert(landed.top>=landed.header&&landed.top<landed.height*.7,
  label+' pair click must immediately show the title below the sticky header: '+JSON.stringify(landed));
 await chosenPair(page,'EURUSD',label);
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
 const reference=await page.evaluate(async()=>{
  const files={
   ois:'../ois-pricing-snapshot.json',research:'../ois-same-contract-repricing-research.json',
   history:'./rates-pricing-history-v1.json',operational:'../../../live_data/sections/OIS_OPERATIONAL_VIEW.json',
   nzd:'../../../live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json',
   pairs:'../../../live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json'
  };
  const sources=Object.fromEntries(await Promise.all(Object.entries(files).map(async([key,url])=>{
   const response=await fetch(url,{cache:'no-store'});
   if(!response.ok)throw Error('Cannot compare rendered 6M value without '+key);
   return [key,await response.json()];
  })));
  const today=new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Rome',year:'numeric',month:'2-digit',day:'2-digit'}).format();
  return window.FXQuantPairMonetary.evaluate({...sources,pair:'EURUSD',today});
 });
 assert(reference.ready,label+' EUR/USD dated source model missing');
 const dmy=date=>date.split('-').reverse().join('/');
 for(const [window,move] of [['1d',reference.oneEvidence],['1w',reference.weekEvidence]]){
  const card=euroPanel.locator('[data-pair-monetary-window="'+window+'"]');
  assert.equal(await card.getAttribute('data-pair-monetary-evidence'),move?.grade||'LEVEL_CONTEXT',
   label+' EUR/USD '+window+' evidence grade differs from served sources');
  const shown=await card.innerText();
  if(move){
   const signed=(move.relativeBp>0?'+':move.relativeBp<0?'−':'')+
    Math.abs(move.relativeBp).toFixed(2).replace('.',',')+' pb';
   assert.equal(await card.locator('strong').innerText(),signed,label+' EUR/USD '+window+' source value');
   assert(shown.includes(dmy(move.to))&&(!move.from||shown.includes(dmy(move.from))),
    label+' EUR/USD '+window+' observation dates must match sources');
  }else{
   for(const [ccy,leg] of [['EUR',reference.levels.base],['USD',reference.levels.quote]])
    assert(Number.isFinite(leg.rate)&&shown.includes(ccy+' '+leg.rate.toFixed(3).replace('.',',')+'%')&&
     shown.includes(dmy(leg.asof)),label+' EUR/USD '+window+' fallback must show dated levels');
  }
 }
 const copy=await euroPanel.innerText();
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
 const chf=locator(page,'.rates-country-strip [data-rate-ccy="CHF"]');
 const chfTile=await chf.innerText();
 await chf.click();
 assert.equal(await chf.getAttribute('aria-pressed'),'true',label+' CHF selector did not activate');
 const chfSnapshot=locator(page,'.rates-stats[aria-label$="CHF"]');
 if(chfTile.includes('10Y osservato')){
  const chfValues=await chfSnapshot.innerText();
  assert(chfValues.includes('Gov 10Y · Osservato')&&chfValues.includes('10Y − 2Y · Storico'),
   label+' CHF spot observation and historical paired curve must remain distinct');
  assert.equal(chfValues.includes('Gov 2Y · Stima'),chfTile.includes('2Y stimato'),
   label+' CHF 2Y quality differs between selector and selected snapshot');
 }
 await page.screenshot({path:evidence+'/'+label+'-rates-chf.png'});
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
 const pairLink=locator(page,'#macro-calendar [data-cal-research="pairs"]').first();
 assert.match(await pairLink.getAttribute('href'),/^#pairs\?pair=[A-Z]{6}$/);
 await pairLink.click();
 await page.waitForFunction(()=>document.querySelector('#content')?.dataset.view==='pairs'&&
  document.querySelector('.pairs-reading-compact'));
 assert.equal(await locator(page,'.pairs-reading-compact').count(),1,
  label+' macro-event pair link did not open a real FX dossier');
 assert.match(new URL(page.url()).hash,/^#pairs\?pair=[A-Z]{6}$/);
}
async function homeCatalystJourney(page,label){
 await route(page,'overview');
 const link=locator(page,'[data-home-catalyst="upcoming"] [data-cal-research="rates"]');
 if(!(await link.count()))return;
 const currency=await link.getAttribute('data-cal-currency');
 assert(/^(USD|EUR|GBP|JPY|CHF|CAD|AUD|NZD)$/.test(currency),label+' unknown catalyst currency');
 await link.click();
 await page.waitForFunction(code=>
  document.querySelector('#content')?.dataset.view==='rates'&&
  document.querySelector('.rates-country[aria-pressed="true"]')?.dataset.rateCcy===code,currency);
}
async function pairWatchlistJourney(page,label){
 const calendarRoute='**/CALENDAR_OPERATIONAL_VIEW.json';
 const thesisRoute='**/pair-estimate-history-v1.json';
 await page.route(thesisRoute,route=>route.fulfill({json:{
  schema:'GMFQ_NEXT_ESTIMATED_FX_THESIS_HISTORY_V1',snapshots:[
   {fixing:'2026-11-12',method:'browser-fixture',pairs:{EURCHF:{favored:'EUR',thesis:'PARZIALE',timing:'IN ATTESA'}}},
   {fixing:'2026-11-13',method:'browser-fixture',pairs:{EURCHF:{favored:'CHF',thesis:'PARZIALE',timing:'IN ATTESA'}}}
  ]
 }}));
 await page.route(calendarRoute,async route=>{
  const now=Date.now();
  // The operational calendar is Europe/Rome-local: UTC date +1 is still today
  // after Italian midnight but before UTC midnight, collapsing the 5th event.
  const parts=Object.fromEntries(new Intl.DateTimeFormat('en-US',{
   timeZone:'Europe/Rome',year:'numeric',month:'2-digit',day:'2-digit'
  }).formatToParts(new Date(now)).map(({type,value})=>[type,value]));
  const romeDay=parts.year+'-'+parts.month+'-'+parts.day;
  const futureDay=offset=>new Date(Date.parse(romeDay+'T12:00:00Z')+offset*864e5).toISOString().slice(0,10);
  const event={event_type:'CENTRAL_BANK_DECISION',importance:'HIGH',quality:'OFFICIAL_CALENDAR',status:'UPCOMING'};
  const events=['AUD','NZD','CAD','USD'].map((ccy,i)=>({...event,ccy,date:futureDay(i+1),title:'Riunione '+ccy}));
  events.push({...event,ccy:'CHF',date:futureDay(5),title:'Riunione SNB',time_local:'09:30',timezone:'Europe/Zurich'});
  await route.fulfill({json:{schema:'GMFQ_CALENDAR_OPERATIONAL_VIEW_V3',last_checked_at_utc:new Date(now).toISOString(),events}});
 });
 await page.reload({waitUntil:'domcontentloaded'});
 const showWatchlist=locator(page,'#fx-pair-list-watch');
 const savedPair=locator(page,'.fx-watch-list [data-pair="EURCHF"]');
 assert.match(await showWatchlist.innerText(),/Watchlist \(1\)/,label+' existing save lost after reload');
 await showWatchlist.click();
 assert.equal(await showWatchlist.getAttribute('aria-pressed'),'true');
 assert.equal(await locator(page,'.fx-rank-all-list').count(),0);
 assert.equal(await savedPair.count(),1);
 const price=locator(page,'.fx-watch-price');
 assert.match(await locator(page,'.fx-watch-thesis').innerText(),/Valuta favorita EUR → CHF/);
 assert.match(await price.innerText(),/Fixing BCE del \d{2}\/\d{2}\/\d{4} e del \d{2}\/\d{2}\/\d{4}/);
 const catalyst=locator(page,'a.fx-watch-event');
 assert.match(await catalyst.innerText(),/CHF · Riunione SNB.*09:30 IT/s);
 await catalyst.click();
 await page.waitForFunction(()=>document.activeElement?.dataset.calEvent?.endsWith('Riunione SNB'));
 assert(await locator(page,'.cal-more').evaluate(el=>el.open));
 await page.reload({waitUntil:'domcontentloaded'});
 await page.waitForFunction(()=>document.activeElement?.dataset.calEvent?.endsWith('Riunione SNB'));
 await page.goBack();
 await showWatchlist.click();
 await savedPair.click();
 assert.equal(new URL(page.url()).hash,'#pairs?pair=EURCHF');
 assert.match(await locator(page,'[data-pair-close]').innerText(),/Torna alla watchlist/);
 await locator(page,'[data-pair-close]').click();
 assert.equal(await savedPair.count(),1);
 await savedPair.click();
 const watch=locator(page,'[data-watch="EURCHF"]');
 await watch.press('Enter');
 assert.equal(await watch.getAttribute('aria-pressed'),'false');
 assert(await watch.evaluate(el=>document.activeElement===el));
 assert.equal(await savedPair.count(),0);
 assert.match(await showWatchlist.innerText(),/Watchlist \(0\)/);
 await locator(page,'[data-pair-close]').click();
 assert.match(await locator(page,'[aria-label="Watchlist FX"]').innerText(),/La watchlist è vuota/);
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2));
 await locator(page,'#fx-pair-list-all').click();
 assert.equal(await locator(page,'.fx-rank-all-list button.fx-rank-pair').count(),28);
 await page.reload({waitUntil:'domcontentloaded'});
 assert.match(await showWatchlist.innerText(),/Watchlist \(0\)/,label+' removal lost after reload');
 await page.unroute(calendarRoute);
 await page.unroute(thesisRoute);
 await page.reload({waitUntil:'domcontentloaded'});
 await showWatchlist.waitFor();
}
async function pairLinkJourney(page,label){
 const frank=new URL('#pairs?pair=EURCHF',BASE).href;
 const heading=locator(page,'#fx-selected-thesis h2');
 await page.goto(frank,{waitUntil:'domcontentloaded'});
 assert.match(await heading.innerText(),/EUR\/CHF/,label+' direct link opened the wrong pair');
 await page.reload({waitUntil:'domcontentloaded'});
 assert.match(await heading.innerText(),/EUR\/CHF/,label+' reloading lost the selected pair');
 await locator(page,'#pair-primary-select').selectOption('AUDCAD');
 assert.match(await heading.innerText(),/AUD\/CAD/);
 assert.equal(new URL(page.url()).hash,'#pairs?pair=AUDCAD');
 await page.goBack();
 await page.waitForFunction(()=>document.querySelector('#fx-selected-thesis h2')?.textContent.includes('EUR/CHF'));
 assert.match(await heading.innerText(),/EUR\/CHF/,label+' browser Back lost the previous pair');
 await page.goForward();
 await page.waitForFunction(()=>document.querySelector('#fx-selected-thesis h2')?.textContent.includes('AUD/CAD'));
 assert.match(await heading.innerText(),/AUD\/CAD/,label+' browser Forward lost the selected pair');
 await locator(page,'[data-pair-close]').click();
 assert.equal(new URL(page.url()).hash,'#pairs');
 assert.equal(await heading.count(),0,label+' ranking link must close the detail');
 await page.goto(new URL('#pairs?pair=ABCDEF',BASE).href);
 await heading.waitFor({state:'hidden'});
 await page.goto(new URL('#pairs?pair=CHFEUR',BASE).href);
 assert.match(await heading.innerText(),/EUR\/CHF/,label+' reversed link must use the supported ordering');
}
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try{
  const latest=library.latestPerType(fs.readdirSync(reportDir).map(library.remoteReport).filter(Boolean));
  const dailyReport=latest.find(report=>report.type==='daily');
  assert.equal(dailyFile,dailyReport?.file,'Daily catalog must reference the latest approved briefing');
  assert.equal(weeklyFiles.length,library.REPORTS.length-1,'Weekly catalog covers every weekly category');
  assert.deepEqual([...weeklyFiles].sort(),latest.filter(report=>report.type!=='daily')
   .map(report=>report.file).sort(),'Weekly catalog must reference the latest approved editions');
  const briefing=await browser.newPage();
  try{
   await briefing.route('https://api.github.com/**',request=>request.abort());
   let releaseVerification;
   const verificationGate=new Promise(resolve=>{releaseVerification=resolve;});
   await briefing.route('**/reports/'+dailyFile,async route=>{
    if(route.request().method()==='HEAD')await verificationGate;
    await route.continue();
   });
   const catalog=briefing.waitForResponse(response=>response.url().endsWith('/reports/daily-latest.json')&&response.ok());
   try{
    await Promise.all([catalog,briefing.goto(new URL('#library',BASE).href,{waitUntil:'domcontentloaded'})]);
    assert(await briefing.locator('#library-loading').isVisible(),'Library must show loading while the Daily URL is verified');
    assert.equal(await briefing.locator('.rl-card a').count(),0,'An archive edition must never flash while loading');
   }finally{releaseVerification();}
   for(const report of latest){
    const card=briefing.locator('.rl-card').filter({has:briefing.locator(`a[href="./reports/${encodeURIComponent(report.file)}"]`)});
    await card.waitFor({state:'visible'});
    assert.equal(await card.locator('time').getAttribute('datetime'),report.date,'Library card date for '+report.type);
    const linked=await briefing.request.get(new URL(report.publicUrl,BASE).href);
    assert(linked.ok(),'Library link must load: '+report.file);
   }
   assert.equal(await briefing.locator('.rl-card').count(),latest.length,'One card per category');
   assert.equal(await briefing.locator('#library-loading').isVisible(),false,'Loading status must clear after verification');
   assert.equal(await briefing.locator('#library-grid .rl-card').count(),weeklyFiles.length,
    'Weekly grid must contain exactly the weekly categories');
   const featured=briefing.locator('#library-featured');
   const link=featured.locator(`a[href="./reports/${dailyFile}"]`);
   await link.waitFor({state:'visible'});
   assert.equal(await briefing.locator(`a[href="./reports/${dailyFile}"]`).count(),1,
    'The Daily must occur once, in the featured panel');
   for(const width of [360,390,1440]){
    await briefing.setViewportSize({width,height:844});
    const box=await link.boundingBox();
    assert(box&&box.y>=0&&box.y+box.height<=844,'Open Briefing must fit in the first screen at '+width);
    assert(await briefing.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2),
     'Library horizontal overflow at '+width);
   }
   const oisFilter=briefing.locator('[data-library-type="ois"]');
   await oisFilter.press('Enter');
   assert.equal(await oisFilter.getAttribute('aria-pressed'),'true');
   assert(await oisFilter.evaluate(button=>document.activeElement===button),'Library filter must keep keyboard focus');
   assert.equal(await featured.isVisible(),false);
   assert.equal(await briefing.locator('#library-grid .rl-card').count(),1);
   await briefing.locator('#library-search').fill('nessuna edizione corrisponde');
   assert(await briefing.locator('#library-grid .rl-empty').isVisible(),'Library must show an empty result');
   await briefing.locator('#library-search').fill('');
   await briefing.locator('[data-library-type="daily"]').click();
   assert(await link.isVisible(),'Daily filter must keep the featured Briefing');
   assert.equal(await briefing.locator('#library-weekly').isVisible(),false);
   await briefing.locator('[data-library-type="all"]').click();
   const response=await briefing.goto(new URL(await link.getAttribute('href'),BASE).href);
   assert(response?.ok(),'The daily briefing selected by the Library must load');
   const headingDate=new Intl.DateTimeFormat('it-IT',{day:'numeric',month:'long',year:'numeric',
    timeZone:'Europe/Rome'}).format(new Date(dailyReport.date+'T12:00:00Z'));
   for(const selector of ['title','h1']){
    assert((await briefing.locator(selector).textContent())?.includes(headingDate),
     'Daily briefing '+selector+' must match the date in its filename');
   }
   assert.equal(await briefing.locator('main section').count(),7,'Daily briefing sections');
   assert.equal(await briefing.locator('#s3 .priority').count(),3,'Daily briefing priorities');
   assert.equal(await briefing.locator('#s4 article').count(),8,'Daily briefing G8');
   assert.equal(await briefing.locator('#s5 article').count(),5,'Daily briefing commodities');
   for(const width of [360,390,430,1440]){
    await briefing.setViewportSize({width,height:900});
    assert(await briefing.locator('h1').isVisible(),'Daily briefing heading at '+width);
    assert(await briefing.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2),
     'Daily briefing horizontal overflow at '+width);
   }
  }finally{await briefing.close();}
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
    assert(count&&Number(count[1])===Number(count[2])&&Number(count[2])>=19,
     label+' missing source(s): '+loaded);
    if(label==='mobile'){
     assert(await page.locator('#sidebar').evaluate(el=>el.inert),'Closed mobile menu must not receive keyboard focus');
     await locator(page,'#menu-toggle').click();
     assert.equal(await locator(page,'#menu-toggle').getAttribute('aria-expanded'),'true',
      'Mobile navigation did not open');
     assert(await page.locator('#sidebar').evaluate(el=>!el.inert&&el.contains(document.activeElement)),'Open menu must receive focus');
     assert(await page.locator('#sidebar').evaluate(el=>getComputedStyle(el).overflowY==='auto'),'Menu must scroll on short screens');
     await page.keyboard.press('Escape');
     assert.equal(await locator(page,'#menu-toggle').getAttribute('aria-expanded'),'false');
     assert(await page.locator('#menu-toggle').evaluate(el=>el===document.activeElement),'Escape must restore menu button focus');
     await locator(page,'#menu-toggle').click();
     await locator(page,'#nav [data-route="pairs"]').click();
     await route(page,'pairs');
     assert.equal(await locator(page,'#menu-toggle').getAttribute('aria-expanded'),'false',
      'Mobile navigation did not close after selection');
    }
    const inspected=[];
    for(const key of Object.keys(routes))inspected.push(await inspectRoute(page,label,key));
    await homeMoneyJourney(page,label);
    await g8Choice(page,label);
    await scenarioMacroJourney(page,label);
    await macroDriversJourney(page,label);
    await pairJourney(page,label);
    await pairWatchlistJourney(page,label);
    await pairMonetaryJourney(page,label);
    await calendarResearchJourney(page,label);
    await pairLinkJourney(page,label);
    await pricingWindowJourney(page,label);
    await g8HistoryJourney(page,label);
    await relative6mJourney(page,label);
    assert.equal(errors.length,0,label+' browser errors: '+errors.slice(0,4).join(' | '));
    await locator(page,'#content').screenshot({path:evidence+'/'+label+'-pair-journey.png'});
    await homeCatalystJourney(page,label);
    reports.push({label,sourceCount:Number(count[1]),routes:inspected,interaction:'PASS'});
   }finally{await page.close();}
  }
  fs.writeFileSync(evidence+'/current-journey-summary.json',JSON.stringify(reports,null,2));
  console.log('FXQUANT_NEXT_CURRENT_JOURNEY_PASS',JSON.stringify(reports.map(x=>({
   label:x.label,sourceCount:x.sourceCount,routeCount:x.routes.length,interaction:x.interaction
  }))));
 }finally{await browser.close();}
})().catch(e=>{console.error('FXQUANT_NEXT_QA_FAIL',e.stack||e);process.exit(1);});
