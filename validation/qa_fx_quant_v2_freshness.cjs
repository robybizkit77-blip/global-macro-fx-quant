'use strict';
// Read-only freshness audit for the FX Quant V2 research website.
// A successful process means the audit ran, NOT that every market series is fresh.
const fs=require('fs'),path=require('path');
const dir=path.resolve(__dirname,'../live_data/sections');
const site=path.resolve(__dirname,'../site/fx-quant-v2');
const today=process.env.FXV2_AS_OF||new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Rome',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
if(!/^\d{4}-\d{2}-\d{2}$/.test(today))throw Error('Invalid audit as-of '+today);
const result={schema:'GMFQ_FXV2_FRESHNESS_AUDIT_V1',as_of_rome:today,generated_at_utc:new Date().toISOString(),
  status:'INCOMPLETE',hard_errors:[],findings:[],checks:[],summary:{}};
const read=n=>JSON.parse(fs.readFileSync(path.join(dir,n+'.json'),'utf8'));
const file=n=>fs.readFileSync(path.join(site,n),'utf8');
const iso=d=>typeof d==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(d)?d:null;
const days=d=>iso(d)?Math.round((Date.parse(today+'T12:00:00Z')-Date.parse(d+'T12:00:00Z'))/86400000):null;
const check=(area,item,as_of,limit,quality,kind='series')=>{
 const age=days(as_of),valid=age!==null&&age>=0;
 const state=!valid?'INVALID':age>limit?'DELAYED':'ON_CADENCE';
 const row={area,item,kind,as_of,calendar_age_days:age,allowed_calendar_days:limit,quality,state};
 result.checks.push(row);
 if(!valid)result.hard_errors.push({area,item,reason:'Invalid/future source date: '+as_of});
 else if(state==='DELAYED')result.findings.push({severity:'GAP',area,item,detail:'As-of '+as_of+', '+age+' calendar days (monitor threshold '+limit+'). Source quality: '+quality});
 return row;
};
const gap=(area,item,detail)=>result.findings.push({severity:'GAP',area,item,detail});
const note=(area,item,detail)=>result.findings.push({severity:'REVIEW',area,item,detail});
const requireValid=(flag,msg)=>{if(!flag)result.hard_errors.push({reason:msg})};

const rates=read('NATIVE_RATES_DATA');
const ccy=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
const maxRateAge={USD:4,EUR:4,GBP:4,JPY:4,CHF:14,CAD:4,AUD:10,NZD:7};
for(const c of ccy){
 const x=rates[c]||{};
 requireValid(Number.isFinite(x['2Y'])&&Number.isFinite(x['10Y']),'Missing numeric canonical government 2Y/10Y for '+c);
 check('governments',c,x.date,maxRateAge[c],x.quality||'UNSPECIFIED');
}
const ec=read('ECB_G8_PRICE_HISTORY');
check('prices','ECB G8 matched-date fixing',ec.last_as_of,4,ec.source||'ECB');
requireValid(ec.pair_count===28&&Array.isArray(ec.rows)&&ec.rows.length>250,'Insufficient ECB G8/28 pair history');
const pair=read('PAIR_SETUP_OPERATIONAL_VIEW');
check('pairs','28-cross market price',pair.price_asof,4,'ECB FX matched-date');
requireValid(pair.pair_count===28&&Object.keys(pair.pairs||{}).length===28,'FX Pair Setup coverage is not 28');
if(pair.macro_baseline_asof&&days(pair.macro_baseline_asof)>20)
 gap('pairs','Baseline macro del motore', 'La baseline del motore usa '+pair.macro_baseline_asof+
  '; non confonderla con le serie Macro V3 aggiornate sul sito.');
const observedMacro=JSON.parse(fs.readFileSync(path.join(site,'../control-room-preview/macro-v3-current-evidence.json'),'utf8'));
requireValid(observedMacro.schema==='GMFQ_MACRO_V3_G8_28PAIR_PUBLIC_OBSERVED_CONTEXT_V1'&&
 observedMacro.status==='OBSERVED_ECONOMIC_CONTEXT_NOT_FX_SIGNAL'&&
 observedMacro.summary?.currencies===8&&
 observedMacro.summary?.economic_dimensions===24&&
 observedMacro.summary?.pairs===28&&
 observedMacro.summary?.pair_trade_signals_generated===0&&
 observedMacro.safe_to_recompute_structural_pair_theses===false&&
 observedMacro.safe_to_republish_D===false&&
 observedMacro.eligible_for_trading_or_forward_backtest===false&&
 observedMacro.canonical_D_macro_baseline_as_of===pair.macro_baseline_asof&&
 Object.keys(observedMacro.pair_context||{}).length===28,
 'Macro V3 observed context not fully isolated from canonical 28 pair setup');
