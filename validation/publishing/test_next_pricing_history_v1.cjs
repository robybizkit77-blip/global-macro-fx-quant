'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const file=p=>fs.readFileSync(path.join(root,p),'utf8');
const source=file('site/fx-quant-v2/next/rates-pricing-history-v1.js');
new vm.Script(source,{filename:'rates-pricing-history-v1.js'});
const {country,connect,relative,historicalMoves,render}=require('../../site/fx-quant-v2/next/rates-pricing-history-v1.js');
const data=JSON.parse(file('site/fx-quant-v2/next/rates-pricing-history-v1.json'));
assert.equal(data.schema,'GMFQ_NEXT_G8_PRICING_HISTORY_V1');
assert.equal(data.official_ois_created,false);
assert.equal(data.date_gaps_interpolated,false);
assert.equal(data.eligible_for_fx_engine,false);
assert.equal(data.eligible_for_backtests_as_official_ois,false);
const G8=['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'];
assert.deepEqual(Object.keys(data.currencies),G8);
for(const c of G8){
 const row=country(data,c,30);
 assert(row&&row.tenors['3m']&&row.tenors['6m']&&row.tenors['12m']);
 assert(row.observedDates>=1,c+' must have an actual archived observation');
 for(const t of ['3m','6m','12m']){
  for(const p of row.tenors[t]){
   assert(p.date<=data.as_of,c+' no future dates');
   assert(typeof p.rate==='number'&&Number.isFinite(p.rate));
   if(['USD','EUR','CHF'].includes(c)){
    assert(p.contract&&p.source_class==='SECONDARY_SAME_CONTRACT');
   }
  }
 }
}
assert(country(data,'GBP',30).observedDates>=12);
assert(country(data,'USD',30).observedDates>=10);
assert(country(data,'EUR',30).observedDates>=10);
assert(country(data,'CHF',30).observedDates>=10);
assert(country(data,'NZD',30).observedDates>=4);
assert(country(data,'NZD',30).derivedReferences>=0);
const quoteA={date:'2026-11-11',rate:3.5,contract:'AAA',source_class:'SECONDARY_SAME_CONTRACT',derived:false};
const quoteB={...quoteA,date:'2026-11-12',contract:'BBB'};
assert(!connect(quoteA,quoteB),'Different listed contracts cannot be joined');
assert(connect(quoteA,{...quoteB,contract:'AAA'}),'Same listed contract next day can connect');
assert(!connect(quoteA,{...quoteB,date:'2026-11-20',contract:'AAA'}),'Missing source dates break lines');
assert(!connect(quoteA,{...quoteB,date:'2026-11-13',contract:'AAA'}),'One missing weekday breaks lines');
const friday={...quoteA,date:'2026-11-13'},monday={...quoteA,date:'2026-11-16'};
assert(connect(friday,monday),'Adjacent weekdays across weekend remain connected');
assert(!connect(friday,{...monday,date:'2026-11-17'}),'Missing Monday breaks line');
assert(!connect(friday,{...monday,date:'2026-11-14'}),'Weekend quote cannot create a weekday interval');
assert.equal(historicalMoves({tenors:{'6m':[quoteA,{...quoteA,date:'2026-11-13',rate:3.7},monday]}}).length,1,'Do not render a multi-weekday change as an adjacent observation');
assert(connect({date:'2026-11-11',contract:'BBB',source_class:'BANK_BILL_PROXY_DELTA_REFERENCE',derived:true},
 {...quoteB,source_class:'BANK_BILL_PROXY'}),'Declared NZD 1D reference can be dotted');
