'use strict';
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
const engine=require('../site/fx-quant-v2/next/recession-traffic-light-v1.js');
const catalog=require('../live_data/sections/MACRO_SERIES.json');
const overlay=require('../site/fx-quant-v2/next/semaphore-supplement-v1.json');
const day=new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Rome',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
const calc=o=>engine.coverage.flatMap(c=>engine.model(catalog,day,c,o)).filter(x=>x.signal.tone!=='neutral').length;
const base=process.env.RESEARCH_BASE||'http://127.0.0.1:8000/site/fx-quant-v2/research/';
(async()=>{const browser=await chromium.launch({headless:true});try{
 for(const [name,viewport] of [['desktop',{width:1440,height:1000}],['mobile',{width:390,height:844}]]){
  const page=await browser.newPage({viewport,deviceScaleFactor:1});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base,{waitUntil:'domcontentloaded'});await page.waitForSelector('#coverage',{timeout:70000});
  assert.equal(Number(await page.locator('#coverage').getAttribute('data-covered')),calc(overlay));
  assert.equal(await page.locator('tbody tr').count(),8);assert.equal(await page.locator('tbody .cell').count(),56);
  assert.equal(await page.locator('.country-tabs button').count(),8);
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2),'Page overflow: '+name);
  assert.equal(await page.locator('#notice').isVisible(),false);
  await page.screenshot({path:'research-'+name+'.png',fullPage:true});
  for(const c of engine.coverage){await page.locator('.country-tabs [data-country="'+c+'"]').click();assert.equal(await page.locator('.country-tabs [data-country="'+c+'"]').getAttribute('aria-pressed'),'true');const reading=page.locator('.country-body');for(const heading of ['Cosa va','Cosa frena','Cosa guardare'])assert(await reading.getByText(heading,{exact:true}).isVisible());assert.equal(await reading.locator('.lead').count(),2);assert.equal(await page.locator('.metrics .metric').count(),4)}
  assert.deepEqual(errors,[]);await page.close();
 }
 const failure=await browser.newPage();let fail=true;await failure.route('**/semaphore-supplement-v1.json*',r=>fail?r.fulfill({status:503,body:'unavailable'}):r.continue());
 await failure.goto(base);await failure.waitForSelector('#coverage',{timeout:70000});assert.equal(Number(await failure.locator('#coverage').getAttribute('data-covered')),calc(null));assert(await failure.locator('#notice').isVisible());fail=false;await failure.locator('#notice button').click();await failure.waitForFunction(n=>Number(document.querySelector('#coverage')?.dataset.covered)===n,calc(overlay));await failure.close();
 console.log('RESEARCH_REBUILD_PASS',JSON.stringify({day,coverage:calc(overlay),baseline:calc(null),countries:8,matrix:56,desktop:true,mobile:true,fallback:true}));
 }finally{await browser.close()}})().catch(e=>{console.error(e.stack||e);process.exit(1)});
