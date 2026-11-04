'use strict';
/* Independent quality/readiness classification for Global Macro FX Quant V2.
 * "Ready for research" never means certified OIS, point-in-time FX signals,
 * or automatic promotion of a stale canonical government-rate series.
 */
const CCY=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
const AGE=(today,date)=>{
 if(typeof date!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(date))return null;
 const a=Date.parse(today+'T12:00:00Z'),b=Date.parse(date+'T12:00:00Z');
 if(!Number.isFinite(a)||!Number.isFinite(b))return null;
 return Math.round((a-b)/86400000);
};
function readiness({today,gov,govResearch,oisCore,oisResearch,macroObserved,fxPairs,sourceAudit}){
 if(!/^\d{4}-\d{2}-\d{2}$/.test(today))throw Error('valid Europe/Rome YYYY-MM-DD date required');
 const has=CCY.every(x=>Object.hasOwn(gov||{},x)&&Object.hasOwn(oisCore?.currencies||{},x)&&Object.hasOwn(oisResearch?.currencies||{},x));
 if(!has)throw Error('all eight research currencies required');
 if(oisResearch.schema!=='GMFQ_FXV2_PRICING_SNAPSHOT_V1'||
    oisResearch.ui_only!==true||oisResearch.eligible_for_fx_engine!==false)
  throw Error('V2 OIS research provenance/permissions invalid');
 const individual=CCY.map(ccy=>{
  const market=oisResearch.currencies[ccy];
  const entries=['3m','6m','12m'].map(h=>{
   const x=market.horizons?.[h];
   if(!x||typeof x.rate!=='number'||!Number.isFinite(x.rate)||x.rate<=-10||x.rate>=30||
      AGE(today,x.as_of)===null||AGE(today,x.as_of)<0)throw Error(ccy+' '+h+' missing/invalid');
   return {horizon:h,as_of:x.as_of,rate:x.rate,days_old:AGE(today,x.as_of)};
  });
  const kind=market.kind;
  if(ccy==='GBP'?(kind!=='OIS'||market.quality!=='FONTE UFFICIALE'):kind==='OIS')
    throw Error(ccy+' incorrect OIS/futures instrument classification');
  const official=oisCore.currencies[ccy];
  return {ccy,kind,quality:market.quality,
   levels:entries,
   source_dates:entries.map(v=>v.as_of),
   source_as_of:market.as_of,
   source_label_as_of_matches_one_horizon:entries.some(x=>x.as_of===market.as_of),
   source_as_of_equal_all_horizons:entries.every(x=>x.as_of===market.as_of),
   official_core_pricing_certified:official.operational_status==='GREEN_OFFICIAL'&&official.quality==='OFFICIAL_CERTIFIED',
   core_status:official.operational_status,
   government_canonical_as_of:gov[ccy].date,
   government_canonical_age_days:AGE(today,gov[ccy].date)};
 });
 const rateStale=individual.filter(x=>x.ccy==='CHF'||x.ccy==='NZD');
 const baseline=fxPairs.macro_baseline_asof;
 if(!baseline||AGE(today,baseline)===null||AGE(today,baseline)<0)throw Error('invalid FX core baseline');
 if(macroObserved.schema!=='GMFQ_MACRO_V3_G8_28PAIR_PUBLIC_OBSERVED_CONTEXT_V1'||
   macroObserved.historic_PIT_OOS_not_certified!==true||
   macroObserved.safe_to_recompute_structural_pair_theses!==false||
   macroObserved.summary?.pairs!==28||macroObserved.summary?.economic_dimensions!==24||
   macroObserved.canonical_D_macro_baseline_as_of!==baseline)
  throw Error('Macro V3 / FX Core isolation not verifiable');
 if(fxPairs.pair_count!==28)throw Error('canonical FX pair coverage != 28');
 const validBench=govResearch.schema==='GMFQ_FXV2_CHF_NZD_BENCHMARK_RESEARCH_V1'&&
  govResearch.eligible_for_fx_pair_engine===false&&govResearch.canonical_government_rates_untouched===true&&
  govResearch.NZD?.independent_xlsx_reconciled===false&&govResearch.NZD?.cross_roll_change_allowed===false;
 if(!validBench)throw Error('CHF NZD research not isolated from Core');
 const numeric=individual.reduce((n,x)=>n+x.levels.length,0);
 const reportedPages=sourceAudit.summary?.v2_pages;
 if(reportedPages!==12)throw Error('V2 page coverage must be twelve');
 const firstGrade=CCY.filter(x=>oisCore.currencies[x].quality==='OFFICIAL_CERTIFIED'&&
  oisCore.currencies[x].operational_status==='GREEN_OFFICIAL');
 const withheld=CCY.filter(x=>oisCore.currencies[x].operational_status!=='GREEN_OFFICIAL'||
  oisCore.currencies[x].quality!=='OFFICIAL_CERTIFIED');
 const returnValue={
  schema:'GMFQ_FXV2_READINESS_DUAL_TRACK_V1',as_of_rome:today,
  research:{
   state:numeric===24&&reportedPages===12?'AVAILABLE_WITH_SOURCE_QUALITY_LIMITS':'INCOMPLETE',
   website_pages:reportedPages,
   rate_pricing_horizons:numeric,
   government_currencies:individual.length,
   macro_observed_dimensions:macroObserved.summary.economic_dimensions,
   macro_pair_contexts:macroObserved.summary.pairs,
   official_ois_currencies:individual.filter(x=>x.kind==='OIS').map(x=>x.ccy),
   other_futures_or_proxy_currencies:individual.filter(x=>x.kind!=='OIS').map(x=>x.ccy),
   chf_same_date_research:govResearch.CHF?.paired_date||null,
   nzd_post_roll_research:govResearch.NZD?.latest_date||null,
   core_rates_untouched:true,
   source_as_of_mismatches:individual.filter(x=>!x.source_as_of_equal_all_horizons).map(x=>({
    ccy:x.ccy,country_as_of:x.source_as_of,horizon_as_of:[...new Set(x.source_dates)].sort()
   }))
  },
  trading_core:{
   state:'NOT_REVALIDATED_FROM_RESEARCH',
   pair_count:fxPairs.pair_count,
   baseline_macro_as_of:baseline,
   baseline_macro_age_days:AGE(today,baseline),
   baseline_was_recomputed:false,
   certified_policy_pricing_count:firstGrade.length,
   certified_policy_pricing_currencies:firstGrade,
   noncertified_policy_pricing_currencies:withheld,
   old_canonical_gov_currencies:rateStale.map(x=>({
    ccy:x.ccy,as_of:x.government_canonical_as_of,days_old:x.government_canonical_age_days
   })),
   source_data_used_for_backtests:false,
   all_source_gaps_cleared:sourceAudit.summary?.gaps===0
  },
  reading_rule:'24 G8 pricing research levels are not 24 certified OIS curves. Market-data source dates are not publication times. Macro V3 observations cannot revalidate the legacy FX signal without point-in-time tests.',
  metrics:{
   original_audit_status:sourceAudit.status,
   unresolved_source_gaps:sourceAudit.summary?.gaps,
   source_review_notes:sourceAudit.summary?.review_notes,
   price_as_of:fxPairs.price_asof
  }
 };
 return returnValue;
}
module.exports={readiness,AGE};
