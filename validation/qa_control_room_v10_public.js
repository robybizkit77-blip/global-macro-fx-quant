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
     const state=await getState(page);
     console.log('PUBLIC_V10_SMOKE',name,JSON.stringify(state));
     if(state.mode!=='live'||state.chartCount!==8||state.pricingCount!==8||!state.globe||
        state.badApprofondisci||!state.dxy||state.dxy==='—'||state.width>state.viewport+16||
        !state.notes.includes('R²')||!state.notes.includes('CHF/EUR')||
        !state.notes.includes('base ')){
       throw Error(name+' public Home contract failed: '+JSON.stringify(state));
     }
     // Verify that the actual published Rates file has caught up with the
     // official, manually verified NZD 16 Oct snapshot. NZD must no longer be
     // labeled as AUD-proxy STIMA in the rate-bar note.
     const ratesMirror=await page.evaluate(async()=>{const r=await fetch('/global-macro-fx-quant/live_data/sections/NATIVE_RATES_DATA.json',{cache:'no-store'});if(!r.ok)throw Error('Rates mirror HTTP '+r.status);const x=await r.json();return {date:x.NZD.date,y2:x.NZD['2Y'],y10:x.NZD['10Y'],quality:x.NZD.quality}});
     if(ratesMirror.date!=='2026-10-16'||ratesMirror.y2!==3.89||ratesMirror.y10!==5.0||
        ratesMirror.quality!=='FULL_CURRENT_OFFICIAL_MANUAL_VERIFIED'||
        state.notes.includes('NZD/AUD')){
       throw Error(name+' public NZD official/mirror contract failed: '+JSON.stringify({ratesMirror,notes:state.notes}));
     }
     console.log('PUBLIC_NZD_OFFICIAL_RATES_GREEN',name,JSON.stringify(ratesMirror));
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
         setup_date:setup.price_asof,setup_audit:setup.price_audit?.status,
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
        pricing.setup_audit!=='PASS'||!pricing.setup_date||
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
           return !!d?.getElementById('gmfq-chf-snb-10y-context');
         });
         if(snbVersionVisible)break;
         await page.goto(BASE+'?snb10qa='+Date.now()+'-'+attempt+'#/tassi?focus=ois',{waitUntil:'domcontentloaded',timeout:120000});
         try{
           await page.waitForFunction(()=>{
             const d=document.getElementById('gmfq-page')?.contentDocument;
             return !!d?.getElementById('gmfq-chf-snb-10y-context');
           },null,{timeout:9000});
         }catch(_){console.log('PUBLIC_V10_SNB_VERSION_PENDING',name,attempt)}
         await page.waitForTimeout(4000);
       }
       if(!snbVersionVisible){
         snbVersionVisible=await page.evaluate(()=>!!document.getElementById('gmfq-page')?.contentDocument?.getElementById('gmfq-chf-snb-10y-context'));
       }
       if(!snbVersionVisible)throw Error(name+' PUBLIC_V10_CDN_STALE_NO_SNB_VERSION after cache-busted retries');
       await page.waitForFunction(()=>{
         const d=document.getElementById('gmfq-page')?.contentDocument;
         return d?.getElementById('gmfq-pricing-research')?.querySelector('.gmfq-research-plot svg, .gmfq-research-plot p');
       },null,{timeout:20000});
       const research=await page.evaluate(async()=>{
         const d=document.getElementById('gmfq-page').contentDocument;
         const panel=d.getElementById('gmfq-pricing-research');
         const feed=await fetch('https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/main/live_data/sections/OIS_OPERATIONAL_VIEW.json',{cache:'no-store'}).then(x=>x.json());
         const snb=await fetch('https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/main/live_data/sections/CHF_SNB_10Y_SPOT_CONTEXT.json',{cache:'no-store'}).then(x=>x.json());
         const days=x=>(Date.UTC(new Date().getUTCFullYear(),new Date().getUTCMonth(),new Date().getUTCDate())-Date.parse(x+'T00:00:00Z'))/86400000;
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
           note:panel.innerText,docWidth:d.documentElement.scrollWidth,viewport:d.documentElement.clientWidth,
           snbBox:panel.querySelector('#gmfq-chf-snb-10y-context')?.innerText,
           snbExpected:snb?.schema==='GMFQ_CHF_SNB_10Y_SPOT_CONTEXT_V1'&&snb.status==='OFFICIAL_PUBLISHED_10Y_INFORMATIONAL'&&
             snb.has_current_2y===false&&snb.eligible_for_curve_spreads===false&&snb.eligible_for_core_signals===false&&
             Number.isFinite(snb.value_percent)&&days(snb.as_of)>=0&&days(snb.as_of)<=4?
             {value:snb.value_percent.toFixed(3),date:snb.as_of}:null
         };
       });
       if(research.actualCurves!==research.expectedCurves||research.secondaryCards!==research.expectedCards||
          !research.note.includes('non sono una curva OIS')||
          !research.note.includes('NON curva OIS né policy delta')||
          research.docWidth>research.viewport+16||
          (research.snbExpected?
             !research.snbBox?.includes('CHF 10Y SNB '+research.snbExpected.value+'%')||
             !research.snbBox.includes(research.snbExpected.date)||
             !research.snbBox.includes('SOLO INFORMATIVO')||
             !research.snbBox.includes('nessuno spread o segnale'):
             !research.snbBox?.includes('non disponibile o non corrente')))
         throw Error(name+' public certified/secondary Rates research fail-closed contract '+JSON.stringify(research));
       console.log('CONTROL_ROOM_PREVIEW_PUBLIC_PRICING_RESEARCH_GREEN',name,
         JSON.stringify({curves:research.actualCurves,secondary:research.secondaryCards,viewport:research.viewport}));
     }
     await page.goto(BASE+'#/home',{waitUntil:'domcontentloaded',timeout:120000});
     await page.waitForFunction(()=>document.getElementById('gmfq-page')?.contentDocument?.querySelectorAll('#pairs tr[data-filter]').length>0,null,{timeout:60000});
     const homePair=await page.frameLocator('#gmfq-page').locator('#pairs tr[data-filter]').first().getAttribute('data-filter');
     if(!/^[A-Z]{6}$/.test(homePair||''))throw Error(name+' Preview Home invalid pair deep link '+homePair);
     await page.frameLocator('#gmfq-page').locator('#pairs tr[data-filter]').first().click();
     await page.waitForURL(url=>url.hash==='#/screener?pair='+homePair,{timeout:15000});
     console.log('CONTROL_ROOM_PREVIEW_PAIR_NAVIGATION_PASS',name,homePair);
     await page.goto(BASE+'#/home',{waitUntil:'domcontentloaded',timeout:120000});
     await page.waitForFunction(()=>document.getElementById('gmfq-page')?.contentDocument?.querySelectorAll('#ois .oisrow').length===8,null,{timeout:60000});
     await page.frameLocator('#gmfq-page').locator('#ois .oisrow[data-ccy="USD"]').click();
     await page.waitForURL(/#\/banche\?ccy=USD$/,{timeout:15000});
     await page.close();
   }
   console.log('CONTROL_ROOM_V10_PUBLIC_G8_DXY_NAVIGATION_GREEN');
 } finally {await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
