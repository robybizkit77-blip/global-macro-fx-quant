'use strict';
/* Date-aware research desk: no past-as-future macro events or fabricated FX surprises. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const root=path.resolve(__dirname,'../..');
const next='site/fx-quant-v2/next/';
const read=p=>fs.readFileSync(path.join(root,p),'utf8');
const json=p=>JSON.parse(read(p));
const sandbox={window:{},URL};
vm.runInNewContext(read(next+'morning-desk-v1.js'),sandbox,
 {filename:'morning-desk-v1.js',timeout:5000});
const morning=sandbox.window.FXQuantMorningDesk;
const calendar=json('live_data/sections/CALENDAR_OPERATIONAL_VIEW.json');
const date='2026-11-13';
const selected=[{base:'AUD',quote:'USD',key:'AUDUSD'},
 {base:'EUR',quote:'GBP',key:'EURGBP'}];
const events=morning.nextFxCatalysts(calendar,selected,date);
assert.equal(events.sourceAsOf,'2026-11-13');
assert.equal(events.today?.ccy,'USD','Official same-day PPI must not disappear from Home');
assert.equal(events.today?.title,'Producer Price Index');
assert.equal(events.today?.date,date);
assert.equal(events.next?.ccy,'CHF','Next future high-impact G8 event from official source');
assert.equal(events.next?.date,'2026-11-16');
assert.equal(events.next?.quality,'OFFICIAL_PROVISIONAL');
assert.equal(events.relevant?.ccy,'AUD','Next future catalyst affecting selected pair');
assert.equal(events.relevant?.date,'2026-11-19');
const text=morning.catalystReading(calendar,selected,date,x=>x);
assert(text.includes('era previsto oggi USD'),text);
assert(text.includes('esito non è confermato'),text);
assert(text.includes('prossimo evento G8 programmato è CHF'),text);
assert(text.includes('data provvisoria'));
assert(text.includes('catalizzatore diretto è AUD'));
assert(!text.includes('prossimo evento G8 programmato è GBP'));
assert(text.includes('consenso non disponibile'));
assert(!text.includes('sorpresa di +'));
// A genuinely future official macro event may be shown as next. A spoofed or
// copied item must not become a new catalyst.
const fake=structuredClone(calendar);
fake.events.unshift({...fake.events[0],date:'2026-11-13',
 title:'FALSO EVENTO DAL WEB',quality:'UNVERIFIED'});
assert(!morning.catalystReading(fake,selected,date,x=>x).includes('FALSO EVENTO'));
const stale=structuredClone(calendar);
stale.last_checked_at_utc='2026-10-01T00:00:00Z';
assert.equal(morning.nextFxCatalysts(stale,selected,date).sourceAsOf,null);
assert(morning.catalystReading(stale,selected,date,x=>x).includes('non aggiornato'));
const futureSource=structuredClone(calendar);
futureSource.last_checked_at_utc='2026-11-14T00:00:00Z';
assert.equal(morning.nextFxCatalysts(futureSource,selected,date).sourceAsOf,null);
const noRelevant=morning.nextFxCatalysts(calendar,[{base:'EUR',quote:'USD'}],date);
assert(noRelevant.next&&noRelevant.relevant,
 'Calendar can choose a relevant later central-bank event without inventing immediate releases');
const top={ccy:'USD',macroScore:0.65,policyScore:0.5,priceScore:0.1,
 rate:{quality:'PROXY'},partial:true};
const bottom={ccy:'EUR',macroScore:-0.6,policyScore:0,priceScore:-0.5,
 rate:{quality:'PROXY'},partial:true};
const lead=morning.currencyDriver(top,'top');
assert(lead.includes('momentum interno')&&lead.includes('governativo 2Y'));
assert(lead.includes('Copertura macro/tassi parziale'));
const lag=morning.currencyDriver(bottom,'bottom');
assert(lag.includes('momentum interno')&&lag.includes('debolezza FX'));
const empty=morning.currencyDriver({ccy:'GBP',macroScore:0,policyScore:0,
 priceScore:0,partial:false},'top');
assert(empty.includes('nessuna singola componente'));
const feed=json(next+'morning-desk-current.json');
const estEngine=require(path.join(root,next,'macro-strength-estimated-v1.js'));
const ranking=require(path.join(root,next,'pair-rankings.js'));
const estimated=estEngine.evaluate({
 observed:json('site/control-room-preview/macro-v3-current-evidence.json'),
 prices:json('live_data/sections/ECB_G8_PRICE_HISTORY.json'),
 ois:json('site/fx-quant-v2/ois-pricing-snapshot.json'),
 rates:json('live_data/sections/NATIVE_RATES_DATA.json'),
 model:json('live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json'),
 now:date,rankingFn:ranking.currencyRanking
});
assert.equal(estimated.status,'STIMA_OPERATIVA_NON_VALIDATA',estimated.reason);
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({
 '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
})[c]);
const args={feed,plot:()=>'<div class="chart"></div>',esc,date:x=>x,dayNow:()=>date};
const currentResearch={estimated,rates:json('live_data/sections/NATIVE_RATES_DATA.json'),calendar,selectResearchPairs:ranking.selectResearchPairs,
 watchForPair:x=>ranking.pairDecisionWatch(x,null)};
const article=morning.build(args);
const updated=morning.build({...args,currentResearch});
assert(updated.includes('morning-fx-pulse-catalyst'));
assert(updated.includes('Prossime verifiche macro.'));
assert(updated.includes('nel ranking combinato G8')===false);
assert(updated.indexOf('data-fx-pulse="current"')>updated.indexOf('class="morning-lead"'),
 'Estimated pair analysis must not precede the editorial desk');
const originalArchive=updated.replace(/<details class="morning-secondary-research[\s\S]*?<\/details>/,'');
assert(originalArchive.includes('Edizione originale non riscritta'),
 'Calendar reconciliation must preserve the original dated editorial');
assert(updated.includes('data-home-calendar-reconciled="true"'),
 'A verified official issuer event omitted by the frozen morning must override the first read');
const headline=updated.match(/<header class="morning-lead">[\s\S]*?<\/header>/)?.[0]||'';
assert(headline.includes('PPI USA')&&headline.includes('14:30'),headline);
assert(!headline.includes('Nessun dato domina'), 'An outdated calendar headline cannot remain the current top story');
const fxFirst=updated.match(/<section class="morning-first-read"[\s\S]*?<\/section>/)?.[0]||'';
assert(fxFirst.includes('Nella stima quantitativa G8 USD occupa la posizione'),
 'Editorial must use the same active G8 estimate as currency/pair pages');
const usdWeek=currentResearch.rates.USD.weekly2_validation;
const eurWeek=currentResearch.rates.EUR.weekly2_validation;
if(usdWeek.start_date===eurWeek.start_date&&usdWeek.end_date===eurWeek.end_date){
 assert(fxFirst.includes('Tra '+usdWeek.start_date+' e '+usdWeek.end_date) &&
  fxFirst.includes('differenziale settimanale'),
  'Same-window verified Treasury 2Y vs Eurozone 2Y proxy must reach the first read');
}
assert(fxFirst.includes('EUR/USD:') && fxFirst.includes('USD/JPY:'),
 'Two FX pairs must carry a concrete estimated price/direction interpretation');
assert(!/non abbiamo|non possiamo|senza variazioni/i.test(fxFirst),
 'Main FX narrative cannot fall back to defensive missing-data prose');

assert(updated.indexOf('class="morning-lead"')<updated.indexOf('morning-secondary-research'),
 'Research estimates must be collapsed after the first read');
assert(updated.includes('class="morning-supporting morning-deep-reading"'),
 'Charts and scenarios remain available without crowding the first screen');
const noCalendar=morning.build({...args,currentResearch:{...currentResearch,calendar:null}});
assert(!noCalendar.includes('data-home-calendar-reconciled="true"'),
 'A missing official feed must not invent a same-day catalyst');
assert(!article.includes('data-home-calendar-reconciled="true"'),
 'The archived original remains visibly distinct from a dated calendar correction');
const app=read(next+'app.js');
assert(app.includes("estimated,rates:get('rates'),calendar:get('calendar')"));
const index=read(next+'index.html');
assert(index.includes('./morning-desk-v1.js?v=7'));
assert(index.includes('./morning-desk-v1.css?v=5'));
assert(index.includes('./app.js?v=18.44-estimates'));
const css=read(next+'morning-desk-v1.css');
assert(css.includes('.morning-fx-pulse-catalyst'));
console.log('NEXT_HOME_FX_CATALYST_V1_PASS: G8 economic drivers, past-vs-future official calendar, no fabricated surprises and immutable frozen briefing');
