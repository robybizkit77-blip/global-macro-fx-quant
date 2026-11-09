'use strict';
/* Regression on the real published Macro Studio renderer, without a browser
 * or network. Test exact BEA/FRED current-vintage narrative and all G8 guards.
 */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');

const ROOT=path.resolve(__dirname,'../..');
const js=fs.readFileSync(path.join(ROOT,'site/fx-quant-v2/next/macro-studio.js'),'utf8');
const source=JSON.parse(fs.readFileSync(path.join(ROOT,'live_data/sections/MACRO_SERIES.json'),'utf8'));
const FX=['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'];
const FLAGS=Object.fromEntries(FX.map(c=>[c,c]));
const NAMES=Object.fromEntries(FX.map(c=>[c,c]));
const sandbox={window:{}};
vm.runInNewContext(js,sandbox,{filename:'macro-studio.js'});
assert.equal(typeof sandbox.window.FXQuantMacro.render,'function');

function html(opts={}){
  const data=opts.data||source,ccy=opts.country||'USD';
  const state={
    ccy,msCategory:'Crescita',msSeriesId:null,msView:'level',msWindow:24,
    msHeat:'inflation',msHeatSort:'ccy',msHeatAsc:true,msOther:'EUR',
    msCompareMetric:'inflation',msAdvanced:false
  };
  const api={
    get:k=>({macroSeries:data,macro:{currencies:{}},rates:{}})[k]||null,
    FX,FLAGS,NAMES,state,
    plot:()=>'<div class="fake-chart"></div>',
    pageHero:()=>'<header>Macro</header>',
    esc:x=>String(x??'').replace(/&/g,'&amp;').replace(/</g,'&lt;'),
    fmt:(v,d=2)=>typeof v==='number'&&Number.isFinite(v)?
      v.toLocaleString('it-IT',{minimumFractionDigits:d,maximumFractionDigits:d}):'—',
    sign:(v,d=1,suffix='')=>typeof v==='number'&&Number.isFinite(v)?
      (v>0?'+':v<0?'−':'')+Math.abs(v).toLocaleString('it-IT',{
        minimumFractionDigits:d,maximumFractionDigits:d})+suffix:'—',
    date:x=>x,finite:x=>typeof x==='number'&&Number.isFinite(x),
    validDay:x=>/^\d{4}-\d{2}-\d{2}$/.test(x),
    dayNow:()=>opts.today||'2026-11-09'
  };
  const full=sandbox.window.FXQuantMacro.render(api);
  const match=full.match(/<section class="macro-country-hero[^"]*"[\s\S]*?<\/section>/);
  assert.ok(match,'expected same existing hero markup');
  return {full,hero:match[0]};
}
function clone(){return JSON.parse(JSON.stringify(source));}
function byid(d,id){return d.USD.find(s=>s.id===id);}
function septemberFixture(){
 const d=clone();
 for(const [id,fid,values] of [
   ['US_PCEC96_history_value','PCEC96',[16882.2,16975,16977.6]],
   ['US_DSPIC96_history_DSPIC96','DSPIC96',[18414.1,18416.2,18366.1]]
 ]){
   const s=byid(d,id);
   assert.ok(s,'expected canonical series '+id);
   s.dates=['2026-07-01','2026-08-01','2026-09-01'];
   s.values=values;
   s.last_date=s.dates.at(-1);
   s.last_value=values.at(-1);
   s.frequency='M';
   s.unit='Billions of Chained 2017 Dollars SAAR';
   s.current_vintage_provenance={
     ...s.current_vintage_provenance,
     status:'BEA_REVISED_HISTORY_VIA_FRED_CURRENT_NOT_PIT',
     source_series_id:fid,issuer:'US_BEA',
     issuer_release_reference_month:'2026-09',
     source_series_first_release_PIT_certified:false
   };
 }
 return d;
}
function check(label,fn){try{fn();process.stdout.write('PASS '+label+'\n');}catch(e){console.error('FAIL '+label);throw e;}}

