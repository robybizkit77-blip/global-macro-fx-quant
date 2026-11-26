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
const root=path.resolve(__dirname,'../..');
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
 calendar:read('live_data/sections/CALENDAR_OPERATIONAL_VIEW.json')},
 new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Rome',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date()));
assert.equal(live.rows.length,10);
console.log('DATA_HEALTH_LIVE_SOURCE_DIAGNOSTIC',JSON.stringify(live));