check('macro_observed_research','G8 / 24 osservazioni / 28 confronti V3',
 observedMacro.generated_europe_rome_day,10,
 'OBSERVED_REVISED_NOT_POINT_IN_TIME_NO_FX_SIGNALS');
note('pairs','Two independent macro vintages',
 'PAIR_SETUP baseline '+pair.macro_baseline_asof+
 ' è rimasta canonica; Macro V3 al '+observedMacro.generated_europe_rome_day+
 ' mostra 24 osservazioni, NON un nuovo score o segnale FX.');
const pairsHtml=file('coppie.html');
requireValid(pairsHtml.includes('assets/pair-macro-observed-context-v1.js')&&
 pairsHtml.includes('macro-v3-current-evidence.json')&&
 pairsHtml.includes('id="macroV3Context"'),
 'FXV2 pairs must display G8 observed Macro V3 separately from legacy pair thesis');
const cot=read('V250_COT_CHART_DATA');
for(const c of ccy){const s=cot[c]||{};
  requireValid(Array.isArray(s.dates)&&s.dates.length>=52,'COT history incomplete '+c);
  if(s.dates?.length)check('positioning',c+' CFTC weekly',s.dates.at(-1),11,'CFTC weekly, Tuesday positions','weekly');
}
const macro=read('MACRO_SERIES');
let macroCount=0;
for(const c of ccy){const count=macro[c]?.length||0;macroCount+=count;requireValid(count>=10,'Missing canonical macro series '+c);}
requireValid(macroCount>=200,'Missing expected Macro G8 full research coverage');
note('macro','Serie Macro',macroCount+' indicatori: le osservazioni hanno frequenze e periodi eterogenei. Non considerarli dati giornalieri.');
const cb=read('NATIVE_CB_DATA');
for(const c of ccy){
 const x=cb[c]||{};
 requireValid(Boolean(iso(x.last_date)),'Invalid CB last decision '+c);
 if(iso(x.next_meeting)&&x.next_meeting<today&&x.last_date<x.next_meeting){
  if(c==='AUD'){
   const rba=JSON.parse(file('rba-decision-2026-11-03-official.json'));
   const vetted=rba.schema==='GMFQ_FXV2_RBA_OFFICIAL_DECISION_OVERLAY_V1'&&
    rba.currency==='AUD'&&
    rba.published_status==='OFFICIAL_RBA_RELEASE_VERIFIED__V2_INFORMATIONAL_ONLY'&&
    rba.source_url==='https://www.rba.gov.au/media-releases/2026/mr-26-30.html'&&
    iso(rba.last_date)&&rba.last_date===x.next_meeting&&rba.last_date<=today&&
    Number.isFinite(rba.rate)&&Number.isFinite(rba.rate_change_bp)&&
    rba.rate_change_bp===25&&rba.eligible_for_core_signals===false&&
    rba.eligible_for_pair_engine===false&&rba.eligible_for_backtests===false;
   if(vetted){
    check('central_banks_v2','AUD RBA official decision (V2-only)',rba.last_date,35,'OFFICIAL_RBA_RELEASE_V2_ONLY');
    note('central_banks','AUD Core non allineato, V2 aggiornata',
     'Feed Core NATIVE_CB_DATA resta al '+x.last_date+', mentre la V2 mostra la decisione RBA ufficiale '+rba.last_date+' tramite overlay separato. Il prossimo meeting '+rba.next_meeting+' va verificato da una nuova fonte, non considerato aggiornato automaticamente.');
   }else gap('central_banks','AUD nuova decisione non riconciliata','Overlay V2 della riunione RBA non valido o scaduto; Core '+x.last_date);
  }else{
   gap('central_banks',c+' decisione non riconciliata',
       'Ultima decisione '+x.last_date+'; riunione '+x.next_meeting+' già trascorsa senza successivo esito nel feed.');
  }
 }
}
const ois=read('OIS_OPERATIONAL_VIEW');
let certified=0;
for(const c of ccy){
 const x=ois.currencies?.[c]||{};
 if(x.operational_status==='GREEN_OFFICIAL'&&x.quality==='OFFICIAL_CERTIFIED'){
  certified++;
  check('market_pricing',c+' certified '+(x.source||'policy futures / OIS'),x.as_of,5,'OFFICIAL_CERTIFIED');
 }else{
  const ctx=x.operational_status||'MISSING';
  gap('market_pricing',c+' curva pricing',
      'Non certificata come curva ufficiale operativa: '+ctx+
      ' (fonte '+(x.quality||'missing')+', osservazione '+(x.as_of||'none')+'). Utilizzare proxy separati e datati, non chiamarli OIS.');
 }
}
const news=read('NEWS_PULSE_OPERATIONAL'),calendar=read('CALENDAR_OPERATIONAL_VIEW');
check('calendar','refresh operativo',String(calendar.last_checked_at_utc||'').slice(0,10),3,'OPERATIONAL');
check('news','last check',String(news.last_checked_at_utc||'').slice(0,10),3,'OPERATIONAL');
const dxy=read('DXY_SYNTHETIC_ECB');
check('prices','DXY synthetic (not ICE)',dxy.as_of,4,'ESTIMATED_INFORMATIONAL');
const residual=read('ESTIMATED_RESIDUAL_GAPS');
for(const name of ['GOLD.market_proxy','WTI.market_proxy','BRENT.market_proxy']){
 const x=residual.lanes?.[name]||{};
 requireValid(Number.isFinite(x.value),'Missing secondary futures price '+name);
 check('cross_asset',name,x.proxy_as_of,4,'SECONDARY_FUTURES_INFORMATIONAL');
}
const cross=JSON.parse(file('design-studio-cross-asset-v1-data.json'));
const crossLive=JSON.parse(file('cross-asset-live-data.json'));
requireValid(crossLive.schema==='GMFQ_FXV2_CROSS_ASSET_SOURCE_OVERLAY_V1','Unexpected V2 Cross-Asset source-feed schema');
const sourceIds={SP500:'S&P 500',NASDAQCOM:'Nasdaq Composite',IG_OAS:'IG OAS',HY_OAS:'HY OAS',VIX:'VIX Cboe'};
const stored=crossLive.streams||{};
for(const [id,label] of Object.entries(sourceIds)){
 const s=stored[id];
 if(s&&iso(s.date)&&Number.isFinite(s.value)&&s.value>0&&s.quality==='PUBLISHED_SOURCE_RESEARCH_ONLY'){
  check('cross_asset_live',label,s.date,s.max_source_age_days||7,s.publisher||'FRED/Cboe');
 }else{
  gap('cross_asset_live',label,'Nessuna serie recente e validata nel feed V2; conservare lo snapshot datato senza attribuire aggiornamenti alla seduta odierna.');
 }
}
for(const [idx,x] of (cross.equity?.indices||[]).entries()){
 if(idx<2&&stored[idx===0?'SP500':'NASDAQCOM'])continue;
 if(iso(x.as_of))check('cross_asset','Snapshot equity '+x.name,x.as_of,2,'STATIC_SNAPSHOT');
}
for(const name of ['HY','IG']){
 const x=cross.credit?.[name];
 if(stored[name+'_OAS'])continue;
 if(x&&iso(x.as_of||x.date))check('cross_asset','Snapshot credit '+name,x.as_of||x.date,2,'STATIC_SNAPSHOT');
}
if(!stored.VIX&&cross.volatility?.VIX?.date)
 check('cross_asset','Snapshot VIX',cross.volatility.VIX.date,2,'STATIC_SNAPSHOT');
