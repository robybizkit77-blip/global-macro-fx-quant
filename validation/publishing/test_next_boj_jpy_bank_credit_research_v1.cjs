'use strict';
/* Exact BoJ MD11 JPY monthly credit stock; separate from FX Core and BoJ reserves. */
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'../..');
const source=require(path.join(root,'site/fx-quant-v2/next/jpy-boj-bank-credit-research-v1.js'));
const studio=require(path.join(root,'site/fx-quant-v2/next/liquidity-credit-studio.js'));
const native=JSON.parse(fs.readFileSync(path.join(root,'live_data/sections/NATIVE_LIQ_DATA.json'),'utf8'));
const index=fs.readFileSync(path.join(root,'site/fx-quant-v2/next/index.html'),'utf8');
assert.match(index,/jpy-boj-bank-credit-research-v1\.js\?v=\d+/);
assert.equal(source.schema,'GMFQ_NEXT_JPY_BOJ_BANK_CREDIT_RESEARCH_V1');
assert.equal(source.status,'VERIFIED_BOJ_MD11_MONTHLY_BANK_CREDIT_RESEARCH_ONLY');
assert.equal(source.publisher,'Bank of Japan');
assert.equal(source.database,'MD11');
assert.equal(source.series_id,'DLCLAEDBLTTO');
assert.equal(source.category,'bank_credit_end_period_stock');
assert.equal(source.unit,'100 milioni JPY');
assert.equal(source.frequency,'M');
assert.equal(source.end_of_period,true);
assert.equal(source.eligible_for_fx_core,false);
assert.equal(source.eligible_for_backtest,false);
assert.equal(source.first_release_pit_verified,false);
assert.equal(source.observation_is_not_publication_date,true);
assert.equal(source.original_canonical_last,'2026-07');
assert.equal(source.original_canonical_value,6764306);
assert(Number.isInteger(source.matched_canonical_months)&&source.matched_canonical_months>=12);
assert.equal(source.last_observation,source.dates.at(-1));
assert(source.dates.length>=12);
assert.equal(source.dates.length,source.values.length);
const ym=d=>Number(d.slice(0,4))*12+Number(d.slice(5));
for(let i=0;i<source.dates.length;i++){
 const d=source.dates[i],v=source.values[i];
 assert.match(d,/^\d{4}-(0[1-9]|1[0-2])$/);
 assert(Number.isFinite(v)&&v>2000000&&v<12000000);
 if(i>0){
  assert.equal(ym(d)-ym(source.dates[i-1]),1,'no month gaps or duplicates');
  assert(Math.abs(v/source.values[i-1]-1)<.12);
 }
}
const canonical=native.JPY.credit;
const anchor=canonical.dates.indexOf(source.original_canonical_last);
assert(anchor>=0);
assert.equal(canonical.values[anchor],source.original_canonical_value);
const overlap=source.dates.indexOf(source.original_canonical_last);
assert(overlap!==-1);
assert.equal(source.values[overlap],canonical.values[anchor]);
assert(canonical.last_date>=source.original_canonical_last);
assert(new Date(source.last_observation+'-01')<=new Date());
const FX=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
const fmt=(v,n=2)=>Number(v).toLocaleString('it-IT',{minimumFractionDigits:n,maximumFractionDigits:n});
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const api=ccy=>({
 get:k=>k==='liquidity'?native:null,FX,FLAGS:Object.fromEntries(FX.map(x=>[x,x])),
 NAMES:Object.fromEntries(FX.map(x=>[x,x])),state:{liqCcy:ccy},
 plot:()=>'<svg></svg>',pageHero:()=>'<h1>FX</h1>',
 esc,fmt,date:x=>x,dayNow:()=>new Date().toISOString().slice(0,10)
});
const jp=studio.render(api('JPY'));
assert.match(jp,/class="drivers-cad-official drivers-jpy-official"/);
assert.match(jp,/DLCLAEDBLTTO/);
assert.match(jp,/conti bancari, fiduciari e delle filiali estere/);
assert.match(jp,/Non sono nuovi prestiti/i);
assert.match(jp,/USD\/JPY/);
assert.match(jp,/JGB\/UST/);
assert.match(jp,/ranking FX invariato/);
assert(jp.includes(source.last_observation));
assert(jp.includes(fmt(source.values.at(-1)/10,2)+' miliardi JPY'),
 'Source units must convert 100 million yen to billions of yen exactly');
assert(jp.includes(fmt(source.values.at(-2)/10,2)+' miliardi'));
const core=jp.split('data-liq-role="credit"')[1]?.split('</div>')[0]||'';
assert(core.includes('Ultimo '+canonical.last_date+' · '+fmt(canonical.last_value,2)),
 'Verified source sidecar must never replace canonical JPY credit dates');
for(const other of FX.filter(ccy=>ccy!=='JPY'))
 assert(!studio.render(api(other)).includes('drivers-jpy-official'),
  'BoJ bank credit source is JPY-only: '+other);
