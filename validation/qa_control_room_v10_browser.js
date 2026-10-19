/* Browser contract for v10. All feeds are locally intercepted fixture copies from repo. */
'use strict';
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path');
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
const snbSpot=JSON.parse(fs.readFileSync(path.join(DATA,'CHF_SNB_10Y_SPOT_CONTEXT.json'),'utf8'));
if(snbSpot.tenor!=='10Y'||snbSpot.has_current_2y!==false||snbSpot.eligible_for_curve_spreads!==false)throw Error('Invalid independent SNB 10Y context fixture');
function commonAnchorDate(target,proxy,tenor='history2'){
 const dates=new Set(ratesFeed[proxy][tenor].dates);
 return ratesFeed[target][tenor].dates.filter(d=>d<=ratesFeed[target].date&&dates.has(d)).at(-1);
}
function recentOfficialRate(row){
 if(!row||!String(row.quality||'').includes('OFFICIAL')||!/^\d{4}-\d{2}-\d{2}$/.test(row.date||''))return false;
 const now=new Date();
 const gap=(Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),now.getUTCDate())-Date.parse(row.date+'T00:00:00Z'))/86400000;
 return gap>=0&&gap<=4;
}
const chfAnchor=commonAnchorDate('CHF','EUR');
const nzdAnchor=commonAnchorDate('NZD','AUD');
const nzdOfficial=recentOfficialRate(ratesFeed.NZD);
if(!chfAnchor||(!nzdOfficial&&!nzdAnchor))throw Error('Missing common official rates estimation anchors');
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
    const diff=(Date.UTC(new Date().getUTCFullYear(),new Date().getUTCMonth(),new Date().getUTCDate())-
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
  if(homeAudit.role!=='button'||!homeAudit.stamp?.includes('OIS '+certified+'/8')||
     !(expectedFx?homeAudit.stamp.includes('FX '+fxData.last_as_of.slice(8,10)+'/'+fxData.last_as_of.slice(5,7)):
       homeAudit.stamp.includes('FX non corr.'))||
     (certified<8&&homeAudit.label!=='DATI PARZIALI')||
     !homeAudit.source?.includes('Non è DXY ICE ufficiale')||
     !homeAudit.source?.includes('futures monetari, non OIS puri')||
     homeAudit.documentWidth>homeAudit.viewport+16)
    throw Error(label+' incorrect Home source freshness display '+JSON.stringify(homeAudit));
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
  const expectedEstimates=nzdOfficial?1:2;
  if(r.rateBarTexts.filter(x=>x.endsWith('*')).length<expectedEstimates||!r.rateBarNote.includes('STIMA'))
    fatal.push('Missing or unlabelled model estimate for non-current G8 yields');
  if(!r.rateBarNote.includes('base '+chfAnchor)||
     (!nzdOfficial&&!r.rateBarNote.includes('base '+nzdAnchor)))
    fatal.push('Model estimates are not anchored at a same-date official pair: '+r.rateBarNote);
  if(nzdOfficial&&(r.rateBarNote.includes('NZD/AUD')||
       !r.rateBarTexts.includes('NZD')||r.rateBarTexts.includes(Number(ratesFeed.NZD['2Y']).toFixed(2)+'*')))
    fatal.push('Certified NZD yield incorrectly shown as an estimate');
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
  const research=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument,host=d?.getElementById('gmfq-pricing-research');
    return {
      fourCurves:host?.querySelectorAll('svg polyline').length,
      secondary:host?.querySelectorAll('.gmfq-quote-card').length,
      legend:host?.querySelector('.gmfq-research-legend')?.innerText,
      disclaimers:host?.innerText,
      snbSpot:host?.querySelector('#gmfq-chf-snb-10y-context')?.innerText,
      sourceCount:host?.querySelectorAll('#gmfq-source-readiness .gmfq-source-row').length,
      sourceLinks:host?.querySelectorAll('#gmfq-source-readiness .gmfq-source-link a').length,
      sourceCurrencies:[...host?.querySelectorAll('#gmfq-source-readiness .gmfq-source-row b')||[]].map(x=>x.textContent),
      sourceDoc:host?.querySelector('#gmfq-source-readiness')?.textContent,
      chartWidth:host?.querySelector('.gmfq-research-plot')?.scrollWidth,
      docWidth:d?.documentElement.scrollWidth,viewport:d?.documentElement.clientWidth
    };
  });
  if(research.fourCurves!==4||research.secondary!==3||
     !research.legend.includes('GBP')||!research.legend.includes('CAD')||
     !research.disclaimers.includes('NON curva OIS')&&
      !research.disclaimers.includes('non sono una curva OIS')||
     !research.disclaimers.includes('NON curva OIS né policy delta')||
     !research.disclaimers.includes('CHF 2Y/10Y')||
     !research.snbSpot?.includes('CHF 10Y SNB '+Number(snbSpot.value_percent).toFixed(3)+'%')||
     !research.snbSpot.includes(snbSpot.as_of)||!research.snbSpot.includes('SOLO INFORMATIVO')||
     !research.snbSpot.includes('nessuno spread o segnale')||
     research.sourceCount!==4||research.sourceLinks!==4||
     !['USD','EUR','CHF','NZD'].every(c=>research.sourceCurrencies.some(x=>x.includes(c)))||
     !research.sourceDoc.includes('non completa il 2Y')||
     !research.sourceDoc.includes('Nessun dato indicativo è promosso')||
     research.docWidth>research.viewport+16)
     throw Error(label+' Pricing research traceability failed: '+JSON.stringify(research));
  await page.frameLocator('#gmfq-page').locator('#gmfq-pricing-research button[data-pricing-ccy="GBP"]').click();
  const selectedCurveCount=await page.frameLocator('#gmfq-page').locator('#gmfq-pricing-research svg polyline').count();
  if(selectedCurveCount!==1)throw Error(label+' single bank curve filter failed');
  await page.frameLocator('#gmfq-page').locator('#gmfq-pricing-research button[data-pricing-ccy="ALL"]').click();
  await page.screenshot({path:'v10-qa-images/'+label+'-rates-g8-detail.png',fullPage:true});

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
      model:panel?.textContent.includes('non aggiorna automaticamente il giudizio del motore'),
      width:d?.documentElement.scrollWidth,viewport:d?.documentElement.clientWidth};
  });
  if(first.count!==28||first.currencies!==2||first.links!==8||
     !first.model||first.width>first.viewport+16)
    throw Error(label+' pair deep-dive route/model-date guard failed '+JSON.stringify(first));
  // Selecting a non-USD cross updates both the original detail and our
  // additive research path; a permalink to the currently selected pair remains.
  await page.frameLocator('#gmfq-page').locator('#pair-index button.pair-open[data-pair="EURCHF"]').click();
  await page.waitForFunction(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    return d?.getElementById('gmfq-pair-research-path')?.dataset.pair==='EURCHF';
  },null,{timeout:12000});
  await page.waitForURL(u=>u.hash==='#/coppie?pair=EURCHF',{timeout:5000});
  const detail=await page.evaluate(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    return {name:d?.querySelector('#pair-detail .desk-kicker')?.textContent,
      text:d?.getElementById('gmfq-pair-research-path')?.textContent,
      g8:d?.querySelectorAll('#pair-index button.pair-open[data-pair]').length,
      width:d?.documentElement.scrollWidth,viewport:d?.documentElement.clientWidth};
  });
  if(!detail.name?.includes('EURCHF')||!detail.text?.includes('ECB')||
    !detail.text?.includes('CHF')||!detail.text?.includes('non aggiorna automaticamente')||
    detail.g8!==28||detail.width>detail.viewport+16)
    throw Error(label+' EURCHF selected-pair research context failed '+JSON.stringify(detail));
  await page.frameLocator('#gmfq-page').locator('#gmfq-pair-research-path button[data-gmfq-study-route="tassi"][data-gmfq-study-currency="CHF"]').click();
  await page.waitForURL(u=>u.hash==='#/tassi?ccy=CHF',{timeout:15000});
  await page.waitForFunction(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    return d?.getElementById('rates-select')?.querySelector('button[data-ccy="CHF"]')?.getAttribute('aria-pressed')==='true';
  },null,{timeout:20000});
  console.log('CONTROL_ROOM_PREVIEW_28_PAIR_RESEARCH_GREEN',label,JSON.stringify({fromHome,selected:'EURCHF',links:first.links,viewport:first.viewport}));

  console.log('CONTROL_ROOM_PREVIEW_G8_DETAIL_FOCUS_GREEN',label,JSON.stringify({ratesDetail,researchSummary:{fourCurves:research.fourCurves,secondary:research.secondary,docWidth:research.docWidth,viewport:research.viewport}}));
  await page.close();
 }
 await browser.close();
 console.log('CONTROL_ROOM_V10_VISUAL_NAV_DXY_G8_PASS');
})().catch(e=>{console.error(e);process.exit(1)});
