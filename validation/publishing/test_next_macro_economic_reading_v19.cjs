'use strict';
/* V19: source-aware, descriptive macro semantics on real G8 source catalog.
 * This test never writes to the FX Core or upgrades revised history to PIT.
 */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const next=path.join(root,'site/fx-quant-v2/next');
const code=fs.readFileSync(path.join(next,'macro-studio.js'),'utf8');
const context={window:{},module:{exports:{}}};
new vm.Script(code,{filename:'macro-studio.js'}).runInNewContext(context,{timeout:1500});
const explain=context.window.FXQuantMacro?.explainIndicator;
assert.equal(typeof explain,'function','V19 economics interpretation export');
const catalog=JSON.parse(fs.readFileSync(path.join(root,'live_data/sections/MACRO_SERIES.json'),'utf8'));
const categories=new Set();
let inspected=0;
for(const [country,series] of Object.entries(catalog)){
 assert(/^(USD|EUR|GBP|JPY|CHF|AUD|NZD|CAD)$/.test(country));
 for(const s of series){
  if(!Array.isArray(s.values)||s.values.length<2||!Array.isArray(s.dates)||
     s.dates.length!==s.values.length)continue;
  const n=s.values.length,v=s.values[n-1],pr=s.values[n-2];
  if(!Number.isFinite(v)||!Number.isFinite(pr))continue;
  const st={d1:v-pr,cur:{period:s.dates[n-1]},pr:{period:s.dates[n-2]}};
  const result=explain(s,st);
  assert(result.meaning.length>45, country+' '+s.id+' missing economic significance');
  assert(result.check.length>25, country+' '+s.id+' missing independent validation');
  assert(!/undefined|NaN|Infinity/.test(result.meaning+' '+result.check));
  if(s.category)categories.add(s.category);
  inspected++;
 }
}
assert(inspected>=50,'Use actual G8 source catalog, not synthetic ranking');
for(const c of ['Crescita','Inflazione','Lavoro','Housing','Credito','Liquidità','Rates'])
 assert(categories.has(c),'Missing macro category '+c);
const test=(category,label,unit,delta)=>explain({category,label,unit},
 {d1:delta,cur:{period:'2026-09'},pr:{period:'2026-08'}});
assert.match(test('Inflazione','CPI headline','Index 1982=100',2).meaning,/indice dei prezzi/);
assert.match(test('Inflazione','HICP headline','% YoY',-0.2).meaning,/tasso annuo/);
assert.match(test('Inflazione','RBNZ survey CPI 1Y','',0.2).meaning,/aspettative dichiarate/);
assert.match(test('Lavoro','Disoccupazione','%',0.3).meaning,/minori assunzioni/);
assert.match(test('Lavoro','Occupazione','persons',-500).meaning,/occupazione o domanda/);
assert.match(test('Credito','BLS standard credito imprese','Net percentage',3).meaning,/segno del sondaggio|verso economico/);
assert.match(test('Liquidità','M3','EUR millions',100).meaning,/non equivalgono a acquisti/);
assert.match(test('Rates','Rendimento 10Y','%',0.5).check,/term premium/);
const absent=explain({category:'Inflazione',label:'CPI'},
 {d1:null,cur:null,pr:null});
assert.match(absent.meaning,/Mancano osservazioni/);
const index=fs.readFileSync(path.join(next,'index.html'),'utf8');
assert(index.includes('macro-studio.js?v=4'),'Page must use the V19 Macro Studio asset');
assert(code.includes('Perché conta economicamente:')&&code.includes('Cosa controllare adesso:'),
 'Economic interpretation must be shown inside the existing Macro graphic reading');
console.log('NEXT_MACRO_ECONOMIC_V19_PASS: '+inspected+' dated G8 observations and '+categories.size+
 ' categories checked; CPI index/YoY/survey, unemployment/employment, credit and liquidity semantics verified.');
