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
  await page.screenshot({path:'v10-qa-images/'+label+'-rates-g8-detail.png',fullPage:true});
  console.log('CONTROL_ROOM_PREVIEW_G8_DETAIL_FOCUS_GREEN',label,JSON.stringify(ratesDetail));
  await page.close();
 }
 await browser.close();
 console.log('CONTROL_ROOM_V10_VISUAL_NAV_DXY_G8_PASS');
})().catch(e=>{console.error(e);process.exit(1)});
