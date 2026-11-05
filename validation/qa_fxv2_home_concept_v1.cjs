'use strict';
/* UI-only smoke test: compare isolated Home concept on desktop and mobile.
   The existing site/fx-quant-v2/index.html is not modified or replaced. */
const {chromium}=require('playwright');
const fs=require('node:fs');
const path=require('node:path');
const base=(process.env.FXV2_BASE||'http://127.0.0.1:8000/site/fx-quant-v2').replace(/\/+$/,'');
const output='fxv2-browser-evidence';
fs.mkdirSync(output,{recursive:true});
(async()=>{
 const browser=await chromium.launch({headless:true});
 const errors=[];
 try{
  for(const [label,viewport] of [['desktop',{width:1440,height:900}],['mobile',{width:390,height:844}]]){
   const page=await browser.newPage({viewport,deviceScaleFactor:1,reducedMotion:'reduce'});
   page.on('pageerror',e=>errors.push(label+': '+String(e)));
   const res=await page.goto(base+'/home-concept-global-macro.html',{waitUntil:'domcontentloaded',timeout:60000});
   if(res?.status()!==200)throw Error('Concept HTTP '+res?.status());
   // On mobile the shared site menu is intentionally collapsed by default.
   // Presence is the invariant; verify it becomes visible when explicitly opened.
   await page.locator('#fxv2-nav a').first().waitFor({state:'attached',timeout:15000});
   if(label==='mobile'){
    const toggle=page.locator('#fxv2-global-header .fxv2-toggle');
    await toggle.click();
    await page.locator('#fxv2-nav a').first().waitFor({state:'visible',timeout:5000});
    await toggle.click();
   }
   await page.locator('#dxyChart polyline').first().waitFor({timeout:14000});
   await page.locator('#ratesChart polyline').first().waitFor({timeout:14000});
   const result=await page.evaluate(()=>{
    const $=s=>document.querySelector(s);
    return {
     nav:document.querySelectorAll('#fxv2-nav a').length,
     hero:$('#heroTitle')?.textContent?.trim(),
     background:!!$('.macro-atmosphere')&&!!$('.hero-overline'),
     deck:document.querySelectorAll('#oggi .brief-section').length,
     editorial:!!$('#briefObserved')&&!!$('#briefMacro')&&!!$('#briefPricing')&&!!$('#briefVerdict'),
     observed:$('#briefObserved')?.textContent,
     macro:$('#briefMacro')?.textContent,
     pricing:$('#briefPricing')?.textContent,
     verdict:$('#briefVerdict')?.textContent,
     asof:$('#briefDates')?.textContent,
     links:document.querySelectorAll('.desk-links a').length,
     rows:document.querySelectorAll('#g8Grid button[data-ccy]').length,
     dxy:document.querySelectorAll('#dxyChart polyline').length,
     rates:document.querySelectorAll('#ratesChart polyline').length,
     ratesCard:$('#briefRates')?.textContent,
     fxCard:$('#briefFX')?.textContent,
     disclaimer:$('#briefFXNote')?.textContent,
     overflow:Math.max(0,document.documentElement.scrollWidth-innerWidth),
     current:document.querySelectorAll('#fxv2-nav a[aria-current="page"]').length,
    };
   });
   if(result.nav!==12||result.current!==1||!result.background||
      result.deck!==3||!result.editorial||result.links<5||result.rows!==8||
      result.dxy!==1||result.rates!==2||result.overflow>10||
      !result.hero||!result.ratesCard?.includes('%')||
      !result.disclaimer?.includes('BCE')||!result.fxCard||
      !result.observed?.includes('Treasury 2Y')||
      !result.observed?.includes('10Y')||
      !result.verdict?.includes('Fed')||
      !(result.macro?.includes('non ha una data di rilascio')||
        result.macro?.includes('Manca un riepilogo macro USD con data di rilascio verificabile'))||
      !result.pricing?.includes('OIS')||
      !result.asof?.includes('Treasury')||
      !result.asof?.includes('BCE')){
     throw Error('Concept QA '+label+': '+JSON.stringify(result));
   }
   await page.locator('#g8Grid button[data-ccy="JPY"]').click();
   await page.waitForFunction(()=>document.querySelector('#focusName')?.textContent?.includes('Yen'),null,{timeout:9000});
   await page.screenshot({path:path.join(output,'global-macro-concept-'+label+'.png'),fullPage:true,animations:'disabled'});
   console.log('FXV2_HOME_CONCEPT '+label+' PASS '+JSON.stringify(result));
   await page.close();
  }
  if(errors.length)throw Error('JS errors: '+errors.join(' | '));
  console.log('FXV2_HOME_CONCEPT_DESKTOP_MOBILE_PASS');
 }finally{await browser.close();}
})().catch(e=>{console.error('FXV2_HOME_CONCEPT_FAIL',e);process.exitCode=1;});
