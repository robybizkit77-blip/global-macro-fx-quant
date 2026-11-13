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
assert.match(index,/research-library\.css\?v=1/);
assert.match(index,/research-library\.js\?v=10/);
assert.match(index,/9 sezioni/);
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
assert.equal(L.REPORTS.find(x=>x.type==='daily').date,'2026-11-13');
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
assert.equal(L.filterReports()[0].date,'2026-11-13');
assert.equal(L.reportDate('COT_FX_G8_03_NOV_2026_V10.html'),'2026-11-03');
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
assert.equal(L.latestPerType([...L.REPORTS,{...L.REPORTS[0],file:'Briefing_Forex_Commodities_2026-11-13_V4_DEFINITIVO.html'}]).length,8);
assert.equal(L.latestPerType([...L.REPORTS,{...L.REPORTS[0],file:'Briefing_Forex_Commodities_2026-11-13_V4_DEFINITIVO.html'}])[0].file,
 'Briefing_Forex_Commodities_2026-11-13_V4_DEFINITIVO.html','Higher approved revision wins on identical dates');
assert.equal(L.latestPerType([...L.REPORTS,{...L.REPORTS[0],file:'Briefing_Forex_Commodities_2026-11-13_V4.html'}])[0].file,
 'Briefing_Forex_Commodities_2026-11-13_V4.html','V4 must supersede corrected V3 on identical dates');
// Publication freshness belongs to the REPORT cadence, never market prices.
// Weekly publication dates must not be confused with daily source freshness,
// and Tuesday COT observation must not be labelled as a Friday release.
const today='2026-11-13';
const daily=L.REPORTS.find(r=>r.type==='daily');
const cot=L.REPORTS.find(r=>r.type==='cot');
const ois=L.REPORTS.find(r=>r.type==='ois');
const cross=L.REPORTS.find(r=>r.type==='cross');
const pairs=L.REPORTS.find(r=>r.type==='pairs');
assert.equal(L.editionStatus(daily,today).state,'today');
assert.match(L.editionStatus(daily,today).text,/seduta odierna/);
assert.equal(L.editionStatus({...daily,date:'2026-11-12'},'2026-11-13').state,'previous',
 'A previous daily report cannot masquerade as the next session report');
assert.equal(L.editionStatus({...daily,date:'2026-11-12'},'2026-11-14').state,'previous',
 'Weekend cannot hide a missing Friday daily edition');
assert.equal(L.editionStatus({...daily,date:'2026-11-13'},'2026-11-14').state,'latest-business');
assert.equal(L.editionStatus(ois,today).state,'weekly',
 'Six-day-old OIS weekly is last published, not automatically stale');
assert.equal(L.editionStatus(cross,today).state,'previous');
assert.equal(L.editionStatus(pairs,today).state,'previous');
assert.equal(L.editionStatus(cot,today).state,'weekly',
 'Tuesday 03 Nov observation is still last published on Thu 12 Nov');
assert.match(L.editionStatus(cot,today).text,/posizioni al 03\/11\/2026 \(martedì\)/);
assert.equal(L.editionStatus(cot,'2026-11-16').state,'previous');
assert.equal(L.editionStatus({...daily,date:'2026-11-20'},today).state,'unverified',
 'A future edition cannot be labelled as published today');
const fixedRows=L.rows(today);
assert.match(fixedRows,/Briefing pubblicato per la seduta odierna/);
assert.match(fixedRows,/Edizione storica · non aggiornata questa settimana/);
assert.match(fixedRows,/Ultimo COT pubblicato · posizioni al 03\/11\/2026 \(martedì\)/);
assert.doesNotMatch(L.render(),/REPORT CORRENTI VISIBILI/,
 'The number of available categories is NOT the count of current editions');
assert.match(L.render(),/ULTIME EDIZIONI PUBBLICATE/);
assert.match(L.render(),/produzione e trasferimento dei report sono processi separati/);

L.setCategory('ois');
assert.equal(L.filterReports().length,1);
L.setQuery('GBP');
assert.equal(L.filterReports().length,0);
assert.match(L.rows(),/Nessun report/);
L.setCategory('all');L.setQuery('');
assert.match(L.render(),/Solo l’ultima edizione/);
assert.match(L.render(),/Curve OIS/);
assert.match(L.render(),/una nuova edizione compare solo se è stata realmente pubblicata/);
assert.match(L.render(),/id="library-grid"/);
assert.match(L.render(),/id="library-search"/);
assert.match(L.render(),/data-library-type="ois"/);
(async()=>{
 const initialFetch=globalThis.fetch;
 try{
  const remoteName='Briefing_Forex_Commodities_2026-11-13_V4_DEFINITIVO.html';
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
  globalThis.fetch=async()=>({ok:false,status:429});
  await L.refresh();
  assert.equal(L.filterReports('daily')[0].file,remoteName,'Fallback must retain last verified edition');
  console.log('NEXT_LIBRARY_LATEST_8_OIS_NO_MONITOR_AUTO_PUBLISHED_DISCOVERY_PASS');
 }finally{globalThis.fetch=initialFetch;}
})().catch(e=>{console.error(e);process.exitCode=1});
