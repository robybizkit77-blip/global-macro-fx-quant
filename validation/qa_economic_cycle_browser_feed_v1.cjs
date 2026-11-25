'use strict';
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
const model=require('../site/fx-quant-v2/next/recession-traffic-light-v1.js');
const BASE=process.env.SEMAPHORE_BASE||'http://127.0.0.1:8000/site/fx-quant-v2/next/';
const endpoint='**/semaphore-supplement-v1.json*';
const monitor='.recession-light';
async function coverage(page){
 return Number(await page.locator(monitor).getAttribute('data-semaphore-coverage'));
}
async function expected(page){
 const raw=await page.evaluate(async()=>{
  const [c,o]=await Promise.all([fetch('../../../live_data/sections/MACRO_SERIES.json',{cache:'no-store'}),fetch('./semaphore-supplement-v1.json',{cache:'no-store'})]);
  if(!c.ok||!o.ok)throw Error('Required economic source HTTP failure');
  return {catalog:await c.json(),overlay:await o.json(),day:new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Rome',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date())};
 });
 const calc=overlay=>model.coverage.flatMap(c=>model.model(raw.catalog,raw.day,c,overlay)).filter(x=>x.signal.tone!=='neutral').length;
 const full=calc(raw.overlay),base=calc(null);
 assert(full>base,'Supplement must add actual browser coverage');
 if(raw.overlay.as_of==='2026-11-25'&&raw.day==='2026-11-25')assert.equal(full,56);
 return {full,base,day:raw.day,as_of:raw.overlay.as_of};
}
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:900}});
  let attempts=0;
  if(!process.env.SEMAPHORE_PUBLIC)await page.route(endpoint,async route=>{
   if(++attempts===1)return route.abort('failed');
   return route.continue();
  });
  await page.goto(BASE+'#macro',{waitUntil:'domcontentloaded',timeout:45000});
  await page.waitForSelector(monitor+'[data-semaphore-feed="network"]',{timeout:70000});
  if(!process.env.SEMAPHORE_PUBLIC)assert(attempts>=2,'Transient source failure did not retry');
  await page.unroute(endpoint);
  const proof=await expected(page);
  assert.equal(await coverage(page),proof.full,'Rendered coverage must match model with the actual source');
  const progress=await page.locator(monitor+' [role="progressbar"][aria-label="Copertura G8"]').getAttribute('aria-valuenow');
  assert.equal(Number(progress),proof.full);
  console.log('ECONOMIC_CYCLE_BROWSER_PASS',JSON.stringify({...proof,rendered:await coverage(page),attempts,public:!!process.env.SEMAPHORE_PUBLIC}));
  if(await page.locator('[data-rd-layout="approved-preview"]').count()){
   const assertLayout=async p=>{
    for(const sel of ['.rd-global','.rd-insights','.rd-matrix-wrap','#rd-country .rd-country-body','.rd-metrics'])assert(await p.locator(sel).isVisible(),sel+' must be visible');
    assert.equal(await p.locator('.rd-matrix-wrap tbody tr').count(),8);
    assert.equal(await p.locator('.rd-matrix-wrap tbody .rd-cell').count(),56);
    assert.equal(await p.locator('.rd-country-tabs button').count(),8);
    assert.equal(await p.locator('.rd-metrics .rd-metric').count(),4);
    assert.equal(await p.locator('.macro-research').isVisible(),false);
    assert.equal(await p.locator('.rd-detail').evaluate(el=>el.open),false);
    const order=await p.evaluate(()=>['.rd-global','.rd-insights','.rd-matrix-wrap','#rd-country'].map(s=>document.querySelector(s).getBoundingClientRect().top));
    assert(order.every((v,i)=>!i||v>order[i-1]),'Approved reading order: global, drivers, matrix, country');
    assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2),'Page horizontal overflow');
    assert(await p.locator('#nav [data-route="macro"]').getAttribute('aria-current')==='page');
    assert.equal(await p.locator('.rd-root').evaluate(el=>getComputedStyle(el).fontFamily),await p.locator('#content').evaluate(el=>getComputedStyle(el).fontFamily),'Inherit Next typography');
   };
   await assertLayout(page);
   await page.screenshot({path:'next-approved-macro-desktop.png',fullPage:true});
   for(const ccy of model.coverage){
    await page.locator('.rd-country-tabs [data-ms-country="'+ccy+'"]').click();
    assert.equal(await page.locator('.rd-country-tabs [data-ms-country="'+ccy+'"]').getAttribute('aria-pressed'),'true');
    assert.equal(await coverage(page),proof.full);
   }
   await page.locator('.rd-matrix-wrap [data-ms-country="AUD"]').click();
   assert.equal(await page.locator('.rd-country-tabs [data-ms-country="AUD"]').getAttribute('aria-pressed'),'true');
   await page.locator('#rd-country a[href="#rates"]').click();
   await page.waitForFunction(()=>document.querySelector('#content')?.dataset.view==='rates');
   assert.equal(await page.locator('#rs-country').inputValue(),'AUD');
   await page.locator('#nav [data-route="macro"]').click();
   await page.waitForSelector('[data-rd-layout="approved-preview"]');
   await page.locator('[data-macro-panel="explorer"] > summary').click();
   const categories=page.locator('[data-macro-panel="explorer"] [data-ms-category]');
   if(await categories.count()>1){await categories.nth(1).click();assert.equal(await page.locator('[data-macro-panel="explorer"]').getAttribute('open'),'');}
   const mobile=await browser.newPage({viewport:{width:390,height:844},isMobile:true,deviceScaleFactor:2,hasTouch:true});
   await mobile.goto(BASE+'#macro',{waitUntil:'domcontentloaded',timeout:45000});
   await mobile.waitForSelector(monitor+'[data-semaphore-feed="network"]',{timeout:70000});
   await assertLayout(mobile);
   assert.equal(await coverage(mobile),proof.full);
   await mobile.screenshot({path:'next-approved-macro-mobile.png',fullPage:true});
   await mobile.close();
   console.log('NEXT_MACRO_APPROVED_LAYOUT_PASS desktop/mobile, 56 cells, all countries, rates handoff, explorer persistence');
  }else if(!process.env.SEMAPHORE_PUBLIC){throw Error('Approved macro layout not rendered');}
  if(!process.env.SEMAPHORE_PUBLIC){
   const failed=await browser.newPage();
   let reject=true,failures=0;
   await failed.route(endpoint,async route=>reject?(failures++,route.fulfill({status:503,body:'Unavailable'})):route.continue());
   await failed.goto(BASE+'#macro',{waitUntil:'domcontentloaded',timeout:45000});
   await failed.waitForSelector(monitor+'[data-semaphore-feed="missing"]',{timeout:70000});
   assert.equal(failures,3);
   assert.equal(await coverage(failed),proof.base);
   assert.match(await failed.locator(monitor+' [role="status"]').innerText(),/Copertura parziale/);
   reject=false;
   await failed.locator('[data-sem-feed-retry]').click();
   await failed.waitForSelector(monitor+'[data-semaphore-feed="network"]',{timeout:70000});
   assert.equal(await coverage(failed),proof.full);
   console.log('ECONOMIC_CYCLE_BROWSER_FAILURE_RECOVERY_PASS',JSON.stringify({failed:proof.base,recovered:proof.full}));
   await failed.close();
  }
  await page.close();
 }finally{await browser.close()}
})().catch(e=>{console.error(e.stack||e);process.exit(1)});
