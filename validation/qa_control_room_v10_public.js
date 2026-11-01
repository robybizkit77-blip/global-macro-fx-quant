/* Public URL smoke QA. No mocked feeds: validates what the actual GitHub Pages website serves. */
'use strict';
const {chromium}=require('playwright');
const fs=require('node:fs');
const {execFileSync}=require('node:child_process');
const {readApproved,verifyPublicNzd}=require('./control_room_nzd_public_contract_v1.js');
const {matrix:expectedOisResearchMatrix,romeTodayIso}=require('../site/control-room-preview/ois-pricing-estimates-v1.js');
const {expectedOfficialCurrencies}=require('./control_room_public_ois_eligibility_v1.js');
const approvedNzdrates=readApproved('.');
// PR browser QA targets the *currently published* main; its new loader
// and version token will appear on GitHub Pages only after merge.
const loader=process.env.GITHUB_EVENT_NAME==='pull_request'?
 execFileSync('git',['show','origin/main:site/control-room-preview/index.html'],{encoding:'utf8'}):
 fs.readFileSync('site/control-room-preview/index.html','utf8');
// The correct public browser check is the version specified by canonical main,
// not the previous hardcoded query token. Verify its actual deployed bytes.
const navigationVersion=/\.\/home-navigation-v10\.js\?v=([a-z0-9-]+)/i.exec(loader)?.[1];
if(!navigationVersion)throw Error('Canonical Preview navigation version absent');
const addonVersion=/\.\/ois-pricing-estimates-v1\.js\?v=([a-z0-9-]+)/i.exec(loader)?.[1];
if(!addonVersion)throw Error('Canonical Preview OIS research addon version absent');
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
     const errs=[],failedRequests=[],httpErrors=[];
     page.on('pageerror',e=>errs.push(String(e)));
     page.on('requestfailed',req=>failedRequests.push({url:req.url(),reason:req.failure()?.errorText}));
     page.on('response',res=>{if(res.status()>=400)httpErrors.push({url:res.url(),status:res.status()});});
     // The branch may advance before the Pages deployment/CDN serves the new revision.
     // Retry a cache-busted public URL until the *actual browser* sees the new note contract.
     let deployed=false,lastObserved=null;
     for(let attempt=0;attempt<18;attempt++){
       const response=await page.goto(BASE+'?qa='+Date.now()+'-'+attempt,{waitUntil:'domcontentloaded',timeout:120000});
       if(!response?.ok())throw Error(name+' public site HTTP failure: '+response?.status());
       try{
         await page.waitForFunction(()=>{
           const d=document.getElementById('gmfq-page')?.contentDocument;
           return d?.documentElement?.dataset.liveState==='LOADED'
             && d.querySelectorAll('#ois .oisrow').length===8
             && d.querySelectorAll('#ylegend .gmfq-legend-item').length===8
             && d.querySelector('#valute .cc[data-filter="DXY"] .move')?.textContent.includes('STIMA');
         },null,{timeout:12000});
         lastObserved=await getState(page);
         if(lastObserved.notes?.includes('R²')&&lastObserved.notes?.includes('base ')){
           deployed=true;break;
         }
         console.log('PUBLIC_V10_VERSION_PENDING',name,attempt,lastObserved.notes);
       }catch(error){
         const docState=await getState(page).catch(e=>({error:String(e)}));
         const detail=await page.evaluate(()=>{
           const f=document.getElementById('gmfq-page'),d=f?.contentDocument;
           return {outer:document.getElementById('state')?.innerText,frame:!!f,child:!!d,
             scripts:[...(d?.scripts||[])].slice(-4).map(x=>x.src||'inline'),
             htmlEnd:d?.body?.innerText?.slice(-250)};
         }).catch(e=>({error:String(e)}));
         console.log('PUBLIC_V10_VERSION_PENDING',name,attempt,JSON.stringify({
           message:String(error).slice(0,160),docState,detail,errs,failedRequests:httpErrors.length?failedRequests.slice(-8):failedRequests.slice(-4),httpErrors:httpErrors.slice(-8)
         }));
       }
       await page.waitForTimeout(6000);
     }
     if(!deployed)throw Error(name+' public CDN did not serve the matched-date G8 estimate build: '+JSON.stringify(lastObserved));
     // This UI is introduced in the current PR, so only the post-merge public
     // run requires it. Bounded CDN retry verifies the actual public website.
     if(process.env.GITHUB_EVENT_NAME!=='pull_request'){
       let found=false;
       for(let attempt=0;attempt<14;attempt++){
         found=await page.evaluate(()=>{
           const d=document.getElementById('gmfq-page')?.contentDocument;
           return !!d?.getElementById('gmfq-home-data-audit')&&
             d.querySelector('.mast .fresh')?.getAttribute('role')==='button';
         });
         if(found)break;
         await page.goto(BASE+'?freshqa='+Date.now()+'-'+attempt+'#/home',
           {waitUntil:'domcontentloaded',timeout:120000});
         try{
           await page.waitForFunction(()=>{
             const d=document.getElementById('gmfq-page')?.contentDocument;
             return d?.documentElement?.dataset.liveState==='LOADED'&&
               !!d?.getElementById('gmfq-home-data-audit');
           },null,{timeout:8500});
         }catch(_){console.log('PUBLIC_V10_FRESHNESS_CDN_PENDING',name,attempt)}
         await page.waitForTimeout(3000);
       }
       if(!found)found=await page.evaluate(()=>!!document.getElementById('gmfq-page')?.contentDocument?.getElementById('gmfq-home-data-audit'));
       if(!found)throw Error(name+' PUBLIC_HOME_SOURCE_FRESHNESS_VERSION_NOT_DEPLOYED');
       // SHA parity alone does not guarantee that the public Pages CDN has
       // served this new dual source-label build. Retry only the public URL.
       let dualReady=false;
       for(let attempt=0;attempt<22;attempt++){
         dualReady=await page.evaluate(()=>{
           const d=document.getElementById('gmfq-page')?.contentDocument;
           const stamp=d?.getElementById('liveAsOf')?.textContent||'';
           const source=d?.getElementById('gmfq-home-data-audit')?.textContent||'';
           return stamp.includes('cert. · Contesto ')&&
                  source.includes('Contesto monetario G8 · ricerca');
         });
         if(dualReady)break;
         await page.goto(BASE+'?dualOisQA='+Date.now()+'-'+attempt+'#/home',
           {waitUntil:'domcontentloaded',timeout:120000});
         try{
           await page.waitForFunction(()=>{
             const d=document.getElementById('gmfq-page')?.contentDocument;
             return d?.documentElement?.dataset.liveState==='LOADED'&&
                    !!d.getElementById('gmfq-home-data-audit');
           },null,{timeout:9000});
         }catch(_){console.log('PUBLIC_DUAL_OIS_CDN_PENDING',name,attempt)}
         await page.waitForTimeout(3500);
       }
       if(!dualReady)throw Error(name+' PUBLIC_CDN_STALE_NO_DUAL_OIS_PROVENANCE');
       const audit=await page.evaluate(()=>{
         const d=document.getElementById('gmfq-page').contentDocument;
         return {
           state:d.getElementById('liveState')?.textContent,
           stamp:d.getElementById('liveAsOf')?.textContent,
           detail:d.getElementById('gmfq-home-data-audit')?.textContent,
           documentWidth:d.documentElement.scrollWidth,
           viewport:d.documentElement.clientWidth
         };
       });
       if(!audit.state?.startsWith('DATI ')&&audit.state!=='FONTI VERIFICATE'||
          !audit.stamp?.includes('OIS ')||
          !audit.stamp?.includes('cert. · Contesto ')||
          !audit.detail?.includes('Contesto monetario G8 · ricerca')||
          !audit.detail?.includes('Contesto monetario G8 · ricerca')||
          !(audit.detail.includes('proxy Bank Bill−cash calibrato su 19 osservazioni RBNZ')||
            audit.detail.includes('Copertura ricerca non verificabile. Non viene promossa alcuna stima a dato ufficiale.'))||
          !audit.detail?.includes('Non è DXY ICE ufficiale')||
          !audit.detail?.includes('futures monetari, non OIS puri')||
          !audit.detail?.includes('Le date delle diverse fonti non sono intercambiabili')||
          audit.documentWidth>audit.viewport+16)
         throw Error(name+' public source-date disclosure missing '+JSON.stringify(audit));
       // GitHub Pages deployment and its edge cache are not atomic. Read the
       // actual new script version and mounted rail on the PUBLIC browser before
       // testing its layout; never treat an older published build as GREEN.
       let readingReady=false;
       for(let attempt=0;attempt<16;attempt++){
         readingReady=await page.evaluate(expected=>{
           const d=document.getElementById('gmfq-page')?.contentDocument;
           return [...document.scripts].some(x=>
              x.src.endsWith('home-navigation-v10.js?v='+expected))&&
              d?.getElementById('gmfq-home-reading-path')?.dataset.sourceEffect==='NONE';
         },navigationVersion);
         if(readingReady)break;
         await page.goto(BASE+'?homeReadingQa='+Date.now()+'-'+attempt+'#/home',
           {waitUntil:'domcontentloaded',timeout:120000});
         try{
           await page.waitForFunction(expected=>{
             const d=document.getElementById('gmfq-page')?.contentDocument;
             return [...document.scripts].some(x=>
               x.src.endsWith('home-navigation-v10.js?v='+expected))&&
               d?.getElementById('gmfq-home-reading-path')?.dataset.sourceEffect==='NONE';
           },navigationVersion,{timeout:12000});
           readingReady=true;
         }catch(_){console.log('PUBLIC_HOME_READING_CDN_PENDING',name,attempt)}
       }
       if(!readingReady)throw Error(name+' PUBLIC_HOME_READING_VERSION_NOT_DEPLOYED '+navigationVersion);
       if(['home-dated-first-read-20261101','home-pulse-materiality-20261101'].includes(navigationVersion)){
         await page.waitForFunction(()=>{
           const d=document.getElementById('gmfq-page')?.contentDocument,
             lead=d?.getElementById('gmfq-home-change-lead'),
             pulse=d?.getElementById('gmfq-market-pulse');
           return !!lead&&['DATED_REPRICING','LEVEL_CONTEXT_ONLY','NO_RECENT_CHANGE']
             .includes(lead.dataset.state)&&
             ['RECENT_VALIDATED','DATED_LEVEL_CONTEXT','WITHHELD']
             .includes(pulse?.dataset.pulseStatus);
         },null,{timeout:30000});
         const proof=await page.evaluate(()=>{
           const d=document.getElementById('gmfq-page').contentDocument,
             lead=d.getElementById('gmfq-home-change-lead'),
             pulse=d.getElementById('gmfq-market-pulse');
           const rail=d.getElementById('gmfq-home-reading-path'),
             change=lead.getBoundingClientRect(),hero=d.querySelector('.hero').getBoundingClientRect();
           return {state:lead.dataset.state,asof:lead.dataset.observationAsOf,
             sourceEffect:lead.dataset.sourceEffect,text:lead.querySelector('.gmfq-home-change-value')?.textContent,
             note:lead.querySelector('.gmfq-home-change-provenance')?.textContent,
             link:!!lead.querySelector('button[data-home-pulse-focus]'),
             pulse:pulse.dataset.pulseStatus,pulseDay:pulse.dataset.asOf,
             pulseText:pulse.querySelector('.gmfq-pulse-lead')?.textContent,
             first:change.top>=rail.getBoundingClientRect().top-1&&change.top<hero.top,
             width:d.documentElement.scrollWidth,viewport:d.documentElement.clientWidth};
         });
         if(!proof.first||!proof.link||proof.sourceEffect!=='NONE'||
            proof.width>proof.viewport+16||!proof.text||!proof.note)
           throw Error(name+' public Home 1st read incomplete '+JSON.stringify(proof));
         if(proof.pulse==='RECENT_VALIDATED'&&
            (proof.state!=='DATED_REPRICING'||proof.asof!==proof.pulseDay||
             proof.text!==proof.pulseText||!proof.note.includes('non intraday')))
           throw Error(name+' public unsourced first-screen repricing '+JSON.stringify(proof));
         if(proof.pulse==='WITHHELD'&&
            (proof.state!=='NO_RECENT_CHANGE'||proof.asof))
           throw Error(name+' public invented Home repricing '+JSON.stringify(proof));
         if(proof.pulse==='DATED_LEVEL_CONTEXT'&&
            (proof.state!=='LEVEL_CONTEXT_ONLY'||proof.asof))
           throw Error(name+' stale levels called fresh repricing '+JSON.stringify(proof));
         console.log('PUBLIC_HOME_DATED_FIRST_READ_GREEN',name,JSON.stringify(proof));
       }

       // Verify the published Home puts the source-led research sequence
       // before the protected globe/grid, without an extra dashboard.
       const reading=await page.evaluate(()=>{
         const d=document.getElementById('gmfq-page').contentDocument;
         const rail=d.getElementById('gmfq-home-reading-path'),
           hero=d.querySelector('.hero'),grid=d.querySelector('.gridtop');
         const keys=[...rail?.querySelectorAll('button[data-reading-target]')||[]]
           .map(x=>x.dataset.readingTarget);
         return {present:!!rail,keys,macro:rail?.dataset.macroStatus,
           ois:rail?.dataset.oisCertified,screener:rail?.dataset.screenerCount,
           sourceEffect:rail?.dataset.sourceEffect,
           visualEdition:rail?.dataset.visualEdition,
           layout:{
             columns:getComputedStyle(grid).gridTemplateColumns.trim().split(/\s+/).length,
             heroFullWidth:Math.abs(hero.getBoundingClientRect().width-grid.getBoundingClientRect().width)<=2,
             globeSameImage:getComputedStyle(hero.querySelector('.globe')).backgroundImage.includes('data:image/png;base64'),
             backgroundRatio:getComputedStyle(hero.querySelector('.globe')).backgroundSize==='auto 100%',
             railColumns:getComputedStyle(rail).gridTemplateColumns.trim().split(/\s+/).length,
             marketCards:grid.querySelectorAll(':scope>.panel:not(.hero)').length===2,
             styleMounted:!!d.getElementById('gmfq-home-visual-edition-css')
           },
           lower:{
             market:!!d.getElementById('gmfq-home-market-chapter'),
             pair:!!d.getElementById('gmfq-home-pair-chapter'),
             marketBefore:!!(d.getElementById('gmfq-home-market-chapter')?.compareDocumentPosition(d.querySelector('.mid'))&Node.DOCUMENT_POSITION_FOLLOWING),
             pairBefore:!!(d.getElementById('gmfq-home-pair-chapter')?.compareDocumentPosition(d.querySelector('.bottom'))&Node.DOCUMENT_POSITION_FOLLOWING),
             midCols:d.querySelector('.mid')?d.defaultView.getComputedStyle(d.querySelector('.mid')).gridTemplateColumns.trim().split(/\s+/).length:null,
             bottomCols:d.querySelector('.bottom')?d.defaultView.getComputedStyle(d.querySelector('.bottom')).gridTemplateColumns.trim().split(/\s+/).length:null,
             messagesCols:d.querySelector('.bottom .messagebox')?d.defaultView.getComputedStyle(d.querySelector('.bottom .messagebox')).gridTemplateColumns.trim().split(/\s+/).length:null,
             fullWidthTable:Math.abs((d.querySelector('.bottom>.panel:first-child')?.getBoundingClientRect().width||0)-(d.querySelector('.bottom')?.getBoundingClientRect().width||0))<=2,
             allCharts:['strength','ratesbars','spreads'].every(k=>!!d.getElementById(k)?.querySelector('svg')),
             chartsHeight:d.getElementById('ratesbars')?.clientHeight,
             messages:d.querySelectorAll('.bottom .messagebox .msg').length
           },
           newHome:{
             flags:[...d.querySelectorAll('#valute .cc[data-filter]')].map(x=>({
               code:x.dataset.filter,flag:x.querySelector('.tickerhead .flag')?.textContent,
               dxyTag:x.querySelector('.gmfq-home-dxy-origin')?.textContent
             })),
             pricing:[...d.querySelectorAll('#ois .oisrow')].map(x=>({
               code:x.dataset.ccy,status:x.dataset.pricingState,allowed:x.dataset.policyDeltaAllowed,
               text:x.textContent
             })),
             pulsePresent:!!d.getElementById('gmfq-market-pulse'),
             pulseState:d.getElementById('gmfq-market-pulse')?.dataset.pulseStatus,
             pulseText:d.getElementById('gmfq-market-pulse')?.innerText,
             pulseTitle:d.querySelector('#gmfq-market-pulse h2')?.textContent,
             pulseExternal:d.querySelector('#gmfq-market-pulse .gmfq-pulse-links > span')?.textContent,
             pulseItems:[...d.querySelectorAll('#gmfq-market-pulse .gmfq-pulse-item')].map(x=>({
                code:x.dataset.pulseCcy,instrument:x.dataset.instrumentType,
                detailClosed:x.querySelector('details')?.open===false,
                note:x.querySelector('.gmfq-pulse-instrument')?.textContent
             })),
             pulseNewsHref:d.querySelector('#gmfq-market-pulse a[href="https://www.reuters.com/markets/"]')?.href,
             eventRadar:(()=>{
               const h=d.getElementById('gmfq-event-radar');
               return {present:!!h,status:h?.dataset.calendarStatus,
                 sourceEffect:h?.dataset.signalEffect,text:h?.textContent,
                 rows:[...h?.querySelectorAll('li[data-event-date]')||[]].map(x=>({ccy:x.dataset.eventCcy,date:x.dataset.eventDate})),
                 width:h?.scrollWidth,client:h?.clientWidth};
             })(),
             dxyChartFuture:!!d.querySelector('.gmfq-dxy-dialog')
           },
           priorityTarget:rail?.dataset.priorityTarget,
           priorityState:rail?.dataset.priorityState,
           priorityText:rail?.querySelector('.gmfq-reading-priority')?.textContent,
           priorityFirst:!!(rail?.querySelector('.gmfq-reading-priority')?.compareDocumentPosition(rail.querySelector('.gmfq-reading-steps'))&Node.DOCUMENT_POSITION_FOLLOWING),
           emphasized:[...rail?.querySelectorAll('button[data-reading-priority="true"]')||[]].map(x=>x.dataset.readingTarget),
           nextToGlobe:!!rail&&!!hero&&!!grid&&!!d.querySelector('.hero .globe')&&
             grid.contains(hero)&&
             !!(rail.compareDocumentPosition(grid)&Node.DOCUMENT_POSITION_FOLLOWING),
           width:rail?.scrollWidth,client:rail?.clientWidth,
           page:d.documentElement.scrollWidth,viewport:d.documentElement.clientWidth};
       });
       // Verify the live DOM against independent publicly delivered
       // operational AND canonical OIS data, applying the same strict
       // four-Rome-calendar-day source freshness rule as the renderer.
       // Historical official observations remain historical, never forced to
       // appear as live repricing, and estimated data can never count.
       const publicOis=await page.evaluate(async()=>{
         const base='/global-macro-fx-quant/live_data/sections/';
         const urls=['OIS_OPERATIONAL_VIEW.json','OIS_DATA.json'];
         return await Promise.all(urls.map(async name=>{
           const response=await fetch(base+name,{cache:'no-store'});
           if(!response.ok)throw Error('Public OIS feed '+name+' HTTP '+response.status);
           return response.json();
         }));
       });
       const expectedOfficial=expectedOfficialCurrencies(publicOis[0],publicOis[1],romeTodayIso());
       const displayedOfficial=reading.newHome.pricing
         .filter(x=>x.status==='OFFICIAL_REPRICING').map(x=>x.code);
       if(reading.newHome.pricing.length!==8||
          new Set(reading.newHome.pricing.map(x=>x.code)).size!==8||
          JSON.stringify([...displayedOfficial].sort())!==JSON.stringify([...expectedOfficial].sort()))
          throw Error(name+' public official OIS display/source-age mismatch '+JSON.stringify({
            displayedOfficial,expectedOfficial,asof:romeTodayIso(),
            sourceDates:Object.fromEntries(expectedOfficial.map(c=>[c,publicOis[0].currencies[c].as_of]))
          }));
       console.log('PUBLIC_V10_DYNAMIC_CERTIFIED_OIS_SOURCE_AGE_PASS',name,
         JSON.stringify({asof:romeTodayIso(),official:expectedOfficial}));
       if(!reading.present||!reading.nextToGlobe||reading.sourceEffect!=='NONE'||
           reading.visualEdition!=='home-composition-v1'||
           !reading.layout.styleMounted||!reading.layout.heroFullWidth||
           !reading.layout.globeSameImage||!reading.layout.backgroundRatio||
           !reading.layout.marketCards||
           reading.layout.columns!==(name==='mobile'?1:2)||
           reading.layout.railColumns!==(name==='mobile'?1:2)||
           reading.newHome.flags.length!==8||
           reading.newHome.flags.some(x=>!x.flag)||
           !reading.newHome.flags.find(x=>x.code==='DXY')?.dxyTag?.includes('SINTETICO')||
           reading.newHome.pricing.length!==8||
           reading.newHome.pricing.filter(x=>x.status==='OFFICIAL_REPRICING').length!==expectedOfficial.length||
           reading.newHome.pricing.some(x=>(x.allowed==='true')!==(x.status==='OFFICIAL_REPRICING'))||
           !reading.newHome.pulsePresent||!reading.newHome.pulseNewsHref||
           (process.env.GITHUB_EVENT_NAME!=='pull_request'&&navigationVersion==='event-risk-radar-20261022'&&
             (!reading.newHome.eventRadar.present||
              !['FUTURE_VERIFIED_AGENDA','WITHHELD'].includes(reading.newHome.eventRadar.status)||
              reading.newHome.eventRadar.sourceEffect!=='NONE'||
              !reading.newHome.eventRadar.text?.includes('non notizie né risultati già pubblicati')||
              reading.newHome.eventRadar.width>reading.newHome.eventRadar.client+2||
              reading.newHome.eventRadar.rows.some(x=>!['USD','EUR','GBP','JPY','AUD','CAD','NZD','CHF'].includes(x.ccy)||
                x.date<=romeTodayIso())||
              (reading.newHome.eventRadar.status==='WITHHELD'&&reading.newHome.eventRadar.rows.length>0)))||
           (process.env.GITHUB_EVENT_NAME!=='pull_request'&&navigationVersion==='market-pulse-pricing-20261022'&&
            (reading.newHome.pulseTitle!=='Market Pulse · tassi impliciti'||
             !reading.newHome.pulseExternal?.includes('Notizie esterne')||
             reading.newHome.pulseItems.some(x=>!['GBP','CAD','JPY','AUD'].includes(x.code)||
               x.instrument!==(x.code==='GBP'?'OIS':'FUTURES')||
               x.detailClosed!==true||
               !x.note?.includes(x.code==='GBP'?'OIS BoE':'Futures'))))||
           !reading.lower.market||!reading.lower.pair||
           !reading.lower.marketBefore||!reading.lower.pairBefore||
           reading.lower.midCols!==(name==='mobile'?1:3)||
           reading.lower.bottomCols!==1||
           reading.lower.messagesCols!==(name==='mobile'?1:2)||
           !reading.lower.fullWidthTable||!reading.lower.allCharts||
           reading.lower.chartsHeight<190||reading.lower.messages<1||
          JSON.stringify(reading.keys)!==JSON.stringify(['macro','pricing','pairs'])||
          reading.priorityTarget!==(reading.macro!=='DATED_SNAPSHOT'?'macro':Number(reading.ois)<8?'pricing':'pairs')||
          reading.priorityState!==(reading.macro==='HISTORICAL'?'HISTORICAL':reading.macro==='WITHHELD'?'WITHHELD':Number(reading.ois)<8?'PARTIAL':'RESEARCH_ONLY')||
          reading.emphasized?.length!==1||reading.emphasized[0]!==reading.priorityTarget||
          !reading.priorityFirst||
          !(reading.priorityText?.startsWith('Prima ')||reading.priorityText?.startsWith('Passa allo Screener'))||
          !['HISTORICAL','DATED_SNAPSHOT','WITHHELD'].includes(reading.macro)||
          !Number.isInteger(Number(reading.ois))||Number(reading.ois)>8||
          !Number.isInteger(Number(reading.screener))||Number(reading.screener)>28||
          reading.width>reading.client+2||reading.page>reading.viewport+16)
         throw Error(name+' public Home decision-first research path wrong '+JSON.stringify(reading));
       console.log('CONTROL_ROOM_V10_HOME_READING_PUBLIC_GREEN',name,reading);
       if(name==='mobile')await page.frameLocator('#gmfq-page').locator('#gmfq-mobile-data-audit').click();
       else await page.frameLocator('#gmfq-page').locator('.mast .fresh').press('Enter');
       await page.frameLocator('#gmfq-page').locator('dialog#gmfq-home-data-audit[open]').waitFor({timeout:10000});
       await page.frameLocator('#gmfq-page').locator('.gmfq-audit-close').click();
       console.log('CONTROL_ROOM_PREVIEW_PUBLIC_SOURCE_FRESHNESS_GREEN',name,
         JSON.stringify({state:audit.state,stamp:audit.stamp,viewport:audit.viewport}));
     }
     const state=await getState(page);
     console.log('PUBLIC_V10_SMOKE',name,JSON.stringify(state));
     if(state.mode!=='live'||state.chartCount!==8||state.pricingCount!==8||!state.globe||
        state.badApprofondisci||!state.dxy||state.dxy==='—'||state.width>state.viewport+16||
        !state.notes.includes('R²')||!state.notes.includes('CHF/EUR')||
        !state.notes.includes('base ')){
       throw Error(name+' public Home contract failed: '+JSON.stringify(state));
     }
     // The manually reviewed RBNZ B2 snapshot can advance through the registry.
     // Once its observation is historical, an explicitly labelled AUD proxy
     // may appear. That is not a retroactive loss of source certification.
     const ratesMirror=await page.evaluate(async()=>{
       const r=await fetch('/global-macro-fx-quant/live_data/sections/NATIVE_RATES_DATA.json',{cache:'no-store'});
       if(!r.ok)throw Error('Rates mirror HTTP '+r.status);
       const x=await r.json();return x.NZD;
     });
     const nzdProof=verifyPublicNzd(ratesMirror,approvedNzdrates.approved,
       approvedNzdrates.canonical,state.notes);
     console.log('PUBLIC_NZD_REVIEWED_RATES_MIRROR_GREEN',name,JSON.stringify(nzdProof));
     // This is the active Control Room Preview, not the legacy root dashboard.
     // Verify the three real, publicly delivered FX inputs of the active Preview:
     // official ECB 28-pair price history, the 28 canonical pair setups, and the
     // informational ECB DXY synthetic. Never mistake branch parity for HTTP proof.
     const pricing=await page.evaluate(async()=>{
       const BASE='/global-macro-fx-quant/live_data/sections/';
       async function read(name){
         const res=await fetch(BASE+name,{cache:'no-store'});
         if(!res.ok)throw Error('Preview market feed '+name+' HTTP '+res.status);
         return res.json();
       }
       const [history,setup,dxy]=await Promise.all([
         read('ECB_G8_PRICE_HISTORY.json'),
         read('PAIR_SETUP_OPERATIONAL_VIEW.json'),
         read('DXY_SYNTHETIC_ECB.json')
       ]);
       return {
         history_schema:history.schema,history_status:history.status,
         history_date:history.last_as_of,history_rows:history.rows?.length,
         history_pair_count:history.pair_count,
         last_row_date:history.rows?.at(-1)?.Date,
         setup_schema:setup.schema,setup_status:setup.status,
         setup_pair_count:setup.pair_count,setup_pairs:Object.keys(setup.pairs||{}).length,
         setup_date:setup.price_asof,setup_macro_asof:setup.macro_baseline_asof,setup_audit:setup.price_audit?.status,
         dxy_schema:dxy.schema,dxy_status:dxy.status,dxy_date:dxy.as_of,
         dxy_latest:dxy.history?.at(-1)?.date,
         dxy_non_official:dxy.not_official_ice===true,
         dxy_not_signal:dxy.usable_as_official_ice_or_trade_signal===false
       };
     });
     if(pricing.history_schema!=='GMFQ_ECB_G8_PRICE_HISTORY_V1'||
        pricing.history_status!=='CURRENT_OFFICIAL_HISTORY'||
        pricing.history_rows<500||pricing.history_pair_count!==28||
        pricing.last_row_date!==pricing.history_date||
        pricing.setup_schema!=='GMFQ_PAIR_SETUP_OPERATIONAL_VIEW_V1'||
        pricing.setup_status!=='CURRENT_CANONICAL_ENGINE'||
        pricing.setup_pair_count!==28||pricing.setup_pairs!==28||
        pricing.setup_audit!=='PASS'||!pricing.setup_date||!pricing.setup_macro_asof||
        pricing.setup_macro_asof>pricing.setup_date||
        pricing.dxy_schema!=='GMFQ_DXY_SYNTHETIC_ECB_V1'||
        pricing.dxy_status!=='ESTIMATED_INFORMATIONAL'||
        pricing.dxy_date!==pricing.history_date||
        pricing.dxy_latest!==pricing.dxy_date||
        !pricing.dxy_non_official||!pricing.dxy_not_signal)
        throw Error(name+' active Preview ECB/pair/DXY public-feed validation failed '+JSON.stringify(pricing));
     const gap=(Date.parse(pricing.history_date+'T00:00:00Z')-Date.parse(pricing.setup_date+'T00:00:00Z'))/86400000;
     if(!Number.isInteger(gap)||gap<0||gap>3)
        throw Error(name+' Preview pair setups too old for ECB price history '+JSON.stringify(pricing));
     console.log('CONTROL_ROOM_PREVIEW_PUBLIC_FX_28_PAIR_DXY_FEED_PASS',name,JSON.stringify(pricing));
     if(errs.length)throw Error(name+' browser page error: '+errs.join('; '));
     // Chart interaction is research-only; every G8 series remains selectable.
  const focusButton=page.frameLocator('#gmfq-page').locator('#ylegend button[data-gmfq-ccy-focus="EUR"]');
     if(await focusButton.count()){
       await focusButton.click();
       const selected=await page.evaluate(()=>document.getElementById('gmfq-page').contentDocument.getElementById('curves')?.dataset.gmfqYieldFocus);
       if(selected!=='EUR')throw Error('EUR yield focus failed: '+selected);
       await focusButton.click();
       const restored=await page.evaluate(()=>document.getElementById('gmfq-page').contentDocument.getElementById('curves')?.dataset.gmfqYieldFocus);
       if(restored!=='ALL')throw Error('G8 yield restore failed: '+restored);
     }else console.log('G8_FOCUS_NOT_YET_DEPLOYED: PR public QA is checking prior main; local browser QA checks new code');
     await page.frameLocator('#gmfq-page').locator('#valute .cc[data-filter="DXY"]').click();
     await page.frameLocator('#gmfq-page').locator('dialog#gmfq-dxy-dialog[open]').waitFor({timeout:10000});
     if(process.env.GITHUB_EVENT_NAME!=='pull_request'&&navigationVersion==='dxy-context-20261022'){
       const ctx=await page.evaluate(()=>{
         const d=document.getElementById('gmfq-page').contentDocument,
           box=d.getElementById('gmfq-dxy-dialog'),metrics=box?.querySelector('.gmfq-dxy-metrics');
         return {visible:!!metrics?.getClientRects().length,
           count:metrics?.querySelectorAll('strong').length,
           notIce:metrics?.dataset.iceOfficial==='false',
           disclaimer:box?.textContent.includes('non sull’indice ICE'),
           chart:!!box?.querySelector('svg polyline'),
           modalWidth:box?.getBoundingClientRect().width,
           viewport:d.documentElement.clientWidth};
       });
       if(!ctx.visible||ctx.count!==3||!ctx.notIce||!ctx.disclaimer||!ctx.chart||
          ctx.modalWidth>ctx.viewport+2)
         throw Error('Public DXY source-safe context not present '+JSON.stringify(ctx));
     }
     await page.frameLocator('#gmfq-page').locator('.gmfq-dxy-dialog .gmfq-close').click();
     await page.frameLocator('#gmfq-page').locator('.mid > .panel:nth-child(2)').click();
     await page.waitForURL(/#\/tassi\?focus=2y$/,{timeout:15000});
     await page.waitForFunction(()=>document.getElementById('gmfq-page')?.contentDocument?.querySelector('#rates-select'),null,{timeout:20000});
     // Confirm actual CDN output after merge, not only main source parity.
     // A valid SVG with two JPY points can hide 246 skipped non-padded dates.
     if(process.env.GITHUB_EVENT_NAME!=='pull_request' &&
        navigationVersion==='g8-sovereign-full-history-20261101'){
       const sovereignPublicRates=await page.evaluate(async()=>{
         const res=await fetch('/global-macro-fx-quant/live_data/sections/NATIVE_RATES_DATA.json',
           {cache:'no-store'});
         if(!res.ok)throw Error('Public sovereign feed HTTP '+res.status);
         return res.json();
       });
       await page.waitForFunction(()=>
         document.getElementById('gmfq-page')?.contentDocument
          ?.querySelectorAll('#rates-select button[data-ccy]').length===8,
         null,{timeout:20000});
       const plotSummary=[];
       for(const ccy of ['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']){
         const src=sovereignPublicRates[ccy];
         if(!src)throw Error(name+' public missing sovereign '+ccy);
         const normal=d=>{
           const m=/^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(d||'');
           return m?m[1]+'-'+m[2].padStart(2,'0')+'-'+m[3].padStart(2,'0'):null;
         };
         const two=new Map(src.history2.dates.map((d,i)=>[normal(d),src.history2.values[i]]));
         const last=Date.parse(src.date+'T00:00:00Z');
         const expected=src.history10.dates.map((d,i)=>({d:normal(d),
           y2:two.get(normal(d)),y10:src.history10.values[i]}))
          .filter(x=>x.d&&Number.isFinite(x.y2)&&Number.isFinite(x.y10)&&x.d<=src.date&&
            Date.parse(x.d+'T00:00:00Z')>=last-184*86400000);
         if(expected.length<2)throw Error(name+' public source history incomplete '+ccy);
         await page.frameLocator('#gmfq-page').locator('#rates-select button[data-ccy="'+ccy+'"]').click();
         await page.waitForFunction(({ccy,count})=>{
           const d=document.getElementById('gmfq-page')?.contentDocument,
             h=d?.getElementById('rates-chart'),
             svg=h?.querySelector('svg[data-gmfq-sovereign-plot]');
           return svg?.dataset.ccy===ccy&&svg.getClientRects().length>0&&
             Number(h.dataset.gmfqSovereignCount)===count&&
             svg.querySelectorAll('polyline[data-tenor]').length===2;
         },{ccy,count:expected.length},{timeout:17000});
         const proof=await page.evaluate(()=>{
           const d=document.getElementById('gmfq-page').contentDocument,
             h=d.getElementById('rates-chart'),svg=h.querySelector('svg[data-gmfq-sovereign-plot]');
           return {ccy:svg.dataset.ccy,n:Number(h.dataset.gmfqSovereignCount),
             asof:h.querySelector('.gmfq-gov-source')?.textContent||'',
             traces:[...svg.querySelectorAll('polyline[data-tenor]')].map(x=>({
               tenor:x.dataset.tenor,n:(x.getAttribute('points')||'').trim().split(/\s+/).length
             }))};
         });
         if(proof.ccy!==ccy||proof.n!==expected.length||
            proof.traces.length!==2||proof.traces.some(x=>x.n!==expected.length)||
            !proof.asof.includes(src.date))
           throw Error(name+' public truncated 2Y/10Y plot '+ccy+' '+JSON.stringify(proof));
         plotSummary.push({ccy,points:proof.n,date:src.date});
       }
       console.log('PUBLIC_V10_G8_SOVEREIGN_VISUAL_SOURCE_PARITY_GREEN',name,
         JSON.stringify({script:navigationVersion,plots:plotSummary}));
     }
     // The PR preview is checked by local browser QA. On merged main,
     // certify what public GitHub Pages ACTUALLY renders (not only bundle SHA):
     // 8 visible panels, explicit 3M/6M/12M, dated source type and no fake OIS.
     if(process.env.GITHUB_EVENT_NAME!=='pull_request' &&
        addonVersion==='ois-g8-source-visual-20261101'){
       let cardsReady=false;
       for(let attempt=0;attempt<12;attempt++){
         try{
           await page.waitForFunction(()=>{
             const d=document.getElementById('gmfq-page')?.contentDocument;
             return d?.getElementById('gmfq-g8-mini-charts')?.dataset.miniCurves==='8'&&
               !!d.querySelector('#gmfq-g8-mini-charts .gmfq-mini-key')&&
               d.querySelectorAll('#gmfq-g8-mini-charts article[data-chart-ccy]').length===8;
           },null,{timeout:7500});
           cardsReady=true;break;
         }catch(_){
           await page.goto(BASE+'?oisVisual='+Date.now()+'-'+attempt+'#/tassi?focus=ois',
             {waitUntil:'domcontentloaded',timeout:120000});
         }
       }
       if(!cardsReady)throw Error(name+' public OIS visual source-grade build not served by CDN');
       const ui=await page.evaluate(()=>{
         const d=document.getElementById('gmfq-page').contentDocument,
           root=d.getElementById('gmfq-g8-mini-charts');
         return {legend:root.querySelector('.gmfq-mini-key')?.textContent,
           width:d.documentElement.scrollWidth,client:d.documentElement.clientWidth,
           cards:[...root.querySelectorAll('article[data-chart-ccy]')].map(x=>({
             ccy:x.dataset.chartCcy,quality:x.dataset.quality,
             instrument:x.dataset.instrument,points:Number(x.dataset.points),
             missing:Number(x.dataset.missingTenors),joined:x.dataset.joined,
             lines:x.querySelectorAll('svg path').length,
             slots:[...x.querySelectorAll('.gmfq-mini-values [data-horizon]')].map(z=>({
               tenor:z.dataset.horizon,status:z.dataset.pointState,
               label:z.textContent
             }))
           }))};
       });
       if(ui.cards.length!==8||ui.width>ui.client+16||
          !ui.legend?.includes('Futures indicativi')||
          !ui.legend?.includes('Contestati')||
          !ui.legend?.includes('Scenario NZD'))
         throw Error(name+' public G8 OIS source legend/viewport failed '+JSON.stringify(ui));
       const expected={GBP:'DIRECT_OIS',AUD:'OFFICIAL_FUTURES',CAD:'OFFICIAL_FUTURES',
         JPY:'OFFICIAL_FUTURES',NZD:'MODEL_SCENARIO'};
       for(const c of ui.cards){
         const instrument=expected[c.ccy]||
           (c.quality==='CONFLICTED'?'CONTESTED_FUTURES':'INDICATIVE_FUTURES');
         if(c.instrument!==instrument||c.slots.map(z=>z.tenor).join(',')!=='3m,6m,12m'||
            c.slots.filter(z=>z.status==='MISSING').length!==c.missing||
            c.missing!==3-c.points||
            (c.quality!=='OFFICIAL'&&(c.joined!=='false'||c.lines!==0)))
          throw Error(name+' source-sensitive 3M/6M/12M chart failed '+JSON.stringify(c));
         if(c.quality==='CONFLICTED'&&!c.slots.some(z=>z.status==='DISPUTED'))
          throw Error(name+' disputed individual quote is not visibly marked '+JSON.stringify(c));
         if(c.ccy==='CHF'&&c.points===1&&c.missing!==2)
          throw Error(name+' CHF isolated 12M promoted to curve');
       }
       console.log('PUBLIC_G8_OIS_SOURCE_GRADED_390_1440_GREEN',name,
         JSON.stringify(ui.cards.map(c=>({ccy:c.ccy,points:c.points,missing:c.missing,instrument:c.instrument}))));
     }
     // In PR the public website still has the previous addon; inspect the
     // new market-research panel only on main, after the exact deployment.
     if(process.env.GITHUB_EVENT_NAME!=='pull_request'){
       // Source-derived independent expectation from the same public
       // canonical feeds. A previous CDN script can render eight rows yet
       // incorrectly suppress valid individually dated USD/CHF contracts.
       const actualFeeds=await page.evaluate(async()=>{
         const base='https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/main/live_data/sections/';
         const [o,n]=await Promise.all(['OIS_OPERATIONAL_VIEW.json','NZD_CB_PRICING_DIRECTIONAL_PROXY.json'].map(async file=>{
           const response=await fetch(base+file,{cache:'no-store'});
           if(!response.ok)throw Error('public research source HTTP '+response.status+' '+file);
           return response.json();
         }));
         return {ois:o,nzd:n};
       });
       const expectedTiers=Object.fromEntries(
         expectedOisResearchMatrix(actualFeeds.ois,actualFeeds.nzd,romeTodayIso())
           .map(x=>[x.ccy,x.tier]));
       const expectedKeys=['USD','EUR','GBP','JPY','AUD','CAD','NZD','CHF'];
       let newResearchVisible=false,latestResearch=null;
       // GitHub branch parity is earlier than Pages build/CDN convergence.
       // Allow bounded real-time propagation; do not mark a stale build GREEN.
       for(let attempt=0;attempt<24;attempt++){
         try{
           await page.waitForFunction(()=>{
             const d=document.getElementById('gmfq-page')?.contentDocument;
             const r=d?.getElementById('gmfq-ois-research-estimates');
             return r?.dataset.status==='RESEARCH_ONLY'&&
               r.querySelectorAll('.gmfq-est-row[data-ccy]').length===8;
           },null,{timeout:7000});
           latestResearch=await page.evaluate(expected=>{
             const d=document.getElementById('gmfq-page').contentDocument,
               panel=d.getElementById('gmfq-ois-research-estimates'),
               rows=[...panel.querySelectorAll('.gmfq-est-row[data-ccy]')];
             return {
               exactAddon:[...document.scripts].some(x=>
                 x.src.endsWith('ois-pricing-estimates-v1.js?v='+expected)),
               states:Object.fromEntries(rows.map(x=>[x.dataset.ccy,x.dataset.estimateType]))
             };
           },addonVersion);
           const exactStates=latestResearch.exactAddon&&
             expectedKeys.every(k=>latestResearch.states[k]===expectedTiers[k]);
           if(exactStates){newResearchVisible=true;break;}
           console.log('PUBLIC_OIS_ADDON_CDN_PENDING',name,attempt,
             JSON.stringify({expectedVersion:addonVersion,expectedTiers,observed:latestResearch}));
         }catch(error){
           console.log('PUBLIC_OIS_RESEARCH_WAIT',name,attempt,String(error).slice(0,180));
         }
         if(attempt<23){
           await page.waitForTimeout(3000);
           await page.goto(BASE+'?oisResearch='+Date.now()+'-'+attempt+'#/tassi?focus=ois',
             {waitUntil:'domcontentloaded',timeout:120000});
         }
       }
       if(!newResearchVisible)throw Error(name+
         ' public OIS addon version or source classification not converged '+
         JSON.stringify({expectedVersion:addonVersion,expectedTiers,observed:latestResearch}));
       console.log('PUBLIC_OIS_ADDON_VERSION_AND_DYNAMIC_SOURCE_TIERS_GREEN',
         name,JSON.stringify({version:addonVersion,tiers:expectedTiers}));
       const estimateProof=await page.evaluate(()=>{
         const d=document.getElementById('gmfq-page').contentDocument;
         const p=d.getElementById('gmfq-ois-research-estimates');
         const rows=[...p.querySelectorAll('.gmfq-est-row[data-ccy]')];
         return {count:rows.length,keys:rows.map(x=>x.dataset.ccy),
           states:Object.fromEntries(rows.map(x=>[x.dataset.ccy,x.dataset.estimateType])),
           core:p.dataset.coreEffect,promote:p.dataset.officialPromotion,
           caveat:p.textContent.includes('non intervallo statistico'),
           width:d.documentElement.scrollWidth,viewport:d.documentElement.clientWidth};
       });
       if(estimateProof.count!==8||!['USD','EUR','GBP','JPY','AUD','CAD','NZD','CHF'].every(k=>estimateProof.keys.includes(k))||
          estimateProof.core!=='NONE'||estimateProof.promote!=='false'||!estimateProof.caveat||
          estimateProof.width>estimateProof.viewport+16)
         throw Error(name+' public G8 pricing estimate / mobile transparency failed '+JSON.stringify(estimateProof));
       console.log('CONTROL_ROOM_PUBLIC_G8_PRICING_ESTIMATES_GREEN',name,JSON.stringify(estimateProof));
        if(process.env.GITHUB_EVENT_NAME!=='pull_request'){
          const compact=await page.evaluate(()=>{
            const p=document.getElementById('gmfq-page').contentDocument.getElementById('gmfq-ois-research-estimates');
            const details=p?.querySelector('.gmfq-est-disclosure');
            return {open:details?.open===true,visible:!!p?.querySelector('.gmfq-est-table')?.getClientRects().length,
              note:p?.querySelector('.gmfq-est-quick-read')?.textContent,
              count:p?.querySelectorAll('.gmfq-est-row[data-ccy]').length};
          });
          if(!compact.open||!compact.visible||compact.count!==8||
             !compact.note?.includes('valute con riferimenti numerici'))
            throw Error('Public G8 Rates numerical references not visible: '+JSON.stringify(compact));
          await page.frameLocator('#gmfq-page').locator('#gmfq-ois-research-estimates .gmfq-est-disclosure > summary').click();
          const closed=await page.evaluate(()=>{
            const p=document.getElementById('gmfq-page').contentDocument.getElementById('gmfq-ois-research-estimates');
            return !p?.querySelector('.gmfq-est-disclosure')?.open&&!p?.querySelector('.gmfq-est-table')?.getClientRects().length;
          });
          if(!closed)throw Error('Public G8 pricing table cannot be collapsed');
        }
       let visible=false;
       for(let attempt=0;attempt<12;attempt++){
         visible=await page.evaluate(()=>!!document.getElementById('gmfq-page')?.contentDocument?.getElementById('gmfq-pricing-research'));
         if(visible)break;
         await page.goto(BASE+'?pricingQA='+Date.now()+'-'+attempt+'#/tassi?focus=ois',{waitUntil:'domcontentloaded',timeout:120000});
         await page.waitForTimeout(3500);
       }
       if(!visible)throw Error(name+' public Rates research panel never appeared in the canonical Preview');
       // Main and gh-pages may already agree while the Pages CDN still serves
       // an older iframe bundle. Require the NEW SNB 10Y read-only panel DOM
       // before asserting the new feature. Avoid mistaking deploy lag for a
       // pricing/source regression; do not accept only the old Rates panel.
       let snbVersionVisible=false;
       for(let attempt=0;attempt<18;attempt++){
         snbVersionVisible=await page.evaluate(()=>{
           const d=document.getElementById('gmfq-page')?.contentDocument;
           return !!d?.getElementById('gmfq-chf-snb-10y-context')&&!!d?.getElementById('gmfq-source-readiness');
         });
         if(snbVersionVisible)break;
         await page.goto(BASE+'?snb10qa='+Date.now()+'-'+attempt+'#/tassi?focus=ois',{waitUntil:'domcontentloaded',timeout:120000});
         try{
           await page.waitForFunction(()=>{
             const d=document.getElementById('gmfq-page')?.contentDocument;
             return !!d?.getElementById('gmfq-chf-snb-10y-context')&&!!d?.getElementById('gmfq-source-readiness');
           },null,{timeout:9000});
         }catch(_){console.log('PUBLIC_V10_SNB_VERSION_PENDING',name,attempt)}
         await page.waitForTimeout(4000);
       }
       if(!snbVersionVisible){
         snbVersionVisible=await page.evaluate(()=>!!document.getElementById('gmfq-page')?.contentDocument?.getElementById('gmfq-source-readiness'));
       }
       if(!snbVersionVisible)throw Error(name+' PUBLIC_V10_CDN_STALE_NO_SNB_VERSION after cache-busted retries');
       // A source's audit dossier must vanish only after a separately
       // certified official transition. The number is source-derived, not four.
       const pendingDossiers=await page.evaluate(async()=>{
         const root='https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/main/live_data/sections/';
         const [access,op]=await Promise.all(['OIS_SOURCE_READINESS_VIEW.json','OIS_OPERATIONAL_VIEW.json'].map(async f=>{
           const response=await fetch(root+f,{cache:'no-store'});
           if(!response.ok)throw Error('public source-readiness HTTP '+response.status);
           return response.json();
         }));
         const keys=Object.keys(access.currencies||{}).sort();
         const pending=Object.keys(op.currencies||{}).filter(c=>
           op.currencies[c].operational_status!=='GREEN_OFFICIAL').sort();
         if(pending.length!==keys.length||
            !keys.every((c,i)=>c===pending[i]&&
              ['WITHHELD','GREEN_ESTIMATED'].includes(access.currencies[c]?.status))||
            access.blocked_currency_count!==keys.filter(c=>access.currencies[c].status==='WITHHELD').length)
           throw Error('source-readiness pending/official identity divergence');
         return {count:keys.length,codes:keys};
       });
       // GitHub Pages CDN may serve a former addon temporarily. Require the
       // exact approved adapter and the currently outstanding source dossiers.
       if(process.env.GITHUB_EVENT_NAME!=='pull_request'){
         let realReadiness=false;
         for(let probe=0;probe<15;probe++){
           realReadiness=await page.evaluate(arg=>{
             const frame=document.getElementById('gmfq-page')?.contentDocument;
             return [...document.scripts].some(el=>
               el.src.endsWith('home-navigation-v10.js?v='+arg.version))&&
               frame?.querySelectorAll('#gmfq-source-readiness .gmfq-source-row').length===arg.count&&
               frame?.querySelectorAll('#gmfq-source-readiness .gmfq-source-link a').length===arg.count;
           },{version:navigationVersion,count:pendingDossiers.count});
           if(realReadiness)break;
           await page.goto(BASE+'?readinessQA='+Date.now()+'-'+probe+'#/tassi?focus=ois',
             {waitUntil:'domcontentloaded',timeout:120000});
           try{
             await page.waitForFunction(arg=>{
               const d=document.getElementById('gmfq-page')?.contentDocument;
               return [...document.scripts].some(el=>
                 el.src.endsWith('home-navigation-v10.js?v='+arg.version))&&
                 d?.querySelectorAll('#gmfq-source-readiness .gmfq-source-row').length===arg.count&&
                 d?.querySelectorAll('#gmfq-source-readiness .gmfq-source-link a').length===arg.count;
             },{version:navigationVersion,count:pendingDossiers.count},{timeout:9000});
           }catch(_){console.log('PUBLIC_SOURCE_READINESS_CDN_PENDING',name,probe)}
           await page.waitForTimeout(2000);
         }
         if(!realReadiness)realReadiness=await page.evaluate(arg=>{
           const d=document.getElementById('gmfq-page')?.contentDocument;
           return [...document.scripts].some(x=>x.src.endsWith('home-navigation-v10.js?v='+arg.version))&&
              d?.querySelectorAll('#gmfq-source-readiness .gmfq-source-row').length===arg.count&&
              d?.querySelectorAll('#gmfq-source-readiness .gmfq-source-link a').length===arg.count;
         },{version:navigationVersion,count:pendingDossiers.count});
         if(!realReadiness)throw Error(name+' PUBLIC_READINESS_VERSION_NOT_DEPLOYED_OR_UNAVAILABLE');
       }
       await page.waitForFunction(()=>{
         const d=document.getElementById('gmfq-page')?.contentDocument;
         return d?.getElementById('gmfq-pricing-research')?.querySelector('.gmfq-research-plot svg, .gmfq-research-plot p');
       },null,{timeout:20000});
       if(process.env.GITHUB_EVENT_NAME!=='pull_request'){
         // Compare against currently published, dated canonical G8 yields.
         // An AUD observation from Oct 21 is historical on Oct 26; its
         // source status must not be "repaired" or hidden to appease QA.
         const publicRates=await page.evaluate(async()=>{
           const res=await fetch('/global-macro-fx-quant/live_data/sections/NATIVE_RATES_DATA.json',
             {cache:'no-store'});
           if(!res.ok)throw Error('Public canonical rates HTTP '+res.status);
           return res.json();
         });
         const today=romeTodayIso();
         const sourceDate=day=>{
           if(!/^20\d{2}-\d{2}-\d{2}$/.test(day||''))return null;
           const v=Date.parse(day+'T00:00:00Z');
           return Number.isFinite(v)&&new Date(v).toISOString().slice(0,10)===day?v:null;
         };
         const nowDay=sourceDate(today);
         const yieldExpected=Object.fromEntries(
           ['USD','EUR','GBP','JPY','AUD','CAD','NZD','CHF'].map(ccy=>{
             const r=publicRates[ccy],day=sourceDate(r?.date);
             const valid=day!==null&&day<=nowDay&&typeof r?.quality==='string'&&
               r.quality.includes('OFFICIAL')&&['2Y','10Y'].every(t=>{
                 const h=t==='2Y'?r.history2:r.history10;
                 return Number.isFinite(r[t])&&Array.isArray(h?.dates)&&
                   Array.isArray(h?.values)&&h.dates.length>=20&&
                   h.dates.length===h.values.length&&h.dates.at(-1)===r.date&&
                   Number.isFinite(h.values.at(-1))&&
                   Math.abs(h.values.at(-1)-r[t])<=0.00001&&r[t]>-5&&r[t]<25;
               });
             return [ccy,!valid?'UNAVAILABLE':(nowDay-day)/86400000>4?'HISTORICAL':'RECENT'];
           }));
         const y=await page.evaluate(()=>{
           const d=document.getElementById('gmfq-page')?.contentDocument,
             p=d?.getElementById('gmfq-yields-study');
           return {present:!!p,count:p?.querySelectorAll('.gmfq-yield-row[data-ccy]').length,
             verified:p?.dataset.coverage,core:p?.dataset.coreEffect,pair:p?.dataset.pairEffect,
             states:[...p?.querySelectorAll('.gmfq-yield-row[data-ccy]')||[]].map(x=>({ccy:x.dataset.ccy,state:x.dataset.state})),
             historical:[...p?.querySelectorAll('.gmfq-yield-row[data-state="HISTORICAL"]')||[]].map(x=>x.dataset.ccy),
             snb:p?.querySelector('[data-snb-10y="SEPARATE"]')?.textContent,
             width:p?.scrollWidth,client:p?.clientWidth};
         });
         if(!y.present||y.verified!=='8'||y.count!==8||
            y.core!=='NONE'||y.pair!=='NONE'||
            y.states?.length!==8||y.states.some(x=>yieldExpected[x.ccy]!==x.state)||
            JSON.stringify([...y.historical].sort())!==JSON.stringify(
              Object.entries(yieldExpected).filter(([,status])=>status==='HISTORICAL')
               .map(([ccy])=>ccy).sort())||
            !y.snb?.includes('non calcolare spread misti')||
            y.width>y.client+2)
            throw Error(name+' G8 dated yields missing from public Rates research '+JSON.stringify(y));
         console.log('CONTROL_ROOM_PUBLIC_G8_DATED_YIELDS_STUDY_GREEN',name,
           JSON.stringify({count:y.count,historical:y.historical,expected:yieldExpected,noModelPromotion:true}));
         // Public regression: original G8 government table must not show blanks for CHF/NZD.
         if(process.env.GITHUB_EVENT_NAME!=='pull_request'){
           const rows=await page.evaluate(()=>{
             const d=document.getElementById('gmfq-page')?.contentDocument;
             return ['NZD','CHF'].map(ccy=>{
               const tr=[...d?.querySelectorAll('#rates-rows > tr')||[]].find(x=>
                 x.cells[0]?.textContent.includes(ccy==='NZD'?'Nuova Zelanda':'Svizzera'));
               return {ccy,asof:tr?.dataset.gmfqHistoricalYield,usDay:tr?.dataset.gmfqHistoricalSpreadDate,
                 visible:!!tr?.getClientRects().length,cells:[...tr?.cells||[]].map(x=>x.textContent.trim())};
             });
           });
           for(const r of rows){
             const source=publicRates[r.ccy];
             if(!r.visible||r.asof!==source.date||!r.usDay||r.usDay>source.date||
               !r.cells[0]?.includes('STORICO '+source.date)||
               !r.cells[1]?.includes(source['2Y'].toFixed(3)+'%')||
               !r.cells[2]?.includes(source['10Y'].toFixed(3)+'%')||
               !r.cells[3]?.includes(' bp')||
               !r.cells[4]?.includes('data comune '+r.usDay)||
               !r.cells[6]?.includes('CERTIFICATO · STORICO'))
               throw Error(name+' public original G8 government table missing dated CHF/NZD '+JSON.stringify(r));
           }
           console.log('CONTROL_ROOM_PUBLIC_NATIVE_G8_CHF_NZD_DATED_GREEN',name,JSON.stringify(rows));
         }
         const webReview=await page.evaluate(async()=>{
           const d=document.getElementById('gmfq-page')?.contentDocument,
             p=d?.getElementById('gmfq-yields-study'),
             note=p?.querySelector('[data-nzd-web-review="RESEARCH_UNAPPROVED"]'),
             raw=await fetch('https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/main/live_data/sections/NATIVE_RATES_DATA.json',{cache:'no-store'}).then(x=>x.json());
           return {liveNZD:raw.NZD?.date,status:p?.dataset.nzdWebReview,
             note:note?.textContent,noteDate:note?.textContent?.includes('2026-10-22'),
             noteLink:note?.querySelector('a')?.getAttribute('href'),core:p?.dataset.coreEffect,pair:p?.dataset.pairEffect};
         });
         const noteExpected=webReview.liveNZD==='2026-10-16';
         if(webReview.core!=='NONE'||webReview.pair!=='NONE'||
            (noteExpected&&(webReview.status!=='RESEARCH_UNAPPROVED'||!webReview.noteDate||
              !webReview.note?.includes('3.910%')||!webReview.note?.includes('4.980%')||
              !webReview.note?.includes('NON APPROVATO')||
              !webReview.noteLink?.startsWith('https://www.rbnz.govt.nz/')))||
            (!noteExpected&&webReview.status!=='UNAVAILABLE'))
           throw Error(name+' RBNZ web-review must remain study only '+JSON.stringify(webReview));
         console.log('CONTROL_ROOM_PUBLIC_NZD_B2_UNAPPROVED_STUDY_GREEN',name,
           JSON.stringify({reviewStatus:webReview.status,liveNZD:webReview.liveNZD}));
       }
       const research=await page.evaluate(async()=>{
         const d=document.getElementById('gmfq-page').contentDocument;
         const panel=d.getElementById('gmfq-pricing-research');
         const feed=await fetch('https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/main/live_data/sections/OIS_OPERATIONAL_VIEW.json',{cache:'no-store'}).then(x=>x.json());
         const snb=await fetch('https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/main/live_data/sections/CHF_SNB_10Y_SPOT_CONTEXT.json',{cache:'no-store'}).then(x=>x.json());
         const access=await fetch('https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/main/live_data/sections/OIS_SOURCE_READINESS_VIEW.json',{cache:'no-store'}).then(x=>x.json());
         const days=x=>(Date.parse(window.GMFQ_OIS_RESEARCH_V1.romeTodayIso()+'T00:00:00Z')-Date.parse(x+'T00:00:00Z'))/86400000;
         const eligible=Object.keys(feed.currencies||{}).filter(k=>{
           const x=feed.currencies?.[k];
           return x?.operational_status==='GREEN_OFFICIAL'&&x.official_status==='ACTIVE'&&
             x.quality==='OFFICIAL_CERTIFIED'&&x.backtest_eligible_as_official===true&&
             days(x.as_of)>=0&&days(x.as_of)<=4&&['3m','6m','12m'].every(t=>Number.isFinite(x.horizons?.[t]?.policy_delta_bp));
         });
         const secondary=['USD','EUR','CHF'].filter(k=>feed.currencies?.[k]?.operational_status==='WITHHELD'&&
           feed.currencies?.[k]?.secondary_quote_context?.full_curve_usable===false&&
           feed.currencies?.[k]?.secondary_quote_context?.policy_delta_allowed===false);
         return {
           actualCurves:panel.querySelectorAll('.gmfq-research-plot svg g[data-graded-ccy]').length,
            expectedCurves:eligible.length,
            gradedRows:[...panel.querySelectorAll('.gmfq-research-plot svg g[data-graded-ccy]')].map(x=>({
              ccy:x.dataset.gradedCcy,tier:x.dataset.quality,
              points:x.querySelectorAll('circle').length,
              expectedPoints:Number(x.dataset.verifiedTenors),
              labels:[...x.querySelectorAll('circle title')].map(y=>y.textContent),
              joined:x.dataset.joined,lines:x.querySelectorAll('polyline').length
            })),
           secondaryCards:panel.querySelectorAll('.gmfq-quote-card').length,expectedCards:secondary.length,
           note:panel.textContent,docWidth:d.documentElement.scrollWidth,viewport:d.documentElement.clientWidth,
           readinessCount:panel.querySelectorAll('#gmfq-source-readiness .gmfq-source-row').length,
           readinessLinks:panel.querySelectorAll('#gmfq-source-readiness a').length,
           readinessCodes:[...panel.querySelectorAll('#gmfq-source-readiness .gmfq-source-row')].map(x=>x.dataset.sourceCcy).sort(),
           readinessContent:panel.querySelector('#gmfq-source-readiness')?.textContent,
           readinessExpected:access?.schema==='GMFQ_OIS_SOURCE_READINESS_VIEW_V1'&&
             access.status==='READ_ONLY_SOURCE_READINESS'&&access.prices_omitted===true&&
             access.no_automatic_promotions===true&&days(access.as_of)>=0&&days(access.as_of)<=3&&
             Object.keys(access.currencies||{}).length===
               Object.values(feed.currencies||{}).filter(x=>x.operational_status!=='GREEN_OFFICIAL').length&&
             Object.keys(access.currencies||{}).every(k=>
               ['WITHHELD','GREEN_ESTIMATED'].includes(access.currencies?.[k]?.status)&&
               access.currencies[k].status===feed.currencies?.[k]?.operational_status&&
               access.currencies[k].usable_for_policy_pricing===false&&
               access.currencies[k].backtest_eligible_as_official===false)&&
             access.blocked_currency_count===
               Object.values(access.currencies||{}).filter(x=>x.status==='WITHHELD').length?
             Object.keys(access.currencies||{}).length:null,
           snbBox:panel.querySelector('#gmfq-chf-snb-10y-context')?.textContent,
           snbExpected:snb?.schema==='GMFQ_CHF_SNB_10Y_SPOT_CONTEXT_V1'&&snb.status==='OFFICIAL_PUBLISHED_10Y_INFORMATIONAL'&&
             snb.has_current_2y===false&&snb.eligible_for_curve_spreads===false&&snb.eligible_for_core_signals===false&&
             Number.isFinite(snb.value_percent)&&days(snb.as_of)>=0&&days(snb.as_of)<=4?
             {value:snb.value_percent.toFixed(3),date:snb.as_of}:null
         };
       });
       if(research.actualCurves!==8||
           new Set(research.gradedRows.map(x=>x.ccy)).size!==8||
           research.gradedRows.some(x=>x.points<1||x.points>3||
             x.expectedPoints!==x.points||
             !['OFFICIAL','PROXY','MIXED','CONFLICTED','SCENARIO'].includes(x.tier)||
             (x.points<3&&(x.joined!=='false'||x.lines!==0||
               !x.labels.every(t=>t.includes('SCADENZA ISOLATA NON CURVA'))))||
             (['MIXED','CONFLICTED'].includes(x.tier)&&
               (x.joined!=='false'||x.lines!==0)))||
           (research.gradedRows.some(x=>x.points<3)&&
             !research.note.includes('Copertura parziale:'))||
           !research.gradedRows.some(x=>x.ccy==='CHF'&&x.tier==='PROXY'&&
             x.points>=1&&x.joined==='false'&&x.lines===0)||
           !research.note.includes('Grafico G8 3M/6M/12M: 8/8')||
           !research.note.includes('Curve certificate: '+research.expectedCurves+'/8')||
           research.secondaryCards!==research.expectedCards||
          (research.expectedCards>0 && !research.note.includes('non sono una curva OIS'))||
          (research.expectedCards===0 && !research.note.includes('GREEN_ESTIMATED restano indicative'))||
          !research.note.includes('NON curva OIS né policy delta')||
          (process.env.GITHUB_EVENT_NAME!=='pull_request'&&(
             research.readinessExpected===null||
             research.readinessCount!==research.readinessExpected||
             research.readinessLinks!==research.readinessExpected||
             JSON.stringify(research.readinessCodes)!==JSON.stringify(pendingDossiers.codes)||
             !research.readinessContent?.includes('Nessun dato indicativo è promosso')||
             !research.readinessContent?.includes('non completa il 2Y')||
             !research.readinessContent?.includes('Il loro stato di accesso può essere precedente al runtime operativo')))||
          research.docWidth>research.viewport+16||
          (research.snbExpected?
             !research.snbBox?.includes('CHF 10Y SNB '+research.snbExpected.value+'%')||
             !research.snbBox.includes(research.snbExpected.date)||
             !research.snbBox.includes('SOLO INFORMATIVO')||
             !research.snbBox.includes('nessuno spread o segnale'):
             !research.snbBox?.includes('non disponibile o non corrente')))
         throw Error(name+' public certified/secondary Rates research fail-closed contract '+JSON.stringify(research));
       // The deployed version must show the conclusion first while retaining
       // the old certified curves and sources in accessible details.
       if(process.env.GITHUB_EVENT_NAME!=='pull_request'){
         const reading=await page.evaluate(()=>{
           const d=document.getElementById('gmfq-page')?.contentDocument,
             p=d?.getElementById('gmfq-pricing-research'),
             det=p?.querySelector('#gmfq-pricing-evidence-details');
           return {status:p?.dataset.sourceStatus,curves:p?.dataset.verifiedCurves,
             estimated:p?.dataset.estimatedLanes,withheld:p?.dataset.withheldLanes,
             closed:det?.open===false,
             heading:p?.querySelector('.gmfq-pricing-core-status')?.textContent,
              note:p?.querySelector('.gmfq-research-note')?.textContent,
             plotVisible:!!p?.querySelector('.gmfq-research-plot')?.getClientRects().length,
             secondaryHidden:!(p?.querySelector('.gmfq-quote-card')?.getClientRects().length),
             sourcePresent:!!p?.querySelector('#gmfq-source-readiness')};
         });
         if(reading.status!=='READ_ONLY'||Number(reading.curves)!==research.expectedCurves||
            !reading.closed||!reading.plotVisible||!reading.secondaryHidden||
            !reading.sourcePresent||!reading.heading?.includes('/8')||
             !reading.note?.startsWith('Le curve sintetizzano prezzi per scadenza'))
           throw Error(name+' public Rates decision-first not visible '+JSON.stringify(reading));
         await page.frameLocator('#gmfq-page').locator('#gmfq-pricing-evidence-details>summary').press('Enter');
         const disclosure=await page.evaluate(()=>{
           const d=document.getElementById('gmfq-page')?.contentDocument,
             p=d?.getElementById('gmfq-pricing-research');
           return {open:p?.querySelector('#gmfq-pricing-evidence-details')?.open,
             secondaryVisible:!!p?.querySelector('.gmfq-quote-card')?.getClientRects().length,
             chfVisible:!!p?.querySelector('#gmfq-chf-snb-10y-context')?.getClientRects().length};
         });
         if(!disclosure.open||!disclosure.chfVisible||
            (research.expectedCards>0&&!disclosure.secondaryVisible))
           throw Error(name+' public source drilldown lost '+JSON.stringify(disclosure));
         console.log('CONTROL_ROOM_V10_RATES_RESEARCH_FIRST_PUBLIC_GREEN',name,reading);
       }
       console.log('CONTROL_ROOM_PREVIEW_PUBLIC_PRICING_RESEARCH_GREEN',name,
         JSON.stringify({curves:research.actualCurves,secondary:research.secondaryCards,viewport:research.viewport}));
     }
     await page.goto(BASE+'#/home',{waitUntil:'domcontentloaded',timeout:120000});
     await page.waitForFunction(()=>document.getElementById('gmfq-page')?.contentDocument?.querySelectorAll('#pairs tr[data-filter]').length>0,null,{timeout:60000});
     // GitHub Pages can serve the previous add-on after main/gh-pages SHA parity.
     // Before testing the new Home pair route, require the exact new loader
     // script version in the ACTUAL public browser, not merely in the repo.
     if(process.env.GITHUB_EVENT_NAME!=='pull_request'){
       let current=false;
       for(let attempt=0;attempt<16;attempt++){
         current=await page.evaluate(expected=>{
           return [...document.scripts].some(x=>x.src.endsWith('home-navigation-v10.js?v='+expected));
         },navigationVersion);
         if(current)break;
         console.log('PUBLIC_PAIR_ADDON_CDN_PENDING',name,attempt);
         await page.goto(BASE+'?pairqa='+Date.now()+'-'+attempt+'#/home',
           {waitUntil:'domcontentloaded',timeout:120000});
         try{await page.waitForFunction(()=>{
           const d=document.getElementById('gmfq-page')?.contentDocument;
           return d?.documentElement?.dataset.liveState==='LOADED'&&d.querySelectorAll('#pairs tr[data-filter]').length>0;
         },null,{timeout:12000});}
         catch(_){console.log('PUBLIC_PAIR_HOME_FEED_PENDING',name,attempt)}
         await page.waitForTimeout(3000);
       }
       if(!current)current=await page.evaluate(expected=>
         [...document.scripts].some(x=>x.src.endsWith('home-navigation-v10.js?v='+expected)),navigationVersion);
       if(!current)throw Error(name+' PUBLIC_PAIR_ADDON_VERSION_NOT_DEPLOYED');
     }
     const homePair=await page.frameLocator('#gmfq-page').locator('#pairs tr[data-filter]').first().getAttribute('data-filter');
     if(!/^[A-Z]{6}$/.test(homePair||''))throw Error(name+' Preview Home invalid pair deep link '+homePair);
     await page.frameLocator('#gmfq-page').locator('#pairs tr[data-filter]').first().click();
     const oldPublic=process.env.GITHUB_EVENT_NAME==='pull_request';
     // During a PR the already-published website can legitimately serve
     // either the old or the newly deployed pair route. Only post-merge
     // runs demand the NEW route and canonical 28-pair Deep Dive.
     await page.waitForFunction(({code,pr})=>{
       const h=location.hash;
       return h==='#/coppie?pair='+code||(pr&&h==='#/screener?pair='+code);
     },{code:homePair,pr:oldPublic},{timeout:15000});
     if(!oldPublic){
       await page.waitForFunction(code=>{
         const d=document.getElementById('gmfq-page')?.contentDocument;
         return d?.documentElement?.dataset.pairState==='READY'&&
           d.querySelectorAll('#pair-index button.pair-open[data-pair]').length===28&&
           d.getElementById('gmfq-pair-research-path')?.dataset.pair===code;
       },homePair,{timeout:35000});
       if(['pairs-explained-ranking-20261022','pairs-focus-eight-20261022','pairs-first-risk-check-20261023','pairs-top8-overlap-20261023','pairs-dense-first-read-20261023','home-nzd-b2-web-reviewed-20261023','home-nzd-b2-pair-zero-gates-20261024','home-morning-clock-verified-20261024'].includes(navigationVersion)){
         await page.waitForFunction(()=>{
           const d=document.getElementById('gmfq-page')?.contentDocument,p=d?.getElementById('gmfq-pair-rank');
           return p?.dataset.status==='READ_ONLY'&&
             d.querySelectorAll('#pair-index tr[data-research-rank]').length===28;
         },null,{timeout:30000});
         const capture=()=>page.evaluate(()=>{
           const d=document.getElementById('gmfq-page').contentDocument,p=d.getElementById('gmfq-pair-rank'),
             rows=[...d.querySelectorAll('#pair-index tr[data-research-rank]')];
           return {source:p?.dataset.status,mode:p?.dataset.sortMode,signals:p?.dataset.hasTradeRanking,
             count:p?.dataset.count,baseline:p?.dataset.macroAsOf,model:p?.dataset.priceAsOf,
             overlap:(()=>{
               const n=p.querySelector('.gmfq-rank-overlap');
               return {status:n?.dataset.status,source:n?.dataset.source,
                 total:n?.dataset.topCount,risks:n?.dataset.withRisks,
                 max:n?.dataset.frequency,repeated:n?.dataset.mostRepeated,
                 favored:n?.dataset.favoredCount,text:n?.textContent};
             })(),
             view:p?.dataset.viewMode,visibleCount:Number(p?.dataset.visibleCount),
             viewToggles:[...p.querySelectorAll('button[data-pair-view]')].map(x=>({
               value:x.dataset.pairView,pressed:x.getAttribute('aria-pressed')})),
             overflow:p?.scrollWidth>p?.clientWidth+2,
             docWidth:d.documentElement.scrollWidth,viewport:d.documentElement.clientWidth,
             readingMode:p?.dataset.readingMode,
             methodClosed:p?.querySelector('.gmfq-rank-method-detail')?.open===false,
             readingState:(()=>{
               const tb=d.getElementById('pair-index'),row=rows[0],w=d.defaultView;
               return {level:tb?.dataset.researchReading,
                 whyVisible:!!row?.querySelector('.gmfq-row-why')?.getClientRects().length,
                 lensDisplay:row?.querySelector('.gmfq-row-lenses')?
                   w.getComputedStyle(row.querySelector('.gmfq-row-lenses')).display:null,
                 checkDisplay:row?.querySelector('.gmfq-row-next')?
                   w.getComputedStyle(row.querySelector('.gmfq-row-next')).display:null};
             })(),
             rows:rows.map(x=>({code:x.querySelector('button.pair-open')?.dataset.pair,
               rank:Number(x.dataset.researchRank),reason:x.querySelector('.gmfq-row-why')?.textContent,firstCheck:x.querySelector('.gmfq-row-next')?.textContent,checkSource:x.querySelector('.gmfq-row-next')?.dataset.source,visible:!!x.getClientRects().length,selected:x.classList.contains('pair-current')}))};
         });
         const rankedSetup=await capture();
         if(['pairs-dense-first-read-20261023','home-nzd-b2-web-reviewed-20261023','home-nzd-b2-pair-zero-gates-20261024','home-morning-clock-verified-20261024'].includes(navigationVersion)){
           if(rankedSetup.readingMode!=='compact'||rankedSetup.readingState.level!=='compact'||
              !rankedSetup.methodClosed||!rankedSetup.readingState.whyVisible||
              rankedSetup.readingState.lensDisplay!=='none'||
              rankedSetup.readingState.checkDisplay!=='none')
             throw Error(name+' public compact pair reading failed '+JSON.stringify(rankedSetup));
           await page.frameLocator('#gmfq-page').locator('#gmfq-pair-rank button[data-pair-reading="details"]').click();
           const detailed=await capture();
           if(detailed.readingMode!=='details'||detailed.readingState.level!=='details'||
              detailed.readingState.lensDisplay==='none'||
              detailed.readingState.checkDisplay==='none'||
              JSON.stringify(detailed.rows.map(x=>x.code))!==JSON.stringify(rankedSetup.rows.map(x=>x.code)))
             throw Error(name+' public first controls not discoverable '+JSON.stringify(detailed));
           await page.frameLocator('#gmfq-page').locator('#gmfq-pair-rank button[data-pair-reading="compact"]').click();
         }

         const checkPublicOverlap=state=>{
           if(!['pairs-top8-overlap-20261023','pairs-dense-first-read-20261023','home-nzd-b2-web-reviewed-20261023','home-nzd-b2-pair-zero-gates-20261024','home-morning-clock-verified-20261024'].includes(navigationVersion))return;
           const rows=state.rows.slice(0,8),frequency={};
           if(rows.length!==8)throw Error(name+' first-eight overlap needs eight original records');
           for(const item of rows){
             if(!/^[A-Z]{6}$/.test(item.code||''))
               throw Error(name+' invalid published pair code in overlap');
             const a=item.code.slice(0,3),b=item.code.slice(3);
             frequency[a]=(frequency[a]||0)+1;
             frequency[b]=(frequency[b]||0)+1;
           }
           const max=Math.max(...Object.values(frequency));
           const tied=Object.keys(frequency).filter(c=>frequency[c]===max).sort();
           const o=state.overlap;
           if(o?.status!=='OBSERVED'||o?.source!=='PAIR_SETUP_OPERATIONAL_VIEW'||
              o?.total!=='8'||o?.max!==String(max)||o?.repeated!==tied.join(',')||
              !o?.text?.includes('Sovrapposizione valutaria, non correlazione né rischio portafoglio stimati')||
              !/^\d+$/.test(o?.risks||'')||Number(o.risks)>8)
             throw Error(name+' published top-eight overlap missing or incorrectly sourced '+JSON.stringify({o,frequency}));
         };
         checkPublicOverlap(rankedSetup);

         if(rankedSetup.source!=='READ_ONLY'||rankedSetup.signals!=='false'||rankedSetup.count!=='28'||
            rankedSetup.baseline!==pricing.setup_macro_asof||rankedSetup.model!==pricing.setup_date||
            rankedSetup.overflow||rankedSetup.docWidth>rankedSetup.viewport+16||
            rankedSetup.rows.length!==28||
            rankedSetup.rows.some((x,i)=>x.rank!==i+1||!x.reason)||
            new Set(rankedSetup.rows.map(x=>x.code)).size!==28||
            !rankedSetup.rows.find(x=>x.code==='AUDCHF')?.reason.includes('Timing contrario')||
            !rankedSetup.rows.find(x=>x.code==='EURUSD')?.reason.includes('Prezzo già avanzato'))
           throw Error(name+' public ranked pairs or named CON RISCHI constraint absent '+JSON.stringify(rankedSetup));
         if(['pairs-first-risk-check-20261023','pairs-top8-overlap-20261023','pairs-dense-first-read-20261023','home-nzd-b2-web-reviewed-20261023','home-nzd-b2-pair-zero-gates-20261024','home-morning-clock-verified-20261024'].includes(navigationVersion)&&
            rankedSetup.rows.some(x=>!x.firstCheck?.startsWith('Primo controllo · ')||
              x.checkSource!=='PAIR_SETUP_OPERATIONAL_VIEW'))
           throw Error(name+' public source-derived first pair risk checks missing '+JSON.stringify(rankedSetup));
         if(['pairs-focus-eight-20261022','pairs-first-risk-check-20261023','pairs-top8-overlap-20261023','pairs-dense-first-read-20261023','home-nzd-b2-web-reviewed-20261023','home-nzd-b2-pair-zero-gates-20261024','home-morning-clock-verified-20261024'].includes(navigationVersion)){
           const shown=rankedSetup.rows.filter(x=>x.visible);
           if(rankedSetup.view!=='focus'||rankedSetup.visibleCount!==shown.length||
             shown.length<8||shown.length>9||
             rankedSetup.rows.slice(0,8).some(x=>!x.visible)||
             rankedSetup.rows.some(x=>x.rank>8&&x.visible&&!x.selected)||
             rankedSetup.viewToggles[0]?.pressed!=='true')
              throw Error(name+' public compact pair view not source-safe '+JSON.stringify(rankedSetup));
           await page.frameLocator('#gmfq-page').locator('#gmfq-pair-rank button[data-pair-view="all"]').click();
           const expanded=await capture();
           if(expanded.view!=='all'||expanded.visibleCount!==28||expanded.rows.some(x=>!x.visible))
              throw Error(name+' public original 28-pair expansion failed '+JSON.stringify(expanded));
           await page.frameLocator('#gmfq-page').locator('#gmfq-pair-rank button[data-pair-view="focus"]').click();
         }
         await page.frameLocator('#gmfq-page').locator('#gmfq-pair-rank button[data-rank-mode="thesis"]').click();
         const rankedThesis=await capture();
         checkPublicOverlap(rankedThesis);
         if(rankedThesis.mode!=='thesis'||rankedThesis.rows.length!==28||
            rankedThesis.rows[0].code!=='USDCHF'||
            rankedThesis.rows.some((x,i)=>x.rank!==i+1))
           throw Error(name+' public thesis ordering absent '+JSON.stringify(rankedThesis));
         await page.frameLocator('#gmfq-page').locator('#gmfq-pair-rank button[data-rank-mode="setup"]').click();
         console.log('CONTROL_ROOM_PUBLIC_PAIR_28_ORDER_GREEN',name,{
           setup:rankedSetup.rows[0].code,thesis:rankedThesis.rows[0].code});
       }
       // Published Preview: the reader should see the canonical decision first,
       // with optional detailed research present but not overwhelming the page.
       const firstRead=await page.evaluate(()=>{
         const d=document.getElementById('gmfq-page')?.contentDocument;
         const p=d?.getElementById('gmfq-pair-research-path');
         const decision=p?.querySelector('#gmfq-pair-decision-bridge');
         const details=p?.querySelector('#gmfq-pair-full-research');
         return {before:!!decision&&!!details&&
             !!(decision.compareDocumentPosition(details)&Node.DOCUMENT_POSITION_FOLLOWING),
           decisionVisible:!!decision?.getClientRects().length,
           closed:details?.open===false,
           sourcePresent:!!p?.querySelector('#gmfq-pair-macro-rates')};
       });
       if(!firstRead.before||!firstRead.decisionVisible||
          !firstRead.closed||!firstRead.sourcePresent)
         throw Error(name+' public Pair decision-first layout not deployed '+JSON.stringify(firstRead));
       const p=await page.evaluate(()=>{
         const d=document.getElementById('gmfq-page')?.contentDocument;
         return {pairs:d?.querySelectorAll('#pair-index button.pair-open[data-pair]').length,
           buttons:d?.querySelectorAll('#gmfq-pair-research-path button[data-gmfq-study-currency]').length,
           content:d?.getElementById('gmfq-pair-research-path')?.textContent,
           docWidth:d?.documentElement.scrollWidth,viewport:d?.documentElement.clientWidth};
       });
       // A new certified Price overlay can have exactly the SAME date as the
       // latest ECB fixing. It must still disclose the old Macro baseline;
       // the legacy "fixing newer than thesis" sentence is not always true.
       const expectedPriceLabel=process.env.GITHUB_EVENT_NAME==='pull_request'?
         'Modello: ':'Prezzo del modello: ';
       if(p.pairs!==28||p.buttons!==8||
          !p.content?.includes(expectedPriceLabel+pricing.setup_date)||
          !p.content?.includes('Baseline Macro/Tassi: '+pricing.setup_macro_asof)||
          !p.content?.includes('Il dettaglio sopra resta la lettura canonica della tesi')||
          p.docWidth>p.viewport+16)
          throw Error(name+' public Pair Deep Dive date/routing regression '+JSON.stringify(p));
       // On PR, public Pages still serves approved main. Post-merge, verify
       // the actual published research-ledger layout and its mobile stacking.
       if(process.env.GITHUB_EVENT_NAME!=='pull_request'){
         const visual=await page.evaluate(()=>{
           const d=document.getElementById('gmfq-page')?.contentDocument;
           const path=d?.getElementById('gmfq-pair-research-path');
           const stamps=path?.querySelector('.gmfq-path-evidence');
           const cols=path?.querySelector('.gmfq-decision-cols');
           const win=d?.defaultView;
           return {
             keys:[...stamps?.querySelectorAll('span[data-source]')||[]].map(x=>x.dataset.source),
             sourceText:stamps?.textContent,
             macroState:stamps?.dataset.macroState,
             gridCols:cols?win.getComputedStyle(cols).gridTemplateColumns.trim().split(/\s+/).length:0,
             background:cols?.firstElementChild?
               win.getComputedStyle(cols.firstElementChild).backgroundColor:null,
             width:d?.documentElement.scrollWidth,
             viewport:d?.documentElement.clientWidth
           };
         });
         if(JSON.stringify(visual.keys)!==JSON.stringify(['macro','price','fixing'])||
            visual.macroState!=='HISTORICAL'||
            !visual.sourceText?.includes('Prezzo del modello: '+pricing.setup_date)||
            !visual.sourceText?.includes('Baseline Macro/Tassi: '+pricing.setup_macro_asof)||
            visual.sourceText?.includes('Valuta favorita dal motore:')||
            visual.gridCols!==(visual.viewport<=700?1:3)||
            !['transparent','rgba(0, 0, 0, 0)'].includes(visual.background)||
            visual.width>visual.viewport+16)
           throw Error(name+' published Pair first reading visual hierarchy drift '+JSON.stringify(visual));
         console.log('CONTROL_ROOM_PAIR_EDITORIAL_SOURCE_LEDGER_PUBLIC_GREEN',name,
           JSON.stringify({keys:visual.keys,gridCols:visual.gridCols,viewport:visual.viewport}));
       }
       // The approved Pair ranking starts in the compact Top-8 view.
       // EUR/CHF may be below rank 8; reveal all rows through the real user control
       // before testing navigation. Do not bypass visibility with a forced click.
       await page.frameLocator('#gmfq-page').locator('#gmfq-pair-rank button[data-pair-view="all"]').click();
       await page.frameLocator('#gmfq-page').locator('#pair-index button.pair-open[data-pair="EURCHF"]').click();
       await page.waitForFunction(()=>location.hash==='#/coppie?pair=EURCHF',null,{timeout:10000});
       await page.waitForFunction(()=>{
         const d=document.getElementById('gmfq-page')?.contentDocument;
         return d?.getElementById('gmfq-pair-research-path')?.dataset.pair==='EURCHF';
       },null,{timeout:14000});
       if(process.env.GITHUB_EVENT_NAME!=='pull_request'){
         // New read-only comparative panel ships with this PR. The public
         // branch may still serve its prior version, but postmerge QA MUST see
         // Macro side + Tassi/CB labels, CHF stale, and two-date gap policy.
         const pairMacro=await page.evaluate(()=>{
           const d=document.getElementById('gmfq-page')?.contentDocument;
           const c=d?.getElementById('gmfq-pair-macro-rates');
           return {present:!!c,macro:c?.querySelectorAll('.gmfq-compare-score strong').length,
             spreadSame:c?.querySelector('.gmfq-compare-spread')?.dataset.sameDate,
             spreadText:c?.querySelector('.gmfq-compare-spread')?.textContent,
             text:c?.textContent,
             width:d?.documentElement.scrollWidth,viewport:d?.documentElement.clientWidth};
         });
         if(!pairMacro.present||pairMacro.macro!==2||
            pairMacro.spreadSame!=='false'||!pairMacro.spreadText?.includes('WITHHELD')||
            !pairMacro.text?.includes('CHF')||
            !pairMacro.text?.includes('I giudizi Macro e Tassi/CB sono quelli dello snapshot del motore')||
            pairMacro.width>pairMacro.viewport+16)
           throw Error(name+' public pair Macro/Rates source guard absent '+JSON.stringify(pairMacro));
         const change=await page.evaluate(()=>{
           const d=document.getElementById('gmfq-page')?.contentDocument;
           const c=d?.getElementById('gmfq-pair-what-changed');
           return {exists:!!c,baseline:c?.dataset.macroBaselineAsOf,
             price:c?.dataset.pairPriceAsOf,baselineState:c?.dataset.macroBaselineState,
             summary:c?.querySelector('.gmfq-change-summary')?.textContent,
             legs:[...c?.querySelectorAll('.gmfq-change-leg')||[]].map(x=>({
             ccy:x.dataset.gmfqChangeCurrency,status:x.dataset.gmfqYieldChange,
             text:x.querySelector('.gmfq-change-measured')?.textContent,
             model:x.querySelector('.gmfq-change-model')?.textContent})),
             note:c?.querySelector('.gmfq-change-warning')?.textContent,
             width:d?.documentElement.scrollWidth,viewport:d?.documentElement.clientWidth};
         });
         if(!change.exists||change.legs.length!==2||
            change.baseline!==pricing.setup_macro_asof||
            change.price!==pricing.setup_date||
            change.baselineState!=='HISTORICAL'||
            !change.summary?.includes('baseline Macro/Tassi '+pricing.setup_macro_asof)||
            change.legs.find(x=>x.ccy==='CHF')?.status!=='WITHHELD'||
            !change.legs.find(x=>x.ccy==='CHF')?.text?.includes('2026-09-30')||
            !change.legs.find(x=>x.ccy==='EUR')?.model?.includes('Crescita: peggiora')||
            !change.note?.includes('non necessariamente 24 ore')||
            change.width>change.viewport+16)
           throw Error(name+' public Pair What Changed quality fail-closed '+JSON.stringify(change));
         const reaction=await page.evaluate(()=>{
           const d=document.getElementById('gmfq-page')?.contentDocument,
             c=d?.getElementById('gmfq-pair-market-reaction');
           return {status:c?.dataset.reactionStatus,text:c?.textContent,
             docWidth:d?.documentElement.scrollWidth,viewport:d?.documentElement.clientWidth};
         });
         if(reaction.status!=='WITHHELD'||
            !reaction.text?.includes('2Y di una o entrambe le valute')||
            reaction.docWidth>reaction.viewport+16)
           throw Error(name+' CHF public FX/Rates audit did not fail closed '+JSON.stringify(reaction));
         await page.frameLocator('#gmfq-page').locator('#pair-index button.pair-open[data-pair="EURUSD"]').click();
         await page.waitForFunction(()=>{
           const d=document.getElementById('gmfq-page')?.contentDocument;
           return d?.getElementById('gmfq-pair-research-path')?.dataset.pair==='EURUSD';
         },null,{timeout:14000});
         const liveAudit=await page.evaluate(()=>{
           const d=document.getElementById('gmfq-page')?.contentDocument,
              c=d?.getElementById('gmfq-pair-market-reaction');
           return {status:c?.dataset.reactionStatus,dates:[c?.dataset.windowStart,c?.dataset.windowEnd],
              texts:[...c?.querySelectorAll('.gmfq-reaction-metrics strong')||[]].map(x=>x.textContent),
              note:c?.querySelector('.gmfq-reaction-warning')?.textContent,
              viewport:d?.documentElement.clientWidth,width:d?.documentElement.scrollWidth};
         });
         // Public 2Y and ECB fixing data advance every session: derive the
         // correct descriptive verdict from observed magnitudes, not a pinned date.
         const spreadBp=Number.parseFloat(liveAudit.texts[0]);
         const fxMovePct=Number.parseFloat(liveAudit.texts[1]);
         const observedSpan=(Date.parse(liveAudit.dates[1]+'T00:00:00Z')-
           Date.parse(liveAudit.dates[0]+'T00:00:00Z'))/86400000;
         const expectedReaction=!Number.isFinite(spreadBp)||!Number.isFinite(fxMovePct)?
           'WITHHELD':Math.abs(spreadBp)<2||Math.abs(fxMovePct)<0.05?
           'NON_CONCLUSIVO':Math.sign(spreadBp)===Math.sign(fxMovePct)?'COERENTE':'DIVERGENTE';
         if(liveAudit.status!==expectedReaction||
            !Number.isFinite(observedSpan)||observedSpan<=0||observedSpan>5||
            !liveAudit.note?.includes('non prova causalità')||
            liveAudit.width>liveAudit.viewport+16)
           throw Error(name+' public EURUSD threshold audit wrong '+JSON.stringify({liveAudit,expectedReaction}));
         const decision=await page.evaluate(()=>{
           const d=document.getElementById('gmfq-page')?.contentDocument,
             c=d?.getElementById('gmfq-pair-decision-bridge');
           return {status:c?.dataset.bridgeStatus,baseline:c?.dataset.baselineStatus,
             cells:[...c?.querySelectorAll('.gmfq-decision-cols>div')||[]].map(x=>x.textContent),
             content:c?.textContent,documentWidth:d?.documentElement.scrollWidth,
             viewport:d?.documentElement.clientWidth};
         });
         const candidateOnPublic=process.env.GITHUB_EVENT_NAME==='pull_request';
         const expectedBridge=candidateOnPublic?'CONTRO_TESI':'NON_DETERMINATO';
         if(decision.status!==expectedBridge||decision.cells.length!==3||
            !decision.cells[0]?.includes('USD')||!decision.cells[1]?.includes('CON RISCHI')||
            !decision.cells[2]?.includes(liveAudit.status==='COERENTE'?'Coerente tra 2Y e FX':liveAudit.status==='DIVERGENTE'?'Divergente tra 2Y e FX':liveAudit.status==='NON_CONCLUSIVO'?'Non conclusivo':'Non valutabile')||
            !decision.content?.includes('Una coerenza 2Y–FX non equivale a conferma della tesi')||
            (!candidateOnPublic&&(decision.baseline!=='STALE_OR_UNVERIFIED'||
               !decision.cells[0]?.includes('Preferenza storica')||
               !decision.content?.includes('Prima rivalidare la baseline Macro/Tassi')||
               !decision.content?.includes('I movimenti recenti FX e 2Y restano osservazioni valide')))||
            !decision.content?.includes('Non sono disponibili trigger numerici certificati')||
            decision.documentWidth>decision.viewport+16)
           throw Error(name+' Public EURUSD bridge conflates Rates/FX agreement with USD thesis '+JSON.stringify(decision));
         const evidence=await page.evaluate(()=>{
           const d=document.getElementById('gmfq-page')?.contentDocument,
             c=d?.getElementById('gmfq-pair-evidence-checklist');
           return {exists:!!c,rows:[...c?.querySelectorAll('.gmfq-evidence-row')||[]].map(x=>x.textContent),
             content:c?.textContent,width:d?.documentElement.scrollWidth,viewport:d?.documentElement.clientWidth};
         });
         // Read the very same public canonical source as the page. Individual
         // blockers are conditional: a NORMAL extension must NOT be invented
         // merely to satisfy an old date-pinned assertion.
         const evidenceSource=await page.evaluate(async()=>{
           const res=await fetch('https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/main/live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json',{cache:'no-store'});
           if(!res.ok)return null;
           const data=await res.json();
           return {asof:data.price_asof,source:data.pairs?.EURUSD?.setup||null};
         });
         const src=evidenceSource?.source,rowText=evidence.rows[2]||'';
         const blockers=src?[
           ['Prezzo nel modello:', ['BAD','NEUTRAL'].includes(src.price?.state)],
           ['Estensione del prezzo:', ['ADVANCED','EXTENDED'].includes(src.extension?.state)],
           ['Timing:', typeof src.timing?.text==='string'],
           ['Posizionamento:', ['HIGH','DIVERGENT'].includes(src.cot?.state)],
           ['Liquidità:', src.liquidity?.state==='BAD']
         ]:[];
         if(!src||!evidence.content?.includes('Prezzo del modello: '+evidenceSource.asof)||
            !evidence.exists||evidence.rows.length!==3||
            !evidence.rows[0]?.includes('USD')||
            !evidence.rows[1]?.includes('EUR')||
            blockers.some(([label,expected])=>rowText.includes(label)!==expected)||
            !evidence.content?.includes('Nessun trigger numerico o livello tecnico viene derivato automaticamente')||
            evidence.width>evidence.viewport+16)
           throw Error(name+' published Pair evidence checklist missing or fabricated '+JSON.stringify(evidence));
         console.log('CONTROL_ROOM_PREVIEW_PUBLIC_PAIR_EVIDENCE_CHECKLIST_GREEN',name,
           JSON.stringify({eurusd:3,viewport:evidence.viewport}));
         console.log('CONTROL_ROOM_PREVIEW_PUBLIC_PAIR_DECISION_BRIDGE_GREEN',name,
           JSON.stringify({eurusd:decision.status,viewport:decision.viewport}));
         console.log('CONTROL_ROOM_PREVIEW_PUBLIC_PAIR_FX_REACTION_GREEN',name,
           JSON.stringify({eurusd:liveAudit.status,eurusdWindow:liveAudit.dates,
             eurchf:reaction.status,viewport:liveAudit.viewport}));
         console.log('CONTROL_ROOM_PREVIEW_PUBLIC_PAIR_WHAT_CHANGED_GREEN',name,
           JSON.stringify({selected:'EURCHF',chf:'WITHHELD',viewport:change.viewport}));
         console.log('CONTROL_ROOM_PREVIEW_PUBLIC_PAIR_MACRO_RATES_GREEN',name,
           JSON.stringify({selected:'EURCHF',spread:pairMacro.spreadSame,viewport:pairMacro.viewport}));
  
       }
       console.log('CONTROL_ROOM_PREVIEW_PUBLIC_28_PAIR_RESEARCH_GREEN',name,JSON.stringify({
         homePair,opened:'EURCHF',routes:p.buttons,viewport:p.viewport}));
     }
     console.log('CONTROL_ROOM_PREVIEW_PAIR_NAVIGATION_PASS',name,homePair);
     await page.goto(BASE+'#/home',{waitUntil:'domcontentloaded',timeout:120000});
     await page.waitForFunction(()=>document.getElementById('gmfq-page')?.contentDocument?.querySelectorAll('#ois .oisrow').length===8,null,{timeout:60000});
     await page.frameLocator('#gmfq-page').locator('#ois .oisrow[data-ccy="USD"]').click();
     await page.waitForURL(/#\/banche\?ccy=USD$/,{timeout:15000});

     if(process.env.GITHUB_EVENT_NAME!=='pull_request'){
       // Require actual public v10 Cross-Asset module, not legacy root Risk.
       let seen=false;
       for(let attempt=0;attempt<15;attempt++){
         await page.goto(BASE+'?crossgoldqa='+Date.now()+'-'+attempt+'#/cross',
           {waitUntil:'domcontentloaded',timeout:120000});
         try{
           await page.waitForFunction(()=>{
             const doc=document.getElementById('gmfq-page')?.contentDocument;
             return ['SECONDARY_CURRENT','SECONDARY_HISTORICAL','WITHHELD'].includes(
               doc?.getElementById('gmfq-cross-gold-v10')?.dataset.sourceStatus);
           },null,{timeout:5000});
           seen=true;break;
         }catch(e){console.log('PUBLIC_CROSS_GOLD_CDN_PENDING',name,attempt)}
         await page.waitForTimeout(2500);
       }
       if(!seen)throw Error(name+' public Control Room Cross-Asset Gold module not delivered');
       const gold=await page.evaluate(()=>{
         const doc=document.getElementById('gmfq-page')?.contentDocument;
         const card=doc?.getElementById('gmfq-cross-gold-v10');
         return {state:card?.dataset.sourceStatus,asof:card?.dataset.goldAsOf,
           text:card?.textContent,quote:card?.querySelector('.gmfq-gold-quote')?.textContent,
            spotBackground:card?.querySelector('.gmfq-gold-spot')?doc.defaultView.getComputedStyle(card.querySelector('.gmfq-gold-spot')).backgroundColor:null,
            spotBorder:card?.querySelector('.gmfq-gold-spot')?(doc.documentElement.clientWidth<=700?doc.defaultView.getComputedStyle(card.querySelector('.gmfq-gold-spot')).borderTopWidth:doc.defaultView.getComputedStyle(card.querySelector('.gmfq-gold-spot')).borderLeftWidth):null,
           docWidth:doc?.documentElement.scrollWidth,viewport:doc?.documentElement.clientWidth,
           legacy:!!doc?.querySelector('[data-gmfq-operational="risk"]')};
       });
       if(!['SECONDARY_CURRENT','SECONDARY_HISTORICAL'].includes(gold.state)||
          !/^20\d{2}-\d{2}-\d{2}$/.test(gold.asof||'')||
          !gold.text?.includes('Gold Price LBMA · WITHHELD')||
          !gold.text?.includes('GC=F · futures COMEX indicativo')||
          !gold.text?.includes('non equivale a oro spot')||
          gold.quote==='—'||gold.legacy||
           !['transparent','rgba(0, 0, 0, 0)'].includes(gold.spotBackground)||
           gold.spotBorder!=='1px'||gold.docWidth>gold.viewport+16){
         throw Error(name+' public Cross-Asset Gold not verified '+JSON.stringify(gold));
       }
       console.log('CONTROL_ROOM_V10_PUBLIC_CROSS_GOLD_GREEN',name,
         JSON.stringify({status:gold.state,asof:gold.asof,value:gold.quote,
           viewport:gold.viewport}));

       await page.waitForFunction(()=>{
         const d=document.getElementById('gmfq-page')?.contentDocument;
         return ['AVAILABLE','PARTIAL','WITHHELD'].includes(
           d?.getElementById('gmfq-cross-risk-v10')?.dataset.sourceStatus);
       },null,{timeout:20000});
       const risk=await page.evaluate(()=>{
         const d=document.getElementById('gmfq-page')?.contentDocument,
           panel=d?.getElementById('gmfq-cross-risk-v10');
         return {status:panel?.dataset.sourceStatus,
           references:panel?.dataset.studyReferences,official:panel?.dataset.studyOfficial,
           secondary:panel?.dataset.studySecondary,effect:panel?.dataset.studyEffect,
           snapshot:panel?.querySelector('.gmfq-cross-coverage')?.textContent,
           priority:panel?.querySelector('.gmfq-cross-risk-intro')?.textContent,
           sourceKeys:[...panel?.querySelectorAll('.gmfq-cross-risk-evidence span[data-source]')||[]].map(x=>x.dataset.source),
           priorityFirst:!!(panel?.querySelector('.gmfq-cross-risk-intro')?.compareDocumentPosition(panel.querySelector('.gmfq-cross-risk-evidence'))&Node.DOCUMENT_POSITION_FOLLOWING),
           grid:panel?.querySelector('.gmfq-cross-risk-grid')?d.defaultView.getComputedStyle(panel.querySelector('.gmfq-cross-risk-grid')).gridTemplateColumns.trim().split(/\s+/).length:null,
           cardBg:panel?.querySelector('.gmfq-cross-risk-card')?d.defaultView.getComputedStyle(panel.querySelector('.gmfq-cross-risk-card')).backgroundColor:null,
           cards:[...panel?.querySelectorAll('[data-cross-instrument]')||[]]
             .map(c=>({name:c.dataset.crossInstrument,status:c.dataset.crossStatus,
               asof:c.textContent,value:c.querySelector('.gmfq-cross-risk-value')?.textContent})),
           text:panel?.textContent,width:d?.documentElement.scrollWidth,
           viewport:d?.documentElement.clientWidth};
       });
       const coverageValid=process.env.GITHUB_EVENT_NAME==='pull_request'||
         (risk.references==='4'&&risk.official==='2'&&risk.secondary==='2'&&
          risk.effect==='NONE'&&risk.snapshot?.includes('4/4 riferimenti numerici per lo studio'));
       if(!coverageValid||risk.cards.length!==3||
          !risk.priority?.startsWith('VIX misura volatilità implicita')||
          !risk.priorityFirst||
          JSON.stringify(risk.sourceKeys)!==JSON.stringify(['vix','wti','brent'])||
          risk.grid!==(risk.viewport<=820?1:3)||
          !['transparent','rgba(0, 0, 0, 0)'].includes(risk.cardBg)||
          !risk.cards.some(c=>c.name==='VIX'&&c.status.startsWith('OFFICIAL_'))||
          !risk.cards.some(c=>c.name==='WTI'&&c.status.startsWith('OFFICIAL_'))||
          !risk.cards.some(c=>c.name==='BRENT'&&c.status.startsWith('SECONDARY_'))||
          !risk.text?.includes('Brent spot ufficiale: WITHHELD')||
          !risk.text?.includes('Nessun confronto di spread fra spot e futures')||
          risk.width>risk.viewport+16)
          throw Error(name+' public Cross-Asset risk/energy not delivered '+JSON.stringify(risk));
       console.log('CONTROL_ROOM_V10_PUBLIC_CROSS_RISK_GREEN',name,
         JSON.stringify({status:risk.status,
           cards:risk.cards.map(c=>({name:c.name,status:c.status,value:c.value})),
           viewport:risk.viewport}));

     }

     // Post-merge only: source-first Macro and Screener must be visible on the
     // actually deployed release; the older public CDN build is not accepted.
     if(process.env.GITHUB_EVENT_NAME!=='pull_request'){
       await page.goto(BASE+'?macroReading='+Date.now()+'#/macro?ccy=EUR',{waitUntil:'domcontentloaded',timeout:120000});
       await page.waitForFunction(()=>{
         const d=document.getElementById('gmfq-page')?.contentDocument;
         return d?.getElementById('gmfq-macro-source-lens')?.dataset.auditStatus==='READ_ONLY';
       },null,{timeout:25000});
       const macroFirst=await page.evaluate(()=>{
         const d=document.getElementById('gmfq-page')?.contentDocument;
         const panel=d.getElementById('gmfq-macro-source-lens');
         const detail=panel.querySelector('#gmfq-macro-observation-details');
         return {baseline:panel.dataset.baselineAsOf,
           preview:panel.querySelector('#gmfq-macro-reading')?.textContent,
           dynamics:[...panel.querySelectorAll('.gmfq-macro-dynamic')].map(x=>({
             metric:x.dataset.macroMetric,status:x.dataset.dynamicStatus,
             direction:x.dataset.direction,acc:x.dataset.acceleration,
             date:x.dataset.asOf,visible:!!x.getClientRects().length
           })),
           dynamicNote:panel.querySelector('.gmfq-macro-dynamics-note')?.textContent,
            priority:panel.querySelector('.gmfq-macro-takeaway')?.textContent,
            priorityFirst:!!(panel.querySelector('.gmfq-macro-takeaway')?.compareDocumentPosition(panel.querySelector('.gmfq-macro-state'))&Node.DOCUMENT_POSITION_FOLLOWING),
           closed:detail?.open===false,
           hidden:![...panel.querySelectorAll('.gmfq-macro-observation')].some(x=>x.getClientRects().length>0),
           count:panel.querySelectorAll('.gmfq-macro-observation').length,
           observedCount:panel.dataset.observedStudyCount,
           overviewCount:panel.querySelector('#gmfq-macro-g8-study')?.dataset.observationCount,
           overviewRows:[...panel.querySelectorAll('#gmfq-macro-g8-study [data-g8-ccy]')].map(x=>({
             ccy:x.dataset.g8Ccy,inflation:x.dataset.inflationStatus,
             labour:x.dataset.labourStatus,visible:!!x.getClientRects().length
           })),
           noEffect:panel.querySelector('#gmfq-macro-g8-study')?.dataset.coreEffect==='NONE'&&
             panel.querySelector('#gmfq-macro-g8-study')?.dataset.biasEffect==='NONE',
           width:d.documentElement.scrollWidth,viewport:d.documentElement.clientWidth};
       });
       const macroNew=process.env.GITHUB_EVENT_NAME!=='pull_request';
       const studyValid=macroNew?
         macroFirst.preview?.includes('Inflazione: ')&&macroFirst.preview.includes('Disoccupazione: ')&&
         macroFirst.observedCount==='16'&&macroFirst.overviewCount==='16'&&
         macroFirst.overviewRows.length===8&&macroFirst.overviewRows.every(x=>
           ['USD','EUR','GBP','JPY','AUD','CAD','NZD','CHF'].includes(x.ccy)&&
           x.inflation==='OBSERVED'&&x.labour==='OBSERVED'&&x.visible)&&macroFirst.noEffect:
         macroFirst.preview?.includes('Inflazione: periodo ')&&
         macroFirst.preview.includes('Lavoro: periodo ');
       if(!macroFirst.baseline||!studyValid||
          !macroFirst.priority?.startsWith('Gli score sono uno snapshot del modello')||
           !macroFirst.priorityFirst||
           !macroFirst.closed||!macroFirst.hidden||macroFirst.count!==2||
          macroFirst.width>macroFirst.viewport+16)
         throw Error(name+' public Macro reading not deployed '+JSON.stringify(macroFirst));
       if(navigationVersion==='macro-observed-dynamics-20261022'){
          if(macroFirst.dynamics.length!==2||
             !macroFirst.dynamicNote?.includes('non alla forza della valuta')||
             macroFirst.dynamics.some(x=>x.status!=='OBSERVED'||!x.visible||
               !['SALE','SCENDE','STABILE'].includes(x.direction)||
               !['ACCELERA','RALLENTA','STABILE'].includes(x.acc)||!x.date))
            throw Error(name+' public Macro sourced dynamics incorrect '+JSON.stringify(macroFirst));
       }
       await page.frameLocator('#gmfq-page').locator('#gmfq-macro-observation-details>summary').press('Enter');
       if(!(await page.frameLocator('#gmfq-page').locator('.gmfq-macro-observation').first().isVisible()))
         throw Error(name+' public Macro source detail not accessible');
       await page.goto(BASE+'?screenerReading='+Date.now()+'#/screener',{waitUntil:'domcontentloaded',timeout:120000});
       await page.waitForFunction(()=>{
         const d=document.getElementById('gmfq-page')?.contentDocument;
         return d?.getElementById('gmfq-screener-blockers')?.dataset.diagnosisStatus==='READ_ONLY';
       },null,{timeout:25000});
       const screenerFirst=await page.evaluate(()=>{
         const d=document.getElementById('gmfq-page')?.contentDocument;
         const p=d.getElementById('gmfq-screener-blockers');
         const details=p.querySelector('#gmfq-blocker-details');
         // Do not blame the research addon for an existing native Screener
         // overflow: compare the full page width to the same page without it.
         const panelWidth=p.scrollWidth,panelClient=p.clientWidth;
         p.style.display='none';
         const nativeWidth=d.documentElement.scrollWidth;
         p.style.display='';
         return {nativeWidth,panelWidth,panelClient,
           summary:p.querySelector('.gmfq-blocker-overview')?.textContent,
           qualityCoverage:p.dataset.qualityCoverage,reviewCount:p.dataset.reviewCount,
           quality:[...p.querySelectorAll('.gmfq-screener-quality span[data-quality]')].map(x=>({
             tier:x.dataset.quality,count:Number(x.querySelector('b')?.textContent)
           })),
           review:(()=>{
             const box=p.querySelector('.gmfq-screener-review');
             return {rank:box?.dataset.ranking,signals:box?.dataset.tradeSignals,
               note:box?.querySelector('.gmfq-screener-review-note')?.textContent,
               pairs:[...box?.querySelectorAll('button.gmfq-review-pair')||[]].map(x=>({
                 code:x.dataset.pair,tier:x.dataset.quality,visible:!!x.getClientRects().length
               }))};
           })(),
            priority:p.querySelector('.gmfq-blocker-priority')?.textContent,
            priorityFirst:!!(p.querySelector('.gmfq-blocker-priority')?.compareDocumentPosition(p.querySelector('.gmfq-blocker-overview'))&Node.DOCUMENT_POSITION_FOLLOWING),
            sources:[...p.querySelectorAll('.gmfq-blocker-date span[data-source]')].map(x=>x.dataset.source),
           count:p.querySelectorAll('.gmfq-blocker-pair').length,
           closed:details?.open===false,
           hidden:![...p.querySelectorAll('.gmfq-blocker-pair')].some(x=>x.getClientRects().length>0),
           width:d.documentElement.scrollWidth,viewport:d.documentElement.clientWidth};
       });
       if(!screenerFirst.priority?.startsWith('Le coppie senza una tesi coerente')||
           !screenerFirst.priorityFirst||
           JSON.stringify(screenerFirst.sources)!==JSON.stringify(['macro','price'])||
           !screenerFirst.summary?.includes('Macro vs Tassi/CB: ')||
          !screenerFirst.summary.includes('Differenziale 2Y senza tesi: ')||
          !screenerFirst.summary.includes('Vantaggio insufficiente: ')||
          screenerFirst.count!==11||!screenerFirst.closed||!screenerFirst.hidden||
          screenerFirst.panelWidth>screenerFirst.panelClient+2||
          screenerFirst.width>Math.max(screenerFirst.viewport+16,screenerFirst.nativeWidth+2))
         throw Error(name+' public Screener source-first reading not deployed '+JSON.stringify(screenerFirst));
       if(navigationVersion==='screener-review-28-20261022'){
          const expectedTiers=['DA CONFERMARE','DA MONITORARE','CON RISCHI','NON VALUTABILE'];
          const review=screenerFirst.review;
          if(screenerFirst.qualityCoverage!=='28'||
             Number(screenerFirst.reviewCount)!==review?.pairs.length||
             screenerFirst.quality.length!==4||
             screenerFirst.quality.some((x,i)=>x.tier!==expectedTiers[i]||
               !Number.isInteger(x.count)||x.count<0)||
             screenerFirst.quality.reduce((n,x)=>n+x.count,0)!==28||
             review.rank!=='NONE'||review.signals!=='NONE'||
             !review.note?.includes('non proposte di ingresso')||
             review.pairs.some(x=>!['DA CONFERMARE','DA MONITORARE'].includes(x.tier)||
               !/^[A-Z]{6}$/.test(x.code)||!x.visible))
            throw Error(name+' public Screener source-quality first reading failed '+JSON.stringify(screenerFirst));
          if(review.pairs.length){
            const pair=review.pairs.find(x=>x.code==='USDCAD')||review.pairs[0];
            await page.frameLocator('#gmfq-page').locator('#gmfq-screener-blockers button.gmfq-review-pair[data-pair="'+pair.code+'"]').click();
            await page.waitForURL(u=>u.hash==='#/coppie?pair='+pair.code,{timeout:20000});
            await page.goto(BASE+'?screenerBack='+Date.now()+'#/screener',{waitUntil:'domcontentloaded',timeout:120000});
            await page.waitForFunction(()=>{
              const d=document.getElementById('gmfq-page')?.contentDocument;
              return d?.getElementById('gmfq-screener-blockers')?.dataset.diagnosisStatus==='READ_ONLY';
            },null,{timeout:30000});
          }
       }
       await page.frameLocator('#gmfq-page').locator('#gmfq-blocker-details>summary').press('Enter');
       if(!(await page.frameLocator('#gmfq-page').locator('#gmfq-screener-blockers button[data-pair="GBPJPY"]').isVisible()))
         throw Error(name+' public Screener individual reasons inaccessible');
       // Valute: same first-reading order and three source identities on public Pages.
       await page.goto(BASE+'?valuteReading='+Date.now()+'#/valute?ccy=EUR',{waitUntil:'domcontentloaded',timeout:120000});
       await page.waitForFunction(()=>{
         const d=document.getElementById('gmfq-page')?.contentDocument;
         return !!d?.querySelector('#gmfq-valute-source-compass .gmfq-vsc-ledger');
       },null,{timeout:25000});
       const valuteFirst=await page.evaluate(()=>{
         const d=document.getElementById('gmfq-page')?.contentDocument;
         const panel=d.getElementById('gmfq-valute-source-compass');
         const lead=panel.querySelector('.gmfq-vsc-priority'),ledger=panel.querySelector('.gmfq-vsc-ledger');
         const panelWidth=panel.scrollWidth,panelClient=panel.clientWidth;
         panel.style.display='none';const nativeWidth=d.documentElement.scrollWidth;panel.style.display='';
         return {lead:lead?.textContent,state:panel.dataset.readingState,
           first:!!(lead?.compareDocumentPosition(ledger)&Node.DOCUMENT_POSITION_FOLLOWING),
           keys:[...ledger.querySelectorAll('span[data-source]')].map(x=>x.dataset.source),
           disclosure:!!panel.querySelector('.gmfq-vsc-details summary'),
           closed:panel.querySelector('.gmfq-vsc-details')?.open===false,
           ledgerHidden:!ledger?.getClientRects().length,
           panelWidth,panelClient,nativeWidth,
           width:d.documentElement.scrollWidth,viewport:d.documentElement.clientWidth};
       });
       const newValute=process.env.GITHUB_EVENT_NAME!=='pull_request'&&
         ['FX_WITHHELD','MACRO_WITHHELD','MACRO_HISTORICAL','DXY_WITHHELD','SEPARATE_SOURCES'].includes(valuteFirst.state)&&
         valuteFirst.disclosure===true;
       const validLead=newValute?
         (['FX_WITHHELD','MACRO_WITHHELD','MACRO_HISTORICAL','DXY_WITHHELD','SEPARATE_SOURCES'].includes(valuteFirst.state)&&
          (valuteFirst.state==='MACRO_HISTORICAL'?valuteFirst.lead?.includes('tesi Macro ancora alla baseline'):
           valuteFirst.state.endsWith('_WITHHELD')?valuteFirst.lead?.startsWith('Prima verifica:')||
              (valuteFirst.state==='DXY_WITHHELD'&&valuteFirst.lead?.includes('DXY sintetico non è corrente')):
           valuteFirst.lead?.startsWith('Prezzi BCE, DXY sintetico'))&&
          valuteFirst.closed&&valuteFirst.ledgerHidden):
         valuteFirst.lead?.startsWith('Fixing giornaliero, DXY sintetico');
       if(!validLead||!valuteFirst.first||
          JSON.stringify(valuteFirst.keys)!==JSON.stringify(['fixing','dxy','macro'])||
          !valuteFirst.disclosure||valuteFirst.panelWidth>valuteFirst.panelClient+2||
          valuteFirst.width>Math.max(valuteFirst.viewport+16,valuteFirst.nativeWidth+2))
         throw Error(name+' public Valute editorial source ledger failed '+JSON.stringify(valuteFirst));
       if(newValute){
         await page.frameLocator('#gmfq-page').locator('#gmfq-valute-source-compass .gmfq-vsc-details > summary').press('Enter');
         const valuteOpen=await page.evaluate(()=>{
           const p=document.getElementById('gmfq-page').contentDocument.getElementById('gmfq-valute-source-compass');
           return {opened:p.querySelector('.gmfq-vsc-details')?.open,shown:!!p.querySelector('.gmfq-vsc-ledger')?.getClientRects().length};
         });
         if(!valuteOpen.opened||!valuteOpen.shown)
            throw Error(name+' Valute source drilldown missing '+JSON.stringify(valuteOpen));
       }
       if(process.env.GITHUB_EVENT_NAME!=='pull_request'&&navigationVersion==='valute-cross-horizon-20261023'){
         await page.waitForFunction(()=>{
           const d=document.getElementById('gmfq-page')?.contentDocument;
           return d?.getElementById('gmfq-vsc-momentum')?.dataset.comparisonStatus==='OBSERVED';
         },null,{timeout:30000});
         const read=()=>page.evaluate(()=>{
           const p=document.getElementById('gmfq-page')?.contentDocument?.getElementById('gmfq-vsc-momentum');
           return {status:p?.dataset.status,asof:p?.dataset.asof,
             days:p?.dataset.horizon,currency:p?.dataset.comparisonCurrency,
             other:p?.dataset.comparisonOtherRank,
             source:p?.querySelector('.gmfq-vsm-reading')?.dataset.source,
             text:p?.querySelector('.gmfq-vsm-reading')?.textContent,
             count:p?.querySelectorAll('ol li').length,
             width:p?.scrollWidth,client:p?.clientWidth};
         });
         const five=await read();
         if(five.status!=='OBSERVED'||five.days!=='5'||five.currency!=='AUD'||
            five.other!=='7'||five.source!=='ECB_G8_PRICE_HISTORY'||
            five.count!==8||five.width>five.client+2||
            !five.text.includes('Le due finestre si sovrappongono: non prova una svolta.'))
           throw Error(name+' public 5-session horizon reading disagrees with official FX snapshot '+JSON.stringify(five));
         await page.frameLocator('#gmfq-page').locator('#gmfq-vsc-momentum button[data-vsm-days="20"]').click();
         const twenty=await read();
         if(twenty.status!=='OBSERVED'||twenty.days!=='20'||
            twenty.currency!=='GBP'||twenty.other!=='5'||
            twenty.source!=='ECB_G8_PRICE_HISTORY'||twenty.count!==8||
            !twenty.text.includes('Le due finestre si sovrappongono: non prova una svolta.'))
           throw Error(name+' public 20-session horizon reading disagrees with official FX snapshot '+JSON.stringify(twenty));
       }
       console.log('CONTROL_ROOM_V10_MACRO_SCREENER_READING_PUBLIC_GREEN',name,
         {baseline:macroFirst.baseline,groups:screenerFirst.summary,blocked:screenerFirst.count});
     }
     // Post-deploy: check the real two desk pages without mocked feeds. Public
     // CDN must serve the new read-only additive script; no old build passes.
     if(process.env.GITHUB_EVENT_NAME!=='pull_request'){
       for(const pageName of ['banche','cot']){
         let ready=false;
         for(let probe=0;probe<12;probe++){
           await page.goto(BASE+'?researchFirst='+Date.now()+'-'+probe+'#/'+pageName,
             {waitUntil:'domcontentloaded',timeout:120000});
           try{await page.waitForFunction(({expected,id})=>{
             const doc=document.getElementById('gmfq-page')?.contentDocument;
             return [...document.scripts].some(x=>x.src.endsWith('home-navigation-v10.js?v='+expected))&&
               ['READ_ONLY','SOURCE_DIVERGENCE','WITHHELD'].includes(
                 doc?.getElementById(id)?.dataset.readingStatus);
           },{expected:navigationVersion,id:pageName==='banche'?'gmfq-cb-reading-first':'gmfq-cot-reading-first'},
           {timeout:10000});ready=true;break}catch(_){}
         }
         if(!ready)throw Error(name+' PUBLIC_CB_COT_VERSION_NOT_DEPLOYED '+pageName);
         const reading=await page.evaluate(section=>{
           const d=document.getElementById('gmfq-page').contentDocument;
           const p=d.getElementById(section==='banche'?'gmfq-cb-reading-first':'gmfq-cot-reading-first');
           const detail=p.querySelector('details'),nativeId=section==='banche'?'cb-chart':'cot-chart';
           const pageWidth=d.documentElement.scrollWidth;
           p.style.display='none';const originalWidth=d.documentElement.scrollWidth;p.style.display='';
           return {status:p.dataset.readingStatus,asof:p.dataset.cftcAsOf,
             certified:p.dataset.certified,estimated:p.dataset.estimated,withheld:p.dataset.withheld,
             conflicts:p.dataset.conflicts,extremes:p.dataset.extremes,crowding:p.dataset.crowding,
             focusRows:[...p.querySelectorAll('.gmfq-cot-focus-list li')].map(x=>({
               ccy:x.dataset.cotFocusCcy,ratio:Number(x.dataset.netoi),
               percentile:Number(x.dataset.percentileRounded),
               hasLabel:x.textContent.includes(x.dataset.percentileRounded+'°/104W'),
               visible:!!x.getClientRects().length})),
             focusNote:p.querySelector('.gmfq-cot-focus-note')?.textContent,
             focusAsOf:p.querySelector('.gmfq-cot-focus')?.dataset.cftcAsOf,
             extremeAudit:(()=>{
               const node=p.querySelector('.gmfq-cot-percentile'),det=node?.querySelector('.gmfq-cot-percentile-details');
               return {asof:node?.dataset.cftcAsOf,sep:node?.dataset.relativeVsNet,
                 inversions:node?.dataset.inversionCount,closed:det?.open===false,
                 count:det?.querySelectorAll('.gmfq-cot-percentile-list li').length,
                 note:node?.querySelector('.gmfq-cot-rank-note')?.textContent,
                 rows:[...det?.querySelectorAll('.gmfq-cot-percentile-list li')||[]].map(x=>({
                   ccy:x.dataset.extremeCcy,pct:Number(x.dataset.extremeRank),
                   cls:x.dataset.extremeClass,net:Number(x.dataset.extremeNet),
                   relation:x.dataset.rankVsNet}))};
             })(),
             percentileCount:p.dataset.percentileCount,rankVsNet:p.dataset.rankVsNet,
             weeklyAsOf:p.dataset.weeklyAsOf,weeklyCount:p.dataset.weeklyCount,
             weekly:(()=>{
               const details=p.querySelector('.gmfq-cot-weekly-details');
               return {present:!!details,closed:details?.open===false,
                 previous:details?.dataset.priorAsof,
                 latest:details?.dataset.currentAsof,
                 count:details?.querySelectorAll('.gmfq-cot-weekly-list li').length,
                 method:details?.querySelector('.gmfq-cot-weekly-method')?.textContent};
             })(),
             meeting:(()=>{
               const box=p.querySelector('.gmfq-cb-meeting-focus'),det=p.querySelector('.gmfq-cb-meeting-details');
               return {status:box?.dataset.calendarStatus,asof:box?.dataset.asOf,source:box?.dataset.source,
                 groups:[...box?.querySelectorAll('.gmfq-cb-meeting-dates li')||[]].map(x=>({
                   day:x.dataset.meetingDay,ccys:[...x.querySelectorAll('[data-meeting-ccy]')].map(y=>y.dataset.meetingCcy)
                 })),
                 closed:det?.open===false,total:Number(det?.dataset.count),
                 rows:[...det?.querySelectorAll('.gmfq-cb-meeting-all li')||[]].map(x=>({
                   ccy:x.dataset.meetingCcy,date:x.dataset.meetingDate,tier:x.dataset.meetingTier
                 }))};
             })(),
             heading:p.querySelector('.gmfq-first-claim')?.textContent,
             priority:p.querySelector('.gmfq-first-priority')?.textContent,
             priorityFirst:!!(p.querySelector('.gmfq-first-priority')?.compareDocumentPosition(p.querySelector('.gmfq-first-claim'))&Node.DOCUMENT_POSITION_FOLLOWING),
             closed:detail.open===false,originalChart:!!d.getElementById(nativeId),
             originalTable:!!d.getElementById(section==='banche'?'cb-table':'cot-table'),
             panelScroll:p.scrollWidth,panelWidth:p.clientWidth,pageWidth,originalWidth,
             viewport:d.documentElement.clientWidth};
         },pageName);
         const publicPricingSummary=pageName==='banche'?
           await page.evaluate(async()=>{
             const url='https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/main/live_data/sections/OIS_OPERATIONAL_VIEW.json';
             const response=await fetch(url,{cache:'no-store'});
             if(!response.ok)throw Error('public CB pricing source HTTP '+response.status);
             const live=await response.json();
             const summary=live.summary,ccys=Object.values(live.currencies||{});
             if(ccys.length!==8||
                summary.green_official!==ccys.filter(x=>x.operational_status==='GREEN_OFFICIAL').length||
                summary.green_estimated!==ccys.filter(x=>x.operational_status==='GREEN_ESTIMATED').length||
                summary.operational_withheld!==ccys.filter(x=>x.operational_status==='WITHHELD').length)
               throw Error('public CB pricing summary not source-reconciled');
             return summary;
           }):null;
         if(pageName==='cot'&&['cot-crowding-focus-20261022','cot-weekly-position-20261022','cot-percentile-vs-net-20261022'].includes(navigationVersion)){
           const n=Math.min(3,Number(reading.crowding));
           if(reading.focusRows.length!==n||reading.focusAsOf!==reading.asof||
             !reading.focusNote?.includes('non direzione del prezzo')||
             reading.focusRows.some((x,i)=>!['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'].includes(x.ccy)||
               !x.visible||!x.hasLabel||Math.abs(x.ratio)<30||x.percentile<0||x.percentile>100||
               (i>0&&Math.abs(x.ratio)>Math.abs(reading.focusRows[i-1].ratio))))
              throw Error(name+' public CFTC focused crowding incorrect '+JSON.stringify(reading));
         }
         if(pageName==='cot'&&['cot-weekly-position-20261022','cot-percentile-vs-net-20261022'].includes(navigationVersion)){
           if(!reading.weekly?.present||!reading.weekly.closed||
              reading.weeklyCount!=='8'||reading.weekly.count!==8||
              reading.weeklyAsOf!==reading.weekly.previous||
              reading.asof!==reading.weekly.latest||
              !reading.weekly.method?.includes('dimensioni contrattuali diverse'))
             throw Error(name+' public COT historical 1W provenance error '+JSON.stringify(reading));
           await page.frameLocator('#gmfq-page')
             .locator('#gmfq-cot-reading-first .gmfq-cot-weekly-details>summary').press('Enter');
           const weeklyExpanded=await page.evaluate(()=>{
             const p=document.getElementById('gmfq-page').contentDocument.getElementById('gmfq-cot-reading-first');
             const det=p.querySelector('.gmfq-cot-weekly-details');
             return {open:det?.open,visible:[...det?.querySelectorAll('.gmfq-cot-weekly-list li')||[]].filter(x=>x.getClientRects().length).length};
           });
           if(!weeklyExpanded.open||weeklyExpanded.visible!==8)
             throw Error(name+' public COT full G8 weekly detail inaccessible '+JSON.stringify(weeklyExpanded));
           await page.frameLocator('#gmfq-page')
             .locator('#gmfq-cot-reading-first .gmfq-cot-weekly-details>summary').press('Enter');
         }
         if(pageName==='cot'&&navigationVersion==='cot-percentile-vs-net-20261022'){
           const ext=reading.extremeAudit;
           if(!ext||ext.asof!==reading.asof||ext.sep!=='SEPARATE'||!ext.closed||
              reading.percentileCount!==String(ext.count)||ext.count!==Number(reading.extremes)||
              reading.rankVsNet!==ext.inversions||
              !ext.note?.includes('Percentile ≠ segno del Net')||
              ext.rows.some(x=>!['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'].includes(x.ccy)||
                x.pct<0||x.pct>100||!['EXTREME LONG','EXTREME SHORT'].includes(x.cls)||
                (x.pct>=80&&x.cls!=='EXTREME LONG')||
                (x.pct<=20&&x.cls!=='EXTREME SHORT')||
                x.relation!==((x.cls==='EXTREME LONG'&&x.net<0)||
                               (x.cls==='EXTREME SHORT'&&x.net>0)?'OPPOSED':'ALIGNED')))
              throw Error(name+' public COT rank vs signed Net invalid '+JSON.stringify(reading));
           const rankToggle=page.frameLocator('#gmfq-page')
             .locator('#gmfq-cot-reading-first .gmfq-cot-percentile-details>summary');
           await rankToggle.press('Enter');
           const rankExpanded=await page.evaluate(()=>{
             const p=document.getElementById('gmfq-page').contentDocument.getElementById('gmfq-cot-reading-first');
             const det=p.querySelector('.gmfq-cot-percentile-details');
             return {open:det?.open,visible:[...det?.querySelectorAll('.gmfq-cot-percentile-list li')||[]].filter(x=>x.getClientRects().length).length};
           });
           if(!rankExpanded.open||rankExpanded.visible!==ext.count)
              throw Error(name+' public COT 104W detail inaccessible '+JSON.stringify(rankExpanded));
           await rankToggle.press('Enter');
         }
         if(pageName==='banche'&&navigationVersion==='cb-meeting-calendar-20261022'){
           const m=reading.meeting;
           if(!m||m.status!=='HISTORICAL_SNAPSHOT'||m.source!=='NATIVE_CB_DATA'||
              !m.closed||m.total!==8||m.rows.length!==8||
              m.rows.some(x=>!['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'].includes(x.ccy)||
                 !['CERTIFIED','ESTIMATED','WITHHELD'].includes(x.tier))||
              m.groups.some(x=>!/^20\d{2}-\d{2}-\d{2}$/.test(x.day)||
                x.ccys.length<1||x.ccys.length>8))
             throw Error(name+' public G8 CB snapshot/tier summary invalid '+JSON.stringify(m));
           const toggle=page.frameLocator('#gmfq-page').locator('#gmfq-cb-reading-first .gmfq-cb-meeting-details>summary');
           await toggle.press('Enter');
           const opened=await page.evaluate(()=>{
             const p=document.getElementById('gmfq-page').contentDocument.getElementById('gmfq-cb-reading-first'),
               det=p.querySelector('.gmfq-cb-meeting-details');
             return det?.open&&[...det.querySelectorAll('.gmfq-cb-meeting-all li')].every(x=>x.getClientRects().length>0);
           });
           if(!opened)throw Error(name+' public G8 CB meeting details inaccessible');
           await toggle.press('Enter');
         }
         if(!reading.originalChart||!reading.originalTable||!reading.closed||
            !reading.priorityFirst||
            (pageName==='banche'?
               !reading.priority?.startsWith('Le ultime decisioni sono snapshot storici'):
               !reading.priority?.startsWith('Gli estremi COT descrivono'))||
            reading.panelScroll>reading.panelWidth+2||
            reading.pageWidth>Math.max(reading.viewport+16,reading.originalWidth+2)||
            (pageName==='banche'?
               reading.status!=='READ_ONLY'||
               reading.certified!==String(publicPricingSummary.green_official)||
               reading.estimated!==String(publicPricingSummary.green_estimated)||
               reading.withheld!==String(publicPricingSummary.operational_withheld):
               reading.status!=='READ_ONLY'||reading.conflicts!==''||
               !/^20\d{2}-\d{2}-\d{2}$/.test(reading.asof||'')||
               !reading.heading?.includes('Percentile')&&!reading.heading?.includes('Estremi percentile')))
           throw Error(name+' public '+pageName+' read-only source summary failed '+JSON.stringify(reading));
         await page.frameLocator('#gmfq-page')
           .locator('#'+(pageName==='banche'?'gmfq-cb-reading-first':'gmfq-cot-reading-first')+'>details:first-of-type>summary')
           .press('Enter');
         const open=await page.evaluate(section=>{
           const d=document.getElementById('gmfq-page')?.contentDocument,
             p=d?.getElementById(section==='banche'?'gmfq-cb-reading-first':'gmfq-cot-reading-first');
           const sourceDetail=p?.querySelector(':scope > details');
           return {open:sourceDetail?.open,
             visible:[...sourceDetail?.querySelectorAll('p')||[]].every(x=>x.getClientRects().length>0)};
         },pageName);
         if(!open.open||!open.visible)
           throw Error(name+' public '+pageName+' source evidence not keyboard accessible');
         console.log('CONTROL_ROOM_V10_CB_COT_READING_PUBLIC_GREEN',name,pageName,reading);
       }
     }
     await page.close();
   }
   console.log('CONTROL_ROOM_V10_PUBLIC_G8_DXY_NAVIGATION_GREEN');
 } finally {await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
