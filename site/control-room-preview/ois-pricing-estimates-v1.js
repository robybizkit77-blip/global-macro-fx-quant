/* CHF/USD futures indicative, EUR unsynchronised, NZD explicit hypothetical basis.
   Read-only Rates-page supplement. Never promotes official OIS or pair signals. */
(function(){
'use strict';
const fx=['USD','EUR','GBP','JPY','AUD','CAD','NZD','CHF'],tenors=['3m','6m','12m'];
const flags={USD:'🇺🇸',EUR:'🇪🇺',GBP:'🇬🇧',JPY:'🇯🇵',AUD:'🇦🇺',CAD:'🇨🇦',NZD:'🇳🇿',CHF:'🇨🇭'};
const labels={OFFICIAL:'FONTE MONETARIA CERTIFICATA',PROXY:'STIMA · FUTURES',MIXED:'STIMA · FUTURES / DATE NON SINCRONIZZATE',CONFLICTED:'STIMA CONTESTATA · QUOTAZIONI NON CONVALIDATE',SCENARIO:'SCENARIO · RBNZ B2 · STIMA BANK BILL–OCR',WITHHELD:'FONTE NON DISPONIBILE'};
const number=x=>typeof x==='number'&&Number.isFinite(x)?x:null;
const fmt=x=>number(x)===null?'—':x.toFixed(2);
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
/* Reference date of the Italian research desk, including CET/CEST turnover.
   This is a calendar label only; it NEVER changes official observation dates. */
function romeTodayIso(now=new Date()){
 const parts=new Intl.DateTimeFormat('en-US',{timeZone:'Europe/Rome',
   year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(now);
 const val=k=>parts.find(p=>p.type===k)?.value;
 return val('year')+'-'+val('month')+'-'+val('day');
}
function fresh(date,today){
 if(!/^\d{4}-\d{2}-\d{2}$/.test(date||'')||!/^\d{4}-\d{2}-\d{2}$/.test(today||''))return false;
 const d=(Date.parse(today+'T00:00:00Z')-Date.parse(date+'T00:00:00Z'))/86400000;
 return Number.isInteger(d)&&d>=0&&d<=5;
}
/* Research empirical NZD bank-bill cash-carry calibration, NOT NZBO/OIS quotes.
   Arrays must match validation/cb_pricing/NZD_BB_CASH_RESEARCH_CALIBRATION_V1_2026-10-21.json.
   Public RBNZ monthly averages / month-end OCR manually pinned 2026-10-21. */
const NZD_REFERENCE_ROWS=[["2023-06",5.5,5.68],["2023-07",5.5,5.67],["2023-08",5.5,5.64],["2023-09",5.5,5.68],["2023-10",5.5,5.68],["2023-11",5.5,5.63],["2023-12",5.5,5.63],["2024-01",5.5,5.64],["2024-02",5.5,5.71],["2024-03",5.5,5.64],["2024-04",5.5,5.63],["2024-05",5.5,5.62],["2024-06",5.5,5.62]];
const NZD_RECENT_ROWS=[["2026-01",2.25,2.5],["2026-02",2.25,2.49],["2026-03",2.25,2.51],["2026-04",2.25,2.56],["2026-05",2.25,2.63],["2026-06",2.25,2.68]];
/* Distinct July–September 2026 observations, never used to fit the 24bp point.
   Source: same public RBNZ 90-day bank bill / month-end OCR table. */
const NZD_HOLDOUT_ROWS=[["2026-07",2.5,2.85],["2026-08",2.5,2.98],["2026-09",2.75,3.13]];
function empiricalMedian(values){
 const s=[...values].sort((a,b)=>a-b),k=Math.floor(s.length/2);
 return s.length%2?s[k]:(s[k-1]+s[k])/2;
}
function calibratedNzdCarry(){
 const basis=(input,expectedOCR)=>{
  if(!Array.isArray(input)||input.length<5)return null;
  const out=[];
  for(const [month,ocr,bill] of input){
   if(!/^\d{4}-\d{2}$/.test(month)||number(ocr)===null||
      number(bill)===null||ocr!==expectedOCR||bill<0||bill>25)return null;
   out.push(Math.round((bill-ocr)*10000)/100);
  }
  return out;
 };
 const old=basis(NZD_REFERENCE_ROWS,5.50),recent=basis(NZD_RECENT_ROWS,2.25);
 if(!old||!recent)return null;
 const all=old.concat(recent),mOld=empiricalMedian(old),mRecent=empiricalMedian(recent);
 const estimated=Math.round(0.30*mOld+0.70*mRecent);
 // Holdout months are EXCLUDED from the 24bp central point estimate. They
 // reveal a previously underestimated upper error band (Aug 2026 = 48bp).
 const originalLo=Math.floor(Math.min(...all)-2);
 const originalHi=Math.ceil(Math.max(...all)+2);
 const holdout=[];
 for(const [month,ocr,bill] of NZD_HOLDOUT_ROWS){
  if(!/^\d{4}-\d{2}$/.test(month)||number(ocr)===null||number(bill)===null||
     !(ocr>0&&bill>0&&bill<25))return null;
  holdout.push(Math.round((bill-ocr)*10000)/100);
 }
 if(holdout.length!==3||NZD_HOLDOUT_ROWS.map(x=>x[0]).join(',')!==
    '2026-07,2026-08,2026-09')return null;
 const errors=holdout.map(x=>Math.abs(x-estimated));
 const mae=Math.round((errors.reduce((a,b)=>a+b,0)/errors.length)*100)/100;
 const lo=originalLo;
 const hi=Math.max(originalHi,Math.ceil(Math.max(...holdout)+2));
 const originalCovered=holdout.filter(x=>x>=originalLo&&x<=originalHi).length;
 const expandedCovered=holdout.filter(x=>x>=lo&&x<=hi).length;
 if(!Number.isFinite(estimated)||estimated<=0||estimated>=100||lo<0||hi>100||
    !(lo<estimated&&estimated<hi)||originalCovered!==2||expandedCovered!==3||
    mae<0||mae>100)return null;
 return {schema:'GMFQ_NZD_EMPIRICAL_CASH_CARRY_SCENARIO_V1',
  basis_bp:estimated,low_bp:lo,high_bp:hi,observations:all.length,
  reference_median_bp:mOld,recent_median_bp:mRecent,
  holdout_months:3,holdout_point_mae_bp:mae,
  holdout_max_absolute_error_bp:Math.max(...errors),
  holdout_original_band_coverage:originalCovered,
  holdout_expanded_band_coverage:expandedCovered,
  expanded_band_selected_after_observing_holdout:true,
  holdout_is_real_ois_spread:false,
  source:'RBNZ B2 monthly 90-day bills and OCR',reviewed_as_of:'2026-10-21',
  direct_nzbo_ois_quote:false,statistical_confidence_interval:false,
  forward_ois_curve:false,policy_delta_allowed:false,core_effect:'NONE'};
}
/* Read-only futures provenance: checked dated ticker, verified trading day,
   price 100 minus rate, proximity of expiry to labelled 90/180/365d targets.
   This cannot construct a forward OIS cash curve, basis or 1D/1W repricing. */
const FUTURE_SPEC={USD:['CBOT:','ZQ'],EUR:['EUREX:','FST3'],CHF:['ICEEUR:','SA3']};
const TENOR_TARGET={'3m':90,'6m':180,'12m':365};
function dayIndex(v){
 if(!/^\d{4}-\d{2}-\d{2}$/.test(v||''))return null;
 const t=Date.parse(v+'T00:00:00Z');
 return Number.isFinite(t)&&new Date(t).toISOString().slice(0,10)===v?t/86400000:null;
}
function auditDatedFuture(ccy,term,primary,rate,quoteDate,today){
 const spec=FUTURE_SPEC[ccy],target=TENOR_TARGET[term];
 if(!spec||!target||!primary||number(primary.futures_price)===null||
    number(rate)===null||!fresh(quoteDate,today)||primary.quote_as_of!==quoteDate||
    primary.quote_timestamp_verified!==true||
    primary.quote_timestamp_source!=='SSR_DAILY_BAR_DATA_UPDATE_TIME')return null;
 const code=String(primary.contract||''),pattern=new RegExp('^'+spec[1]+'[FGHJKMNQUVXZ][0-9]{4}$');
 if(!pattern.test(code)||primary.symbol!==spec[0]+code||
    primary.mapping!=='nearest dated listed contract expiry to today+'+target+'d; no interpolation')return null;
 // Contract-to-tenor proximity is fixed AT THE OBSERVATION DAY.
 // Reopening the site tomorrow must never shift yesterday's futures expiry.
 // Recency remains checked separately by fresh(quoteDate,today).
 const expiry=dayIndex(primary.expiration),quoteIndex=dayIndex(quoteDate);
 if(expiry===null||quoteIndex===null||expiry<quoteIndex)return null;
 const gap=expiry-quoteIndex-target;
 // Tolerate ONE calendar day of bar-time vs collection-time mismatch at the expiry-window boundary.
 // Any accepted borderline point is explicitly APPROXIMATE_EXPIRY, never OIS.
 if(Math.abs(gap)>46)return null;
 const implied=100-primary.futures_price;
 if(Math.abs(implied-rate)>0.0002||implied<-5||implied>25)return null;
 return {value:rate,date:quoteDate,contract:code,expires:primary.expiration,
  tenor_gap_days:gap,mapping_quality:Math.abs(gap)<=21?'NEAR_TARGET':'APPROXIMATE_EXPIRY',
  source_quote_verified:true,direct_ois_quote:false,policy_repricing_allowed:false};
}
/* Conflict-graded secondary prints are unverified context, not market OIS. */
function auditDisputedFuture(ccy,term,p,keys,today){
 if(p?.quote_timestamp_verified!==false||
    p?.quote_timestamp_source!=='QUARANTINED_SAME_CONTRACT_SAME_DAY'||
    !Array.isArray(keys))return null;
 const matches=keys.filter(k=>k?.horizon===term&&k.contract===p.contract&&
   k.observation_date===p.quote_as_of&&
   typeof k.event_id==='string'&&/^[a-f0-9]{64}$/.test(k.event_id));
 if(matches.length!==1)return null;
 // The independent contract/expiry/date/price arithmetic is reused purely
 // for geometry, never as a verification or a policy-pricing promotion.
 const check=auditDatedFuture(ccy,term,{
  ...p,quote_timestamp_verified:true,
  quote_timestamp_source:'SSR_DAILY_BAR_DATA_UPDATE_TIME'
 },p.rate,p.quote_as_of,today);
 if(!check)return null;
 return {...check,source_quote_verified:false,source_quote_disputed:true,
  dispute_event_id:matches[0].event_id,direct_ois_quote:false,
  policy_repricing_allowed:false};
}
function matrix(ois,bb,today){
 return fx.map(ccy=>{
  const x=ois?.currencies?.[ccy]||{},points={};let tier='WITHHELD',source='';
  if(x.operational_status==='GREEN_OFFICIAL'&&x.official_status==='ACTIVE'&&
     x.quality==='OFFICIAL_CERTIFIED'&&x.backtest_eligible_as_official===true&&fresh(x.as_of,today)){
    if(tenors.every(t=>number(x.horizons?.[t]?.rate)!==null)){
     for(const t of tenors)points[t]={value:x.horizons[t].rate,date:x.as_of};
     tier='OFFICIAL';source=x.source||'';
    }
  }else if(['USD','EUR','CHF'].includes(ccy)&&x.operational_status==='GREEN_ESTIMATED'&&
    x.official_status==='WITHHELD'&&x.quality==='ESTIMATED_INFORMATIONAL'&&
    x.backtest_eligible_as_official===false&&x.method_id==='TRADINGVIEW_DATED_FUTURES_SSR_V2'){
    const sourceDisputed=x.source_conflict_status===
      'UNRESOLVED_SECONDARY_SOURCE_SAME_DAY_CONFLICT';
    for(const t of tenors){
     const p=x.horizons?.[t]||{},checked=auditDatedFuture(ccy,t,p,p.rate,p.quote_as_of,today);
     if(checked)points[t]=checked;
     else if(sourceDisputed){
      const disputed=auditDisputedFuture(ccy,t,p,x.source_conflict_keys,today);
      if(disputed)points[t]=disputed;
     }
    }
    if(Object.keys(points).length){
      tier=Object.values(points).some(p=>p.source_quote_disputed)?
       'CONFLICTED':
       new Set(Object.values(points).map(p=>p.date)).size>1?'MIXED':'PROXY';
      source=(x.source||'')+(tier==='CONFLICTED'?
       ' · QUOTAZIONI SECONDARIE CONTESTATE: livelli provvisori, nessun Delta OIS':'');
    }
  }else if(['USD','EUR','CHF'].includes(ccy)&&x.operational_status==='WITHHELD'&&
    x.official_status==='WITHHELD'&&x.quality==='ESTIMATED_INFORMATIONAL'&&
    x.backtest_eligible_as_official===false){
    const q=x.secondary_quote_context||{};
    if(q.status==='INDICATIVE_OBSERVATIONS_NON_OIS'&&q.full_curve_usable===false&&
       q.cross_date_join_allowed===false&&q.policy_delta_allowed===false&&
       q.repricing_signal_allowed===false&&q.backtest_eligible_as_official===false){
      for(const t of tenors){
       const p=q.horizons?.[t]||{},primary=x.horizons?.[t]||{};
       if(p.source_quality!=='SECONDARY_VERIFIED_DAILY_BAR'||p.contract!==primary.contract)continue;
       const checked=auditDatedFuture(ccy,t,primary,p.rate_indicative,p.quote_as_of,today);
       if(checked)points[t]=checked;
      }
      if(Object.keys(points).length){tier='MIXED';source=q.source||'';}
    }
  }else if(ccy==='NZD'&&x.official_status==='WITHHELD'&&
    bb?.schema==='GMFQ_NZD_CB_PRICING_DIRECTIONAL_PROXY_V1'&&
    bb.currency==='NZD'&&bb.status==='LIVE_DIRECTIONAL_PROXY_READY'&&
    bb.governance?.substitutes_for_ois_level===false&&
    bb.governance?.policy_delta_from_proxy_allowed===false&&fresh(bb.as_of,today)){
    const calibration=calibratedNzdCarry();
    if(calibration&&bb.governance?.backtest_eligible_as_official_ois===false){
     for(const t of tenors){
      const p=bb.horizons?.[t]||{},raw=number(p.implied_bank_bill_rate);
      if(raw!==null&&raw>=-5&&raw<=25&&
         /^\d{4}-\d{2}-\d{2}$/.test(p.expiration||'')&&
         typeof p.mapping==='string'&&p.mapping.includes('nearest listed expiry')){
       points[t]={
        value:Math.round((raw-calibration.basis_bp/100)*100)/100,date:bb.as_of,
        range:[Math.round((raw-calibration.high_bp/100)*100)/100,
               Math.round((raw-calibration.low_bp/100)*100)/100]
       };
      }
     }
     if(Object.keys(points).length){
      tier='SCENARIO';source=(bb.source||'')+
        ' · '+calibration.source+' ('+calibration.observations+
        ' mesi; sconto empirico '+calibration.basis_bp+' bp)';
     }
    }
  }
  return {ccy,tier,points,source,official_ois:ccy==='GBP'&&tier==='OFFICIAL',
    allow_official_promotion:false,allow_repricing:false,
    core_score_effect:'NONE',bias_effect:'NONE',pair_effect:'NONE',backtest_official:false};
 });
}
/* Exposes individually audited 6M informational levels on Pair pages.
   This is NOT 6M policy repricing: no derivative pair impact, no core promotion. */
function indicativeSixMonth(ois,today){
 const observations=matrix(ois,null,today),approved={};
 for(const row of observations){
  if(!['USD','EUR','CHF'].includes(row.ccy)||
     !['PROXY','MIXED','CONFLICTED'].includes(row.tier))continue;
  const p=row.points?.['6m'];
  if(!p||!p.source_quote_verified||!p.contract||!p.expires||
     !fresh(p.date,today)||number(p.value)===null||
     p.policy_repricing_allowed!==false||p.direct_ois_quote!==false)continue;
  approved[row.ccy]=Object.freeze({
    type:row.tier,currency:row.ccy,value:p.value,
    quote_as_of:p.date,contract:p.contract,expiry:p.expires,
    label:row.tier==='CONFLICTED'?'FUTURES DATATO · '+row.ccy+' 6M verificato singolarmente, altri contratti contestati':
      row.tier==='MIXED'?'FUTURES DATATO · '+row.ccy+' non sincronizzato':'FUTURES INDICATIVO',
    is_official_ois:false,policy_delta_allowed:false,pair_effect:'NONE',core_effect:'NONE'
  });
 }
 return Object.freeze(approved);
}
/* Study-only NZD 6M bridge: reuse the same audited 3/6/12 Rates matrix. */
function scenarioSixMonth(ois,bb,today){
 const r=matrix(ois,bb,today).find(x=>x.ccy==='NZD'&&x.tier==='SCENARIO');
 const p=r?.points?.['6m'],range=p?.range;
 if(!p||number(p.value)===null||!fresh(p.date,today)||
    !Array.isArray(range)||range.length!==2||
    number(range[0])===null||number(range[1])===null||
    !(range[0]<p.value&&p.value<range[1])||p.date!==bb?.as_of||
    r.allow_repricing!==false||r.allow_official_promotion!==false)return Object.freeze({});
 return Object.freeze({NZD:Object.freeze({
  currency:'NZD',type:'SCENARIO',value:p.value,
  range:Object.freeze([...range]),quote_as_of:p.date,
  is_official_ois:false,policy_delta_allowed:false,
  backtest_eligible_as_official:false,pair_effect:'NONE',core_effect:'NONE'
 })});
}
/* A full G8 research row requires three valid dated levels. A single
   observed contract must NOT count as complete 3M/6M/12M coverage. */
function coverage(ois,bb,today){
 const rows=matrix(ois,bb,today);
 const complete=rows.filter(x=>x.tier!=='WITHHELD'&&
   tenors.every(t=>number(x.points[t]?.value)!==null&&fresh(x.points[t]?.date,today)));
 const official=complete.filter(x=>x.tier==='OFFICIAL');
 const context=complete.filter(x=>x.tier!=='OFFICIAL');
 return {
  schema:'GMFQ_OIS_G8_RESEARCH_COVERAGE_V1',
  date:today,total:8,official_count:official.length,
  context_count:context.length,covered_count:complete.length,
  official_codes:official.map(x=>x.ccy),
  context_codes:context.map(x=>x.ccy),
  incomplete_codes:rows.filter(x=>!complete.includes(x)).map(x=>x.ccy),
  currency_tiers:Object.fromEntries(rows.map(x=>[x.ccy,
   complete.includes(x)?x.tier:'INCOMPLETE_OR_STALE'])),
  unverified_are_not_official:true,
  no_ois_official_promotion:true,core_effect:'NONE',
  pair_effect:'NONE',backtest_estimated_as_official:false
 };
}

/* Pure, source-dated SAME futures-contract comparisons for each approximate
   3M/6M/12M label. No OIS repricing, no smoothing and never compare a roll. */
function matchedResearchMoves(text,rows,today){
 if(typeof text!=='string'||text.length>3000000)return [];
 const parsed=[],seen=new Set();
 const exchange={USD:'CBOT:',EUR:'EUREX:',CHF:'ICEEUR:'};
 const roots={USD:'ZQ',EUR:'FST3',CHF:'SA3'};
 const validDay=x=>/^\d{4}-\d{2}-\d{2}$/.test(x||'')&&
   Number.isFinite(Date.parse(x+'T00:00:00Z'))&&
   new Date(Date.parse(x+'T00:00:00Z')).toISOString().slice(0,10)===x;
 try{
  for(const line of text.split('\n')){
   if(!line.trim())continue;
   const x=JSON.parse(line),ccy=x.currency;
   if(x.schema!=='GMFQ_OIS_SAME_CONTRACT_QUOTE_V1'||
      !Object.prototype.hasOwnProperty.call(exchange,ccy)||
      x.source_timestamp_evidence!=='SSR_DAILY_BAR_DATA_UPDATE_TIME'||
      x.source_method!=='TRADINGVIEW_DATED_FUTURES_SSR_V2'||
      x.official_ois_quote!==false||x.policy_delta_eligible!==false||
      x.backtest_eligible_as_official!==false||
      !['3m','6m','12m'].includes(x.observed_under_horizon)||
      typeof x.contract!=='string'||
      !(new RegExp('^'+roots[ccy]+'[FGHJKMNQUVXZ][0-9]{4}$')).test(x.contract)||
      x.symbol!==exchange[ccy]+x.contract||
      !validDay(x.observation_date)||!validDay(x.expiration)||
      x.expiration<=x.observation_date||
      typeof x.first_seen_at_utc!=='string'||
      !/^\d{4}-\d{2}-\d{2}T/.test(x.first_seen_at_utc)||
      !validDay(x.first_seen_at_utc.slice(0,10))||
      x.first_seen_at_utc.slice(0,10)<x.observation_date||
      number(x.futures_price)===null||number(x.implied_rate)===null||
      Math.abs(100-x.futures_price-x.implied_rate)>0.0002)return [];
   const identity=[ccy,x.contract,x.observation_date].join('|');
   if(seen.has(identity))return [];
   seen.add(identity);parsed.push(x);
  }
 }catch(_){return [];}
 const result=[];
 for(const ccy of ['USD','EUR','CHF']){
  const row=rows.find(x=>x.ccy===ccy);
  if(!row||!['PROXY','MIXED'].includes(row.tier))continue;
  for(const tenor of ['3m','6m','12m']){
   const p=row.points?.[tenor];
   if(!p?.source_quote_verified||!p.contract||!p.expires||!validDay(p.date)||
      !fresh(p.date,today))continue;
   const bars=parsed.filter(x=>x.currency===ccy&&
     x.contract===p.contract&&x.symbol===exchange[ccy]+p.contract&&
     x.expiration===p.expires&&x.observed_under_horizon===tenor&&
     x.observation_date<=p.date)
    .sort((a,b)=>a.observation_date.localeCompare(b.observation_date));
   if(bars.length<2)continue;
   const last=bars[bars.length-1],prior=bars[bars.length-2];
   if(last.observation_date!==p.date||
      Math.abs(last.implied_rate-p.value)>0.0002)continue;
   const dayGap=(Date.parse(last.observation_date+'T00:00:00Z')-
     Date.parse(prior.observation_date+'T00:00:00Z'))/86400000;
   if(!Number.isInteger(dayGap)||dayGap<1||dayGap>7)continue;
   result.push({ccy,tenor,contract:p.contract,from:prior.observation_date,
     to:last.observation_date,calendar_gap_days:dayGap,
     delta_bp:Math.round((last.implied_rate-prior.implied_rate)*10000)/100,
     research_only:true,policy_delta_allowed:false,official_ois:false});
  }
 }
 return result;
}
function matchedResearchHtml(moves){
 const currencies=['USD','EUR','CHF'],terms=['3m','6m','12m'];
 if(!moves?.length)return '<p class="gmfq-est-note">Movimenti degli stessi contratti: osservazioni confrontabili non disponibili. Nessun ΔOIS ricostruito.</p>';
 const cells=new Map(moves.map(x=>[x.ccy+'|'+x.tenor,x]));
 const td=(ccy,t)=>{
  const r=cells.get(ccy+'|'+t);
  return r?'<div class="gmfq-same-value" data-term="'+t+'" data-contract="'+esc(r.contract)+'"><b>'+
   (r.delta_bp>0?'+':'')+fmt(r.delta_bp)+' bp</b>'+
   '<small>'+esc(r.contract)+'</small><small>'+esc(r.from)+' → '+esc(r.to)+'</small></div>':
   '<div class="gmfq-same-value"><b>—</b><small>Non confrontabile</small></div>';
 };
 return '<section class="gmfq-est-note gmfq-same-contract" data-same-contract="RESEARCH_ONLY">'+
  '<strong>Variazioni osservate · stessi contratti futures</strong>'+
  '<p>Confronto su ciascuna scadenza indicativa: 3M / 6M / 12M. Date e contratto verificati singolarmente.</p>'+
  '<div class="gmfq-same-table" role="table" aria-label="Variazioni futures per contratto">'+
  '<div role="row" class="gmfq-same-line gmfq-same-head"><span>Valuta</span><span>3M</span><span>6M</span><span>12M</span></div>'+
  currencies.map(ccy=>'<div role="row" class="gmfq-same-line" data-same-ccy="'+ccy+'">'+
   '<div><strong>'+flags[ccy]+' '+ccy+'</strong></div>'+
   terms.map(t=>td(ccy,t)).join('')+'</div>').join('')+'</div>'+
  '<small>Variazioni dello <b>stesso futures</b> su intervalli osservati anche diversi da una seduta. Non sono ΔOIS ufficiali, curve sincronizzate o segnali FX.</small></section>';
}
/* A research visual, not an OIS curve: mixed-date futures are unjoined. */
function miniCharts(rows){
 const cards=rows.map(r=>{
  const p=tenors.map((t,i)=>({t,i,v:r.points[t]})).filter(x=>number(x.v?.value)!==null&&fresh(x.v.date,x.v.date));
  if(p.length<2)return '<article class="gmfq-mini-curve" data-chart-ccy="'+r.ccy+'" data-points="'+p.length+'"><b>'+flags[r.ccy]+' '+r.ccy+'</b><p>Storico insufficiente · dati in tabella</p></article>';
  const values=p.map(x=>x.v.value),bottom=Math.min(...values),top=Math.max(...values),pad=Math.max(.1,(top-bottom)*.2);
  const x=i=>38+111*i,y=v=>82-62*(v-bottom+pad)/(top-bottom+2*pad);
  const synced=new Set(p.map(a=>a.v.date)).size===1,joined=p.length===3&&synced&&r.tier!=='CONFLICTED';
  const path=joined?'<path d="'+p.map((a,i)=>(i?'L':'M')+x(a.i)+','+y(a.v.value).toFixed(1)).join(' ')+
   '" fill="none" stroke="'+(r.tier==='OFFICIAL'?'#52b6cf':'#d9bd7a')+'" stroke-width="2"'+
   (r.tier==='OFFICIAL'?'':' stroke-dasharray="5 4"')+'/>':'';
  const dots=p.map(a=>'<g data-tenor="'+a.t+'"><circle cx="'+x(a.i)+'" cy="'+y(a.v.value).toFixed(1)+
   '" r="4" fill="'+(r.tier==='OFFICIAL'?'#52b6cf':'#d9bd7a')+'"><title>'+esc(a.t+' '+fmt(a.v.value)+'% '+a.v.date)+
   '</title></circle><text x="'+x(a.i)+'" y="'+Math.max(11,y(a.v.value)-9).toFixed(1)+
   '" text-anchor="middle">'+(r.tier==='OFFICIAL'?'':'≈')+fmt(a.v.value)+'%</text></g>').join('');
  const date=r.tier==='CONFLICTED'?
    'Quotazioni contestate · punti non connessi · '+[...new Set(p.map(a=>a.v.date))].join(' / '):
    joined?p[0].v.date:'Date distinte: '+[...new Set(p.map(a=>a.v.date))].join(' / ');
  return '<article class="gmfq-mini-curve" data-chart-ccy="'+r.ccy+'" data-quality="'+r.tier+
    '" data-points="'+p.length+'" data-joined="'+joined+'"><header><b>'+flags[r.ccy]+' '+r.ccy+
    '</b><small>'+labels[r.tier]+'</small></header><svg viewBox="0 0 300 112" role="img" aria-label="'+esc(r.ccy+' '+date)+
    '"><g class="axis"><line x1="20" y1="88" x2="280" y2="88"/>'+tenors.map((t,i)=>
      '<text x="'+x(i)+'" y="106" text-anchor="middle">'+t.toUpperCase()+'</text>').join('')+
    '</g>'+path+dots+'</svg><small class="date">'+esc(date)+'</small></article>';
 }).join('');
 return '<section id="gmfq-g8-mini-charts" data-mini-curves="'+rows.length+'"><header><b>Grafici 3M / 6M / 12M · G8</b><small>Scala indipendente per valuta. Tratteggio = stima; punti non connessi = date diverse. Nessuna curva OIS inventata.</small></header><div class="gmfq-mini-grid">'+cards+'</div></section>';
}
function view(rows,moves=[]){
 const cell=(r,t)=>{const x=r.points[t];return x?
  '<b>'+(r.tier==='OFFICIAL'?'':'≈')+fmt(x.value)+'%</b><small>'+esc(x.date)+'</small>'+
    (x.source_quote_disputed?'<small>⚠ QUOTAZIONE CONTESTATA · non convalidata</small>':
     x.source_quote_verified?'<small>scad. '+(x.tenor_gap_days>0?'+':'')+x.tenor_gap_days+'gg vs target</small>':'')+
   (x.range?'<small>'+fmt(x.range[0])+'–'+fmt(x.range[1])+'%</small>':''):
  '<b>—</b><small>n.d.</small>';};
 const counts=Object.fromEntries(['OFFICIAL','PROXY','MIXED','CONFLICTED','SCENARIO','WITHHELD'].map(t=>[t,rows.filter(r=>r.tier===t).length]));
 // The user needs all eight dated 3M/6M/12M references at first glance.
 // Preserve full source provenance and leave methodology collapsible.
 // No estimate becomes a certified OIS or an official policy delta.
 const usable=rows.filter(r=>r.tier!=='WITHHELD'&&tenors.every(t=>
  number(r.points[t]?.value)!==null&&r.points[t]?.date)).length;
 const brief=usable+'/8 valute con riferimenti numerici (ufficiali, proxy o scenari) · '+
   counts.OFFICIAL+' fonti certificate · '+counts.PROXY+' futures indicativi · '+
   counts.MIXED+' con date diverse · '+counts.CONFLICTED+' con quotazioni contestate · '+counts.SCENARIO+' scenario NZD'+
   (counts.WITHHELD?' · '+counts.WITHHELD+' senza fonte attendibile':'');
 return '<h2 class="desk-panel-title">G8 · OIS e stime monetarie 3M / 6M / 12M</h2>'+
 '<p class="gmfq-est-quick-read" data-g8-estimated-curve-coverage="'+usable+'/8"><strong>Copertura G8 · </strong>'+esc(brief)+
 '. Tutte le valute sono consultabili; le stime non diventano segnali.</p>'+miniCharts(rows)+
 '<details class="gmfq-est-disclosure" open data-default="OPEN"><summary>Tabella G8 · 3M / 6M / 12M, dati e fonti (tocca per nascondere)</summary>'+
 '<div class="gmfq-est-body"><p><b>8 valute, 3 scadenze per valuta.</b> Le curve non certificate restano <b>stime/proxy</b> con date separate, non quotazioni OIS né curve sincronizzate. Le quotazioni discordanti per lo stesso contratto/data sono <b>contestate, non convalidate</b>, senza repricing e senza linee congiunte. Nessun segnale FX deriva dai valori stimati.</p>'+
 '<div role="table" class="gmfq-est-table"><div class="gmfq-est-row gmfq-est-head" role="row"><span>Valuta</span><span>3M</span><span>6M</span><span>12M</span></div>'+
 rows.map(r=>'<div role="row" class="gmfq-est-row" data-ccy="'+r.ccy+'" data-estimate-type="'+r.tier+'">'+
 '<div><strong>'+flags[r.ccy]+' '+r.ccy+'</strong><small>'+labels[r.tier]+'</small></div>'+
 tenors.map(t=>'<div>'+cell(r,t)+'</div>').join('')+
 '<div class="gmfq-est-source">'+esc(r.source||'Fonte non corrente')+'</div></div>').join('')+'</div>'+
 matchedResearchHtml(moves)+'<p class="gmfq-est-note"><b>Metodo:</b> GBP OIS BoE; AUD/CAD/JPY futures monetari ufficiali; USD/EUR/CHF: ogni contratto è datato separatamente; se le date non coincidono, sono solo osservazioni individuali e non una curva sincronizzata. Su USD/EUR/CHF vengono verificati prezzo, contratto, data e scadenza; lo scarto in giorni è visibile, <b>senza inventare una correzione OIS</b>. NZD: scenario empirico su Bank Bill 90 giorni − OCR RBNZ (19 mesi, due regimi): sconto stimato 24 bp, fascia prudenziale 10–50 bp, ampliata dopo un test su luglio–settembre 2026 (errore medio del punto centrale circa 16 bp). <b>non è uno spread OIS misurato e non intervallo statistico</b>. Sono futures trimestrali, non una curva OIS spot. Nessuna stima produce variazioni OIS 1D/1W, segnali FX o backtest.</p></div></details>';
}
const css=[
 '#gmfq-ois-research-estimates{margin:0 0 14px;min-width:0}',
 '#gmfq-ois-research-estimates .gmfq-est-quick-read{padding:4px 15px 2px;margin:5px 0;color:#b7cbd8;font:12px/1.55 Arial,sans-serif;overflow-wrap:anywhere}',
 '#gmfq-ois-research-estimates .gmfq-est-quick-read strong{color:#e4edf5}',
 '#gmfq-g8-mini-charts{padding:10px 15px 14px;border-top:1px solid #294456}',
 '#gmfq-g8-mini-charts>header{display:grid;gap:3px;font:12px Arial,sans-serif;color:#e4eef6;margin-bottom:8px}',
 '#gmfq-g8-mini-charts>header small{color:#afc1cd;font:10px/1.5 Arial,sans-serif}',
 '#gmfq-g8-mini-charts .gmfq-mini-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}',
 '#gmfq-g8-mini-charts .gmfq-mini-curve{min-width:0;border:1px solid #294859;background:#092133;padding:8px;border-radius:6px}',
 '#gmfq-g8-mini-charts .gmfq-mini-curve header{display:flex;justify-content:space-between;gap:8px;color:#e6eff5;font:12px Arial,sans-serif}',
 '#gmfq-g8-mini-charts .gmfq-mini-curve header small{color:#c8b47f;font:9px/1.5 Arial,sans-serif}',
 '#gmfq-g8-mini-charts .gmfq-mini-curve svg{display:block;width:100%;height:auto;max-height:130px}',
 '#gmfq-g8-mini-charts .gmfq-mini-curve svg text{fill:#e2eef5;font:10px Arial,sans-serif}',
 '#gmfq-g8-mini-charts .gmfq-mini-curve svg .axis line{stroke:#345061}',
 '#gmfq-g8-mini-charts .gmfq-mini-curve .date{display:block;color:#acc5d3;font:9px/1.4 Arial,sans-serif}',
 '@media(max-width:600px){#gmfq-g8-mini-charts{padding:8px}#gmfq-g8-mini-charts .gmfq-mini-grid{grid-template-columns:1fr}}',
 '#gmfq-ois-research-estimates .gmfq-est-disclosure{padding:0 15px 12px;margin-top:5px}',
 '#gmfq-ois-research-estimates .gmfq-est-disclosure>summary{color:#e0c88b;font:600 12px/1.55 Arial,sans-serif;cursor:pointer;padding:10px 0;border-top:1px solid #274355;outline-offset:3px}',
 '#gmfq-ois-research-estimates .gmfq-est-disclosure>summary:focus-visible{outline:2px solid #e0c88b}',
 '#gmfq-ois-research-estimates .gmfq-est-disclosure:not([open])>:not(summary){display:none!important}',
 '@media(max-width:600px){#gmfq-ois-research-estimates .gmfq-est-quick-read{padding:4px 10px 1px;font-size:11px}#gmfq-ois-research-estimates .gmfq-est-disclosure{padding:0 10px 10px}#gmfq-ois-research-estimates .gmfq-est-disclosure>summary{font-size:11px}}',
 '#gmfq-ois-research-estimates .gmfq-est-body{padding:12px 15px;color:#bacedd;font:12px/1.5 Arial,sans-serif}',
 '#gmfq-ois-research-estimates .gmfq-est-table{border:1px solid #2c495a;background:#0a2132;border-radius:6px;overflow:hidden}',
 '#gmfq-ois-research-estimates .gmfq-est-row{display:grid;grid-template-columns:minmax(115px,1.3fr) repeat(3,minmax(75px,1fr));border-bottom:1px solid #254153}',
 '#gmfq-ois-research-estimates .gmfq-est-row>div,#gmfq-ois-research-estimates .gmfq-est-row>span{padding:7px 7px;min-width:0;overflow-wrap:anywhere}',
 '#gmfq-ois-research-estimates .gmfq-est-row b{display:block;color:#e6eff5;font:600 14px/1.3 Arial,sans-serif;font-variant-numeric:tabular-nums}',
 '#gmfq-ois-research-estimates .gmfq-est-row small{display:block;color:#a4bccc;font:10px/1.35 Arial,sans-serif}',
 '#gmfq-ois-research-estimates .gmfq-est-source{grid-column:1/-1;color:#9aafbd;font-size:10px;padding-top:0!important}',
 '#gmfq-ois-research-estimates .gmfq-est-head{color:#adbecc;background:#142c3d;font:600 10px Arial,sans-serif}',
 '#gmfq-ois-research-estimates [data-estimate-type="SCENARIO"] b,#gmfq-ois-research-estimates [data-estimate-type="MIXED"] b{color:#e3c681}',
 '#gmfq-ois-research-estimates .gmfq-est-note{margin-top:12px;color:#b1c5d2}',
 '#gmfq-ois-research-estimates .gmfq-same-table{border:1px solid #2c495a;background:#0a2132;border-radius:6px;margin:8px 0;overflow:hidden}',
 '#gmfq-ois-research-estimates .gmfq-same-line{display:grid;grid-template-columns:minmax(72px,.75fr) repeat(3,minmax(0,1fr));border-bottom:1px solid #254153}',
 '#gmfq-ois-research-estimates .gmfq-same-line>*{padding:7px 5px;min-width:0;overflow-wrap:anywhere}',
 '#gmfq-ois-research-estimates .gmfq-same-head{background:#142c3d;color:#adbecc;font-weight:600}',
 '#gmfq-ois-research-estimates .gmfq-same-value b{color:#e6eff5;display:block;font-size:12px;font-variant-numeric:tabular-nums}',
 '#gmfq-ois-research-estimates .gmfq-same-value small{color:#a4bccc;display:block;font-size:9px;line-height:1.35}',
 '@media(max-width:600px){#gmfq-ois-research-estimates .gmfq-same-line{grid-template-columns:minmax(55px,.7fr) repeat(3,minmax(0,1fr))}#gmfq-ois-research-estimates .gmfq-same-line>*{padding:6px 3px}#gmfq-ois-research-estimates .gmfq-same-value b{font-size:11px}#gmfq-ois-research-estimates .gmfq-same-value small{font-size:8px}}',
 '@media(max-width:600px){#gmfq-ois-research-estimates .gmfq-est-body{padding:9px}#gmfq-ois-research-estimates .gmfq-est-row{grid-template-columns:minmax(78px,1.1fr) repeat(3,minmax(0,1fr))}#gmfq-ois-research-estimates .gmfq-est-row>div,#gmfq-ois-research-estimates .gmfq-est-row>span{padding:6px 4px}#gmfq-ois-research-estimates .gmfq-est-row b{font-size:12px}#gmfq-ois-research-estimates .gmfq-est-row small{font-size:9px}}'
].join('');
if(typeof module!=='undefined'&&module.exports)module.exports={romeTodayIso,matrix,view,matchedResearchMoves,fresh,coverage,indicativeSixMonth,scenarioSixMonth,auditDatedFuture,calibratedNzdCarry,NZD_REFERENCE_ROWS,NZD_RECENT_ROWS,NZD_HOLDOUT_ROWS};
if(typeof window!=='undefined')window.GMFQ_OIS_RESEARCH_V1=Object.freeze({romeTodayIso,matrix,coverage,indicativeSixMonth,scenarioSixMonth});
if(typeof document==='undefined')return;
const frame=document.getElementById('gmfq-page');if(!frame)return;
const ROOT='https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/main/live_data/sections/';
let mounted=null;
function active(){return(location.hash||'#/home').split('?')[0]==='#/tassi';}
async function get(p){const r=await fetch(ROOT+p,{cache:'no-store'});if(!r.ok)throw Error('feed '+p);return r.json();}
async function loadSameContractArchive(){
 const url='https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/main/validation/cb_pricing/history/OIS_SAME_CONTRACT_QUOTES_V1.jsonl';
 const response=await fetch(url,{cache:'no-store'});
 if(!response.ok)throw Error('same-contract source history unavailable');
 return response.text();
}
async function mount(doc){
 if(!active()||frame.contentDocument!==doc||mounted===doc)return;
 const anchor=doc.getElementById('ois-rows')?.closest('.desk-panel');if(!anchor)return;
 mounted=doc;
 const box=doc.createElement('section');box.id='gmfq-ois-research-estimates';box.className='desk-panel';
 box.dataset.coreEffect='NONE';box.dataset.officialPromotion='false';box.dataset.status='LOADING';
 box.innerHTML='<h2 class="desk-panel-title">G8 · tassi monetari</h2>';
 // The verified, quality-graded 8-currency matrix is the primary Rates
 // readout; do not force the user to scroll past an official-only table
 // that shows WITHHELD for perfectly usable dated secondary observations.
 anchor.insertAdjacentElement('beforebegin',box);
 const st=doc.createElement('style');st.textContent=css;doc.head.appendChild(st);
 try{const [a,b,h]=await Promise.allSettled([get('OIS_OPERATIONAL_VIEW.json'),get('NZD_CB_PRICING_DIRECTIONAL_PROXY.json'),loadSameContractArchive()]);
  if(frame.contentDocument!==doc||!active())return;
  const o=a.status==='fulfilled'?a.value:null,p=b.status==='fulfilled'?b.value:null;
  if(o?.schema!=='GMFQ_OIS_OPERATIONAL_VIEW_V1'||!o.currencies)throw Error('invalid feed');
  const rows=matrix(o,p,romeTodayIso());
  box.dataset.status='RESEARCH_ONLY';box.dataset.officalSources=''+rows.filter(r=>r.tier==='OFFICIAL').length;
  const now=romeTodayIso();
  const complete=rows.length===8&&rows.every(r=>r.tier!=='WITHHELD'&&
   tenors.every(t=>number(r.points[t]?.value)!==null&&fresh(r.points[t]?.date,now)));
  box.dataset.sourceGradedCoverage=complete?'8/8':'PARTIAL';
  box.dataset.signalEffect='NONE';
  box.innerHTML=view(rows,matchedResearchMoves(h.status==='fulfilled'?h.value:'',rows,now));
  // Keep the native STRICT CERTIFIED FEED unchanged and inspectable on demand.
  // Collapse its visually duplicate, official-only gaps ONLY while a fully
  // sourced and dated 8/8 matrix is available; fail open otherwise.
  if(complete&&anchor.isConnected&&!doc.getElementById('gmfq-certified-only-toggle')){
   const toggle=doc.createElement('button');
   toggle.type='button';toggle.id='gmfq-certified-only-toggle';
   toggle.dataset.scope='NATIVE_OFFICIAL_ONLY';
   toggle.setAttribute('aria-controls','ois-rows');
   toggle.style.cssText='display:block;width:100%;text-align:left;margin:0 0 13px;padding:9px 13px;border:1px solid #294b61;background:#0c2131;color:#b5c8d8;border-radius:6px;font:12px/1.5 Arial,sans-serif;cursor:pointer';
   box.insertAdjacentElement('afterend',toggle);
   const focus=new URLSearchParams(location.hash.split('?')[1]||'').get('focus');
   let shown=focus==='ois';
   const sync=()=>{
    anchor.hidden=!shown;
    // Old approved official-only block remains intact in the DOM and can
    // never inherit values from futures or cash-carry research scenarios.
    anchor.style.setProperty('display',shown?'':'none',shown?'':'important');
    toggle.setAttribute('aria-expanded',String(shown));
    toggle.textContent=shown?
     'Nascondi dettaglio fonte certificata · copertura ufficiale 4/8':
     'Apri dettaglio delle sole fonti certificate · 4/8 (le stime 8/8 sono sopra)';
   };
   toggle.addEventListener('click',()=>{shown=!shown;sync()});
   sync();
  }
 }catch(e){box.dataset.status='WITHHELD';box.innerHTML='<h2 class="desk-panel-title">G8 · dati non disponibili</h2>';
  console.warn('[GMFQ OIS research withheld]',String(e));}
}
function loaded(){let doc;try{doc=frame.contentDocument}catch(_){return}
 if(doc?.body)mount(doc).catch(e=>console.warn('[GMFQ OIS research withheld]',e));}
frame.addEventListener('load',loaded);
try{if(frame.contentDocument?.readyState==='complete')loaded()}catch(_){}
})();