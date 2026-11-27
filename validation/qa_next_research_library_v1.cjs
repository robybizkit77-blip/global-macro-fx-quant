'use strict';
/* Verified public HTML, latest per report category, OIS and safe auto-discovery. */
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const ROOT=path.resolve(__dirname,'..');
const read=p=>fs.readFileSync(path.join(ROOT,p),'utf8');
const index=read('site/fx-quant-v2/next/index.html');
const app=read('site/fx-quant-v2/next/app.js');
const src=read('site/fx-quant-v2/next/research-library.js');
const css=read('site/fx-quant-v2/next/research-library.css');
new vm.Script(app,{filename:'app.js'});
new vm.Script(src,{filename:'research-library.js'});
const L=require('../site/fx-quant-v2/next/research-library.js');
assert.match(index,/href="#library" data-route="library"/);
assert.match(index,/research-library\.css\?v=4/);
assert.match(index,/research-library\.js\?v=21/);
assert.match(index,/11 sezioni/);
assert.match(app,/library:'Research Library'/);
assert.match(app,/library:\(\)=>window\.FXQuantResearchLibrary/);
assert.match(app,/libraryFilter/);
assert.match(app,/e\.target\.id==='library-search'/);
assert.match(css,/max-width:700px/);
assert.equal(L.REPORTS.length,8);
assert.equal(new Set(L.REPORTS.map(x=>x.type)).size,8);
assert.equal(new Set(L.REPORTS.map(x=>x.file)).size,8);
assert.equal(L.CATEGORIES.length,9); // 'Tutti' plus eight canonical types
assert.ok(!L.REPORTS.some(x=>x.type==='monitor'),'Discontinued Trade Thesis Monitor must be absent');
assert.ok(!L.CATEGORIES.some(x=>x[0]==='monitor'),'Discontinued report filter must be absent');
assert.ok(L.REPORTS.some(x=>x.type==='ois'&&x.file.includes('V7_CONFRONTO_31OTT_06NOV')));
assert.equal(L.REPORTS.find(x=>x.type==='daily').date,'2026-11-16');
assert.equal(L.REPORTS.find(x=>x.type==='cross').date,'2026-10-17');
assert.equal(L.REPORTS.find(x=>x.type==='pairs').date,'2026-10-17');
assert.ok(L.REPORTS.find(x=>x.type==='pairs').publicUrl.startsWith('./reports/'));
const legacy=path.resolve(ROOT,'site/website-v1/reports');
const next=path.resolve(ROOT,'site/fx-quant-v2/next/reports');
for(const r of L.REPORTS){
 assert.match(r.date,/^2026-(10|11)-\d\d$/);
 assert.match(r.file,/\.html$/);
 const output=path.resolve(ROOT,'site/fx-quant-v2/next',L.url(r));
 const base=r.publicUrl||r.date>='2026-11-01'?next:legacy;
 assert.ok(output.startsWith(base+path.sep),'Report must resolve within real published source');
 assert.ok(fs.existsSync(output),'Broken HTML link: '+r.file);
 const html=fs.readFileSync(output,'utf8');
 assert.ok(html.length>1000&&/<html|<!doctype/i.test(html),'Invalid public HTML '+r.file);
 const original=path.join(legacy,r.file);
 if(fs.existsSync(original)){
  assert.equal(html,fs.readFileSync(original,'utf8'),'Original mirrored report must remain byte-identical');
 }else{
  assert.ok(output.startsWith(next+path.sep),
   'Next-only report must resolve to the verified published Next tree: '+r.file);
 }
}
assert.equal(L.filterReports().length,8);
assert.equal(L.filterReports('daily').length,1);
assert.equal(L.filterReports('cot').length,1);
assert.equal(L.filterReports('ois').length,1);
assert.equal(L.filterReports('monitor').length,0);
assert.equal(L.filterReports('all','banche').length,2);
assert.equal(L.filterReports('all','inesistente').length,0);
assert.equal(L.filterReports()[0].date,'2026-11-16');
assert.equal(L.reportDate('COT_FX_G8_03_NOV_2026_V10.html'),'2026-11-03');
const approvedReview='Global_Markets_Review_14_Novembre_2026_DARK_SLATE_V13_SOLO_SEZIONI.html';
const latestReview='Global_Markets_Review_21_Novembre_2026_DARK_SLATE_V13.html';
const recurringReview='Weekly_Global_Macro_Strength_Cross_Asset_2026-11-20_DARK_SLATE_V13.html';
const weeklyIndex=JSON.parse(read('site/fx-quant-v2/next/reports/weekly-latest.json'));
assert.deepEqual(weeklyIndex.files.filter(file=>L.reportType(file)==='cross'),[latestReview]);
assert.equal(L.reportType(approvedReview),'cross');
assert.equal(L.reportDate(approvedReview),'2026-11-14');
assert.equal(L.reportType(latestReview),'cross');
assert.equal(L.reportDate(latestReview),'2026-11-21');
assert.equal(L.remoteReport(latestReview).title,'Global Markets Review');
assert.equal(L.reportDate('Global_Markets_Review_31_Novembre_2026_DARK_SLATE_V13.html'),null);
assert.equal(L.remoteReport('Global_Markets_Review_21_Novembre_2026_DARK_SLATE_V13_PROVA.html'),null);
assert.equal(L.reportDate(recurringReview),'2026-11-20');
assert.equal(L.remoteReport(recurringReview).title,'Global Markets Review');
assert.equal(L.remoteReport(recurringReview.replace('.html','_BOZZA.html')),null);
assert.equal(L.reportType('Global_Markets_Review_14_Novembre_2026_DARK_SLATE_V12_APERTURE_ALLINEATE.html'),null);
assert.ok(read('site/fx-quant-v2/next/reports/'+approvedReview).includes('settimana chiusa venerdì 13 novembre 2026'));
assert.ok(read('site/fx-quant-v2/next/reports/'+latestReview).includes('settimana chiusa venerdì 20 novembre 2026'));
assert.equal(L.reportDate('Weekly_CB_Pricing_G8_2026-11-06_V7.html'),'2026-11-06');
assert.equal(L.reportType('Weekly_CB_Pricing_G8_2026-11-06_V7.html'),'ois');
assert.equal(L.reportType('Weekly_Central_Bank_Pricing_G8_2026-11-07_DARK_DESK_DATI_PARZIALI.html'),'ois',
 'The actual scheduled weekly report producer must resolve to OIS category');