check('USD hero consumes both September revised real series, not just labour and CPI',()=>{
 const {hero}=html({data:septemberFixture()});
 assert.match(hero,/I consumi reali frenano, il reddito arretra/);
 assert.match(hero,/settembre 2026/);
 assert.match(hero,/consumi reali variano 0,0% sul mese/);
 assert.match(hero,/contro \+0,5% nel mese precedente/);
 assert.match(hero,/reddito disponibile reale varia −0,3%/);
 assert.match(hero,/storici revisionati, non prime pubblicazioni point-in-time/);
 assert.match(hero,/Non dimostrano da soli variazioni nelle attese Fed/);
 assert.match(hero,/servizi/);
 assert.match(hero,/macro-country-narrative/);
});
check('The source values, provenance and last date match main canonical data',()=>{
 for(const [id,fid,value] of [
  ['US_PCEC96_history_value','PCEC96',16977.6],
  ['US_DSPIC96_history_DSPIC96','DSPIC96',18366.1]
 ]){
  const s=byid(source,id),meta=s.current_vintage_provenance;
  assert.equal(s.last_date,s.dates.at(-1));
  assert.equal(s.last_value,s.values.at(-1));
  if(s.last_date==='2026-09-01')assert.equal(s.last_value,value);
  assert.equal(s.frequency,'M');
  assert.equal(s.unit,'Billions of Chained 2017 Dollars SAAR');
  assert.equal(meta.source_series_id,fid);
  assert.equal(meta.issuer,'US_BEA');
  assert.equal(meta.issuer_release_reference_month,s.last_date.slice(0,7));
  assert.equal(meta.source_series_first_release_PIT_certified,false);
 }
});
check('Non-USD hero does not inherit US demand story or change its macro verdict',()=>{
 for(const ccy of FX.filter(x=>x!=='USD')){
  const {hero}=html({country:ccy,data:septemberFixture()});
  assert.doesNotMatch(hero,/reddito disponibile reale varia|US_PCEC96|settembre 2026 i consumi/);
  assert.match(hero,/I dati non indicano ancora una direzione unica/);
 }
});
check('Missing verified vintage leaves legacy inflation-labour hero intact',()=>{
 const d=septemberFixture();
 delete byid(d,'US_PCEC96_history_value').current_vintage_provenance;
 const {hero}=html({data:d});
 assert.doesNotMatch(hero,/I consumi reali frenano/);
 assert.match(hero,/I dati non indicano ancora una direzione unica/);
});
check('Unsynchronized dates, issuer periods or PIT mislabel refuse demand story',()=>{
 for(const kind of ['mismatch-date','wrong-issuer-month','pit']){
  const d=septemberFixture(),v=byid(d,'US_DSPIC96_history_DSPIC96');
  if(kind==='mismatch-date')v.last_date='2026-08-01';
  if(kind==='wrong-issuer-month')v.current_vintage_provenance.issuer_release_reference_month='2026-08';
  if(kind==='pit')v.current_vintage_provenance.source_series_first_release_PIT_certified=true;
  const {hero}=html({data:d});
  assert.doesNotMatch(hero,/I consumi reali frenano/,kind);
 }
});
check('Old data is not described as an up-to-date economic turning point',()=>{
 const {hero}=html({today:'2027-03-01'});
 assert.doesNotMatch(hero,/I consumi reali frenano/);
});
check('Future matched observations recalculate dynamically without hardcoded September',()=>{
 const d=septemberFixture();
 for(const [id,next] of [['US_PCEC96_history_value',17010],
                          ['US_DSPIC96_history_DSPIC96',18400]]){
   const row=byid(d,id);
   row.dates[row.dates.length-1]='2026-10-01';
   row.values[row.values.length-1]=next;
   row.last_date='2026-10-01';
   row.last_value=next;
   row.current_vintage_provenance.issuer_release_reference_month='2026-10';
 }
 const {hero}=html({data:d});
 assert.match(hero,/ottobre 2026/);
 assert.doesNotMatch(hero,/A settembre 2026/);
 assert.match(hero,/Consumi e reddito reali: cosa sta cambiando/);
});
process.stdout.write('MACRO_US_REAL_HOUSEHOLDS_HERO_REGRESSION_PASS\n');
