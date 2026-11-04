'use strict';
/* Visual and factual contract for standalone Home V6; operational Home unchanged. */
const {chromium}=require('playwright');
const fs=require('node:fs');const path=require('node:path');
const base=(process.env.FXV2_BASE||'http://127.0.0.1:8000/site/fx-quant-v2').replace(/\/+$/,'');
const output='fxv2-browser-evidence';fs.mkdirSync(output,{recursive:true});
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  for(const [name,width,height] of [['desktop',1440,900],['mobile',390,844]]){
   const page=await browser.newPage({viewport:{width,height},deviceScaleFactor:1,reducedMotion:'reduce'});
   const exceptions=[];page.on('pageerror',e=>exceptions.push(String(e)));
   const response=await page.goto(base+'/home-semplice-v6.html',{waitUntil:'domcontentloaded',timeout:60000});
   if(response?.status()!==200)throw Error('HTTP '+response?.status());
   await page.locator('#chartRates polyline').first().waitFor({timeout:14000});
   await page.locator('#chartDxy polyline').first().waitFor({timeout:14000});
   await page.waitForFunction(()=>document.querySelector('#status')?.textContent?.includes('BCE'),null,{timeout:14000});
   const result=await page.evaluate(()=>{
    const t=id=>document.getElementById(id)?.textContent?.trim()||'';
    return {
     head:t('headline'),lead:t('lead'),observation:t('observed'),
     meaning:t('meaning'),missing:t('missing'),verdict:t('verdict'),
     status:t('status'),facts:[t('fact2'),t('fact10'),t('factDxy')],
     lineCharts:document.querySelectorAll('#chartRates polyline,#chartDxy polyline').length,
     mainLinks:document.querySelectorAll('.mainnav>a').length,
     moreLinks:document.querySelectorAll('.dropdown a').length,
     storySections:document.querySelectorAll('.storyitem').length,
     overflow:document.documentElement.scrollWidth-innerWidth
    };
   });
   if(result.lineCharts!==3||result.storySections!==3||result.mainLinks!==5||
      result.moreLinks<7||result.overflow>10||result.facts.some(x=>!x||x.includes('—'))||
      !result.observation.includes('Treasury 2Y')||!result.observation.includes('DXY')||
      !result.meaning.includes('OIS')||!result.missing.includes('date')||
      !result.verdict||exceptions.length)throw Error(name+': '+JSON.stringify({...result,exceptions}));
   await page.locator('.more summary').click();
   await page.locator('.dropdown a').first().waitFor({state:'visible',timeout:5000});
   await page.locator('.more summary').click();
   await page.screenshot({path:path.join(output,'home-simple-v6-'+name+'.png'),fullPage:true,animations:'disabled'});
   console.log('FXV2_HOME_SIMPLE_V6 '+name+' PASS '+JSON.stringify(result));
   await page.close();
  }
  console.log('FXV2_HOME_SIMPLE_V6_DESKTOP_MOBILE_PASS');
 }finally{await browser.close();}
})().catch(e=>{console.error('FXV2_HOME_SIMPLE_V6_FAIL',e);process.exitCode=1;});
