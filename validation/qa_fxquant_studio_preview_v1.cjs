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
   // Test actual canonical content, not just presence of an iframe or links.
   await page.getByRole('button',{name:'COT',exact:true}).click();
   let embedded=page.frameLocator('#studio-research-frame');
   await embedded.locator('.cot-rank-table').waitFor({timeout:45000});
   assert(await embedded.locator('.cot-rank-table tbody tr').count()>=8,'COT G8 ranking table missing');
   assert.match(await embedded.locator('.cot-rank-table').innerText(),/Net|Percentile/i);
   await page.locator('#nav button').getByText('Tassi',{exact:true}).click();
   embedded=page.frameLocator('#studio-research-frame');
   await embedded.locator('#rates-expected').waitFor({timeout:45000});
   assert.equal(await embedded.locator('#rates-expected #rates-pricing-history, #rates-expected #rates-pricing-moves').count(),2);
   await embedded.locator('#rates-government').waitFor();
   await page.locator('#nav button').getByText('Macro',{exact:true}).click();
   await page.locator('[data-research-tab="macro"]').click();
   embedded=page.frameLocator('#studio-research-frame');
   await embedded.locator('.rd-country-tabs').waitFor({timeout:45000});
   assert.equal(await embedded.locator('.rd-country-tabs [data-ms-country]').count(),8);
   await page.locator('#nav button').getByText('Cross-Asset',{exact:true}).click();
   await page.locator('[data-research-tab="liquidity"]').click();
   embedded=page.frameLocator('#studio-research-frame');
   await embedded.locator('#liquidity-charts').waitFor({timeout:45000});
   assert(await embedded.locator('#liquidity-charts .drivers-chart').count()>=2);
   assert.equal(errors.length,0,errors.join('\n'));
   await page.locator('#nav button').getByText('Control Room',{exact:true}).click();
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
