'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const h=require('../../site/fx-quant-v2/next/data-health-v1.js');
const today='2026-11-26';
const data={currencyPrices:{last_as_of:today},pairs:{price_asof:today,macro_baseline_asof:'2026-09-25'},
 rates:{USD:{date:'2026-11-25'},CHF:{date:'2026-09-30'}},
 macroObserved:{generated_europe_rome_day:today},
 oisOperational:{currencies:{USD:{as_of:today,operational_status:'WITHHELD'},CHF:{as_of:today,operational_status:'GREEN_ESTIMATED'}}},
 liquidity:{USD:{as_of:'2026-08',liquidity:{label:'M2',dates:['2026-09','2026-10'],last_date:'2026-10'}}},
 cotHistory:{USD:{dates:['2026-11-17']}},risk:{streams:{VIX:{date:'2026-11-25'}}}};
const r=h.read(data,today),items=name=>r.rows.find(x=>x.name===name).items;
assert.equal(items('Forex e coppie')[0].state,'observed');
assert.equal(items('Tassi governativi').find(x=>x.label==='CHF').state,'review');
assert.equal(items('Pricing monetario').find(x=>x.label==='USD').state,'withheld');
assert.equal(items('Pricing monetario').find(x=>x.label==='CHF').state,'estimated');
assert.equal(items('Liquidità e credito').find(x=>x.label==='USD · M2').day,'2026-10');
assert.equal(items('Liquidità e credito').find(x=>x.label==='USD · M2').state,'observed');
assert.equal(items('Base strutturale FX')[0].state,'frozen');
assert.equal(r.attention,true);
assert.equal(h.read({},today).attention,true);
assert.equal(h.periodEnd('31/07/2026'),Date.UTC(2026,6,31));
assert.equal(h.periodEnd('2026-Q3'),Date.UTC(2026,8,30));
assert.ok(h.render(r,String).includes('non certificazione di freschezza'));
const supplemental=h.read(data,today,{FXQuantGBPBoEReservesResearch:{source_period:'2026-11-25'},FXQuantNZDRBNZLiquidity:{period:'2026-09',credit_conditions:{latest_observation:'2026-09'}}});
const sup=supplemental.rows.find(x=>x.name==='Fonti integrative · liquidità e credito').items;
assert.equal(sup.find(x=>x.label==='GBP · Riserve BoE settimanali').state,'research');
assert.equal(sup.find(x=>x.label==='NZD · D10/C50 liquidità, moneta, credito').day,'2026-09');
assert.equal(sup.find(x=>x.label==='CHF · Credito SNB').state,'missing');
const root=path.resolve(__dirname,'../..');
const vm=require('node:vm'),context={};context.window=context;
vm.createContext(context);
for(const name of ['us-h8-bank-credit-research-v1.js','eur-ecb-nfc-credit-research-v1.js','gbp-boe-reserves-research-v1.js','gbp-boe-secured-credit-research-v1.js','jpy-boj-bank-credit-research-v1.js','cad-official-credit-research-v1.js','aud-rba-business-credit-growth-research-v1.js','aud-rba-es-balances-research-v1.js','nzd-rbnz-liquidity-research-v1.js']){
 vm.runInContext(fs.readFileSync(path.join(root,'site/fx-quant-v2/next',name),'utf8'),context,{filename:name});
}
const read=p=>JSON.parse(fs.readFileSync(path.join(root,p),'utf8'));
const live=h.read({rates:read('live_data/sections/NATIVE_RATES_DATA.json'),
 liquidity:read('live_data/sections/NATIVE_LIQ_DATA.json'),
 currencyPrices:read('live_data/sections/ECB_G8_PRICE_HISTORY.json'),
 pairs:read('live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json'),
 oisOperational:read('live_data/sections/OIS_OPERATIONAL_VIEW.json'),
 cb:read('live_data/sections/NATIVE_CB_DATA.json'),
 cotHistory:read('live_data/sections/V250_COT_CHART_DATA.json'),
 macroObserved:read('site/control-room-preview/macro-v3-current-evidence.json'),
 risk:read('site/fx-quant-v2/cross-asset-live-data.json'),
 news:read('live_data/sections/NEWS_PULSE_OPERATIONAL.json'),
 calendar:read('live_data/sections/CALENDAR_OPERATIONAL_VIEW.json'),
 residualResearch:read('live_data/sections/ESTIMATED_RESIDUAL_GAPS.json'),
 chfSpot:read('live_data/sections/CHF_SNB_10Y_SPOT_CONTEXT.json'),
 chfResearch:read('site/fx-quant-v2/chf-snb-paired-history.json'),
 audDailyResearch:read('site/fx-quant-v2/aud-rba-f2-history-research.json'),
 ois:read('site/fx-quant-v2/ois-pricing-snapshot.json'),
 nzdDirectionalProxy:read('live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json'),
 nzdReconciled:read('site/fx-quant-v2/nzd-rbnz-b2-reconciled-research.json'),
 nzdPostroll:read('site/fx-quant-v2/nzd-b2-postroll-web-research.json')},
 new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Rome',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date()),context);
assert.equal(live.rows.length,12);
assert.ok(live.rows.find(x=>x.name==='Fonti integrative · tassi e pricing').items.find(x=>x.label==='NZD · RBNZ B2 HTML/XLSX').day);
assert.equal(live.rows.find(x=>x.name==='Fonti integrative · liquidità e credito').items.length,21);
assert.ok(live.rows.find(x=>x.name==='Fonti integrative · liquidità e credito').items.every(x=>x.day), 'all registered supplemental liquidity dates present');
console.log('DATA_HEALTH_LIVE_SOURCE_DIAGNOSTIC',JSON.stringify(live));
