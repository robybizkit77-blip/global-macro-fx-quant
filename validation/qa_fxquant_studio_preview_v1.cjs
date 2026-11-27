'use strict';
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  for(const width of [1440,390]){
   const page=await browser.newPage({viewport:{width,height:900}});
   const errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.goto('http://127.0.0.1:8765/site/fx-quant-v2/studio/');
   await page.waitForFunction(()=>!document.getElementById('refresh').disabled,{},{timeout:40000});
   const status=await page.locator('#source-state').innerText();
   assert.match(status,/11\/11 feed letti/,'Actual repository feeds must load: '+status);
   assert.match(status,/motore FX disponibile/,'Existing FX engine must evaluate: '+status);
   for(const route of ['Control Room','Macro','Tassi','Forex','Cross-Asset','Calendario','Report']){
    await page.locator('#nav button').getByText(route,{exact:true}).click();
    assert(await page.locator('#view h1').count(),route+' has no title');
    assert(await page.locator('#view').innerText().then(t=>t.length>100),route+' empty');
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1),route+' horizontal page overflow at '+width);
    assert.doesNotMatch(await page.locator('#view').innerText(),/\bNaN\b|\bundefined\b/);
   }
   await page.locator('#nav button').getByText('Forex',{exact:true}).click();
   await page.getByRole('button',{name:'28 coppie',exact:true}).click();
   assert.equal(await page.locator('.pairrow').count(),28);
   await page.getByLabel('Valuta base').selectOption('GBP');
   await page.getByLabel('Controvaluta').selectOption('JPY');
   assert.match(await page.locator('#view').innerText(),/GBP\/JPY/);
   assert.equal(errors.length,0,errors.join('\n'));
   await page.route('**/ECB_G8_PRICE_HISTORY.json',route=>route.abort());
   await page.locator('#refresh').click();
   await page.waitForFunction(()=>!document.getElementById('refresh').disabled,{},{timeout:40000});
   assert.match(await page.locator('#source-state').innerText(),/10\/11 feed letti.*motore FX non disponibile.*prices/);
   assert.equal(errors.length,0,errors.join('\n'));
   console.log('STUDIO_PREVIEW_REAL_FEEDS_NAVIGATION_FALLBACK_PASS',width);
   await page.close();
  }
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
