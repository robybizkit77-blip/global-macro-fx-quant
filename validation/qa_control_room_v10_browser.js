/* Browser contract for v10. All feeds are locally intercepted fixture copies from repo. */
'use strict';
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path');
const {romeTodayIso,scenarioSixMonth}=require('../site/control-room-preview/ois-pricing-estimates-v1.js');
const DATA=path.join(process.cwd(),'live_data/sections');
const dxyFeed=JSON.parse(fs.readFileSync(path.join(DATA,'DXY_SYNTHETIC_ECB.json'),'utf8'));
const nzdProxy=JSON.parse(fs.readFileSync(path.join(DATA,'NZD_CB_PRICING_DIRECTIONAL_PROXY.json'),'utf8'));
if(dxyFeed.schema!=='GMFQ_DXY_SYNTHETIC_ECB_V1'||dxyFeed.not_official_ice!==true||
   dxyFeed.status!=='ESTIMATED_INFORMATIONAL')throw Error('DXY research provenance contract failed');
if(nzdProxy.schema!=='GMFQ_NZD_CB_PRICING_DIRECTIONAL_PROXY_V1'||
   nzdProxy.status!=='LIVE_DIRECTIONAL_PROXY_READY')throw Error('NZD directional proxy contract failed');
const dxyDisplayed=Number(dxyFeed.value).toFixed(2);
const nzdScenario=scenarioSixMonth(
 JSON.parse(fs.readFileSync(path.join(DATA,'OIS_OPERATIONAL_VIEW.json'),'utf8')),
 nzdProxy,romeTodayIso()).NZD;
