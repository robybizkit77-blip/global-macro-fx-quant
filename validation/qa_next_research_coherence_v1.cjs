'use strict';
/* Contract test: research thesis, evidence and page continuity must share dates.
   No network, browser, external packages, or changes to FX Core. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const read=x=>fs.readFileSync(x,'utf8');
const json=x=>JSON.parse(read(x));
const app=read('site/fx-quant-v2/next/app.js');
const helperStart=app.indexOf('function researchCase(){');
const overviewStart=app.indexOf('function overview(){');
const overviewEnd=app.indexOf('\nfunction currencies(){',overviewStart);
assert(helperStart>=0&&overviewStart>helperStart&&overviewEnd>overviewStart,'Missing Next Research functions');
new vm.Script(app,{filename:'next-app.js'});
const functions=app.slice(helperStart,overviewEnd);
const initial={
 rates:json('live_data/sections/NATIVE_RATES_DATA.json'),
 dxy:json('live_data/sections/DXY_SYNTHETIC_ECB.json'),
 risk:json('site/fx-quant-v2/cross-asset-live-data.json'),
 pairs:json('live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json'),
 macro:json('live_data/sections/MACRO_THERMOMETER_DATA.json'),
 cot:json('live_data/sections/V247_COT_STORIES.json'),
 ois:json('site/fx-quant-v2/ois-pricing-snapshot.json'),
 cb:json('live_data/sections/NATIVE_CB_DATA.json')
};
const clone=x=>JSON.parse(JSON.stringify(x));
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const validDay=x=>typeof x==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(x);
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const date=x=>validDay(x)?x.slice(8,10)+'/'+x.slice(5,7)+'/'+x.slice(0,4):esc(x||'n.d.');
const fmt=(v,n=2)=>finite(v)?v.toLocaleString('it-IT',{minimumFractionDigits:n,maximumFractionDigits:n}):'—';
const sign=(v,n=1,suffix='')=>finite(v)?(v>0?'+':v<0?'−':'')+fmt(Math.abs(v),n)+suffix:'—';
function evaluate(data,now='2026-11-08'){
 const ctx={
  get:k=>data[k]||null,finite,validDay,esc,date,fmt,sign,
  dayNow:()=>now,
  fresh:(d,window=8)=>validDay(d)&&d<=now&&
    (Date.parse(now+'T12:00:00Z')-Date.parse(d+'T12:00:00Z'))/864e5<=window,
  eurPairs:()=>data.pairs?.pairs||{},
  homeScreenChart:()=>'<div class="test-chart"></div>',
  FLAGS:{USD:'USA'},ROUTES:{rates:'Tassi & OIS',risk:'Rischio'}
 };
 vm.createContext(ctx);
 new vm.Script(functions+'\nvar qa={context:researchCase(),article:overview(),rates:researchBridge("rates"),risk:researchBridge("risk")};').runInContext(ctx,{timeout:1000});
 return ctx.qa;
}
const baseline=evaluate(initial);
assert.match(baseline.article,/class="market-letter market-dashboard"/);
assert.match(baseline.article,/class="letter-evidence"/);
assert.match(baseline.article,/class="dashboard-kpi-grid"/);
assert.match(baseline.article,/class="dashboard-analysis"/);
assert.match(baseline.article,/class="dashboard-dossier"/);
assert.match(baseline.article,/Che cosa mi farebbe cambiare idea/);
assert.match(baseline.rates,/Rileggi la tesi del desk/);
assert.match(baseline.risk,/Nasdaq|Le osservazioni azionario/);
assert(!baseline.article.includes('desk-path-grid'));
const stress=clone(initial);
for(const k of ['NASDAQCOM','VIX','HY_OAS'])stress.risk.streams[k].date='2026-11-09';
stress.risk.streams.NASDAQCOM.change_1d_pct=-4;
stress.risk.streams.VIX.previous=20;stress.risk.streams.VIX.value=31;
stress.risk.streams.HY_OAS.previous=3.1;stress.risk.streams.HY_OAS.value=3.45;
stress.pairs.price_asof='2026-11-09';
let x=evaluate(stress,'2026-11-10');
assert.equal(x.context.kind,'stress');
assert.equal(x.context.focus,'nasdaq');
assert.match(x.article,/data-research-kind="stress"/);
assert.match(x.article,/Credito High Yield/);
const relief=clone(stress);
relief.risk.streams.NASDAQCOM.change_1d_pct=3.2;
relief.risk.streams.VIX.previous=31;relief.risk.streams.VIX.value=23;
relief.risk.streams.HY_OAS.previous=3.45;relief.risk.streams.HY_OAS.value=3.13;
x=evaluate(relief,'2026-11-10');
assert.equal(x.context.kind,'relief');
assert.match(x.article,/La distensione sarebbe fragile/);
const bond=clone(initial);
bond.rates.USD.date='2026-11-12';bond.rates.USD.chg2_bp=12;bond.rates.USD.chg10_bp=8;
bond.dxy.as_of='2026-11-12';bond.pairs.price_asof='2026-11-12';
x=evaluate(bond,'2026-11-12');
assert.equal(x.context.kind,'yield-selloff');
assert.equal(x.context.focus,'rates');
assert.match(x.article,/I rendimenti risalgono/);
assert.doesNotMatch(x.article,/data-research-kind="stress"/);
const fx=clone(bond);
fx.rates.USD.chg2_bp=4;fx.rates.USD.chg10_bp=0;
fx.dxy.previous_value=101;fx.dxy.value=99;
x=evaluate(fx,'2026-11-12');
assert.equal(x.context.kind,'fx-divergence');
assert.equal(x.context.focus,'dxy');
assert.match(x.article,/Treasury e dollaro divergono/);
const outOfSync=clone(stress);
outOfSync.risk.streams.VIX.date='2026-11-08';
assert.notEqual(evaluate(outOfSync,'2026-11-10').context.kind,'stress');
const empty=evaluate({});
assert.equal(empty.context.kind,'mixed');
assert.match(empty.article,/letter-proof-empty/);
const malicious=clone(initial);
malicious.pairs.pairs.EURUSD.decision_frame.relation='<img src=x onerror=alert(1)>';
const html=evaluate(malicious).article;
assert(html.includes('&lt;img'));
assert(!html.includes('<img'));
const stale=evaluate(initial,'2026-12-01');
assert.match(stale.article,/lettura di archivio/);
assert.match(app,/state\.data=nextData/);
assert.match(app,/cache:'no-store'/);
assert.match(app,/visibilitychange/);
const page=read('site/fx-quant-v2/next/index.html');
assert.match(page,/editorial-v4\.css\?v=9/);
assert.match(page,/app\.js\?v=9/);
console.log('NEXT_RESEARCH_COHERENCE_PASS: regimes=stress,relief,yield-selloff,fx-divergence,mixed; matched evidence; fresh/stale/missing; XSS; page continuity; cache refresh');
