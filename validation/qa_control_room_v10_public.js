/* Public URL smoke QA. No mocked feeds: validates what the actual GitHub Pages website serves. */
'use strict';
const {chromium}=require('playwright');
const fs=require('node:fs');
const {execFileSync}=require('node:child_process');
const {readApproved,verifyPublicNzd}=require('./control_room_nzd_public_contract_v1.js');
const {matrix:expectedOisResearchMatrix,romeTodayIso}=require('../site/control-room-preview/ois-pricing-estimates-v1.js');
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
          !audit.detail?.includes('proxy Bank Bill−cash calibrato su 19 osservazioni RBNZ')||
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
           nextToGlobe:!!rail&&!!hero&&!!grid&&!!d.querySelector('.hero .globe')&&
             grid.contains(hero)&&
             !!(rail.compareDocumentPosition(grid)&Node.DOCUMENT_POSITION_FOLLOWING),
           width:rail?.scrollWidth,client:rail?.clientWidth,
           page:d.documentElement.scrollWidth,viewport:d.documentElement.clientWidth};
       });
       if(!reading.present||!reading.nextToGlobe||reading.sourceEffect!=='NONE'||
          JSON.stringify(reading.keys)!==JSON.stringify(['macro','pricing','pairs'])||
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
     await page.frameLocator('#gmfq-page').locator('#valute .cc[data-filter="DXY"]').click();
     await page.frameLocator('#gmfq-page').locator('dialog#gmfq-dxy-dialog[open]').waitFor({timeout:10000});
     await page.frameLocator('#gmfq-page').locator('.gmfq-dxy-dialog .gmfq-close').click();
     await page.frameLocator('#gmfq-page').locator('.mid > .panel:nth-child(2)').click();
     await page.waitForURL(/#\/tassi\?focus=2y$/,{timeout:15000});
     await page.waitForFunction(()=>document.getElementById('gmfq-page')?.contentDocument?.querySelector('#rates-select'),null,{timeout:20000});
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
       for(let attempt=0;attempt<16;attempt++){
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
         await page.goto(BASE+'?oisResearch='+Date.now()+'-'+attempt+'#/tassi?focus=ois',
           {waitUntil:'domcontentloaded',timeout:120000});
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
       // The public CDN may serve an older Home navigation script after the
       // new main / gh-pages source SHAs already agree. Verify the deployed
       // canonical version AND all four source-readiness rows before auditing.
       if(process.env.GITHUB_EVENT_NAME!=='pull_request'){
         let realReadiness=false;
         for(let probe=0;probe<15;probe++){
           realReadiness=await page.evaluate(expected=>{
             const frame=document.getElementById('gmfq-page')?.contentDocument;
             return [...document.scripts].some(el=>
               el.src.endsWith('home-navigation-v10.js?v='+expected))&&
               frame?.querySelectorAll('#gmfq-source-readiness .gmfq-source-row').length===4&&
               frame?.querySelectorAll('#gmfq-source-readiness .gmfq-source-link a').length===4;
           },navigationVersion);
           if(realReadiness)break;
           await page.goto(BASE+'?readinessQA='+Date.now()+'-'+probe+'#/tassi?focus=ois',
             {waitUntil:'domcontentloaded',timeout:120000});
           try{
             await page.waitForFunction(expected=>{
               const d=document.getElementById('gmfq-page')?.contentDocument;
               return [...document.scripts].some(el=>
                 el.src.endsWith('home-navigation-v10.js?v='+expected))&&
                 d?.querySelectorAll('#gmfq-source-readiness .gmfq-source-row').length===4&&
                 d?.querySelectorAll('#gmfq-source-readiness .gmfq-source-link a').length===4;
             },navigationVersion,{timeout:9000});
           }catch(_){console.log('PUBLIC_SOURCE_READINESS_CDN_PENDING',name,probe)}
           await page.waitForTimeout(2000);
         }
         if(!realReadiness)realReadiness=await page.evaluate(expected=>{
           const d=document.getElementById('gmfq-page')?.contentDocument;
           return [...document.scripts].some(x=>x.src.endsWith('home-navigation-v10.js?v='+expected))&&
              d?.querySelectorAll('#gmfq-source-readiness .gmfq-source-row').length===4&&
              d?.querySelectorAll('#gmfq-source-readiness .gmfq-source-link a').length===4;
         },navigationVersion);
         if(!realReadiness)throw Error(name+' PUBLIC_READINESS_VERSION_NOT_DEPLOYED_OR_UNAVAILABLE');
       }
       await page.waitForFunction(()=>{
         const d=document.getElementById('gmfq-page')?.contentDocument;
         return d?.getElementById('gmfq-pricing-research')?.querySelector('.gmfq-research-plot svg, .gmfq-research-plot p');
       },null,{timeout:20000});
       const research=await page.evaluate(async()=>{
         const d=document.getElementById('gmfq-page').contentDocument;
         const panel=d.getElementById('gmfq-pricing-research');
         const feed=await fetch('https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/main/live_data/sections/OIS_OPERATIONAL_VIEW.json',{cache:'no-store'}).then(x=>x.json());
         const snb=await fetch('https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/main/live_data/sections/CHF_SNB_10Y_SPOT_CONTEXT.json',{cache:'no-store'}).then(x=>x.json());
         const access=await fetch('https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/main/live_data/sections/OIS_SOURCE_READINESS_VIEW.json',{cache:'no-store'}).then(x=>x.json());
         const days=x=>(Date.parse(window.GMFQ_OIS_RESEARCH_V1.romeTodayIso()+'T00:00:00Z')-Date.parse(x+'T00:00:00Z'))/86400000;
         const eligible=['GBP','JPY','AUD','CAD'].filter(k=>{
           const x=feed.currencies?.[k];
           return x?.operational_status==='GREEN_OFFICIAL'&&x.quality==='OFFICIAL_CERTIFIED'&&
             days(x.as_of)>=0&&days(x.as_of)<=4&&['3m','6m','12m'].every(t=>Number.isFinite(x.horizons?.[t]?.policy_delta_bp));
         });
         const secondary=['USD','EUR','CHF'].filter(k=>feed.currencies?.[k]?.operational_status==='WITHHELD'&&
           feed.currencies?.[k]?.secondary_quote_context?.full_curve_usable===false&&
           feed.currencies?.[k]?.secondary_quote_context?.policy_delta_allowed===false);
         return {
           actualCurves:panel.querySelectorAll('svg polyline').length,expectedCurves:eligible.length,
           secondaryCards:panel.querySelectorAll('.gmfq-quote-card').length,expectedCards:secondary.length,
           note:panel.textContent,docWidth:d.documentElement.scrollWidth,viewport:d.documentElement.clientWidth,
           readinessCount:panel.querySelectorAll('#gmfq-source-readiness .gmfq-source-row').length,
           readinessLinks:panel.querySelectorAll('#gmfq-source-readiness a').length,
           readinessContent:panel.querySelector('#gmfq-source-readiness')?.textContent,
           readinessExpected:access?.schema==='GMFQ_OIS_SOURCE_READINESS_VIEW_V1'&&
             access.status==='READ_ONLY_SOURCE_READINESS'&&access.prices_omitted===true&&
             access.no_automatic_promotions===true&&days(access.as_of)>=0&&days(access.as_of)<=3&&
             ['USD','EUR','CHF','NZD'].every(k=>
               ['WITHHELD','GREEN_ESTIMATED','GREEN_OFFICIAL'].includes(access.currencies?.[k]?.status)&&
               access.currencies[k].status===feed.currencies?.[k]?.operational_status&&
               access.currencies[k].usable_for_policy_pricing===false&&
               access.currencies[k].backtest_eligible_as_official===false)&&
             access.blocked_currency_count===
               ['USD','EUR','CHF','NZD'].filter(k=>access.currencies[k].status==='WITHHELD').length?
             4:null,
           snbBox:panel.querySelector('#gmfq-chf-snb-10y-context')?.textContent,
           snbExpected:snb?.schema==='GMFQ_CHF_SNB_10Y_SPOT_CONTEXT_V1'&&snb.status==='OFFICIAL_PUBLISHED_10Y_INFORMATIONAL'&&
             snb.has_current_2y===false&&snb.eligible_for_curve_spreads===false&&snb.eligible_for_core_signals===false&&
             Number.isFinite(snb.value_percent)&&days(snb.as_of)>=0&&days(snb.as_of)<=4?
             {value:snb.value_percent.toFixed(3),date:snb.as_of}:null
         };
       });
       if(research.actualCurves!==research.expectedCurves||research.secondaryCards!==research.expectedCards||
          !research.note.includes('non sono una curva OIS')||
          !research.note.includes('NON curva OIS né policy delta')||
          (process.env.GITHUB_EVENT_NAME!=='pull_request'&&(
             research.readinessExpected===null||
             research.readinessCount!==research.readinessExpected||
             research.readinessLinks!==research.readinessExpected||
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
             plotVisible:!!p?.querySelector('.gmfq-research-plot')?.getClientRects().length,
             secondaryHidden:!(p?.querySelector('.gmfq-quote-card')?.getClientRects().length),
             sourcePresent:!!p?.querySelector('#gmfq-source-readiness')};
         });
         if(reading.status!=='READ_ONLY'||Number(reading.curves)!==research.expectedCurves||
            !reading.closed||!reading.plotVisible||!reading.secondaryHidden||
            !reading.sourcePresent||!reading.heading?.includes('/8'))
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
       if(p.pairs!==28||p.buttons!==8||
          !p.content?.includes('Modello: '+pricing.setup_date)||
          !p.content?.includes('Baseline Macro/Tassi: '+pricing.setup_macro_asof)||
          !p.content?.includes('Il dettaglio sopra resta la lettura canonica della tesi')||
          p.docWidth>p.viewport+16)
          throw Error(name+' public Pair Deep Dive date/routing regression '+JSON.stringify(p));
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
           return {exists:!!c,legs:[...c?.querySelectorAll('.gmfq-change-leg')||[]].map(x=>({
             ccy:x.dataset.gmfqChangeCurrency,status:x.dataset.gmfqYieldChange,
             text:x.querySelector('.gmfq-change-measured')?.textContent,
             model:x.querySelector('.gmfq-change-model')?.textContent})),
             note:c?.querySelector('.gmfq-change-warning')?.textContent,
             width:d?.documentElement.scrollWidth,viewport:d?.documentElement.clientWidth};
         });
         if(!change.exists||change.legs.length!==2||
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
         if(!evidence.exists||evidence.rows.length!==3||
            !evidence.rows[0]?.includes('USD')||
            !evidence.rows[1]?.includes('EUR')||
            !evidence.rows[2]?.includes('Estensione del prezzo:')||
            !evidence.rows[2]?.includes('Posizionamento:')||
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
           docWidth:doc?.documentElement.scrollWidth,viewport:doc?.documentElement.clientWidth,
           legacy:!!doc?.querySelector('[data-gmfq-operational="risk"]')};
       });
       if(!['SECONDARY_CURRENT','SECONDARY_HISTORICAL'].includes(gold.state)||
          !/^20\d{2}-\d{2}-\d{2}$/.test(gold.asof||'')||
          !gold.text?.includes('Gold Price LBMA · WITHHELD')||
          !gold.text?.includes('GC=F · futures COMEX indicativo')||
          !gold.text?.includes('non equivale a oro spot')||
          gold.quote==='—'||gold.legacy||gold.docWidth>gold.viewport+16){
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
           cards:[...panel?.querySelectorAll('[data-cross-instrument]')||[]]
             .map(c=>({name:c.dataset.crossInstrument,status:c.dataset.crossStatus,
               asof:c.textContent,value:c.querySelector('.gmfq-cross-risk-value')?.textContent})),
           text:panel?.textContent,width:d?.documentElement.scrollWidth,
           viewport:d?.documentElement.clientWidth};
       });
       if(risk.cards.length!==3||
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
           closed:detail?.open===false,
           hidden:![...panel.querySelectorAll('.gmfq-macro-observation')].some(x=>x.getClientRects().length>0),
           count:panel.querySelectorAll('.gmfq-macro-observation').length,
           width:d.documentElement.scrollWidth,viewport:d.documentElement.clientWidth};
       });
       if(!macroFirst.baseline||!macroFirst.preview?.includes('Inflazione: periodo ')||
          !macroFirst.preview.includes('Lavoro: periodo ')||
          !macroFirst.closed||!macroFirst.hidden||macroFirst.count!==2||
          macroFirst.width>macroFirst.viewport+16)
         throw Error(name+' public Macro reading not deployed '+JSON.stringify(macroFirst));
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
           count:p.querySelectorAll('.gmfq-blocker-pair').length,
           closed:details?.open===false,
           hidden:![...p.querySelectorAll('.gmfq-blocker-pair')].some(x=>x.getClientRects().length>0),
           width:d.documentElement.scrollWidth,viewport:d.documentElement.clientWidth};
       });
       if(!screenerFirst.summary?.includes('Macro vs Tassi/CB: ')||
          !screenerFirst.summary.includes('Differenziale 2Y senza tesi: ')||
          !screenerFirst.summary.includes('Vantaggio insufficiente: ')||
          screenerFirst.count!==11||!screenerFirst.closed||!screenerFirst.hidden||
          screenerFirst.panelWidth>screenerFirst.panelClient+2||
          screenerFirst.width>Math.max(screenerFirst.viewport+16,screenerFirst.nativeWidth+2))
         throw Error(name+' public Screener source-first reading not deployed '+JSON.stringify(screenerFirst));
       await page.frameLocator('#gmfq-page').locator('#gmfq-blocker-details>summary').press('Enter');
       if(!(await page.frameLocator('#gmfq-page').locator('#gmfq-screener-blockers button[data-pair="GBPJPY"]').isVisible()))
         throw Error(name+' public Screener individual reasons inaccessible');
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
             heading:p.querySelector('.gmfq-first-claim')?.textContent,
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
         if(!reading.originalChart||!reading.originalTable||!reading.closed||
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
           .locator('#'+(pageName==='banche'?'gmfq-cb-reading-first':'gmfq-cot-reading-first')+' details>summary')
           .press('Enter');
         const open=await page.evaluate(section=>{
           const d=document.getElementById('gmfq-page')?.contentDocument,
             p=d?.getElementById(section==='banche'?'gmfq-cb-reading-first':'gmfq-cot-reading-first');
           return {open:p?.querySelector('details')?.open,
             visible:[...p?.querySelectorAll('details p')||[]].every(x=>x.getClientRects().length>0)};
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
