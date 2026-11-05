'use strict';
const {chromium}=require('playwright'),fs=require('fs'),path=require('node:path');
const projectRoot=path.resolve(__dirname,'..');
const sourceJSON=p=>JSON.parse(fs.readFileSync(path.join(projectRoot,p),'utf8'));
const baseRates=sourceJSON('live_data/sections/NATIVE_RATES_DATA.json');
const chfNzdResearch=sourceJSON('site/fx-quant-v2/chf-nzd-benchmark-research.json');
const {derive:deriveWorking}=require('../site/fx-quant-v2/assets/rates-working-model-v1.js');
const todayRome=new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Rome',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
const nzdAsxSource=sourceJSON('live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json');
const nzdAsxAnchor=sourceJSON('site/fx-quant-v2/nzd-asx-government-anchor-v1.json');
// Mirror the V2 Coppie research-only derive with SAME-CONTRACT ASX 6M scenario.
// This does not update any canonical rates or FX Core signals.
const workingResearch=deriveWorking(baseRates,chfNzdResearch,todayRome,nzdAsxSource,nzdAsxAnchor);
const spreadLegNZD=workingResearch.rates.NZD||baseRates.NZD;
const spreadLegCHF=workingResearch.rates.CHF||baseRates.CHF;
const expectedIndicativeSpread=!!(spreadLegNZD.estimated||spreadLegCHF.estimated);
const expected2yGap=(spreadLegNZD['2Y']-spreadLegCHF['2Y'])*100;
const expectedGapText=(expected2yGap>=0?'+':'−')+
 Math.abs(expected2yGap).toLocaleString('it-IT',{minimumFractionDigits:1,maximumFractionDigits:1})+' bp';
const expectedLegTag=r=>r.tenor_quality?.['2Y']==='STIMATO'?'STIMA 2Y':
 r.tenor_quality?.['2Y']==='WEB_PROXY'?'PROXY 2Y':
 r.tenor_quality?.['2Y']==='OSSERVATO'&&r.research_observed===true&&r.no_core_effect===true?
 'SNB 2Y · RICERCA':'FEED CANONICO 2Y';
const base=(process.env.FXV2_BASE||'http://127.0.0.1:8000/site/fx-quant-v2').replace(/\/+$/,'');
const mode=process.env.FXV2_MODE||'local';
const out='fxv2-browser-evidence';fs.mkdirSync(out,{recursive:true});
const pages=[
 ['home','index.html','#g8Grid'],['valute','valute.html','#currencyGrid'],
 ['coppie','coppie.html','#screener'],['tassi','tassi.html','#countryTabs'],
 ['ois','ois.html','#pricingGrid'],
 ['macro','macro.html','#currencyGrid'],['banche','banche.html','#cbGrid'],
 ['cot','cot.html','#pickGrid'],['cross','cross-asset.html','#assetGrid'],
 ['liquidita','liquidita-credito.html','#countryGrid'],
 ['calendario','calendario-news.html','#eventGrid'],['ricerca','research.html','#archive']];
const viewports=[['desktop',{width:1440,height:900}],['mobile',{width:390,height:844}]];
const markers={
 valute:['#periodContext','fixing BCE dal feed canonico'],
 tassi:['#feedStatus','Feed repository acquisiti'],
 macro:['#dataStatus','Feed canonico MACRO_SERIES collegato'],
 banche:['#dataStatus','Feed banche centrali collegato'],
 cot:['#freshness','Origine:'],cross:['#sourceList','Proxy futures secondari'],
 calendario:['#feedAsOf','Calendario canonico verificato']
};
const actions={valute:'button[data-period="1M"]',macro:'button[data-ccy="NZD"]',
 banche:'button[data-c="NZD"]',cot:'button[data-mode="netoi"]',
 cross:'button[data-view="ENERGY"]',calendario:'button[data-filter="next7"]'};
