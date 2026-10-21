/* Browser contract for v10. All feeds are locally intercepted fixture copies from repo. */
'use strict';
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path');
const {romeTodayIso}=require('../site/control-room-preview/ois-pricing-estimates-v1.js');
const DATA=path.join(process.cwd(),'live_data/sections');
const dxyFeed=JSON.parse(fs.readFileSync(path.join(DATA,'DXY_SYNTHETIC_ECB.json'),'utf8'));
const nzdProxy=JSON.parse(fs.readFileSync(path.join(DATA,'NZD_CB_PRICING_DIRECTIONAL_PROXY.json'),'utf8'));
if(dxyFeed.schema!=='GMFQ_DXY_SYNTHETIC_ECB_V1'||dxyFeed.not_official_ice!==true||
   dxyFeed.status!=='ESTIMATED_INFORMATIONAL')throw Error('DXY research provenance contract failed');
if(nzdProxy.schema!=='GMFQ_NZD_CB_PRICING_DIRECTIONAL_PROXY_V1'||
   nzdProxy.status!=='LIVE_DIRECTIONAL_PROXY_READY')throw Error('NZD directional proxy contract failed');
const dxyDisplayed=Number(dxyFeed.value).toFixed(2);
const nzdDisplayed=Number(nzdProxy.horizons['6m'].implied_bank_bill_rate).toFixed(2);
const ratesFeed=JSON.parse(fs.readFileSync(path.join(DATA,'NATIVE_RATES_DATA.json'),'utf8'));
const setupFeed=JSON.parse(fs.readFileSync(path.join(DATA,'PAIR_SETUP_OPERATIONAL_VIEW.json'),'utf8'));
const operational=JSON.parse(fs.readFileSync(path.join(DATA,'OIS_OPERATIONAL_VIEW.json'),'utf8'));
const sourceReadiness=JSON.parse(fs.readFileSync(path.join(DATA,'OIS_SOURCE_READINESS_VIEW.json'),'utf8'));
const sourceIds=Object.keys(sourceReadiness.currencies||{});
const g8=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
if(sourceIds.some(c=>!g8.includes(c))||
   sourceIds.some(c=>!['WITHHELD','GREEN_ESTIMATED'].includes(sourceReadiness.currencies[c].status))||
   sourceIds.length!==g8.filter(c=>
     operational.currencies[c].operational_status!=='GREEN_OFFICIAL').length||
   sourceReadiness.blocked_currency_count!==sourceIds.filter(c=>
     sourceReadiness.currencies[c].status==='WITHHELD').length)
  throw Error('Readiness source registry count/status mismatch');

const expectedSecondaryQuotes=['USD','EUR','CHF'].filter(k=>{
  const x=operational.currencies?.[k],ctx=x?.secondary_quote_context;
  return x?.operational_status==='WITHHELD'&&
    ctx?.status==='INDICATIVE_OBSERVATIONS_NON_OIS'&&
    ctx.full_curve_usable===false&&ctx.cross_date_join_allowed===false&&
    ctx.policy_delta_allowed===false&&ctx.repricing_signal_allowed===false;
}).length;

const snbSpot=JSON.parse(fs.readFileSync(path.join(DATA,'CHF_SNB_10Y_SPOT_CONTEXT.json'),'utf8'));
if(snbSpot.tenor!=='10Y'||snbSpot.has_current_2y!==false||snbSpot.eligible_for_curve_spreads!==false)throw Error('Invalid independent SNB 10Y context fixture');
function commonAnchorDate(target,proxy,tenor='history2'){
 const dates=new Set(ratesFeed[proxy][tenor].dates);
 return ratesFeed[target][tenor].dates.filter(d=>d<=ratesFeed[target].date&&dates.has(d)).at(-1);
}
function recentOfficialRate(row){
 if(!row||!String(row.quality||'').includes('OFFICIAL')||!/^\d{4}-\d{2}-\d{2}$/.test(row.date||''))return false;
 const gap=(Date.parse(romeTodayIso()+'T00:00:00Z')-Date.parse(row.date+'T00:00:00Z'))/86400000;
 return gap>=0&&gap<=4;
}
const chfAnchor=commonAnchorDate('CHF','EUR');
const nzdAnchor=commonAnchorDate('NZD','AUD');
const nzdOfficial=recentOfficialRate(ratesFeed.NZD);
if(!chfAnchor||(!nzdOfficial&&!nzdAnchor))throw Error('Missing common official rates estimation anchors');
/* Market series are refreshed every day. Determine the expected descriptive
   verdict from the displayed rates/FX magnitudes and pre-registered thresholds,
   never from a hardcoded historical date or fixed EURUSD/GBPJPY outcome. */
