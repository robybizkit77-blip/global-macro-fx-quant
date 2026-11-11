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
assert.match(index,/research-library\.js\?v=1/);
assert.match(index,/9 sezioni/);
assert.match(app,/library:'Research Library'/);
assert.match(app,/library:\(\)=>window\.FXQuantResearchLibrary/);
assert.match(app,/libraryFilter/);
assert.match(app,/e\.target\.id==='library-search'/);
assert.ok(css.includes('max-width:700px'),'Missing mobile design');
assert.equal(L.REPORTS.length,9);
assert.equal(new Set(L.REPORTS.map(x=>x.file)).size,L.REPORTS.length);
assert.equal(L.REPORTS.some(x=>x.date==='2026-11-06'),false,
 'Do not claim that private recent reports are publicly published');
const base=path.resolve(ROOT,'site/website-v1/reports');
for(const r of L.REPORTS){
 assert.match(r.date,/^2026-10-\d{2}$/);
 assert.match(r.file,/\.html$/);
 const resolved=path.resolve(ROOT,'site/fx-quant-v2/next',L.url(r));
 assert.ok(resolved.startsWith(base+path.sep),'Library must link to actual report folder');
 assert.ok(fs.existsSync(resolved),'Broken published report URL: '+r.file);
 const doc=fs.readFileSync(resolved,'utf8');
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
assert.equal(L.REPORTS.find(x=>x.type==='cot').date,'2026-10-06',
 'COT report date must be its actual file edition, not the date of the old index');
assert.equal(L.filterReports().length,9);
assert.equal(L.filterReports('monitor').length,3);
assert.equal(L.filterReports('cot').length,1);
assert.equal(L.filterReports('all','banche').length,2);
assert.equal(L.filterReports('all','nessun-report-immaginario').length,0);
assert.equal(L.filterReports()[0].date,'2026-10-15');
L.setCategory('cot');assert.equal(L.filterReports().length,1);
L.setQuery('GBP');assert.equal(L.filterReports().length,0);
assert.match(L.rows(),/Nessun report/);
L.setCategory('all');L.setQuery('');assert.equal(L.filterReports().length,9);
assert.match(L.render(),/Archivio storico, non quadro di mercato attuale/);
assert.match(L.render(),/Library privata/);
assert.match(L.render(),/id="library-grid"/);
assert.match(L.render(),/id="library-search"/);
assert.match(L.render(),/data-library-type="cot"/);
console.log('NEXT_RESEARCH_LIBRARY_9_REAL_PUBLIC_REPORTS_DATED_LINKED_FILTERED_MOBILE_SAFE');