const eur=country(data,'EUR',30),gbp=country(data,'GBP',30);
const relativePoints=relative(eur,gbp);
assert(relativePoints.length>=5,'6M EUR/GBP official vs futures common-date comparison');
assert(relativePoints.every(x=>x.source_class==='RELATIVE_SAME_DATE'));
const gbpDays=new Set(gbp.tenors['6m'].map(x=>x.date));
assert(relativePoints.every(x=>gbpDays.has(x.date)));
const noComp=relative(country(data,'NZD',14),country(data,'JPY',14));
assert(noComp.every(x=>x.date<=data.as_of));
for(const c of G8){
 const html=render({history:data,ccy:c,other:'USD',window:30});
 assert(html.includes('id="rates-pricing-history"'));
 assert(html.includes('data-history-currency="'+c+'"'));
 assert(html.includes('data-rs-history-window="14"')&&
        html.includes('data-rs-history-window="30"')&&
        html.includes('data-rs-history-window="60"'));
 assert((html.match(/class="ois-history-currency /g)||[]).length===8);
 assert(html.includes('data-rate-ccy="NZD"'));
 assert(html.includes('data-rate-ccy="CAD"'));
 assert(html.includes('Lo storico disponibile')||html.includes('ois-history-moves'));
 assert(html.includes('non uno spread OIS negoziabile')||html.includes('non uno spread OIS negoziabile'));
 assert(html.includes('<svg'),'At least one dated chart expected');
}
const gbpChart=render({history:data,ccy:'GBP',other:'EUR',window:30});
assert(gbpChart.includes('OIS BoE'),'Official OIS legend must survive');
const usdChart=render({history:data,ccy:'USD',other:'EUR',window:30});
assert(usdChart.includes('NON sono OIS')||usdChart.includes('Non sono OIS'),
 'Secondary futures must never become official OIS');
const nzdChart=render({history:data,ccy:'NZD',other:'CAD',window:30});
assert(nzdChart.includes('riferimenti 1D/1W ricostruiti'),'NZD sparse proxy must disclose reconstructed levels');
const fake=structuredClone(data);
fake.currencies.GBP.source='<img src=x onerror=alert(1)>';
const safe=render({history:fake,ccy:'GBP',other:'EUR',window:30});
assert(!safe.includes('<img')&&safe.includes('&lt;img'));
assert(!render({history:{...data,official_ois_created:true},ccy:'GBP'}).includes('<svg'),
 'Official OIS promotion breaks data-readiness gate');
const page=file('site/fx-quant-v2/next/index.html');
assert(page.indexOf('rates-pricing-history-v1.js?v=8')<page.indexOf('rates-studio.js?v='));
assert.match(page,/rates-studio\.css\?v=\d+/);
const app=file('site/fx-quant-v2/next/app.js');
assert(app.includes("oisHistory:'./rates-pricing-history-v1.json'"));
assert(app.includes("data-rs-history-window"));
const rates=file('site/fx-quant-v2/next/rates-studio.js');
assert(rates.includes('FXQuantPricingHistory?.render'));
console.log('NEXT_G8_PRICING_HISTORY_V1_PASS: 8x3 dated tenors, archive conflicts, rollover gaps, derived NZD, common-date relative 6M');

const {weekdayReference,horizonMoves}=require('../../site/fx-quant-v2/next/rates-pricing-history-v1.js');
assert.equal(weekdayReference('2026-11-23',1),'2026-11-20');
assert.equal(weekdayReference('2026-11-23',5),'2026-11-16');
assert.equal(weekdayReference('2026-11-23',20),'2026-10-26');
const mk=(date,rate,contract='A',derived=false,source_class='SECONDARY_SAME_CONTRACT')=>({date,rate,contract,derived,source_class});
const sample={kind:'FUTURES SECONDARI',tenors:{'6m':[mk('2026-10-26',3.2,'B'),mk('2026-11-16',3.4),mk('2026-11-20',3.5),mk('2026-11-23',3.55)]}};
assert.deepEqual(horizonMoves(sample).map(m=>m.bp),[5,15,null]);
const roll=structuredClone(sample);roll.tenors['6m'][2].contract='B';
assert.deepEqual(horizonMoves(roll).map(m=>m.bp),[null,null,null]);
const gap=structuredClone(sample);gap.tenors['6m'].splice(2,1);
assert.equal(horizonMoves(gap)[0].bp,null);
const nzdFixture={kind:'PROXY FUTURES',tenors:{'6m':[mk('2026-11-16',3.82,'Jun',true,'BANK_BILL_PROXY_DELTA_REFERENCE'),mk('2026-11-20',3.72,'Jun',true,'BANK_BILL_PROXY_DELTA_REFERENCE'),mk('2026-11-23',3.7,'Jun',false,'BANK_BILL_PROXY')]}};
assert.deepEqual(horizonMoves(nzdFixture).map(m=>m.bp),[-2,-12,null]);
assert(horizonMoves(nzdFixture)[0].derived);
const future={kind:'FUTURES',tenors:{'6m':[mk('2026-11-20',3.5,null,false,'OFFICIAL_TENOR'),mk('2026-11-23',3.55,null,false,'OFFICIAL_TENOR')]}};
assert.match(horizonMoves(future)[0].basis,/rollover possibile/);
for(const c of G8){
 const h=render({history:data,ccy:c,window:14});
 assert(h.includes('data-pricing-horizon-matrix'));
 assert(h.includes('1 / 5 / 20 giorni feriali'));
 for(const k of G8)assert.equal((h.match(new RegExp('data-rate-ccy="'+k+'"','g'))||[]).length,1,'unique historical currency control '+k);
}
assert.equal(horizonMoves(null).filter(x=>x.bp!==null).length,0);
console.log('NEXT_G8_PRICING_HORIZON_MATRIX_PASS');

assert(!connect({...quoteA,source_class:'BANK_BILL_PROXY'},{...quoteB,source_class:'BANK_BILL_PROXY'}),'NZD rollover must break chart');

const crossTenor={kind:'FUTURES SECONDARI',tenors:{
 '6m':[mk('2026-10-26',.1,'OLD'),mk('2026-11-23',.35,'CURRENT')],
 '12m':[mk('2026-10-26',.275,'CURRENT')]}};
const recovered=horizonMoves(crossTenor)[2];
assert.equal(recovered.bp,7.5);
assert.match(recovered.basis,/prima 12M \(non 6M costante\)/);
const conflicted=structuredClone(crossTenor);
conflicted.tenors['3m']=[mk('2026-10-26',.29,'CURRENT')];
assert.equal(horizonMoves(conflicted)[2].bp,null,'Conflicting cross-tenor prices are not accepted');
const derivedCross=structuredClone(crossTenor);
derivedCross.tenors['12m'][0].derived=true;
assert.equal(horizonMoves(derivedCross)[2].bp,null);
assert.equal(horizonMoves({...crossTenor,kind:'FUTURES'})[2].bp,null);
console.log('NEXT_FIXED_CONTRACT_CROSS_TENOR_MOMENTUM_PASS');

const approx20={kind:'FUTURES',tenors:{'6m':[
 mk('2026-10-23',4.845,null,false,'OFFICIAL_TENOR'),
 mk('2026-11-23',4.81,null,false,'OFFICIAL_TENOR')]}};
const approxMove=horizonMoves(approx20)[2];
assert.equal(approxMove.bp,-3.5);
assert.equal(approxMove.from,'2026-10-23');
assert.equal(approxMove.referenceTarget,'2026-10-26');
assert.equal(approxMove.approximateWindow,true);
assert.match(approxMove.basis,/21 giorni feriali/);
assert.equal(horizonMoves(approx20)[1].bp,null);
assert.equal(horizonMoves(approx20)[0].bp,null);
const tooOld=structuredClone(approx20);
tooOld.tenors['6m'][0].date='2026-10-22';
assert.equal(horizonMoves(tooOld)[2].bp,null);
const exact20=structuredClone(approx20);
exact20.tenors['6m'].splice(1,0,mk('2026-10-26',4.85,null,false,'OFFICIAL_TENOR'));
assert.equal(horizonMoves(exact20)[2].bp,-4);
assert(!horizonMoves(exact20)[2].approximateWindow);
const differentContract=structuredClone(approx20);
differentContract.tenors['6m'][0].contract='OLD';
differentContract.tenors['6m'][1].contract='NEW';
assert.equal(horizonMoves(differentContract)[2].bp,null);
assert.equal(horizonMoves({...approx20,kind:'FUTURES SECONDARI'})[2].bp,null);
console.log('NEXT_20D_OBSERVED_REFERENCE_APPROXIMATION_PASS');

const nzdMonthly={kind:'PROXY FUTURES',tenors:{'6m':[
 {...mk('2026-10-26',3.8,'Mar 2027',false,'BANK_BILL_PROXY'),expiration:'2027-03-10'},
 {...mk('2026-11-23',3.7,'Jun 2027',false,'BANK_BILL_PROXY'),expiration:'2027-06-16'}]},
 fixedContract20d:{from:'2026-10-26',to:'2026-11-23',contract:'Jun 2027',expiration:'2027-06-16',
 reference_rate:4.06,current_rate:3.7,change_bp:-36,basis:'EXACT_LISTED_ASX_BANK_BILL_CONTRACT_NOT_OIS',
 source_sha256:'a'.repeat(64),source_url:'https://www.asx.com.au/data/futures/reports/EODWebMarketSummary261026ZFT.htm'}};
assert.equal(horizonMoves(nzdMonthly)[2].bp,-36);
const staleMonthly=structuredClone(nzdMonthly);staleMonthly.fixedContract20d.to='2026-11-20';
assert.equal(horizonMoves(staleMonthly)[2].bp,null);
const wrongExpiry=structuredClone(nzdMonthly);wrongExpiry.fixedContract20d.expiration='2027-03-10';
assert.equal(horizonMoves(wrongExpiry)[2].bp,null);
const wrongDelta=structuredClone(nzdMonthly);wrongDelta.fixedContract20d.change_bp=-99;
assert.equal(horizonMoves(wrongDelta)[2].bp,null);
console.log('NEXT_NZD_ASX_MONTHLY_REFERENCE_PASS');

const usdRoll={ccy:'USD',kind:'FUTURES SECONDARI',tenors:{'6m':[
 mk('2026-10-27',4.38,'APR'),mk('2026-11-17',4.47,'APR'),
 mk('2026-11-19',4.58,'MAY'),mk('2026-11-24',4.475,'MAY')]},
 estimatedRollMomentum:{'20':{from:'2026-10-27',to:'2026-11-24',roll_date:'2026-11-18',
 old_contract:'APR',new_contract:'MAY',start_rate:4.38,old_roll_rate:4.495,new_roll_rate:4.55,
 end_rate:4.475,old_move_bp:11.5,new_move_bp:-7.5,change_bp:4,capture_gap_hours:4.8,
 basis:'ESTIMATED_SINGLE_ROLL_SAME_SOURCE_NOT_SYNCHRONIZED',official_ois_created:false,fx_engine_effect:'NONE'}}};
assert.equal(horizonMoves(usdRoll)[2].bp,4);
assert(horizonMoves(usdRoll)[2].derived);
assert.match(horizonMoves(usdRoll)[2].basis,/STIMA rollover/);
const invalidRoll=structuredClone(usdRoll);invalidRoll.estimatedRollMomentum['20'].change_bp=99;
assert.equal(horizonMoves(invalidRoll)[2].bp,null);
assert.equal(horizonMoves({...usdRoll,ccy:'CHF'})[2].bp,null);
console.log('NEXT_USD_ROLL_ESTIMATE_PASS');
