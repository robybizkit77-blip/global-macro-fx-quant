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
const setupFeed=JSON.parse(fs.readFileSync(path.join(DATA,'PAIR_SETUP_OPERATIONAL_VIEW.json'),'utf8'));
const operational=JSON.parse(fs.readFileSync(path.join(DATA,'OIS_OPERATIONAL_VIEW.json'),'utf8'));
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
 const now=new Date();
 const gap=(Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),now.getUTCDate())-Date.parse(row.date+'T00:00:00Z'))/86400000;
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
  await page.waitForFunction(()=>{
    const d=document.getElementById('gmfq-page')?.contentDocument;
    return d?.querySelectorAll('#gmfq-source-readiness .gmfq-source-row').length===4&&
           d?.querySelectorAll('#gmfq-source-readiness .gmfq-source-link a').length===4;
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
  if(research.fourCurves!==4||research.secondary!==expectedSecondaryQuotes||
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
     reasons.baseline!==setupFeed.macro_baseline_asof||
     !reasons.descriptive||reasons.innerScroll>reasons.innerClient+2||
     reasons.width>Math.max(reasons.viewport+16,reasons.nativeWidth+2))
    throw Error(label+' screener reason contract failed '+JSON.stringify(reasons));
  await page.screenshot({path:'v10-qa-images/'+label+'-screener-reasons.png',fullPage:true});
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
      disclaimer:c?.querySelector('.gmfq-change-warning')?.textContent};
  });
  if(!deltaCHF.exists||deltaCHF.legs.length!==2||
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
    return {text:c?.textContent,legs:[...c?.querySelectorAll('.gmfq-change-leg')||[]].map(x=>({
      ccy:x.dataset.gmfqChangeCurrency,status:x.dataset.gmfqYieldChange,
      actual:x.querySelector('.gmfq-change-measured')?.textContent,model:x.querySelector('.gmfq-change-model')?.textContent}))};
  });
  const eu=deltaEURUSD.legs.find(x=>x.ccy==='EUR'),us=deltaEURUSD.legs.find(x=>x.ccy==='USD');
  if(eu?.status!=='MEASURED'||us?.status!=='MEASURED'||
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
      text:panel?.textContent,viewport:doc?.documentElement.clientWidth,
      width:doc?.documentElement.scrollWidth,legacy:!!doc?.querySelector('[data-gmfq-operational="risk"]')};
  });
  const goldFixture=JSON.parse(fs.readFileSync(path.join(DATA,'ESTIMATED_RESIDUAL_GAPS.json'),'utf8'))
    .lanes['GOLD.market_proxy'];
  const goldQuote=Number(goldFixture.value).toLocaleString('it-IT',
    {minimumFractionDigits:2,maximumFractionDigits:2});
  if(!['SECONDARY_CURRENT','SECONDARY_HISTORICAL'].includes(gold.state)||
     gold.asof!==goldFixture.proxy_as_of||!gold.value?.includes(goldQuote)||
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
  if(risk.cards.length!==3||!risk.text.includes('Brent spot ufficiale: WITHHELD')||
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
