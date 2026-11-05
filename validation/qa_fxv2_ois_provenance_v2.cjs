'use strict';
// Pure VM tests of the published OIS page's actual normalizer and renderer.
// Browser/network not required. No writes to production or research journals.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const ROOT=path.resolve(__dirname,'..');
const html=fs.readFileSync(path.join(ROOT,'site/fx-quant-v2/ois.html'),'utf8');
const snapshot=JSON.parse(fs.readFileSync(path.join(ROOT,'site/fx-quant-v2/ois-pricing-snapshot.json'),'utf8'));
const ois=JSON.parse(fs.readFileSync(path.join(ROOT,'live_data/sections/OIS_OPERATIONAL_VIEW.json'),'utf8'));
const est=JSON.parse(fs.readFileSync(path.join(ROOT,'live_data/sections/CB_PRICING_ESTIMATED.json'),'utf8'));
const nzd=JSON.parse(fs.readFileSync(path.join(ROOT,'live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json'),'utf8'));
const match=html.match(/<script>\s*([\s\S]*?)<\/script><\/body>/);
assert(match,'OIS inline application must exist');
const program=match[1];
const boot='setup();\nloadRelativeResearch();\nloadSameContractResearch();\n(async()=>{';
assert(program.includes(boot),'OIS QA fixture must suppress only the network bootstrap');
const app=program.slice(0,program.indexOf(boot))+
 'globalThis.__oisQA={clean,update,render,showDetail,showCompare,liveNormalized,state};\nsetup();\n})();';
const nodes={};
for(const id of ['pricingGrid','pricingRows','feedStatus','detailTitle','detailName','detailMeta','pricingChart',
 'tenors','contractHistory','contractHistoryRows','contractHistoryFoot','detailInterpretation','sourceTitle','sourceType','sourceDate','sourceName','sourceCaveat',
 'compare6','compareText','compareFoot','compareA','compareB','dettaglio']){
 nodes[id]={innerHTML:'',textContent:'',value:'',hidden:false,dataset:{},addEventListener(){},scrollIntoView(){}};
}
const context={document:{getElementById:id=>nodes[id]},console};
vm.createContext(context);
vm.runInContext(app,context,{timeout:5000,filename:'ois-v2-actual-page.js'});
const t=context.__oisQA;
assert.equal(snapshot.eligible_for_fx_engine,false);
assert.equal(Object.keys(snapshot.currencies).length,8);
for(const [ccy,row] of Object.entries(snapshot.currencies))assert.equal(t.update(ccy,row),3);
t.render();
assert.match(nodes.feedStatus.textContent,/8\/8 valute · 24\/24 livelli/);
assert.match(nodes.feedStatus.textContent,/0 tenori da feed \/ 24 da snapshot/);
assert.equal(t.state.currencies.GBP.horizons['6m'].kind,'OIS');
assert.equal(t.state.currencies.USD.horizons['6m'].kind,'FUTURES SECONDARI');
assert.equal(t.state.currencies.USD.horizons['3m'].as_of,snapshot.currencies.USD.horizons['3m'].as_of);
assert.match(nodes.sourceDate.textContent,/Nessun refresh dell’orologio cambia la data del prezzo/);

// A same-date live 6M quote may replace a snapshot; deliberately older
// 3M and 12M must NOT roll the source clock backwards.
const prev3=t.state.currencies.USD.horizons['3m'];
const prev12=t.state.currencies.USD.horizons['12m'];
const sixDate=t.state.currencies.USD.horizons['6m'].as_of;
const probe={kind:'FUTURES SECONDARI',quality:'STIMA INDICATIVA',source:'dated-source-probe',
 origin:'live',as_of:sixDate,horizons:{
 '3m':{rate:4.9,as_of:'2000-01-01'},
 '6m':{rate:4.111,as_of:sixDate,change_1w_bp:7.5},
 '12m':{rate:4.9,as_of:'2000-01-01'}}};
assert.equal(t.update('USD',probe),1,'only same-date live 6M may replace snapshot 6M');
assert.equal(t.state.currencies.USD.horizons['3m'].rate,prev3.rate);
assert.equal(t.state.currencies.USD.horizons['12m'].rate,prev12.rate);
assert.equal(t.state.currencies.USD.horizons['6m'].origin,'live');
assert.equal(t.state.currencies.USD.horizons['6m'].change_1w_bp,7.5);
assert.equal(t.update('USD',{...probe,horizons:{
 '3m':{rate:7.7,as_of:'2999-01-01'}}}),0,'future observation must be rejected');
assert.equal(t.update('USD',{...probe,horizons:{
 '6m':{rate:null,as_of:sixDate}}}),0,'missing 6M cannot overwrite a valid quote');
t.render();
assert.match(nodes.feedStatus.textContent,/1 tenori da feed \/ 23 da snapshot/);
assert.match(nodes.pricingRows.innerHTML,/6M Δ1W|7,5 pb|7.5 pb|7,5/);
assert.match(nodes.tenors.innerHTML,/1W/);

// Actual canonical source: official GBP OIS vs non-OIS futures and NZD proxy.
const live=t.liveNormalized(ois,est,nzd);
assert.equal(live.GBP.kind,'OIS');
assert.equal(live.JPY.kind,'FUTURES');
assert.equal(live.NZD.kind,'PROXY FUTURES');
assert.equal(live.USD.kind,'FUTURES SECONDARI');
assert.equal(live.GBP.origin,'live');
assert.equal(t.update('GBP',live.GBP),3);
assert.equal(t.state.currencies.GBP.horizons['6m'].rate,ois.currencies.GBP.horizons['6m'].rate);
assert.equal(t.state.currencies.GBP.horizons['6m'].change_1w_bp,ois.currencies.GBP.horizons['6m'].change_1w_bp);
t.state.selected='GBP';t.render();
assert.match(nodes.tenors.innerHTML,/1D/);
assert.match(nodes.tenors.innerHTML,/1W/);
assert.match(nodes.sourceCaveat.textContent,/Bank of England/);
t.state.a='GBP';t.state.b='USD';t.showCompare();
assert.match(nodes.compareFoot.textContent,/Differenziale di livello INDICATIVO/);
const gbp6Date=t.state.currencies.GBP.horizons['6m'].as_of;
const usd6Date=t.state.currencies.USD.horizons['6m'].as_of;
assert.match(nodes.compareFoot.textContent,
 gbp6Date===usd6Date?/stessa data/:/date NON allineate/,
 'OIS compare date caveat must reflect the actual per-tenor source dates');
t.state.a='USD';t.state.b='USD';t.showCompare();
assert.equal(nodes.compare6.textContent,'—');
assert.match(nodes.compareText.textContent,/due valute differenti/);
assert(!html.includes('V2_FX_signal_computed=true'));
console.log('FXV2_OIS_PROVENANCE_V2_PASS: 8x3, immutable per-tenor dates, partial updates, 1D/1W, no invented curves or signal');