assert.equal(L.reportDate('Weekly_Central_Bank_Pricing_G8_2026-11-07_DARK_DESK_DATI_PARZIALI.html'),'2026-11-07');
const aliasApproved='Weekly_Central_Bank_Pricing_G8_2026-11-07_V8_DEFINITIVO.html';
const aliasCandidate=L.remoteReport(aliasApproved);
assert(aliasCandidate&&aliasCandidate.type==='ois','A dated, explicitly approved alias must be discoverable');
assert.equal(aliasCandidate.date,'2026-11-07');
assert.equal(L.remoteReport('Weekly_Central_Bank_Pricing_G8_2026-11-07_V8_PROVA.html'),null,
 'A draft alias must stay excluded');
assert.equal(L.remoteReport('Weekly_Central_Bank_Pricing_G8_2026-11-07_V8_BACKUP.html'),null);
assert.equal(L.reportType('Weekly_Central_Bank_Unknown_G8_2026-11-07_V8_DEFINITIVO.html'),null,
 'The public scanner must remain limited to existing eight report types');

assert.equal(L.remoteReport('Weekly_CB_Pricing_G8_2026-11-06_V8_PROVA.html'),null);
assert.equal(L.remoteReport('Weekly_Central_Bank_Pricing_G8_2026-11-12_V8_DATI_PARZIALI.html'),null,
 'Partially verified OIS reports are not automatically approved by a newer filename');
assert.equal(L.remoteReport('Trade_Thesis_Monitor_2026-11-11_DARK.html'),null);
assert.equal(L.latestPerType([...L.REPORTS,{...L.REPORTS[0],file:'Briefing_Forex_Commodities_2026-11-16_V4_DEFINITIVO.html'}]).length,8);
assert.equal(L.latestPerType([...L.REPORTS,{...L.REPORTS[0],file:'Briefing_Forex_Commodities_2026-11-16_V4_DEFINITIVO.html'}])[0].file,
 'Briefing_Forex_Commodities_2026-11-16_V4_DEFINITIVO.html','Higher approved revision wins on identical dates');
