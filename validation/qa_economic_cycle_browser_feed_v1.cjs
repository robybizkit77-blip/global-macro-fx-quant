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