const result={schema:'GMFQ_FXV2_BROWSER_QA_V1',mode,base,started_utc:new Date().toISOString(),pages:[],findings:[]};
function issue(name,view,kind,detail){result.findings.push({name,view,kind,detail:String(detail).slice(0,450)});}
async function audit(browser,name,file,selector,view,viewport){
 const ctx=await browser.newContext({viewport,reducedMotion:'reduce'}),page=await ctx.newPage();
 const exceptions=[],network=[],rec={name,view,http:null,menu:null,primary:null,overflow:null,feed:null};
 page.on('pageerror',e=>exceptions.push(String(e)));
 // Chromium may cancel a completed/unused request when navigating away
 // from a fully rendered page (net::ERR_ABORTED). Feed availability is
 // independently asserted by mandatory page markers below. Keep real HTTP,
 // DNS, timeout and connection errors strictly visible.
 page.on('requestfailed',r=>{
  const err=r.failure()?.errorText||'UNKNOWN';
  if(/raw\.githubusercontent\.com/.test(r.url()) && err!=='net::ERR_ABORTED')
   network.push(r.url()+' '+err);
 });
 page.on('response',r=>{if(/raw\.githubusercontent\.com/.test(r.url())&&r.status()>=400)network.push(r.status()+' '+r.url());});
 try{
  const response=await page.goto(base+'/'+file,{waitUntil:'domcontentloaded',timeout:70000});
  rec.http=response?.status();if(rec.http!==200)throw Error('HTTP '+rec.http);
  await page.locator('#fxv2-global-header').waitFor({timeout:20000});
  await page.waitForLoadState('networkidle',{timeout:16000}).catch(()=>{});
  await page.waitForTimeout(550);
  const o=await page.evaluate(selector=>{
   const root=document.querySelector(selector),h=document.querySelector('#fxv2-global-header'),s=document.body.innerText;
   return{menu:h?.querySelectorAll('#fxv2-nav a').length||0,
     current:h?.querySelectorAll('#fxv2-nav a[aria-current="page"]').length||0,
     page:document.body.dataset.fxv2Page||'',
     primary:root?.children.length||0,exists:!!root,
     overflow:Math.max(0,document.documentElement.scrollWidth-innerWidth),
     offenders:[...document.querySelectorAll('body *')].map(e=>({e,box:e.getBoundingClientRect()})).filter(x=>x.box.width>0&&x.box.height>0&&x.box.right>innerWidth+12).slice(0,15).map(x=>({tag:x.e.tagName,id:x.e.id,className:String(x.e.className||'').slice(0,80),left:Math.round(x.box.left),right:Math.round(x.box.right),width:Math.round(x.box.width)})),
     textLen:s.trim().length,bad:['undefined','[object Object]','NaN'].filter(x=>s.includes(x))};
  },selector);
  Object.assign(rec,o);
  if(o.menu!==12||o.current!==1||o.page!==name)issue(name,view,'navigation',JSON.stringify(o));
  if(!o.exists||!o.primary)issue(name,view,'empty_content',selector);
  if(o.textLen<450)issue(name,view,'empty_page',o.textLen);
  if(o.overflow>12)issue(name,view,'overflow_px',JSON.stringify({overflow:o.overflow,offenders:o.offenders}));
  if(o.bad.length)issue(name,view,'bad_rendered_values',o.bad);
  if(markers[name]){
   const [s,expected]=markers[name];
   const full=((await page.locator(s).first().textContent().catch(()=>''))||'').trim();
   rec.feed=full.slice(0,340);
   if(!full.includes(expected))issue(name,view,'live_feed_not_confirmed',rec.feed||s+' empty');
  }
  if(name==='tassi'){
    await page.waitForFunction(()=>
      document.querySelector('#feedStatus')?.textContent?.includes('date e qualità per scadenza')&&
      document.querySelectorAll('#pricingGrid .data-card').length===3,
      null,{timeout:14000});
    const detail=await page.locator('#pricingGrid').textContent();
    if(!detail.includes('FUTURES')&&!detail.includes('STIMA')&&
       !detail.includes('INFORMATIVA'))
      issue(name,view,'rates_per_horizon_provenance_not_visible',detail.slice(0,700));
  }
  if(name==='cross'&&mode==='public'){
    const full=((await page.locator('#sourceList').textContent())||'');
    if(!full.includes('Cross-Asset FRED/Cboe:')||
       !full.includes('SP500')||!full.includes('NASDAQCOM')||!full.includes('VIX'))
      issue(name,view,'cross_asset_feed_not_loaded','Expected dated FRED/Cboe five-series source marker not visible: '+full.slice(-450));
    const display=((await page.locator('#vixFact').textContent())||'');
    if(!/^VIX\s+[\d,.]+/.test(display))issue(name,view,'vix_render_not_synced','VIX UI value not rendered: '+display);
  }
  if(name==='liquidita'){
    await page.waitForFunction(()=>
      document.querySelector('#footerDate')?.textContent?.includes('Credito ICE/FRED:'),
      null,{timeout:13000});
    const credit=await page.evaluate(()=>({
      footer:document.querySelector('#footerDate')?.textContent||'',
      rows:[...document.querySelectorAll('#assetRows .asset')].map(x=>x.textContent||'')
    }));
    if(credit.rows.length!==4||!credit.footer.includes('2/2 serie pubblicate')||
       !credit.rows[2].includes('FRED/ICE · FONTE PUBBLICATA, RICERCA V2')||
       !credit.rows[3].includes('FRED/ICE · FONTE PUBBLICATA, RICERCA V2'))
      issue(name,view,'liquidity_ig_hy_not_live',JSON.stringify(credit).slice(0,500));
    if(mode==='pr-local'&&view==='desktop'){
      // Fail one published source and prove other credit leg remains independent.
      const feed=JSON.parse(fs.readFileSync('site/fx-quant-v2/cross-asset-live-data.json','utf8'));
      feed.streams.IG_OAS.source_url='https://example.org/NOT_ICE_FRED';
      await page.route('**/cross-asset-live-data.json*',route=>route.fulfill({
        status:200,contentType:'application/json',body:JSON.stringify(feed)
      }));
      await page.reload({waitUntil:'domcontentloaded'});
      await page.waitForFunction(()=>
        document.querySelector('#footerDate')?.textContent?.includes('1/2 serie pubblicate'),
        null,{timeout:16000});
      const partial=await page.evaluate(()=>({
        footer:document.querySelector('#footerDate')?.textContent,
        rows:[...document.querySelectorAll('#assetRows .asset')].map(x=>x.textContent)
      }));
      if(!partial.rows[2].includes('PUBLISHED_OFFICIAL_INDEX')||
         !partial.rows[3].includes('FRED/ICE · FONTE PUBBLICATA, RICERCA V2'))
        issue(name,view,'liquidity_partial_feed_did_not_preserve_ig',JSON.stringify(partial).slice(0,450));
      await page.unroute('**/cross-asset-live-data.json*');
    }
  }
  if(name==='macro'){
    await page.waitForFunction(()=>document.querySelector('#macroCandidateNote')?.textContent?.includes('BASELINE MACRO V1 · ricerca descrittiva al'),null,{timeout:15000});
    const usdCandidate=((await page.locator('#macroCandidateNote').textContent())||'');
    if(!usdCandidate.includes('USD')||!usdCandidate.includes('Disoccupazione: variazione')||
       !usdCandidate.includes('Nessuna forza FX')||
       !usdCandidate.includes('Inflazione: variazione'))
      issue(name,view,'macro_candidate_read_only_missing',usdCandidate.slice(0,480));
    await page.locator('#currencyGrid button[data-ccy="NZD"]').click();
    const nzdCandidate=((await page.locator('#macroCandidateNote').textContent())||'');
    if(!nzdCandidate.includes('NZD')||!nzdCandidate.includes('accelerazione NON calcolabile'))
      issue(name,view,'macro_candidate_gdp_missing_not_explicit',nzdCandidate.slice(0,480));
  }
  if(name==='coppie'&&(mode==='public'||mode==='pr-local')){
    // Informative 2Y spread: research overlays must never enter pair quality signals.
    await page.locator('#allPairs').selectOption('NZDCHF');
    await page.waitForFunction(()=>document.querySelector('#pairGap')?.textContent?.includes('bp')&&document.querySelector('#gapDate')?.textContent?.trim().length>0,null,{timeout:15000});
    const x=await page.evaluate(()=>({
      gap:document.querySelector('#pairGap')?.textContent,
      quality:document.querySelector('#gapDate')?.textContent,
      a:document.querySelector('#legADate')?.textContent,
      b:document.querySelector('#legBDate')?.textContent,
      caveat:document.querySelector('#pairRatesSourceNote')?.textContent,
      canonical:document.querySelector('#pairQuality')?.textContent
    }));
    const baseLabel=expectedLegTag(spreadLegNZD),quoteLabel=expectedLegTag(spreadLegCHF);
    const validSource=x.a.includes(baseLabel)&&x.b.includes(quoteLabel);
    const validProvenance=expectedIndicativeSpread?
      x.quality.includes('STIMA/PROXY INDICATIVO')&&
      x.caveat.includes('NON leggere lo spread come repricing'):
      !x.quality.includes('STIMA/PROXY INDICATIVO')&&
      x.caveat.includes('Lo spread di livello non è OIS');
    if(x.gap!==expectedGapText||!validSource||!validProvenance||!x.canonical)
      issue(name,view,'pair_estimated_spread_missing',
       JSON.stringify({...x,expectedGapText,baseLabel,quoteLabel,expectedIndicativeSpread}));
    // Separate Macro -> pricing bridge: 3M/6M/12M sources must move with the
    // selected pair and must not change the original quality verdict.
    await page.waitForFunction(()=>
      document.querySelector('#macroOisBase')?.textContent?.includes('3M')&&
      document.querySelector('#macroOisQuote')?.textContent?.includes('12M')&&
      document.querySelector('#macroOisGap')?.textContent?.includes('6M NZD'),
      null,{timeout:18000});
    const bridgeNZD=await page.evaluate(()=>({
      a:document.querySelector('#macroOisBase')?.textContent,
      b:document.querySelector('#macroOisQuote')?.textContent,
      spread:document.querySelector('#macroOisGap')?.textContent,
      freshness:document.querySelector('#macroOisFreshness')?.textContent,
      caveat:document.querySelector('#macroOisCaveat')?.textContent
    }));
    if(!bridgeNZD.a.includes('NZD · 3M')||
       !bridgeNZD.b.includes('CHF · 3M')||
       !bridgeNZD.a.includes('PROXY FUTURES')||
       !bridgeNZD.b.includes('FUTURES SECONDARI')||
       !bridgeNZD.freshness.includes('Nessuna differenza delle variazioni 1D/1W calcolata')||
       !bridgeNZD.caveat.includes('nessun backtest'))
      issue(name,view,'pair_macro_pricing_bridge_nzd_chf',JSON.stringify(bridgeNZD).slice(0,600));
    await page.locator('#allPairs').selectOption('EURUSD');
    await page.waitForFunction(()=>document.querySelector('#macroOisBase')?.textContent?.startsWith('EUR · 3M')&&
      document.querySelector('#macroOisQuote')?.textContent?.startsWith('USD · 3M'),null,{timeout:12000});
    const bridgeEUR=await page.evaluate(()=>({
      spread:document.querySelector('#macroOisGap')?.textContent,
      macro:document.querySelector('#macroOisMacroText')?.textContent,
      sources:document.querySelector('#macroOisFreshness')?.textContent
    }));
    if(!bridgeEUR.spread.includes('6M EUR − USD')||
       !bridgeEUR.macro.includes('baseline 25/09/2026')||
       !bridgeEUR.sources.includes('Nessuna differenza delle variazioni 1D/1W calcolata'))
      issue(name,view,'pair_macro_pricing_bridge_eur_usd',JSON.stringify(bridgeEUR));
    // New 28-pair research triangulation must be visible only as dated
    // independent evidence, never as a live signal or upgrade of pair quality.
    await page.waitForFunction(()=>
      document.querySelector('#macroOisTriangRates')?.textContent?.includes('PRICING RELATIVO')&&
      document.querySelector('#macroOisTriangMacro')?.textContent?.includes('MACRO V3')&&
      document.querySelector('#macroOisTriangPrice')?.textContent?.includes('PREZZO FX'),
      null,{timeout:15000});
    const triang=await page.evaluate(()=>({
      rates:document.querySelector('#macroOisTriangRates')?.textContent,
      macro:document.querySelector('#macroOisTriangMacro')?.textContent,
      price:document.querySelector('#macroOisTriangPrice')?.textContent,
      caveat:document.querySelector('#macroOisTriangCaveat')?.textContent
    }));
    if(!triang.rates.includes('EUR/USD')||
       !triang.rates.includes('3M')||
       !triang.rates.includes('6M')||
       !triang.rates.includes('12M')||
       !triang.rates.includes('non variazioni OIS')||
       !triang.macro.includes('nessun nuovo voto FX')||
       !/fixing 20\d\d-\d\d-\d\d/.test(triang.price)||
       !triang.price.includes('variazione 1M')||
       !triang.caveat.includes('Nessun segnale'))
      issue(name,view,'macro_rates_price_triangulation_missing',JSON.stringify(triang).slice(0,1400));
    await page.waitForFunction(()=>
      document.querySelector('#macroOisQuantReadiness')?.textContent?.includes('STORICO QUANT'),
      null,{timeout:17000});
    const auditText=await page.locator('#macroOisQuantReadiness').textContent();
    if(!auditText.includes('STORICO QUANT')||
       (auditText.includes('confronti datati')&&
        (!auditText.includes('non evidenza predittiva')||
         !auditText.includes('nessuna stima di alpha, hit rate o Sharpe'))))
      issue(name,view,'quant_temporal_research_missing_or_overclaimed',auditText.slice(0,700));
    await page.waitForFunction(()=>
      document.querySelector('#macroOisProspectiveStatus')?.textContent?.includes('ESPERIMENTO 6M'),
      null,{timeout:15000});
    const  sixMonthState=(await page.locator('#macroOisProspectiveStatus').textContent())||'';
    if(!sixMonthState.includes('ESPERIMENTO 6M')||
       !(/nessun risultato predittivo|Nessuna evidenza predittiva|non è ancora una validazione predittiva/.test(sixMonthState)))
      issue(name,view,'prospective_6m_research_mislabelled',sixMonthState.slice(0,720));
    await page.waitForFunction(()=>document.querySelector('#macroV3Context')?.textContent?.includes('DINAMICA MACRO (RICERCA, NON NUOVO BIAS)'),null,{timeout:18000});
    const dynamicEUR=(await page.locator('#macroV3Context').textContent())||'';
    if(!dynamicEUR.includes('PIL: variazione del ritmo trimestrale')||
       !dynamicEUR.includes('Baseline del motore 2026-09-25 invariata')||
       !dynamicEUR.includes('Senza consenso, sorpresa, OIS e reazione del prezzo'))
      issue(name,view,'dynamic_macro_not_read_only',dynamicEUR.slice(-650));
    await page.locator('#allPairs').selectOption('AUDCAD');
    const dynamicAUD=(await page.locator('#macroV3Context').textContent())||'';
    if(!dynamicAUD.includes('PIL: accelerazione relativa NON calcolabile')||
       !dynamicAUD.includes('Inflazione non sincronizzata'))
      issue(name,view,'macro_noncomparable_intervals_not_flagged',dynamicAUD.slice(-550));
    await page.locator('#allPairs').selectOption('EURUSD');
    const ordinary=((await page.locator('#gapDate').textContent())||'');
    if(ordinary.includes('STIMA/PROXY INDICATIVO'))
      issue(name,view,'pair_estimates_leaked','EUR/USD erroneously marked estimated: '+ordinary);
  }
  if(name==='coppie'){
    await page.locator('#allPairs').selectOption('EURUSD');
    await page.waitForFunction(()=>
      document.querySelector('#macroV3Context')?.textContent?.includes('MACRO V3 · osservazioni pubblicate'),
      null,{timeout:15000});
    const first=(await page.locator('#macroV3Context').textContent())||'';
    if(!first.includes('EUR')||!first.includes('USD')||
       !first.includes('disoccupazione')||!first.includes('Inflazione')||
       !first.includes('Crescita')||!first.includes('2026Q3')||
       !first.includes('annualizzato SAAR')||!first.includes('25/09')&&
       !first.includes('2026-09-25'))
      issue(name,view,'macro_v3_evidence_not_loaded',first.slice(0,440));
    const canonicalBefore=(await page.locator('#pairQuality').textContent())||'';
    await page.locator('#allPairs').selectOption('AUDCAD');
    const second=(await page.locator('#macroV3Context').textContent())||'';
    if(!second.includes('AUD')||!second.includes('CAD')||
       !second.includes('2026Q2')||!second.includes('non nuovo bias FX')||
       second===first)
      issue(name,view,'macro_v3_pair_swap_failed',second.slice(0,440));
    await page.locator('#allPairs').selectOption('EURUSD');
    const canonicalAfter=(await page.locator('#pairQuality').textContent())||'';
    if(canonicalBefore!==canonicalAfter)
      issue(name,view,'macro_v3_mutated_canonical_quality',
       'before='+canonicalBefore+' after='+canonicalAfter);
    if(mode==='pr-local'&&view==='desktop'){
      await page.route('**/macro-v3-current-evidence.json*',route=>route.fulfill({
        status:200,contentType:'application/json',body:JSON.stringify({
          schema:'GMFQ_MACRO_V3_G8_28PAIR_PUBLIC_OBSERVED_CONTEXT_V1',
          safe_to_recompute_structural_pair_theses:true,summary:{pairs:28}
        })
      }));
      await page.reload({waitUntil:'domcontentloaded'});
      await page.waitForFunction(()=>
       document.querySelector('#macroV3Context')?.textContent?.includes('ricerca non ancora verificata'),
       null,{timeout:17000});
      const rejected=(await page.locator('#macroV3Context').textContent())||'';
      if(rejected.includes('MACRO V3 · osservazioni pubblicate'))
        issue(name,view,'unsafe_macro_v3_promoted',rejected.slice(0,400));
      await page.unroute('**/macro-v3-current-evidence.json*');
    }
  }
  if(name==='ois'){
    await page.waitForFunction(()=>document.querySelectorAll('#pricingGrid button[data-c]').length===8,null,{timeout:15000});
    const data=await page.evaluate(()=>({
      cols:document.querySelectorAll('#pricingRows tr').length,
      cards:document.querySelectorAll('#pricingGrid button[data-c]').length,
      tenors:document.querySelectorAll('#tenors .term').length,
      gbp:[...document.querySelectorAll('#pricingGrid button[data-c]')].find(x=>x.dataset.c==='GBP')?.innerText||'',
      usd:[...document.querySelectorAll('#pricingGrid button[data-c]')].find(x=>x.dataset.c==='USD')?.innerText||'',
      nz:[...document.querySelectorAll('#pricingGrid button[data-c]')].find(x=>x.dataset.c==='NZD')?.innerText||'',
      status:document.querySelector('#feedStatus')?.innerText
    }));
    if(data.cards!==8||data.cols!==8||data.tenors!==3||
       !data.gbp.includes('OIS')||!data.usd.includes('FUTURES SECONDARI')||
       !data.nz.includes('PROXY FUTURES')||!data.status.includes('24/24')||
       !data.status.includes('tenori oltre 7 giorni')||
       !data.status.includes('OIS ufficiale solo GBP'))
       issue(name,view,'ois_g8_coverage_or_provenance',JSON.stringify(data));
    await page.locator('#pricingGrid button[data-c="JPY"]').click();
    const title=(await page.locator('#detailTitle').textContent())||'';
    const caveat=(await page.locator('#sourceCaveat').textContent())||'';
    const sourceAge=(await page.locator('#sourceDate').textContent())||'';
    if(!title.includes('Giappone')||!caveat.includes('non sono contratti OIS')||
       !sourceAge.includes('Nessun refresh dell’orologio cambia la data del prezzo.'))
      issue(name,view,'ois_country_interaction_failed',title+' '+caveat);
    await page.locator('#compareA').selectOption('GBP');
    await page.locator('#compareB').selectOption('USD');
    if(!((await page.locator('#compareFoot').textContent())||'').includes('Differenziale di livello INDICATIVO'))
      issue(name,view,'ois_cross_instrument_caveat_missing','Comparison must never be called an observed OIS spread');
  }
  if(name==='tassi'&&mode==='public'){
    // This is a read-only verification of V2 research panels, never a Core rates certification.
    for(const [ccy,expected,words] of [
      ['CHF','CHF · coppia SNB 2Y e 10Y sulla stessa base',['non è osservato','STIMA']],
      ['NZD','NZD · benchmark RBNZ cambiati',['Prima del cambio','Dopo il cambio']]
    ]){
      await page.locator('#countryTabs button[data-ccy="'+ccy+'"]').click({timeout:12000});
      await page.locator('#benchmarkResearch:not([hidden])').waitFor({timeout:12000});
      const head=((await page.locator('#benchmarkHeadline').textContent())||'').trim();
      const text=((await page.locator('#benchmarkResearch').textContent())||'');
      const grade=((await page.locator('#asof2').textContent())||'').trim();
      const curve=((await page.locator('#curveExplanation').textContent())||'').trim();
      const chfObserved=ccy==='CHF'&&grade.includes('OSSERVATO 2Y');
      const expectedWords=chfObserved?['Entrambi i rendimenti','nessuna stima']:words;
      if(/STIMA|PROXY/.test(grade)&&!curve.includes('CALCOLO INDICATIVO'))
        issue(name,view,'estimate_provenance_missing',ccy+' · '+grade+' · '+curve.slice(0,150));
      if(chfObserved&&!curve.includes('RICERCA SNB OSSERVATA'))
        issue(name,view,'observed_snb_pair_provenance_missing',ccy+' · '+grade+' · '+curve.slice(0,150));
      if(!head.includes(expected)||expectedWords.some(w=>!text.toLowerCase().includes(w.toLowerCase()))){
        issue(name,view,'research_benchmark_not_loaded','Source context for '+ccy+' not rendered: '+head+' '+text.slice(0,180));
      }
    }
  }
  if(name==='tassi'&&mode==='pr-local'){
    for(const ccy of ['CHF','NZD']){
      await page.locator('#countryTabs button[data-ccy="'+ccy+'"]').click({timeout:10000});
      await page.waitForFunction(
        ({currency})=>{
          const grade=document.querySelector('#asof2')?.textContent||'';
          return currency==='CHF'
            ?grade.includes('STIMA 2Y')||grade.includes('OSSERVATO 2Y')
            :grade.includes('PROXY 2Y');
        },{currency:ccy},{timeout:12000}
      );
      const level=((await page.locator('#curveLevel').textContent())||'').trim();
      const why=((await page.locator('#curveExplanation').textContent())||'').trim();
      if(!/\d/.test(level)||!(why.includes('CALCOLO INDICATIVO')||
            (ccy==='CHF'&&why.includes('RICERCA SNB OSSERVATA'))))
        issue(name,view,'working_estimate_missing',ccy+' · '+level+' · '+why);
    }
    await page.locator('#compareA').selectOption('CHF');
    await page.locator('#compareB').selectOption('NZD');
    const notes=((await page.locator('#compareNote').textContent())||'');
    const cards=await page.locator('#compareGrid .data-card').count();
    if(cards!==4||!notes.includes('STIME')||!notes.includes('PROXY'))
      issue(name,view,'estimated_diff_missing','CHF/NZD comparison cards='+cards+' '+notes.slice(0,250));
    await page.locator('#countryTabs button[data-ccy="AUD"]').click();
    await page.waitForFunction(()=>document.querySelector('#ratesNote')?.textContent?.includes('RBA F2: aggiornamento SETTIMANALE'),null,{timeout:14000});
    const audSummary=((await page.locator('#ratesNote').textContent())||'');
    const audSource=((await page.locator('#yieldSource').textContent())||'');
    if(!audSummary.includes('non stimiamo un 2Y/10Y giornaliero')||
       !audSource.includes('Cadenza RBA F2'))
      issue(name,view,'aud_cadence_missing',audSummary.slice(-240)+' '+audSource.slice(-140));
    // Exercise a newer fully verified official same-day 2Y/10Y research feed.
    await page.route('**/aud-rba-f2-research.json*',route=>route.fulfill({
      status:200,contentType:'application/json',body:JSON.stringify({
        schema:'GMFQ_FXV2_AUD_RBA_F2_RESEARCH_V1',currency:'AUD',
        status:'OFFICIAL_F2_CSV_FETCHED_RESEARCH_ONLY',as_of:'2026-11-02',
        '2Y':5.012,'10Y':5.234,curve_bp:22.2,
        source_download_verified:true,publication_date:'2026-11-03',
        source_url:'https://www.rba.gov.au/statistics/tables/csv/f2-data.csv',
        source:'Reserve Bank of Australia · F2 weekly research',
        series_2Y:'FCMYGBAG2D',series_10Y:'FCMYGBAG10D',
        same_date_same_source:true,research_only:true,
        canonical_government_rates_untouched:true,eligible_for_core:false,
        eligible_for_fx_pair_engine:false,eligible_for_backtests:false
      })
    }));
    await page.reload({waitUntil:'domcontentloaded'});
    await page.locator('#countryTabs button[data-ccy="AUD"]').click();
    await page.waitForFunction(()=>document.querySelector('#rate2')?.textContent?.includes('5,01'),null,{timeout:14000});
    const audRate=(await page.locator('#rate2').textContent())||'';
    const audQuality=(await page.locator('#asof2').textContent())||'';
    const audCaveat=(await page.locator('#curveExplanation').textContent())||'';
    if(!audRate.includes('5,01')||!audQuality.includes('OSSERVATO')||
       !audCaveat.includes('CALCOLO INDICATIVO'))
      issue(name,view,'aud_research_model_mismatch',audRate+' '+audQuality+' '+audCaveat.slice(0,180));
    await page.unroute('**/aud-rba-f2-research.json*');
  }
  if(name==='calendario'&&mode==='pr-local'&&view==='desktop'){
    // The two feeds are independently useful: a broken News feed must not freeze Calendar.
    const newsPath='**/NEWS_PULSE_OPERATIONAL.json*',calendarPath='**/CALENDAR_OPERATIONAL_VIEW.json*';
    await page.route(newsPath,route=>route.fulfill({
      status:200,contentType:'application/json',body:'{"schema":"INVALID_NEWS_TEST"}'
    }));
    await page.reload({waitUntil:'domcontentloaded'});
    await page.waitForFunction(()=>
      document.querySelector('#feedAsOf')?.textContent?.includes('News snapshot'),
      null,{timeout:18000});
    const calendarProof=(await page.locator('#feedAsOf').textContent())||'';
    if(!calendarProof.includes('Calendario canonico verificato:')||
       !calendarProof.includes('News snapshot'))
      issue(name,view,'news_outage_blocked_calendar',calendarProof);
    await page.unroute(newsPath);

    // Likewise, a broken Calendar does not suppress refreshed, dated News headlines.
    await page.route(calendarPath,route=>route.fulfill({
      status:200,contentType:'application/json',body:'{"schema":"INVALID_CALENDAR_TEST"}'
    }));
    await page.reload({waitUntil:'domcontentloaded'});
    await page.waitForFunction(()=>
      document.querySelector('#feedAsOf')?.textContent?.includes('News controllate:'),
      null,{timeout:18000});
    const newsProof=(await page.locator('#feedAsOf').textContent())||'';
    if(!newsProof.includes('Calendario snapshot')||
       !newsProof.includes('contenuto al '))
      issue(name,view,'calendar_outage_blocked_news',newsProof);
    await page.unroute(calendarPath);
  }
  if(view==='mobile'){
   const b=page.locator('#fxv2-global-header .fxv2-toggle');
   await b.click({timeout:10000});
   if((await b.getAttribute('aria-expanded'))!=='true')issue(name,view,'mobile_menu','open failed');
   await b.click({timeout:10000});
   if((await b.getAttribute('aria-expanded'))!=='false')issue(name,view,'mobile_menu','close failed');
  }
  if(actions[name]){
   const b=page.locator(actions[name]).first();
   if(!(await b.count()))issue(name,view,'interaction_missing',actions[name]);
   else{
    await b.click({timeout:10000});await page.waitForTimeout(160);
    const ok=await b.evaluate(e=>e.getAttribute('aria-pressed')==='true'||e.classList.contains('active')||e.classList.contains('on'));
    if(!ok)issue(name,view,'interaction_failed',actions[name]);
   }
  }
 }catch(e){rec.error=String(e);issue(name,view,'load_or_interaction_error',e);}
 finally{
  rec.exceptions=exceptions.slice(0,7);rec.network=network.slice(0,7);
  exceptions.forEach(x=>issue(name,view,'uncaught_javascript',x));
  network.forEach(x=>issue(name,view,'feed_network_failure',x));
  if(result.findings.some(x=>x.name===name&&x.view===view))
   try{await page.screenshot({path:out+'/'+view+'-'+name+'.png',fullPage:true,timeout:10000});}catch(_){}
  result.pages.push(rec);
  console.log('FXV2_PAGE '+JSON.stringify({name,view,http:rec.http,nav:rec.menu,primary:rec.primary,overflow:rec.overflow,
     feed:rec.feed?.slice(0,60),exceptions:exceptions.length,failed:network.length,error:rec.error}));
  await ctx.close();
 }
}
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try{for(const [view,viewport] of viewports)for(const [name,file,selector] of pages)
  await audit(browser,name,file,selector,view,viewport);}
 finally{await browser.close();}
 result.completed_utc=new Date().toISOString();
 result.status=result.findings.length?'FAIL':'PASS';
 fs.writeFileSync(out+'/'+mode+'.json',JSON.stringify(result,null,2)+'\n');
 console.log('FXV2_QA_RESULT '+JSON.stringify({status:result.status,pages:result.pages.length,findings:result.findings.length,first:result.findings.slice(0,25)}));
 if(result.findings.length)process.exitCode=1;
})().catch(e=>{console.error('FXV2_QA_FATAL',e);process.exitCode=2;});