assert.equal(L.latestPerType([...L.REPORTS,{...L.REPORTS[0],file:'Briefing_Forex_Commodities_2026-11-16_V4.html'}])[0].file,
 'Briefing_Forex_Commodities_2026-11-16_V4.html','V4 must supersede corrected V3 on identical dates');
// Publication freshness belongs to the REPORT cadence, never market prices.
// Weekly publication dates must not be confused with daily source freshness,
// and Tuesday COT observation must not be labelled as a Friday release.
const today='2026-11-13';
const daily=L.REPORTS.find(r=>r.type==='daily');
const cot=L.REPORTS.find(r=>r.type==='cot');
const ois=L.REPORTS.find(r=>r.type==='ois');
const cross=L.REPORTS.find(r=>r.type==='cross');
const pairs=L.REPORTS.find(r=>r.type==='pairs');
assert.equal(L.editionStatus(daily,'2026-11-16').state,'today');
assert.match(L.editionStatus(daily,'2026-11-16').text,/seduta odierna/);
assert.equal(L.editionStatus({...daily,date:'2026-11-12'},'2026-11-13').state,'previous',
 'A previous daily report cannot masquerade as the next session report');
assert.equal(L.editionStatus({...daily,date:'2026-11-12'},'2026-11-14').state,'previous',
 'Weekend cannot hide a missing Friday daily edition');
assert.equal(L.editionStatus({...daily,date:'2026-11-13'},'2026-11-14').state,'latest-business');
assert.equal(L.editionStatus(ois,today).state,'weekly',
 'Six-day-old OIS weekly is last published, not automatically stale');
assert.equal(L.editionStatus(cross,today).state,'previous');
assert.equal(L.editionStatus(pairs,today).state,'previous');
assert.equal(L.editionStatus(cot,'2026-11-17').state,'weekly');
assert.ok(cot.desc.includes('pubblicate il 16 novembre'));
assert.equal(L.editionStatus({...cot,date:'2026-11-03'},'2026-11-17').state,'previous');
const otherCot=L.remoteReport('COT_FX_G8_03_NOV_2026_V10_DEFINITIVO.html');
assert.ok(otherCot&&!otherCot.desc.includes('pubblicate il 16 novembre'),
 'Only the pinned COT edition may describe its known release date');
assert.equal(L.editionStatus(cot,'2026-11-23').state,'previous');
assert.match(L.editionStatus(cot,today).text,/posizioni al 10\/11\/2026 \(martedì\)/);
assert.equal(L.editionStatus({...daily,date:'2026-11-20'},today).state,'unverified',
 'A future edition cannot be labelled as published today');
const fixedRows=L.rows(today);
assert.match(L.rows('2026-11-16'),/Briefing pubblicato per la seduta odierna/);
assert.match(fixedRows,/Edizione storica · non aggiornata questa settimana/);
assert.match(fixedRows,/Ultimo COT pubblicato · posizioni al 10\/11\/2026 \(martedì\)/);
const home=L.render();
assert.doesNotMatch(home,/rl-stats|REPORT CORRENTI VISIBILI/,
 'Library should use its opening for the featured Briefing');
assert.match(home,/<h1>Research Library<\/h1>/);
assert.match(home,/<div id="library-featured"><article class="rl-card rl-featured">/);
assert.match(home,/Apri Briefing <span aria-hidden="true">/);
assert.equal(home.split(daily.file).length-1,1,
 'The featured Briefing must be the only Daily link');
assert.equal((home.match(/<article class="rl-card">/g)||[]).length,7);