note('cross_asset','Copertura a frequenze diverse','S&P 500, Nasdaq, IG/HY OAS e VIX hanno un feed V2 di ricerca con date proprie; Russell, Dow, Euro Stoxx, partecipazione, Cina e alcuni dati spot rimangono snapshot, senza attribuzione a sedute attuali.');
const bench=JSON.parse(file('chf-nzd-benchmark-research.json'));
requireValid(bench.schema==='GMFQ_FXV2_CHF_NZD_BENCHMARK_RESEARCH_V1'&&
  bench.eligible_for_fx_pair_engine===false&&
  bench.eligible_for_backtests===false&&
  bench.canonical_government_rates_untouched===true,
  'CHF/NZD research source must never be mistaken for the certified FX engine');
if(bench.CHF&&bench.CHF.pair_status==='OFFICIAL_SNBSAMEBASIS_RESEARCH_REVIEW_REQUIRED'&&
   bench.CHF.eligible_for_pair_spreads===false&&Number.isFinite(bench.CHF['2Y'])&&Number.isFinite(bench.CHF['10Y'])){
 check('rates_research','CHF SNB same-date spot pair (not Core)',bench.CHF.paired_date,14,'SNB_RESEARCH_REVIEW_REQUIRED');
 requireValid(bench.CHF.separate_10y?.not_joinable_with_paired_2y===true,'CHF separate 10Y must not join stale 2Y');
}else gap('rates_research','CHF source','No same-day SNB 2Y/10Y research pair verified');
if(bench.NZD&&bench.NZD.status==='RBNZ_GOVT_B2_WEB_RESEARCH_UNAPPROVED'&&
   bench.NZD.cross_roll_change_allowed===false&&
   bench.NZD.independent_xlsx_reconciled===false&&bench.NZD.after_roll?.length===2){
 check('rates_research','NZD RBNZ B2 post-roll web research',bench.NZD.latest_date,7,'RBNZ_WEB_NOT_XLSX_RECONCILED');
 requireValid(Math.abs((bench.NZD.latest_10Y-bench.NZD.latest_2Y)*100-bench.NZD.latest_curve_bp)<.11,'NZD B2 post-roll curve arithmetic invalid');
 requireValid(bench.NZD.before_roll?.at(-1)?.date<bench.NZD.roll_date&&
   bench.NZD.after_roll[0].date===bench.NZD.roll_date,
   'NZD benchmark must split into nonjoined segments');
}else gap('rates_research','NZD source','No validated RBNZ benchmark-roll split in research feed');
note('rates_research','Research vs Core','CHF/NZD research levels do not promote OIS, FX spreads, cross-roll changes or backtests.');
const liq=read('NATIVE_LIQ_DATA');
requireValid(ccy.every(c=>!!liq[c]),'Incomplete G8 liquidity/credit feed');
const liqHtml=file('liquidita-credito.html');
requireValid(liqHtml.includes('assets/liquidity-credit-feed-v1.js')&&
             liqHtml.includes('cross-asset-live-data.json')&&
             liqHtml.includes('Credito ICE/FRED:'),
 'V2 Liquidità/Credito must independently consume dated FRED IG/HY overlay');
