'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const load=p=>JSON.parse(fs.readFileSync(path.join(root,p),'utf8'));
const {read}=require(path.join(root,'site/fx-quant-v2/next/rates-economic-reading.js'));
const gov=load('live_data/sections/NATIVE_RATES_DATA.json');
const money=load('site/fx-quant-v2/ois-pricing-snapshot.json').currencies;
const today='2026-11-10';
const names=['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'];
for(const c of names){
 const r=gov[c],h2=r?.history2,h10=r?.history10;
 const ten=new Map((h10?.dates||[]).map((x,i)=>[x,h10.values[i]]));
 const pairs=(h2?.dates||[]).map((d,i)=>({d,y2:h2.values[i],y10:ten.get(d)}))
   .filter(x=>/^\d{4}-\d{2}-\d{2}$/.test(x.d)&&x.d<=r.date&&x.d<=today&&
     Number.isFinite(x.y2)&&Number.isFinite(x.y10)).sort((a,b)=>a.d.localeCompare(b.d));
 const end=pairs.at(-1),prev=pairs.at(-2);
 const args={country:c,now:today,asof:end?.d,previous:prev?.d,
  bp2:end&&prev?(end.y2-prev.y2)*100:null,
  bp10:end&&prev?(end.y10-prev.y10)*100:null,
  kind:money[c]?.kind,quality:money[c]?.quality,h6:money[c]?.horizons?.['6m']};
 const x=read(args);
 assert(x.headline.length>20&&x.meaning.length>30&&x.pricingEvidence.length>25&&x.watch.length>25,c);
 assert(!/undefined|NaN|Infinity/.test(x.headline+x.meaning+x.pricingEvidence+x.watch),c);
 if(end&&prev)assert(x.meaning.includes(end.d)&&x.meaning.includes(prev.d),c+' source dates');
 if(end?.d!=='2026-11-09'&&args.h6?.as_of!==end?.d&&
   args.h6?.rate!==null&&args.h6?.rate!==undefined&&args.h6?.as_of<=today&&end&&prev)
  assert(x.pricingEvidence.includes('non sono simultanee'),c+' different dates');
}
const mk=(bp2,bp10,asof='2026-11-09',extra={})=>read({
 country:'USD',now:today,asof,previous:asof<'2026-11-06'?'2026-09-29':'2026-11-06',bp2,bp10,
 kind:'OIS',quality:'FONTE UFFICIALE',
 h6:{rate:4.10,as_of:asof,change_1d_bp:2},...extra
});
assert.match(mk(-12,-3).meaning,/bull steepening/);
assert.match(mk(-3,-12).meaning,/bull flattening/);
assert.match(mk(12,3).meaning,/bear flattening/);
assert.match(mk(3,12).meaning,/bear steepening/);
assert.match(mk(-12,-3).headline,/2Y guida/);
assert.match(mk(-3,-12).headline,/10Y guida/);
assert.match(mk(-3,-12,'2026-09-30').headline,/storica/);
assert.match(mk(4,8,'2026-11-09',{h6:{rate:4.10,as_of:'2026-11-06',change_1d_bp:17}}).pricingEvidence,
 /non sono simultanee/);
assert.doesNotMatch(mk(4,8,'2026-11-09',{h6:{rate:4.10,as_of:'2026-11-06',change_1d_bp:17}}).pricingEvidence,
 /Variazione 1D/);
assert.match(mk(4,8).pricingEvidence,/Variazione 1D/);
assert.match(mk(4,8,'2026-11-09',{h6:{rate:4.10,as_of:'2026-11-09',change_1d_bp:null}}).pricingEvidence,
 /Manca una variazione 1D/);
assert.match(mk(4,8,'2026-11-09',{h6:{rate:4.10,as_of:'2026-12-01',change_1d_bp:4}}).pricingEvidence,
 /non abbiamo un 6M/i);
const page=fs.readFileSync(path.join(root,'site/fx-quant-v2/next/index.html'),'utf8');
const rates=fs.readFileSync(path.join(root,'site/fx-quant-v2/next/rates-studio.js'),'utf8');
const app=fs.readFileSync(path.join(root,'site/fx-quant-v2/next/app.js'),'utf8');
assert(page.includes('rates-economic-reading.js?v=20'));
assert(page.includes('rates-studio.js?v=3'));
assert(page.includes('rates-studio.css?v=2'));
assert(page.includes('app.js?v=18.53-rates-fx-context'));
assert(rates.includes('fxRelativeEvidence(c,other)'), 'Rates first read needs a FX handoff');
assert(rates.includes('root.FXQuantRatesBridge.snapshot('),
 'FX movement must come from certified common-date 2Y/ECB bridge, not a new correlation');
assert(rates.includes('data-fx-proof=')&&rates.includes('data-rates-openpair='),
 'Verified/unavailable evidence tiers and real pair deep links are mandatory');
assert(app.includes("e.target.closest('[data-rates-openpair]')")&&
 app.includes("if(!get('pairs')?.pairs?.[pair])return;"),
 'Pair handoff must fail closed if pair source is absent');
const ratesCss=fs.readFileSync(path.join(root,'site/fx-quant-v2/next/rates-studio.css'),'utf8');
assert(ratesCss.includes('.rates-fx-handoff')&&ratesCss.includes('max-width:600px')&&
 ratesCss.includes(':focus-visible'),'Rates evidence design must be responsive and keyboard accessible');
assert(page.indexOf('rates-economic-reading.js')<page.indexOf('rates-studio.js'));
assert(rates.includes('m.headline')&&rates.includes('m.pricingEvidence')&&rates.includes('m.watch'));
console.log('NEXT_RATES_V20_PASS: G8 8/8, four curve regimes, source-date and stale guards, 6M unavailable/non-simultaneous/same-date.');