L.setCategory('ois');
assert.equal(L.filterReports().length,1);
assert.match(L.render(),/<div id="library-featured" hidden>/);
assert.equal((L.render().match(/<article class="rl-card">/g)||[]).length,1);
L.setQuery('GBP');
assert.equal(L.filterReports().length,0);
assert.match(L.rows(),/Nessun report/);
L.setQuery('');L.setCategory('daily');
assert.match(L.render(),/aria-labelledby="library-weekly-title" hidden/);
L.setCategory('all');
assert.match(L.render(),/Curve OIS/);
assert.match(L.render(),/Una nuova edizione compare solo se è stata realmente pubblicata/);
assert.match(L.render(),/id="library-grid"/);
assert.match(L.render(),/id="library-search"/);
assert.match(L.render(),/data-library-type="ois"/);
(async()=>{
 const initialFetch=globalThis.fetch;
 try{
  const remoteName='Briefing_Forex_Commodities_2026-11-16_V4_DEFINITIVO.html';
  globalThis.fetch=async(url,opts)=>{
   if(String(url).includes('api.github.com'))return {ok:true,json:async()=>[
    {name:remoteName,type:'file'},
    {name:'Trade_Thesis_Monitor_2026-11-11_DARK.html',type:'file'},
    {name:'Weekly_CB_Pricing_G8_2026-11-06_V8_PROVA.html',type:'file'}
   ]};
   if(String(url).includes(remoteName)&&opts.method==='HEAD')return {ok:true};
   throw Error('Unexpected endpoint '+url);
  };
  await L.refresh();
  assert.equal(L.filterReports('daily')[0].file,remoteName);
  assert.equal(L.filterReports().length,8);
  assert.equal(L.filterReports('monitor').length,0);
  const localName='Briefing_Forex_Commodities_2026-11-16_V5_DEFINITIVO.html';
  const weeklyName='Weekly_CB_Pricing_G8_2026-11-13_DARK_DESK_V12_PRICING_G8_SPIEGATO.html';
  globalThis.fetch=async(url,opts)=>{
   if(url==='./reports/daily-latest.json')return {ok:true,json:async()=>({file:localName})};
   if(url==='./reports/weekly-latest.json')return {ok:true,json:async()=>({files:[weeklyName,localName,approvedReview]})};
   if([localName,weeklyName,approvedReview].some(file=>url==='./reports/'+file)&&opts.method==='HEAD')return {ok:true};
   return {ok:false,status:429};
  };
  await L.refresh();
  assert.equal(L.filterReports('daily')[0].file,localName,'Same-site briefing works without the GitHub API');
  assert(L.render().split('id="library-filterbar"')[0].includes(localName),
   'The featured Daily uses the verified same-site edition');
  assert.equal(L.filterReports('ois')[0].file,weeklyName,'Same-site weekly catalog works without the GitHub API');
  assert.deepEqual(L.filterReports('cross').map(r=>[r.title,r.date,L.url(r)]),[
   ['Global Markets Review','2026-11-14','./reports/'+approvedReview]
  ]);
  assert.equal(L.filterReports().length,8);
  globalThis.fetch=async(url,opts)=>{
   if(url==='./reports/weekly-latest.json')return {ok:true,json:async()=>({files:[recurringReview]})};
   if(url==='./reports/'+recurringReview&&opts.method==='HEAD')return {ok:true};
   return {ok:false,status:404};
  };
  await L.refresh();
  assert.deepEqual(L.filterReports('cross').map(r=>[r.title,r.date,L.url(r)]),[
   ['Global Markets Review','2026-11-20','./reports/'+recurringReview]
  ]);
  const missingName='Briefing_Forex_Commodities_2026-11-16_V6_DEFINITIVO.html';
  globalThis.fetch=async(url)=>url==='./reports/daily-latest.json'
   ?{ok:true,json:async()=>({file:missingName})}:{ok:false,status:404};
  await L.refresh();
  assert.equal(L.filterReports('daily')[0].file,localName,'Skip an unpublished briefing');
  globalThis.fetch=async()=>({ok:false,status:429});
  await L.refresh();
  assert.equal(L.filterReports('daily')[0].file,localName,'Fallback must retain last verified edition');
  const offline={fetch:globalThis.fetch,AbortSignal,document:{getElementById:()=>null}};
  vm.runInNewContext(src,{window:offline});
  const offlineLibrary=offline.FXQuantResearchLibrary;
  assert.doesNotMatch(offlineLibrary.render(),/Apri Briefing/,'No archive should flash during loading');
  await offlineLibrary.refresh();
  assert.match(offlineLibrary.render(),/Briefing d’archivio/,'Archive should be identified if indexes fail');
  assert.match(offlineLibrary.render(),/Indice del Briefing non verificato/);
  console.log('NEXT_LIBRARY_LATEST_8_OIS_NO_MONITOR_AUTO_PUBLISHED_DISCOVERY_PASS');
 }finally{globalThis.fetch=initialFetch;}
})().catch(e=>{console.error(e);process.exitCode=1});
