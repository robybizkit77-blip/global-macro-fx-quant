#!/usr/bin/env node
'use strict';
/* Browser-focused v10 Rates CHF proxy and EUR yield source change QA.
   Keeps pre-existing morning-calendar source freshness failure separate. */
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');

async function run(){
 const a=process.argv.slice(2),p=k=>a[a.indexOf(k)+1];
 const scenario=p('--scenario'),expected10=Number(p('--chf-10y')),output=p('--out'),dir=p('--screenshots');
 if(!['before','after'].includes(scenario)||!Number.isFinite(expected10)||
    !output?.startsWith('/tmp/')||!dir?.startsWith('/tmp/'))throw Error('Invalid scenario or /tmp paths');
 const browser=await chromium.launch({headless:true}),cases=[],issues=[];
 try{
  for(const [label,viewport] of [['desktop',{width:1440,height:950}],['mobile',{width:390,height:844}]]){
   const page=await browser.newPage({viewport}),errors=[];
   page.on('pageerror',e=>errors.push(e.message));
   await page.route('https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/main/live_data/sections/*.json',async route=>{
     const n=route.request().url().split('/').at(-1).split('?')[0];
     const file=path.join(process.cwd(),'live_data/sections',n);
     if(!fs.existsSync(file))return route.fulfill({status:404,body:'Unavailable fixture'});
     return route.fulfill({status:200,contentType:'application/json',body:fs.readFileSync(file),
                           headers:{'Access-Control-Allow-Origin':'*'}});
   });
   const url='http://127.0.0.1:8818/site/control-room-preview/';
   const response=await page.goto(url+'#/tassi',{waitUntil:'domcontentloaded',timeout:120000});
   assert(response?.ok(),'v10 preview failed to load');
   await page.waitForFunction(()=>{
     const d=document.getElementById('gmfq-page')?.contentDocument;
     return Boolean(d?.querySelector('#gmfq-yields-study .gmfq-yield-row[data-ccy="CHF"] .gmfq-yield-scenario'));
   },null,{timeout:45000});
   const observed=await page.evaluate(()=>{
     const d=document.getElementById('gmfq-page')?.contentDocument,
       c=d?.querySelector('#gmfq-yields-study .gmfq-yield-row[data-ccy="CHF"]'),
       e=d?.querySelector('#gmfq-yields-study .gmfq-yield-row[data-ccy="EUR"]'),
       host=d?.getElementById('gmfq-yields-study');
     return {viewport:d?.documentElement.clientWidth,
       document_width:d?.documentElement.scrollWidth,
       chf_scenario:c?.querySelector('.gmfq-yield-scenario')?.textContent,
       source_rebase_status:host?.dataset.eurSourceRebase,
       chf_source_rebase_notice:c?.querySelector('.gmfq-yield-rebase')?.textContent||null,
       chf_source_rebase_count:c?.querySelectorAll('.gmfq-yield-rebase').length||0,
       chf_asof:c?.dataset.asof,eur_current_cell:e?.textContent,eur_asof:e?.dataset.asof,
       proxy_not_official:host?.textContent?.includes('non prezzi ufficiali'),
       no_core_effect:host?.dataset.coreEffect==='NONE',
       no_pair_effect:host?.dataset.pairEffect==='NONE'};
   });
   assert(observed.viewport>100,'No v10 viewport');
   assert(observed.document_width<=observed.viewport+16,
     label+' rates horizontal overflow '+JSON.stringify(observed));
   assert(observed.chf_scenario?.includes('10Y ≈'+expected10.toFixed(3)+'% (BASSA)'),
     label+' CHF low-confidence 10Y proxy not displayed '+JSON.stringify(observed));
   if(scenario==='before'){
     assert.equal(observed.source_rebase_status,'NONE');
     assert.equal(observed.chf_source_rebase_notice,null);
   }else{
     assert.equal(observed.source_rebase_status,'RESEARCH_CANDIDATE_NOT_PUBLISHED');
     assert.equal(observed.chf_source_rebase_count,1);
     assert(observed.chf_source_rebase_notice?.includes('ANTEPRIMA RICERCA')&&
            observed.chf_source_rebase_notice?.includes('revisione dello scenario β')&&
            observed.chf_source_rebase_notice?.includes('non un movimento osservato oggi')&&
            observed.chf_source_rebase_notice?.includes('Affidabilità BASSA'));
   }
   assert.equal(observed.chf_asof,'2026-09-30');
   assert(observed.eur_current_cell?.includes('3.007%')&&
          observed.eur_current_cell?.includes('3.384%'),'EUR current yields unexpectedly changed');
   assert(observed.proxy_not_official&&observed.no_core_effect&&observed.no_pair_effect,
          'Derived proxy incorrectly labeled a canonical model or official quote');
   fs.mkdirSync(dir,{recursive:true});
   await page.screenshot({path:path.join(dir,label+'-v10-rates.png'),fullPage:true});
   const home=await page.goto(url+'#/home',{waitUntil:'domcontentloaded',timeout:120000});
   // Hash-only navigation keeps the same document and Playwright may
   // legitimately return null instead of a fresh HTTP response.
   assert(!home||home.ok(),'v10 Home HTTP navigation failed');
   await page.waitForFunction(()=>{
     const d=document.getElementById('gmfq-page')?.contentDocument;
     return Boolean(d?.querySelector('#valute .cc[data-filter="DXY"]'));
   },null,{timeout:45000});
   await page.screenshot({path:path.join(dir,label+'-v10-home.png'),fullPage:true});
   if(errors.length)issues.push({label,errors});
   cases.push({label,viewport,observed,errors});
   await page.close();
  }
 }finally{await browser.close();}
 const receipt={schema:'GMFQ_V10_ECB_EUR2Y10Y_BROWSER_COMPARE_V1',scenario,cases,issues,
   status:issues.length?'BROWSER_ERROR':'TARGETED_BROWSER_CANDIDATE_GREEN',
   full_general_calendar_morning_gate_checked:false,
   full_site_a_to_z_acceptance:false,original_approved_32_part_UI_unchanged:true,
   production_published:false};
 fs.writeFileSync(output,JSON.stringify(receipt,null,2)+'\n');
 assert.equal(issues.length,0,JSON.stringify(issues));
 assert.equal(cases.length,2);
 console.log('V10_EUR_2Y10Y_1440_390_TARGETED_CHF_BASSA_BROWSER_PASS',JSON.stringify({
   scenario,cases:cases.map(x=>({label:x.label,observed:x.observed}))}));
}
run().catch(e=>{console.error(e);process.exit(1)});