const nzdDisplayed=Number(nzdScenario?.value??nzdProxy.horizons['6m'].implied_bank_bill_rate).toFixed(2);
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
 const directional=Math.sign(bp)===Math.sign(fx)?'COERENTE':'DIVERGENTE';
 // Display rounds 2Y to 0.1bp and FX to 0.01%. Near either
 // cut-off raw values cannot be reconstructed from rounded labels.
 if(Math.abs(Math.abs(bp)-2)<=0.05000001||
    Math.abs(Math.abs(fx)-0.05)<=0.00500001)
   return row?.state==='NON_CONCLUSIVO'||row?.state===directional?
     row.state:'INVALID_ROUNDED_THRESHOLD_VERDICT';
 if(Math.abs(bp)<2||Math.abs(fx)<0.05)return 'NON_CONCLUSIVO';
 return directional;
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
  // Immutable, source-dated 2Y secondary observations (not canonical Rates).
  await page.route('https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/main/validation/rates/fixtures/chf_nzd_2y_secondary_market_2026-10-30.json',async route=>{
    const quote=fs.readFileSync('validation/rates/fixtures/chf_nzd_2y_secondary_market_2026-10-30.json');
    await route.fulfill({status:200,contentType:'application/json',body:quote,headers:{'Access-Control-Allow-Origin':'*'}});
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
  // Match the existing, approved v10 officialPricingCurrent() contract:
  // 4 calendar days, ACTIVE source and backtest-eligible official curve.
  // Rates 2Y/10Y have a distinct 5-day contract; applying that to OIS
  // would falsely count stale GBP on 2026-10-26 as still current.
  const officialCurrent=Object.entries(expectedOis.currencies).filter(([,x])=>
    x.operational_status==='GREEN_OFFICIAL'&&x.official_status==='ACTIVE'&&
    x.quality==='OFFICIAL_CERTIFIED'&&x.backtest_eligible_as_official===true&&
    current(x.as_of,4)&&
    ['3m','6m','12m'].every(k=>Number.isFinite(x.horizons?.[k]?.rate)&&
      Number.isFinite(x.horizons?.[k]?.policy_delta_bp))).map(([ccy])=>ccy).sort();
  const certified=officialCurrent.length;
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
  const morning=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page').contentDocument,
      p=d.getElementById('gmfq-morning-study-readiness'),
      rail=d.getElementById('gmfq-home-reading-path');
    return {present:!!p,state:p?.dataset.state,verified:Number(p?.dataset.verified),
      prior:p?.dataset.priorSession,sourceEffect:p?.dataset.sourceEffect,
      tags:['fx','pairs','vix','news','calendar'].map(x=>p?.dataset[x]),
      rates:p?.dataset.lagRates,ois:p?.dataset.withheldOis,
      text:p?.textContent,insideOriginalRail:!!rail?.contains(p),
      clipped:d.documentElement.scrollWidth>d.documentElement.clientWidth+16};
  });
  const previousWeekday=(()=>{
    const x=new Date(romeTodayIso()+'T00:00:00Z');
    do{x.setUTCDate(x.getUTCDate()-1)}while([0,6].includes(x.getUTCDay()));
    return x.toISOString().slice(0,10);
  })();
  const newsSnapshot=JSON.parse(fs.readFileSync(path.join(DATA,'NEWS_PULSE_OPERATIONAL.json'),'utf8'));
  const calendarSnapshot=JSON.parse(fs.readFileSync(path.join(DATA,'CALENDAR_OPERATIONAL_VIEW.json'),'utf8'));
  const toRomeDate=stamp=>new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Rome',
      year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(stamp));
  const g8History=JSON.parse(fs.readFileSync(path.join(DATA,'ECB_G8_PRICE_HISTORY.json'),'utf8'));
  const baselineVix=JSON.parse(fs.readFileSync(path.join(DATA,'D.json'),'utf8')).risk.VIX;
  const expectedDaily=[
    g8History.last_as_of>=previousWeekday&&g8History.last_as_of<=romeTodayIso(),
    setupFeed.price_asof===g8History.last_as_of&&setupFeed.price_audit?.status==='PASS'&&
      setupFeed.price_asof>=previousWeekday&&setupFeed.price_asof<=romeTodayIso(),
    baselineVix.last_date>=previousWeekday&&baselineVix.last_date<=romeTodayIso()&&
      baselineVix.dates.at(-1)===baselineVix.last_date,
    toRomeDate(newsSnapshot.generated_at_utc)===romeTodayIso(),
    toRomeDate(calendarSnapshot.generated_at_utc)===romeTodayIso(),
  ];
  if(!morning.present||!morning.insideOriginalRail||morning.clipped||
     morning.sourceEffect!=='NONE'||morning.prior!==previousWeekday||
     morning.verified!==expectedDaily.filter(Boolean).length||
     morning.tags.some((v,i)=>v!==String(expectedDaily[i]))||
     morning.state!==(expectedDaily.every(Boolean)?'DAILY_VERIFIED_WITH_GAPS':'DAILY_INCOMPLETE')||
     !morning.text.includes('Macro '+setupFeed.macro_baseline_asof+' (baseline storica)')||
     !morning.text.includes('OIS ufficiali')||
     !homeAudit.source?.includes('Studio delle 08:00 · ultime fonti giornaliere'))
    throw Error(label+' morning 08:00 study source status mismatches canonical feeds '+JSON.stringify({morning,expectedDaily}));
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
      priorityTarget:rail?.dataset.priorityTarget,
      priorityState:rail?.dataset.priorityState,
      priorityText:rail?.querySelector('.gmfq-reading-priority')?.textContent,
      priorityFirst:!!(rail?.querySelector('.gmfq-reading-priority')?.compareDocumentPosition(rail.querySelector('.gmfq-reading-steps'))&Node.DOCUMENT_POSITION_FOLLOWING),
      emphasized:btn.filter(b=>b.dataset.readingPriority==='true').map(b=>b.dataset.readingTarget),
      positioned:!!rail&&!!hero&&!!grid&&grid.contains(hero)&&
       !!(rail.compareDocumentPosition(grid)&Node.DOCUMENT_POSITION_FOLLOWING),
      positions:{hero:hero?.getBoundingClientRect().top,rail:rail?.getBoundingClientRect().top,grid:grid?.getBoundingClientRect().top,heroFollowsGrid:!!(grid?.compareDocumentPosition(hero)&Node.DOCUMENT_POSITION_FOLLOWING),heroFollowsRail:!!(rail?.compareDocumentPosition(hero)&Node.DOCUMENT_POSITION_FOLLOWING),parentHero:hero?.parentElement?.className,parentGrid:grid?.parentElement?.className},
      globe:!!d.querySelector('.hero .globe'),
      visualEdition:rail?.dataset.visualEdition,
      layout:{
        gridColumns:getComputedStyle(grid).gridTemplateColumns.trim().split(/\s+/).length,
        heroFullWidth:Math.abs(hero.getBoundingClientRect().width-grid.getBoundingClientRect().width)<=2,
        globePreserved:getComputedStyle(hero.querySelector('.globe')).backgroundImage.includes('data:image/png;base64'),
        globeRatio:getComputedStyle(hero.querySelector('.globe')).backgroundSize==='auto 100%',
        priorityColumns:getComputedStyle(rail).gridTemplateColumns.trim().split(/\s+/).length,
        firstPanel:!!grid.querySelector('.panel:nth-child(2) .oisrow'),
        secondPanel:!!grid.querySelector('.yieldpanel #curves svg'),
        styleMounted:!!d.getElementById('gmfq-home-visual-edition-css')
      },
      lower:{
        market:!!d.getElementById('gmfq-home-market-chapter'),
        pair:!!d.getElementById('gmfq-home-pair-chapter'),
        marketBefore:!!(d.getElementById('gmfq-home-market-chapter')?.compareDocumentPosition(d.querySelector('.mid'))&Node.DOCUMENT_POSITION_FOLLOWING),
        pairBefore:!!(d.getElementById('gmfq-home-pair-chapter')?.compareDocumentPosition(d.querySelector('.bottom'))&Node.DOCUMENT_POSITION_FOLLOWING),
        midCols:d.querySelector('.mid')?d.defaultView.getComputedStyle(d.querySelector('.mid')).gridTemplateColumns.trim().split(/\s+/).length:null,
        bottomCols:d.querySelector('.bottom')?d.defaultView.getComputedStyle(d.querySelector('.bottom')).gridTemplateColumns.trim().split(/\s+/).length:null,
        messageCols:d.querySelector('.bottom .messagebox')?d.defaultView.getComputedStyle(d.querySelector('.bottom .messagebox')).gridTemplateColumns.trim().split(/\s+/).length:null,
        chartHeight:d.querySelector('.mid #ratesbars')?.clientHeight,
        tableFull:Math.abs((d.querySelector('.bottom>.panel:first-child')?.getBoundingClientRect().width||0)-(d.querySelector('.bottom')?.getBoundingClientRect().width||0))<=2,
        allCharts:['strength','ratesbars','spreads'].every(k=>!!d.getElementById(k)?.querySelector('svg')),
        messages:d.querySelectorAll('.bottom .messagebox .msg').length
      },
      railScroll:rail?.scrollWidth,railWidth:rail?.clientWidth,
      bodyScroll:d.documentElement.scrollWidth,bodyWidth:d.documentElement.clientWidth};
  });
  const countNot=Object.values(setupFeed.pairs).filter(x=>x?.setup?.quality==='NON VALUTABILE').length;
  const correctMacro=current(setupFeed.macro_baseline_asof,10);
  const priorityExpected=!correctMacro?'macro':certified<8?'pricing':'pairs';
  const priorityStateExpected=!correctMacro?'HISTORICAL':certified<8?'PARTIAL':'RESEARCH_ONLY';
  if(!homeReading.exists||homeReading.count!==3||
     JSON.stringify(homeReading.routes)!==JSON.stringify(['macro','pricing','pairs'])||
     !homeReading.positioned||!homeReading.globe||homeReading.sourceEffect!=='NONE'||
     homeReading.visualEdition!=='home-composition-v1'||
     !homeReading.layout.styleMounted||!homeReading.layout.heroFullWidth||
     !homeReading.layout.globePreserved||!homeReading.layout.globeRatio||
     !homeReading.layout.firstPanel||!homeReading.layout.secondPanel||
     homeReading.layout.gridColumns!==(label==='mobile'?1:2)||
     homeReading.layout.priorityColumns!==(label==='mobile'?1:2)||
     !homeReading.lower.market||!homeReading.lower.pair||
     !homeReading.lower.marketBefore||!homeReading.lower.pairBefore||
     homeReading.lower.midCols!==(label==='mobile'?1:3)||
     homeReading.lower.bottomCols!==1||
     homeReading.lower.messageCols!==(label==='mobile'?1:2)||
     !homeReading.lower.tableFull||!homeReading.lower.allCharts||
     homeReading.lower.chartHeight<190||homeReading.lower.messages<1||
     homeReading.macro!==setupFeed.macro_baseline_asof||
     homeReading.macroStatus!==(correctMacro?'DATED_SNAPSHOT':'HISTORICAL')||
     homeReading.ois!==String(certified)||homeReading.screener!==String(countNot)||
     homeReading.priorityTarget!==priorityExpected||homeReading.priorityState!==priorityStateExpected||
     !homeReading.priorityFirst||homeReading.emphasized.length!==1||
     homeReading.emphasized[0]!==priorityExpected||
     (priorityExpected==='macro'&&!homeReading.priorityText?.includes(setupFeed.macro_baseline_asof))||
     (priorityExpected==='pricing'&&!homeReading.priorityText?.includes(certified+'/8'))||
     (priorityExpected==='pairs'&&!homeReading.priorityText?.includes(countNot+'/28'))||
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

  await page.waitForFunction(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    return ['RECENT_VALIDATED','DATED_LEVEL_CONTEXT','WITHHELD'].includes(d?.getElementById('gmfq-market-pulse')?.dataset.pulseStatus);
  },null,{timeout:26000});
  await page.waitForFunction(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    return ['FUTURE_VERIFIED_AGENDA','WITHHELD'].includes(d?.getElementById('gmfq-event-radar')?.dataset.calendarStatus);
  },null,{timeout:25000});
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
      flags:[...d.querySelectorAll('#valute .cc[data-filter]')].map(x=>({
        symbol:x.dataset.filter,flag:x.querySelector('.tickerhead .flag')?.textContent,
        visible:!!x.querySelector('.tickerhead .flag')?.getClientRects().length,
        caption:x.querySelector('.gmfq-home-dxy-origin')?.textContent
      })),
      pricing:ois.map(x=>({ccy:x.ccy,status:d.querySelector('#ois .oisrow[data-ccy="'+x.ccy+'"]')?.dataset.pricingState,
        allowed:d.querySelector('#ois .oisrow[data-ccy="'+x.ccy+'"]')?.dataset.policyDeltaAllowed,
        content:x.desc})),
      eventRadar:(()=>{
        const h=d.getElementById('gmfq-event-radar');
        return {state:h?.dataset.calendarStatus,asof:h?.dataset.asOf,signal:h?.dataset.signalEffect,
          title:h?.querySelector('h2')?.textContent,text:h?.textContent,
          count:h?.querySelectorAll('li[data-event-date]').length,
          dates:[...h?.querySelectorAll('li[data-event-date]')||[]].map(e=>e.dataset.eventDate),
          rows:[...h?.querySelectorAll('li[data-event-date]')||[]].map(e=>({
            code:e.dataset.eventCcy,quality:e.dataset.eventQuality,visible:e.closest('details')?.open!==false
          })),
          detailsOpen:h?.querySelector('details')?.open,
          width:h?.scrollWidth,client:h?.clientWidth};
      })(),
      pulse:{state:d.getElementById('gmfq-market-pulse')?.dataset.pulseStatus,
        asof:d.getElementById('gmfq-market-pulse')?.dataset.asOf,
        articles:d.querySelectorAll('#gmfq-market-pulse .gmfq-pulse-item').length,
         contextual:[...d.querySelectorAll('#gmfq-market-pulse [data-pulse-context-ccy]')].map(x=>({
           ccy:x.dataset.pulseContextCcy,quality:x.dataset.pulseQuality,
           text:x.innerText,researchOnly:x.dataset.researchOnly})),
        instruments:[...d.querySelectorAll('#gmfq-market-pulse .gmfq-pulse-item')].map(x=>({
          ccy:x.dataset.pulseCcy,type:x.dataset.instrumentType,
          name:x.querySelector('.gmfq-pulse-instrument')?.textContent,
          one:x.querySelector('.gmfq-pulse-metrics span:nth-child(1) b')?.textContent,
          week:x.querySelector('.gmfq-pulse-metrics span:nth-child(2) b')?.textContent,
          detailsClosed:x.querySelector('details')?.open===false,
          researchOnly:x.dataset.researchOnly})),
        externalSeparation:d.querySelector('#gmfq-market-pulse .gmfq-pulse-links>span')?.textContent,
        title:d.querySelector('#gmfq-market-pulse h2')?.textContent,
        text:d.getElementById('gmfq-market-pulse')?.innerText,
        newsLink:d.querySelector('#gmfq-market-pulse a[href="https://www.reuters.com/markets/"]')?.href,
        width:d.getElementById('gmfq-market-pulse')?.scrollWidth,
        client:d.getElementById('gmfq-market-pulse')?.clientWidth},
      bars2y:d.querySelector('#ratesbars svg')!==null,
      spread:d.querySelector('#spreads svg')!==null,
      designGlobe:!!d.querySelector('.hero .globe'),
      pageWidth:d.documentElement.scrollWidth,viewWidth:d.documentElement.clientWidth
    };
  });
  console.log(label,JSON.stringify(r));
  const fatal=[];
  const currencies=['DXY','EUR','JPY','GBP','AUD','CAD','NZD','CHF'];
  if(r.flags.length!==8||JSON.stringify(r.flags.map(x=>x.symbol))!==JSON.stringify(currencies)||
     r.flags.some(x=>!x.visible||!x.flag)||!r.flags.find(x=>x.symbol==='DXY')?.caption?.includes('SINTETICO'))
    fatal.push('Home flagged currency tiles or DXY disclosure missing '+JSON.stringify(r.flags));
  if(r.pricing.length!==8||new Set(r.pricing.map(x=>x.ccy)).size!==8||
     JSON.stringify(r.pricing.filter(x=>x.status==='OFFICIAL_REPRICING').map(x=>x.ccy).sort())!==JSON.stringify(officialCurrent)||
     r.pricing.some(x=>!['OFFICIAL_REPRICING','FUTURES_LEVEL_ONLY','CASH_CARRY_SCENARIO','BANK_BILL_PROXY','WITHHELD'].includes(x.status)||
       (x.allowed==='true')!==(x.status==='OFFICIAL_REPRICING'))||
     r.pricing.some(x=>x.status==='FUTURES_LEVEL_ONLY'&&!x.content.includes('PX'))||
     r.pricing.some(x=>x.status==='BANK_BILL_PROXY'&&!x.content.includes('BB'))||
     r.pricing.some(x=>x.status==='CASH_CARRY_SCENARIO'&&
       (x.ccy!=='NZD'||!nzdScenario||!x.content.includes(nzdDisplayed+'% ST')||x.allowed!=='false')))
    fatal.push('6M pricing source tiers wrong: '+JSON.stringify(r.pricing));
  if(!['RECENT_VALIDATED','DATED_LEVEL_CONTEXT','WITHHELD'].includes(r.pulse.state)||
     !r.pulse.text.includes('non titoli giornalistici in tempo reale')||
     !r.pulse.newsLink||r.pulse.width>r.pulse.client+2||
     (r.pulse.state==='RECENT_VALIDATED'&&(r.pulse.articles<1||
       !/^20\d{2}-\d{2}-\d{2}$/.test(r.pulse.asof))))
    fatal.push('Market Pulse source-date/fail-closed contract failed '+JSON.stringify(r.pulse));
   if(r.pulse.state==='DATED_LEVEL_CONTEXT'&&
      (r.pulse.contextual.length!==8||
       new Set(r.pulse.contextual.map(x=>x.ccy)).size!==8||
       r.pulse.contextual.some(x=>!['OFFICIAL','PROXY','MIXED','SCENARIO'].includes(x.quality)||
          x.researchOnly!=='true'||!x.text.includes('6M'))||
       !r.pulse.text.includes('Nessuna variazione recente validata')))
     fatal.push('Home 6M context fallback invalid '+JSON.stringify(r.pulse.contextual));
  if(r.pulse.title!=='Market Pulse · tassi impliciti'||
     !r.pulse.externalSeparation?.includes('Notizie esterne')||
     (r.pulse.state==='RECENT_VALIDATED'&&r.pulse.instruments.some(x=>
       !['GBP','CAD','JPY','AUD'].includes(x.ccy)||
       x.type!==(x.ccy==='GBP'?'OIS':'FUTURES')||
       !x.name?.includes(x.ccy==='GBP'?'OIS BoE':'Futures')||
       !/^[-+]?[0-9]+\.[0-9] bp$/.test(x.one||'')||
       !/^[-+]?[0-9]+\.[0-9] bp$/.test(x.week||'')||
       !x.detailsClosed||x.researchOnly!=='true')))
    fatal.push('Market Pulse instrument hierarchy/market vs news contract failed '+JSON.stringify(r.pulse));
  const today=romeTodayIso();
  if(!['FUTURE_VERIFIED_AGENDA','WITHHELD'].includes(r.eventRadar.state)||
     r.eventRadar.signal!=='NONE'||
     r.eventRadar.title!=='Event Risk · prossime pubblicazioni'||
     !r.eventRadar.text?.includes('non notizie né risultati già pubblicati')||
     r.eventRadar.width>r.eventRadar.client+2||
     (r.eventRadar.state==='FUTURE_VERIFIED_AGENDA'&&
       (r.eventRadar.count<1||r.eventRadar.count>6||
        r.eventRadar.dates.some(d=>d<=today)||
        r.eventRadar.rows.some(x=>!['USD','EUR','GBP','JPY','AUD','CAD','NZD','CHF'].includes(x.code)||!x.quality?.startsWith('OFFICIAL_'))||
        r.eventRadar.rows.filter(x=>x.visible).length!==Math.min(2,r.eventRadar.count)||
        (r.eventRadar.count>2&&r.eventRadar.detailsOpen!==false)))||
     (r.eventRadar.state==='WITHHELD'&&r.eventRadar.count!==0))
    fatal.push('Event Risk future-only/preview contract failed '+JSON.stringify(r.eventRadar));
  if((r.dxy||'').trim()!==dxyDisplayed)fatal.push('DXY synthetic not synchronized with its source: '+r.dxy+' != '+dxyDisplayed);
  if(!r.noApprofondisci)fatal.push('old overlay link still shown');
  if(r.rateSeries.length!==8)fatal.push('missing G8 yield lines');
  if(r.oisCount!==8||(nzdScenario&&!r.nzdbb?.includes(nzdDisplayed))||
     (!nzdScenario&&r.pricing.some(x=>x.ccy==='NZD'&&x.status==='CASH_CARRY_SCENARIO')))
    fatal.push('NZD dated scenario / directional proxy mismatch');
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
  if(r.eventRadar.state==='FUTURE_VERIFIED_AGENDA'&&r.eventRadar.count>2){
    const toggle=page.frameLocator('#gmfq-page').locator('#gmfq-event-radar .gmfq-event-radar-more > summary');
    await toggle.click();
    const expandedRadar=await page.evaluate(()=>{
      const h=document.getElementById('gmfq-page').contentDocument.getElementById('gmfq-event-radar');
      return {open:h.querySelector('details')?.open,
        visible:[...h.querySelectorAll('li[data-event-date]')].filter(x=>x.getClientRects().length).length};
    });
    if(!expandedRadar.open||expandedRadar.visible!==r.eventRadar.count)
      throw Error('Event Risk full rows inaccessible '+JSON.stringify(expandedRadar));
    await toggle.click();
  }
  fs.mkdirSync('v10-qa-images',{recursive:true});
  await page.screenshot({path:'v10-qa-images/'+label+'-home.png',fullPage:true});
  // Chart interaction is research-only; every G8 series remains selectable.
  const focusButton=page.frameLocator('#gmfq-page').locator('#ylegend button[data-gmfq-ccy-focus="CHF"]');
  await focusButton.click();
  const selected=await page.evaluate(()=>document.getElementById('gmfq-page').contentDocument.getElementById('curves')?.dataset.gmfqYieldFocus);
  if(selected!=='CHF')throw Error('CHF yield focus failed: '+selected);
  await focusButton.click();
  const restored=await page.evaluate(()=>document.getElementById('gmfq-page').contentDocument.getElementById('curves')?.dataset.gmfqYieldFocus);
  if(restored!=='ALL')throw Error('G8 yield restore failed: '+restored);
  await page.frameLocator('#gmfq-page').locator('#ylegend button[data-gmfq-tenor="10Y"]').click();
  const tenor=await page.evaluate(()=>document.getElementById('gmfq-page').contentDocument.getElementById('curves')?.dataset.gmfqYieldTenor);
  if(tenor!=='10Y')throw Error('10Y yield tenor failed: '+tenor);
  await page.frameLocator('#gmfq-page').locator('#valute .cc[data-filter="DXY"]').click();
  if(!await page.frameLocator('#gmfq-page').locator('dialog#gmfq-dxy-dialog[open]').count())throw Error('In-app DXY dialog did not open');
  const expectedDxy=(()=>{
    const h=dxyFeed.history,t=h.slice(-20),last=t.at(-1),prior=t.at(-2),base=t.at(-6);
    return {day:100*(last.value/prior.value-1),five:100*(last.value/base.value-1),
      low:Math.min(...t.map(x=>x.value)),high:Math.max(...t.map(x=>x.value)),
      sample:t.length};
  })();
  const dxyEvidence=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page').contentDocument,
      modal=d.getElementById('gmfq-dxy-dialog'),metric=modal?.querySelector('.gmfq-dxy-metrics');
    return {open:modal?.open,metrics:metric?.textContent,metricCount:metric?.querySelectorAll('strong').length,
      notIce:metric?.dataset.iceOfficial,notes:modal?.textContent,chart:!!modal?.querySelector('svg polyline'),
      plotWidth:modal?.querySelector('svg')?.getBoundingClientRect().width,
      modalWidth:modal?.getBoundingClientRect().width,
      viewport:d.documentElement.clientWidth};
  });
  const pct=v=>(v>0?'+':'')+v.toFixed(2)+'%';
  if(!dxyEvidence.open||dxyEvidence.metricCount!==3||
    dxyEvidence.notIce!=='false'||!dxyEvidence.chart||
    !dxyEvidence.metrics?.includes(pct(expectedDxy.day))||
    !dxyEvidence.metrics?.includes(pct(expectedDxy.five))||
    !dxyEvidence.metrics?.includes(expectedDxy.low.toFixed(2))||
    !dxyEvidence.metrics?.includes(expectedDxy.high.toFixed(2))||
    !dxyEvidence.notes?.includes('non sull’indice ICE')||
    dxyEvidence.modalWidth>dxyEvidence.viewport+2)
    throw Error('DXY verified source context, visual and non-ICE provenance failed '+JSON.stringify(dxyEvidence));
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
  
  await page.waitForFunction(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    return d?.getElementById('gmfq-yields-study')?.dataset.coverage==='8';
  },null,{timeout:20000});
  const yieldStudy=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page').contentDocument,
      p=d.getElementById('gmfq-yields-study');
    return {count:p.querySelectorAll('.gmfq-yield-row[data-ccy]').length,
      recent:p.dataset.recent,historical:[...p.querySelectorAll('.gmfq-yield-row[data-state="HISTORICAL"]')].map(x=>x.dataset.ccy),
      dates:[...p.querySelectorAll('.gmfq-yield-row[data-ccy]')].map(x=>x.dataset.asof),
      snb:p.querySelector('[data-snb-10y="SEPARATE"]')?.textContent,
      secondary:[...p.querySelectorAll('.gmfq-yield-row[data-ccy]')].map(x=>({
       currency:x.dataset.ccy,
       text:x.querySelector('[data-tier="SECONDARY_OBSERVED_NOT_OFFICIAL"]')?.textContent||null,
       tier:x.querySelector('[data-tier="SECONDARY_OBSERVED_NOT_OFFICIAL"]')?.dataset.tier||null,
       date:x.querySelector('[data-tier="SECONDARY_OBSERVED_NOT_OFFICIAL"]')?.dataset.date||null,
       quality:x.querySelector('[data-tier="SECONDARY_OBSERVED_NOT_OFFICIAL"]')?.dataset.quality||null
      })),
      noCore:p.dataset.coreEffect==='NONE'&&p.dataset.pairEffect==='NONE',
      width:p.scrollWidth,client:p.clientWidth};
  });
  // Sovereign Rates freshness is intentionally per-source and date-based.
  // On 26 Oct the AUD 21 Oct rate is 5 days old and must be shown as
  // historical, not silently counted as a recent official quote.
  const actualRates=JSON.parse(fs.readFileSync(path.join(DATA,'NATIVE_RATES_DATA.json'),'utf8'));
  const expectedHistorical=g8.filter(ccy=>
    !(current(actualRates[ccy]?.date,4)&&
      String(actualRates[ccy]?.quality||'').includes('OFFICIAL'))).sort();
  if(yieldStudy.count!==8||yieldStudy.recent!==String(8-expectedHistorical.length)||
     JSON.stringify(yieldStudy.historical.slice().sort())!==JSON.stringify(expectedHistorical)||
     !yieldStudy.snb?.includes('non calcolare spread misti')||!yieldStudy.noCore||
     yieldStudy.width>yieldStudy.client+2)
    throw Error(label+' G8 observed sovereign yield study not ready '+JSON.stringify(yieldStudy));

  // Secondary CHF/NZD government 2Y market observations must not overwrite
  // the dated official yield; exactly two source-context rows are expected
  // while the canonical source is lagging. No sovereign slope or pair signal.
  const twoYResearch=JSON.parse(fs.readFileSync(
    'validation/rates/fixtures/chf_nzd_2y_secondary_market_2026-10-30.json','utf8'));
  for(const c of ['CHF','NZD']){
    const row=yieldStudy.secondary.find(x=>x.currency===c);
    const official=actualRates[c];
    const market=twoYResearch.observations[c];
    const eligible=official.date<market.market_observation_date&&
      !current(official.date,5);
    if(!row||(eligible&&!row.text?.includes('2Y mercato'))||
       (eligible&&(row.date!==market.market_observation_date||
          !row.text.includes('NON ufficiale')||
          !row.text.includes('non usare per spread FX')))||
       (!eligible&&row.text))
     throw Error(label+' 2Y secondary market provenance not separated '+JSON.stringify({c,row,eligible}));
  }
  console.log('CONTROL_ROOM_SECONDARY_2Y_CHF_NZD_RESEARCH_GREEN',label);
  // Explicit requirement: all eight currency estimates and certified sources
  // must be visible at first read. Method and sources remain accessible.
  await page.waitForFunction(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    return d?.querySelector('#gmfq-ois-research-estimates[data-status="RESEARCH_ONLY"] .gmfq-est-disclosure');
  },null,{timeout:20000});
  const compact=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page').contentDocument,
      p=d.getElementById('gmfq-ois-research-estimates'),details=p.querySelector('.gmfq-est-disclosure');
    return {open:details.open,visible:!!p.querySelector('.gmfq-est-table')?.getClientRects().length,
      note:p.querySelector('.gmfq-est-quick-read')?.textContent,
      sourceRows:p.querySelectorAll('.gmfq-est-row[data-ccy]').length};
  });
  const chartAudit=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument,
      p=d?.getElementById('gmfq-g8-mini-charts');
    return {visible:!!p?.getClientRects().length,count:p?.querySelectorAll('[data-chart-ccy]').length,
      charts:[...p?.querySelectorAll('[data-chart-ccy]')||[]].map(x=>({
        ccy:x.dataset.chartCcy,quality:x.dataset.quality,points:x.querySelectorAll('circle').length,
        joined:x.dataset.joined,svg:!!x.querySelector('svg')?.getClientRects().length
      }))};
  });
  if(!chartAudit.visible||chartAudit.count!==8||
     chartAudit.charts.some(x=>!x.svg||x.points!==3)||
     chartAudit.charts.some(x=>x.quality==='MIXED'&&x.joined!=='false'))
    throw Error(label+' Missing/unverified source-graded G8 charts '+JSON.stringify(chartAudit));
  console.log('CONTROL_ROOM_VISIBLE_G8_CHARTS_GREEN',label,JSON.stringify(chartAudit));
  if(!compact.open||!compact.visible||compact.sourceRows!==8||
     !compact.note?.includes('valute con riferimenti numerici'))
    throw Error('G8 Rates references hidden or incomplete: '+JSON.stringify(compact));
  const sourcePriority=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument,
     p=d?.getElementById('gmfq-ois-research-estimates'),
     o=d?.getElementById('ois-rows')?.closest('.desk-panel'),
     toggle=d?.getElementById('gmfq-certified-only-toggle');
    return {coverage:p?.dataset.sourceGradedCoverage,
      signal:p?.dataset.signalEffect,
      primaryFirst:!!(p&&o&&(p.compareDocumentPosition(o)&Node.DOCUMENT_POSITION_FOLLOWING)),
      officialOnlyHidden:!!o?.hidden,
      toggle:!!toggle,expanded:toggle?.getAttribute('aria-expanded'),
      rows:[...p?.querySelectorAll('.gmfq-est-row[data-ccy]')||[]].map(x=>({
        c:x.dataset.ccy,tier:x.dataset.estimateType,
        numeric:[...x.querySelectorAll(':scope > div')].slice(1,4).map(y=>y.querySelector('b')?.textContent)
      }))};
  });
  if(sourcePriority.coverage!=='8/8'||sourcePriority.signal!=='NONE'||
     !sourcePriority.primaryFirst||!sourcePriority.officialOnlyHidden||
     !sourcePriority.toggle||sourcePriority.expanded!=='false'||
     sourcePriority.rows.length!==8||
     sourcePriority.rows.some(x=>!['OFFICIAL','PROXY','MIXED','SCENARIO'].includes(x.tier)||
       x.numeric.length!==3||x.numeric.some(v=>!v||v==='—')))
    throw Error(label+' Rates main matrix not fully 8/8 source-graded or official-only not collapsed '+JSON.stringify(sourcePriority));
  await page.frameLocator('#gmfq-page').locator('#gmfq-certified-only-toggle').click();
  const officialOpened=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    return {visible:!!d?.getElementById('ois-rows')?.getClientRects().length,
      expanded:d?.getElementById('gmfq-certified-only-toggle')?.getAttribute('aria-expanded')};
  });
  if(!officialOpened.visible||officialOpened.expanded!=='true')
    throw Error('Source-only official OIS audit cannot be examined '+JSON.stringify(officialOpened));
  await page.frameLocator('#gmfq-page').locator('#gmfq-certified-only-toggle').click();
  console.log('CONTROL_ROOM_RATES_8_8_PRIMARY_SOURCE_GRADE_NO_FALSE_OFFICIAL_GREEN',label);
  const toggle=page.frameLocator('#gmfq-page').locator('#gmfq-ois-research-estimates .gmfq-est-disclosure > summary');
  await toggle.click();
  const collapsed=await page.evaluate(()=>{
    const p=document.getElementById('gmfq-page').contentDocument.getElementById('gmfq-ois-research-estimates');
    return {closed:!p.querySelector('.gmfq-est-disclosure').open,
      hidden:!p.querySelector('.gmfq-est-table')?.getClientRects().length};
  });
  if(!collapsed.closed||!collapsed.hidden)
    throw Error('G8 pricing table cannot be collapsed: '+JSON.stringify(collapsed));
  await toggle.click();
  const expanded=await page.evaluate(()=>{
    const p=document.getElementById('gmfq-page').contentDocument.getElementById('gmfq-ois-research-estimates');
    return {open:p.querySelector('.gmfq-est-disclosure').open,
      visible:!!p.querySelector('.gmfq-est-table')?.getClientRects().length,
      currencies:[...p.querySelectorAll('.gmfq-est-row[data-ccy]')].map(x=>x.dataset.ccy),
      method:p.textContent.includes('non intervallo statistico')};
  });
  if(!expanded.open||!expanded.visible||expanded.currencies.length!==8||!expanded.method)
    throw Error('G8 Rates expanded detail/source loss: '+JSON.stringify(expanded));
  await page.frameLocator('#gmfq-page').locator('#rates-select button[data-ccy="NZD"]').click();
  await page.waitForFunction(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    return d?.querySelector('#rates-select button[data-ccy="NZD"]')?.getAttribute('aria-pressed')==='true'
       && d?.getElementById('rates-status')?.textContent.includes('Nuova Zelanda');
  },null,{timeout:15000});
  await page.waitForFunction(expected=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    // The actual plotted ECB/BoE/other curves must obey the SAME
    // 4-day officialPricingCurrent policy as Home and the pair panel.
    return d?.querySelectorAll('#gmfq-pricing-research .gmfq-research-plot svg polyline').length===expected;
  },certified,{timeout:25000});
  // Sources are fetched asynchronously AFTER the currently eligible curves
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
  // A green publisher lane may be stale (GBP 21 Oct on 26 Oct); count
  // currently eligible published price curves, not all certified sources.
  const expectedEstimated=operational.summary.green_estimated;
  const expectedWithheld=operational.summary.operational_withheld;
  const plottedOfficial=Object.entries(operational.currencies).filter(([c,r])=>
    r.operational_status==='GREEN_OFFICIAL'&&r.official_status==='ACTIVE'&&
    r.quality==='OFFICIAL_CERTIFIED'&&r.backtest_eligible_as_official===true&&
    current(r.as_of,4)&&
    ['3m','6m','12m'].every(t=>Number.isFinite(r.horizons?.[t]?.policy_delta_bp)))
    .map(([c])=>c);
  if(research.sourceStatus!=='READ_ONLY'||research.visibleCount!==String(plottedOfficial.length)||
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
  const expandedSourceDetail=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    const p=d?.getElementById('gmfq-pricing-research');
    return {open:p?.querySelector('#gmfq-pricing-evidence-details')?.open,
      secondaryVisible:!!p?.querySelector('.gmfq-quote-card')?.getClientRects().length,
      swissVisible:!!p?.querySelector('#gmfq-chf-snb-10y-context')?.getClientRects().length,
      sourceDetailPresent:!!p?.querySelector('#gmfq-source-readiness')};
  });
  // No secondary quote card is needed once all three USD/EUR/CHF
  // observation lanes are individually verified GREEN_ESTIMATED. Cards
  // must appear only for currently WITHHELD lanes with audited context.
  if(!expandedSourceDetail.open||
     expandedSourceDetail.secondaryVisible!==(expectedSecondaryQuotes>0)||
     !expandedSourceDetail.swissVisible||!expandedSourceDetail.sourceDetailPresent)
    throw Error(label+' Rates full source research unavailable '+JSON.stringify(expandedSourceDetail));
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
      meeting:(()=>{
        const box=p.querySelector('.gmfq-cb-meeting-focus'),det=p.querySelector('.gmfq-cb-meeting-details');
        return {source:box?.dataset.source,asof:box?.dataset.asOf,status:box?.dataset.calendarStatus,
          note:box?.textContent,closed:det?.open===false,total:Number(det?.dataset.count),
          groups:[...box?.querySelectorAll('.gmfq-cb-meeting-dates li')||[]].map(x=>({
            date:x.dataset.meetingDay,ccys:[...x.querySelectorAll('[data-meeting-ccy]')].map(y=>y.dataset.meetingCcy)
          })),
          rows:[...det?.querySelectorAll('.gmfq-cb-meeting-all li')||[]].map(x=>({
            ccy:x.dataset.meetingCcy,date:x.dataset.meetingDate,last:x.dataset.policyAsof,tier:x.dataset.meetingTier
          }))};
      })(),meetingDateGroups:p.dataset.meetingDateGroups,meetingUpcomingCount:p.dataset.meetingUpcomingCount,
      priority:p.querySelector('.gmfq-first-priority')?.textContent,
      evidence:p.querySelector('.gmfq-first-claim')?.textContent,
      order:!!(p.querySelector('.gmfq-first-priority')?.compareDocumentPosition(p.querySelector('.gmfq-first-claim'))&Node.DOCUMENT_POSITION_FOLLOWING),
      text:p.textContent,closed:det.open===false,
      chart:!!d.getElementById('cb-chart'),table:!!d.getElementById('cb-table'),
      width:p.scrollWidth,client:p.clientWidth,
      doc:d.documentElement.scrollWidth,viewport:d.documentElement.clientWidth};
  });
  // Current policy snapshots and published price clocks are distinct.
  // When the policy book cannot be reconciled with current pricing, the
  // intended fail-closed display is WITHHELD; do not demand a nonexistent
  // certified live CB commentary or current meeting agenda.
  if(cbFirst.status==='WITHHELD'){
    if(!cbFirst.priority?.includes('sintesi resta sospesa')||
       !cbFirst.evidence?.includes('Decisioni o pricing non riconciliabili')||
       !cbFirst.text.includes('Dati o copertura insufficienti')||
       !cbFirst.text.toLowerCase().includes('snapshot policy storico')||
       !cbFirst.closed||!cbFirst.chart||!cbFirst.table||!cbFirst.order||
       cbFirst.width>cbFirst.client+2||cbFirst.doc>cbFirst.viewport+16)
      throw Error(label+' CB fail-closed source provenance not honest '+JSON.stringify(cbFirst));
    console.log('CONTROL_ROOM_V10_CB_HISTORIC_SOURCE_FAIL_CLOSED_GREEN',label,
      {policy_last:cbFirst.last,pricing_current:certified});
    await page.screenshot({path:'v10-qa-images/'+label+'-cb-reading-first.png',fullPage:true});
  }else{
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
  const cbMeetingToday=new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Rome',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
  const expectedCb=Object.entries(cbFixture).map(([ccy,x])=>({ccy,date:x.next_meeting,last:x.last_date}))
    .sort((a,b)=>a.date.localeCompare(b.date));
  const futureCb=expectedCb.filter(x=>x.date>cbMeetingToday),days=[...new Set(futureCb.map(x=>x.date))].slice(0,3);
  const goodMeeting=cbFirst.meeting?.source==='NATIVE_CB_DATA'&&
    cbFirst.meeting.status==='HISTORICAL_SNAPSHOT'&&cbFirst.meeting.asof===cbFirst.last&&
    cbFirst.meeting.note?.includes('non sono annunci né meeting confermati in tempo reale')&&
    cbFirst.meetingDateGroups===String(days.length)&&
    cbFirst.meetingUpcomingCount===String(futureCb.length)&&
    cbFirst.meeting.closed&&cbFirst.meeting.total===8&&cbFirst.meeting.rows.length===8&&
    cbFirst.meeting.rows.every((x,i)=>{
      const expected=expectedCb[i],status=operational.currencies[x.ccy].operational_status;
      return x.ccy===expected.ccy&&x.date===expected.date&&x.last===expected.last&&
        x.tier===(status==='GREEN_OFFICIAL'?'CERTIFIED':status==='GREEN_ESTIMATED'?'ESTIMATED':'WITHHELD');
    })&&cbFirst.meeting.groups.length===days.length&&
    cbFirst.meeting.groups.every((x,i)=>x.date===days[i]&&
      JSON.stringify(x.ccys)===JSON.stringify(futureCb.filter(y=>y.date===x.date).map(y=>y.ccy)));
  if(!goodMeeting)throw Error(label+' CB G8 source calendar/provenance broken '+JSON.stringify(cbFirst.meeting));
  const meetingToggle=page.frameLocator('#gmfq-page').locator('#gmfq-cb-reading-first .gmfq-cb-meeting-details>summary');
  await meetingToggle.press('Enter');
  const meetingVisible=await page.evaluate(()=>{
    const panel=document.getElementById('gmfq-page').contentDocument.getElementById('gmfq-cb-reading-first'),
      det=panel.querySelector('.gmfq-cb-meeting-details');
    return {opened:det?.open,rows:[...det?.querySelectorAll('.gmfq-cb-meeting-all li')||[]]
      .filter(x=>x.getClientRects().length).length};
  });
  if(!meetingVisible.opened||meetingVisible.rows!==8)
    throw Error(label+' CB 8-bank detail keyboard disclosure failed '+JSON.stringify(meetingVisible));
  await meetingToggle.press('Enter');
  await page.frameLocator('#gmfq-page').locator('#gmfq-cb-reading-first>details:not(.gmfq-cb-meeting-details)>summary').press('Enter');
  const cbFull=await page.frameLocator('#gmfq-page').locator('#gmfq-cb-reading-first>details:not(.gmfq-cb-meeting-details) p').last().isVisible();
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
  } // End certified CB branch: withheld sources may not be promoted by tests.

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
      focusCount:p.dataset.focusCount,
      focusTitle:p.querySelector('.gmfq-cot-focus-title')?.textContent,
      focusNote:p.querySelector('.gmfq-cot-focus-note')?.textContent,
      focusRows:[...p.querySelectorAll('.gmfq-cot-focus-list li')].map(x=>({
        ccy:x.dataset.cotFocusCcy,netoi:Number(x.dataset.netoi),
        pct:Number(x.dataset.percentileRounded),netSign:x.dataset.netDirection,
        class:x.dataset.percentileClass,visible:!!x.getClientRects().length,
        weeklyNet:Number(x.querySelector('[data-weekly-net]')?.dataset.weeklyNet),
        label:x.textContent
      })),
      percentileCount:p.dataset.percentileCount,rankVsNet:p.dataset.rankVsNet,
      extremeAudit:(()=>{
        const node=p.querySelector('.gmfq-cot-percentile'),detail=p.querySelector('.gmfq-cot-percentile-details');
        return {asof:node?.dataset.cftcAsOf,sep:node?.dataset.relativeVsNet,
          inversions:node?.dataset.inversionCount,closed:detail?.open===false,
          note:node?.querySelector('.gmfq-cot-rank-note')?.textContent,
          rows:[...detail?.querySelectorAll('.gmfq-cot-percentile-list li')||[]].map(x=>({
            ccy:x.dataset.extremeCcy,pct:Number(x.dataset.extremeRank),
            cls:x.dataset.extremeClass,net:Number(x.dataset.extremeNet),
            delta:Number(x.dataset.extremeWeek),relation:x.dataset.rankVsNet
          }))};
      })(),
      weeklyAsOf:p.dataset.weeklyAsOf,weeklyCount:p.dataset.weeklyCount,
      weeklyDetail:(()=>{
        const detail=p.querySelector('.gmfq-cot-weekly-details');
        return {closed:detail?.open===false,previous:detail?.dataset.priorAsof,
          latest:detail?.dataset.currentAsof,
          currencies:[...detail?.querySelectorAll('.gmfq-cot-weekly-list li')||[]].map(x=>({
            ccy:x.dataset.weeklyCcy,net:Number(x.dataset.weeklyNet),
            previousNet:Number(x.dataset.weeklyPrevNet),delta:Number(x.dataset.weeklyDelta),
            text:x.textContent
          })),method:detail?.querySelector('.gmfq-cot-weekly-method')?.textContent};
      })(),
      priority:p.querySelector('.gmfq-first-priority')?.textContent,
      evidence:p.querySelector('.gmfq-first-claim')?.textContent,
      order:!!(p.querySelector('.gmfq-first-priority')?.compareDocumentPosition(p.querySelector('.gmfq-first-claim'))&Node.DOCUMENT_POSITION_FOLLOWING),
      text:p.textContent,closed:p.querySelector('details').open===false,
      chart:!!d.getElementById('cot-chart'),table:!!d.getElementById('cot-table'),
      width:p.scrollWidth,client:p.clientWidth,
      doc:d.documentElement.scrollWidth,viewport:d.documentElement.clientWidth};
  });
  const expectedExtremes=g8.map(ccy=>{
    const t=cotFixture[ccy],pct=Math.round(t.percentile.at(-1)),net=t.net.at(-1),
      cls=pct>=80?'EXTREME LONG':pct<=20?'EXTREME SHORT':'NEUTRALE';
    return {ccy,pct,net,delta:net-t.net.at(-2),cls,
      relation:(cls==='EXTREME LONG'&&net<0)||(cls==='EXTREME SHORT'&&net>0)?'OPPOSED':'ALIGNED'};
  }).filter(x=>x.cls!=='NEUTRALE');
  const opposedExpected=expectedExtremes.filter(x=>x.relation==='OPPOSED');
  const opposedCHF=opposedExpected.find(x=>x.ccy==='CHF');
  const expectedCHFNote=opposedCHF?
    'CHF '+opposedCHF.pct+'° · '+opposedCHF.cls+', ma Net':null;
  if(cotFirst.percentileCount!==String(expectedExtremes.length)||
     cotFirst.rankVsNet!==String(opposedExpected.length)||
     cotFirst.extremeAudit?.asof!==cotFixture.USD.dates.at(-1)||
     cotFirst.extremeAudit.sep!=='SEPARATE'||
     cotFirst.extremeAudit.inversions!==String(opposedExpected.length)||
     !cotFirst.extremeAudit.closed||
     cotFirst.extremeAudit.rows.length!==expectedExtremes.length||
     !cotFirst.extremeAudit.note?.includes('Percentile ≠ segno del Net')||
     (expectedCHFNote&&!cotFirst.extremeAudit.note?.includes(expectedCHFNote))||
     cotFirst.extremeAudit.rows.some((x,i)=>{
       const expected=expectedExtremes[i];return !expected||
         x.ccy!==expected.ccy||x.pct!==expected.pct||x.net!==expected.net||
         x.delta!==expected.delta||x.cls!==expected.cls||x.relation!==expected.relation;
     }))
    throw Error(label+' COT relative-percentile vs signed-net evidence failed '+
      JSON.stringify({got:cotFirst.extremeAudit,expectedExtremes}));
  const expectedCrowding=g8.map(ccy=>({
    ccy,netoi:cotFixture[ccy].netoi.at(-1),pct:Math.round(cotFixture[ccy].percentile.at(-1)),
    netSign:cotFixture[ccy].net.at(-1)>0?'NET_LONG':cotFixture[ccy].net.at(-1)<0?'NET_SHORT':'NET_FLAT'
  })).filter(x=>Math.abs(x.netoi)>=30).sort((a,b)=>Math.abs(b.netoi)-Math.abs(a.netoi)).slice(0,3);
  const sourceFocusOk=cotFirst.focusRows.length===expectedCrowding.length&&
   cotFirst.focusRows.every((x,i)=>{
     const expected=expectedCrowding[i];
     return x.ccy===expected.ccy&&Math.abs(x.netoi-expected.netoi)<0.00001&&
       x.pct===expected.pct&&x.netSign===expected.netSign&&x.visible&&
       x.label.includes(x.pct+'°/104W')&&
       x.class===(x.pct>=80?'EXTREME LONG':x.pct<=20?'EXTREME SHORT':'NEUTRALE');
   });
  const weeklyExpected=g8.map(ccy=>{
    const t=cotFixture[ccy],net=t.net.at(-1),previousNet=t.net.at(-2);
    return {ccy,net,previousNet,delta:net-previousNet};
  });
  const weeklyFocusOk=cotFirst.focusRows.every(row=>
    row.weeklyNet===weeklyExpected.find(x=>x.ccy===row.ccy)?.delta);
  const weeklyDetailOk=cotFirst.weeklyAsOf===cotFixture.USD.dates.at(-2)&&
    cotFirst.weeklyCount==='8'&&cotFirst.weeklyDetail?.closed===true&&
    cotFirst.weeklyDetail.previous===cotFixture.USD.dates.at(-2)&&
    cotFirst.weeklyDetail.latest===cotFixture.USD.dates.at(-1)&&
    cotFirst.weeklyDetail.currencies.length===8&&
    cotFirst.weeklyDetail.currencies.every((x,i)=>x.ccy===weeklyExpected[i].ccy&&
      x.net===weeklyExpected[i].net&&x.previousNet===weeklyExpected[i].previousNet&&
      x.delta===weeklyExpected[i].delta)&&
    cotFirst.weeklyDetail.method?.includes('Non confrontare direttamente il numero di contratti');
  if(!weeklyFocusOk||!weeklyDetailOk)
    throw Error(label+' COT weekly Net changes do not match official weekly positions '+
      JSON.stringify({cotFirst,weeklyExpected}));
  if(!sourceFocusOk||cotFirst.focusCount!==String(expectedCrowding.length)||
     !cotFirst.focusTitle?.includes('CONCENTRAZIONE NET/OI ≥30%')||
     !cotFirst.focusNote?.includes('non direzione del prezzo'))
    throw Error(label+' COT focused crowding does not match 104W source '+JSON.stringify({cotFirst,expectedCrowding}));
  if(cotFirst.status!=='READ_ONLY'||cotFirst.conflicts!==''||
     cotFirst.asof!==cotFixture.USD.dates.at(-1)||
     cotFirst.extremes!==String(expectedExtremes.length)||
     cotFirst.crowding!==String(g8.filter(ccy=>
       Math.abs(cotFixture[ccy].netoi.at(-1))>=30).length)||
     !cotFirst.closed||!cotFirst.chart||!cotFirst.table||
     !cotFirst.text.includes('Prezzo FX: WITHHELD')||
     !cotFirst.priority?.startsWith('Gli estremi COT descrivono')||
     !cotFirst.evidence?.includes('Estremi percentile 104W')||!cotFirst.order||
     cotFirst.text.includes('narrativo incoerente')||
     cotFirst.width>cotFirst.client+2||cotFirst.doc>cotFirst.viewport+16)
    throw Error(label+' COT quantitative/narrative divergence guard '+JSON.stringify(cotFirst));
  const extremeToggle=page.frameLocator('#gmfq-page').locator('#gmfq-cot-reading-first .gmfq-cot-percentile-details>summary');
  await extremeToggle.press('Enter');
  const extremeVisible=await page.evaluate(()=>{
    const p=document.getElementById('gmfq-page').contentDocument.getElementById('gmfq-cot-reading-first');
    const detail=p.querySelector('.gmfq-cot-percentile-details');
    return {opened:detail?.open,visible:[...detail?.querySelectorAll('.gmfq-cot-percentile-list li')||[]].filter(x=>x.getClientRects().length).length};
  });
  if(!extremeVisible.opened||extremeVisible.visible!==expectedExtremes.length)
     throw Error(label+' COT historical percentile extremes detail inaccessible '+JSON.stringify(extremeVisible));
  await extremeToggle.press('Enter');
  const weeklyToggle=page.frameLocator('#gmfq-page').locator('#gmfq-cot-reading-first .gmfq-cot-weekly-details>summary');
  await weeklyToggle.press('Enter');
  const weeklyExpanded=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page').contentDocument,
      p=d.getElementById('gmfq-cot-reading-first'),detail=p.querySelector('.gmfq-cot-weekly-details');
    return {open:detail.open,rows:[...detail.querySelectorAll('.gmfq-cot-weekly-list li')].filter(x=>x.getClientRects().length).length};
  });
  if(!weeklyExpanded.open||weeklyExpanded.rows!==8)
    throw Error(label+' COT weekly 8 G8 observations inaccessible '+JSON.stringify(weeklyExpanded));
  await weeklyToggle.press('Enter');
  await page.frameLocator('#gmfq-page').locator('#gmfq-cot-reading-first>details>summary').press('Enter');
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
  const narrativeNoPromotion=await page.evaluate(()=>{
    const p=document.getElementById('gmfq-page').contentDocument.getElementById('gmfq-cot-reading-first');
    return {rankStatus:p.dataset.rankVsNet,hasSourceRank:!!p.querySelector('.gmfq-cot-percentile')};
  });
  if(narrativeNoPromotion.hasSourceRank||narrativeNoPromotion.rankStatus)
    throw Error(label+' COT rank interpretation promoted conflicting stories '+JSON.stringify(narrativeNoPromotion));
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
  // A corrupted prior-week contract cannot produce an apparently valid ΔNet.
  await page.route('**/V250_COT_CHART_DATA.json',async r=>{
    const x=JSON.parse(fs.readFileSync(path.join(DATA,'V250_COT_CHART_DATA.json'),'utf8'));
    x.GBP.net[x.GBP.net.length-2]+=1; // previous long-short does not match net
    await r.fulfill({status:200,contentType:'application/json',body:JSON.stringify(x),
      headers:{'Access-Control-Allow-Origin':'*'}});
  });
  await page.goto(url+'#/home',{waitUntil:'domcontentloaded',timeout:120000});
  await page.goto(url+'#/cot?ccy=GBP&bad=previous-net',{waitUntil:'domcontentloaded',timeout:120000});
  await page.waitForFunction(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument,p=d?.getElementById('gmfq-cot-reading-first');
    return p?.dataset.readingStatus==='WITHHELD'&&!p.querySelector('.gmfq-cot-weekly-details');
  },null,{timeout:35000});
  await page.unroute('**/V250_COT_CHART_DATA.json');
  console.log('CONTROL_ROOM_V10_CB_COT_FIRST_READING_GREEN',label,{
    policy:cbFirst.status,ois:cbFirst.certified,cot:cotFirst.asof,
    extremes:cotFirst.extremes,crowding:cotFirst.crowding,conflict:cotFirst.conflicts});

  // Macro provenance: historical model scores cannot be refreshed by newer,
  // independently dated Inflation/Labour observations.
  const oldModel=JSON.parse(fs.readFileSync(path.join(DATA,'D.json'),'utf8'));
  const macroThermo=JSON.parse(fs.readFileSync(path.join(DATA,'MACRO_THERMOMETER_DATA.json'),'utf8'));
  // Official-web Q2 GDP evidence is a fixture-based source, never a live
  // headline inferred from the old D scalar. Intercept it identically in QA.
  await page.route('https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/main/validation/macro/fixtures/v2_g8_quarterly_gdp_q2_2026_web_release_ledger_v1.json',async route=>{
    const evidence=fs.readFileSync('validation/macro/fixtures/v2_g8_quarterly_gdp_q2_2026_web_release_ledger_v1.json');
    await route.fulfill({status:200,contentType:'application/json',body:evidence,headers:{'Access-Control-Allow-Origin':'*'}});
  });
  await page.goto(url+'#/macro?ccy=EUR',{waitUntil:'domcontentloaded',timeout:120000});
  await page.waitForFunction(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    return d?.getElementById('gmfq-macro-source-lens')?.dataset.auditStatus==='READ_ONLY';
  },null,{timeout:40000});
  await page.waitForFunction(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument,
      p=d?.getElementById('gmfq-macro-v2-current-evidence');
    return p?.dataset.status==='OBSERVED_RESEARCH_CONTEXT'&&
      p.querySelectorAll('.gmfq-macro-v2-country').length===8;
  },null,{timeout:40000});
  const macroV2=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument,
      p=d?.getElementById('gmfq-macro-v2-current-evidence');
    return {status:p?.dataset.status,count:p?.dataset.currencyCount,
      score:p?.dataset.macroScoreEffect,pairs:p?.dataset.pairRankEffect,
      rows:[...p?.querySelectorAll('.gmfq-macro-v2-country')||[]].map(x=>({
        currency:x.dataset.ccy,quarter:x.dataset.growthPeriod,
        ratesDate:x.dataset.ratesDate,oisQuality:x.dataset.oisQuality,
        marketTier:x.dataset.secondary2yTier,marketDate:x.dataset.secondary2yDate,
        text:x.textContent})),
      width:p?.scrollWidth,client:p?.clientWidth,
      docWidth:d?.documentElement.scrollWidth,viewport:d?.documentElement.clientWidth};
  });
  const expectedMacroCcy=g8.filter(c=>!!macroThermo.currencies?.[c]);
  // The native dashboard uses its own fixed display order. Validate the
  // unordered 8-currency coverage, not a cosmetic currency ordering.
  if(macroV2.status!=='OBSERVED_RESEARCH_CONTEXT'||macroV2.count!=='8'||
     macroV2.score!=='NONE'||macroV2.pairs!=='NONE'||
     macroV2.rows.length!==8||
     JSON.stringify(macroV2.rows.map(x=>x.currency).sort())!==JSON.stringify(expectedMacroCcy.sort())||
     macroV2.rows.some(x=>x.quarter!=='2026Q2'||!x.text.includes('Inflazione')||
       !x.text.includes('Disoccupazione')||!x.text.includes('6M monetario')||
       x.ratesDate!==ratesFeed[x.currency].date)||
     macroV2.width>macroV2.client+2||macroV2.docWidth>macroV2.viewport+16)
    throw Error(label+' G8 current V2 economic/rates source context incorrect '+JSON.stringify(macroV2));
  for(const c of ['CHF','NZD']){
    const row=macroV2.rows.find(x=>x.currency===c);
    const quote=JSON.parse(fs.readFileSync('validation/rates/fixtures/chf_nzd_2y_secondary_market_2026-10-30.json')).observations[c];
    const expected=ratesFeed[c].date<quote.market_observation_date&&!current(ratesFeed[c].date,5);
    if(!row||(expected&&(
      row.marketTier!=='SECONDARY_OBSERVED_NOT_OFFICIAL'||
      row.marketDate!==quote.market_observation_date||
      !row.text.includes('2Y riferimento mercato')||
      !row.text.includes('nessuno spread/score')))||
      (!expected&&row.marketTier!=='NONE'))
      throw Error(label+' macro market 2Y context contamination '+JSON.stringify({c,row,expected}));
  }
  console.log('CONTROL_ROOM_MACRO_V2_G8_CURRENT_EVIDENCE_RESEARCH_GREEN',label,
    {count:macroV2.rows.length,period:'2026Q2',scoreEffect:'NONE'});
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
      dynamics:[...p.querySelectorAll('.gmfq-macro-dynamic')].map(x=>({
        metric:x.dataset.macroMetric,status:x.dataset.dynamicStatus,
        direction:x.dataset.direction,acceleration:x.dataset.acceleration,
        date:x.dataset.asOf,visible:!!x.getClientRects().length
      })),
      dynamicNote:p.querySelector('.gmfq-macro-dynamics-note')?.textContent,
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
  const expectedDynamics=['inflation','labour'].map((key,i)=>({
    metric:i===0?'Inflazione':'Lavoro',source:macroThermo.currencies.EUR[key]
  }));
  if(macroLens.dynamics.length!==2||
     !macroLens.dynamicNote?.includes('non alla forza della valuta')||
     !macroLens.dynamicNote?.includes('Nessun aggiornamento dei 24 score')||
     macroLens.dynamics.some((x,i)=>x.metric!==expectedDynamics[i].metric||
       x.status!=='OBSERVED'||x.direction!==expectedDynamics[i].source.direction||
       x.acceleration!==expectedDynamics[i].source.acceleration||
       x.date!==expectedDynamics[i].source.as_of||!x.visible))
    throw Error(label+' Macro validated dynamics missing '+JSON.stringify(macroLens.dynamics));
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
  const invalidDynamics=await page.evaluate(()=>{
    const p=document.getElementById('gmfq-page').contentDocument.getElementById('gmfq-macro-source-lens');
    return [...p.querySelectorAll('.gmfq-macro-dynamic')].map(x=>({metric:x.dataset.macroMetric,status:x.dataset.dynamicStatus}));
  });
  if(invalidDynamics[0]?.metric!=='Inflazione'||invalidDynamics[0]?.status!=='WITHHELD'||
     invalidDynamics[1]?.metric!=='Lavoro'||invalidDynamics[1]?.status!=='OBSERVED')
    throw Error(label+' invalid Macro period incorrectly promoted to dynamics');
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
    const detail=p.querySelector('.gmfq-vsc-details');
    return {fx:p.dataset.fxAsOf,dxy:p.dataset.dxyStatus,macro:p.dataset.macroAsOf,
      readingState:p.dataset.readingState,
      text:p.textContent,detail:!!detail?.querySelector('summary'),
      initiallyClosed:detail?.open===false,
      ledgerInitiallyHidden:!p.querySelector('.gmfq-vsc-ledger')?.getClientRects().length,
      priority:p.querySelector('.gmfq-vsc-priority')?.textContent,
      sourceKeys:[...p.querySelectorAll('.gmfq-vsc-ledger span[data-source]')].map(x=>x.dataset.source),
      priorityFirst:!!(p.querySelector('.gmfq-vsc-priority')?.compareDocumentPosition(detail)&Node.DOCUMENT_POSITION_FOLLOWING),
      innerWidth,innerClient,nativeWidth,width:d.documentElement.scrollWidth,viewport:d.documentElement.clientWidth};
  });
  if(valute.fx!==fxHistory.last_as_of||valute.macro!==legacy.asOf||
     valute.dxy!=='SYNTHETIC_ECB'||!valute.detail||
     !valute.initiallyClosed||!valute.ledgerInitiallyHidden||
     valute.readingState!=='MACRO_HISTORICAL'||
     !valute.priority?.includes('tesi Macro ancora alla baseline '+legacy.asOf)||
     !valute.priority?.includes('I nuovi fixing non aggiornano lo score')||
     !valute.priorityFirst||
     JSON.stringify(valute.sourceKeys)!==JSON.stringify(['fixing','dxy','macro'])||
     !valute.text.includes('non il DXY ICE ufficiale')||
     !valute.text.includes('Il ranking momentum G8 qui sotto è calcolato separatamente')||
     valute.innerWidth>valute.innerClient+2||
     valute.width>Math.max(valute.viewport+16,valute.nativeWidth+2))
    throw Error(label+' Valute provenance contract '+JSON.stringify(valute));
  const valuteToggle=page.frameLocator('#gmfq-page').locator('#gmfq-valute-source-compass .gmfq-vsc-details > summary');
  await valuteToggle.click();
  const expandedValute=await page.evaluate(()=>{
    const p=document.getElementById('gmfq-page').contentDocument.getElementById('gmfq-valute-source-compass');
    return {open:p.querySelector('.gmfq-vsc-details')?.open,
      ledgerVisible:!!p.querySelector('.gmfq-vsc-ledger')?.getClientRects().length,
      keys:[...p.querySelectorAll('.gmfq-vsc-ledger span[data-source]')].map(x=>x.dataset.source)};
  });
  if(!expandedValute.open||!expandedValute.ledgerVisible||
      JSON.stringify(expandedValute.keys)!==JSON.stringify(['fixing','dxy','macro']))
    throw Error(label+' Valute full source ledger inaccessible '+JSON.stringify(expandedValute));
  await valuteToggle.click();
  await page.screenshot({path:'v10-qa-images/'+label+'-valute-sources.png',fullPage:true});
  // Relative price ranking: two explicit horizons, all eight currencies, no
  // reinterpretation of the frozen Macro baseline or trade readiness.
  await page.waitForFunction(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    return d?.getElementById('gmfq-vsc-momentum')?.dataset.status==='OBSERVED';
  },null,{timeout:30000});
  const readValuteMomentumRank=async()=>page.evaluate(()=>{
    const d=document.getElementById('gmfq-page').contentDocument,
      p=d.getElementById('gmfq-vsc-momentum');
    return {status:p?.dataset.status,source:p?.dataset.source,signals:p?.dataset.tradeSignals,
      horizon:p?.dataset.horizon,asof:p?.dataset.asof,from:p?.dataset.from,
      rows:[...p?.querySelectorAll('ol li')||[]].map(x=>({
        ccy:x.dataset.vsmCcy,n:Number(x.dataset.vsmRank),text:x.textContent.trim()})),
      note:p?.querySelector('.gmfq-vsm-caution')?.textContent,
      firstRead:{
        source:p?.querySelector('.gmfq-vsm-reading')?.dataset.source,
        status:p?.dataset.comparisonStatus,ccy:p?.dataset.comparisonCurrency,
        otherRank:p?.dataset.comparisonOtherRank,
        text:p?.querySelector('.gmfq-vsm-reading')?.textContent},
      width:p?.scrollWidth,client:p?.clientWidth,
      doc:d.documentElement.scrollWidth,viewport:d.documentElement.clientWidth};
  });
  const expectedRank=h=>{
    const old=fxHistory.rows.at(-h-1),recent=fxHistory.rows.at(-1);
    return g8.map(ccy=>({ccy,change:-Math.log(recent[ccy]/old[ccy])}))
      .sort((a,b)=>b.change-a.change||a.ccy.localeCompare(b.ccy))
      .map(x=>x.ccy);
  };
  const checkRank=(actual,h)=>{
    const expected=expectedRank(h);
    const leader=expected[0],alternate=expectedRank(h===5?20:5),
          leaderOtherRank=alternate.indexOf(leader)+1,
          reading=actual.firstRead;
    if(reading.source!=='ECB_G8_PRICE_HISTORY'||reading.status!=='OBSERVED'||
       reading.ccy!==leader||reading.otherRank!==String(leaderOtherRank)||
       !reading.text.includes('Lettura rapida')||
       !reading.text.includes('Le due finestre si sovrappongono: non prova una svolta.')||
       !reading.text.includes(h===5?'20 sedute':'5 sedute'))
      throw Error(label+' G8 '+h+'-session reading contradicts source ranking '+JSON.stringify({reading,expected,alternate}));
    if(actual.status!=='OBSERVED'||actual.source!=='ECB_G8_PRICE_HISTORY'||
       actual.signals!=='NONE'||actual.horizon!==String(h)||
       actual.asof!==fxHistory.last_as_of||actual.from!==fxHistory.rows.at(-h-1).Date||
       actual.rows.length!==8||
       actual.rows.some((x,i)=>x.ccy!==expected[i]||x.n!==i+1||!x.text.includes('%'))||
       !actual.note?.includes('non è forza Macro/Tassi')||
       actual.width>actual.client+2||actual.doc>actual.viewport+16)
      throw Error(label+' G8 '+h+'-session momentum/source semantics failed '+JSON.stringify({actual,expected}));
  };
  checkRank(await readValuteMomentumRank(),5);
  await page.frameLocator('#gmfq-page').locator('#gmfq-vsc-momentum button[data-vsm-days="20"]').click();
  checkRank(await readValuteMomentumRank(),20);
  await page.frameLocator('#gmfq-page').locator('#gmfq-vsc-momentum button[data-vsm-days="5"]').click();
  checkRank(await readValuteMomentumRank(),5);
  console.log('CONTROL_ROOM_V10_VALUTE_ECB_MOMENTUM_RANK_GREEN',label);
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
  if(invalidFx.fx!==''||!invalidFx.text.includes('FX BCE non corrente o non verificabile')||
     !invalidFx.text.includes('Prima verifica: fixing BCE FX non corrente'))
    throw Error(label+' Valute invalid FX not withheld '+JSON.stringify(invalidFx));
  const rankingAbsent=await page.evaluate(()=>!document.getElementById('gmfq-page')?.contentDocument?.getElementById('gmfq-vsc-momentum'));
  if(!rankingAbsent)throw Error(label+' unverified ECB observations must never produce a momentum ranking');
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
      qualityCoverage:p.dataset.qualityCoverage,reviewCount:p.dataset.reviewCount,
      quality:[...p.querySelectorAll('.gmfq-screener-quality span[data-quality]')].map(x=>({
        tier:x.dataset.quality,count:Number(x.querySelector('b')?.textContent)})),
      reviewState:(()=>{
        const box=p.querySelector('.gmfq-screener-review');
        return {rank:box?.dataset.ranking,signal:box?.dataset.tradeSignals,
          text:box?.textContent,
          pairs:[...box?.querySelectorAll('button.gmfq-review-pair[data-pair]')||[]].map(x=>({
            code:x.dataset.pair,tier:x.dataset.quality,visible:!!x.getClientRects().length
          }))};
      })(),
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
  const knownTiers=['DA CONFERMARE','DA MONITORARE','CON RISCHI','NON VALUTABILE'];
  const expectedQuality=Object.fromEntries(knownTiers.map(k=>[k,
    Object.values(setupFeed.pairs).filter(x=>x.setup.quality===k).length]));
  const expectedReview=Object.entries(setupFeed.pairs)
    .filter(([,x])=>['DA MONITORARE','DA CONFERMARE'].includes(x.setup.quality))
    .map(([code,x])=>({code,tier:x.setup.quality})).sort((a,b)=>a.code.localeCompare(b.code));
  const reviewValid=reasons.qualityCoverage==='28'&&
    reasons.reviewCount===String(expectedReview.length)&&
    reasons.reviewState?.rank==='NONE'&&reasons.reviewState?.signal==='NONE'&&
    reasons.reviewState.text?.includes('non proposte di ingresso')&&
    reasons.reviewState.text?.includes(setupFeed.macro_baseline_asof)&&
    reasons.quality.length===knownTiers.length&&
    reasons.quality.every((x,i)=>x.tier===knownTiers[i]&&x.count===expectedQuality[x.tier])&&
    reasons.reviewState.pairs.length===expectedReview.length&&
    reasons.reviewState.pairs.every((x,i)=>x.code===expectedReview[i].code&&
      x.tier===expectedReview[i].tier&&x.visible);
  if(!reviewValid)
    throw Error(label+' canonical 28-quality Screener coverage/review-only grouping failed '+JSON.stringify(reasons));
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

  // Research-only shortcuts must land at the canonical Pair Deep Dive
  // without creating a signal, entry, rank or secondary pair calculation.
  if(expectedReview.length){
    const link=expectedReview.find(x=>x.code==='USDCAD')||expectedReview[0];
    await page.goto(url+'#/screener',{waitUntil:'domcontentloaded',timeout:120000});
    await page.waitForFunction(()=>{
      const d=document.getElementById('gmfq-page')?.contentDocument;
      return d?.getElementById('gmfq-screener-blockers')?.dataset.diagnosisStatus==='READ_ONLY';
    },null,{timeout:30000});
    await page.frameLocator('#gmfq-page').locator('#gmfq-screener-blockers button.gmfq-review-pair[data-pair="'+link.code+'"]').click();
    await page.waitForURL(u=>u.hash==='#/coppie?pair='+link.code,{timeout:20000});
  }

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
  await page.waitForFunction(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument,p=d?.getElementById('gmfq-pair-rank');
    return p?.dataset.status==='READ_ONLY'&&
      d.querySelectorAll('#pair-index tr[data-research-rank]').length===28;
  },null,{timeout:30000});
  const readRank=()=>page.evaluate(()=>{
    const d=document.getElementById('gmfq-page').contentDocument,p=d.getElementById('gmfq-pair-rank'),
      rows=[...d.querySelectorAll('#pair-index tr[data-research-rank]')];
    return {status:p?.dataset.status,count:p?.dataset.count,mode:p?.dataset.sortMode,
      trade:p?.dataset.hasTradeRanking,baseline:p?.dataset.macroAsOf,price:p?.dataset.priceAsOf,
      view:p?.dataset.viewMode,visibleCount:Number(p?.dataset.visibleCount),
      nativeSummary:d.getElementById('pair-visible')?.textContent,
      readingMode:p?.dataset.readingMode,
      rowReading:d.getElementById('pair-index')?.dataset.researchReading,
      readingButtons:[...p.querySelectorAll('button[data-pair-reading]')].map(x=>({
        level:x.dataset.pairReading,pressed:x.getAttribute('aria-pressed')})),
      methodClosed:p.querySelector('.gmfq-rank-method-detail')?.open===false,
      readingSample:(()=>{
        const r=rows[0],w=d.defaultView;
        return {rank:r?.dataset.researchRank,whyVisible:!!r?.querySelector('.gmfq-row-why')?.getClientRects().length,
          lensDisplay:r?.querySelector('.gmfq-row-lenses')?w.getComputedStyle(r.querySelector('.gmfq-row-lenses')).display:null,
          checkDisplay:r?.querySelector('.gmfq-row-next')?w.getComputedStyle(r.querySelector('.gmfq-row-next')).display:null,
          sourceLens:r?.querySelector('.gmfq-row-lenses')?.dataset.source,
          sourceCheck:r?.querySelector('.gmfq-row-next')?.dataset.source};
      })(),
      overlap:(()=>{
        const n=p.querySelector('.gmfq-rank-overlap');
        return {status:n?.dataset.status,source:n?.dataset.source,text:n?.textContent,
          total:n?.dataset.topCount,risks:n?.dataset.withRisks,
          repeated:n?.dataset.mostRepeated,max:n?.dataset.frequency,
          favored:n?.dataset.favoredCount};
      })(),
      viewModes:[...p.querySelectorAll('button[data-pair-view]')].map(x=>({
        mode:x.dataset.pairView,pressed:x.getAttribute('aria-pressed')})),
      panelWidth:p?.scrollWidth,panelClient:p?.clientWidth,
      docWidth:d.documentElement.scrollWidth,viewport:d.documentElement.clientWidth,
      modes:[...p.querySelectorAll('button[data-rank-mode]')].map(x=>({
        mode:x.dataset.rankMode,pressed:x.getAttribute('aria-pressed')})),
      descriptions:rows.map(x=>({
        code:x.querySelector('button.pair-open')?.dataset.pair,rank:Number(x.dataset.researchRank),
        why:x.querySelector('.gmfq-row-why')?.textContent,
        firstCheck:x.querySelector('.gmfq-row-next')?.textContent,
        checkSource:x.querySelector('.gmfq-row-next')?.dataset.source,
        lenses:x.querySelector('.gmfq-row-lenses')?.textContent,
        lensSource:x.querySelector('.gmfq-row-lenses')?.dataset.source,
        label:x.querySelector('.gmfq-row-rank')?.textContent,mode:x.dataset.researchMode,
        visible:!!x.getClientRects().length,selected:x.classList.contains('pair-current')
      }))};
  });
  const rankSetup=await readRank();
  if(rankSetup.status!=='READ_ONLY'||rankSetup.count!=='28'||rankSetup.trade!=='false'||
     rankSetup.baseline!==setupFeed.macro_baseline_asof||rankSetup.price!==setupFeed.price_asof||
     rankSetup.mode!=='setup'||rankSetup.panelWidth>rankSetup.panelClient+2||
     rankSetup.docWidth>rankSetup.viewport+16||
     rankSetup.descriptions.length!==28||
     rankSetup.descriptions.some((x,i)=>x.rank!==i+1||
       x.label!==String(i+1).padStart(2,'0')||
       x.mode!=='setup'||!x.why?.length||!x.firstCheck?.startsWith('Primo controllo · ')||
       x.checkSource!=='PAIR_SETUP_OPERATIONAL_VIEW'||
       !setupFeed.pairs[x.code])||
     JSON.stringify(rankSetup.modes)!==JSON.stringify([
       {mode:'setup',pressed:'true'},{mode:'thesis',pressed:'false'}]))
    throw Error(label+' Pair ranked setup first reading failed '+JSON.stringify(rankSetup));
  // Verify the first viewport shows one named obstacle per native row;
  // source-detail layers remain mounted and accessible one click away.
  if(rankSetup.readingMode!=='compact'||rankSetup.rowReading!=='compact'||
     !rankSetup.methodClosed||!rankSetup.readingSample.whyVisible||
     rankSetup.readingSample.lensDisplay!=='none'||
     rankSetup.readingSample.checkDisplay!=='none'||
     rankSetup.readingSample.sourceLens!=='PAIR_SETUP_OPERATIONAL_VIEW'||
     rankSetup.readingSample.sourceCheck!=='PAIR_SETUP_OPERATIONAL_VIEW'||
     JSON.stringify(rankSetup.readingButtons)!==JSON.stringify([
       {level:'compact',pressed:'true'},{level:'details',pressed:'false'}]))
    throw Error(label+' first pair viewport is too dense or hides source risk '+JSON.stringify(rankSetup));
  await page.frameLocator('#gmfq-page').locator('#gmfq-pair-rank button[data-pair-reading="details"]').click();
  const detailedRead=await readRank();
  if(detailedRead.readingMode!=='details'||detailedRead.rowReading!=='details'||
     detailedRead.readingSample.lensDisplay==='none'||
     detailedRead.readingSample.checkDisplay==='none'||
     !detailedRead.readingSample.whyVisible||
     detailedRead.readingButtons[1]?.pressed!=='true'||
     JSON.stringify(detailedRead.descriptions.map(x=>x.code))!==
       JSON.stringify(rankSetup.descriptions.map(x=>x.code)))
    throw Error(label+' full pair checks lost or native rank changed '+JSON.stringify(detailedRead));
  await page.frameLocator('#gmfq-page').locator('#gmfq-pair-rank .gmfq-rank-method-detail>summary').press('Enter');
  const methodExpanded=await readRank();
  if(methodExpanded.methodClosed)
    throw Error(label+' disclosed pair ordering method cannot be opened');
  await page.frameLocator('#gmfq-page').locator('#gmfq-pair-rank .gmfq-rank-method-detail>summary').press('Enter');
  await page.frameLocator('#gmfq-page').locator('#gmfq-pair-rank button[data-pair-reading="compact"]').click();
  const compactRestored=await readRank();
  if(compactRestored.readingMode!=='compact'||compactRestored.rowReading!=='compact'||
     !compactRestored.methodClosed||compactRestored.readingSample.lensDisplay!=='none'||
     compactRestored.readingSample.checkDisplay!=='none')
    throw Error(label+' pair concise first reading not restored '+JSON.stringify(compactRestored));
  // 8-row currency recurrence is a transparent watchlist warning,
  // calculated from exact source pair legs, not a portfolio risk score.
  const verifyOverlap=(state)=>{
    const first8=state.descriptions.slice(0,8),frequency=Object.fromEntries(g8.map(c=>[c,0]));
    const favored=Object.fromEntries(g8.map(c=>[c,0]));
    for(const row of first8){
      const a=row.code.slice(0,3),b=row.code.slice(3);
      frequency[a]++;frequency[b]++;
      const fav=setupFeed.pairs[row.code].setup.structuralFav;
      if(fav)favored[fav]++;
    }
    const m=Math.max(...Object.values(frequency));
    const tied=Object.keys(frequency).filter(c=>frequency[c]===m).sort();
    const overlap=state.overlap;
    if(overlap.status!=='OBSERVED'||overlap.source!=='PAIR_SETUP_OPERATIONAL_VIEW'||
       overlap.total!=='8'||overlap.max!==String(m)||
       overlap.risks!==String(first8.filter(r=>setupFeed.pairs[r.code].setup.quality==='CON RISCHI').length)||
       overlap.repeated!==tied.join(',')||
       overlap.favored!==tied.map(c=>favored[c]).join(' / ')||
       !overlap.text?.includes('Sovrapposizione valutaria, non correlazione né rischio portafoglio stimati'))
       throw Error(label+' pair top-eight overlap differs from source '+JSON.stringify({state,frequency,favored}));
  };
  verifyOverlap(rankSetup);
  const initialVisible=rankSetup.descriptions.filter(x=>x.visible);
  if(rankSetup.view!=='focus'||rankSetup.visibleCount!==initialVisible.length||
     initialVisible.length<8||initialVisible.length>9||
     rankSetup.descriptions.slice(0,8).some(x=>!x.visible)||
     rankSetup.descriptions.some(x=>x.visible&&x.rank>8&&!x.selected)||
     rankSetup.viewModes.length!==2||
     rankSetup.viewModes[0].pressed!=='true'||rankSetup.viewModes[1].pressed!=='false'||
     !rankSetup.nativeSummary?.includes(initialVisible.length+'/28'))
    throw Error(label+' pair first view not compact or selected pair hidden '+JSON.stringify(rankSetup));
  await page.frameLocator('#gmfq-page').locator('#gmfq-pair-rank button[data-pair-view="all"]').click();
  const expandedPairs=await readRank();
  if(expandedPairs.view!=='all'||expandedPairs.visibleCount!==28||
     expandedPairs.descriptions.some(x=>!x.visible)||expandedPairs.viewModes[1].pressed!=='true')
    throw Error(label+' cannot inspect all 28 original pairs '+JSON.stringify(expandedPairs));
  await page.frameLocator('#gmfq-page').locator('#gmfq-pair-rank button[data-pair-view="focus"]').click();
  const focusAgain=await readRank();
  verifyOverlap(focusAgain);
  if(focusAgain.view!=='focus'||focusAgain.descriptions.filter(x=>x.visible).length!==initialVisible.length)
    throw Error(label+' compact pair first view not restored '+JSON.stringify(focusAgain));
  for(const row of rankSetup.descriptions){
    const p=setupFeed.pairs[row.code],q=p.setup.quality==='NON VALUTABILE';
    const expectedThesis=p.decision_frame.quality==='CONTRASTO STRUTTURALE FORTE'?'Tesi forte':
       p.decision_frame.quality==='VANTAGGIO RELATIVO PARZIALE'?'Tesi parziale':'Senza tesi';
    const expectedPrice=q?'Prezzo non valutabile':
       p.setup.price.state==='GOOD'?'Prezzo conferma':
       p.setup.price.state==='NEUTRAL'?'Prezzo neutro':'Prezzo contrario';
    const expectedTiming=q?'Timing non valutabile':
       ({ALIGNED:'Timing allineato',PARTIAL:'Timing parziale',ADVERSE:'Timing contrario',
         MIXED:'Timing misto',UNCERTAIN:'Timing incerto'})[p.setup.timing.state];
    if(row.lenses!==[expectedThesis,expectedPrice,expectedTiming].join(' · ')||
       row.lensSource!=='PAIR_SETUP_OPERATIONAL_VIEW')
       throw Error(label+' pair three source lenses differ from canonical feed '+JSON.stringify(row));
  }
  // Narrative risk gates are inspection prompts, not new signals.
  const firstChecks=rankSetup.descriptions;
  if(firstChecks.some(x=>x.firstCheck.includes('ingresso immediato')||
       x.firstCheck.includes('stop loss')||!x.firstCheck?.length))
     throw Error(label+' new first checks imply actionable trade levels');
  const audRisk=firstChecks.find(x=>x.code==='AUDCHF'),
        eurRisk=firstChecks.find(x=>x.code==='EURUSD');
  if(!audRisk?.firstCheck||!eurRisk?.firstCheck)
     throw Error(label+' source examples lack a research-check line');

  const rankedCodes=rankSetup.descriptions.map(x=>x.code);
  const unranked=rankedCodes.findIndex(x=>setupFeed.pairs[x].setup.quality==='NON VALUTABILE');
  if(unranked<0||rankedCodes.slice(unranked).some(x=>
      setupFeed.pairs[x].setup.quality!=='NON VALUTABILE'))
    throw Error(label+' pair without a thesis incorrectly outranks canonical thesis');
  // The current live source can remove ADVANCED or ADVERSE from an example.
  // Fail if ANY rendered reason does not match today's canonical conditions,
  // rather than demanding yesterday's risk on a fixed currency pair.
  const sourcedReasons=(p)=>{
    const x=p.setup||{},f=p.decision_frame||{};
    if(x.quality==='NON VALUTABILE')return [
      f.quality==='PILASTRI DIVISI'?'Macro e Tassi/CB in conflitto':
      f.quality==='SEPARAZIONE RATES MATERIALE'?'Solo spread 2Y; tesi assente':
      'Nessuna preferenza Macro/Tassi'];
    const out=[];
    if(x.price?.state==='BAD')out.push('Prezzo contro la tesi');
    else if(x.price?.state==='NEUTRAL')out.push('Prezzo non conferma');
    if(x.timing?.state==='ADVERSE')out.push('Timing contrario');
    if(['ADVANCED','EXTENDED'].includes(x.extension?.state))out.push('Prezzo già avanzato');
    if(p.transition?.state==='DIVERGENZA RELATIVA DA MONITORARE')
      out.push('Dinamica relativa divergente');
    if(x.timing?.state==='UNCERTAIN')out.push('Timing incerto');
    if(x.timing?.state==='MIXED')out.push('Timing misto');
    if(x.timing?.state==='PARTIAL')out.push('Timing solo parziale');
    if(x.cot?.state==='HIGH')out.push('COT affollato/estremo');
    if(x.cot?.state==='DIVERGENT')out.push('COT contrario');
    if(x.liquidity?.state==='BAD')out.push('Liquidità sfavorevole');
    if(f.quality==='VANTAGGIO RELATIVO PARZIALE')
      out.push('Tesi sorretta da un solo pilastro');
    return out.length?out:['Servono trigger e rapporto rischio/rendimento esterni al modello'];
  };
  for(const row of rankSetup.descriptions){
    const item=setupFeed.pairs[row.code];
    const expected=sourcedReasons(item).slice(0,2).join(' · ');
    const favored=item.setup.quality==='NON VALUTABILE'?'Nessuna direzione · ':
      'Favore '+item.setup.structuralFav+' · ';
    if(row.why!==favored+expected)
      throw Error(label+' risk explanation is not tied to current source state: '+
        row.code+' expected '+favored+expected+' received '+row.why);
  }
  if(!rankSetup.descriptions.some(x=>
      setupFeed.pairs[x.code]?.setup?.quality==='CON RISCHI'&&x.why?.length>5))
    throw Error(label+' current canonical risk has no explanatory text');
  await page.frameLocator('#gmfq-page').locator('#gmfq-pair-rank button[data-rank-mode="thesis"]').click();
  const rankThesis=await readRank();
  verifyOverlap(rankThesis);
  if(rankThesis.readingMode!=='compact'||rankThesis.readingSample.checkDisplay!=='none')
    throw Error(label+' changing sort unexpectedly expands pair row details');
  // The winner changes with daily fixing: independently construct the
  // canonical thesis priority tuple from the current source, not yesterday's
  // USDCHF/AUDCHF winner. The unit test separately audits the sorter itself.
  const thesisKey=code=>{
    const p=setupFeed.pairs[code],x=p.setup;
    return [Number(x.quality!=='NON VALUTABILE'),
      p.decision_frame.quality==='CONTRASTO STRUTTURALE FORTE'?3:
        p.decision_frame.quality==='VANTAGGIO RELATIVO PARZIALE'?2:0,
      p.transition?.state==='DINAMICA RELATIVA ALLINEATA'?2:
        p.transition?.state==='NESSUNA DIVERGENZA RELATIVA CHIARA'?1:0,
      ({GOOD:2,NEUTRAL:1,BAD:0})[x.price?.state]??0,
      ({ALIGNED:4,PARTIAL:3,MIXED:2,UNCERTAIN:1,ADVERSE:0})[x.timing?.state]??-1,
      x.extension?.state==='NORMAL'?1:0,
      ({GOOD:2,NEUTRAL:1,BAD:0})[x.liquidity?.state]??0,
      ({MEDIUM:3,CONTEXT:2,HIGH:1,DIVERGENT:0})[x.cot?.state]??0];
  };
  const expectedThesisCodes=Object.keys(setupFeed.pairs).sort((a,b)=>{
    const aa=thesisKey(a),bb=thesisKey(b);
    for(let i=0;i<aa.length;i++)if(aa[i]!==bb[i])return bb[i]-aa[i];
    return a.localeCompare(b);
  });
  if(rankThesis.mode!=='thesis'||rankThesis.view!=='focus'||
     rankThesis.descriptions.slice(0,8).some(x=>!x.visible)||
     rankThesis.descriptions.length!==28||
     rankThesis.modes[1]?.pressed!=='true'||
     rankThesis.descriptions.some((x,i)=>x.rank!==i+1||x.mode!=='thesis')||
     JSON.stringify(rankThesis.descriptions.map(x=>x.code))!==JSON.stringify(expectedThesisCodes))
    throw Error(label+' strength-of-thesis order failed '+JSON.stringify(rankThesis));
  await page.frameLocator('#gmfq-page').locator('#gmfq-pair-rank button[data-rank-mode="setup"]').click();
  await page.frameLocator('#gmfq-page').locator('#pair-search').fill('USDCHF');
  await page.waitForFunction(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument,
      x=d?.querySelectorAll('#pair-index tr[data-research-rank]')||[];
    return x.length===1&&x[0].querySelector('button.pair-open')?.dataset.pair==='USDCHF';
  },null,{timeout:20000});
  const filteredRank=await readRank();
  if(filteredRank.descriptions.length!==1||!filteredRank.descriptions[0].visible||
     filteredRank.visibleCount!==1||
     filteredRank.descriptions[0].rank!==rankedCodes.indexOf('USDCHF')+1)
    throw Error(label+' native pair search loses rank or source label '+JSON.stringify(filteredRank));
  await page.frameLocator('#gmfq-page').locator('#pair-search').fill('');
  await page.waitForFunction(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    return d?.querySelectorAll('#pair-index tr[data-research-rank]').length===28;
  },null,{timeout:20000});
  const restoredPairRank=await readRank();
  if(JSON.stringify(restoredPairRank.descriptions.map(x=>x.code))!==JSON.stringify(rankedCodes))
    throw Error(label+' native pair search/reset broke comparative ordering');
  console.log('CONTROL_ROOM_PAIR_28_DUAL_RANKING_GREEN',label,{
    firstSetup:rankedCodes[0],firstThesis:rankThesis.descriptions[0]?.code});
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
  await page.frameLocator('#gmfq-page').locator('#gmfq-pair-rank button[data-pair-view="all"]').click();
  await page.frameLocator('#gmfq-page').locator('#pair-index button.pair-open[data-pair="EURCHF"]').click();
  await page.waitForFunction(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    return d?.getElementById('gmfq-pair-research-path')?.dataset.pair==='EURCHF';
  },null,{timeout:12000});
  await page.frameLocator('#gmfq-page').locator('#gmfq-pair-rank button[data-pair-view="focus"]').click();
  const selectedCompact=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page').contentDocument,p=d.getElementById('gmfq-pair-rank'),
      row=d.querySelector('#pair-index tr.pair-current button.pair-open[data-pair="EURCHF"]');
    return {view:p?.dataset.viewMode,visible:!!row?.getClientRects().length};
  });
  if(selectedCompact.view!=='focus'||!selectedCompact.visible)
    throw Error(label+' selected deep-linked EURCHF hidden by compact view '+JSON.stringify(selectedCompact));
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
  await page.frameLocator('#gmfq-page').locator('#gmfq-pair-rank button[data-pair-view="all"]').click();
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

  // Compare the actual common-date 2Y spreads and ECB EUR/USD fixing.
  // Rounded display values cannot resolve a borderline raw threshold;
  // this remains descriptive consistency, not event-study causality.
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
     (['ADVANCED','EXTENDED'].includes(setupFeed.pairs.EURUSD.setup.extension.state)
        ?!eurChecklist.rows[2].includes('Estensione del prezzo:')
        :eurChecklist.rows[2].includes('Estensione del prezzo:'))||
     !eurChecklist.rows[2].includes('Timing:')||
     !eurChecklist.rows[2].includes('Posizionamento:')||
     !eurChecklist.text.includes('Solo uno dei due pilastri strutturali separa chiaramente le valute')||
     !eurChecklist.text.includes('Nessun trigger numerico o livello tecnico viene derivato automaticamente')||
     eurChecklist.width>eurChecklist.viewport+16)
    throw Error(label+' EURUSD next evidence checklist must expose canonical setup blockers not market-derived entry '+JSON.stringify(eurChecklist));

  // AUD / CAD are individually certified but published on different dates.
  // Never combine their most recent independent spot yields into a 2Y spread.
  await page.frameLocator('#gmfq-page').locator('#gmfq-pair-rank button[data-pair-view="all"]').click();
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

  await page.frameLocator('#gmfq-page').locator('#gmfq-pair-rank button[data-pair-view="all"]').click();
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

  await page.frameLocator('#gmfq-page').locator('#gmfq-pair-rank button[data-pair-view="all"]').click();
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

  await page.frameLocator('#gmfq-page').locator('#gmfq-pair-rank button[data-pair-view="all"]').click();
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
      study:p?.querySelector('.gmfq-cross-coverage')?.textContent,
      references:p?.dataset.studyReferences,official:p?.dataset.studyOfficial,
      secondary:p?.dataset.studySecondary,effect:p?.dataset.studyEffect,
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
  if(risk.references!=='4'||risk.official!=='2'||risk.secondary!=='2'||risk.effect!=='NONE'||
    !risk.study?.includes('4/4 riferimenti numerici per lo studio')||
    risk.cards.length!==3||!risk.lead?.startsWith('VIX misura volatilità implicita')||
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
