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
const day='2026-11-13';
const args={snapshot,operational,research,nzd,today:day};
const result=model(args);
assert.deepEqual(Object.keys(result),['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD']);
assert.equal(result.GBP.kind,'OIS');
assert.equal(result.GBP.officialOis,true);
assert.equal(result.GBP.oneAvailable,3);
assert.equal(result.GBP.rows[1].one.bp,2.3);
assert.equal(result.GBP.rows[1].week.bp,18);
assert.equal(result.GBP.rows[1].asof,'2026-11-12');
assert.equal(result.CAD.rows[1].one.bp,5);
assert.equal(result.CAD.kind,'FUTURES');
assert.equal(result.JPY.rows[1].one.bp,0);
assert.equal(result.AUD.rows[2].one.bp,0);
assert.equal(result.NZD.kind,'PROXY FUTURES');
assert.equal(result.NZD.rows[1].one.bp,-3);
assert.equal(result.USD.kind,'FUTURES SECONDARI');
assert.equal(result.USD.officialOis,false);
assert.equal(result.USD.rows[0].one.bp,3);
assert.equal(result.USD.rows[1].one.bp,3.5);
assert.equal(result.USD.rows[1].week.bp,34);
assert.equal(result.USD.rows[0].week,null,'Missing 1W cannot be a zero change');
assert.equal(result.EUR.rows[1].one.bp,2.5);
assert.equal(result.CHF.rows[1].one.bp,1);
assert.equal(result.CHF.rows[1].week,null);
assert.equal(result.CHF.rows[2].week.bp,17.5);
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
const stale=model({...args,today:'2026-12-15'});
for(const c of Object.keys(stale))for(const t of stale[c].rows)
 assert(!t.one&&!t.week,'Historical snapshot may not be passed off as current daily repricing');
const spoof=structuredClone(operational);
spoof.currencies.GBP.operational_status='WITHHELD';
assert.equal(model({...args,operational:spoof}).GBP.rows[1].one,null,
 'Official OIS status gate is mandatory');
const noResearch=model({...args,research:null});
assert.equal(noResearch.USD.rows[1].one,null,'Secondary futures deltas require research provenance');
assert.equal(noResearch.GBP.rows[1].one.bp,2.3,'Official GBP OIS remains available');
const num=x=>typeof x==='number'&&Number.isFinite(x);
const fmt=(n,p=2)=>num(n)?n.toFixed(p).replace('.',','):'—';
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const renderArgs={...args,currency:'GBP',window:'1d',
 plot:()=>'<div class="chart" data-curve="comparison"></div>',esc,fmt,date:x=>x};
const gbp=render(renderArgs);
assert(gbp.includes('data-pricing-kind="OIS"')&&
 gbp.includes('data-curve="comparison"'),
 'Official OIS current/previous curve comparison required');
assert(gbp.includes('2,3 pb'),'GBP 6M daily OIS change must appear in the first read');
assert(gbp.includes('data-pricing-ccy="CHF"')&&gbp.includes('data-pricing-ccy="NZD"'),
 'Eight-currency 6M benchmark must keep every G8 classification');
assert(gbp.includes('data-rs-pricing-window="1d"')&&
 gbp.includes('data-rs-pricing-window="1w"'),'1D/1W controls required');
const usd=render({...renderArgs,currency:'USD'});
assert(usd.includes('data-pricing-kind="FUTURES SECONDARI"'));
assert(usd.includes('Nessuna curva artificiale')&&
 !usd.includes('data-curve="comparison"'),'Mixed-date USD futures cannot be drawn as a single concurrent curve');
const eur=render({...renderArgs,currency:'EUR'});
assert(eur.includes('Nessuna curva artificiale'));
const chf=render({...renderArgs,currency:'CHF'});
assert(chf.includes('NON una curva OIS ufficiale'),'Secondary SARON futures cannot become OIS');
const alt=render({...renderArgs,currency:'USD',window:'1w'});
assert(alt.includes('data-pricing-window="1w"')&&alt.includes('—'),
 'No 1W archive must be zero-filled');
const old=render({...renderArgs,today:'2026-12-15',currency:'GBP'});
assert(!old.includes('data-curve="comparison"'),'Stale OIS must not draw current curve');
const badSource=structuredClone(snapshot);
badSource.currencies.GBP.source='<img src=x onerror=alert(1)>';
const safe=render({...renderArgs,snapshot:badSource,operational});
assert(safe.includes('&lt;img')&&!safe.includes('<img'));
const page=fs.readFileSync(root+'index.html','utf8');
const app=fs.readFileSync(root+'app.js','utf8');
const rates=fs.readFileSync(root+'rates-studio.js','utf8');
assert(page.indexOf('rates-pricing-moves-v1.js?v=1')<page.indexOf('rates-studio.js?v=5'));
assert(page.includes('rates-studio.css?v=4'));
assert(app.includes("oisSameContract:'../ois-same-contract-repricing-research.json'"));
assert(app.includes("oisOperational:'../../../live_data/sections/OIS_OPERATIONAL_VIEW.json'"));
assert(app.includes("data-rs-pricing-window"));
assert(rates.includes('FXQuantPricingMoves?.render'));
assert(!rates.includes('change_1d_bp:0')&&!rates.includes('change_1w_bp:0'),
 'Renderer must not invent zero deltas');
console.log('NEXT_RATES_OIS_1D_1W_G8_PASS: official GBP curve + official futures + same-contract research, stale and rollover guards');