console.log('BOJ_JPY_OFFICIAL_BANK_CREDIT_RESEARCH_PASS',JSON.stringify({
 latest:source.last_observation,stock100mYen:source.values.at(-1),
 previous:source.values.at(-2),matchingMonths:source.matched_canonical_months,
 newMonths:source.new_after_canonical,canonicalDate:canonical.last_date,
 fxCoreChanged:false,notNewLoans:true
}));

 // All four full-stock issuer histories reach the existing chart, not only
 // the narrative. Historical native facts stay separate and immutable.
 const sourceFiles={
  USD:'us-h8-bank-credit-research-v1.js',
  EUR:'eur-ecb-nfc-credit-research-v1.js',
  JPY:'jpy-boj-bank-credit-research-v1.js',
  CAD:'cad-official-credit-research-v1.js'
 };
 const before=JSON.stringify(native);
 for(const [ccy,file] of Object.entries(sourceFiles)){
  const issuer=require(path.join(root,'site/fx-quant-v2/next',file));
  const plots=[];
  const html=studio.render({...api(ccy),plot:arg=>{plots.push(arg);return '<svg></svg>';}});
  const credit=plots.find(x=>x.label==='Credito · fonte ufficiale separata '+ccy);
  assert(credit,'Missing issuer chart '+ccy);
  assert.equal(credit.lines[0].values.at(-1).label,issuer.dates.at(-1));
  assert.equal(credit.lines[0].values.at(-1).value,issuer.values.at(-1));
  assert.match(html,/Credito · fonte ufficiale separata/);
 }
 assert.equal(JSON.stringify(native),before);
 // Invalid future or nonnumeric observations must not produce an issuer chart.
 const original=globalThis.FXQuantUSBanksCreditResearch;
 try{
  const bad=structuredClone(original);
  bad.values[0]=null;
  globalThis.FXQuantUSBanksCreditResearch=bad;
  const plots=[];
  studio.render({...api('USD'),plot:arg=>{plots.push(arg);return '<svg></svg>';}});
  assert(!plots.some(x=>x.label==='Credito · fonte ufficiale separata USD'));
 }finally{globalThis.FXQuantUSBanksCreditResearch=original;}
 console.log('NEXT_VERIFIED_ISSUER_CREDIT_CHART_PASS',Object.keys(sourceFiles));

 // The already-collected official alternative reserve series must reach the
 // JPY dossier; it is not a replacement for the original vintage.
 const residual=JSON.parse(fs.readFileSync(path.join(root,'live_data/sections/ESTIMATED_RESIDUAL_GAPS.json'),'utf8'));
 const reserve=residual.lanes['JPY.reserve_balances'];
 const withReserve=(ccy,data=residual)=>studio.render({...api(ccy),get:k=>k==='liquidity'?native:k==='residualResearch'?data:null});
 const japan=withReserve('JPY');
 assert.match(japan,/BANK OF JAPAN · RISERVE DI FINE MESE/);
 assert(japan.includes(reserve.proxy_as_of));
 assert(japan.includes(fmt(reserve.proxy_value/10,2)+' miliardi JPY'));
 assert.match(japan,/equivalenza con la vintage storica non certificata/);
 assert.match(japan,/DLCLAEDBLTTO/,'Credit reading must remain available alongside reserves');
 assert(!withReserve('USD').includes('BANK OF JAPAN · RISERVE DI FINE MESE'));
 for(const mutate of [x=>{x.source_endpoint='https://example.com';},x=>{x.proxy_as_of='2099-01';},x=>{x.continuity_anchor.matched=false;}]){
  const bad=structuredClone(residual);mutate(bad.lanes['JPY.reserve_balances']);
  assert(!withReserve('JPY',bad).includes('BANK OF JAPAN · RISERVE DI FINE MESE'));
 }
 assert.equal(JSON.stringify(native),before);
 console.log('NEXT_JPY_RESERVE_READING_PASS',reserve.proxy_as_of,reserve.proxy_value);

 const tankan=source.tankan;
 assert(tankan,'Expected actual Tankan sidecar from verified production run');
 const plots=[];
 const surveyHtml=studio.render({...api('JPY'),plot:x=>{plots.push(x);return '<svg></svg>';}});
 assert.match(surveyHtml,/BANK OF JAPAN · TANKAN/);
 assert(surveyHtml.includes(tankan.latest_observation));
 const graph=plots.find(x=>x.label==='Condizioni di credito · fonte ufficiale separata JPY');
 assert(graph);
 assert.deepEqual(graph.lines[0].values,tankan.dates.map((label,i)=>({label,value:tankan.lending_attitude[i]})));
 assert(surveyHtml.includes(fmt(tankan.loan_rate_change.at(-1),0)));
 assert(!studio.render(api('EUR')).includes('BANK OF JAPAN · TANKAN'));
 const priorJPY=globalThis.FXQuantJPYBankCreditResearch;
 try{
  globalThis.FXQuantJPYBankCreditResearch={...source,tankan:{...tankan,positive_lending_means:'restrictive'}};
  assert(!studio.render(api('JPY')).includes('BANK OF JAPAN · TANKAN'));
 }finally{globalThis.FXQuantJPYBankCreditResearch=priorJPY;}
 console.log('NEXT_JPY_TANKAN_CHART_PASS',tankan.latest_observation,tankan.lending_attitude.at(-1));