function expectedReactionFromMetrics(row){
 const vals=row?.values||[];
 if(vals.length<2)return 'WITHHELD';
 const bp=Number.parseFloat(vals[0]),fx=Number.parseFloat(vals[1]);
 if(!Number.isFinite(bp)||!Number.isFinite(fx))return 'WITHHELD';
 if(Math.abs(bp)<2||Math.abs(fx)<0.05)return 'NON_CONCLUSIVO';
 return Math.sign(bp)===Math.sign(fx)?'COERENTE':'DIVERGENTE';
}
(async()=>{
 const browser=await chromium.launch({headless:true});
 for(const [label,viewport] of [['desktop',{width:1440,height:950}],['mobile',{width:390,height:844}]]){
  const page=await browser.newPage({viewport});
  const errors=[];
  page.on('pageerror',err=>errors.push(String(err)));
  await page.route('https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/main/live_data/sections/*.json',async route=>{
    const name=route.request().url().split('/').at(-1).split('?')[0];
    const file=path.join(process.cwd(),'live_data/sections',name);
    if(!fs.existsSync(file))return route.fulfill({status:404,body:'Missing fixture'});
    return route.fulfill({status:200,contentType:'application/json',body:fs.readFileSync(file),headers:{'Access-Control-Allow-Origin':'*'}});
  });
  const url='http://127.0.0.1:8818/site/control-room-preview/';
  const response=await page.goto(url,{waitUntil:'domcontentloaded',timeout:120000});
  if(!response||!response.ok())throw Error(label+' home did not load');
  try { await page.waitForFunction(()=>{
    const f=document.getElementById('gmfq-page'),d=f?.contentDocument;
    return d?.documentElement?.getAttribute('data-live-state')==='LOADED'
      && d.querySelectorAll('#ois .oisrow').length===8
      && d.querySelector('#valute .cc[data-filter="DXY"] .value')?.textContent.trim()!=='—'
      && d.querySelectorAll('#ylegend .gmfq-legend-item').length===8;
  },null,{timeout:30000}); } catch(e) {
    const debug=await page.evaluate(()=>{
      const f=document.getElementById('gmfq-page'),d=f?.contentDocument;
      return {outer:document.getElementById('state')?.innerText,
        pageTitle:document.title,frame:!!f,document:!!d,mode:d?.documentElement?.dataset.marketMode,
        liveState:d?.documentElement?.dataset.liveState,
        oisRows:d?.querySelectorAll('#ois .oisrow').length,
        ratesLabels:d?.querySelectorAll('#ylegend .gmfq-legend-item').length,
        dxy:d?.querySelector('#valute .cc[data-filter="DXY"] .value')?.textContent,
        scripts:[...(d?.scripts||[])].map(x=>x.src||'inline').slice(-3),
        htmlError:d?.body?.innerText?.slice(-500)};
    });
    console.error('V10_WAIT_DIAGNOSTIC',label,JSON.stringify({debug,errors}));
    fs.mkdirSync('v10-qa-images',{recursive:true});
    await page.screenshot({path:'v10-qa-images/'+label+'-diagnostic.png',fullPage:true});
    throw e;
  }
  // A successful 4/4 HTTP load does NOT mean eight current OIS curves.
  // Read the same fixture dates and verify the on-screen statement and
  // keyboard-accessible source details, on desktop AND smartphone.
  const fxData=JSON.parse(fs.readFileSync(path.join(DATA,'ECB_G8_PRICE_HISTORY.json'),'utf8'));
  const expectedOis=JSON.parse(fs.readFileSync(path.join(DATA,'OIS_OPERATIONAL_VIEW.json'),'utf8'));
  const current=(dt,max=5)=>{
    const diff=(Date.parse(romeTodayIso()+'T00:00:00Z')-
      Date.parse(dt+'T00:00:00Z'))/86400000;
    return Number.isFinite(diff)&&diff>=0&&diff<=max;
  };
  const certified=Object.values(expectedOis.currencies).filter(x=>
    x.operational_status==='GREEN_OFFICIAL'&&x.quality==='OFFICIAL_CERTIFIED'&&current(x.as_of)&&
    ['3m','6m','12m'].every(k=>Number.isFinite(x.horizons?.[k]?.rate)&&Number.isFinite(x.horizons?.[k]?.policy_delta_bp))).length;
  const expectedFx=current(fxData.last_as_of,4);
  await page.waitForFunction(()=>!!document.getElementById('gmfq-page')?.contentDocument?.getElementById('gmfq-home-data-audit'),
    null,{timeout:15000});
  const homeAudit=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page').contentDocument;
    return {
      label:d.querySelector('#liveState')?.textContent.trim(),
      stamp:d.querySelector('#liveAsOf')?.textContent.trim(),
      role:d.querySelector('.mast .fresh')?.getAttribute('role'),
      source:d.querySelector('#gmfq-home-data-audit')?.textContent.trim(),
      documentWidth:d.documentElement.scrollWidth,viewport:d.documentElement.clientWidth
    };
  });
  if(!homeAudit.source?.includes('Macro/Tassi · baseline strutturale')||
     !homeAudit.source?.includes(setupFeed.macro_baseline_asof)||
     !homeAudit.stamp?.includes('Macro stor./n.v.'))
    throw Error(label+' Home Macro provenance missing '+JSON.stringify(homeAudit));
  if(homeAudit.role!=='button'||!homeAudit.stamp?.includes('OIS '+certified+'/8')||
     !(expectedFx?homeAudit.stamp.includes('FX '+fxData.last_as_of.slice(8,10)+'/'+fxData.last_as_of.slice(5,7)):
       homeAudit.stamp.includes('FX non corr.'))||
     (certified<8&&homeAudit.label!=='DATI PARZIALI')||
     !homeAudit.source?.includes('Non è DXY ICE ufficiale')||
     !homeAudit.source?.includes('futures monetari, non OIS puri')||
     homeAudit.documentWidth>homeAudit.viewport+16)
    throw Error(label+' incorrect Home source freshness display '+JSON.stringify(homeAudit));
  // Reading order, not another dashboard. All three facts share the already
  // certified source audit. Native hero/globe and the original grid remain.
  const homeReading=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page').contentDocument;
    const rail=d.getElementById('gmfq-home-reading-path'),
      hero=d.querySelector('.hero'),grid=d.querySelector('.gridtop'),
      btn=[...rail?.querySelectorAll('button[data-reading-target]')||[]];
    return {exists:!!rail,count:btn.length,labels:btn.map(b=>b.textContent.trim()),
      routes:btn.map(b=>b.dataset.readingTarget),
      macro:rail?.dataset.macroAsOf,macroStatus:rail?.dataset.macroStatus,
      ois:rail?.dataset.oisCertified,screener:rail?.dataset.screenerCount,
      fx:rail?.dataset.fxAsOf,sourceEffect:rail?.dataset.sourceEffect,
      positioned:!!rail&&!!hero&&!!grid&&grid.contains(hero)&&
       !!(rail.compareDocumentPosition(grid)&Node.DOCUMENT_POSITION_FOLLOWING),
      positions:{hero:hero?.getBoundingClientRect().top,rail:rail?.getBoundingClientRect().top,grid:grid?.getBoundingClientRect().top,heroFollowsGrid:!!(grid?.compareDocumentPosition(hero)&Node.DOCUMENT_POSITION_FOLLOWING),heroFollowsRail:!!(rail?.compareDocumentPosition(hero)&Node.DOCUMENT_POSITION_FOLLOWING),parentHero:hero?.parentElement?.className,parentGrid:grid?.parentElement?.className},
      globe:!!d.querySelector('.hero .globe'),
      railScroll:rail?.scrollWidth,railWidth:rail?.clientWidth,
      bodyScroll:d.documentElement.scrollWidth,bodyWidth:d.documentElement.clientWidth};
  });
  const countNot=Object.values(setupFeed.pairs).filter(x=>x?.setup?.quality==='NON VALUTABILE').length;
  const correctMacro=current(setupFeed.macro_baseline_asof,10);
  if(!homeReading.exists||homeReading.count!==3||
     JSON.stringify(homeReading.routes)!==JSON.stringify(['macro','pricing','pairs'])||
     !homeReading.positioned||!homeReading.globe||homeReading.sourceEffect!=='NONE'||
     homeReading.macro!==setupFeed.macro_baseline_asof||
     homeReading.macroStatus!==(correctMacro?'DATED_SNAPSHOT':'HISTORICAL')||
     homeReading.ois!==String(certified)||homeReading.screener!==String(countNot)||
     !homeReading.labels[0].includes(setupFeed.macro_baseline_asof)||
     !homeReading.labels[1].includes(certified+'/8 fonti certificate')||
     !homeReading.labels[2].includes(countNot+'/28 non valutabili')||
     homeReading.railScroll>homeReading.railWidth+2||
     homeReading.bodyScroll>homeReading.bodyWidth+16)
    throw Error(label+' Home reading hierarchy or provenance failed '+JSON.stringify(homeReading));
  await page.screenshot({path:'v10-qa-images/'+label+'-home-reading-priorities.png',fullPage:true});
  console.log('CONTROL_ROOM_V10_HOME_READING_PATH_GREEN',label,{
    macro:homeReading.macro,ois:homeReading.ois,screener:homeReading.screener});

  const triggerSelector=label==='mobile'?'#gmfq-mobile-data-audit':'.mast .fresh';
  const freshTrigger=page.frameLocator('#gmfq-page').locator(triggerSelector);
  if(label==='mobile'){await freshTrigger.click()}
  else{await freshTrigger.focus();await freshTrigger.press('Enter')}
  await page.frameLocator('#gmfq-page').locator('dialog#gmfq-home-data-audit[open]').waitFor({timeout:10000});
  await page.frameLocator('#gmfq-page').locator('.gmfq-audit-close').click();
  if(label==='mobile'&&!(await page.frameLocator('#gmfq-page').locator('#gmfq-mobile-data-audit').isVisible()))
    throw Error('Mobile source-quality trigger not visible');
  if(await page.frameLocator('#gmfq-page').locator('dialog#gmfq-home-data-audit[open]').count())
    throw Error(label+' freshness audit dialog did not close');
  console.log('CONTROL_ROOM_PREVIEW_SOURCE_FRESHNESS_GREEN',label,
    JSON.stringify({state:homeAudit.label,stamp:homeAudit.stamp,certified,viewport:homeAudit.viewport}));

  const r=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page').contentDocument;
    const box=sel=>{const x=d.querySelector(sel);return {clientHeight:x?.clientHeight,scrollHeight:x?.scrollHeight,clientWidth:x?.clientWidth,scrollWidth:x?.scrollWidth}};
    const ois=[...d.querySelectorAll('#ois .oisrow')].map(x=>({ccy:x.dataset.ccy,desc:x.innerText}));
    return {
      route:location.hash,
      dxy:d.querySelector('#valute .cc[data-filter="DXY"] .value')?.innerText,
      noApprofondisci:!d.body.innerText.includes('Approfondisci ↗'),
      rateSeries:[...d.querySelectorAll('#ylegend .gmfq-legend-item')].map(x=>x.innerText),
      rateBarTexts:[...d.querySelectorAll('#ratesbars svg text')].map(x=>x.textContent.trim()),
      rateBarNote:d.querySelector('#ratesbars + .gmfq-chart-note')?.textContent.trim()||'',
      ratesChart:box('.gridtop .yieldpanel'),
      oisPanel:box('.gridtop > .panel:nth-child(2)'),
      nzdbb:ois.find(x=>x.ccy==='NZD')?.desc||null,
      oisCount:ois.length,
      bars2y:d.querySelector('#ratesbars svg')!==null,
      spread:d.querySelector('#spreads svg')!==null,
      designGlobe:!!d.querySelector('.hero .globe'),
      pageWidth:d.documentElement.scrollWidth,viewWidth:d.documentElement.clientWidth
    };
  });
  console.log(label,JSON.stringify(r));
  const fatal=[];
  if((r.dxy||'').trim()!==dxyDisplayed)fatal.push('DXY synthetic not synchronized with its source: '+r.dxy+' != '+dxyDisplayed);
  if(!r.noApprofondisci)fatal.push('old overlay link still shown');
  if(r.rateSeries.length!==8)fatal.push('missing G8 yield lines');
  if(r.oisCount!==8||!r.nzdbb?.includes(nzdDisplayed))fatal.push('NZD directional proxy missing or stale');
  const g8=['USD','EUR','GBP','JPY','AUD','CAD','NZD','CHF'];
  if(g8.some(c=>!r.rateBarTexts.includes(c)))fatal.push('G8 2Y bars missing currency labels');
  // A recently certified NZD yield supersedes the earlier NZD/AUD estimate.
  // Still enforce an anchored CHF estimate, and an NZD estimate only when missing.
  // WITHHELD is the correct outcome when neither a fresh NZD official rate
  // nor a properly anchored NZD proxy estimate is available.
  const nzIndex=r.rateBarTexts.indexOf('NZD'),nzDisplayed=nzIndex>0?r.rateBarTexts[nzIndex-1]:'';
  const nzWithheld=nzDisplayed==='—';
  const nzEstimated=!nzdOfficial&&!nzWithheld&&nzDisplayed.endsWith('*');
  const expectedEstimates=1+(nzEstimated?1:0);
  if(r.rateBarTexts.filter(x=>x.endsWith('*')).length<expectedEstimates||
     !r.rateBarNote.includes('STIMA'))
    fatal.push('Unlabelled or absent CHF anchored model estimate');
  if(!r.rateBarNote.includes('base '+chfAnchor)||
     (nzEstimated&&!r.rateBarNote.includes('base '+nzdAnchor)))
    fatal.push('Displayed model estimates must have common-date anchors: '+r.rateBarNote);
  if(!nzdOfficial&&!nzWithheld&&!nzEstimated)
    fatal.push('NZD without current official data must be estimated or WITHHELD: '+nzDisplayed);
  if(nzdOfficial&&(r.rateBarNote.includes('NZD/AUD')||nzWithheld||
      !r.rateBarTexts.includes('NZD')||
      r.rateBarTexts.includes(Number(ratesFeed.NZD['2Y']).toFixed(2)+'*')))
    fatal.push('Certified NZD yield incorrectly shown as estimate/WITHHELD');
  if(!r.rateBarNote.includes('R² ')||!r.rateBarNote.includes('BASSA'))
    fatal.push('Model confidence/disclaimer is not visible: '+r.rateBarNote);
  if(!r.bars2y||!r.spread||!r.designGlobe)fatal.push('cards/approved design missing');
  if(r.oisPanel.scrollHeight>r.oisPanel.clientHeight+8)fatal.push('OIS clipped');
  if(r.ratesChart.scrollHeight>r.ratesChart.clientHeight+8)fatal.push('Yield panel clipped');
  if(r.pageWidth>r.viewWidth+16)fatal.push('Horizontal overflow');
  if(errors.length)fatal.push('JS '+errors.join(' | '));
  if(fatal.length)throw Error(label+': '+fatal.join('; '));
  fs.mkdirSync('v10-qa-images',{recursive:true});
  await page.screenshot({path:'v10-qa-images/'+label+'-home.png',fullPage:true});
  await page.frameLocator('#gmfq-page').locator('#valute .cc[data-filter="DXY"]').click();
  if(!await page.frameLocator('#gmfq-page').locator('dialog#gmfq-dxy-dialog[open]').count())throw Error('In-app DXY dialog did not open');
  await page.frameLocator('#gmfq-page').locator('.gmfq-dxy-dialog .gmfq-close').click();
  await page.frameLocator('#gmfq-page').locator('.mid > .panel:nth-child(2)').click();
  if(!page.url().includes('#/tassi?focus=2y'))throw Error('Native card navigation failed: '+page.url());
  // The approved Rates detail contains a renderer for eight countries.
  // Check that the additive Preview UI exposes all eight without replacing feeds.
  await page.waitForFunction(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    return d?.getElementById('rates-select')?.querySelectorAll('button[data-ccy]').length===8;
  },null,{timeout:20000});
  const ratesDetail=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page').contentDocument;
    return {
      currencies:[...d.querySelectorAll('#rates-select button[data-ccy]')].map(x=>x.dataset.ccy),
      activeSection:d.activeElement===d.getElementById('rates-rows')?.closest('.desk-panel'),
      hasPricing:!!d.getElementById('ois-rows')
    };
  });
  if(g8.some(c=>!ratesDetail.currencies.includes(c))||!ratesDetail.activeSection||
     !ratesDetail.hasPricing)throw Error(label+' rates focus/G8 detail failed: '+JSON.stringify(ratesDetail));
  await page.frameLocator('#gmfq-page').locator('#rates-select button[data-ccy="NZD"]').click();
  await page.waitForFunction(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    return d?.querySelector('#rates-select button[data-ccy="NZD"]')?.getAttribute('aria-pressed')==='true'
       && d?.getElementById('rates-status')?.textContent.includes('Nuova Zelanda');
  },null,{timeout:15000});
  await page.waitForFunction(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    return d?.querySelectorAll('#gmfq-pricing-research .gmfq-research-plot svg polyline').length===4;
  },null,{timeout:25000});
  // Sources are fetched asynchronously AFTER the four core pricing curves
  // render. Wait for all four individually linked source-readiness rows rather
  // than racing the still-loading "Stato fonti da aggiornare" placeholder.
  // Timeout still FAILS if the actual read-only source context is missing.
  await page.waitForFunction(expected=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    return d?.querySelectorAll('#gmfq-source-readiness .gmfq-source-row').length===expected&&
           d?.querySelectorAll('#gmfq-source-readiness .gmfq-source-link a').length===expected;
  },sourceIds.length,{timeout:25000});
  const research=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument,host=d?.getElementById('gmfq-pricing-research');
    return {
      fourCurves:host?.querySelectorAll('svg polyline').length,
      secondary:host?.querySelectorAll('.gmfq-quote-card').length,
      legend:host?.querySelector('.gmfq-research-legend')?.innerText,
      disclaimers:host?.textContent,
      snbSpot:host?.querySelector('#gmfq-chf-snb-10y-context')?.textContent,
      sourceStatus:host?.dataset.sourceStatus,
      visibleCount:host?.dataset.verifiedCurves,
      estimated:host?.dataset.estimatedLanes,withheld:host?.dataset.withheldLanes,
      readingText:host?.querySelector('.gmfq-pricing-core-status')?.textContent,
      disclosureClosed:host?.querySelector('#gmfq-pricing-evidence-details')?.open===false,
      secondaryHidden:!(host?.querySelector('.gmfq-quote-card')?.getClientRects().length),
      plotVisible:!!host?.querySelector('.gmfq-research-plot')?.getClientRects().length,
      sourceCount:host?.querySelectorAll('#gmfq-source-readiness .gmfq-source-row').length,
      sourceLinks:host?.querySelectorAll('#gmfq-source-readiness .gmfq-source-link a').length,
      sourceCurrencies:[...host?.querySelectorAll('#gmfq-source-readiness .gmfq-source-row b')||[]].map(x=>x.textContent),
      sourceDoc:host?.querySelector('#gmfq-source-readiness')?.textContent,
      chartWidth:host?.querySelector('.gmfq-research-plot')?.scrollWidth,
      docWidth:d?.documentElement.scrollWidth,viewport:d?.documentElement.clientWidth
    };
  });
  // The verified official count stays independent of mixed-date futures.
  // Secondary coverage may legitimately move GREEN_ESTIMATED -> WITHHELD;
  // never pin today's 2/2 split or treat the downgrade as data loss.
  const expectedOfficial=operational.summary.green_official;
  const expectedEstimated=operational.summary.green_estimated;
  const expectedWithheld=operational.summary.operational_withheld;
  const plottedOfficial=Object.entries(operational.currencies).filter(([c,r])=>
    r.operational_status==='GREEN_OFFICIAL'&&r.official_status==='ACTIVE'&&
    r.quality==='OFFICIAL_CERTIFIED'&&r.backtest_eligible_as_official===true&&
    current(r.as_of,4)&&
    ['3m','6m','12m'].every(t=>Number.isFinite(r.horizons?.[t]?.policy_delta_bp)))
    .map(([c])=>c);
  if(research.sourceStatus!=='READ_ONLY'||research.visibleCount!==String(expectedOfficial)||
     research.estimated!==String(expectedEstimated)||
     research.withheld!==String(expectedWithheld)||
     !research.disclosureClosed||!research.secondaryHidden||!research.plotVisible||
     !research.readingText?.includes(plottedOfficial.length+'/8')||
     !plottedOfficial.every(c=>research.readingText.includes(c)))
    throw Error(label+' Rates/OIS decision-first evidence failed '+JSON.stringify(research));
  if(research.fourCurves!==plottedOfficial.length||research.secondary!==expectedSecondaryQuotes||
     !plottedOfficial.every(c=>research.legend.includes(c))||
     !research.disclaimers.includes('NON curva OIS')&&
      !research.disclaimers.includes('non sono una curva OIS')||
     !research.disclaimers.includes('NON curva OIS né policy delta')||
     !research.disclaimers.includes('CHF 2Y/10Y')||
     !research.disclaimers.includes('Le curve sintetizzano prezzi per scadenza')||
     !research.snbSpot?.includes('CHF 10Y SNB '+Number(snbSpot.value_percent).toFixed(3)+'%')||
     !research.snbSpot.includes(snbSpot.as_of)||!research.snbSpot.includes('SOLO INFORMATIVO')||
     !research.snbSpot.includes('nessuno spread o segnale')||
     research.sourceCount!==sourceIds.length||research.sourceLinks!==sourceIds.length||
     !sourceIds.every(c=>research.sourceCurrencies.some(x=>x.includes(c)))||
     !research.sourceDoc.includes('non completa il 2Y')||
     !research.sourceDoc.includes('Nessun dato indicativo è promosso')||
     research.docWidth>research.viewport+16)
     throw Error(label+' Pricing research traceability failed: '+JSON.stringify(research));
  // Both technical research and official Swiss context remain accessible
  // behind the native summary without changing the four certified curves.
  await page.frameLocator('#gmfq-page').locator('#gmfq-pricing-evidence-details > summary').click();
  const expanded=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    const p=d?.getElementById('gmfq-pricing-research');
    return {open:p?.querySelector('#gmfq-pricing-evidence-details')?.open,
      secondaryVisible:!!p?.querySelector('.gmfq-quote-card')?.getClientRects().length,
      swissVisible:!!p?.querySelector('#gmfq-chf-snb-10y-context')?.getClientRects().length,
      sourceDetailPresent:!!p?.querySelector('#gmfq-source-readiness')};
  });
  if(!expanded.open||!expanded.secondaryVisible||!expanded.swissVisible||
     !expanded.sourceDetailPresent)
    throw Error(label+' Rates full source research unavailable '+JSON.stringify(expanded));
  console.log('CONTROL_ROOM_V10_RATES_DECISION_FIRST_GREEN',label,{status:research.sourceStatus,sourceCount:research.fourCurves,withheld:research.withheld});
  if(!plottedOfficial.length)throw Error(label+' no valid official curve to filter');
  await page.frameLocator('#gmfq-page').locator(
    '#gmfq-pricing-research button[data-pricing-ccy="'+plottedOfficial[0]+'"]').click();
  const selectedCurveCount=await page.frameLocator('#gmfq-page').locator('#gmfq-pricing-research svg polyline').count();
  if(selectedCurveCount!==1)throw Error(label+' single bank curve filter failed');
  await page.frameLocator('#gmfq-page').locator('#gmfq-pricing-research button[data-pricing-ccy="ALL"]').click();
  await page.screenshot({path:'v10-qa-images/'+label+'-rates-g8-detail.png',fullPage:true});

  // Central banks: same operational source semantics as Rates; policy
  // decision dates are historical snapshots, NOT live bank decisions.
  const cbFixture=JSON.parse(fs.readFileSync(path.join(DATA,'NATIVE_CB_DATA.json'),'utf8'));
  await page.goto(url+'#/banche?ccy=USD',{waitUntil:'domcontentloaded',timeout:120000});
  await page.waitForFunction(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    return ['READ_ONLY','WITHHELD'].includes(
      d?.getElementById('gmfq-cb-reading-first')?.dataset.readingStatus);
  },null,{timeout:35000});
  const cbFirst=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page').contentDocument,
      p=d.getElementById('gmfq-cb-reading-first'),det=p.querySelector('details');
    return {status:p.dataset.readingStatus,first:p.dataset.policyEarliest,
      last:p.dataset.policyLatest,certified:p.dataset.certified,
      estimated:p.dataset.estimated,withheld:p.dataset.withheld,
      priority:p.querySelector('.gmfq-first-priority')?.textContent,
      evidence:p.querySelector('.gmfq-first-claim')?.textContent,
      order:!!(p.querySelector('.gmfq-first-priority')?.compareDocumentPosition(p.querySelector('.gmfq-first-claim'))&Node.DOCUMENT_POSITION_FOLLOWING),
      text:p.textContent,closed:det.open===false,
      chart:!!d.getElementById('cb-chart'),table:!!d.getElementById('cb-table'),
      width:p.scrollWidth,client:p.clientWidth,
      doc:d.documentElement.scrollWidth,viewport:d.documentElement.clientWidth};
  });
  if(cbFirst.status!=='READ_ONLY'||cbFirst.certified!==String(operational.summary.green_official)||
     cbFirst.estimated!==String(operational.summary.green_estimated)||
     cbFirst.withheld!==String(operational.summary.operational_withheld)||cbFirst.first!==Object.values(cbFixture).map(x=>x.last_date).sort()[0]||
     cbFirst.last!==Object.values(cbFixture).map(x=>x.last_date).sort().at(-1)||
     !cbFirst.closed||!cbFirst.chart||!cbFirst.table||
     !cbFirst.text.includes('futures monetari')||!cbFirst.text.includes('Repricing ≠ probabilità')||
     !cbFirst.priority?.startsWith('Le ultime decisioni sono snapshot storici')||
     !cbFirst.evidence?.includes('Pricing 6M certificato')||!cbFirst.order||
     cbFirst.width>cbFirst.client+2||cbFirst.doc>cbFirst.viewport+16)
    throw Error(label+' CB first reading or native chart not intact '+JSON.stringify(cbFirst));
  await page.frameLocator('#gmfq-page').locator('#gmfq-cb-reading-first details>summary').press('Enter');
  const cbFull=await page.frameLocator('#gmfq-page').locator('#gmfq-cb-reading-first details p').last().isVisible();
  if(!cbFull)throw Error(label+' CB provenance not keyboard accessible');
  await page.screenshot({path:'v10-qa-images/'+label+'-cb-reading-first.png',fullPage:true});
  // Negative policy fixture: future meeting missing MUST invalidate the first
  // reading rather than silently label the last policy snapshot current.
  await page.route('**/NATIVE_CB_DATA.json',async r=>{
    const x=JSON.parse(fs.readFileSync(path.join(DATA,'NATIVE_CB_DATA.json'),'utf8'));
    x.USD.next_meeting='2099-13-50';
    await r.fulfill({status:200,contentType:'application/json',body:JSON.stringify(x),
      headers:{'Access-Control-Allow-Origin':'*'}});
  });
  await page.goto(url+'#/home',{waitUntil:'domcontentloaded',timeout:120000});
  await page.goto(url+'#/banche?ccy=EUR&bad=meeting',{waitUntil:'domcontentloaded',timeout:120000});
  await page.waitForFunction(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    return d?.getElementById('gmfq-cb-reading-first')?.dataset.readingStatus==='WITHHELD';
  },null,{timeout:35000});
  await page.unroute('**/NATIVE_CB_DATA.json');

  // CFTC: all eight 104W series must be internally consistent. USD 79.8077
  // rounds to 80th, while the historical narrative still says NEUTRALE;
  // display this conflict openly, never alter the canonical source.
  const cotFixture=JSON.parse(fs.readFileSync(path.join(DATA,'V250_COT_CHART_DATA.json'),'utf8'));
  await page.goto(url+'#/home',{waitUntil:'domcontentloaded',timeout:120000});
  await page.goto(url+'#/cot?ccy=USD',{waitUntil:'domcontentloaded',timeout:120000});
  await page.waitForFunction(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    return ['SOURCE_DIVERGENCE','READ_ONLY','WITHHELD'].includes(
      d?.getElementById('gmfq-cot-reading-first')?.dataset.readingStatus);
  },null,{timeout:35000});
  const cotFirst=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page').contentDocument,
      p=d.getElementById('gmfq-cot-reading-first');
    return {status:p.dataset.readingStatus,asof:p.dataset.cftcAsOf,
      extremes:p.dataset.extremes,crowding:p.dataset.crowding,conflicts:p.dataset.conflicts,
      priority:p.querySelector('.gmfq-first-priority')?.textContent,
      evidence:p.querySelector('.gmfq-first-claim')?.textContent,
      order:!!(p.querySelector('.gmfq-first-priority')?.compareDocumentPosition(p.querySelector('.gmfq-first-claim'))&Node.DOCUMENT_POSITION_FOLLOWING),
      text:p.textContent,closed:p.querySelector('details').open===false,
      chart:!!d.getElementById('cot-chart'),table:!!d.getElementById('cot-table'),
      width:p.scrollWidth,client:p.clientWidth,
      doc:d.documentElement.scrollWidth,viewport:d.documentElement.clientWidth};
  });
  if(cotFirst.status!=='READ_ONLY'||cotFirst.conflicts!==''||
     cotFirst.asof!==cotFixture.USD.dates.at(-1)||
     cotFirst.extremes!=='5'||cotFirst.crowding!=='3'||
     !cotFirst.closed||!cotFirst.chart||!cotFirst.table||
     !cotFirst.text.includes('Prezzo FX: WITHHELD')||
     !cotFirst.priority?.startsWith('Gli estremi COT descrivono')||
     !cotFirst.evidence?.includes('Estremi percentile 104W')||!cotFirst.order||
     cotFirst.text.includes('narrativo incoerente')||
     cotFirst.width>cotFirst.client+2||cotFirst.doc>cotFirst.viewport+16)
    throw Error(label+' COT quantitative/narrative divergence guard '+JSON.stringify(cotFirst));
  await page.frameLocator('#gmfq-page').locator('#gmfq-cot-reading-first details>summary').press('Enter');
  if(!(await page.frameLocator('#gmfq-page').locator('#gmfq-cot-reading-first details p').last().isVisible()))
    throw Error(label+' COT CFTC provenance not keyboard accessible');
  await page.screenshot({path:'v10-qa-images/'+label+'-cot-reading-first.png',fullPage:true});
  // Negative fixture: intentionally regress just the USD narrative,
  // preserving all numeric CFTC evidence; the cross-source audit MUST flag it.
  await page.route('**/V247_COT_STORIES.json',async r=>{
    const x=JSON.parse(fs.readFileSync(path.join(DATA,'V247_COT_STORIES.json'),'utf8'));
    x.USD.signal='NEUTRALE';
    await r.fulfill({status:200,contentType:'application/json',body:JSON.stringify(x),
      headers:{'Access-Control-Allow-Origin':'*'}});
  });
  await page.goto(url+'#/home',{waitUntil:'domcontentloaded',timeout:120000});
  await page.goto(url+'#/cot?ccy=USD&bad=story',{waitUntil:'domcontentloaded',timeout:120000});
  await page.waitForFunction(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument,p=d?.getElementById('gmfq-cot-reading-first');
    return p?.dataset.readingStatus==='SOURCE_DIVERGENCE'&&p.dataset.conflicts==='USD';
  },null,{timeout:35000});
  await page.unroute('**/V247_COT_STORIES.json');
  await page.route('**/V250_COT_CHART_DATA.json',async r=>{
    const x=JSON.parse(fs.readFileSync(path.join(DATA,'V250_COT_CHART_DATA.json'),'utf8'));
    x.GBP.net[x.GBP.net.length-1]+=1; // breaks long-short = net contract
    await r.fulfill({status:200,contentType:'application/json',body:JSON.stringify(x),
      headers:{'Access-Control-Allow-Origin':'*'}});
  });
  await page.goto(url+'#/home',{waitUntil:'domcontentloaded',timeout:120000});
  await page.goto(url+'#/cot?ccy=GBP&bad=net',{waitUntil:'domcontentloaded',timeout:120000});
  await page.waitForFunction(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    return d?.getElementById('gmfq-cot-reading-first')?.dataset.readingStatus==='WITHHELD';
  },null,{timeout:35000});
  await page.unroute('**/V250_COT_CHART_DATA.json');
  console.log('CONTROL_ROOM_V10_CB_COT_FIRST_READING_GREEN',label,{
    policy:cbFirst.status,ois:cbFirst.certified,cot:cotFirst.asof,
    extremes:cotFirst.extremes,crowding:cotFirst.crowding,conflict:cotFirst.conflicts});

  // Macro provenance: historical model scores cannot be refreshed by newer,
  // independently dated Inflation/Labour observations.
  const oldModel=JSON.parse(fs.readFileSync(path.join(DATA,'D.json'),'utf8'));
  const macroThermo=JSON.parse(fs.readFileSync(path.join(DATA,'MACRO_THERMOMETER_DATA.json'),'utf8'));
  await page.goto(url+'#/macro?ccy=EUR',{waitUntil:'domcontentloaded',timeout:120000});
  await page.waitForFunction(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    return d?.getElementById('gmfq-macro-source-lens')?.dataset.auditStatus==='READ_ONLY';
  },null,{timeout:40000});
  const macroLens=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    const p=d.getElementById('gmfq-macro-source-lens');
    const w=p.scrollWidth,c=p.clientWidth;
    p.style.display='none';
    const nativeWidth=d.documentElement.scrollWidth;
    p.style.display='';
    return {status:p.dataset.auditStatus,baseline:p.dataset.baselineAsOf,
      selected:p.dataset.selectedCurrency,
      priority:p.querySelector('.gmfq-macro-takeaway')?.textContent,
      priorityFirst:!!(p.querySelector('.gmfq-macro-takeaway')?.compareDocumentPosition(p.querySelector('.gmfq-macro-state'))&Node.DOCUMENT_POSITION_FOLLOWING),
      observations:p.querySelectorAll('.gmfq-macro-observation').length,
      description:p.textContent,
      preview:p.querySelector('#gmfq-macro-reading')?.textContent,
      fullClosed:p.querySelector('#gmfq-macro-observation-details')?.open===false,
      observationsHidden:![...p.querySelectorAll('.gmfq-macro-observation')].some(x=>x.getClientRects().length>0),
      innerScroll:w,innerClient:c,nativeWidth,
      docWidth:d.documentElement.scrollWidth,viewport:d.documentElement.clientWidth};
  });
  if(macroLens.baseline!==oldModel.asOf||macroLens.selected!=='EUR'||
     !macroLens.priority?.startsWith('Gli score sono uno snapshot del modello')||!macroLens.priorityFirst||
     macroLens.observations!==2||!macroLens.fullClosed||!macroLens.observationsHidden||
     !macroLens.preview?.includes(macroThermo.currencies.EUR.inflation.as_of)||
     !macroLens.preview?.includes(macroThermo.currencies.EUR.labour.as_of)||
     !macroLens.description.includes('NON CORRENTE, da rivalidare')||
     !macroLens.description.includes(macroThermo.currencies.EUR.inflation.as_of)||
     !macroLens.description.includes(macroThermo.currencies.EUR.labour.as_of)||
     !macroLens.description.includes('non aggiornano i 24 score')||
     macroLens.innerScroll>macroLens.innerClient+2||
     macroLens.docWidth>Math.max(macroLens.viewport+16,macroLens.nativeWidth+2))
   throw Error(label+' Macro data-provenance guard failed '+JSON.stringify(macroLens));
  await page.frameLocator('#gmfq-page').locator('#gmfq-macro-provenance-currency').selectOption('JPY');
  const switched=await page.evaluate(()=>{
    const p=document.getElementById('gmfq-page')?.contentDocument?.getElementById('gmfq-macro-source-lens');
    return {ccy:p?.dataset.selectedCurrency,text:p?.textContent,hash:location.hash};
  });
  if(switched.ccy!=='JPY'||!switched.text.includes(macroThermo.currencies.JPY.inflation.as_of)||
     !switched.text.includes(macroThermo.currencies.JPY.labour.as_of)||
     switched.hash!=='#/macro?ccy=JPY')
    throw Error(label+' Macro currency synchronization failed '+JSON.stringify(switched));
  // Expand full values and provenance with keyboard, without changing any score.
  await page.frameLocator('#gmfq-page').locator('#gmfq-macro-observation-details>summary').press('Enter');
  const macroExpanded=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    const p=d.getElementById('gmfq-macro-source-lens');
    return {open:p.querySelector('#gmfq-macro-observation-details').open,
      visible:[...p.querySelectorAll('.gmfq-macro-observation')].every(x=>x.getClientRects().length>0),
      sources:p.querySelector('#gmfq-macro-source-details')?.textContent.includes('Fonte ')};
  });
  if(!macroExpanded.open||!macroExpanded.visible||!macroExpanded.sources)
    throw Error(label+' Macro detailed observations inaccessible '+JSON.stringify(macroExpanded));
  await page.screenshot({path:'v10-qa-images/'+label+'-macro-provenance.png',fullPage:true});
  // Negative fixture: invalid reference period cannot become current data.
  await page.route('**/MACRO_THERMOMETER_DATA.json',async r=>{
    const invalid=JSON.parse(fs.readFileSync(path.join(DATA,'MACRO_THERMOMETER_DATA.json'),'utf8'));
    invalid.currencies.USD.inflation.as_of='2099-12';
    await r.fulfill({status:200,contentType:'application/json',
      headers:{'Access-Control-Allow-Origin':'*'},body:JSON.stringify(invalid)});
  });
  await page.goto(url+'#/home',{waitUntil:'domcontentloaded',timeout:120000});
  await page.goto(url+'#/macro?ccy=USD&test=invalid',{waitUntil:'domcontentloaded',timeout:120000});
  await page.waitForFunction(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    const p=d?.getElementById('gmfq-macro-source-lens');
    return p?.dataset.auditStatus==='READ_ONLY'&&p?.dataset.selectedCurrency==='USD'&&
      p.querySelector('#gmfq-macro-source-details')?.textContent.includes('Inflazione · dato WITHHELD');
  },null,{timeout:40000});
  const invalidMacro=await page.evaluate(()=>{
    const p=document.getElementById('gmfq-page')?.contentDocument?.getElementById('gmfq-macro-source-lens');
    return {html:p?.querySelector('#gmfq-macro-source-details')?.textContent,ccy:p?.dataset.selectedCurrency};
  });
  if(invalidMacro.ccy!=='USD'||!invalidMacro.html.includes('Inflazione · dato WITHHELD')||
     !invalidMacro.html.includes(macroThermo.currencies.USD.labour.as_of))
    throw Error(label+' invalid Macro thermometer did not fail closed '+JSON.stringify(invalidMacro));
  await page.unroute('**/MACRO_THERMOMETER_DATA.json');
  console.log('CONTROL_ROOM_V10_MACRO_PROVENANCE_GREEN',label,{
    baseline:macroLens.baseline,selected:'EUR / JPY',missing:'WITHHELD'});

  // Read-only Valute compass: ECB official fixing, synthesized DXY and historic
  // Macro snapshot keep separate semantics even with all eight country views.
  const fxHistory=JSON.parse(fs.readFileSync(path.join(DATA,'ECB_G8_PRICE_HISTORY.json'),'utf8'));
  const legacy=JSON.parse(fs.readFileSync(path.join(DATA,'D.json'),'utf8'));
  await page.goto(url+'#/valute?ccy=GBP',{waitUntil:'domcontentloaded',timeout:120000});
  await page.waitForFunction(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    return ['OFFICIAL_FIXING_RECENT','WITHHELD'].includes(
      d?.getElementById('gmfq-valute-source-compass')?.dataset.sourceStatus);
  },null,{timeout:30000});
  const valute=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument,
      p=d.getElementById('gmfq-valute-source-compass');
    const innerWidth=p.scrollWidth,innerClient=p.clientWidth;
    p.style.display='none';const nativeWidth=d.documentElement.scrollWidth;p.style.display='';
    return {fx:p.dataset.fxAsOf,dxy:p.dataset.dxyStatus,macro:p.dataset.macroAsOf,
      text:p.textContent,detail:!!p.querySelector('details summary'),
      priority:p.querySelector('.gmfq-vsc-priority')?.textContent,
      sourceKeys:[...p.querySelectorAll('.gmfq-vsc-ledger span[data-source]')].map(x=>x.dataset.source),
      priorityFirst:!!(p.querySelector('.gmfq-vsc-priority')?.compareDocumentPosition(p.querySelector('.gmfq-vsc-ledger'))&Node.DOCUMENT_POSITION_FOLLOWING),
      innerWidth,innerClient,nativeWidth,width:d.documentElement.scrollWidth,viewport:d.documentElement.clientWidth};
  });
  if(valute.fx!==fxHistory.last_as_of||valute.macro!==legacy.asOf||
     valute.dxy!=='SYNTHETIC_ECB'||!valute.detail||
     !valute.priority?.startsWith('Fixing giornaliero, DXY sintetico')||!valute.priorityFirst||
     JSON.stringify(valute.sourceKeys)!==JSON.stringify(['fixing','dxy','macro'])||
     !valute.text.includes('non il DXY ICE ufficiale')||
     !valute.text.includes('non un nuovo ranking di forza relativa')||
     valute.innerWidth>valute.innerClient+2||
     valute.width>Math.max(valute.viewport+16,valute.nativeWidth+2))
    throw Error(label+' Valute provenance contract '+JSON.stringify(valute));
  await page.screenshot({path:'v10-qa-images/'+label+'-valute-sources.png',fullPage:true});
  // Negative ECB fixture: missing one G8 spot leg invalidates the aggregate
  // official-fixing claim, without altering underlying ranking/bias.
  await page.route('**/ECB_G8_PRICE_HISTORY.json',async r=>{
    const x=JSON.parse(fs.readFileSync(path.join(DATA,'ECB_G8_PRICE_HISTORY.json'),'utf8'));
    x.rows[x.rows.length-1].CHF=null;
    await r.fulfill({status:200,contentType:'application/json',
      headers:{'Access-Control-Allow-Origin':'*'},body:JSON.stringify(x)});
  });
  await page.goto(url+'#/home',{waitUntil:'domcontentloaded',timeout:120000});
  await page.goto(url+'#/valute?ccy=CHF&invalid=1',{waitUntil:'domcontentloaded',timeout:120000});
  await page.waitForFunction(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    return d?.getElementById('gmfq-valute-source-compass')?.dataset.sourceStatus==='WITHHELD';
  },null,{timeout:30000});
  const invalidFx=await page.evaluate(()=>{
    const p=document.getElementById('gmfq-page')?.contentDocument?.getElementById('gmfq-valute-source-compass');
    return {status:p.dataset.sourceStatus,fx:p.dataset.fxAsOf,text:p.textContent};
  });
  if(invalidFx.fx!==''||!invalidFx.text.includes('FX BCE non corrente o non verificabile'))
    throw Error(label+' Valute invalid FX not withheld '+JSON.stringify(invalidFx));
  // SAME invalid ECB fixture must be WITHHELD in the Home audit and Pair
  // Deep Dive, not only in Valute. No canonical engine field is modified.
  await page.goto(url+'#/home?source-parity-test=1',{waitUntil:'domcontentloaded',timeout:120000});
  await page.waitForFunction(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    return !!d?.getElementById('gmfq-home-data-audit')&&
      d.getElementById('gmfq-home-data-audit').textContent.includes('FX G8 · fixing BCE');
  },null,{timeout:30000});
  const homeNegative=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    return {stamp:d?.querySelector('#liveAsOf')?.textContent,
      source:d?.getElementById('gmfq-home-data-audit')?.textContent};
  });
  const badRail=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    const x=d?.getElementById('gmfq-home-reading-path');
    return {fx:x?.dataset.fxAsOf,text:x?.textContent};
  });
  if(badRail.fx!==''||!badRail.text.includes('fixing BCE non verificato'))
    throw Error(label+' invalid FX fixing wrongly promoted in Home priorities '+JSON.stringify(badRail));
  if(!homeNegative.stamp.includes('FX non corr.')||
     !homeNegative.source.includes('Non corrente o non disponibile'))
    throw Error(label+' Home did not mirror Valute FX WITHHELD '+JSON.stringify(homeNegative));
  await page.goto(url+'#/coppie?pair=EURUSD&source-parity-test=1',{waitUntil:'domcontentloaded',timeout:120000});
  await page.waitForFunction(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    const p=d?.getElementById('gmfq-pair-research-path');
    return p?.dataset.pair==='EURUSD'&&p.textContent.includes('Fixing BCE: non verificato');
  },null,{timeout:30000});
  const pairNegative=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument,p=d?.getElementById('gmfq-pair-research-path');
    return {path:p?.textContent?.slice(0,1200),
      reaction:d?.getElementById('gmfq-pair-reaction-audit')?.dataset.reactionStatus||
        p?.querySelector('.gmfq-reaction')?.getAttribute('data-reaction-status')};
  });
  if(!pairNegative.path.includes('Fixing BCE: non verificato'))
    throw Error(label+' Pair did not mirror Valute FX WITHHELD '+JSON.stringify(pairNegative));
  console.log('CONTROL_ROOM_V10_CROSS_PAGE_FX_WITHHELD_GREEN',label,{
    home:'WITHHELD',valute:'WITHHELD',pair:'WITHHELD'});

  await page.unroute('**/ECB_G8_PRICE_HISTORY.json');
  console.log('CONTROL_ROOM_V10_VALUTE_SOURCE_SEPARATION_GREEN',label,{fixing:valute.fx,baseline:valute.macro,negative:'WITHHELD'});

  // Reconcile the three independently rendered dates on the four research
  // surfaces. The score's baseline is not made current by a newer fixing.
  if(valute.macro!==oldModel.asOf||macroLens.baseline!==valute.macro||
     valute.fx!==fxData.last_as_of||
     setupFeed.macro_baseline_asof!==valute.macro)
    throw Error(label+' cross-page date divergence: '+JSON.stringify({
      macro:macroLens.baseline,valute:valute.macro,fixing:valute.fx,setup:setupFeed.macro_baseline_asof}));
  console.log('CONTROL_ROOM_V10_CROSS_PAGE_SOURCE_PARITY_GREEN',label,{
    macro:valute.macro,fixing:valute.fx,setup:setupFeed.price_asof});

  // Read-only Screener: all NON VALUTABILE reasons must come from the canonical
  // decision_frame, without changing its judgments or layout on mobile.
  await page.goto(url+'#/screener',{waitUntil:'domcontentloaded',timeout:120000});
  await page.waitForFunction(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    return d?.getElementById('gmfq-screener-blockers')?.dataset.diagnosisStatus==='READ_ONLY';
  },null,{timeout:40000});
  const reasons=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    const p=d.getElementById('gmfq-screener-blockers');
    const innerScroll=p.scrollWidth,innerClient=p.clientWidth;
    p.style.display='none';
    const nativeWidth=d.documentElement.scrollWidth;
    p.style.display='';
    return {nativeWidth,innerScroll,innerClient,baseline:p?.dataset.macroBaselineAsOf,
      count:p?.querySelectorAll('button.gmfq-blocker-pair[data-pair]').length,
      groups:Object.fromEntries(['CONFLICT','RATES_ONLY','INSUFFICIENT'].map(k=>[
        k,[...(p.querySelector('[data-reason="'+k+'"]')?.querySelectorAll('button[data-pair]')||[])].map(b=>b.dataset.pair)
      ])),
      stale:p?.textContent.includes('NON CORRENTE, tesi da rivalidare'),
      descriptive:p?.textContent.includes('non crea da solo una preferenza FX'),
      summary:p?.querySelector('.gmfq-blocker-overview')?.textContent,
      priority:p?.querySelector('.gmfq-blocker-priority')?.textContent,
      priorityFirst:!!(p.querySelector('.gmfq-blocker-priority')?.compareDocumentPosition(p.querySelector('.gmfq-blocker-overview'))&Node.DOCUMENT_POSITION_FOLLOWING),
      sources:[...p.querySelectorAll('.gmfq-blocker-date span[data-source]')].map(x=>x.dataset.source),
      detailsClosed:p?.querySelector('#gmfq-blocker-details')?.open===false,
      pairButtonsHidden:![...p?.querySelectorAll('.gmfq-blocker-pair')||[]].some(x=>x.getClientRects().length>0),
      width:d.documentElement.scrollWidth,viewport:d.documentElement.clientWidth};
  });
  const nonVal=Object.entries(setupFeed.pairs).filter(([,r])=>r.setup.quality==='NON VALUTABILE');
  const expectedGroups={CONFLICT:[],RATES_ONLY:[],INSUFFICIENT:[]};
  for(const [code,row] of nonVal){
    const k={'PILASTRI DIVISI':'CONFLICT','SEPARAZIONE RATES MATERIALE':'RATES_ONLY',
      'NESSUN CONTRASTO':'INSUFFICIENT'}[row.decision_frame.quality];
    if(!k)throw Error(label+' fixture reason unknown '+code);
    expectedGroups[k].push(code);
  }
  for(const k of Object.keys(expectedGroups)){
    if(JSON.stringify(reasons.groups[k])!==JSON.stringify(expectedGroups[k].sort()))
      throw Error(label+' screener '+k+' reason mismatch '+JSON.stringify(reasons));
  }
  if(reasons.count!==nonVal.length||
     !reasons.priority?.startsWith('Le coppie senza una tesi coerente')||!reasons.priorityFirst||
     JSON.stringify(reasons.sources)!==JSON.stringify(['macro','price'])||
     !reasons.detailsClosed||!reasons.pairButtonsHidden||
     !reasons.summary?.includes('Macro vs Tassi/CB: '+expectedGroups.CONFLICT.length)||
     !reasons.summary?.includes('Differenziale 2Y senza tesi: '+expectedGroups.RATES_ONLY.length)||
     !reasons.summary?.includes('Vantaggio insufficiente: '+expectedGroups.INSUFFICIENT.length)||
     reasons.baseline!==setupFeed.macro_baseline_asof||
     !reasons.descriptive||reasons.innerScroll>reasons.innerClient+2||
     reasons.width>Math.max(reasons.viewport+16,reasons.nativeWidth+2))
    throw Error(label+' screener reason contract failed '+JSON.stringify(reasons));
  await page.screenshot({path:'v10-qa-images/'+label+'-screener-reasons.png',fullPage:true});
  await page.frameLocator('#gmfq-page').locator('#gmfq-blocker-details>summary').press('Enter');
  const openedReasons=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    const p=d?.getElementById('gmfq-screener-blockers');
    return {open:p?.querySelector('#gmfq-blocker-details')?.open,
      visible:p?.querySelector('button[data-pair="GBPJPY"]')?.getClientRects().length>0};
  });
  if(!openedReasons.open||!openedReasons.visible)
    throw Error(label+' Screener detailed reasons inaccessible '+JSON.stringify(openedReasons));
  await page.frameLocator('#gmfq-page').locator('#gmfq-screener-blockers button[data-pair="GBPJPY"]').click();
  await page.waitForURL(u=>u.hash==='#/coppie?pair=GBPJPY',{timeout:20000});

  // Home -> canonical Pair Deep Dive (not a generic Screener). Preserve all
  // 28 canonical G8 pairs and selected-pair permalink across changes.
  await page.goto(url+'#/home',{waitUntil:'domcontentloaded',timeout:120000});
  await page.waitForFunction(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    return d?.documentElement?.dataset.liveState==='LOADED'&&
      d.querySelectorAll('#pairs tr[data-filter]').length>0;
  },null,{timeout:40000});
  const fromHome=await page.frameLocator('#gmfq-page').locator('#pairs tr[data-filter]').first().getAttribute('data-filter');
  if(!/^[A-Z]{6}$/.test(fromHome||''))throw Error(label+' invalid home pair');
  await page.frameLocator('#gmfq-page').locator('#pairs tr[data-filter]').first().click();
  await page.waitForURL(u=>u.hash==='#/coppie?pair='+fromHome,{timeout:15000});
  await page.waitForFunction(code=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    return d?.documentElement?.dataset.pairState==='READY'&&
      d.querySelectorAll('#pair-index button.pair-open[data-pair]').length===28&&
      d.getElementById('gmfq-pair-research-path')?.dataset.pair===code;
  },fromHome,{timeout:30000});
  const first=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    const panel=d?.getElementById('gmfq-pair-research-path');
    return {count:d?.querySelectorAll('#pair-index button.pair-open[data-pair]').length,
      currencies:d?.querySelectorAll('#gmfq-pair-research-path .gmfq-path-leg').length,
      links:d?.querySelectorAll('#gmfq-pair-research-path button[data-gmfq-study-currency]').length,
      model:panel?.textContent.includes('non aggiorna automaticamente il giudizio del motore')||
        panel?.textContent.includes('La data del fixing e quella del motore coincidono'),
      width:d?.documentElement.scrollWidth,viewport:d?.documentElement.clientWidth};
  });
  if(first.count!==28||first.currencies!==2||first.links!==8||
     !first.model||first.width>first.viewport+16)
    throw Error(label+' pair deep-dive route/model-date guard failed '+JSON.stringify(first));
  // Decision-first: show thesis/setup/reaction, keep all analytical DOM intact.
  const reading=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    const p=d?.getElementById('gmfq-pair-research-path');
    const details=p?.querySelector('#gmfq-pair-full-research');
    const decision=p?.querySelector('#gmfq-pair-decision-bridge');
    const comparison=p?.querySelector('#gmfq-pair-macro-rates');
    const stamps=p?.querySelector('.gmfq-path-evidence');
    const cols=decision?.querySelector('.gmfq-decision-cols');
    const col=cols?.firstElementChild;
    const win=d?.defaultView;
    const gridCols=cols?win.getComputedStyle(cols).gridTemplateColumns.trim().split(/\s+/).length:0;
    const cleanBg=col?win.getComputedStyle(col).backgroundColor:null;
    return {closed:details?.open===false,
      before:!!decision&&!!details&&
        !!(decision.compareDocumentPosition(details)&Node.DOCUMENT_POSITION_FOLLOWING),
      decisionVisible:!!decision?.getClientRects().length,
      technicalHidden:!!comparison&&!comparison.getClientRects().length,
      comparePresent:!!comparison,compareInDisclosure:!!comparison&&!!details?.contains(comparison),
      technicalRects:comparison?.getClientRects().length,
      detailsHtmlStart:details?.innerHTML?.slice(0,350),
      sourcePresent:!!p?.querySelector('#gmfq-pair-market-reaction')&&
        !!p?.querySelector('#gmfq-pair-what-changed')&&
        p.querySelectorAll('button[data-gmfq-study-currency]').length===8,
      sourceKeys:[...stamps?.querySelectorAll('span[data-source]')||[]].map(x=>x.dataset.source),
      sourceText:stamps?.textContent,
      macroSource:stamps?.dataset.macroState,
      decisionGrid:gridCols,
      decisionBackground:cleanBg,
      innerWidth:d?.documentElement.clientWidth};
  });
  if(!reading.closed||!reading.before||!reading.decisionVisible||
     !reading.technicalHidden||!reading.sourcePresent||
     JSON.stringify(reading.sourceKeys)!==JSON.stringify(['macro','price','fixing'])||
     reading.macroSource!=='HISTORICAL'||
     !reading.sourceText?.includes('Baseline Macro/Tassi: '+setupFeed.macro_baseline_asof)||
     !reading.sourceText.includes('Prezzo del modello: '+setupFeed.price_asof)||
     !reading.sourceText.includes('Fixing BCE:')||
     reading.sourceText.includes('Valuta favorita dal motore:')||
     reading.decisionGrid!==(reading.innerWidth<=700?1:3)||
     !['transparent','rgba(0, 0, 0, 0)'].includes(reading.decisionBackground))
    throw Error(label+' Pair decision-first editorial hierarchy failed '+JSON.stringify(reading));
  console.log('CONTROL_ROOM_V10_DECISION_FIRST_GREEN',label,reading);

  // Selecting a non-USD cross updates both the original detail and our
  // additive research path; a permalink to the currently selected pair remains.
  await page.frameLocator('#gmfq-page').locator('#pair-index button.pair-open[data-pair="EURCHF"]').click();
  await page.waitForFunction(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    return d?.getElementById('gmfq-pair-research-path')?.dataset.pair==='EURCHF';
  },null,{timeout:12000});
  const selectedHash=await page.evaluate(()=>location.hash);
  if(selectedHash!=='#/coppie?pair=EURCHF')
    throw Error(label+' EURCHF permalink not updated: '+selectedHash);
  const detail=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    return {name:d?.querySelector('#pair-detail .desk-kicker')?.textContent,
      text:d?.getElementById('gmfq-pair-research-path')?.textContent,
      g8:d?.querySelectorAll('#pair-index button.pair-open[data-pair]').length,
      width:d?.documentElement.scrollWidth,viewport:d?.documentElement.clientWidth};
  });
  if(!detail.name?.includes('EURCHF')||!detail.text?.includes('ECB')||
    !detail.text?.includes('CHF')||
    !(detail.text?.includes('non aggiorna automaticamente')||
      detail.text?.includes('La data del fixing e quella del motore coincidono'))||
    detail.g8!==28||detail.width>detail.viewport+16)
    throw Error(label+' EURCHF selected-pair research context failed '+JSON.stringify(detail));

  // Macro/CB labels come from the certified engine, never from reconstructed
  // government-yield gaps. CHF is stale: its 2Y/10Y and same-day spread
  // cannot be upgraded by a separate official SNB 10Y observation.
  const compareCHF=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page').contentDocument,c=d?.getElementById('gmfq-pair-macro-rates');
    return {title:c?.querySelector('h3')?.textContent,labels:[...c?.querySelectorAll('.gmfq-compare-score strong')||[]].map(x=>x.textContent),
      dates:[...c?.querySelectorAll('.gmfq-compare-leg')||[]].map(x=>x.textContent),
      same:c?.querySelector('.gmfq-compare-spread')?.dataset.sameDate,spread:c?.querySelector('.gmfq-compare-spread')?.textContent,
      disclaimer:c?.querySelector('.gmfq-compare-disclaimer')?.textContent};
  });
  if(!compareCHF.title?.includes('EUR /')||compareCHF.labels.length!==2||
     compareCHF.same!=='false'||!compareCHF.spread.includes('WITHHELD')||
     !compareCHF.dates.some(x=>x.includes('CHF')&&x.includes('2Y / 10Y WITHHELD'))||
     !compareCHF.disclaimer.includes('non sottrarre i loro delta'))
    throw Error(label+' CHF cross-date model/readiness guard broken '+JSON.stringify(compareCHF));
  // An unofficial 6M future can be shown as a dated LEVEL while the certified
  // monetary-policy delta remains unavailable. Test the separation in-browser.
  for(const code of ['CHF','EUR']){
    const op=operational.currencies[code],p=op?.horizons?.['6m'];
    const quote=code==='EUR'?op.secondary_quote_context?.horizons?.['6m']:p;
    const deltaDate=(Date.UTC(new Date().getUTCFullYear(),new Date().getUTCMonth(),new Date().getUTCDate())-
       Date.parse((quote?.quote_as_of||'')+'T00:00:00Z'))/86400000;
    const rate=code==='EUR'?quote?.rate_indicative:p?.rate;
    const valid=p?.quote_timestamp_verified===true&&
      p.quote_timestamp_source==='SSR_DAILY_BAR_DATA_UPDATE_TIME'&&
      p.quote_as_of===quote?.quote_as_of&&
      Number.isInteger(deltaDate)&&deltaDate>=0&&deltaDate<=5&&
      Math.abs(100-p.futures_price-rate)<=0.0002;
    if(!valid)continue;
    const leg=compareCHF.dates.find(x=>x.includes(code));
    if(!leg?.includes('6M repricing policy non certificato')||
       !leg?.includes(p.contract)||!leg?.includes('NON ΔOIS, solo contesto'))
      throw Error(label+' '+code+' dated 6M context missing or misrepresented '+JSON.stringify({leg,quote}));
  }


  const deltaCHF=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument,c=d?.getElementById('gmfq-pair-what-changed');
    return {exists:!!c,legs:[...c?.querySelectorAll('.gmfq-change-leg')||[]].map(x=>({
      ccy:x.dataset.gmfqChangeCurrency,status:x.dataset.gmfqYieldChange,
      model:x.querySelector('.gmfq-change-model')?.textContent,
      actual:x.querySelector('.gmfq-change-measured')?.textContent})),
      baseline:c?.dataset.macroBaselineAsOf,
      price:c?.dataset.pairPriceAsOf,
      baselineState:c?.dataset.macroBaselineState,
      modelSummary:c?.querySelector('.gmfq-change-summary')?.textContent,
      disclaimer:c?.querySelector('.gmfq-change-warning')?.textContent};
  });
  if(!deltaCHF.exists||deltaCHF.legs.length!==2||
     deltaCHF.baseline!==setupFeed.macro_baseline_asof||
     deltaCHF.price!==setupFeed.price_asof||
     deltaCHF.baselineState!==(current(setupFeed.macro_baseline_asof,10)?'DATED_SNAPSHOT':'HISTORICAL')||
     !deltaCHF.modelSummary?.includes('baseline Macro/Tassi '+setupFeed.macro_baseline_asof)||
     deltaCHF.legs.find(x=>x.ccy==='CHF')?.status!=='WITHHELD'||
     !deltaCHF.legs.find(x=>x.ccy==='CHF')?.actual?.includes('2026-09-30')||
     !deltaCHF.legs.find(x=>x.ccy==='EUR')?.model?.includes('Crescita: peggiora')||
     !deltaCHF.disclaimer?.includes('non necessariamente 24 ore'))
    throw Error(label+' CHF what-changed narrative is not fail-closed '+JSON.stringify(deltaCHF));

  // EUR and USD currently share an official 2Y/10Y date. An observed
  // sovereign spread may be calculated from two official SAME-DAY yields,
  // but must be named a LEVEL gap, never a Fed/ECB policy forecast.
  await page.frameLocator('#gmfq-page').locator('#pair-index button.pair-open[data-pair="EURUSD"]').click();
  await page.waitForFunction(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    return d?.getElementById('gmfq-pair-research-path')?.dataset.pair==='EURUSD';
  },null,{timeout:10000});
  const compareEURUSD=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument,c=d?.getElementById('gmfq-pair-macro-rates');
    return {labels:[...c?.querySelectorAll('.gmfq-compare-score strong')||[]].map(x=>x.textContent),
      same:c?.querySelector('.gmfq-compare-spread')?.dataset.sameDate,spread:c?.querySelector('.gmfq-compare-spread')?.textContent,
      dates:[...c?.querySelectorAll('.gmfq-compare-leg')||[]].map(x=>x.textContent),
      disclaimer:c?.querySelector('.gmfq-compare-disclaimer')?.textContent};
  });
  const y2Gap=Math.round((ratesFeed.EUR['2Y']-ratesFeed.USD['2Y'])*100);
  const sameRatesDay=ratesFeed.EUR.date===ratesFeed.USD.date;
  if(compareEURUSD.labels[0]!=='Favorisce 🇺🇸 USD'||
     compareEURUSD.labels[1]!=='Non distingue chiaramente le due valute'||
     compareEURUSD.same!==(sameRatesDay?'true':'false')||
     (sameRatesDay&&!compareEURUSD.spread.includes(y2Gap+' bp'))||
     !compareEURUSD.disclaimer.includes('non vengono ricalcolati'))
    throw Error(label+' EURUSD canonical macro and observed same-day Rates gap mismatch '+JSON.stringify(compareEURUSD));

  const deltaEURUSD=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument,c=d?.getElementById('gmfq-pair-what-changed');
    return {text:c?.textContent,baseline:c?.dataset.macroBaselineAsOf,
      price:c?.dataset.pairPriceAsOf,baselineState:c?.dataset.macroBaselineState,
      legs:[...c?.querySelectorAll('.gmfq-change-leg')||[]].map(x=>({
      ccy:x.dataset.gmfqChangeCurrency,status:x.dataset.gmfqYieldChange,
      actual:x.querySelector('.gmfq-change-measured')?.textContent,model:x.querySelector('.gmfq-change-model')?.textContent}))};
  });
  const eu=deltaEURUSD.legs.find(x=>x.ccy==='EUR'),us=deltaEURUSD.legs.find(x=>x.ccy==='USD');
  if(deltaEURUSD.baseline!==setupFeed.macro_baseline_asof||
     deltaEURUSD.price!==setupFeed.price_asof||
     deltaEURUSD.baselineState!==(current(setupFeed.macro_baseline_asof,10)?'DATED_SNAPSHOT':'HISTORICAL')||
     !deltaEURUSD.text?.includes('baseline Macro/Tassi '+setupFeed.macro_baseline_asof)||
     !deltaEURUSD.text?.includes('Il feed Prezzo/Pair del '+setupFeed.price_asof)||
     deltaEURUSD.text?.includes('LETTURA MODELLO · '+setupFeed.price_asof)||
     eu?.status!=='MEASURED'||us?.status!=='MEASURED'||
     !eu.actual?.includes(ratesFeed.EUR.history2.dates.at(-2)+' → '+ratesFeed.EUR.history2.dates.at(-1))||
     !us.actual?.includes(ratesFeed.USD.history2.dates.at(-2)+' → '+ratesFeed.USD.history2.dates.at(-1))||
     !eu.actual?.includes(((x)=>((x>0?'+':'')+x.toFixed(1)+' bp'))(Math.round((ratesFeed.EUR.history2.values.at(-1)-ratesFeed.EUR.history2.values.at(-2))*1000)/10))||
     !us.actual?.includes(((x)=>((x>0?'+':'')+x.toFixed(1)+' bp'))(Math.round((ratesFeed.USD.history2.values.at(-1)-ratesFeed.USD.history2.values.at(-2))*1000)/10))||
     eu.model!==setupFeed.pairs.EURUSD.relative_dynamics.A.details.filter(x=>/^(Crescita|Lavoro|Rates|Inflazione): /.test(x)).slice(0,4).join(' · ')||
     us.model!==setupFeed.pairs.EURUSD.relative_dynamics.B.details.filter(x=>/^(Crescita|Lavoro|Rates|Inflazione): /.test(x)).slice(0,4).join(' · ')||
     !deltaEURUSD.text?.includes('diagnosi qualitativa'))
    throw Error(label+' EURUSD history-derived 2Y changes vs model not separated '+JSON.stringify(deltaEURUSD));

  // Same-day 2Y country spread (EUR - USD) widened +6.7 bp while
  // ECB EUR/USD fixing rose between EXACTLY 15 and 16 Oct: indicative
  // directional consistency, not event-study causal proof.
  const eurReaction=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    const c=d?.getElementById('gmfq-pair-market-reaction');
    return {state:c?.dataset.reactionStatus,dates:[c?.dataset.windowStart,c?.dataset.windowEnd],
      values:[...c?.querySelectorAll('.gmfq-reaction-metrics strong')||[]].map(n=>n.textContent),
      note:c?.querySelector('.gmfq-reaction-warning')?.textContent,parts:c?.textContent,
      width:d?.documentElement.scrollWidth,viewport:d?.documentElement.clientWidth};
  });
  const expectedEurState=expectedReactionFromMetrics(eurReaction);
  const eurDates=eurReaction.dates||[];
  const eurGap=(Date.parse(eurDates[1]+'T00:00:00Z')-Date.parse(eurDates[0]+'T00:00:00Z'))/86400000;
  if(eurReaction.state!==expectedEurState||!Number.isFinite(eurGap)||eurGap<=0||eurGap>5||
     !eurReaction.note?.includes('non prezzi intraday')||
     !eurReaction.parts?.includes('non spiegazione causale')||
     eurReaction.width>eurReaction.viewport+16)
    throw Error(label+' EURUSD dated 2Y/FX reaction must respect thresholds '+JSON.stringify({eurReaction,expectedEurState}));
  
  const eurDecision=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page').contentDocument,c=d?.getElementById('gmfq-pair-decision-bridge');
    return {state:c?.dataset.bridgeStatus,baseline:c?.dataset.baselineStatus,blocks:[...c?.querySelectorAll('.gmfq-decision-cols>div')||[]].map(x=>x.textContent),
      content:c?.textContent,doc:d?.documentElement.scrollWidth,view:d?.documentElement.clientWidth};
  });
  if(eurDecision.state!=='NON_DETERMINATO'||eurDecision.baseline!=='STALE_OR_UNVERIFIED'||
     eurDecision.blocks.length!==3||
     !eurDecision.blocks[0]?.includes('USD')||!eurDecision.blocks[1]?.includes('CON RISCHI')||
     !eurDecision.blocks[2]?.includes(expectedEurState==='COERENTE'?'Coerente tra 2Y e FX':expectedEurState==='DIVERGENTE'?'Divergente tra 2Y e FX':expectedEurState==='NON_CONCLUSIVO'?'Non conclusivo':'Non valutabile')||
     !eurDecision.content?.includes('Una coerenza 2Y–FX non equivale a conferma della tesi')||
     !eurDecision.blocks[0]?.includes('Preferenza storica')||
     !eurDecision.content?.includes('I movimenti recenti FX e 2Y restano osservazioni valide ma non confermano né invalidano la tesi storica')||
     !eurDecision.content?.includes('Prima rivalidare la baseline Macro/Tassi')||
     !eurDecision.content?.includes('Non sono disponibili trigger numerici certificati')||
     eurDecision.doc>eurDecision.view+16)
    throw Error(label+' EURUSD coherence must not be promoted as canonical USD thesis confirmation '+JSON.stringify(eurDecision));

  const eurChecklist=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page').contentDocument,c=d?.getElementById('gmfq-pair-evidence-checklist');
    return {exists:!!c,rows:[...c?.querySelectorAll('.gmfq-evidence-row')||[]].map(x=>x.textContent),
      text:c?.textContent,width:d?.documentElement.scrollWidth,viewport:d?.documentElement.clientWidth};
  });
  if(!eurChecklist.exists||eurChecklist.rows.length!==3||
     !eurChecklist.rows[0].includes('USD')||!eurChecklist.rows[1].includes('EUR')||
     !eurChecklist.rows[2].includes('Estensione del prezzo:')||
     !eurChecklist.rows[2].includes('Timing:')||
     !eurChecklist.rows[2].includes('Posizionamento:')||
     !eurChecklist.text.includes('Solo uno dei due pilastri strutturali separa chiaramente le valute')||
     !eurChecklist.text.includes('Nessun trigger numerico o livello tecnico viene derivato automaticamente')||
     eurChecklist.width>eurChecklist.viewport+16)
    throw Error(label+' EURUSD next evidence checklist must expose canonical setup blockers not market-derived entry '+JSON.stringify(eurChecklist));

  // AUD / CAD are individually certified but published on different dates.
  // Never combine their most recent independent spot yields into a 2Y spread.
  await page.frameLocator('#gmfq-page').locator('#pair-index button.pair-open[data-pair="AUDCAD"]').click();
  await page.waitForFunction(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    return d?.getElementById('gmfq-pair-research-path')?.dataset.pair==='AUDCAD';
  },null,{timeout:10000});
  const compareAUDCAD=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument,c=d?.getElementById('gmfq-pair-macro-rates');
    return {same:c?.querySelector('.gmfq-compare-spread')?.dataset.sameDate,
      spread:c?.querySelector('.gmfq-compare-spread')?.textContent,
      legs:[...c?.querySelectorAll('.gmfq-compare-leg')||[]].map(x=>x.textContent)};
  });
  if(ratesFeed.AUD.date!==ratesFeed.CAD.date&&
     (compareAUDCAD.same!=='false'||!compareAUDCAD.spread?.includes('WITHHELD')))
    throw Error(label+' AUDCAD mixed-date 2Y spread promoted '+JSON.stringify(compareAUDCAD));
  if(!compareAUDCAD.legs.some(x=>x.includes('futures IB'))||
     !compareAUDCAD.legs.some(x=>x.includes('futures CORRA')))
    throw Error(label+' Official AUD/CAD 6M instrument classes not explicit '+JSON.stringify(compareAUDCAD));
  const deltaAUDCAD=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument,c=d?.getElementById('gmfq-pair-what-changed');
    return [...c?.querySelectorAll('.gmfq-change-leg')||[]].map(x=>({
      ccy:x.dataset.gmfqChangeCurrency,status:x.dataset.gmfqYieldChange,
      actual:x.querySelector('.gmfq-change-measured')?.textContent}));
  });
  if(deltaAUDCAD.find(x=>x.ccy==='AUD')?.status!=='WITHHELD'||
     !deltaAUDCAD.find(x=>x.ccy==='AUD')?.actual?.includes(ratesFeed.AUD.date)||
     deltaAUDCAD.find(x=>x.ccy==='CAD')?.status!=='MEASURED')
    throw Error(label+' AUDCAD observed 2Y series gaps misclassified '+JSON.stringify(deltaAUDCAD));
  const audReaction=await page.evaluate(()=>{
    const c=document.getElementById('gmfq-page')?.contentDocument?.getElementById('gmfq-pair-market-reaction');
    return {status:c?.dataset.reactionStatus,content:c?.textContent};
  });
  if(audReaction.status!=='WITHHELD'||
     !audReaction.content?.includes('NON VALUTABILE'))
     throw Error(label+' AUDCAD reaction used unevenly dated historical 2Y '+JSON.stringify(audReaction));

  await page.frameLocator('#gmfq-page').locator('#pair-index button.pair-open[data-pair="GBPJPY"]').click();
  await page.waitForFunction(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    return d?.getElementById('gmfq-pair-research-path')?.dataset.pair==='GBPJPY';
  },null,{timeout:10000});
  const gbpReaction=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    const c=d?.getElementById('gmfq-pair-market-reaction');
    return {state:c?.dataset.reactionStatus,dates:[c?.dataset.windowStart,c?.dataset.windowEnd],
      values:[...c?.querySelectorAll('.gmfq-reaction-metrics strong')||[]].map(n=>n.textContent)};
  });
  const expectedGbpState=expectedReactionFromMetrics(gbpReaction);
  const gbpGap=(Date.parse(gbpReaction.dates[1]+'T00:00:00Z')-Date.parse(gbpReaction.dates[0]+'T00:00:00Z'))/86400000;
  if(gbpReaction.state!==expectedGbpState||
     (expectedGbpState!=='WITHHELD'&&(!Number.isFinite(gbpGap)||gbpGap<=0||gbpGap>5)))
    throw Error(label+' GBPJPY 2Y/FX verdict must follow actual observed thresholds '+JSON.stringify({gbpReaction,expectedGbpState}));
 
  const gbpDecision=await page.evaluate(()=>{
    const c=document.getElementById('gmfq-page').contentDocument?.getElementById('gmfq-pair-decision-bridge');
    return {status:c?.dataset.bridgeStatus,text:c?.textContent};
  });
  if(gbpDecision.status!=='NON_DETERMINATO'||
     !gbpDecision.text?.includes('Nessuna preferenza netta')||
     !gbpDecision.text?.includes('Il motore non identifica una valuta strutturalmente favorita'))
    throw Error(label+' GBPJPY Rates/FX divergence cannot create a trade thesis '+JSON.stringify(gbpDecision));

  const gbpChecklist=await page.evaluate(()=>{
    const c=document.getElementById('gmfq-page').contentDocument?.getElementById('gmfq-pair-evidence-checklist');
    return {rows:[...c?.querySelectorAll('.gmfq-evidence-row')||[]].map(x=>x.textContent)};
  });
  if(gbpChecklist.rows.length!==3||
     !gbpChecklist.rows[0].includes('Prima serve una preferenza Macro/Tassi/CB')||
     !gbpChecklist.rows[2].includes('Il motore non individua una valuta favorita'))
    throw Error(label+' GBPJPY cannot infer a thesis from rates level alone '+JSON.stringify(gbpChecklist));

  await page.frameLocator('#gmfq-page').locator('#pair-index button.pair-open[data-pair="USDJPY"]').click();
  await page.waitForFunction(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    return d?.getElementById('gmfq-pair-research-path')?.dataset.pair==='USDJPY';
  },null,{timeout:10000});
  const jpyReaction=await page.evaluate(()=>{
    const c=document.getElementById('gmfq-page')?.contentDocument?.getElementById('gmfq-pair-market-reaction');
    return {status:c?.dataset.reactionStatus,content:c?.textContent};
  });
  if(!['COERENTE','DIVERGENTE','NON_CONCLUSIVO','WITHHELD'].includes(jpyReaction.status)||
     (jpyReaction.status==='NON_CONCLUSIVO'&&!jpyReaction.content?.includes('±0,05%')))
    throw Error(label+' USDJPY must remain threshold-labelled and data-derived '+JSON.stringify(jpyReaction));
  const usdDecision=await page.evaluate(()=>{
    const c=document.getElementById('gmfq-page').contentDocument?.getElementById('gmfq-pair-decision-bridge');
    return {status:c?.dataset.bridgeStatus,text:c?.textContent};
  });
  const usdExpected=jpyReaction.status==='NON_CONCLUSIVO'||jpyReaction.status==='WITHHELD'?
    'NON_DETERMINATO':null;
  if((usdExpected&&usdDecision.status!==usdExpected)||
     (usdExpected&&!usdDecision.text?.includes('Nessuna conferma o invalidazione dal fixing'))||
     !usdDecision.text?.includes('Non sono disponibili trigger numerici certificati'))
    throw Error(label+' USDJPY must not invent a trade trigger from short 2Y/FX reaction '+JSON.stringify({usdDecision,jpyReaction}));

  console.log('CONTROL_ROOM_PREVIEW_PAIR_FX_REACTION_GREEN',label,
    JSON.stringify({eurusd:eurReaction.state,gbpjpy:gbpReaction.state,
      usdjpy:jpyReaction.status,audcad:audReaction.status,viewport:eurReaction.viewport}));

  console.log('CONTROL_ROOM_PREVIEW_PAIR_WHAT_CHANGED_GREEN',label,
    JSON.stringify({CHF:'WITHHELD',EUR:'MEASURED +3.7',USD:'MEASURED -3.0',
      AUD:'WITHHELD',CAD:'MEASURED',viewport:detail.viewport}));

  await page.frameLocator('#gmfq-page').locator('#pair-index button.pair-open[data-pair="EURCHF"]').click();
  await page.waitForFunction(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    return d?.getElementById('gmfq-pair-research-path')?.dataset.pair==='EURCHF';
  },null,{timeout:10000});
  const chfReaction=await page.evaluate(()=>{
    const c=document.getElementById('gmfq-page')?.contentDocument?.getElementById('gmfq-pair-market-reaction');
    return {status:c?.dataset.reactionStatus,content:c?.textContent};
  });
  if(chfReaction.status!=='WITHHELD'||!chfReaction.content?.includes('2Y di una o entrambe le valute'))
    throw Error(label+' stale CHF rate promoted to FX reaction signal '+JSON.stringify(chfReaction));

  const chfDecision=await page.evaluate(()=>{
    const c=document.getElementById('gmfq-page').contentDocument?.getElementById('gmfq-pair-decision-bridge');
    return {status:c?.dataset.bridgeStatus,text:c?.textContent};
  });
  if(chfDecision.status!=='NON_DETERMINATO'||
     !chfDecision.text?.includes('CON RISCHI')||
     !chfDecision.text?.includes('audit assente, incompleto o non conclusivo'))
    throw Error(label+' EURCHF stale FX reaction cannot update structural EUR preference '+JSON.stringify(chfDecision));
  const chfChecklist=await page.evaluate(()=>{
    const c=document.getElementById('gmfq-page').contentDocument?.getElementById('gmfq-pair-evidence-checklist');
    return {rows:[...c?.querySelectorAll('.gmfq-evidence-row')||[]].map(x=>x.textContent),
      text:c?.textContent};
  });
  if(chfChecklist.rows.length!==3||
     !chfChecklist.rows[2].includes('Prezzo nel modello: Prezzo diverge')||
     !chfChecklist.text.includes('La finestra recente non dà una verifica direzionale confrontabile'))
    throw Error(label+' EURCHF stale CHF cannot assert confirmed FX trigger '+JSON.stringify(chfChecklist));
  console.log('CONTROL_ROOM_PREVIEW_PAIR_EVIDENCE_CHECKLIST_GREEN',label,
    JSON.stringify({eurusd:eurChecklist.rows.length,gbpjpy:gbpChecklist.rows.length,
      eurchf:chfChecklist.rows.length,viewport:eurChecklist.viewport}));

  console.log('CONTROL_ROOM_PREVIEW_PAIR_DECISION_BRIDGE_GREEN',label,
    JSON.stringify({eurusd:eurDecision.state,gbpjpy:gbpDecision.status,
      usdjpy:usdDecision.status,eurchf:chfDecision.status,viewport:eurDecision.view}));

  console.log('CONTROL_ROOM_PREVIEW_PAIR_MACRO_RATES_GREEN',label,
    JSON.stringify({chf:compareCHF.same,eurusd:compareEURUSD.same,audcad:compareAUDCAD.same,
      observedEurUsdBp:sameRatesDay?y2Gap:null,viewport:detail.viewport}));

  // Technical evidence remains accessible by click and keyboard after switching
  // pairs; no original 28-pair row is removed by the disclosure.
  const fullResearch=page.frameLocator('#gmfq-page').locator('#gmfq-pair-full-research');
  if(!(await fullResearch.evaluate(el=>el.open))){
    await page.frameLocator('#gmfq-page').locator('#gmfq-pair-full-research > summary').click();
  }
  if(!(await page.frameLocator('#gmfq-page').locator('#gmfq-pair-macro-rates').isVisible()))
    throw Error(label+' Pair full research failed to expand');
  await page.frameLocator('#gmfq-page').locator('#gmfq-pair-research-path button[data-gmfq-study-route="tassi"][data-gmfq-study-currency="CHF"]').click();
  await page.waitForURL(u=>u.hash==='#/tassi?ccy=CHF',{timeout:15000});
  await page.waitForFunction(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    return d?.getElementById('rates-select')?.querySelector('button[data-ccy="CHF"]')?.getAttribute('aria-pressed')==='true';
  },null,{timeout:20000});
  console.log('CONTROL_ROOM_PREVIEW_28_PAIR_RESEARCH_GREEN',label,JSON.stringify({fromHome,selected:'EURCHF',links:first.links,viewport:first.viewport}));

  console.log('CONTROL_ROOM_PREVIEW_G8_DETAIL_FOCUS_GREEN',label,JSON.stringify({ratesDetail,researchSummary:{fourCurves:research.fourCurves,secondary:research.secondary,docWidth:research.docWidth,viewport:research.viewport}}));

  // Gold belongs to the ACTIVE v10 Cross-Asset page, not legacy root Risk UI.
  await page.goto(url+'#/cross',{waitUntil:'domcontentloaded',timeout:120000});
  await page.waitForFunction(()=>{
    const doc=document.getElementById('gmfq-page')?.contentDocument;
    return ['SECONDARY_CURRENT','SECONDARY_HISTORICAL','WITHHELD'].includes(
      doc?.getElementById('gmfq-cross-gold-v10')?.dataset.sourceStatus);
  },null,{timeout:25000});
  const gold=await page.evaluate(()=>{
    const doc=document.getElementById('gmfq-page')?.contentDocument;
    const panel=doc?.getElementById('gmfq-cross-gold-v10');
    return {state:panel?.dataset.sourceStatus,asof:panel?.dataset.goldAsOf,
      value:panel?.querySelector('.gmfq-gold-quote')?.textContent,
      spotBackground:panel?.querySelector('.gmfq-gold-spot')?doc.defaultView.getComputedStyle(panel.querySelector('.gmfq-gold-spot')).backgroundColor:null,
      spotBorderSide:panel?.querySelector('.gmfq-gold-spot')?(doc.documentElement.clientWidth<=700?doc.defaultView.getComputedStyle(panel.querySelector('.gmfq-gold-spot')).borderTopWidth:doc.defaultView.getComputedStyle(panel.querySelector('.gmfq-gold-spot')).borderLeftWidth):null,
      text:panel?.textContent,viewport:doc?.documentElement.clientWidth,
      width:doc?.documentElement.scrollWidth,legacy:!!doc?.querySelector('[data-gmfq-operational="risk"]')};
  });
  const goldFixture=JSON.parse(fs.readFileSync(path.join(DATA,'ESTIMATED_RESIDUAL_GAPS.json'),'utf8'))
    .lanes['GOLD.market_proxy'];
  const goldQuote=Number(goldFixture.value).toLocaleString('it-IT',
    {minimumFractionDigits:2,maximumFractionDigits:2});
  if(!['SECONDARY_CURRENT','SECONDARY_HISTORICAL'].includes(gold.state)||
     gold.asof!==goldFixture.proxy_as_of||!gold.value?.includes(goldQuote)||
     !['transparent','rgba(0, 0, 0, 0)'].includes(gold.spotBackground)||
     gold.spotBorderSide!=='1px'||
     !gold.text?.includes('Gold Price LBMA · WITHHELD')||
     !gold.text?.includes('futures COMEX indicativo')||
     !gold.text?.includes('non sono usate in questo confronto')||
     !gold.text?.includes('non equivale a oro spot')||
     gold.legacy||gold.width>gold.viewport+16){
    throw Error(label+' v10 Gold Cross-Asset source or sizing failed '+JSON.stringify(gold));
  }
  console.log('CONTROL_ROOM_V10_CROSS_GOLD_SOURCE_PASS',label,
    JSON.stringify({state:gold.state,asof:gold.asof,value:gold.value,viewport:gold.viewport}));


  // Cross-Asset risk/energy is an additive v10 route, never the old dashboard.
  await page.waitForFunction(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    return ['AVAILABLE','PARTIAL','WITHHELD'].includes(d?.getElementById('gmfq-cross-risk-v10')?.dataset.sourceStatus);
  },null,{timeout:25000});
  const risk=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    const p=d?.getElementById('gmfq-cross-risk-v10');
    return {status:p?.dataset.sourceStatus,
      lead:p?.querySelector('.gmfq-cross-risk-intro')?.textContent,
      provenance:[...p?.querySelectorAll('.gmfq-cross-risk-evidence span[data-source]')||[]].map(x=>x.dataset.source),
      leadFirst:!!(p?.querySelector('.gmfq-cross-risk-intro')?.compareDocumentPosition(p.querySelector('.gmfq-cross-risk-evidence'))&Node.DOCUMENT_POSITION_FOLLOWING),
      gridCols:p?.querySelector('.gmfq-cross-risk-grid')?d.defaultView.getComputedStyle(p.querySelector('.gmfq-cross-risk-grid')).gridTemplateColumns.trim().split(/\s+/).length:null,
      firstBg:p?.querySelector('.gmfq-cross-risk-card')?d.defaultView.getComputedStyle(p.querySelector('.gmfq-cross-risk-card')).backgroundColor:null,
      cards:[...p?.querySelectorAll('[data-cross-instrument]')||[]].map(c=>({
        symbol:c.dataset.crossInstrument,state:c.dataset.crossStatus,
        text:c.textContent,price:c.querySelector('.gmfq-cross-risk-value')?.textContent})),
      text:p?.textContent,width:d?.documentElement.scrollWidth,
      viewport:d?.documentElement.clientWidth};
  });
  const riskData=JSON.parse(fs.readFileSync(path.join(DATA,'D.json'),'utf8'));
  const secondary=JSON.parse(fs.readFileSync(path.join(DATA,'ESTIMATED_RESIDUAL_GAPS.json'),'utf8'));
  const expected=[
    {code:'VIX',series:riskData.risk.VIX},
    {code:'WTI',series:riskData.risk.WTI},
    {code:'BRENT',series:secondary.lanes['BRENT.market_proxy'],secondary:true},
  ];
  if(risk.cards.length!==3||!risk.lead?.startsWith('VIX misura volatilità implicita')||
    !risk.leadFirst||JSON.stringify(risk.provenance)!==JSON.stringify(['vix','wti','brent'])||
    risk.gridCols!==(risk.viewport<=820?1:3)||
    !['transparent','rgba(0, 0, 0, 0)'].includes(risk.firstBg)||
    !risk.text.includes('Brent spot ufficiale: WITHHELD')||
    !risk.text.includes('Nessun confronto di spread fra spot e futures')||
    risk.width>risk.viewport+16)
    throw Error(label+' v10 cross risk layout/source disclosure missing '+JSON.stringify(risk));
  for(const item of expected){
    const card=risk.cards.find(x=>x.symbol===item.code),day=item.secondary?
      item.series.proxy_as_of:item.series.last_date;
    const age=Math.round((Date.UTC(new Date().getUTCFullYear(),new Date().getUTCMonth(),new Date().getUTCDate())-
      Date.parse(day+'T00:00:00Z'))/86400000);
    const expectedState=item.secondary?(age<=3?'SECONDARY_RECENT':'SECONDARY_HISTORICAL'):
      (age<=3?'OFFICIAL_RECENT':'OFFICIAL_HISTORICAL');
    const price=Number(item.series.value??item.series.last_value).toLocaleString('it-IT',
      {minimumFractionDigits:2,maximumFractionDigits:2});
    if(card?.state!==expectedState||!card.text?.includes(day)||!card.price?.includes(price)){
      throw Error(label+' Cross-Asset '+item.code+' mismatched dated source '+JSON.stringify({card,expectedState,price}));
    }
  }
  console.log('CONTROL_ROOM_V10_CROSS_RISK_SOURCE_PASS',label,
    JSON.stringify(risk.cards.map(c=>({symbol:c.symbol,state:c.state,price:c.price}))));
  
  // Corrupted EIA WTI or mismatched BZ futures metadata must fail closed
  // independently of a still-valid Cboe VIX and Gold futures quote.
  await page.route('**/D.json',async route=>{
    const damaged=JSON.parse(fs.readFileSync(path.join(DATA,'D.json'),'utf8'));
    damaged.risk.WTI.last_value=null;
    await route.fulfill({status:200,contentType:'application/json',
      headers:{'Access-Control-Allow-Origin':'*'},body:JSON.stringify(damaged)});
  });
  await page.route('**/ESTIMATED_RESIDUAL_GAPS.json',async route=>{
    const damaged=JSON.parse(fs.readFileSync(path.join(DATA,'ESTIMATED_RESIDUAL_GAPS.json'),'utf8'));
    damaged.lanes['BRENT.market_proxy'].vendor_symbol='WRONG';
    await route.fulfill({status:200,contentType:'application/json',
      headers:{'Access-Control-Allow-Origin':'*'},body:JSON.stringify(damaged)});
  });
  await page.goto(url+'#/home',{waitUntil:'domcontentloaded',timeout:120000});
  await page.goto(url+'#/cross?riskqa=damaged',{waitUntil:'domcontentloaded',timeout:120000});
  await page.waitForFunction(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    return d?.querySelector('#gmfq-cross-risk-v10 [data-cross-instrument="WTI"]')?.dataset.crossStatus==='WITHHELD'&&
      d?.querySelector('#gmfq-cross-risk-v10 [data-cross-instrument="BRENT"]')?.dataset.crossStatus==='WITHHELD';
  },null,{timeout:25000});
  const negativeRisk=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    return [...d?.querySelectorAll('#gmfq-cross-risk-v10 [data-cross-instrument]')||[]]
      .map(el=>({symbol:el.dataset.crossInstrument,status:el.dataset.crossStatus,
        value:el.querySelector('.gmfq-cross-risk-value')?.textContent}));
  });
  if(negativeRisk.find(x=>x.symbol==='WTI')?.value?.trim()!=='—'||
     negativeRisk.find(x=>x.symbol==='BRENT')?.value?.trim()!=='—'||
     !negativeRisk.find(x=>x.symbol==='VIX')?.status?.startsWith('OFFICIAL_')){
    throw Error(label+' Cross-Asset invalid WTI/Brent failed-closed mismatch '+JSON.stringify(negativeRisk));
  }
  await page.unroute('**/D.json');
  await page.unroute('**/ESTIMATED_RESIDUAL_GAPS.json');
  console.log('CONTROL_ROOM_V10_CROSS_RISK_WITHHELD_PASS',label);

  // Negative fixture: a missing Gold futures quote MUST be WITHHELD rather than 0.00.
  await page.route('**/ESTIMATED_RESIDUAL_GAPS.json',async r=>{
    const obj=JSON.parse(fs.readFileSync(path.join(DATA,'ESTIMATED_RESIDUAL_GAPS.json'),'utf8'));
    obj.lanes['GOLD.market_proxy'].value=null;
    await r.fulfill({status:200,contentType:'application/json',
      headers:{'Access-Control-Allow-Origin':'*'},body:JSON.stringify(obj)});
  });
  await page.goto(url+'#/home',{waitUntil:'domcontentloaded',timeout:120000});
  await page.goto(url+'#/cross?test=invalid',{waitUntil:'domcontentloaded',timeout:120000});
  await page.waitForFunction(()=>{
    const doc=document.getElementById('gmfq-page')?.contentDocument;
    return doc?.getElementById('gmfq-cross-gold-v10')?.dataset.sourceStatus==='WITHHELD';
  },null,{timeout:25000});
  const bad=await page.evaluate(()=>{
    const doc=document.getElementById('gmfq-page')?.contentDocument;
    const el=doc?.getElementById('gmfq-cross-gold-v10');
    return {state:el?.dataset.sourceStatus,value:el?.querySelector('.gmfq-gold-quote')?.textContent,
      spot:el?.textContent?.includes('Gold Price LBMA · WITHHELD'),width:doc?.documentElement.scrollWidth,
      viewport:doc?.documentElement.clientWidth};
  });
  if(bad.state!=='WITHHELD'||bad.value?.trim()!=='—'||!bad.spot||
     bad.width>bad.viewport+16){
    throw Error(label+' Gold invalid source not fail-closed '+JSON.stringify(bad));
  }
  console.log('CONTROL_ROOM_V10_CROSS_GOLD_WITHHELD_PASS',label,bad.state);

  await page.close();
 }
 await browser.close();
 console.log('CONTROL_ROOM_V10_VISUAL_NAV_DXY_G8_PASS');
})().catch(e=>{console.error(e);process.exit(1)});