for(const k of ['IG_OAS','HY_OAS']){
 const z=crossLive.streams?.[k];
 if(z?.quality==='PUBLISHED_SOURCE_RESEARCH_ONLY'&&iso(z.date)&&Number.isFinite(z.value)&&
    z.kind==='CREDIT_OAS'&&z.unit==='percent'){
  check('liquidity_credit_live',k+' FRED published source',z.date,7,'RESEARCH_ONLY_FRED_ICE');
 }else gap('liquidity_credit_live',k,'Feed ICE/FRED non valido; la pagina deve mantenere snapshot con data senza promozione artificiale.');
}

note('liquidity_credit','Frequenze miste','Liquidità e credito pubblicati mensilmente o trimestralmente: la data dello snapshot di pagina non certifica il giorno delle osservazioni.');
const ratesHtml=file('tassi.html');
requireValid(ratesHtml.includes('CHF_SNB_10Y_SPOT_CONTEXT.json')&&ratesHtml.includes('NZD_B2_GOVT_WEB_REVIEW_CONTEXT.json'),
 'V2 missing separated CHF/NZD research context overlay');
const pages=['index','valute','coppie','tassi','ois','macro','banche','cot','cross-asset','liquidita-credito','calendario-news','research'];
requireValid(pages.every(x=>fs.existsSync(path.join(site,x+'.html'))),'Missing V2 HTML section');
result.summary={
  checks:result.checks.length,
  source_dates_ok:result.checks.filter(x=>x.state==='ON_CADENCE').length,
  late_or_invalid:result.checks.filter(x=>x.state!=='ON_CADENCE').length,
  gaps:result.findings.filter(x=>x.severity==='GAP').length,
  review_notes:result.findings.filter(x=>x.severity==='REVIEW').length,
  canonical_macro_series:macroCount,certified_policy_pricing:certified,
  eight_government_pairs:ccy.length,fx_pairs:pair.pair_count,v2_pages:pages.length
};
result.status=result.hard_errors.length?'AUDIT_FAILED':result.summary.gaps?'DATA_GAPS_PRESENT':'DATE_CHECKS_PASS';
const out=path.resolve('fxv2-freshness-evidence');
fs.mkdirSync(out,{recursive:true});
fs.writeFileSync(path.join(out,'freshness.json'),JSON.stringify(result,null,2)+'\n');
const lines=['## FX Quant V2 — Source-date freshness', '',
 'Source inspection '+today+' Europe/Rome. **Workflow green means the audit ran, not all feeds are fresh.**',
 'Status: **'+result.status+'**; '+result.summary.checks+' source checks; '+result.summary.gaps+' gaps and '+result.summary.review_notes+' review notes.', '',
 '### Concrete gaps', ...result.findings.filter(x=>x.severity==='GAP').map(x=>'- **'+x.area+' / '+x.item+'** — '+x.detail),'',
 'JSON receipt: fxv2-freshness-evidence/freshness.json'];
fs.writeFileSync(path.join(out,'freshness-summary.md'),lines.join('\n')+'\n');
if(process.env.GITHUB_STEP_SUMMARY)fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY,lines.join('\n')+'\n');
console.log('FXV2_FRESHNESS_RESULT '+JSON.stringify({status:result.status,summary:result.summary,hard_errors:result.hard_errors,top_gaps:result.findings.filter(x=>x.severity==='GAP').slice(0,12)}));
if(result.hard_errors.length)process.exitCode=1;
