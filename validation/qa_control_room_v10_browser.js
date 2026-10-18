/* Browser contract for v10. All feeds are locally intercepted fixture copies from repo. */
'use strict';
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path');
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
  if(!/101\.71/.test(r.dxy||''))fatal.push('DXY synthetic not visible');
  if(!r.noApprofondisci)fatal.push('old overlay link still shown');
  if(r.rateSeries.length!==8)fatal.push('missing G8 yield lines');
  if(r.oisCount!==8||!r.nzdbb?.includes('3.83'))fatal.push('NZD proxy missing');
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
  await page.close();
 }
 await browser.close();
 console.log('CONTROL_ROOM_V10_VISUAL_NAV_DXY_G8_PASS');
})().catch(e=>{console.error(e);process.exit(1)});
