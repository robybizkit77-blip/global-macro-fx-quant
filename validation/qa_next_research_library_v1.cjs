'use strict';
/* Static + functional contract, no network or external browser dependencies. */
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const ROOT=path.resolve(__dirname,'..');
const read=p=>fs.readFileSync(path.join(ROOT,p),'utf8');
const index=read('site/fx-quant-v2/next/index.html');
const app=read('site/fx-quant-v2/next/app.js');
const librarySource=read('site/fx-quant-v2/next/research-library.js');
const css=read('site/fx-quant-v2/next/research-library.css');
new vm.Script(app,{filename:'app.js'});
new vm.Script(librarySource,{filename:'research-library.js'});
const L=require('../site/fx-quant-v2/next/research-library.js');
assert.match(index,/href="#library" data-route="library"/);
assert.match(index,/research-library\.css\?v=1/);
assert.match(index,/research-library\.js\?v=3/);
assert.match(index,/9 sezioni/);
assert.match(app,/library:'Research Library'/);
assert.match(app,/library:\(\)=>window\.FXQuantResearchLibrary/);
assert.match(app,/libraryFilter/);
assert.match(app,/e\.target\.id==='library-search'/);
assert.ok(css.includes('max-width:700px'),'Missing mobile design');
assert.equal(L.REPORTS.length,15);
assert.equal(new Set(L.REPORTS.map(x=>x.file)).size,L.REPORTS.length);
assert.equal(L.filterReports('daily').length,2);
assert.ok(L.REPORTS.some(x=>x.date==='2026-11-11' && x.type==='daily'));
assert.equal(L.REPORTS.some(x=>x.type==='monitor' && x.date>'2026-10-15'),false,
 'Old Trade Thesis Monitor must not be presented as newly updated');
const base=path.resolve(ROOT,'site/website-v1/reports');
const nextBase=path.resolve(ROOT,'site/fx-quant-v2/next/reports');
for(const r of L.REPORTS){
 assert.match(r.date,/^2026-(10|11)-\d{2}$/);
 assert.match(r.file,/\.html$/);
 const resolved=path.resolve(ROOT,'site/fx-quant-v2/next',L.url(r));
 const expectedBase=r.date>='2026-11-01'?nextBase:base;
 assert.ok(resolved.startsWith(expectedBase+path.sep),'Library must link inside its actual published folder');
 assert.ok(fs.existsSync(resolved),'Broken published report URL: '+r.file);
 const doc=fs.readFileSync(resolved,'utf8');
 if(r.date>='2026-11-01'){
  const original=fs.readFileSync(path.join(base,r.file),'utf8');
  assert.equal(doc,original,'Public V2 report must reproduce original edition byte-for-byte');
 }
 assert.ok(doc.length>1000,'Incomplete published file '+r.file);
 assert.ok(/<!doctype html>|<html lang=/i.test(doc),'Not HTML '+r.file);
 if(doc.includes('weekly-global-macro-2026-10-10.part1.txt')){
  for(const file of ['weekly-global-macro-2026-10-10.part1.txt','weekly-global-macro-2026-10-10.part2.txt',
   'weekly-global-macro-2026-10-10.part3.txt','weekly-global-macro-2026-10-10.part4.txt',
   'weekly-global-macro-2026-10-10.part5a.txt','weekly-global-macro-2026-10-10.part5b.txt',
   'weekly-global-macro-2026-10-10.part5c.txt','weekly-global-macro-2026-10-10.part5d.txt',
   'weekly-global-macro-2026-10-10.part6a.txt']){
   assert.ok(fs.existsSync(path.join(base,file)),'Missing multipart HTML '+file);
  }
 }
}
assert.deepEqual(L.REPORTS.filter(x=>x.type==='cot').map(x=>x.date).sort(),['2026-10-06','2026-11-03'],
 'COT report dates must reflect the source reference Tuesday');
assert.equal(L.filterReports().length,15);
assert.equal(L.filterReports('monitor').length,3);
assert.equal(L.filterReports('cot').length,2);
assert.equal(L.filterReports('all','banche').length,4);
assert.equal(L.filterReports('all','nessun-report-immaginario').length,0);
assert.equal(L.filterReports()[0].date,'2026-11-11');
L.setCategory('cot');assert.equal(L.filterReports().length,2);
L.setQuery('GBP');assert.equal(L.filterReports().length,0);
assert.match(L.rows(),/Nessun report/);
L.setCategory('all');L.setQuery('');assert.equal(L.filterReports().length,15);
assert.match(L.render(),/Edizioni datate, non feed intraday/);
assert.match(L.render(),/sincronizzazione automatica/);
assert.match(L.render(),/id="library-grid"/);
assert.match(L.render(),/id="library-search"/);
assert.match(L.render(),/data-library-type="cot"/);
console.log('NEXT_RESEARCH_LIBRARY_15_PUBLIC_REPORTS_DAILY_WEEKLY_MONITOR_HISTORICAL_LINKED_SAFE');
