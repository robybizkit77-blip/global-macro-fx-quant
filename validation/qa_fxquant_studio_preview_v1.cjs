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
   assert.match(await page.locator('#studio-research .plain-reading').innerText(),/Da seguire:/);
   // Native components only: no embedded legacy pages or DOM reuse.
   assert.equal(await page.locator('iframe').count(),0);
   await page.getByRole('button',{name:'COT',exact:true}).click();
   await page.locator('.native-cot-table').waitFor({timeout:45000});
   assert.equal(await page.locator('.native-cot-table tbody tr').count(),8);
   assert.match(await page.locator('#studio-research .plain-reading').innerText(),/I fondi|Il netto/);
   assert.match(await page.locator('.native-cot-table').innerText(),/P104.*Z104/s);
   assert.equal(await page.locator('.native-cot-table tbody tr td:nth-child(8)').evaluateAll(cells=>cells.filter(c=>/^\d+$/.test(c.textContent.trim())).length),8);
   await page.getByRole('button',{name:'Long / Short',exact:true}).click();
   assert(await page.locator('#studio-research .native-chart svg').count()>=2);
   await page.locator('#nav button').getByText('Tassi',{exact:true}).click();
   await page.locator('.native-curve-card').first().waitFor({timeout:45000});
   assert.equal(await page.locator('.native-curve-card').count(),8);
   assert.equal(await page.locator('.native-curve-card svg').count(),8);
   await page.locator('.native-curve-card').filter({hasText:'GBP'}).click();
   assert.match(await page.locator('#studio-research').innerText(),/GBP · curva e repricing/);
   assert.equal(await page.locator('#studio-research .plain-reading').count(),3);
   assert.match(await page.locator('#studio-research .plain-reading').first().innerText(),/tassi attesi|aspettative|Aspettative/);
   await page.locator('#nav button').getByText('Macro',{exact:true}).click();
   await page.getByLabel('Indicatore macro').waitFor();
   assert(await page.getByLabel('Indicatore macro').locator('option').count()>10);
   const originalReading=await page.locator('#studio-research .plain-reading').innerText();
   await page.getByLabel('Indicatore macro').selectOption({index:1});
   assert.notEqual(await page.locator('#studio-research .plain-reading').innerText(),originalReading);
   assert(await page.locator('#studio-research svg').count()>0);
   await page.locator('#nav button').getByText('Cross-Asset',{exact:true}).click();
   assert(await page.locator('#studio-research svg').count()>=2);
   await page.getByRole('button',{name:'VIX',exact:true}).click();
   assert.match(await page.locator('#studio-research .plain-reading').innerText(),/Volatilità/);
   await page.locator('#nav button').getByText('Report',{exact:true}).click();
   assert(await page.locator('a[href*="/reports/"][href$=".html"]').count()>=8);
   assert.equal(await page.locator('iframe').count(),0);
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
