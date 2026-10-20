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
          !audit.detail?.includes('Non è DXY ICE ufficiale')||
          !audit.detail?.includes('futures monetari, non OIS puri')||
          !audit.detail?.includes('Le date delle diverse fonti non sono intercambiabili')||
          audit.documentWidth>audit.viewport+16)
         throw Error(name+' public source-date disclosure missing '+JSON.stringify(audit));
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
           readinessCount:panel.querySelectorAll('#gmfq-source-readiness .gmfq-source-row').length,
           readinessLinks:panel.querySelectorAll('#gmfq-source-readiness a').length,
           readinessContent:panel.querySelector('#gmfq-source-readiness')?.textContent,
           readinessExpected:access?.schema==='GMFQ_OIS_SOURCE_READINESS_VIEW_V1'&&
             access.status==='READ_ONLY_SOURCE_READINESS'&&access.prices_omitted===true&&
             access.no_automatic_promotions===true&&days(access.as_of)>=0&&days(access.as_of)<=3&&
             access.blocked_currency_count===4&&
             ['USD','EUR','CHF','NZD'].every(k=>access.currencies?.[k]?.status==='WITHHELD')?
             Object.values(access.currencies||{}).filter(x=>x.status==='WITHHELD').length:null,
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
         current=await page.evaluate(()=>{
           return !!document.querySelector('script[src*="home-navigation-v10.js?v=thesis-reaction-20261020"]');
         });
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
       if(!current)current=await page.evaluate(()=>!!document.querySelector('script[src*="home-navigation-v10.js?v=thesis-reaction-20261020"]'));
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
       const p=await page.evaluate(()=>{
         const d=document.getElementById('gmfq-page')?.contentDocument;
         return {pairs:d?.querySelectorAll('#pair-index button.pair-open[data-pair]').length,
           buttons:d?.querySelectorAll('#gmfq-pair-research-path button[data-gmfq-study-currency]').length,
           content:d?.getElementById('gmfq-pair-research-path')?.textContent,
           docWidth:d?.documentElement.scrollWidth,viewport:d?.documentElement.clientWidth};
       });
       if(p.pairs!==28||p.buttons!==8||
          !p.content?.includes('non aggiorna automaticamente il giudizio del motore')||
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
         if(liveAudit.status!=='COERENTE'||
             liveAudit.dates.join('/')!=='2026-10-15/2026-10-16'||
             !liveAudit.texts[0]?.includes('+6.7 bp')||
             !liveAudit.texts[1]?.includes('+0.40%')||
             !liveAudit.note?.includes('non prova causalità')||
             liveAudit.width>liveAudit.viewport+16)
            throw Error(name+' public EURUSD Rates/FX reaction audit incorrect '+JSON.stringify(liveAudit));
         const decision=await page.evaluate(()=>{
           const d=document.getElementById('gmfq-page')?.contentDocument,
             c=d?.getElementById('gmfq-pair-decision-bridge');
           return {status:c?.dataset.bridgeStatus,
             cells:[...c?.querySelectorAll('.gmfq-decision-cols>div')||[]].map(x=>x.textContent),
             content:c?.textContent,documentWidth:d?.documentElement.scrollWidth,
             viewport:d?.documentElement.clientWidth};
         });
         if(decision.status!=='CONTRO_TESI'||decision.cells.length!==3||
            !decision.cells[0]?.includes('USD')||!decision.cells[1]?.includes('CON RISCHI')||
            !decision.cells[2]?.includes('Coerente tra 2Y e FX')||
            !decision.content?.includes('Una coerenza 2Y–FX non equivale a conferma della tesi')||
            !decision.content?.includes('Non sono disponibili trigger numerici certificati')||
            decision.documentWidth>decision.viewport+16)
           throw Error(name+' Public EURUSD bridge conflates Rates/FX agreement with USD thesis '+JSON.stringify(decision));
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
     await page.close();
   }
   console.log('CONTROL_ROOM_V10_PUBLIC_G8_DXY_NAVIGATION_GREEN');
 } finally {await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
