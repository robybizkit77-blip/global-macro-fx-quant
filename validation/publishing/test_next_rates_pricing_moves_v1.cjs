'use strict';
/* Strict read-only 1D/1W OIS vs futures repricing contract. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const root='site/fx-quant-v2/next/';
const source=fs.readFileSync(root+'rates-pricing-moves-v1.js','utf8');
new vm.Script(source,{filename:'rates-pricing-moves-v1.js'});
const {model,readCurrency,verifiedSecondary,render}=require('../../site/fx-quant-v2/next/rates-pricing-moves-v1.js');
const json=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const snapshot=json('site/fx-quant-v2/ois-pricing-snapshot.json');
const operational=json('live_data/sections/OIS_OPERATIONAL_VIEW.json');
const research=json('site/fx-quant-v2/ois-same-contract-repricing-research.json');
const nzd=json('live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json');
const day=snapshot.snapshot_built_from_repo_date||'2026-11-13';
const args={snapshot,operational,research,nzd,today:day};
const result=model(args);
assert.deepEqual(Object.keys(result),['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD']);
assert.equal(result.GBP.kind,'OIS');
assert.equal(result.GBP.officialOis,true);
assert.equal(result.GBP.oneAvailable,3);
const same=(a,b)=>typeof a==='number'&&typeof b==='number'&&Math.abs(a-b)<.011;
const official=(ccy,t,window)=>{
 const p=snapshot.currencies[ccy].horizons[t];
 const o=operational.currencies[ccy].horizons[t];
 const prop=window==='1d'?'change_1d_bp':'change_1w_bp';
 return operational.currencies[ccy].operational_status==='GREEN_OFFICIAL'&&
  o&&o.rate===p.rate&&same(o[prop],p[prop])?o[prop]:null;
};
assert.equal(result.GBP.rows[1].one?.bp,official('GBP','6m','1d'));
assert.equal(result.GBP.rows[1].week?.bp,official('GBP','6m','1w'));
assert.equal(result.GBP.rows[1].asof,snapshot.currencies.GBP.horizons['6m'].as_of);
assert.equal(result.CAD.kind,'FUTURES');
assert.equal(result.CAD.rows[1].one?.bp,official('CAD','6m','1d'));
assert.equal(result.JPY.rows[1].one?.bp,official('JPY','6m','1d'));
assert.equal(result.AUD.rows[2].one?.bp,official('AUD','12m','1d'));
assert.equal(result.NZD.kind,'PROXY FUTURES');
assert.equal(result.NZD.rows[1].one?.bp,nzd.horizons['6m'].change_1d_bp);
assert.equal(result.USD.kind,'FUTURES SECONDARI');
assert.equal(result.USD.officialOis,false);
for(const c of ['USD','EUR','CHF']){
 for(const t of ['3m','6m','12m']){
  const row=result[c].rows.find(x=>x.tenor===t),from=research.currencies[c]?.[t];
  const expected=from?.as_of===row.asof&&from?.contract===row.contract?from:null;
  assert.equal(row.one?.bp??null,expected?.one_day&&typeof expected.change_1d_bp==='number'?
   expected.change_1d_bp:null,c+' '+t+' daily same-listed-contract lineage');
  if(row.week)assert.equal(row.week.bp,expected.change_1w_bp);
 }
}
const missingWeek=structuredClone(research);
missingWeek.currencies.USD['3m'].one_week=null;
missingWeek.currencies.USD['3m'].change_1w_bp=null;
assert.equal(model({...args,research:missingWeek}).USD.rows[0].week,null,
 'A source without a weekly move must render missing, not zero');
const draft=structuredClone(research);
draft.currencies.USD['6m'].contract='NEW_ROTATED_CONTRACT';
assert.equal(model({...args,research:draft}).USD.rows[1].one,null,
 'Changing listed contract cannot produce a fake same-contract delta');
const forged=structuredClone(research);
forged.currencies.EUR['6m'].one_day.reference_rate_pct=2.0;
assert.equal(model({...args,research:forged}).EUR.rows[1].one,null,
 'Quoted values and basis-point change must reconcile numerically');
const future=structuredClone(snapshot);
future.currencies.CHF.horizons['6m'].as_of='2999-11-16';
assert.equal(model({...args,snapshot:future}).CHF.rows[1].one,null,
 'Future source observations are disallowed');
const staleDay=new Date(Date.parse(day+'T12:00:00Z')+32*864e5).toISOString().slice(0,10);
const stale=model({...args,today:staleDay});
for(const c of Object.keys(stale))for(const t of stale[c].rows)
 assert(!t.one&&!t.week,'Historical snapshot may not be passed off as current daily repricing');
const spoof=structuredClone(operational);
spoof.currencies.GBP.operational_status='WITHHELD';
assert.equal(model({...args,operational:spoof}).GBP.rows[1].one,null,
 'Official OIS status gate is mandatory');
const noResearch=model({...args,research:null});
assert.equal(noResearch.USD.rows[1].one,null,'Secondary futures deltas require research provenance');
assert.equal(noResearch.GBP.rows[1].one.bp,result.GBP.rows[1].one.bp,'Official GBP OIS remains available');
const num=x=>typeof x==='number'&&Number.isFinite(x);
const fmt=(n,p=2)=>num(n)?n.toFixed(p).replace('.',','):'—';
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const renderArgs={...args,currency:'GBP',window:'1d',
 plot:()=>'<div class="chart" data-curve="comparison"></div>',esc,fmt,date:x=>x};
const gbp=render(renderArgs);
assert(gbp.includes('data-pricing-kind="OIS"')&&
 gbp.includes('data-curve="comparison"'),
 'Official OIS current/previous curve comparison required');
assert(gbp.includes(String(result.GBP.rows[1].one.bp).replace('.',',')+' pb'),
 'GBP official 6M change must reflect the latest source without a frozen value');
assert(gbp.includes('data-pricing-ccy="CHF"')&&gbp.includes('data-pricing-ccy="NZD"'),
 'Eight-currency 6M benchmark must keep every G8 classification');
assert(gbp.includes('data-rs-pricing-window="1d"')&&
 gbp.includes('data-rs-pricing-window="1w"'),'1D/1W controls required');
for(const c of ['USD','EUR','CHF']){
 const text=render({...renderArgs,currency:c});
 assert(text.includes('data-pricing-kind="FUTURES SECONDARI"'),
  c+' secondary contracts cannot be labeled official OIS');
 assert(!text.includes('Questa è una curva OIS ufficiale'),
  c+' futures cannot become a central-bank OIS curve');
 const tenors=result[c].rows;
 const matched=tenors.every(x=>x.one)&&new Set(tenors.map(x=>x.asof)).size===1&&
  new Set(tenors.map(x=>x.one.from).filter(Boolean)).size<=1;
 assert.equal(text.includes('data-curve="comparison"'),matched,
  c+' current-vs-previous curve must only join 3 validated tenors on matching dates');
}
const alt=render({...renderArgs,currency:'USD',window:'1w',research:missingWeek});
assert(alt.includes('data-pricing-window="1w"')&&alt.includes('—'),
 'Missing weekly futures repricing must remain missing, not zero');
const old=render({...renderArgs,today:staleDay,currency:'GBP'});
assert(!old.includes('data-curve="comparison"'),'Stale OIS must not draw current curve');
const badSource=structuredClone(snapshot);
badSource.currencies.GBP.source='<img src=x onerror=alert(1)>';
const safe=render({...renderArgs,snapshot:badSource,operational});
assert(safe.includes('&lt;img')&&!safe.includes('<img'));
const page=fs.readFileSync(root+'index.html','utf8');
const app=fs.readFileSync(root+'app.js','utf8');
const rates=fs.readFileSync(root+'rates-studio.js','utf8');
assert(page.indexOf('rates-pricing-moves-v1.js?v=1')<page.indexOf('rates-studio.js?v=6'));
assert(page.includes('rates-studio.css?v=5'));
assert(app.includes("oisSameContract:'../ois-same-contract-repricing-research.json'"));
assert(app.includes("oisOperational:'../../../live_data/sections/OIS_OPERATIONAL_VIEW.json'"));
assert(app.includes("data-rs-pricing-window"));
assert(rates.includes('FXQuantPricingMoves?.render'));
assert(!rates.includes('change_1d_bp:0')&&!rates.includes('change_1w_bp:0'),
 'Renderer must not invent zero deltas');
console.log('NEXT_RATES_OIS_1D_1W_G8_PASS: official GBP curve + official futures + same-contract research, stale and rollover guards');
