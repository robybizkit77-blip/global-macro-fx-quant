'use strict';
/* V9: usable decisions, not fake trading signals. Test with real repo snapshots. */
const assert=require('node:assert/strict'),fs=require('node:fs');
const {snapshot,profile,series,build}=require('../site/fx-quant-v2/next/decision-journey.js');
const json=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const doc=json('live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json');
const prices=json('live_data/sections/ECB_G8_PRICE_HISTORY.json');
const now=doc.price_asof;
const all=snapshot(doc,prices,now);
assert.equal(all.total,28,'G8 canonical pair universe changed');
assert.equal(all.cases.length,all.total);
assert(all.qualified<=all.total&&all.qualified>=0);
assert(all.examples.length<=3);
assert.deepEqual(all.examples.map(x=>x.key),[...all.examples.map(x=>x.key)].sort());
assert(all.examples.every(x=>x.research&&x.fresh&&x.closes.length>=22));
assert(all.examples.every(x=>x.fav&&x.price==='GOOD'&&x.timing==='ALIGNED'));
const eur=series(prices,'EURUSD',doc.price_asof,now);
assert(eur.length>100);
assert.equal(eur.at(-1).label,doc.price_asof);
const fx=prices.rows.find(x=>x.Date===doc.price_asof);
assert(fx);
assert(Math.abs(eur.at(-1).value-fx.USD/fx.EUR)<1e-10,'EUR/USD ECB cross formula');
const usdJpy=series(prices,'USDJPY',doc.price_asof,now);
assert(Math.abs(usdJpy.at(-1).value-fx.JPY/fx.USD)<1e-10,'USD/JPY ECB cross formula');
const usdcad=series(prices,'USDCAD',doc.price_asof,now);
assert(Math.abs(usdcad.at(-1).value-fx.CAD/fx.USD)<1e-10,'USD/CAD ECB cross formula');
assert.deepEqual(series(prices,'EURUSD','2027-01-01','2026-11-08'),[],'future data rejected');
assert.deepEqual(series(prices,'EURUSD','2026-11-07','2026-11-08'),[],'missing as-of alignment rejected');
assert.deepEqual(series({},'EURUSD',now,now),[],'missing price feed cannot invent series');
const missing=snapshot(doc,{},now);
assert.equal(missing.qualified,0,'unverified price cannot create shortlist');
const stale=snapshot(doc,prices,'2027-02-01');
assert.equal(stale.qualified,0,'stale feed cannot create current shortlist');
assert(all.cases.every(x=>!x.eligible||x.quality==='PULITO'));
const changed=JSON.parse(JSON.stringify(doc));
changed.pairs.EURUSD.setup.price.state='BAD';
const noLong=profile('EURUSD',changed,prices,now);
assert(!noLong.research,'contradictory price cannot qualify for attention');
const fmt=(n,p=2)=>Number.isFinite(n)?n.toLocaleString('it-IT',{minimumFractionDigits:p,maximumFractionDigits:p}):'—';
const sign=(n,p=1,s='')=>Number.isFinite(n)?(n>0?'+':n<0?'−':'')+fmt(Math.abs(n),p)+s:'—';
const date=d=>/^\d{4}-\d{2}-\d{2}$/.test(d||'')?d.slice(8,10)+'/'+d.slice(5,7)+'/'+d.slice(0,4):d||'n.d.';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let charts=0;
const base={get:k=>({pairs:doc,currencyPrices:prices})[k],state:{pair:'EURUSD',pairPriceWindow:60},plot:o=>{charts++;return '<div class="chart" data-n="'+o.lines[0].values.length+'"></div>'},fmt,sign,date,esc,dayNow:()=>now};
const component=build(base),h=component.overview(),p=component.pair();
assert.match(h,/decision-overview/);
assert.match(h,/VERDETTO OPERATIVO/);
assert(!/Compra ora|Vendi ora|Segnale d'ingresso/.test(h),'shortlist is not an order');
assert.match(p,/TRADE ATTRACTIVENESS/);
assert.match(p,/THESIS STRENGTH/);
assert.match(p,/Nessun livello d’ingresso/);
assert.match(p,/Nessun OHLC o candela H4/);
assert.match(p,/data-v9-price-window="20"/);
assert.match(p,/data-n="60"/);
assert.equal(charts,1);
const bad=JSON.parse(JSON.stringify(doc));bad.pairs.EURUSD.decision_frame.relation='<img src=x onerror=alert(1)>';
const malicious=build({...base,get:k=>({pairs:bad,currencyPrices:prices})[k]}).pair();
assert(malicious.includes('&lt;img')&&!malicious.includes('<img'),'escape source content');
const empty=build({...base,get:()=>null});
assert.match(empty.overview(),/feed delle 28 coppie non è disponibile/);
assert.match(empty.pair(),/Grafico daily non validato/);

/* V10: daily directional evidence follows the denominator/numerator of the pair. */
const profiles=all.cases.filter(x=>Number.isFinite(x.m5)&&Number.isFinite(x.m20));
assert(profiles.length>=20,'Insufficient validated G8 daily price data for directional audit');
for(const pair of profiles){
 const expected=pair.fav===pair.key.slice(0,3)?1:pair.fav===pair.key.slice(3)?-1:0;
 assert.equal(pair.direction,expected,'Incorrect quote orientation for '+pair.key);
 if(expected){
  assert.equal(pair.fiveState,pair.m5*expected>0?'COERENTE':pair.m5*expected<0?'CONTRARIO':'STABILE');
  assert.equal(pair.twentyState,pair.m20*expected>0?'COERENTE':pair.m20*expected<0?'CONTRARIO':'STABILE');
  assert.equal(pair.horizonConflict,pair.fiveState==='CONTRARIO'||pair.twentyState==='CONTRARIO');
 }
 assert(pair.breakHigh>=pair.breakLow,'Invalid historical fixing range '+pair.key);
}
const v10=build(base).pair();
assert.match(v10,/decision-price-evidence/,'Daily confirmation indicators missing');
assert.match(v10,/5 FIXING/);
assert.match(v10,/20 FIXING/);
assert.match(v10,/RANGE 20 FIXING PRECEDENTI/);
assert.match(v10,/Rispetto al fixing precedente/);
assert.match(v10,/significatività statistica/);
const compare=profile('EURUSD',doc,prices,now);
const r5=compare.closes.at(-6).value,r6=compare.closes.at(-7).value,r1=compare.closes.at(-2).value;
assert(Math.abs(compare.change5-(compare.m5-(r1/r6-1)*100))<1e-10,'5D change calculation incorrect');
const changedMarket=JSON.parse(JSON.stringify(prices));
const lastRow=changedMarket.rows.find(x=>x.Date===doc.price_asof);
const row5=changedMarket.rows.find(x=>x.Date===compare.closes.at(-6).label);
const row20=changedMarket.rows.find(x=>x.Date===compare.closes.at(-21).label);
assert(lastRow&&row5&&row20,'Need exact fixing dates to test direction inversion');
row5.USD=lastRow.USD*.99;
row20.USD=lastRow.USD*1.01;
const changedProfile=profile('EURUSD',doc,changedMarket,now);
if(changedProfile.fav==='USD'){
 assert.equal(changedProfile.fiveState,'CONTRARIO','5D reversal must be shown for USD as EURUSD denominator');
 assert.equal(changedProfile.twentyState,'COERENTE','20D alignment must be shown for USD as EURUSD denominator');
 assert.match(changedProfile.alignment,/PAUSA A 5 SEDUTE/);
}
const missingPrice=profile('EURUSD',doc,{},now);
assert.equal(missingPrice.fiveState,'NON VALUTABILE','Missing daily series must not imply evidence');
assert.equal(missingPrice.m1,null);


/* V11: next fixing references are exact prior 20 ECB price observations, not entries. */
const eurWatch=profile('EURUSD',doc,prices,now);
const cadWatch=profile('USDCAD',doc,prices,now);
assert.equal(eurWatch.direction,-1,'Favoured USD is EURUSD quote');
assert.equal(eurWatch.watch.favorable,eurWatch.breakLow);
assert.equal(eurWatch.watch.adverse,eurWatch.breakHigh);
assert.equal(eurWatch.watch.favorableDirection,'Sotto');
assert.equal(cadWatch.direction,1,'Favoured USD is USDCAD base');
assert.equal(cadWatch.watch.favorable,cadWatch.breakHigh);
assert.equal(cadWatch.watch.adverse,cadWatch.breakLow);
assert.equal(cadWatch.watch.favorableDirection,'Sopra');
assert(eurWatch.watch.favorableDistancePct>0&&eurWatch.watch.adverseDistancePct>0,'EURUSD inside reference range');
assert(cadWatch.watch.favorableDistancePct>0&&cadWatch.watch.adverseDistancePct>0,'USDCAD inside reference range');
const currentDailyRow=prices.rows.find(x=>x.Date===doc.price_asof);
assert(currentDailyRow,'Current daily fixing row missing');
function revisedToday(mutator){
 const data=JSON.parse(JSON.stringify(prices));
 const row=data.rows.find(x=>x.Date===doc.price_asof);
 mutator(row);return data;
}
const eurStrong=profile('EURUSD',doc,revisedToday(row=>{row.USD=eurWatch.breakLow*.99*row.EUR;}),now);
assert.equal(eurStrong.watch.favorablePassed,true,'EURUSD below prior 20D low must be flagged as already beyond');
assert.equal(eurStrong.watch.adversePassed,false);
assert.equal(eurStrong.watch.favorable,eurWatch.watch.favorable,'Current fixing may not leak into previous 20-fixing range');
const eurWeak=profile('EURUSD',doc,revisedToday(row=>{row.USD=eurWatch.breakHigh*1.01*row.EUR;}),now);
assert.equal(eurWeak.watch.adversePassed,true,'EURUSD above prior 20D high contrasts USD thesis');
const cadStrong=profile('USDCAD',doc,revisedToday(row=>{row.CAD=cadWatch.breakHigh*1.01*row.USD;}),now);
assert.equal(cadStrong.watch.favorablePassed,true,'USDCAD above previous 20D high favours USD');
const cadWeak=profile('USDCAD',doc,revisedToday(row=>{row.CAD=cadWatch.breakLow*.99*row.USD;}),now);
assert.equal(cadWeak.watch.adversePassed,true,'USDCAD below previous 20D low contrasts USD thesis');
assert.equal(profile('AUDUSD',doc,prices,now).watch.ready,false,'No validated favourite means no directional threshold');
assert.equal(profile('EURUSD',doc,{},now).watch.ready,false,'Missing ECB history must not produce levels');
assert.equal(profile('EURUSD',doc,prices,'2027-01-05').watch.ready,false,'Stale snapshots must not generate watch levels');
const v11Pair=build(base).pair();
assert.match(v11Pair,/decision-daily-watch/);
assert.match(v11Pair,/VERSO FAVOREVOLE/);
assert.match(v11Pair,/VERSO CONTRARIO/);
assert.match(v11Pair,/20 fixing precedenti/);
assert.match(v11Pair,/non supporti o resistenze intraday/);
const staleBase={...base,dayNow:()=> '2027-01-05'};
const staleHtml=build(staleBase).pair();
assert.match(staleHtml,/Riferimenti di prezzo non verificabili/);
assert.doesNotMatch(staleHtml,/decision-watch-columns/);


/* V12: visible reference segments describe the CURRENT fixing, never full-width history. */
const vm=require('node:vm');
const appCode=fs.readFileSync('site/fx-quant-v2/next/app.js','utf8');
const plotStart=appCode.indexOf('function plot(opts){');
const plotEnd=appCode.indexOf('\nfunction chartEvents(e){',plotStart);
assert(plotStart>=0&&plotEnd>plotStart,'Missing generic chart renderer');
const chartContext={state:{chartIndex:0,charts:{}},finite:Number.isFinite,
 validDay:s=>typeof s==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(s),
 fmt,esc,date,
 values:eurWatch.closes.slice(-20),refs:[
  {kind:'favorable',value:eurWatch.watch.favorable},
  {kind:'adverse',value:eurWatch.watch.adverse}]};
vm.createContext(chartContext);
new vm.Script(appCode.slice(plotStart,plotEnd)+
 "\nvar drawn=plot({lines:[{name:'EURUSD BCE',color:'#9bd9cc',values}],referenceLines:refs,precision:5});"+
 "\nvar plain=plot({lines:[{name:'EURUSD BCE',values}],referenceLines:[],precision:5});"+
 "\nvar malformed=plot({lines:[{name:'EURUSD BCE',values}],referenceLines:[{kind:'untrusted',value:1000000}],precision:5});"
).runInContext(chartContext,{timeout:1500});
assert.match(chartContext.drawn,/data-reference-line="favorable"/);
assert.match(chartContext.drawn,/data-reference-line="adverse"/);
assert.match(chartContext.drawn,/data-reference-label="favorable"/);
assert.match(chartContext.drawn,/data-reference-label="adverse"/);
assert.doesNotMatch(chartContext.plain,/data-reference-line=/);
assert.doesNotMatch(chartContext.malformed,/data-reference-line=/);
const segments=[...chartContext.drawn.matchAll(/<line data-reference-line="(favorable|adverse)" x1="(\d+)" x2="(\d+)" y1="([\d.]+)"/g)];
assert.equal(segments.length,2,'Only two valid current reference segments are drawn');
assert(segments.every(m=>Number(m[2])>400&&Number(m[3])===682),'Reference must be a short right-side segment, not a fake historical line');
const pricePlotState={pair:'EURUSD',pairPriceWindow:60,pairShowReferences:true};
let plotOpts=null;
const plotAudit=o=>{plotOpts=o;return '<div class="chart">ECB</div>'};
const controls={...base,state:pricePlotState,plot:plotAudit};
let rendered=build(controls).pair();
assert.equal(plotOpts.referenceLines.length,2);
assert.match(rendered,/data-v12-reference-toggle="1"/);
assert.match(rendered,/Riferimenti visibili/);
pricePlotState.pairShowReferences=false;
rendered=build(controls).pair();
assert.equal(plotOpts.referenceLines.length,0,'Chart toggle must remove only overlays');
assert.match(rendered,/Mostra riferimenti/);
assert.match(rendered,/decision-watch-columns/,'Hiding chart overlays must preserve factual watch levels');
pricePlotState.pair='EURGBP';
pricePlotState.pairShowReferences=true;
rendered=build(controls).pair();
assert.equal(plotOpts.referenceLines.length,0,'No structural thesis must not create chart references');
assert.doesNotMatch(rendered,/data-v12-reference-toggle/);
const staleControls={...base,state:{pair:'EURUSD',pairPriceWindow:60,pairShowReferences:true},dayNow:()=> '2027-01-05',plot:plotAudit};
build(staleControls).pair();
assert.equal(plotOpts.referenceLines.length,0,'Stale history must not create fresh references');

const index=fs.readFileSync('site/fx-quant-v2/next/index.html','utf8');
const app=fs.readFileSync('site/fx-quant-v2/next/app.js','utf8');
assert(index.includes('decision-journey.js?v=14')&&index.indexOf('decision-journey.js')<index.indexOf('app.js?v=15'));
assert(index.includes('editorial-v4.css?v=15'));
assert(app.includes('window.FXQuantDecisionJourney?.build'));
assert(app.includes('[data-v9-price-window]'));
console.log('NEXT_V12_DECISION_PASS: 28 FX pairs, honest shortlist, ECB cross price, daily chart, no H4 fiction, data gaps, safe rendering');
