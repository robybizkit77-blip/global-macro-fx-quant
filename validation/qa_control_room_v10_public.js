/* Public URL smoke QA. No mocked feeds: validates what the actual GitHub Pages website serves. */
'use strict';
const {chromium}=require('playwright');
const BASE='https://robybizkit77-blip.github.io/global-macro-fx-quant/site/control-room-preview/';
async function getState(page){
 return page.evaluate(()=>{
   const iframe=document.getElementById('gmfq-page'),d=iframe?.contentDocument;
   return {
     frame:!!iframe,
     route:location.hash,
     mode:d?.documentElement?.dataset.marketMode,
     feedState:d?.documentElement?.dataset.liveState,
     dxy:d?.querySelector('#valute .cc[data-filter="DXY"] .value')?.textContent.trim(),
     dxyEst:d?.querySelector('#valute .cc[data-filter="DXY"] .move')?.textContent.trim(),
     chartCount:d?.querySelectorAll('#ylegend .gmfq-legend-item').length,
     pricingCount:d?.querySelectorAll('#ois .oisrow').length,
     notes:d?.querySelector('#ratesbars + .gmfq-chart-note')?.textContent.trim(),
     badApprofondisci:d?.body?.textContent.includes('Approfondisci ↗'),
     globe:!!d?.querySelector('.hero .globe'),
     width:d?.documentElement.scrollWidth,
     viewport:d?.documentElement.clientWidth
   };
 });
}
(async()=>{
 const browser=await chromium.launch({headless:true});
 try {
   for(const [name,viewport] of [['desktop',{width:1440,height:900}],['mobile',{width:390,height:844}]]){
     const page=await browser.newPage({viewport});
     const errs=[];
     page.on('pageerror',e=>errs.push(String(e)));
     const response=await page.goto(BASE,{waitUntil:'domcontentloaded',timeout:120000});
     if(!response?.ok())throw Error(name+' public site HTTP failure: '+response?.status());
     await page.waitForFunction(()=>{
       const d=document.getElementById('gmfq-page')?.contentDocument;
       return d?.documentElement?.dataset.liveState==='LOADED'
         && d.querySelectorAll('#ois .oisrow').length===8
         && d.querySelectorAll('#ylegend .gmfq-legend-item').length===8
         && d.querySelector('#valute .cc[data-filter="DXY"] .move')?.textContent.includes('STIMA');
     },null,{timeout:60000});
     const state=await getState(page);
     console.log('PUBLIC_V10_SMOKE',name,JSON.stringify(state));
     if(state.mode!=='live'||state.chartCount!==8||state.pricingCount!==8||!state.globe||
        state.badApprofondisci||!state.dxy||state.dxy==='—'||state.width>state.viewport+16||
        !state.notes.includes('R²')||!state.notes.includes('CHF/EUR')||
        !state.notes.includes('NZD/AUD')||!state.notes.includes('base ')){
       throw Error(name+' public Home contract failed: '+JSON.stringify(state));
     }
     if(errs.length)throw Error(name+' browser page error: '+errs.join('; '));
     await page.frameLocator('#gmfq-page').locator('#valute .cc[data-filter="DXY"]').click();
     await page.frameLocator('#gmfq-page').locator('dialog#gmfq-dxy-dialog[open]').waitFor({timeout:10000});
     await page.frameLocator('#gmfq-page').locator('.gmfq-dxy-dialog .gmfq-close').click();
     await page.frameLocator('#gmfq-page').locator('.mid > .panel:nth-child(2)').click();
     await page.waitForURL(/#\/tassi\?focus=2y$/,{timeout:15000});
     await page.waitForFunction(()=>document.getElementById('gmfq-page')?.contentDocument?.querySelector('#rates-select'),null,{timeout:20000});
     await page.goto(BASE+'#/home',{waitUntil:'domcontentloaded',timeout:120000});
     await page.waitForFunction(()=>document.getElementById('gmfq-page')?.contentDocument?.querySelectorAll('#ois .oisrow').length===8,null,{timeout:60000});
     await page.frameLocator('#gmfq-page').locator('#ois .oisrow[data-ccy="USD"]').click();
     await page.waitForURL(/#\/banche\?ccy=USD$/,{timeout:15000});
     await page.close();
   }
   console.log('CONTROL_ROOM_V10_PUBLIC_G8_DXY_NAVIGATION_GREEN');
 } finally {await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
