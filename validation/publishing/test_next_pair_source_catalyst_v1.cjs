'use strict';
/* Relative FX research: sources are not fungible OIS spreads, and calendar
 * events are NOT verified macro surprises or trading triggers. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const next='site/fx-quant-v2/next/';
const read=p=>fs.readFileSync(path.join(root,p),'utf8');
const json=p=>JSON.parse(read(p));
const rank=require(path.join(root,next,'pair-rankings.js'));
const calendar=json('live_data/sections/CALENDAR_OPERATIONAL_VIEW.json');
const on='2026-11-12';
const mk=(key,favored=null)=>({key,base:key.slice(0,3),quote:key.slice(3),
 favored,macroState:'FAVOREVOLE',policyState:'FAVOREVOLE'});
const rates={
 USD:{rate:{quality:'PROXY',kind:'GOV_2Y_PROXY',asof:'2026-11-10'}},
 EUR:{rate:{quality:'PROXY',kind:'GOV_2Y_PROXY',asof:'2026-11-11'}},
 GBP:{rate:{quality:'UFFICIALE',kind:'OIS',asof:'2026-11-11'}},
 JPY:{rate:{quality:'UFFICIALE',kind:'FUTURES',asof:'2026-11-12'}},
 CAD:{rate:{quality:'UFFICIALE',kind:'FUTURES',asof:'2026-11-11'}},
 AUD:{rate:{quality:'UFFICIALE',kind:'FUTURES',asof:'2026-11-11'}},
 NZD:{rate:{quality:'ASSENTE',kind:'MANCANTE',asof:null}},
 CHF:{rate:{quality:'ASSENTE',kind:'MANCANTE',asof:null}}
};
assert.equal(rank.pairRateEvidence(mk('EURUSD'),rates).quality,'PROXY_2Y');
assert.match(rank.pairRateEvidence(mk('EURUSD'),rates).description,/2Y governativo/);
assert.equal(rank.pairRateEvidence(mk('GBPJPY'),rates).quality,'6M_NON_OMOGENEO');
assert.match(rank.pairRateEvidence(mk('GBPJPY'),rates).description,/strumenti o date differiscono/);
assert.equal(rank.pairRateEvidence(mk('AUDCAD'),rates).quality,'6M_ALLINEATO');
assert.equal(rank.pairRateEvidence(mk('NZDCHF'),rates).quality,'INCOMPLETO');
assert.equal(rank.pairRateEvidence(mk('NZDCHF'),null).quality,'INCOMPLETO');
const uk=rank.pairCatalyst(mk('GBPUSD','GBP'),calendar,on,x=>x);
assert(uk&&uk.ccy==='GBP'&&uk.status==='ESITO_NON_VERIFICATO',JSON.stringify(uk));
assert(uk.text.includes('era previsto oggi'));
assert(uk.text.includes('non ne certifica il risultato'));
assert(uk.text.includes('consenso e reazione relativa GBP/USD'));
assert(!uk.text.includes('migliora del')&&!uk.text.includes('ha sorpreso'));
const ch=rank.pairCatalyst(mk('CHFJPY'),calendar,on,x=>x);
assert(ch&&ch.ccy==='CHF'&&ch.date==='2026-11-16');
assert(ch.status==='FUTURO');
assert(ch.text.includes('data provvisoria'));
assert(ch.text.includes('aspettative su CHF rispetto a JPY'));
assert(ch.text.includes('percorso dei tassi già prezzato'));
const aud=rank.pairCatalyst(mk('AUDCAD'),calendar,on,x=>x);
assert(aud&&aud.ccy==='AUD'&&aud.date==='2026-11-19');
const eur=rank.pairCatalyst(mk('EURUSD'),calendar,on,x=>x);
assert(eur&&eur.ccy==='USD'&&eur.date==='2026-12-09');
assert(eur.text.includes('Fed'));
const jpy=rank.pairCatalyst(mk('USDJPY'),calendar,on,x=>x);
assert(jpy&&jpy.ccy==='JPY'&&jpy.date==='2026-11-20');
const old=structuredClone(calendar);
old.last_checked_at_utc='2026-11-01T00:00:00Z';
assert.equal(rank.pairCatalyst(mk('GBPUSD'),old,on),null);
const future=structuredClone(calendar);
future.last_checked_at_utc='2026-11-13T00:00:00Z';
assert.equal(rank.pairCatalyst(mk('GBPUSD'),future,on),null);
const fake=structuredClone(calendar);
fake.events.unshift({...fake.events[0],date:'2026-11-13',
 title:'FAKE SURPRISE',quality:'UNVERIFIED'});
assert(!rank.pairCatalyst(mk('GBPUSD'),fake,on).text.includes('FAKE SURPRISE'));
const spoof=structuredClone(calendar);
spoof.events=[{...calendar.events[0],date:'2026-11-13',ccy:'CAD',
 title:'NOT A GBPUSD EVENT'}];
assert.equal(rank.pairCatalyst(mk('GBPUSD'),spoof,on),null);
assert.equal(rank.pairCatalyst({key:'GBPUSD',base:'EUR',quote:'USD'},calendar,on),null);
assert.equal(rank.pairCatalyst(mk('GBPUSD'),calendar,'garbage'),null);
const engine=require(path.join(root,next,'macro-strength-estimated-v1.js'));
const observed=json('site/control-room-preview/macro-v3-current-evidence.json');
const est=engine.evaluate({
 observed,prices:json('live_data/sections/ECB_G8_PRICE_HISTORY.json'),
 ois:json('site/fx-quant-v2/ois-pricing-snapshot.json'),
 rates:json('live_data/sections/NATIVE_RATES_DATA.json'),
 model:json('live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json'),
 now:on,rankingFn:rank.currencyRanking
});
assert.equal(est.status,'STIMA_OPERATIVA_NON_VALIDATA',est.reason);
assert.equal(est.pairs.length,28);
assert.equal(est.currencies.length,8);
assert.equal(rank.pairRateEvidence(mk('EURUSD'),est.by).quality,'PROXY_2Y');
assert.equal(rank.pairRateEvidence(mk('GBPJPY'),est.by).quality,'6M_NON_OMOGENEO');
const html=rank.render({
 get:key=>key==='estimatedMacro'?est:null,
 FLAGS:{USD:'USD',EUR:'EUR',GBP:'GBP',JPY:'JPY',CHF:'CHF',AUD:'AUD',NZD:'NZD',CAD:'CAD'},
 state:{pair:'GBPUSD',pairDetailOpen:false},
 esc:x=>String(x),date:x=>x,sign:x=>String(x)
});
assert(html.includes('2Y proxy'),'Source limitations must be shown in first-read');
assert(html.includes('fonti o date differiscono')||
 html.includes('date o strumenti diversi'),
 'Differences between 6M instruments/dates cannot be sold as OIS spread');
const shortlist=rank.selectResearchPairs(est.pairs);
assert.equal((html.match(/class="fx-rank-pair /g)||[]).length,28+shortlist.length);
const app=read(next+'app.js');
const start=app.indexOf('function pairs(){'),end=app.indexOf('\nfunction macro(){',start);
assert(start>=0&&end>start);
const part=app.slice(start,end);
assert(part.includes("pairRateEvidence?.(activePair,estimate?.by)"));
assert(part.includes('pairCatalyst?.('));
assert(part.includes("activePair,get('calendar'),dayNow(),date"));
assert(part.includes('data-pair-catalyst="official"'));
assert(part.includes('esc(catalyst.text)'), 'Calendar title must be escaped for HTML');
assert(part.includes('Qualità tassi.'));
assert(part.includes('ThesisStrength')===false,'Do not create a new numerical signal');
const index=read(next+'index.html');
assert(index.includes('./pair-rankings.js?v=7'));
assert(index.includes('./app.js?v=18.43-pair-catalyst1'));
console.log('NEXT_PAIR_SOURCE_CATALYST_V1_PASS: 28 pairs, source-qualified rates and official dated catalyst, no inferred release or trade');
